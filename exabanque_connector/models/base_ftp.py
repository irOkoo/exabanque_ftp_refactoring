import base64
from io import StringIO

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .ftp_lib.TransfertSession import TransfertSession
import logging

_logger = logging.getLogger(__name__)


# All algorithms supported by paramiko
# ssh-ed25519
# ecdsa-sha2-nistp256
# ecdsa-sha2-nistp384
# ecdsa-sha2-nistp521
# ssh-rsa
# rsa-sha2-512
# rsa-sha2-256
# ssh-dss
class BaseFTP(models.Model):
    _name = "base.ftp"
    _description = "Exalog FTP Configuration"

    protocol = fields.Selection(
        [("none", "None"), ("ftps", "FTPS"), ("sftp", "SFTP")],
        string="Protocol",
        default="none",
    )
    autoaddpolicy = fields.Boolean("Auto Add Policy", default=False)
    disabled_algorithms = fields.One2many(
        "base.ftp.disabled.algorithms", "ftp_id", string="Disabled Algorithms"
    )
    allow_agent = fields.Boolean("Allow Agent")
    look_for_keys = fields.Boolean("Look for Keys")
    server_host = fields.Char("Host")
    server_port = fields.Char("Host Port")

    user_login = fields.Char("User Login")
    password_or_rsa_key = fields.Selection(
        [("password", "Password"), ("rsa_key", "RSA Key")],
        string="Use password or RSA Key",
    )
    user_password = fields.Char("User Password")
    user_rsa_public_key_name = fields.Char("User RSA Public Key .pub")
    user_rsa_public_key_data = fields.Binary("User RSA Public Key .pub")
    user_rsa_private_key_name = fields.Char("User RSA Private Key")
    user_rsa_private_key_data = fields.Binary("User RSA Private Key")

    user_certificat = fields.Binary("User Certificat .pfx or .cer")
    root_certificat = fields.Binary("Exalog Root Certificat .cer")

    followers = fields.Many2many(
        "res.partner",
        string="Default Followers",
        default=lambda self: self.env["base.ftp"].get_followers(),
    )
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )

    main_path = fields.Char("Main Path", default="/")

    # export from exabanque into odoo paths
    export_path = fields.Char("Export Path", compute="_compute_export_path", store=True)

    success_recept = fields.Char("Success Recept : retrieve cfonb files", compute="_compute_success_recept", store=True)

    log_path = fields.Char("Log Path", compute="_compute_log_path", store=True)

    # import from odoo into exabanque paths
    emission_path = fields.Char(
        "Emission Path", compute="_compute_emission_path", store=True
    )
    import_path = fields.Char("Import Path", compute="_compute_import_path", store=True)

    # process paths
    process_path = fields.Char(
        "Process Path", compute="_compute_process_path", store=True
    )
    success_path = fields.Char(
        "Success Path", compute="_compute_success_path", store=True
    )
    error_path = fields.Char("Error Path", compute="_compute_error_path", store=True)
    test_path = fields.Char("Test Path", compute="_compute_test_path", store=True)

    @api.depends("main_path")
    def _compute_success_recept(self):
        for record in self:
            if record.main_path[-1] == "/":
                record.success_recept = record.main_path + "success_recept"
            else:
                record.success_recept = record.main_path + "/success_recept"

    @api.depends("main_path")
    def _compute_export_path(self):
        for record in self:
            if record.main_path[-1] == "/":
                record.export_path = record.main_path + "export"
            else:
                record.export_path = record.main_path + "/export"

    @api.depends("main_path")
    def _compute_log_path(self):
        for record in self:
            if record.main_path[-1] == "/":
                record.log_path = record.main_path + "log"
            else:
                record.log_path = record.main_path + "/log"

    @api.depends("main_path")
    def _compute_emission_path(self):
        for record in self:
            if record.main_path[-1] == "/":
                record.emission_path = record.main_path + "emission"
            else:
                record.emission_path = record.main_path + "/emission"

    @api.depends("main_path")
    def _compute_import_path(self):
        for record in self:
            if record.main_path[-1] == "/":
                record.import_path = record.main_path + "import/forecast"
            else:
                record.import_path = record.main_path + "/import/forecast"

    @api.depends("main_path")
    def _compute_process_path(self):
        for record in self:
            if record.main_path[-1] == "/":
                record.process_path = record.main_path + "process"
            else:
                record.process_path = record.main_path + "/process"

    @api.depends("main_path")
    def _compute_success_path(self):
        for record in self:
            if record.main_path[-1] == "/":
                record.success_path = record.main_path + "success"
            else:
                record.success_path = record.main_path + "/success"

    @api.depends("main_path")
    def _compute_error_path(self):
        for record in self:
            if record.main_path[-1] == "/":
                record.error_path = record.main_path + "error"
            else:
                record.error_path = record.main_path + "/error"

    @api.depends("main_path")
    def _compute_test_path(self):
        for record in self:
            if record.main_path[-1] == "/":
                record.test_path = record.main_path + "test"
            else:
                record.test_path = record.main_path + "/test"

    def get_followers(self):
        pass

    def connect_ftps(self):
        return TransfertSession(
            protocol=self.protocol,
            server_host=self.server_host,
            user_login=self.user_login,
            user_password=self.user_password,
        )

    def connect_sftp(self):
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
        if self.password_or_rsa_key == "password":
            return TransfertSession(
                protocol=self.protocol,
                server_host=self.server_host,
                server_port=self.server_port,
                user_login=self.user_login,
                user_password=self.user_password,
                autoaddpolicy=self.autoaddpolicy,
                disabled_algorithms=disabled_algorithms,
                allow_agent=self.allow_agent,
                look_for_keys=self.look_for_keys,
            )
        elif self.password_or_rsa_key == "rsa_key":
            return TransfertSession(
                protocol=self.protocol,
                server_host=self.server_host,
                server_port=self.server_port,
                user_login=self.user_login,
                user_rsa_key_stringio=StringIO(
                    base64.b64decode(self.user_rsa_private_key_data).decode("utf-8")
                ),
                autoaddpolicy=self.autoaddpolicy,
                disabled_algorithms=disabled_algorithms,
                allow_agent=self.allow_agent,
                look_for_keys=self.look_for_keys,
            )
        else:
            raise UserError(_("Please select a valid login method"))

    def test_connection(self):
        if not self.protocol or self.protocol == "none":
            raise UserError(_("Please select a valid protocol"))

        if self.protocol == "ftps":
            if not self.server_host:
                raise UserError(_("Please enter a valid server host"))
            elif not self.user_login:
                raise UserError(_("Please enter a valid user login"))
            elif not self.user_password:
                raise UserError(_("Please enter a valid user password"))

            try:
                self.connect_ftps()

            except Exception as e:
                raise UserError(_("Connection failed:\n %s" % e))

        elif self.protocol == "sftp":
            if not self.server_host:
                raise UserError(_("Please enter a valid server host"))
            elif not self.server_port:
                raise UserError(_("Please enter a valid server port"))
            elif not self.user_login:
                raise UserError(_("Please enter a valid user login"))
            elif not self.password_or_rsa_key:
                raise UserError(_("Please select a valid login method"))
            elif (
                self.password_or_rsa_key == "rsa_key"
                and not self.user_rsa_private_key_data
            ):
                raise UserError(_("Please generate a valid RSA key"))
            elif self.password_or_rsa_key == "password" and not self.user_password:
                raise UserError(_("Please enter a valid user password"))

            try:
                self.connect_sftp()

            except Exception as e:
                if self.server_port == 21:
                    raise UserError(
                        _(
                            "Connection failed:\n Port 21 is reserved for ftps, please use port 22 for sftp."
                        )
                    )

                raise UserError(_("Connection failed:\n %s" % e))

        return True

    def action_test_connection(self):
        if self.test_connection():
            raise ValidationError(_("Connection successfully established!"))

    def action_list_root_dir(self):
        """List the root directory of the server"""

        if self.protocol == "ftps":
            dir_list = f'Root:\n{self.connect_ftps().listdir("/")[2:]}\n\n'
            raise ValidationError(dir_list)

        elif self.protocol == "sftp":
            dir_list = f'Root:\n{self.connect_sftp().listdir("/")}\n\n'
            raise ValidationError(dir_list)

    def action_list_main_dir(self):
        """List the main directory of the server"""

        if self.protocol == "ftps":
            dir_list = f"{self.main_path}:\n{self.connect_ftps().listdir(self.main_path)[2:]}\n\n"
            raise ValidationError(dir_list)

        elif self.protocol == "sftp":
            dir_list = (
                f"{self.main_path}:\n{self.connect_sftp().listdir(self.main_path)}\n\n"
            )
            raise ValidationError(dir_list)

    def list_dir(self, path, session=None):
        if self.protocol == "ftps":
            return f"{path}:\n{self.connect_ftps().listdir(path)[2:]}\n\n"

        elif self.protocol == "sftp":
            if not session:
                session = self.connect_sftp()
            return f"{path}:\n{session.listdir(path)}\n\n"

    def count_dir_elements(self, path, session=None):
        if self.protocol == "ftps":
            return len(self.connect_ftps().listdir(path)[2:])

        elif self.protocol == "sftp":
            if not session:
                session = self.connect_sftp()
            return len(session.listdir(path))

    def get_file_data(self, path, index, session=None):
        """Download a file from the server"""
        try:
            if self.protocol == "ftps":
                return (
                    self.connect_ftps()
                    .download_and_read_file(
                        path + "/" + self.get_file_name(path, index)
                    )
                    .read()
                )

            elif self.protocol == "sftp":
                if not session:
                    session = self.connect_sftp()
                return (
                    session
                    .download_and_read_file(
                        path + "/" + self.get_file_name(path, index, session),
                        encoding="latin-1",
                    )
                    .read()
                )

        except Exception as e:
            raise UserError(_("Failed to download file:\n %s" % e))

    def get_file_name(self, path, index, session=None):
        """Get the name of a file from the server"""

        if self.protocol == "ftps":
            return self.connect_ftps().listdir(path)[2 + index]

        elif self.protocol == "sftp":
            if not session:
                session = self.connect_sftp()
            return session.listdir(path)[index]

    def delete_file_by_name(self, directory, file_name, session):
        try:
            file_path = f"{directory}/{file_name}"
            session.delete_file(file_path)
        except Exception as e:
            _logger.error(f"Error deleting file {file_path}: {e}")    

    def delete_file(self, path, index, session=None):
        """Delete a file from the server"""

        try:
            if self.protocol == "ftps":
                self.connect_ftps().delete_file(
                    path + "/" + self.get_file_name(path, index)
                )

            elif self.protocol == "sftp":
                if not session:
                    session = self.connect_sftp()
                session.delete_file(
                    path + "/" + self.get_file_name(path, index, session)
                )

        except Exception as e:
            raise UserError(_("Failed to delete file after download:\n %s" % e))

    def upload_file(self, path, filename, data, session=None):
        """Upload a file to the server"""

        try:
            if self.protocol == "ftps":
                self.connect_ftps().upload(data, path + "/" + filename)

            elif self.protocol == "sftp":
                if not session:
                    session = self.connect_sftp()
                session.upload(data, path + "/" + filename)

        except Exception as e:
            raise UserError(_("Failed to upload file:\n %s" % e))

    def get_all_files(
        self, path, session, encoding="utf-8"
    ):
        try:
            files = session.get_all_files(
                path, encoding
            )
            return files

        except Exception as e:
            raise UserError(_("Failed to get files:\n %s" % e))

    def generate_rsa_key(self):
        # python code that generate a rsa key if none exist in self.user_certificat and
        # store the .pub in self.user_rsa_public_key_data and the private key in self.user_rsa_private_key_data
        # public key must be stored in a .pub file with openSSH format
        # plus generate filenames for the keys with an id_rsa prefix
        # desired rsa key size is 2048
        # data stored in fields must be base64 encoded

        if self.user_rsa_public_key_data and self.user_rsa_private_key_data:
            raise UserError(_("RSA Key already exists"))
        else:
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

            self.user_rsa_private_key_data = base64.b64encode(private_key)
            self.user_rsa_public_key_data = base64.b64encode(public_key)
            self.user_rsa_private_key_name = "id_rsa"
            self.user_rsa_public_key_name = "id_rsa.pub"
