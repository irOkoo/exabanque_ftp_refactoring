import fnmatch
import io
import logging
import tempfile
from ftplib import FTP
from os import path

_logger = logging.getLogger(__name__)


class TransfertSessionFTP:
    def __init__(
        self,
        server_host=None,
        server_port=None,
        user_login=None,
        user_password=None,
    ):
        _logger.setLevel(logging.DEBUG)

        self.ftp = FTP()
        
        self.ftp.connect(
            host=server_host,
            port=int(server_port),
        )

        self.ftp.login(
            user=user_login,
            passwd=user_password,
        )

    def close(self):
        self.ftp.quit()
        logging.debug("Connection closed")

    def upload(self, data, filepath):
        self.ftp.storlines(f"STOR {filepath}", io.BytesIO(data.encode("utf-8")))

    def download_and_read_file(self, filepath, encoding="utf-8"):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file_path = path.join(tmpdir, path.basename(filepath))
            logging.debug(f"Temporary file: {tmp_file_path}")

            self.ftp.retrbinary(f"RETR {filepath}", open(tmp_file_path, "wb").write)
            return open(tmp_file_path, encoding=encoding)

    def listdir(self, folder_path="/"):
        return self.ftp.nlst(folder_path)

    def delete_file(self, filepath):
        self.ftp.delete(filepath)
        logging.debug(f"Delete {filepath!r} ftp file")

    def move_file(self, filepath, target_folder_path):
        self.ftp.rename(
            "/" + filepath,
            "/" + path.join(target_folder_path, path.basename(filepath)),
        )
        logging.debug(f"Moving {filepath!r} ftp file to {target_folder_path!r}")

    def mkdir(self, folder_path):
        self.ftp.mkd(folder_path)
        logging.debug(f"Create {folder_path!r} ftp folder")

    def rmdir(self, folder_path):
        self.ftp.rmd(folder_path)
        logging.debug(f"Delete {folder_path!r} ftp folder")

    def get_all_files_by_matching_string(self, path, matching_string, encoding="utf-8"):
        """ Return a dict of all files in the path that match the pattern"""
        list_dir = self.listdir(path)
        file_dict = {}
        for file in list_dir:
            if "." in file and fnmatch.fnmatch(file, matching_string):
                file_dict[file] = self.download_and_read_file(path + "/" + file, encoding)
        return file_dict
