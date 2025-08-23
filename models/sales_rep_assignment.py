# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date

class SalesRepAssignment(models.Model):
    _name = 'sales.rep.assignment'
    _description = 'Sales Representative Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date_start desc'
    
    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    active = fields.Boolean(default=True, tracking=True)
    
    # Assignment dimensions
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True, tracking=True,
                                 ondelete='cascade', index=True)
    product_line_ids = fields.Many2many(
        'product.line',
        'sales_rep_assignment_product_line_rel',
        'assignment_id',
        'product_line_id',
        string='Product Lines',
        help='Product lines assigned to this sales representative'
    )
    
    geo_node_ids = fields.Many2many(
        'geo.node',
        'sales_rep_assignment_geo_node_rel',
        'assignment_id',
        'geo_node_id',
        string='Geographic Areas',
        compute='_compute_geo_node_ids',
        store=True,
        help='Geographic areas derived from assigned product lines'
    )
    geo_node_id = fields.Many2one('geo.node', string='Geographic Area', tracking=True,
                               help='Geographic node (city, zone, or neighborhood)')
    product_category_id = fields.Many2one('product.category', string='Product Category', tracking=True)
    
    # Assignment details
    priority = fields.Integer(string='Priority', default=10, tracking=True,
                            help='Higher number means higher priority when multiple assignments match')
    weight = fields.Float(string='Weight', default=100.0, tracking=True,
                        help='Percentage weight for commission distribution when multiple reps are assigned')
    date_start = fields.Date(string='Start Date', default=fields.Date.today, tracking=True)
    date_end = fields.Date(string='End Date', tracking=True)
    
    # Commission details
    commission_scheme_id = fields.Many2one('commission.scheme', string='Commission Scheme', tracking=True,
                                        help='Override the default commission scheme of the sales rep')
    
    # Company
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    @api.depends('product_line_ids')
    def _compute_geo_node_ids(self):
        """Compute geographic areas from assigned product lines"""
        for record in self:
            # Get all territory assignments for the product lines
            territory_assignments = record.product_line_ids.mapped('territory_assignment_ids')
            # Get unique geographic nodes from these assignments
            geo_nodes = territory_assignments.mapped('geo_node_id')
            record.geo_node_ids = [(6, 0, geo_nodes.ids)]
    

    product_line_count = fields.Integer(
        string='Product Lines Count',
        compute='_compute_product_line_count',
        store=True
    )
    
    @api.depends('product_line_ids')
    def _compute_product_line_count(self):
        for record in self:
            record.product_line_count = len(record.product_line_ids)
    
    @api.depends('sales_rep_id', 'geo_node_id', 'product_category_id', 'date_start')
    def _compute_name(self):
        for assignment in self:
            rep_name = assignment.sales_rep_id.name or ''
            geo_name = assignment.geo_node_id.name or 'All Areas'
            product_name = assignment.product_category_id.name or 'All Products'
            date_str = assignment.date_start.strftime('%Y-%m-%d') if assignment.date_start else ''
            
            assignment.name = f'{rep_name}: {geo_name} / {product_name} ({date_str})'
    
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for assignment in self:
            if assignment.date_start and assignment.date_end and assignment.date_start > assignment.date_end:
                raise ValidationError(_('End date cannot be earlier than start date.'))
    
    @api.constrains('weight')
    def _check_weight(self):
        for assignment in self:
            if assignment.weight <= 0 or assignment.weight > 100:
                raise ValidationError(_('Weight must be between 0 and 100.'))
    
    def is_valid_for_date(self, check_date=None):
        """Check if assignment is valid for the given date"""
        self.ensure_one()
        if not check_date:
            check_date = fields.Date.today()
            
        if isinstance(check_date, str):
            check_date = fields.Date.from_string(check_date)
            
        if self.date_start and check_date < self.date_start:
            return False
        if self.date_end and check_date > self.date_end:
            return False
        return True