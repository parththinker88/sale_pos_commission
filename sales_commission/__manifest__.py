# -*- coding: utf-8 -*-
{
    "name": "Sales Commission from Order/Invoice/Payment in Odoo",
    "version": "14.0.1.1.1",
    'category': "Sales",
    "summary" : """
        Sales Commission from Order/Invoice/Payment in Odoo
    """,
    "depends": ['sale_stock', 'sale_margin'],
    "data": [
        'security/sales_commission_security.xml',
        'security/ir.model.access.csv',
        'data/commission_data.xml',
        'views/account_invoice_view.xml',
        'views/commission_view.xml',
        'views/sale_config_settings.xml',
        'views/sale_view.xml',
        'views/product_view.xml',
        'views/sale_config_settings.xml',
        'report/commission_report.xml',
        'report/sale_inv_comm_template.xml'
    ],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': True,
}
