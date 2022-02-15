# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    standard_cost = fields.Float(
        'Standard Cost', default=1.0, digits='Product Price',
        help="Product actual cost.")
    is_standard_costing = fields.Boolean(
        'Is Standard Costing', compute="compute_categ_id", store=True)

    @api.depends('categ_id')
    def compute_categ_id(self):
        """Method to set the is_standard_costing boolean field which should
        hide or display the standard_cost field."""
        for record in self:
            if record.categ_id and \
                    record.categ_id.property_cost_method == 'standard':
                record.is_standard_costing = True
            elif record.categ_id.property_cost_method != 'standard':
                record.is_standard_costing = False
