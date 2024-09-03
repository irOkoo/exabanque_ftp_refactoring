from odoo import fields, models


class BaseFtpDisabledAlgorithms(models.Model):
    _name = "base.ftp.disabled.algorithms"
    _description = "Base FTP Disabled Algorithm"

    name = fields.Char(string="Name", required=True)
    ftp_id = fields.Many2one("base.ftp", string="FTP", required=True)
