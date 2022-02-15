# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import Warning, UserError
import datetime


class CreateCommisionInvoice(models.Model):
    _name = 'create.invoice.commission'
    _description = 'create invoice commission'

    group_by = fields.Boolean('Group By', readonly=False)
    date = fields.Date('Invoice Date', readonly=False)

    def invoice_create(self):
        sale_invoice_ids = self.env['invoice.sale.commission'].browse(
            self._context.get('active_ids'))
        if any(line.invoiced == True for line in sale_invoice_ids):
            raise UserError('Invoiced Lines cannot be Invoiced Again.')

        commission_discount_account = self.env.user.company_id.commission_discount_account
        if not commission_discount_account:
            raise UserError(
                'You have not configured commission Discount Account')

        moves = []
        if self.group_by:
            group_dict = {}
            for record in sale_invoice_ids:
                group_dict.setdefault(record.user_id.name, []).append(record)
            for dict_record in group_dict:
                inv_lines = []
                for inv_record in group_dict.get(dict_record):
                    inv_lines.append({
                        'name': inv_record.name,
                        'quantity': 1,
                        'price_unit': inv_record.commission_amount,
                    })
                partner = self.env['res.partner'].search(
                    [('name', '=', dict_record)])
                inv_id = self.env['account.move'].create({
                    'move_type': 'in_invoice',
                    'partner_id': partner.id,
                    'invoice_date': self.date if self.date else datetime.datetime.today().date(),
                    'invoice_line_ids': [(0, 0, l) for l in inv_lines],
                })
                moves.append(inv_id.id)
            sale_invoice_ids.write({'invoiced': True})

        else:

            for commission_record in sale_invoice_ids:
                inv_lines = []
                inv_lines.append({
                    'name': commission_record.name,
                    'quantity': 1,
                    'price_unit': commission_record.commission_amount,
                })

                inv_id = self.env['account.move'].create({
                    'move_type': 'in_invoice',
                    'invoice_line_ids': [(0, 0, l) for l in inv_lines],
                    'partner_id': commission_record.user_id.partner_id.id,
                    'invoice_date': self.date if self.date else datetime.datetime.today().date()
                })

                moves.append(inv_id.id)
            sale_invoice_ids.write({'invoiced': True})


class CommissionRule(models.Model):
    _name = 'commission.rule'
    _rec_name = 'name'
    _description = 'Sale commission'

    name = fields.Char('Name', required=True)
    commission_trigger_type = fields.Selection([
        ('order', 'Commission based on order confirm'),
        ('invoice', 'Commission based on invoice posted'),
        ('payment', 'Commission based on invoice payment')
    ], string='Commission Trigger', required=True)
    user_ids = fields.Many2many(
        'res.users', 'commision_rel_user', 'commision_id', 'user_id',
        string='Sales Person', required=True,
        help="Select sales person associated with this type of commission")

    exception_ids = fields.One2many(
        'commission.exception', 'commission_id',
        string='Commission Exceptions', help="commission exceptions")

    is_sale_commission = fields.Boolean('Apply for Sales Commission')
    # is_pos_commission = fields.Boolean('Apply for POS Commission')

    @api.model
    def create_commission_lines(self):
        """Scheduler method which is creating commission lines for sales/pos
        based on their Order confirm /Invoice posted /Invoice Payment"""
        sale_order_recs = self.env['sale.order'].search([
            ('is_sale_commission_create', '=', False),
            ('state', '=', 'sale')])

        # for sale confirm commission
        for order in sale_order_recs:
            if order.user_id:
                commission_ids = self.sudo().search(
                    [('commission_trigger_type', '=', 'order'),
                     ('is_sale_commission', '=', True),
                     ('user_ids', 'in', order.user_id.id)])

                if len(commission_ids) >= 1:
                    invoice_commission_ids = order.get_sales_commission(
                        order, commission_ids)
                    if invoice_commission_ids:
                        order.write({
                            'is_sale_commission_create': True
                        })

        invoice_recs = self.env['account.move'].search([
            ('state', '=', 'posted')])

        # for invoice posted commission
        posted_invoice_recs = invoice_recs.filtered(
            lambda a: not a.is_invoice_commission_create and
            a.payment_state in ['not_paid', 'in_payment'])

        for invoice in posted_invoice_recs:
            if invoice.user_id:
                commission_ids = self.sudo().search(
                    [('commission_trigger_type', '=', 'invoice'),
                     ('user_ids', 'in', invoice.user_id.id)])
                commission_ids = commission_ids.filtered(
                    lambda a: a.is_sale_commission or a.is_pos_commission)
                if len(commission_ids) >= 1:
                    invoice_commission_ids = invoice.get_invoice_commission(
                        invoice, commission_ids)
                    if invoice_commission_ids:
                        invoice.write({
                            'is_invoice_commission_create': True
                        })

        # for invoice payment commission
        paid_invoice_recs = invoice_recs.filtered(
            lambda a: not a.is_payment_commission_create and
            a.payment_state == 'paid')

        for invoice in paid_invoice_recs:
            if invoice.user_id:
                commission_ids = self.sudo().search(
                    [('commission_trigger_type', '=', 'payment'),
                     ('user_ids', 'in', invoice.user_id.id)])
                commission_ids = commission_ids.filtered(
                    lambda a: a.is_sale_commission or a.is_pos_commission)
                if len(commission_ids) >= 1:
                    invoice_commission_ids = invoice.get_invoice_commission(
                        invoice, commission_ids)
                    if invoice_commission_ids:
                        invoice.write({
                            'is_payment_commission_create': True
                        })


