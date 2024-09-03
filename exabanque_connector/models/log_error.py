import psycopg2
from markupsafe import Markup
from odoo import SUPERUSER_ID, _, api, fields, models, registry


class LogError(models.Model):
    """Dedicated model to log synchronization Exalog errors"""

    _inherit = ["mail.thread", "mail.activity.mixin"]
    _name = "log.error"
    _description = "Exalog Synchronization Errors"
    _order = "timestamp desc"

    model = fields.Char(string="From Model")
    operation = fields.Char(string="Operation")
    name = fields.Char(string="Name")
    error_message = fields.Text(string="Error Message")
    timestamp = fields.Datetime(
        string="Timestamp", default=lambda self: fields.Datetime.now()
    )
    followers_ids = fields.Many2many(
        "res.partner",
        string="Default Followers",
        default=lambda self: self.env["base.ftp"].get_followers(),
    )  # to do : add to base.sftp
    transaction_id = fields.Many2one("log.transaction", string="Transaction Log")

    def _logme(self, **kwargs):
        """
        sample logme(**kwargs)
        need to be on new_env to avoid rollback from the main transaction
        """
        self.flush()
        db_name = self._cr.dbname
        try:
            db_registry = registry(db_name)
            with db_registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                IrLogging = env["log.error"]
                IrLogging.sudo().create(kwargs)
        except psycopg2.Error:
            pass

    @api.model_create_multi
    def create(self, vals):
        res = super().create(vals)
        res.message_subscribe(partner_ids=res.followers_ids.ids)
        body = _(Markup("Error: %s") % res.error_message)
        res.message_notify(
            body=body,
            subtype_xmlid="mail.mt_comment",
            email_layout_xmlid="mail.mail_notification_light",
            partner_ids=res.followers_ids.ids,
        )
        return res
