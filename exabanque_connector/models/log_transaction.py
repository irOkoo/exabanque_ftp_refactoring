import base64
from datetime import datetime
import logging
from odoo import fields, models

_logger = logging.getLogger(__name__)


class LogTransaction(models.Model):
    """Import and Export Exabanque files"""

    _name = "log.transaction"
    _description = "CEGID EXABANQUE"
    _order = "id desc"

    file_data = fields.Binary(string="File")
    file_name = fields.Char(string="File Name")

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    action_type = fields.Selection(
        [
            ("lcr", "Send LCR and/or PAIN to FTP BANK"),
            ("statement", "Retrieve Statement from FTP BANK"),
        ],
        string="Action Type",
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("treated", "Treated"),
            ("processing", "Processing"),
            ("success", "Success"),
            ("error", "Error"),
            ("test", "Test"),
        ],
        string="State",
        default="new",
    )
    treatment_date = fields.Datetime(string="Treatment Date")
    exa_log_ids = fields.One2many(
        "log.exabanque", "transaction_id", string="Exabanque Log List"
    )
    error_ids = fields.One2many("log.error", "transaction_id", string="Error List")
    account_payment_order_id = fields.Many2one(
        "account.payment.order", string="Payment Order"
    )
    journal_bank_id = fields.Many2one("account.journal", string="Bank Journal")

    def run_cron(self):
        self._run_cron()

    def _run_cron(self):
        for record in self.search([("state", "=", "new")]):
            record = record.with_company(record.company_id.id)
            if record.action_type == "statement":
                record.run_statement()

    def action_statement(self):
        self.run_statement()

    def run_statement(self):
        self.ensure_one()
        import_id = self.env["account.statement.import"].create(
            {
                "statement_file": self.file_data,
                "statement_filename": self.file_name,
            }
        )
        import_id.import_file_custom()

        if not import_id.errors:
            self.state = "success"
            self.treatment_date = datetime.now()
            self.write(
                {
                    "error_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Statement file imported successfully",
                                "transaction_id": self.id,
                                "timestamp": datetime.now(),
                            },
                        )
                    ]
                }
            )

        else:
            self.state = "error"
            self.treatment_date = datetime.now()
            self.write(
                {
                    "error_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Error while importing statement file",
                                "model": "account.statement.import",
                                "operation": "import_file_custom()",
                                "error_message": str(import_id.errors),
                                "transaction_id": self.id,
                                "timestamp": datetime.now(),
                            },
                        )
                    ]
                }
            )

    def run_lcr(self, transaction):
        """Send LCR and/or PAIN to FTP BANK"""
        file_data = base64.b64decode(transaction.file_data)
        file_name = transaction.file_name
        for ftp in self.env["base.ftp"].search(
            [("company_id", "=", transaction.company_id.id)], limit=1
        ):
            try:
                session = ftp.connect_sftp()
                ftp.upload_file(ftp.emission_path, file_name, file_data, session)
                transaction.write({"state": "treated", "treatment_date": datetime.now()})
                session.close()
            except Exception as e:
                _logger.error(f"Error while uploading file: {e}")

    def run_lcr_test(self, transaction):
        """Send LCR and/or PAIN to FTP BANK in test mode"""
        file_data = base64.b64decode(transaction.file_data)
        file_name = transaction.file_name
        for ftp in self.env["base.ftp"].search(
            [("company_id", "=", transaction.company_id.id)], limit=1
        ):
            ftp.upload_file(ftp.test_path, file_name, file_data)
            transaction.write({"state": "test", "treatment_date": datetime.now()})

    def action_lcr(self):
        base_connector = self.env["base.connector"].search(
            [("active", "=", True), ("action_type", "=", "lcr")], limit=1
        )
        if base_connector and base_connector.test_mode:
            self.run_lcr_test(self)
        else:
            self.run_lcr(self)
