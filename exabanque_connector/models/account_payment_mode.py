from odoo import fields, models


class AccountPaymentMode(models.Model):

    _inherit = "account.payment.mode"

    is_exabanque = fields.Boolean(string="Is Exabanque", default=False)
