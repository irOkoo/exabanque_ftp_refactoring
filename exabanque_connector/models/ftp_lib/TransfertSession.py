import io
import logging
import tempfile
from ftplib import FTP
from os import path

import paramiko

_logger = logging.getLogger(__name__)


class TransfertSession:
    def __init__(
        self,
        protocol=None,
        server_host=None,
        server_port=None,
        user_login=None,
        user_password=None,
        user_rsa_key_stringio=None,
        user_certificat=None,
        root_certificat=None,
        autoaddpolicy=False,
        disabled_algorithms=None,
        allow_agent=False,
        look_for_keys=False,
    ):
        self.protocol = protocol
        _logger.setLevel(logging.DEBUG)

        if self.protocol == "ftps":
            self.ftps = FTP(
                host=server_host,
                user=user_login,
                passwd=user_password,
            )

        if self.protocol == "sftp":
            self.ssh = paramiko.SSHClient()
            if autoaddpolicy:
                self.ssh.set_missing_host_key_policy(
                    paramiko.AutoAddPolicy()
                )  # Temporary
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
            elif user_rsa_key_stringio:
                pkey = paramiko.RSAKey.from_private_key(user_rsa_key_stringio)
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
        if self.protocol == "ftps":
            self.ftps.quit()

        if self.protocol == "sftp":
            self.sftp.close()
            self.ssh.close()
        logging.debug("Connection closed")

    # def _mkdir_if_not_exists(self, folder_path):
    #     logging.debug(f'_mkdir_if_not_exists: {folder_path}')
    #     if self.protocol == 'ftps':
    #         save_pwd = self.ftps.pwd()
    #         foldername_list = path.split(folder_path.strip('/'))[1:]
    #         self.ftps.cwd(path.dirname('/' + foldername_list[0]))
    #         for folder_name in foldername_list:
    #             if folder_name not in self.ftps.nlst():
    #                 self.ftps.mkd(folder_name)

    #             self.ftps.cwd(folder_name)

    #         self.ftps.cwd(save_pwd)

    #     elif self.protocol == 'sftp':
    #         save_cwd = self.sftp.getcwd()
    #         folder_list = [folder for folder in folder_path.split('/') if folder]
    #         for folder_name in folder_list:
    #             if folder_name not in self.sftp.listdir():
    #                 self.sftp.mkdir(folder_name)

    #             self.sftp.chdir(folder_name)

    #         self.sftp.chdir(save_cwd)

    def upload(self, data, filepath):
        # self._mkdir_if_not_exists(path.dirname(filepath))
        if self.protocol == "ftps":
            self.ftps.storlines(f"STOR {filepath}", io.BytesIO(data.encode("utf8")))

        elif self.protocol == "sftp":
            with self.sftp.open(filepath, mode="w") as f:
                f.write(data)

    def download_and_read_file(self, filepath, encoding="utf-8"):
        with tempfile.TemporaryDirectory() as tmpdir:
            # tmpdir = 'C://tmp'
            tmp_file_path = path.join(tmpdir, path.basename(filepath))
            logging.debug(f"Temporary file: {tmp_file_path}")

            if self.protocol == "ftps":
                self.ftps.retrbinary(
                    f"RETR {filepath}", open(tmp_file_path, "wb").write
                )
                return open(tmp_file_path, encoding=encoding)

            elif self.protocol == "sftp":
                self.sftp.get(filepath, tmp_file_path)
                return open(tmp_file_path, encoding=encoding)

    def listdir(self, folder_path="/"):
        if self.protocol == "ftps":
            return self.ftps.nlst(folder_path)

        elif self.protocol == "sftp":
            return self.sftp.listdir(folder_path)

    def delete_file(self, filepath):
        if self.protocol == "ftps":
            logging.debug(f"Delete {filepath!r} ftp file")
            self.ftps.delete(path.basename(filepath))

        elif self.protocol == "sftp":
            logging.debug(f"Delete {filepath!r} sftp file")
            self.sftp.remove(filepath)

    def move_file(self, filepath, target_folder_path):
        # self._mkdir_if_not_exists(target_folder_path)
        if self.protocol == "ftps":
            logging.debug(f"Moving {filepath!r} ftp file to {target_folder_path!r}")
            self.ftps.rename(
                "/" + filepath,
                "/" + path.join(target_folder_path, path.basename(filepath)),
            )

        elif self.protocol == "sftp":
            logging.debug(f"Moving {filepath!r} sftp file to {target_folder_path!r}")
            self.sftp.posix_rename(
                filepath, path.join(target_folder_path, path.basename(filepath))
            )

    def get_all_files(self, path, encoding="utf-8"):
        """ Return a dict of all files in the path"""
        list_dir = self.sftp.listdir(path)
        for i in list_dir:
            lstatout = str(self.sftp.lstat(path+'/'+i)).split()[0]
            if lstatout[0] == 'd':
                list_dir.remove(i)
        file_dict = {}
        for file in list_dir:
            file_dict[file] = self.download_and_read_file(path + "/" + file, encoding)
        return file_dict
