# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class CommissionRule(models.Model):
    _name = 'commission.rule'
    _description = 'Commission Rule'
    _order = 'sequence, id'
    
    name = fields.Char(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10,
                             help='Determines the order of rule evaluation')
    active = fields.Boolean(default=True)
    
    # Rule configuration
    scheme_id = fields.Many2one('commission.scheme', string='Commission Scheme', 
                              required=True, ondelete='cascade')
    company_id = fields.Many2one(related='scheme_id.company_id')
    currency_id = fields.Many2one(related='scheme_id.currency_id')
    
    # Rule type
    rule_type = fields.Selection([
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage of Amount'),
    ], string='Rule Type', default='percentage', required=True)
    
    # Rule amount
    fixed_amount = fields.Monetary(string='Fixed Amount', currency_field='currency_id',
                                 help='Fixed commission amount')
    percentage = fields.Float(string='Percentage', help='Percentage of the base amount')
    
    # Rule conditions
    min_amount = fields.Monetary(string='Minimum Amount', currency_field='currency_id',
                               help='Minimum base amount for this rule to apply')
    max_amount = fields.Monetary(string='Maximum Amount', currency_field='currency_id',
                               help='Maximum base amount for this rule to apply')
    
    # Rule triggers
    apply_on = fields.Selection([
        ('so', 'Sales Order'),
        ('invoice', 'Customer Invoice'),
        ('payment', 'Customer Payment'),
    ], string='Apply On', default='invoice', required=True,
        help='When to calculate commission: at order, invoice, or payment')
    
    @api.constrains('percentage')
    def _check_percentage(self):
        for rule in self:
            if rule.rule_type == 'percentage' and (rule.percentage < 0 or rule.percentage > 100):
                raise ValidationError(_('Percentage must be between 0 and 100.'))
    
    @api.constrains('min_amount', 'max_amount')
    def _check_amount_range(self):
        for rule in self:
            if rule.min_amount and rule.max_amount and rule.min_amount > rule.max_amount:
                raise ValidationError(_('Maximum amount cannot be less than minimum amount.'))
    
    def calculate_commission(self, base_amount):
        """Calculate commission amount based on the rule"""
        self.ensure_one()
        
        # Check if the base amount is within the rule's range
        if self.min_amount and base_amount < self.min_amount:
            return 0.0
        if self.max_amount and base_amount > self.max_amount:
            return 0.0
        
        # Calculate commission based on rule type
        if self.rule_type == 'fixed':
            return self.fixed_amount
        elif self.rule_type == 'percentage':
            return base_amount * (self.percentage / 100.0)
        
        return 0.0