class CommissionException(models.Model):
    _name = 'commission.exception'
    _rec_name = 'commission_based_on'
    _description = 'Commission Exception'

    commission_based_on = fields.Selection([
        ('all_products', 'All Products'),
        ('product_categories', 'Product Categories'),
        ('product_sub_categories', 'Product Sub-Categories'),
        ('multi_product', 'Multi-Products')], string="Based On",
        help="commission exception based on", default='all_products',
        required=True)
    product_ids = fields.Many2many(
        'product.product', 'commision_product_rel', 'commision_id', 'product_id',
        string='Product', help="Exception based on products")
    all_product_ids = fields.Many2many(
        'product.product', 'commision_all_product_rel', 'commision_id', 'product_id',
        string='All Product')
    categ_id = fields.Many2one('product.category', string='Product Category',
                               help="Exception based on product category")
    sub_categ_id = fields.Many2one(
        'product.category', string='Product Sub-Category',
        help="Exception based on product sub-category")
    commission_with = fields.Selection([
        ('fix_price', 'Fix Price'),
        ('margin', 'Regular Margin'),
        ('standard_margin', 'Standard Margin')], string="Commission With",
        help="commission exception based on",
        required=True)
    target_price = fields.Float(string="Target Price")
    target_margin = fields.Float(string="Target Margin %")
    above_target_commission = fields.Float(string="Above Price Commission %")
    below_target_commission = fields.Float(string="Below Price Commission %")
    commission_id = fields.Many2one('commission.rule', string='Commission Rule',
                                    help="Related Commission",)
    category_store = fields.Many2many(
        'product.category', string="Category store", compute="_compute_all_ids", store=True)

    @api.depends('commission_based_on', 'sub_categ_id', 'categ_id')
    def _compute_all_ids(self):
        """"""
        for line in self:
            category_lst = []
            if line.categ_id and line.commission_based_on == 'product_categories':
                category_lst.append(line.categ_id.id)

                for child in line.categ_id.child_id:
                    if child.id not in category_lst:
                        category_lst.append(child.id)
                category_store = ''
                for num in category_lst:
                    category_store = category_store + ',' + str(num)
                line.category_store = category_lst
            elif line.categ_id and line.commission_based_on == 'product_sub_categories':

                for child in line.sub_categ_id.child_id:
                    if child.id not in category_lst:
                        category_lst.append(child.id)

                category_store = ''
                for num in category_lst:
                    category_store = category_store + ',' + str(num)

                line.category_store = category_lst

            else:
                line.category_store = category_lst

    @api.model
    def create(self, vals):
        """Method to set all the product_ids if the commission_based_on
        'All Product'."""
        if vals.get('commission_based_on') and \
                vals.get('commission_based_on') == 'all_products':
            product_ids = self.env['product.product'].search([])
            vals.update({
                'all_product_ids': [(6, 0, [product.id for product in product_ids if product])]
            })
        return super(CommissionException, self).create(vals)

    def write(self, vals):
        """Method to set all the product_ids if the commission_based_on
        'All Product' or remove the products_ids if it is not based on all_products"""
        if vals.get('commission_based_on') and \
                vals.get('commission_based_on') == 'all_products':
            product_ids = self.env['product.product'].search([])
            vals.update({
                'all_product_ids': [(6, 0, [product.id for product in product_ids if product])]
            })
        elif vals.get('commission_based_on') != self.commission_based_on and \
                self.all_product_ids:
            vals['all_product_ids'] = False
        return super(CommissionException, self).write(vals)
