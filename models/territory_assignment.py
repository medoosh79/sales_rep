# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class TerritoryAssignment(models.Model):
    _name = 'territory.assignment'
    _description = 'Territory Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'product_line_id, geo_node_id, sequence'
    
    # Core fields
    name = fields.Char(string='Coverage Name', compute='_compute_name', store=True)
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True, tracking=True)
    
    # Main relationships
    product_line_id = fields.Many2one('product.line', string='Product Line', required=True, 
                                    ondelete='cascade', tracking=True)
    geo_node_id = fields.Many2one('geo.node', string='Geographic Area', required=True, 
                                ondelete='cascade', tracking=True)
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', 
                                 tracking=True)
    
    # Coverage details
    coverage_type = fields.Selection([
        ('exclusive', 'Exclusive Coverage'),
        ('shared', 'Shared Coverage'),
        ('backup', 'Backup Coverage')
    ], string='Coverage Type', default='exclusive', required=True, tracking=True)
    
    priority = fields.Selection([
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High'),
        ('4', 'Very High')
    ], string='Priority', default='2', tracking=True)
    
    # Date fields
    date_start = fields.Date(string='Start Date', default=fields.Date.today, tracking=True)
    date_end = fields.Date(string='End Date', tracking=True)
    
    # Commission and targets
    commission_rate = fields.Float(string='Commission Rate (%)', digits=(5, 2), tracking=True)
    monthly_target = fields.Float(string='Monthly Target', tracking=True)
    quarterly_target = fields.Float(string='Quarterly Target', tracking=True)
    yearly_target = fields.Float(string='Yearly Target', tracking=True)
    
    # Additional information
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one('res.company', string='Company', 
                               default=lambda self: self.env.company)
    
    # Computed fields
    product_count = fields.Integer(string='Products', compute='_compute_product_count')
    child_areas_count = fields.Integer(string='Child Areas', compute='_compute_child_areas_count')
    
    @api.depends('product_line_id', 'geo_node_id')
    def _compute_name(self):
        for coverage in self:
            if coverage.product_line_id and coverage.geo_node_id:
                coverage.name = f"{coverage.product_line_id.name} - {coverage.geo_node_id.name}"
            else:
                coverage.name = 'New Coverage'
    
    @api.depends('name', 'sales_rep_id')
    def _compute_display_name(self):
        for coverage in self:
            if coverage.sales_rep_id:
                coverage.display_name = f"{coverage.name} ({coverage.sales_rep_id.name})"
            else:
                coverage.display_name = coverage.name or 'New Coverage'
    
    @api.depends('product_line_id.product_count')
    def _compute_product_count(self):
        for coverage in self:
            coverage.product_count = coverage.product_line_id.product_count if coverage.product_line_id else 0
    
    @api.depends('geo_node_id.child_ids')
    def _compute_child_areas_count(self):
        for coverage in self:
            coverage.child_areas_count = len(coverage.geo_node_id.child_ids) if coverage.geo_node_id else 0
    
    @api.constrains('product_line_id', 'geo_node_id', 'coverage_type', 'date_start', 'date_end')
    def _check_exclusive_coverage(self):
        """Ensure exclusive coverage doesn't overlap"""
        for coverage in self:
            if coverage.coverage_type == 'exclusive':
                domain = [
                    ('product_line_id', '=', coverage.product_line_id.id),
                    ('geo_node_id', '=', coverage.geo_node_id.id),
                    ('coverage_type', '=', 'exclusive'),
                    ('id', '!=', coverage.id),
                    ('active', '=', True)
                ]
                
                # Check date overlap
                if coverage.date_start:
                    domain.append(('date_end', '>=', coverage.date_start))
                if coverage.date_end:
                    domain.append(('date_start', '<=', coverage.date_end))
                else:
                    domain.append('|')
                    domain.append(('date_end', '=', False))
                    domain.append(('date_start', '<=', coverage.date_start))
                
                existing = self.search(domain)
                if existing:
                    raise ValidationError(_(
                        'Exclusive coverage already exists for %s in %s during this period.'
                    ) % (coverage.product_line_id.name, coverage.geo_node_id.name))
    
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        """Ensure end date is after start date"""
        for coverage in self:
            if coverage.date_start and coverage.date_end and coverage.date_start > coverage.date_end:
                raise ValidationError(_('End date must be after start date.'))
    
    @api.constrains('commission_rate')
    def _check_commission_rate(self):
        """Ensure commission rate is valid"""
        for coverage in self:
            if coverage.commission_rate and (coverage.commission_rate < 0 or coverage.commission_rate > 100):
                raise ValidationError(_('Commission rate must be between 0 and 100.'))
    
    @api.constrains('sales_rep_id', 'product_line_id', 'geo_node_id', 'date_start', 'date_end', 'active')
    def _check_unique_sales_rep_assignment(self):
        """Ensure no duplicate sales rep assignments for same area and product line in overlapping periods"""
        for assignment in self:
            if assignment.sales_rep_id and assignment.active:
                domain = [
                    ('sales_rep_id', '=', assignment.sales_rep_id.id),
                    ('product_line_id', '=', assignment.product_line_id.id),
                    ('geo_node_id', '=', assignment.geo_node_id.id),
                    ('id', '!=', assignment.id),
                    ('active', '=', True)
                ]
                
                # Check for date overlap
                if assignment.date_start:
                    # If current assignment has start date, check for overlaps
                    if assignment.date_end:
                        # Current assignment has both start and end dates
                        domain.extend([
                            '|',
                            '&', ('date_start', '<=', assignment.date_end), ('date_start', '>=', assignment.date_start),
                            '|',
                            '&', ('date_end', '>=', assignment.date_start), ('date_end', '<=', assignment.date_end),
                            '|',
                            '&', ('date_start', '<=', assignment.date_start), ('date_end', '>=', assignment.date_end),
                            '&', ('date_start', '<=', assignment.date_start), ('date_end', '=', False)
                        ])
                    else:
                        # Current assignment has start date but no end date (ongoing)
                        domain.extend([
                            '|',
                            ('date_end', '>=', assignment.date_start),
                            ('date_end', '=', False)
                        ])
                else:
                    # Current assignment has no start date, check for any active assignments
                    pass  # Domain already filters for active assignments
                
                existing = self.search(domain)
                if existing:
                    existing_assignment = existing[0]
                    start_str = assignment.date_start.strftime('%Y-%m-%d') if assignment.date_start else 'غير محدد'
                    end_str = assignment.date_end.strftime('%Y-%m-%d') if assignment.date_end else 'مفتوح'
                    existing_start_str = existing_assignment.date_start.strftime('%Y-%m-%d') if existing_assignment.date_start else 'غير محدد'
                    existing_end_str = existing_assignment.date_end.strftime('%Y-%m-%d') if existing_assignment.date_end else 'مفتوح'
                    
                    raise ValidationError(_(
                        'المندوب "%s" مُعيَّن بالفعل للمنطقة "%s" وخط الإنتاج "%s" في فترة متداخلة.\n\n'
                        'التعيين الحالي: من %s إلى %s\n'
                        'التعيين الموجود: من %s إلى %s\n\n'
                        'لا يمكن تعيين نفس المندوب لنفس المنطقة وخط الإنتاج في فترات متداخلة.'
                    ) % (
                        assignment.sales_rep_id.name,
                        assignment.geo_node_id.name,
                        assignment.product_line_id.name,
                        start_str, end_str,
                        existing_start_str, existing_end_str
                    ))
    
    @api.constrains('geo_node_id', 'date_start', 'date_end', 'active', 'sales_rep_id')
    def _check_unique_territory_assignment(self):
        """Ensure no multiple sales reps assigned to same territory in overlapping periods"""
        for assignment in self:
            if assignment.active and assignment.sales_rep_id:
                domain = [
                    ('geo_node_id', '=', assignment.geo_node_id.id),
                    ('id', '!=', assignment.id),
                    ('active', '=', True),
                    ('sales_rep_id', '!=', False)
                ]
                
                # Check for date overlap
                if assignment.date_start:
                    if assignment.date_end:
                        # Current assignment has both start and end dates
                        domain.extend([
                            '|',
                            '&', ('date_start', '<=', assignment.date_end), ('date_start', '>=', assignment.date_start),
                            '|',
                            '&', ('date_end', '>=', assignment.date_start), ('date_end', '<=', assignment.date_end),
                            '|',
                            '&', ('date_start', '<=', assignment.date_start), ('date_end', '>=', assignment.date_end),
                            '&', ('date_start', '<=', assignment.date_start), ('date_end', '=', False)
                        ])
                    else:
                        # Current assignment has start date but no end date (ongoing)
                        domain.extend([
                            '|',
                            ('date_end', '>=', assignment.date_start),
                            ('date_end', '=', False)
                        ])
                else:
                    # Current assignment has no start date, check for any active assignments
                    pass  # Domain already filters for active assignments
                
                existing = self.search(domain)
                if existing:
                    existing_assignment = existing[0]
                    start_str = assignment.date_start.strftime('%Y-%m-%d') if assignment.date_start else 'غير محدد'
                    end_str = assignment.date_end.strftime('%Y-%m-%d') if assignment.date_end else 'مفتوح'
                    existing_start_str = existing_assignment.date_start.strftime('%Y-%m-%d') if existing_assignment.date_start else 'غير محدد'
                    existing_end_str = existing_assignment.date_end.strftime('%Y-%m-%d') if existing_assignment.date_end else 'مفتوح'
                    
                    raise ValidationError(_(
                        'لا يمكن تعيين مندوب آخر على المنطقة "%s" لأنها مُعيَّنة بالفعل للمندوب "%s" في فترة متداخلة.\n\n'
                        'التعيين الحالي: المندوب "%s" من %s إلى %s\n'
                        'التعيين الموجود: المندوب "%s" من %s إلى %s\n\n'
                        'يجب إنهاء التعيين الحالي أولاً أو تحديد فترة زمنية غير متداخلة.'
                    ) % (
                        assignment.geo_node_id.name,
                        existing_assignment.sales_rep_id.name,
                        assignment.sales_rep_id.name,
                        start_str, end_str,
                        existing_assignment.sales_rep_id.name,
                        existing_start_str, existing_end_str
                    ))
    
    def action_view_products(self):
        """Action to view products in this coverage"""
        self.ensure_one()
        return {
            'name': _('Products'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.product_line_id.product_ids.ids)],
            'context': {'default_product_line_id': self.product_line_id.id}
        }
    
    def action_view_child_areas(self):
        """Action to view child geographic areas"""
        self.ensure_one()
        return {
            'name': _('Child Areas'),
            'type': 'ir.actions.act_window',
            'res_model': 'geo.node',
            'view_mode': 'list,form',
            'domain': [('parent_id', '=', self.geo_node_id.id)],
            'context': {'default_parent_id': self.geo_node_id.id}
        }
    
    def action_create_child_coverages(self):
        """Create coverage for all child areas with same settings"""
        self.ensure_one()
        child_areas = self.geo_node_id.child_ids
        if not child_areas:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Child Areas'),
                    'message': _('This geographic area has no child areas.'),
                    'type': 'warning',
                }
            }
        
        created_coverages = []
        for child in child_areas:
            # Check if coverage already exists
            existing = self.search([
                ('product_line_id', '=', self.product_line_id.id),
                ('geo_node_id', '=', child.id),
                ('active', '=', True)
            ])
            
            if not existing:
                coverage_vals = {
                    'product_line_id': self.product_line_id.id,
                    'geo_node_id': child.id,
                    'coverage_type': self.coverage_type,
                    'priority': self.priority,
                    'commission_rate': self.commission_rate,
                    'date_start': self.date_start,
                    'date_end': self.date_end,
                    'company_id': self.company_id.id,
                }
                created_coverages.append(self.create(coverage_vals))
        
        if created_coverages:
            return {
                'name': _('Created Assignments'),
                'type': 'ir.actions.act_window',
                'res_model': 'territory.assignment',
                'view_mode': 'list,form',
                'domain': [('id', 'in', [c.id for c in created_coverages])],
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No New Coverages'),
                    'message': _('All child areas already have coverage for this product line.'),
                    'type': 'info',
                }
            }