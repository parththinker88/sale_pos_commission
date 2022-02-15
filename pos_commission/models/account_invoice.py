# -*- coding: utf-8 -*-


from odoo import api, fields, models


class InvoiceSaleCommission(models.Model):
    _inherit = 'invoice.sale.commission'

    pos_order_id = fields.Many2one('pos.order', string='POS Order Reference',
                                   help="Affected POS Order")
