# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo import tools
import datetime


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_sale_commission_create = fields.Boolean(
        'Is Sale Commission Created.?', default=False)
    # additional_currency = fields.Many2one(
    #     'res.currency', store=True, string='Additional Currency For Commission')
    # commission_ids = fields.One2many(
    #     'invoice.sale.commission', 'order_id', string='Sales Commissions',
    #     help="Sale Commission related to this order(based on sales person)")

    def get_exceptions(self, line, commission_brw):
        '''This method searches exception for any product line.
           @return : List of ids for all exception for particular product line.'''
        exception_obj = self.env['commission.exception']
        categ_obj = self.env['product.category']

        all_product_exception_id = exception_obj.sudo().search([
            ('all_product_ids', 'in', line.product_id.id),
            ('commission_id', '=', commission_brw.id),
            ('commission_based_on', '=', 'all_products')
        ])

        if all_product_exception_id:
            return all_product_exception_id

        subcateg_exception_id = exception_obj.sudo().search([
            ('sub_categ_id', '=', line.product_id.categ_id.id),
            ('commission_id', '=', commission_brw.id),
            ('commission_based_on', '=', 'product_sub_categories')])

        if subcateg_exception_id:
            return subcateg_exception_id

        exclusive_categ_exception_id = exception_obj.sudo().search([
            ('category_store', 'in', line.product_id.categ_id.id),
            ('commission_id', '=', commission_brw.id),
            ('commission_based_on', '=', 'product_categories'),
        ])

        if exclusive_categ_exception_id:
            return exclusive_categ_exception_id

        multi_product_exception_id = exception_obj.sudo().search([
            ('product_ids', 'in', line.product_id.id),
            ('commission_id', '=', commission_brw.id),
            ('commission_based_on', '=', 'multi_product')
        ])

        if multi_product_exception_id:
            return multi_product_exception_id

        return False

    def get_sales_commission(self, order, commission_ids):
        '''This is control method for calculating commissions(called from workflow).
           @return : List of ids for commission records created.'''
        invoice_commission_ids = []
        invoice_commission_obj = self.env['invoice.sale.commission']

        for commission_brw in commission_ids:
            for line in order.order_line:
                amount = line.price_subtotal
                invoice_commission_data = {}
                exception_ids = []
                if not line.product_id:
                    continue

                actual_product_cost = 0.0
                regular_amount = 0.0
                standard_amount = 0.0
                actual_regular_margin = 0.0
                actual_standard_margin = 0.0

                # if order company currency and order currency is different.
                if order.currency_id != order.company_id.currency_id:
                    updated_price_subtotal = order.currency_id._convert(
                        line.price_subtotal, order.company_id.currency_id, order.company_id,
                        fields.Date.context_today(self))

                    # if the commission_based_on standard_margin
                    actual_product_cost = line.product_id.standard_cost

                    standard_margin = ((updated_price_subtotal / line.product_uom_qty) -
                                       actual_product_cost)

                    standard_amount = standard_margin * line.product_uom_qty
                    if actual_product_cost == 0.0:
                        actual_standard_margin = (standard_margin * 100) / 1.0
                    else:
                        actual_standard_margin = (
                            standard_margin * 100) / actual_product_cost

                    # if the commission_based_on regular_margin or fix_price
                    regular_margin = (
                        (updated_price_subtotal / line.product_uom_qty) - line.purchase_price)

                    regular_amount = regular_margin * line.product_uom_qty
                    if line.purchase_price == 0.0:
                        # if purchase price is not given in order lines
                        actual_regular_margin = (regular_margin * 100) / 1.0
                    else:
                        actual_regular_margin = (
                            regular_margin * 100) / line.purchase_price
                else:
                    # if the commission_based_on standard_margin
                    actual_product_cost = line.product_id.standard_cost

                    standard_margin = ((line.price_subtotal / line.product_uom_qty) -
                                       actual_product_cost)

                    standard_amount = standard_margin * line.product_uom_qty
                    if actual_product_cost == 0.0:
                        actual_standard_margin = (standard_margin * 100) / 1.0
                    else:
                        actual_standard_margin = (
                            standard_margin * 100) / actual_product_cost

                    # if the commission_based_on regular_margin or fix_price
                    regular_margin = (
                        (line.price_subtotal / line.product_uom_qty) - line.purchase_price)

                    regular_amount = regular_margin * line.product_uom_qty
                    if line.purchase_price == 0.0:
                        # if purchase price is not given in order lines
                        actual_regular_margin = (regular_margin * 100) / 1.0
                    else:
                        actual_regular_margin = (
                            regular_margin * 100) / line.purchase_price

                exception_ids = self.get_exceptions(line, commission_brw)

                if exception_ids:
                    for exception in exception_ids:
                        product_id = False
                        categ_id = False
                        sub_categ_id = False
                        name = ''

                        if exception.commission_with == 'standard_margin' and \
                                actual_standard_margin > exception.target_margin:
                            commission_percentage = exception.above_target_commission

                        elif exception.commission_with == 'standard_margin' and \
                                actual_standard_margin <= exception.target_margin:
                            commission_percentage = exception.below_target_commission

                        elif exception.commission_with == 'fix_price' and \
                                line.price_unit >= exception.target_price:
                            commission_percentage = exception.above_target_commission

                        elif exception.commission_with == 'fix_price' and \
                                line.price_unit < exception.target_price:
                            commission_percentage = exception.below_target_commission

                        elif exception.commission_with == 'margin' and \
                                actual_regular_margin > exception.target_margin:
                            commission_percentage = exception.above_target_commission

                        elif exception.commission_with == 'margin' and \
                                actual_regular_margin <= exception.target_margin:
                            commission_percentage = exception.below_target_commission

                        if exception.commission_with == 'standard_margin':
                            commission_amount = standard_amount * \
                                (commission_percentage / 100)
                        else:
                            commission_amount =  regular_amount * \
                                (commission_percentage / 100)

                        if exception.commission_based_on == 'all_products':
                            product_id = line.product_id.id
                            name = tools.ustr(commission_brw.name) + ' for ' + \
                                tools.ustr(exception.commission_based_on) + ' "' + \
                                tools.ustr(line.product_id.name) + '" @' + \
                                tools.ustr(commission_percentage) + '%'

                        elif exception.commission_based_on == 'product_categories':
                            categ_id = exception.categ_id.id
                            name = tools.ustr(commission_brw.name) + ' for ' + \
                                tools.ustr(exception.commission_based_on) + ' "' + \
                                tools.ustr(exception.categ_id.name) + '" @' + \
                                tools.ustr(commission_percentage) + '%'

                        elif exception.commission_based_on == 'product_sub_categories':
                            sub_categ_id = exception.sub_categ_id.id
                            name = tools.ustr(commission_brw.name) + ' for ' + \
                                tools.ustr(exception.commission_based_on) + ' "' + \
                                tools.ustr(exception.sub_categ_id.name) + '" @' + \
                                tools.ustr(commission_percentage) + '%'

                        elif exception.commission_based_on == 'multi_product':
                            product_id = line.product_id.id
                            name = tools.ustr(commission_brw.name) + ' for ' + \
                                tools.ustr(exception.commission_based_on) + ' "' + \
                                tools.ustr(line.product_id.name) + '" @' + \
                                tools.ustr(commission_percentage) + '%'

                        invoice_commission_data = {
                            'name': name,
                            'product_id': product_id or False,
                            'commission_id': commission_brw.id,
                            'categ_id': categ_id or False,
                            'sub_categ_id': sub_categ_id or False,
                            'user_id': order.user_id.id,
                            'type_name': commission_brw.name,
                            'commission_amount': commission_amount,
                            'order_id': order.id,
                            'date': datetime.datetime.today(),
                            'currency_id': order.currency_id.id,
                            'achieved_target': actual_regular_margin if
                            exception.commission_with == 'margin' else actual_standard_margin
                        }

                        # if company currency and order currency is different
                        if order.currency_id != order.company_id.currency_id:
                            changed_commission_amt = order.company_id.currency_id._convert(
                                invoice_commission_data.get(
                                    'commission_amount'),
                                order.currency_id, order.company_id,
                                fields.Date.context_today(self))
                            invoice_commission_data.update({
                                'amount_currency': changed_commission_amt
                            })

                        invoice_commission_ids.append(
                            invoice_commission_obj.sudo().create(invoice_commission_data))
        return invoice_commission_ids

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if order.user_id:
                commission_ids = self.env['commission.rule'].sudo().search(
                    [('commission_trigger_type', '=', 'order'),
                     ('is_sale_commission', '=', True),
                     ('user_ids', 'in', order.user_id.id)])

                if len(commission_ids) >= 1:
                    invoice_commission_ids = self.get_sales_commission(
                        order, commission_ids)
                    if invoice_commission_ids:
                        order.write({
                            'is_sale_commission_create': True
                        })
        return res

    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        for so in self:
            if so.commission_ids:
                so.commission_ids.sudo().unlink()
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_invoice_line(self, **optional_values):
        res = super(SaleOrderLine, self)._prepare_invoice_line()
        res.update({'sol_id': self.id})
        return res
