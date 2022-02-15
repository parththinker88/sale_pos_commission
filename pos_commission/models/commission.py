# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CommissionRule(models.Model):
    _inherit = 'commission.rule'

    is_pos_commission = fields.Boolean('Apply for POS Commission')

    @api.model
    def create_commission_lines(self):
        """Scheduler method which is creating commission lines for POS
        based on their Order confirm /Invoice posted /Invoice Payment"""
        res = super(CommissionRule, self).create_commission_lines()

        pos_order_recs = self.env['pos.order'].search([
            ('is_pos_commission_create', '=', False),
            ('state', 'in', ['paid', 'posted'])])

        # for pos confirm commission
        for pos_order_id in pos_order_recs:
            if pos_order_id and pos_order_id.user_id:
                commission_ids = self.sudo().search(
                    [('commission_trigger_type', '=', 'order'),
                     ('is_pos_commission', '=', True),
                     ('user_ids', 'in', pos_order_id.user_id.id)])

                if len(commission_ids) >= 1:
                    invoice_commission_ids = pos_order_id.get_sales_commission(
                        pos_order_id, commission_ids)
                    if invoice_commission_ids:
                        pos_order_id.write({
                            'is_pos_commission_create': True
                        })
        return res
