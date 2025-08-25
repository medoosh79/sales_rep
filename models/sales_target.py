# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class SalesTarget(models.Model):
    _name = 'sales.target'
    _description = 'Sales Target Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_start desc, sales_rep_id'
    _rec_name = 'display_name'
    
    # Basic Information
    name = fields.Char('Target Name', required=True, tracking=True)
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True, tracking=True)
    active = fields.Boolean('Active', default=True, tracking=True)
    
    # Period Information
    period_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Period')
    ], string='Period Type', default='monthly', required=True, tracking=True)
    
    period_start = fields.Date('Period Start', required=True, tracking=True)
    period_end = fields.Date('Period End', required=True, tracking=True)
    
    # Target Values
    revenue_target = fields.Monetary('Revenue Target', currency_field='currency_id', tracking=True)
    visits_target = fields.Integer('Visits Target', tracking=True)
    new_customers_target = fields.Integer('New Customers Target', tracking=True)
    orders_target = fields.Integer('Orders Target', tracking=True)
    
    # Achievement Values
    revenue_achieved = fields.Monetary('Revenue Achieved', currency_field='currency_id', compute='_compute_achievements', store=True)
    visits_achieved = fields.Integer('Visits Achieved', compute='_compute_achievements', store=True)
    new_customers_achieved = fields.Integer('New Customers Achieved', compute='_compute_achievements', store=True)
    orders_achieved = fields.Integer('Orders Achieved', compute='_compute_achievements', store=True)
    
    # Achievement Percentages
    revenue_achievement_pct = fields.Float('Revenue Achievement %', compute='_compute_achievement_percentages', store=True)
    visits_achievement_pct = fields.Float('Visits Achievement %', compute='_compute_achievement_percentages', store=True)
    new_customers_achievement_pct = fields.Float('New Customers Achievement %', compute='_compute_achievement_percentages', store=True)
    orders_achievement_pct = fields.Float('Orders Achievement %', compute='_compute_achievement_percentages', store=True)
    
    # Overall Performance
    overall_achievement_pct = fields.Float('Overall Achievement %', compute='_compute_overall_achievement', store=True)
    performance_rating = fields.Selection([
        ('excellent', 'Excellent (>120%)'),
        ('good', 'Good (100-120%)'),
        ('satisfactory', 'Satisfactory (80-100%)'),
        ('needs_improvement', 'Needs Improvement (60-80%)'),
        ('poor', 'Poor (<60%)')
    ], string='Performance Rating', compute='_compute_performance_rating', store=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    # Additional Information
    notes = fields.Text('Notes')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    
    # KPI Lines
    kpi_line_ids = fields.One2many('sales.target.kpi', 'target_id', string='KPI Lines')
    
    @api.depends('name', 'sales_rep_id', 'period_start', 'period_end')
    def _compute_display_name(self):
        for target in self:
            if target.sales_rep_id and target.period_start and target.period_end:
                target.display_name = f"{target.sales_rep_id.name} - {target.period_start.strftime('%m/%Y')} to {target.period_end.strftime('%m/%Y')}"
            else:
                target.display_name = target.name or 'New Target'
    
    @api.depends('sales_rep_id', 'period_start', 'period_end')
    def _compute_achievements(self):
        for target in self:
            if not target.sales_rep_id or not target.period_start or not target.period_end:
                target.revenue_achieved = 0
                target.visits_achieved = 0
                target.new_customers_achieved = 0
                target.orders_achieved = 0
                continue
            
            # Calculate revenue from sale orders
            sale_orders = self.env['sale.order'].search([
                ('user_id', '=', target.sales_rep_id.user_id.id),
                ('date_order', '>=', target.period_start),
                ('date_order', '<=', target.period_end),
                ('state', 'in', ['sale', 'done'])
            ])
            target.revenue_achieved = sum(sale_orders.mapped('amount_total'))
            target.orders_achieved = len(sale_orders)
            
            # Calculate visits from daily visit schedules
            visit_lines = self.env['daily.visit.line'].search([
                ('schedule_id.sales_rep_id', '=', target.sales_rep_id.id),
                ('schedule_id.visit_date', '>=', target.period_start),
                ('schedule_id.visit_date', '<=', target.period_end),
                ('state', '=', 'completed')
            ])
            target.visits_achieved = len(visit_lines)
            
            # Calculate new customers
            new_customers = self.env['res.partner'].search([
                ('create_date', '>=', target.period_start),
                ('create_date', '<=', target.period_end),
                ('is_company', '=', True),
                ('customer_rank', '>', 0)
            ])
            target.new_customers_achieved = len(new_customers)
    
    @api.depends('revenue_target', 'revenue_achieved', 'visits_target', 'visits_achieved',
                 'new_customers_target', 'new_customers_achieved', 'orders_target', 'orders_achieved')
    def _compute_achievement_percentages(self):
        for target in self:
            target.revenue_achievement_pct = (target.revenue_achieved / target.revenue_target * 100) if target.revenue_target else 0
            target.visits_achievement_pct = (target.visits_achieved / target.visits_target * 100) if target.visits_target else 0
            target.new_customers_achievement_pct = (target.new_customers_achieved / target.new_customers_target * 100) if target.new_customers_target else 0
            target.orders_achievement_pct = (target.orders_achieved / target.orders_target * 100) if target.orders_target else 0
    
    @api.depends('revenue_achievement_pct', 'visits_achievement_pct', 'new_customers_achievement_pct', 'orders_achievement_pct')
    def _compute_overall_achievement(self):
        for target in self:
            # Calculate weighted average (revenue has higher weight)
            weights = {'revenue': 0.4, 'visits': 0.2, 'customers': 0.2, 'orders': 0.2}
            total_score = (
                target.revenue_achievement_pct * weights['revenue'] +
                target.visits_achievement_pct * weights['visits'] +
                target.new_customers_achievement_pct * weights['customers'] +
                target.orders_achievement_pct * weights['orders']
            )
            target.overall_achievement_pct = total_score
    
    @api.depends('overall_achievement_pct')
    def _compute_performance_rating(self):
        for target in self:
            if target.overall_achievement_pct >= 120:
                target.performance_rating = 'excellent'
            elif target.overall_achievement_pct >= 100:
                target.performance_rating = 'good'
            elif target.overall_achievement_pct >= 80:
                target.performance_rating = 'satisfactory'
            elif target.overall_achievement_pct >= 60:
                target.performance_rating = 'needs_improvement'
            else:
                target.performance_rating = 'poor'
    
    @api.onchange('period_type', 'period_start')
    def _onchange_period_type(self):
        if self.period_type and self.period_start:
            if self.period_type == 'monthly':
                self.period_end = self.period_start + relativedelta(months=1) - timedelta(days=1)
            elif self.period_type == 'quarterly':
                self.period_end = self.period_start + relativedelta(months=3) - timedelta(days=1)
            elif self.period_type == 'yearly':
                self.period_end = self.period_start + relativedelta(years=1) - timedelta(days=1)
    
    def action_activate(self):
        self.state = 'active'
    
    def action_complete(self):
        self.state = 'completed'
    
    def action_cancel(self):
        self.state = 'cancelled'
    
    def action_reset_to_draft(self):
        self.state = 'draft'
    
    @api.model
    def create_monthly_targets(self, sales_rep_ids=None):
        """Create monthly targets for sales representatives"""
        if not sales_rep_ids:
            sales_rep_ids = self.env['sales.rep'].search([('active', '=', True)]).ids
        
        today = fields.Date.today()
        period_start = today.replace(day=1)
        period_end = period_start + relativedelta(months=1) - timedelta(days=1)
        
        targets = []
        for sales_rep_id in sales_rep_ids:
            # Check if target already exists
            existing = self.search([
                ('sales_rep_id', '=', sales_rep_id),
                ('period_start', '=', period_start),
                ('period_end', '=', period_end)
            ])
            if not existing:
                target_vals = {
                    'name': f"Monthly Target - {period_start.strftime('%B %Y')}",
                    'sales_rep_id': sales_rep_id,
                    'period_type': 'monthly',
                    'period_start': period_start,
                    'period_end': period_end,
                    'state': 'active'
                }
                targets.append(target_vals)
        
        if targets:
            return self.create(targets)
        return self.browse()

class SalesTargetKPI(models.Model):
    _name = 'sales.target.kpi'
    _description = 'Sales Target KPI'
    _order = 'sequence, name'
    
    target_id = fields.Many2one('sales.target', string='Target', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    name = fields.Char('KPI Name', required=True)
    description = fields.Text('Description')
    
    # KPI Configuration
    kpi_type = fields.Selection([
        ('revenue', 'Revenue'),
        ('quantity', 'Quantity'),
        ('percentage', 'Percentage'),
        ('count', 'Count'),
        ('duration', 'Duration')
    ], string='KPI Type', required=True)
    
    target_value = fields.Float('Target Value', required=True)
    achieved_value = fields.Float('Achieved Value', compute='_compute_achieved_value', store=True)
    achievement_pct = fields.Float('Achievement %', compute='_compute_achievement_pct', store=True)
    
    # Weight for overall calculation
    weight = fields.Float('Weight', default=1.0, help='Weight for overall target calculation')
    
    # Status
    status = fields.Selection([
        ('on_track', 'On Track'),
        ('at_risk', 'At Risk'),
        ('behind', 'Behind'),
        ('achieved', 'Achieved')
    ], string='Status', compute='_compute_status', store=True)
    
    @api.depends('target_id', 'kpi_type', 'name')
    def _compute_achieved_value(self):
        # This would be implemented based on specific KPI calculation logic
        for kpi in self:
            kpi.achieved_value = 0  # Placeholder
    
    @api.depends('target_value', 'achieved_value')
    def _compute_achievement_pct(self):
        for kpi in self:
            if kpi.target_value:
                kpi.achievement_pct = (kpi.achieved_value / kpi.target_value) * 100
            else:
                kpi.achievement_pct = 0
    
    @api.depends('achievement_pct')
    def _compute_status(self):
        for kpi in self:
            if kpi.achievement_pct >= 100:
                kpi.status = 'achieved'
            elif kpi.achievement_pct >= 80:
                kpi.status = 'on_track'
            elif kpi.achievement_pct >= 60:
                kpi.status = 'at_risk'
            else:
                kpi.status = 'behind'