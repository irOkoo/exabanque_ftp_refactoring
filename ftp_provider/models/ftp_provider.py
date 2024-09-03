import base64
import logging
from io import StringIO

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from odoo import _, fields, models
from odoo.exceptions import UserError

from .lib.transfert_session_ftp import TransfertSessionFTP
from .lib.transfert_session_sftp import TransfertSessionSFTP

_logger = logging.getLogger(__name__)


class FtpProvider(models.Model):
    _name = "ftp.provider"
    _description = "FTP Provider is basically a list of functions that you can use with your own modules"

    name = fields.Char("Name", required=True)
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    show_test_features = fields.Boolean("Show Test Features", default=False)

    protocol = fields.Selection(
        [("ftp", "FTP"), ("sftp", "SFTP")],
        string="Protocol",
        default="ftp",
    )
    server_host = fields.Char("Host")
    server_port = fields.Char("Host Port", default="21")
    user_login = fields.Char("User Login")
    password_or_key = fields.Selection(
        [
            ("password", "Password"),
            ("rsa_key", "Key - 'ssh-rsa'"),
            ("ed25519_key", "Key - 'ssh-ed25519'"),
        ],
        string="Use password or Encoded Key",
        default="password",
    )
    user_password = fields.Char("User Password")
    user_public_key_name = fields.Char("User Public Key .pub")
    user_public_key_data = fields.Binary("User Public Key .pub")
    user_private_key_name = fields.Char("User Private Key")
    user_private_key_data = fields.Binary("User Private Key")

    autoaddpolicy = fields.Boolean("Auto Add Policy", default=True)
    disabled_algorithms = fields.One2many(
        "ftp.provider.disabled.algorithms",
        "ftp_provider_id",
        string="Disabled Algorithms",
    )
    allow_agent = fields.Boolean("Allow Agent", default=True)
    look_for_keys = fields.Boolean("Look for Keys", default=True)

    # connection methods - - - - - - - - - - - - - - - - - - - - -

    # Return a new FTP session
    # /!\ /!\ Do not forget to close the session with session.close() after using it

    def connect_ftp(self):
        try:
            return TransfertSessionFTP(
                server_host=self.server_host,
                server_port=self.server_port,
                user_login=self.user_login,
                user_password=self.user_password,
            )
        except Exception as e:
            raise UserError(_("Failed to connect to FTP server:\n %s" % e))

    # Return a new SFTP session
    # /!\ /!\ Do not forget to close the session with session.close() after using it

    def connect_sftp(self):
        try:
            disabled_algorithms = None
            if self.disabled_algorithms:
                disabled_algorithms = dict(
                    keys=[
                        self.disabled_algorithms[i].name
                        for i in range(len(self.disabled_algorithms))
                    ],
                    pubkeys=[
                        self.disabled_algorithms[i].name
                        for i in range(len(self.disabled_algorithms))
                    ],
                )
            if self.password_or_key == "password":
                return TransfertSessionSFTP(
                    server_host=self.server_host,
                    server_port=self.server_port,
                    user_login=self.user_login,
                    user_password=self.user_password,
                    autoaddpolicy=self.autoaddpolicy,
                    disabled_algorithms=disabled_algorithms,
                    allow_agent=self.allow_agent,
                    look_for_keys=self.look_for_keys,
                )
            elif self.password_or_key != "password":
                return TransfertSessionSFTP(
                    server_host=self.server_host,
                    server_port=self.server_port,
                    user_login=self.user_login,
                    key_type=self.password_or_key,
                    user_key_stringio=StringIO(
                        base64.b64decode(self.user_private_key_data).decode("utf-8")
                    ),
                    autoaddpolicy=self.autoaddpolicy,
                    disabled_algorithms=disabled_algorithms,
                    allow_agent=self.allow_agent,
                    look_for_keys=self.look_for_keys,
                )

        except Exception as e:
            raise UserError(_("Failed to connect to SFTP server:\n %s" % e))

    # Return a session ftp/sftp
    # Connect to the server and return the corresponding ftp/sftp session from connect_ftp/connect_sftp or raise an error

    def connect(self):
        if self.protocol == "ftp":
            if not self.server_host:
                raise UserError(_("Please enter a valid server host"))
            elif not self.user_login:
                raise UserError(_("Please enter a valid user login"))
            elif not self.user_password:
                raise UserError(_("Please enter a valid user password"))

            session = self.connect_ftp()
            return session

        elif self.protocol == "sftp":
            if not self.server_host:
                raise UserError(_("Please enter a valid server host"))
            elif not self.server_port:
                raise UserError(_("Please enter a valid server port"))
            elif self.server_port == 21:
                raise UserError(
                    _(
                        "Please enter a valid server port, 21 is the default port for FTP not SFTP"
                    )
                )
            elif not self.user_login:
                raise UserError(_("Please enter a valid user login"))
            elif self.password_or_key == "rsa_key" and not self.user_private_key_data:
                raise UserError(_("Please generate or enter a valid RSA key"))
            elif self.password_or_key == "password" and not self.user_password:
                raise UserError(_("Please enter a valid user password"))

            session = self.connect_sftp()
            return session
        
    # Test the connection to the server

    def test_connection(self):
        session = self.connect()
        session.close()

        return True

    # path methods - - - - - - - - - - - - - - - - - - - - -

    # List all the elements in a directory

    def list_dir(self, path, session):
        return f"{path}:\n{session.listdir(path)}\n\n"

    # List all the elements in a directory, dont format the output

    def list_dir_light(self, path, session):
        return session.listdir(path)

    # Count the number of elements in a directory

    def count_dir_elements(self, path, session):
        return len(session.listdir(path))

    # file methods - - - - - - - - - - - - - - - - - - - - - - - -

    # Get the data of a file from the server
    # /!\ /!\ Do not forget to convert to StringIO and base64 encode the returned data before storing it in a binary field
    # For example: base64.b64encode(StringIO(returned_data).read().encode("utf-8"))

    def get_file_data(self, path, index, session, encoding="utf-8"):
        try:
            return session.download_and_read_file(
                path + "/" + self.get_file_name(path, index, session),
                encoding=encoding,
            ).read()

        except Exception as e:
            raise UserError(_("Failed to download file:\n %s" % e))

    # Get the name of a file from the server

    def get_file_name(self, path, index, session):
        return session.listdir(path)[index]

    # Delete a file from the server with it's name

    def delete_file_by_name(self, path, file_name, session):
        try:
            session.delete_file(path + "/" + file_name)

        except Exception as e:
            raise UserError(_("Failed to delete file:\n %s" % e))

    # Delete a file from the server with it's index

    def delete_file_by_index(self, path, index, session):
        try:
            session.delete_file(path + "/" + self.get_file_name(path, index, session))

        except Exception as e:
            raise UserError(_("Failed to delete file:\n %s" % e))

    # Upload a file to the server
    # /!\ /!\ Do not forget to decode the data from a binary field before uploading it
    # For example: base64.b64decode(data).decode("utf-8")

    def upload_file(self, path, filename, data, session):
        try:
            session.upload(data, path + "/" + filename)

        except Exception as e:
            raise UserError(_("Failed to upload file:\n %s" % e))

    # Move a file to a new path within the server
    # Can also copy a file if keep_old_file is True

    def move_file(self, path, new_path, filename, session):
        try:
            session.move_file(path + "/" + filename, new_path)

        except Exception as e:
            raise UserError(_("Failed to move file:\n %s" % e))

    # Download and return a list of all files in a path that name's match a string.
    # Ex: "*.txt" will return all txt files
    # Ex: "*2021*" will return all files with 2021 in their name
    # /!\ /!\ Do not forget to convert to StringIO and base64 encode the returned data before storing it in a binary field
    # return file_datas, file_names

    def get_all_files_by_matching_string(
        self, path, matching_string, session, encoding="utf-8"
    ):
        try:
            files = session.get_all_files_by_matching_string(
                path, matching_string, encoding
            )
            return files

        except Exception as e:
            raise UserError(_("Failed to get files:\n %s" % e))

    # folder methods - - - - - - - - - - - - - - - - - - - - - -

    # Create a folder in the server

    def mkdir(self, path, folder_name, session):
        try:
            session.mkdir(path + "/" + folder_name)
        except Exception as e:
            raise UserError(_("Failed to create folder:\n %s" % e))

    # Delete a folder in the server

    def rmdir(self, path, folder_name, session):
        try:
            session.rmdir(path + "/" + folder_name)

        except Exception as e:
            raise UserError(_("Failed to delete folder:\n %s" % e))

    # actions ---------------------------------------------------------------------

    # Odoo action to test the connection

    def action_test_connection(self):
        self.test_connection()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": _("Connection successfully established"),
                "type": "success",
            },
        }

    # Odoo action to generate key using 'ssh-rsa' algorithm

    def action_generate_ssh_rsa_key(self):
        if self.user_public_key_data and self.user_private_key_data:
            raise UserError(_("Key already exists"))
        else:
            if self.password_or_key != "rsa_key":
                self.password_or_key = "rsa_key"
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            private_key = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
            public_key = key.public_key().public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH,
            )

            self.user_private_key_data = base64.b64encode(private_key)
            self.user_public_key_data = base64.b64encode(public_key)
            self.user_private_key_name = "id_rsa"
            self.user_public_key_name = "id_rsa.pub"
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "message": _("Key successfully generated, please refresh the page"),
                    "type": "success",
                },
            }

    # Odoo action to generate key using 'ssh-ed25519' algorithm

    def action_generate_ssh_ed25519_key(self):
        if self.user_public_key_data and self.user_private_key_data:
            raise UserError(_("Key already exists"))
        else:
            if self.password_or_key != "ed25519_key":
                self.password_or_key = "ed25519_key"
            key = Ed25519PrivateKey.generate()
            private_key = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.NoEncryption(),
            )
            public_key = key.public_key().public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH,
            )

            self.user_private_key_data = base64.b64encode(private_key)
            self.user_public_key_data = base64.b64encode(public_key)
            self.user_private_key_name = "id_ed25519"
            self.user_public_key_name = "id_ed25519.pub"
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "message": _("Key successfully generated, please refresh the page"),
                    "type": "success",
                },
            }

    # Odoo action to show/hide the test features

    def action_show_test_features(self):
        self.show_test_features = not self.show_test_features

    # tests ---------------------------------------------------------------------

    # this part is reserved for testing purposes
    # you can access thoses function by clicking on the "Show Test Features" button
    # in Odoo Technical Settings > FTP Provider > Configuration

    test_text = fields.Text("Text", readonly=True)
    test_path = fields.Char("Path", default="/", readonly=False)
    test_path_secondary = fields.Char("Secondary Path", default="/test", readonly=False)
    test_index = fields.Integer("Index", default="0", readonly=False)
    test_foldername = fields.Char("Folder Name", readonly=False)
    test_filename = fields.Char("File Name", readonly=False)
    test_filedata = fields.Binary("File Data", readonly=False)

    # Test: List all directories at test_path
    
    def test_list_dir(self):
        session = self.connect()
        self.test_text = self.list_dir(self.test_path, session)
        session.close()

    # Test: Count all elements at test_path

    def test_count_dir_elements(self):
        session = self.connect()
        self.test_text = self.count_dir_elements(self.test_path, session)
        session.close()

    # Test: Encode to base64 the file found a test_path index test_index

    def test_get_file_data(self):
        session = self.connect()
        self.test_filedata = base64.b64encode(
            StringIO(self.get_file_data(self.test_path, self.test_index, session))
            .read()
            .encode("utf-8")
        )
        session.close()

    # Test: Return the name of the file at test_path index test_index

    def test_get_file_name(self):
        session = self.connect()
        self.test_filename = self.get_file_name(
            self.test_path, self.test_index, session
        )
        session.close()

    # Test: Delete the file at test_path with the name test_filename

    def test_delete_file_by_name(self):
        session = self.connect()
        self.delete_file_by_name(self.test_path, self.test_filename, session)
        session.close()

    # Test: Delete the file at test_path with index test_index

    def test_delete_file_by_index(self):
        session = self.connect()
        self.delete_file_by_index(self.test_path, self.test_index, session)
        session.close()

    # Test: Upload a file with test_filename name to test_path

    def test_upload_file(self):
        session = self.connect()
        data = base64.b64decode(self.test_filedata).decode("utf-8")
        self.upload_file(self.test_path, self.test_filename, data, session)
        session.close()

    # Test: Make a directory at test_path with test_foldername name

    def test_mkdir(self):
        session = self.connect()
        self.mkdir(self.test_path, self.test_foldername, session)
        session.close()

    # Test: Remove a directory at test_path with test_foldername name

    def test_rmdir(self):
        session = self.connect()
        self.rmdir(self.test_path, self.test_foldername, session)
        session.close()

    # Test: Move a file at test_path with test_filename name to test_path_secondary

    def test_move_file(self):
        session = self.connect()
        self.move_file(
            self.test_path,
            self.test_path_secondary,
            self.test_filename,
            session=session,
        )
        session.close()

    # Test: Get all files that matched test_filename name at test_path and return a list of all files with matching names in test_text

    def test_get_all_files_by_matching_string(self):
        session = self.connect()
        files = self.get_all_files_by_matching_string(
            self.test_path, self.test_filename, session
        )
        self.test_text = str(list(files.keys()))
        session.close()
