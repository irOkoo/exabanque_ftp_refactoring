import base64
import logging

from odoo import _, fields, models
from odoo.addons.base.models.res_bank import sanitize_account_number

logger = logging.getLogger(__name__)


class AccountStatementImport(models.TransientModel):
    _inherit = "account.statement.import"

    errors = fields.Text(string="Error", readonly=True)

    def import_file_custom(self):
        """Process the file chosen in the wizard, create bank statement(s)
        and return an action."""
        self.ensure_one()
        result = {
            "statement_ids": [],
            "notifications": [],
        }
        logger.info("Start to import bank statement file %s", self.statement_filename)
        file_data = base64.b64decode(self.statement_file)
        import_file = self.import_single_file_custom(file_data, result)
        if not import_file:
            return None
        logger.debug("result=%s", result)
        if not result["statement_ids"]:
            self.errors = _(
                "You have already imported this file, or this file "
                "only contains already imported transactions."
            )
            return None
        self.env["ir.attachment"].create(self._prepare_create_attachment(result))
        if self.env.context.get("return_regular_interface_action"):
            action = (
                self.env.ref("account.action_bank_statement_tree").sudo().read([])[0]
            )
            if len(result["statement_ids"]) == 1:
                action.update(
                    {
                        "view_mode": "form,tree",
                        "views": False,
                        "res_id": result["statement_ids"][0],
                    }
                )
            else:
                action["domain"] = [("id", "in", result["statement_ids"])]
        else:
            # dispatch to reconciliation interface
            lines = self.env["account.bank.statement.line"].search(
                [("statement_id", "in", result["statement_ids"])]
            )
            action = {
                "type": "ir.actions.client",
                "tag": "bank_statement_reconciliation_view",
                "context": {
                    "statement_line_ids": lines.ids,
                    "company_ids": self.env.user.company_ids.ids,
                    "notifications": result["notifications"],
                },
            }
        return action

    def import_single_file_custom(self, file_data, result):
        parsing_data = self.with_context(active_id=self.ids[0])._parse_file(file_data)
        if not isinstance(parsing_data, list):  # for backward compatibility
            parsing_data = [parsing_data]
        logger.info(
            "Bank statement file %s contains %d accounts",
            self.statement_filename,
            len(parsing_data),
        )
        i = 0
        for single_statement_data in parsing_data:
            i += 1
            logger.debug(
                "account %d: single_statement_data=%s", i, single_statement_data
            )
            self.import_single_statement_custom(single_statement_data, result)

    def import_single_statement_custom(self, single_statement_data, result):
        if not isinstance(single_statement_data, tuple):
            self.errors = _(
                "The parsing of the statement file returned an invalid result."
            )
            return None
        currency_code, account_number, stmts_vals = single_statement_data
        # Check raw data
        if not self._check_parsed_data(stmts_vals):
            return False
        if not currency_code:
            self.errors = _("Missing currency code in the bank statement file.")
            return None
        # account_number can be None (example : QIF)
        currency = self._match_currency(currency_code)
        journal = self._match_journal_custom(account_number, currency)
        if not journal:
            return None
        if not journal.default_account_id:
            self.errors = (
                _("The Bank Accounting Account in not set on the " "journal '%s'.")
                % journal.display_name
            )
            return None
        # Prepare statement data to be used for bank statements creation
        stmts_vals = self._complete_stmts_vals(stmts_vals, journal, account_number)
        # Create the bank statements
        self._create_bank_statements(stmts_vals, result)
        # Now that the import worked out, set it as the bank_statements_source
        # of the journal
        if journal.bank_statements_source != "file_import":
            # Use sudo() because only 'account.group_account_manager'
            # has write access on 'account.journal', but 'account.group_account_user'
            # must be able to import bank statement files
            journal.sudo().write({"bank_statements_source": "file_import"})

    def _match_journal_custom(self, account_number, currency):
        """Find the journal that matches the account number and currency."""
        company = self.env.company
        journal_obj = self.env["account.journal"]
        if not account_number:  # exemple : QIF
            if not self.env.context.get("journal_id"):
                self.errors = _(
                    "The format of this bank statement file doesn't "
                    "contain the bank account number, so you must "
                    "start the wizard from the right bank journal "
                    "in the dashboard."
                )
                return None
            journal = journal_obj.browse(self.env.context.get("journal_id"))
        else:
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

            if not journal:
                bank_accounts = self.env["res.partner.bank"].search(
                    [
                        ("partner_id", "=", company.partner_id.id),
                        ("sanitized_acc_number", "ilike", sanitized_account_number),
                    ],
                    limit=1,
                )
                if bank_accounts:
                    self.errors = _(
                        "The bank account with number '%s' exists in Odoo "
                        "but it is not set on any bank journal. You should "
                        "set it on the related bank journal. If the related "
                        "bank journal doesn't exist yet, you should create "
                        "a new one."
                    ) % (account_number,)
                    return None
                else:
                    self.errors = _(
                        "Could not find any bank account with number '%s' "
                        "linked to partner '%s'. You should create the bank "
                        "account and set it on the related bank journal. "
                        "If the related bank journal doesn't exist yet, you "
                        "should create a new one."
                    ) % (account_number, company.partner_id.display_name)
                    return None

        # We support multi-file and multi-statement in a file
        # so self.env.context.get('journal_id') doesn't mean much
        # I don't think we should really use it
        journal_currency = journal.currency_id or company.currency_id
        if journal_currency != currency:
            self.errors = _(
                "The currency of the bank statement (%s) is not the same as the "
                "currency of the journal '%s' (%s)."
            ) % (currency.name, journal.display_name, journal_currency.name)
            return None
        return journal
