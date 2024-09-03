import base64
import logging
import re
from datetime import datetime
from odoo.addons.base.models.res_bank import sanitize_account_number

from odoo import fields, models

_logger = logging.getLogger(__name__)


class BaseConnector(models.Model):
    """Setup recurents action and create a transactions"""

    _name = "base.connector"
    _description = "FTP Connection"

    active = fields.Boolean("Active", default=False)
    journal_id = fields.Many2one(
        "account.journal",
        string="WARNING: This setup will overwrite all existing journals in the file.",
        domain="[('company_id', '=', company_id)]",
    )
    action_type = fields.Selection(
        [
            ("lcr", "Send LCR and/or PAIN to FTP BANK"),
            ("statement", "Retrieve Statement from FTP BANK (statement)"),
            ("log", "Retrieve logs (logs)"),
        ],
        string="Action Type",
    )
    use_cron = fields.Boolean("Use Cron for new transactions ?", default=False)
    test_mode = fields.Boolean("Test Mode", default=False)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    def run_lcr(self):
        """Send LCR to FTP BANK"""
        ftp = self.env["base.ftp"].search([], limit=1)
        session = ftp.connect_sftp()
        if session:
            for transaction in self.env["log.transaction"].search(
                [("state", "=", "new"), ("action_type", "=", "lcr")]
            ):
                file_data = base64.b64decode(transaction.file_data)
                file_name = transaction.file_name
                ftp.upload_file(ftp.emission_path, file_name, file_data, session)                
                transaction.write(
                        {"state": "treated", "treatment_date": datetime.now()}
                    )

    def run_lcr_test(self):
        for transaction in self.env["log.transaction"].search(
            [("state", "=", "new"), ("action_type", "=", "lcr")]
        ):
            file_data = base64.b64decode(transaction.file_data)
            file_name = transaction.file_name
            for ftp in self.env["base.ftp"].search(
                [("company_id", "=", transaction.company_id.id)], limit=1
            ):
                ftp.upload_file(ftp.test_path, file_name, file_data)
                transaction.write({"state": "test", "treatment_date": datetime.now()})

    def check_lcr(self):
        """Check the status file"""
        _logger.info("Checking LCR files")
        ftp = self.env["base.ftp"].search([], limit=1)
        session = ftp.connect_sftp()
        if session:
            for transaction in self.env["log.transaction"].search(
                [("state", "in", ["processing", "treated"]), ("action_type", "=", "lcr")]
            ):
                file_name = transaction.file_name
                try:
                    if file_name in ftp.list_dir(ftp.process_path,session):
                        transaction.state = "processing"

                    if file_name in ftp.list_dir(ftp.error_path,session):
                        transaction.state = "error"
                        transaction.write(
                            {
                                "error_ids": [
                                    (
                                        0,
                                        0,
                                        {
                                            "name": "Error within Exabanque",
                                            "model": "base.connector",
                                            "operation": "process file",
                                            "error_message": "Found file in error path",
                                            "transaction_id": transaction.id,
                                            "timestamp": datetime.now(),
                                        },
                                    )
                                ]
                            }
                        )

                    if file_name in ftp.list_dir(ftp.success_path,session):
                        transaction.state = "success"

                except Exception as e:
                    _logger.error(f"Error checking file {file_name}: {e}")
            session.close()

    def run_statement(self):
        """Retrieve statement from FTP BANK"""
        files_to_delete = []
        _logger.info("Running statement")
        for ftp in self.env["base.ftp"].search([("company_id", "=", self.company_id.id)]):
            try:
                session = ftp.connect_sftp()
                if session:
                    # count = ftp.count_dir_elements(ftp.success_recept, session)
                    dict_files = ftp.get_all_files(ftp.success_recept, session, 'latin-1')
                    for file_name, file_data in dict_files.items():
                        try:
                            file_tmp = file_data.read()
                            file_binary = file_tmp.encode('latin-1')
                            if file_data and file_name:
                                journal_bank = self.extract_bank_journal(file_name)
                                ret = self.env["log.transaction"].create(
                                    {
                                        "action_type": "statement",
                                        "company_id": ftp.company_id.id,
                                        "file_data": base64.b64encode(file_binary),
                                        "file_name": file_name,
                                        "journal_bank_id": journal_bank.id if journal_bank else None,
                                    }
                                )
                                if ret:
                                    files_to_delete.append(file_name)
                        except Exception as e:
                            _logger.error(f"Error processing file {file_name}: {e}")

                    for file_name in files_to_delete:
                        try:
                            ftp.delete_file_by_name(ftp.success_recept, file_name, session)
                        except Exception as e:
                            _logger.error(f"Error deleting file {file_name}: {e}")

                    session.close()
            except Exception as e:
                _logger.error(f"Error connecting to FTP: {e}")

    def run_log(self):
        """Retrieve logs from FTP BANK"""
        files_to_delete = []
        _logger.info("Exabanque Beging Running log")
        for ftp in self.env["base.ftp"].search([]):
            try:
                session = ftp.connect_sftp()
                if session:
                    count = ftp.count_dir_elements(ftp.log_path, session)
                for index in range(count):
                    try:
                        file_data = ftp.get_file_data(ftp.log_path, index, session)
                        file_name = ftp.get_file_name(ftp.log_path, index, session)
                        ret = self.env["log.exabanque"].create(
                            {
                                "date": datetime.now(),
                                "company_id": ftp.company_id.id,
                                "log_file_data": base64.b64encode(file_data.encode("latin-1")),
                                "log_file_name": file_name,
                            }
                        )
                        if ret:
                            files_to_delete.append(file_name)
                    except Exception as e:
                        _logger.error(f"Error processing file {file_name}: {e}")                
                    for file_name in files_to_delete:
                        try:
                            ftp.delete_file_by_name(ftp.log_path, file_name, session)
                        except Exception as e:
                            _logger.error(f"Error deleting file {file_name}: {e}")
                session.close()
            except Exception as e:
                _logger.error(f"Error connecting to FTP: {e}")

    def _run_cron(self):
        for record in self.search([("active", "=", True)]):
            if record.action_type == "lcr":
                if record.use_cron:
                    if record.test_mode:
                        record.run_lcr_test()
                    else:
                        record.run_lcr()
                record.check_lcr()
            if record.action_type == "statement":
                record.run_statement()
            # always run log last so transaction are already created
            if record.action_type == "log":
                record.run_log()

    def run_cron(self):
        self._run_cron()

    def extract_bank_journal(self, file_name):
        """Extract the bank journal from the file name"""
        pattern = r"(\d{11})\dEUR"
        match = re.search(pattern, file_name)
        if match:
            # Extraction du numéro de compte
            account_number = match.group(1)
            journal_obj = self.env["account.journal"]
            sanitized_account_number = sanitize_account_number(account_number)

            journal = journal_obj.search(
                    [
                        ("type", "=", "bank"),
                        (
                            "bank_account_id.sanitized_acc_number",
                            "ilike",
                            sanitized_account_number,
                        ),
                    ],
                    limit=1,
                )
            if journal:
                return journal
        return False
