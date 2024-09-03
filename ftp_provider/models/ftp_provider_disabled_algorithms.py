from odoo import fields, models


class FtpProviderDisabledAlgorithms(models.Model):
    _name = "ftp.provider.disabled.algorithms"
    _description = "Base FTP Disabled Algorithm"

    name = fields.Char(string="Name", required=True)
    ftp_provider_id = fields.Many2one("ftp.provider", string="FTP", required=True)
