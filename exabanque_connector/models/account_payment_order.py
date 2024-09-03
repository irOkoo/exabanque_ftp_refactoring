import base64

from odoo import _, fields, models


class AccountPaymentOrder(models.Model):
    _inherit = "account.payment.order"

    log_transaction_id = fields.Many2one("log.transaction", string="Log Transaction")

    def open2generated(self):
        result = super().open2generated()
        if self.payment_mode_id and self.payment_mode_id.is_exabanque:
            file_data, file_name = self.generate_payment_file()
            transaction = self.env["log.transaction"].search(
                [("action_type", "=", "lcr"), ("file_name", "=", file_name)]
            )
            if not transaction:
                transaction = self.env["log.transaction"].create(
                    {
                        "action_type": "lcr",
                        "file_name": file_name,
                        "file_data": base64.b64encode(file_data),
                        "state": "new",
                        "company_id": self.company_id.id,
                        "account_payment_order_id": self.id,
                    }
                )
            self.log_transaction_id = transaction.id
            transaction.run_lcr(transaction)
            return {
                "name": _("Transaction"),
                "type": "ir.actions.act_window",
                "res_model": "log.transaction",
                "view_mode": "form",
                "res_id": transaction.id,
                "target": "current",
            }
        return result

    def action_log_transaction(self):
        self.ensure_one()
        return {
            "name": _("Transaction"),
            "type": "ir.actions.act_window",
            "res_model": "log.transaction",
            "view_mode": "form",
            "res_id": self.log_transaction_id.id,
            "target": "current",
        }
