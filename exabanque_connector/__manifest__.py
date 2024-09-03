#################################################################################
# Author      : irokoo
# Copyright(c): 2023 - irokoo
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
#
#################################################################################

{
    "name": "FTP-Bank Connector",
    "summary": """
        This is the FTB-Bank Connector module for Exabanque.
        """,
    "version": "14.0.1.6",
    "description": """
        This is the FTB-Bank Connector module for Exabanque. It allows to connect to the bank and get the bank statements.
        """,
    "author": "irokoo.fr",
    "maintainer": "",
    "license": "LGPL-3",
    "website": "",
    "images": ["static/src/icon.png"],
    "category": "Extra Tools",
    "external_dependencies": {"python": ["paramiko"]},
    "depends": [
        "base",
        "mail",
        "account",
        "account_accountant",
        "account_statement_import_fr_cfonb",
        "account_banking_fr_lcr",
        "account_payment_mode",
    ],
    "data": [
        # data
        "data/ir_cron.xml",
        # report
        # security
        "security/ir.model.access.csv",
        # views
        "views/account_payment_mode_views.xml",
        "views/account_payment_order_views.xml",
        "views/base_connector_views.xml",
        "views/base_ftp_views.xml",
        "views/log_error_views.xml",
        "views/log_exabanque_views.xml",
        "views/log_transaction_views.xml",
        # views menu
        "views/menuitem.xml",
        # views qweb
        # wizard
    ],
    "installable": True,
    "application": True,
    "price": 0,
    "currency": "EUR",
}
