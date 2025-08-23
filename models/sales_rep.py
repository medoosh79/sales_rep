# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SalesRepresentative(models.Model):
    _name = 'sales.rep'
    _description = 'Sales Representative'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    
    name = fields.Char(string='Name', required=True, tracking=True)
    code = fields.Char(string='Code', tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Related Partner', tracking=True,
                               help='Partner record related to this sales representative')
    user_id = fields.Many2one('res.users', string='Related User', tracking=True,
                            help='User account related to this sales representative')
    employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True,
                                help='Employee record related to this sales representative')
    job_id = fields.Many2one('hr.job', string='Job Position', tracking=True,
                           help='Job position of this sales representative')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    
    # Contact information
    phone = fields.Char(string='Phone', tracking=True)
    mobile = fields.Char(string='Mobile', tracking=True)
    email = fields.Char(string='Email', tracking=True)
    
    # Commission related fields
    commission_scheme_id = fields.Many2one('commission.scheme', string='Commission Scheme', tracking=True)
    
    # Statistics and KPIs
    total_sales = fields.Monetary(string='Total Sales', currency_field='currency_id', compute='_compute_statistics', store=False)
    total_commission = fields.Monetary(string='Total Commission', currency_field='currency_id', compute='_compute_statistics', store=False)
    
    # Assignments
    assignment_ids = fields.One2many('sales.rep.assignment', 'sales_rep_id', string='Territory Assignments')
    assignment_count = fields.Integer(compute='_compute_assignment_count')
    
    # Territory Assignment relationship
    territory_assignment_ids = fields.One2many(
        'territory.assignment',
        'sales_rep_id',
        string='Territory Assignments',
        help='Territory assignments for this sales representative'
    )
    territory_assignment_count = fields.Integer(
        string='Territory Assignment Count',
        compute='_compute_territory_assignment_count',
        store=True
    )
    
    @api.depends('assignment_ids')
    def _compute_assignment_count(self):
        for rep in self:
            rep.assignment_count = len(rep.assignment_ids)
    
    @api.depends('territory_assignment_ids')
    def _compute_territory_assignment_count(self):
        for rep in self:
            rep.territory_assignment_count = len(rep.territory_assignment_ids)
            
    def action_view_assignments(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sales_rep_mgmt_pro.action_sales_rep_assignment")
        action['domain'] = [('sales_rep_id', '=', self.id)]
        action['context'] = {'default_sales_rep_id': self.id}
        return action
    
    def _compute_statistics(self):
        """Compute sales and commission statistics"""
        for rep in self:
            # This will be implemented in later phases with actual sales data
            rep.total_sales = 0.0
            rep.total_commission = 0.0
    
    @api.constrains('code')
    def _check_code_unique(self):
        for rep in self:
            if rep.code:
                domain = [('code', '=', rep.code), ('id', '!=', rep.id)]
                if self.search_count(domain):
                    raise ValidationError(_('Sales Representative code must be unique!'))
    
    def name_get(self):
        result = []
        for rep in self:
            name = rep.name
            if rep.code:
                name = f'[{rep.code}] {name}'
            result.append((rep.id, name))
        return result