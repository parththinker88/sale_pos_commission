# -*- coding: utf-8 -*-

from odoo import api, fields, models


class res_configuration_settings(models.TransientModel):
    _inherit = "res.config.settings"

    commission_discount_account = fields.Many2one(
        'account.account', domain=[('user_type_id', '=', 'Expenses')],
        string="Commission Account",
        related="company_id.commission_discount_account", readonly=False)


class ResCompanyInherit(models.Model):
    _inherit = 'res.company'

    commission_discount_account = fields.Many2one(
        'account.account', domain=[('user_type_id', '=', 'Expenses')],
        string="Commission Account")
