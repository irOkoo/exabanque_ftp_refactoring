# Copyright 2024 irokoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "FTP Provider",
    "summary": "Provide a full equiped FTP connection for your modules to depends to.",
    "version": "14.0.0.0.4",
    "category": "Sale Management",
    "author": "irokoo",
    "website": "https://www.irokoo.fr",
    "license": "AGPL-3",
    "images": [
        "static/description/icon.png",
    ],
    "depends": [
        "base",
    ],
    "external_dependencies": {
        "python": [
            "paramiko",
            "cryptography",
        ],
    },
    "data": [
        # security
        "security/ir.model.access.csv",
        # views
        "views/ftp_provider_views.xml",
    ],
    "installable": True,
    "application": True,
}
