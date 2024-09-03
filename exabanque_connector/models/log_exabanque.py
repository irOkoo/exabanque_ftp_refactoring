import base64
from xml.etree import ElementTree as ET

from odoo import api, fields, models


class LogExabanque(models.Model):

    _name = "log.exabanque"
    _description = "Log Exabanque"
    _order = "date desc"

    date = fields.Datetime(string="Date")

    log_file_name = fields.Char(string="File Name")
    log_file_data = fields.Binary(string="File Data")

    direction = fields.Selection(
        [
            ("emission", "Emission"),
            ("reception", "Reception"),
            ("import", "Import"),
        ],
        string="Direction",
    )
    directory = fields.Char(string="Directory")
    file_name = fields.Char(string="File Name")
    com_ref = fields.Char(string="Company Reference")
    result = fields.Selection(
        [
            ("ok", "OK"),
            ("nok", "Not OK"),
        ],
        string="Result",
    )
    result_error_code = fields.Text(string="Result Error")
    report = fields.Text(string="Report")

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.user.company_id,
    )
    transaction_id = fields.Many2one("log.transaction", string="Transaction")

    def parse_log_file(self, file_content):
        # Dummy function to parse the log file and extract necessary information
        # Implement the actual logic to parse the log file and return a dictionary of the parsed data
        # Example: Extracting result and transaction_id (adapt according to actual file structure)
        root = ET.fromstring(file_content)

        # Initialize a dictionary to hold parsed data
        parsed_data = {
            "log_file_name": None,  # Assume you can determine this from the context or pass as a parameter
            "direction": None,
            "directory": None,
            "file_name": None,
            "com_ref": None,
            "result": None,
            "result_error_code": None,
            "report": None,
        }

        # Extract information from XML
        parsed_data["direction"] = root.findtext(".//sens")
        parsed_data["directory"] = root.findtext(".//repertoire")
        parsed_data["file_name"] = root.findtext(".//fichier")
        parsed_data["com_ref"] = root.findtext(".//com_ref")
        result = root.findtext(".//resultat")
        if result.startswith("OK"):
            parsed_data["result"] = "ok"
        elif result.startswith("NOK"):
            parsed_data["result"] = "nok"
            parsed_data["result_error_code"] = int(result[3:])
        parsed_data["report"] = root.findtext(".//rapport")

        return parsed_data

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Decode and parse the file data if present
            if "log_file_data" in vals:
                file_content = base64.b64decode(vals["log_file_data"]).decode("latin-1")
                parsed_data = self.parse_log_file(file_content)
                vals.update(parsed_data)
                transaction_model = self.env["log.transaction"]
                transaction = transaction_model.search(
                    [("file_name", "=", vals.get("file_name"))]
                )
                if transaction:
                    vals["transaction_id"] = transaction.id
        return super().create(vals_list)
