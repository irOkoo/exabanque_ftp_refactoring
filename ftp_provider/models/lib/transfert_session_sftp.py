import fnmatch
import logging
import tempfile
from os import path

import paramiko

_logger = logging.getLogger(__name__)


class TransfertSessionSFTP:
    def __init__(
        self,
        server_host=None,
        server_port=None,
        user_login=None,
        user_password=None,
        key_type=None,
        user_key_stringio=None,
        autoaddpolicy=False,
        disabled_algorithms=None,
        allow_agent=False,
        look_for_keys=False,
    ):
        _logger.setLevel(logging.DEBUG)

        self.ssh = paramiko.SSHClient()
        if autoaddpolicy:
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Temporary
        if user_password:
            self.ssh.connect(
                hostname=server_host,
                port=server_port,
                username=user_login,
                password=user_password,
                banner_timeout=10000,
                disabled_algorithms=disabled_algorithms,
                allow_agent=allow_agent,
                look_for_keys=look_for_keys,
            )
        else:
            if key_type == "rsa_key":
                pkey = paramiko.RSAKey.from_private_key(user_key_stringio)
            elif key_type == "ed25519_key":
                pkey = paramiko.Ed25519Key.from_private_key(user_key_stringio)
            self.ssh.connect(
                hostname=server_host,
                port=server_port,
                username=user_login,
                pkey=pkey,
                banner_timeout=10000,
                disabled_algorithms=disabled_algorithms,
                allow_agent=allow_agent,
                look_for_keys=look_for_keys,
            )
        self.sftp = self.ssh.open_sftp()

    def close(self):
        self.sftp.close()
        self.ssh.close()
        logging.debug("Connection closed")

    def upload(self, data, filepath):
        with self.sftp.open(filepath, mode="w") as f:
            f.write(data)

    def download_and_read_file(self, filepath, encoding="utf-8"):
        with tempfile.TemporaryDirectory() as tmpdir:
            # tmpdir = "/tmp"
            tmp_file_path = path.join(tmpdir, path.basename(filepath))
            logging.debug(f"Temporary file: {tmp_file_path}")

            self.sftp.get(filepath, tmp_file_path)
            return open(tmp_file_path, encoding=encoding)

    def listdir(self, folder_path="/"):
        return self.sftp.listdir(folder_path)

    def delete_file(self, filepath):
        self.sftp.remove(filepath)
        logging.debug(f"Delete {filepath!r} sftp file")

    def move_file(self, filepath, target_folder_path):
        self.sftp.posix_rename(
            filepath, path.join(target_folder_path, path.basename(filepath))
        )
        logging.debug(f"Moving {filepath!r} sftp file to {target_folder_path!r}")

    def mkdir(self, folder_path):
        self.sftp.mkdir(folder_path)
        logging.debug(f"Create {folder_path!r} sftp folder")

    def rmdir(self, folder_path):
        self.sftp.rmdir(folder_path)
        logging.debug(f"Delete {folder_path!r} sftp folder")

    def get_all_files_by_matching_string(self, path, matching_string, encoding="utf-8"):
        """ Return a dict of all files in the path that match the pattern"""
        list_dir = self.listdir(path)
        file_dict = {}
        for file in list_dir:
            if "." in file and fnmatch.fnmatch(file, matching_string):
                file_dict[file] = self.download_and_read_file(path + "/" + file, encoding)
        return file_dict
