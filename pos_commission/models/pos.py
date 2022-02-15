# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo import tools
import datetime


class PosOrder(models.Model):
    _inherit = "pos.order"

    is_pos_commission_create = fields.Boolean(
        'Is Pos Commission Created.?', default=False)

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
            for line in order.lines:
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
                if order.pricelist_id.currency_id != order.company_id.currency_id:
                    updated_price_subtotal = order.pricelist_id.currency_id._convert(
                        line.price_subtotal, order.company_id.currency_id, order.company_id,
                        fields.Date.context_today(self))

                    # if the commission_based_on standard_margin
                    actual_product_cost = line.product_id.standard_cost

                    standard_margin = ((updated_price_subtotal / line.qty) -
                                       actual_product_cost)

                    standard_amount = standard_margin * line.qty
                    if actual_product_cost == 0.0:
                        actual_standard_margin = (standard_margin * 100) / 1.0
                    else:
                        actual_standard_margin = (
                            standard_margin * 100) / actual_product_cost

                    # if the commission_based_on regular_margin or fix_price
                    regular_margin = (
                        (updated_price_subtotal / line.qty) - line.product_id.standard_price)

                    regular_amount = regular_margin * line.qty
                    if line.product_id.standard_price == 0.0:
                        # if purchase price is not given in order lines
                        actual_regular_margin = (regular_margin * 100) / 1.0
                    else:
                        actual_regular_margin = (
                            regular_margin * 100) / line.product_id.standard_price
                else:
                    # if the commission_based_on standard_margin
                    actual_product_cost = line.product_id.standard_cost

                    standard_margin = ((line.price_subtotal / line.qty) -
                                       actual_product_cost)

                    standard_amount = standard_margin * line.qty
                    if actual_product_cost == 0.0:
                        actual_standard_margin = (standard_margin * 100) / 1.0
                    else:
                        actual_standard_margin = (
                            standard_margin * 100) / actual_product_cost

                    # if the commission_based_on regular_margin or fix_price
                    regular_margin = (
                        (line.price_subtotal / line.qty) - line.product_id.standard_price)

                    regular_amount = regular_margin * line.qty
                    if line.product_id.standard_price == 0.0:
                        # if purchase price is not given in order lines
                        actual_regular_margin = (regular_margin * 100) / 1.0
                    else:
                        actual_regular_margin = (
                            regular_margin * 100) / line.product_id.standard_price

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
                            'pos_order_id': order.id,
                            'date': datetime.datetime.today(),
                            'currency_id': order.pricelist_id.currency_id.id,
                            'achieved_target': actual_regular_margin if
                            exception.commission_with == 'margin' else actual_standard_margin

                        }

                        # if company currency and order currency is different
                        if order.pricelist_id.currency_id != order.company_id.currency_id:
                            changed_commission_amt = order.company_id.currency_id._convert(
                                invoice_commission_data.get(
                                    'commission_amount'),
                                order.pricelist_id.currency_id, order.company_id,
                                fields.Date.context_today(self))
                            invoice_commission_data.update({
                                'amount_currency': changed_commission_amt
                            })

                        invoice_commission_ids.append(
                            invoice_commission_obj.sudo().create(invoice_commission_data))
        return invoice_commission_ids

    # @api.model
    # def create_from_ui(self, orders, draft=False):
    #     order_ids = super(PosOrder, self).create_from_ui(orders, draft=False)
    # This code is for pos_commission
    #     print("\n\n\n\n order>>>>>>>>", order_ids)
    #     for order_id in order_ids:
    #         pos_order_id = self.browse(order_id.get('id'))
    #         if pos_order_id and pos_order_id.user_id:
    #             commission_ids = self.env['commission.rule'].sudo().search(
    #                 [('commission_trigger_type', '=', 'order'),
    #                  ('is_pos_commission', '=', True),
    #                  ('user_ids', 'in', pos_order_id.user_id.id)])
    #             print("\n\n\n\n commission++++++++", commission_ids)
    #             if len(commission_ids) >= 1:
    #                 invoice_commission_ids = self.get_sales_commission(
    #                     pos_order_id, commission_ids)
    #                 if invoice_commission_ids:
    #                     pos_order_id.write({
    #                         'is_pos_commission_create': True
    #                     })
    #     return order_ids
