# -*- coding: utf-8 -*-


from odoo import api, fields, models, tools
from docutils.nodes import field
import datetime
from odoo.exceptions import Warning, UserError


class WizardInvoiceSaleCommission(models.Model):
    _name = 'wizard.invoice.sale.commission'
    _description = 'Wizard Invoice Sale Commission'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    salesperson = fields.Many2one('res.users', 'Sales Person', required=True)

    def print_commission_report(self):
        temp = []
        sale_invoice_commission_ids = self.env['invoice.sale.commission'].search(
            [('date', '>=', self.start_date),
             ('date', '<=', self.end_date), ('user_id', '=', self.salesperson.id)])
        if not sale_invoice_commission_ids:
            raise UserError('There Is No Any Commissions.')
        else:
            for a in sale_invoice_commission_ids:
                temp.append(a.id)
        data = temp
        datas = {
            'ids': self._ids,
            'model': 'invoice.sale.commission',
            'form': data,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'salesperson': self.salesperson.name
        }
        return self.env.ref('sales_commission.report_pdf').report_action(self, data=datas)


class InvoiceSaleCommission(models.Model):
    _name = 'invoice.sale.commission'
    _description = 'Invoice Sale Commission'
    _order = 'date desc, id desc'

    name = fields.Char(string="Description")
    type_name = fields.Char(string="Commission Name")
    user_id = fields.Many2one('res.users', string='Sales Person',
                              help="sales person associated with this type of commission",
                              required=True)
    commission_amount = fields.Monetary(
        string="Commission Amount", store=True, copy=True,
        currency_field='company_currency_id')
    invoice_id = fields.Many2one('account.move', string='Invoice Reference',
                                 help="Affected Invoice")
    order_id = fields.Many2one('sale.order', string='Order Reference',
                               help="Affected Sale Order")
    commission_id = fields.Many2one('commission.rule', string='Sale Commission',
                                    help="Related Commission",)
    product_id = fields.Many2one('product.product', string='Product',
                                 help="product",)
    categ_id = fields.Many2one('product.category', string='Product Category')
    sub_categ_id = fields.Many2one(
        'product.category', string='Product Sub-Category')
    date = fields.Date('Date')
    invoiced = fields.Boolean(string='Invoiced', readonly=True, default=False)
    achieved_target = fields.Float("Acheived Target(%)")
    currency_id = fields.Many2one('res.currency', 'Currency')
    amount_currency = fields.Monetary(
        string='Amount in Currency', store=True, copy=True,
        currency_field='currency_id',
        help="The amount expressed in an optional other currency if it is a multi-currency entry.")
    company_currency_id = fields.Many2one(
        'res.currency', string='Company Currency',
        readonly=True, store=True,
        default=lambda self:  self.env.user.company_id.currency_id,
        help='Utility field to express amount currency')


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    is_invoice_commission_create = fields.Boolean(
        'Is Invoice Commission Created.?', default=False)
    is_payment_commission_create = fields.Boolean(
        'Is Payment Commission Created.?', default=False)

    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.debit',
        'line_ids.credit',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id')
    def _compute_amount(self):
        for move in self:

            if move.payment_state == 'invoicing_legacy':
                # invoicing_legacy state is set via SQL when setting setting field
                # invoicing_switch_threshold (defined in account_accountant).
                # The only way of going out of this state is through this setting,
                # so we don't recompute it here.
                move.payment_state = move.payment_state
                continue

            total_untaxed = 0.0
            total_untaxed_currency = 0.0
            total_tax = 0.0
            total_tax_currency = 0.0
            total_to_pay = 0.0
            total_residual = 0.0
            total_residual_currency = 0.0
            total = 0.0
            total_currency = 0.0
            currencies = set()

            for line in move.line_ids:
                if line.currency_id:
                    currencies.add(line.currency_id)

                if move.is_invoice(include_receipts=True):
                    # === Invoices ===

                    if not line.exclude_from_invoice_tab:
                        # Untaxed amount.
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.tax_line_id:
                        # Tax amount.
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.account_id.user_type_id.type in ('receivable', 'payable'):
                        # Residual amount.
                        total_to_pay += line.balance
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    # === Miscellaneous journal entry ===
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency

            if move.move_type == 'entry' or move.is_outbound():
                sign = 1
            else:
                sign = -1
            move.amount_untaxed = sign * \
                (total_untaxed_currency if len(currencies)
                 == 1 else total_untaxed)
            move.amount_tax = sign * \
                (total_tax_currency if len(currencies) == 1 else total_tax)
            move.amount_total = sign * \
                (total_currency if len(currencies) == 1 else total)
            move.amount_residual = -sign * \
                (total_residual_currency if len(currencies)
                 == 1 else total_residual)
            move.amount_untaxed_signed = -total_untaxed
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(
                total) if move.move_type == 'entry' else -total
            move.amount_residual_signed = total_residual

            currency = len(
                currencies) == 1 and currencies.pop() or move.company_id.currency_id

            # Compute 'payment_state'.
            new_pmt_state = 'not_paid' if move.move_type != 'entry' else False

            if move.is_invoice(include_receipts=True) and move.state == 'posted':
                if currency.is_zero(move.amount_residual):
                    if all(payment.is_matched for payment in move._get_reconciled_payments()):
                        new_pmt_state = 'paid'

                    else:
                        new_pmt_state = move._get_invoice_in_payment_state()
                        # get the commission if the invoice is paid.
                        if move.user_id:
                            commission_ids = self.env['commission.rule'].sudo().search(
                                [('commission_trigger_type', '=', 'payment'),
                                 ('is_sale_commission', '=', True),
                                 ('user_ids', 'in', move.user_id.id)])

                            if len(commission_ids) >= 1:
                                invoice_commission_ids = self.get_invoice_commission(
                                    move, commission_ids)
                                if invoice_commission_ids:
                                    move.write({
                                        'is_payment_commission_create': True
                                    })

                elif currency.compare_amounts(total_to_pay, total_residual) != 0:
                    new_pmt_state = 'partial'

            if new_pmt_state == 'paid' and move.move_type in ('in_invoice', 'out_invoice', 'entry'):
                reverse_type = move.move_type == 'in_invoice' and \
                    'in_refund' or move.move_type == 'out_invoice' and 'out_refund' or 'entry'
                reverse_moves = self.env['account.move'].search(
                    [('reversed_entry_id', '=', move.id),
                     ('state', '=', 'posted'), ('move_type', '=', reverse_type)])

                # We only set 'reversed' state in cas of 1 to 1 full
                # reconciliation with a reverse entry; otherwise, we use the
                # regular 'paid' state
                reverse_moves_full_recs = reverse_moves.mapped(
                    'line_ids.full_reconcile_id')
                if reverse_moves_full_recs.mapped(
                        'reconciled_line_ids.move_id').filtered(
                        lambda x: x not in (reverse_moves + reverse_moves_full_recs.mapped(
                            'exchange_move_id'))) == move:
                    new_pmt_state = 'reversed'

            move.payment_state = new_pmt_state

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

    def get_commission_data(self, invoice, commission_ids):
        """Method to create the invoice_sale_commission record if the move_type
        is out_invoice or out_refund."""
        invoice_commission_ids = []
        invoice_commission_obj = self.env['invoice.sale.commission']
        for commission_brw in commission_ids:
            for line in invoice.invoice_line_ids:
                move = line.move_id
                invoice_commission_data = {}
                exception_ids = []
                if not line.product_id:
                    continue

                actual_product_cost = 0.0
                regular_amount = 0.0
                standard_amount = 0.0
                actual_regular_margin = 0.0
                actual_standard_margin = 0.0

                # if move and move_line currency is different.
                if line.move_id.currency_id != move.company_id.currency_id:
                    updated_price_subtotal = move.currency_id._convert(
                        line.price_subtotal, move.company_id.currency_id, move.company_id,
                        line.move_id.date or
                        fields.Date.context_today(self))

                    # if the commission_based_on standard_margin
                    actual_product_cost = line.product_id.standard_cost

                    standard_margin = ((updated_price_subtotal / line.quantity) -
                                       actual_product_cost)

                    standard_amount = standard_margin * line.quantity
                    if actual_product_cost == 0.0:
                        actual_standard_margin = (standard_margin * 100) / 1.0
                    else:
                        actual_standard_margin = (
                            standard_margin * 100) / actual_product_cost

                    # if the commission_based_on regular_margin or fix_price
                    regular_margin = (
                        (updated_price_subtotal / line.quantity) - line.sol_id.purchase_price)

                    regular_amount = regular_margin * line.quantity
                    if line.sol_id and line.sol_id.purchase_price == 0.0:
                        # if purchase price is not given in order lines
                        actual_regular_margin = (regular_margin * 100) / 1.0
                    elif line.sol_id:
                        actual_regular_margin = (
                            regular_margin * 100) / line.sol_id.purchase_price
                else:
                    # if the commission_based_on standard_margin
                    actual_product_cost = line.product_id.standard_cost

                    standard_margin = ((line.price_subtotal / line.quantity) -
                                       actual_product_cost)

                    standard_amount = standard_margin * line.quantity
                    if actual_product_cost == 0.0:
                        actual_standard_margin = (standard_margin * 100) / 1.0
                    else:
                        actual_standard_margin = (
                            standard_margin * 100) / actual_product_cost

                    # if the commission_based_on regular_margin or fix_price
                    regular_margin = (
                        (line.price_subtotal / line.quantity) - line.sol_id.purchase_price)

                    regular_amount = regular_margin * line.quantity
                    if line.sol_id and line.sol_id.purchase_price == 0.0:
                        # if purchase price is not given in order lines
                        actual_regular_margin = (regular_margin * 100) / 1.0
                    elif line.sol_id:
                        actual_regular_margin = (
                            regular_margin * 100) / line.sol_id.purchase_price

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
                                tools.ustr(exception.categ_id.name) + '" @' + \
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
                            'user_id': invoice.user_id.id,
                            'type_name': commission_brw.name,
                            'commission_amount': commission_amount,
                            'invoice_id': invoice.id,
                            'date': datetime.datetime.today(),
                            'currency_id': invoice.currency_id.id,
                            'achieved_target': actual_regular_margin if
                            exception.commission_with == 'margin' else actual_standard_margin
                        }

                        if invoice.move_type == 'out_refund':
                            invoice_commission_data.update({
                                'commission_amount': commission_amount * -1,
                            })

                        # if company currency and move currency is different
                        if line.move_id.currency_id != move.company_id.currency_id:
                            changed_commission_amt = move.company_id.currency_id._convert(
                                invoice_commission_data.get(
                                    'commission_amount'),
                                line.move_id.currency_id, line.company_id,
                                fields.Date.context_today(self))
                            invoice_commission_data.update({
                                'amount_currency': changed_commission_amt
                            })

                        invoice_commission_ids.append(
                            invoice_commission_obj.sudo().create(invoice_commission_data))
        return invoice_commission_ids

    def get_invoice_commission(self, invoice, commission_ids):
        '''This is control method for calculating commissions(called from workflow).
           @return : List of ids for commission records created.'''
        if invoice.move_type == 'out_invoice' or \
                invoice.move_type == 'out_refund':
            return self.get_commission_data(invoice, commission_ids)

    def action_post(self):
        res = super(AccountInvoice, self).action_post()
        for invoice in self:
            if invoice.user_id:
                commission_ids = self.env['commission.rule'].sudo().search(
                    [('commission_trigger_type', '=', 'invoice'),
                     ('user_ids', 'in', invoice.user_id.id)])

                commission_ids = commission_ids.sudo().filtered(
                    lambda a: a.is_sale_commission or a.is_pos_commission)

                if len(commission_ids) >= 1:
                    invoice_commission_ids = self.get_invoice_commission(
                        invoice, commission_ids)
                    if invoice_commission_ids:
                        invoice.write({
                            'is_invoice_commission_create': True
                        })
        return res

    def button_draft(self):
        res = super(AccountInvoice, self).button_draft()
        for mv in self:
            if mv.commission_ids:
                mv.commission_ids.sudo().unlink()
        return res


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

    sol_id = fields.Many2one('sale.order.line', string='Sales Order Line')
