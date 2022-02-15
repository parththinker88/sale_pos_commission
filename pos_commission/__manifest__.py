# -*- coding: utf-8 -*-
{
    "name": "POS Commission from Order/Invoice/Payment in Odoo",
    "version": "14.0.1.1.1",
    'category': "POS",
    "summary" : """
        POS Commission from Order/Invoice/Payment in Odoo
    """,
    "depends": ['sales_commission', 'point_of_sale'],
    "data": [
        'views/account_invoice_view.xml',
        'views/commission_view.xml',
        'views/pos_view.xml',
        'report/sale_inv_comm_template.xml'
    ],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': True,
}
