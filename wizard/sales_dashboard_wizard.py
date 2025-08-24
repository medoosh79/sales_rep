# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class SalesDashboardWizard(models.TransientModel):
    _name = 'sales.dashboard.wizard'
    _description = 'Sales Dashboard Report Wizard'

    # Date range filters
    date_from = fields.Date(
        string='Date From',
        default=lambda self: fields.Date.today().replace(day=1),
        required=True
    )
    date_to = fields.Date(
        string='Date To',
        default=fields.Date.today,
        required=True
    )
    
    # Quick date filters
    date_range = fields.Selection([
        ('today', 'Today'),
        ('yesterday', 'Yesterday'),
        ('this_week', 'This Week'),
        ('last_week', 'Last Week'),
        ('this_month', 'This Month'),
        ('last_month', 'Last Month'),
        ('this_quarter', 'This Quarter'),
        ('last_quarter', 'Last Quarter'),
        ('this_year', 'This Year'),
        ('last_year', 'Last Year'),
        ('custom', 'Custom Range')
    ], string='Date Range', default='this_month')
    
    # Filters
    sales_rep_ids = fields.Many2many(
        'res.users',
        string='Sales Representatives',
        help='Leave empty to include all sales representatives'
    )
    
    route_ids = fields.Many2many(
        'sales.route',
        string='Routes',
        help='Leave empty to include all routes'
    )
    
    customer_ids = fields.Many2many(
        'res.partner',
        string='Customers',
        help='Leave empty to include all customers'
    )
    
    visit_states = fields.Selection([
        ('all', 'All States'),
        ('completed', 'Completed Only'),
        ('pending', 'Pending Only'),
        ('cancelled', 'Cancelled Only')
    ], string='Visit States', default='all')
    
    # Report options
    report_type = fields.Selection([
        ('summary', 'Summary Report'),
        ('detailed', 'Detailed Report'),
        ('comparison', 'Comparison Report')
    ], string='Report Type', default='summary', required=True)
    
    group_by = fields.Selection([
        ('sales_rep', 'Sales Representative'),
        ('route', 'Route'),
        ('customer', 'Customer'),
        ('visit_type', 'Visit Type'),
        ('month', 'Month'),
        ('week', 'Week')
    ], string='Group By', default='sales_rep')
    
    include_charts = fields.Boolean(
        string='Include Charts',
        default=True,
        help='Include graphical charts in the report'
    )
    
    @api.onchange('date_range')
    def _onchange_date_range(self):
        """Update date_from and date_to based on selected range"""
        today = fields.Date.today()
        
        if self.date_range == 'today':
            self.date_from = self.date_to = today
        elif self.date_range == 'yesterday':
            yesterday = today - timedelta(days=1)
            self.date_from = self.date_to = yesterday
        elif self.date_range == 'this_week':
            start_week = today - timedelta(days=today.weekday())
            self.date_from = start_week
            self.date_to = today
        elif self.date_range == 'last_week':
            start_week = today - timedelta(days=today.weekday() + 7)
            end_week = start_week + timedelta(days=6)
            self.date_from = start_week
            self.date_to = end_week
        elif self.date_range == 'this_month':
            self.date_from = today.replace(day=1)
            self.date_to = today
        elif self.date_range == 'last_month':
            first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            last_day_last_month = today.replace(day=1) - timedelta(days=1)
            self.date_from = first_day_last_month
            self.date_to = last_day_last_month
        elif self.date_range == 'this_quarter':
            quarter_start = today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
            self.date_from = quarter_start
            self.date_to = today
        elif self.date_range == 'last_quarter':
            this_quarter_start = today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
            last_quarter_start = this_quarter_start - relativedelta(months=3)
            last_quarter_end = this_quarter_start - timedelta(days=1)
            self.date_from = last_quarter_start
            self.date_to = last_quarter_end
        elif self.date_range == 'this_year':
            self.date_from = today.replace(month=1, day=1)
            self.date_to = today
        elif self.date_range == 'last_year':
            last_year = today.year - 1
            self.date_from = today.replace(year=last_year, month=1, day=1)
            self.date_to = today.replace(year=last_year, month=12, day=31)
    
    def action_generate_report(self):
        """Generate the dashboard report"""
        self.ensure_one()
        
        # Build domain for visits
        domain = [
            ('scheduled_date', '>=', self.date_from),
            ('scheduled_date', '<=', self.date_to)
        ]
        
        if self.sales_rep_ids:
            domain.append(('sales_rep_id', 'in', self.sales_rep_ids.ids))
        
        if self.route_ids:
            domain.append(('route_id', 'in', self.route_ids.ids))
        
        if self.customer_ids:
            domain.append(('customer_id', 'in', self.customer_ids.ids))
        
        if self.visit_states != 'all':
            if self.visit_states == 'completed':
                domain.append(('state', '=', 'completed'))
            elif self.visit_states == 'pending':
                domain.append(('state', 'in', ['draft', 'confirmed', 'in_progress']))
            elif self.visit_states == 'cancelled':
                domain.append(('state', '=', 'cancelled'))
        
        # Generate report based on type
        if self.report_type == 'summary':
            return self._generate_summary_report(domain)
        elif self.report_type == 'detailed':
            return self._generate_detailed_report(domain)
        elif self.report_type == 'comparison':
            return self._generate_comparison_report(domain)
    
    def _generate_summary_report(self, domain):
        """Generate summary report"""
        context = {
            'search_default_' + self.group_by: 1,
            'dashboard_wizard_id': self.id,
            'date_from': self.date_from,
            'date_to': self.date_to
        }
        
        return {
            'name': _('Sales Dashboard - Summary Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'visit.report',
            'view_mode': 'pivot,graph,list',
            'domain': domain,
            'context': context,
            'target': 'current'
        }
    
    def _generate_detailed_report(self, domain):
        """Generate detailed report"""
        context = {
            'search_default_' + self.group_by: 1,
            'dashboard_wizard_id': self.id,
            'date_from': self.date_from,
            'date_to': self.date_to
        }
        
        return {
            'name': _('Sales Dashboard - Detailed Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'visit.report',
            'view_mode': 'list,pivot,graph',
            'domain': domain,
            'context': context,
            'target': 'current'
        }
    
    def _generate_comparison_report(self, domain):
        """Generate comparison report"""
        # For comparison, we'll show route performance
        context = {
            'search_default_' + self.group_by: 1,
            'dashboard_wizard_id': self.id,
            'date_from': self.date_from,
            'date_to': self.date_to
        }
        
        return {
            'name': _('Sales Dashboard - Comparison Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'route.report',
            'view_mode': 'list,pivot,graph',
            'context': context,
            'target': 'current'
        }
    
    def action_open_dashboard(self):
        """Open the main dashboard view"""
        return {
            'name': _('Sales Representative Dashboard'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.dashboard',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'date_from': self.date_from,
                'date_to': self.date_to,
                'sales_rep_ids': self.sales_rep_ids.ids,
                'route_ids': self.route_ids.ids
            }
        }

class SalesDashboard(models.TransientModel):
    _name = 'sales.dashboard'
    _description = 'Sales Representative Dashboard'
    
    name = fields.Char(string='Dashboard', default='Sales Dashboard')
    
    # KPI Fields
    total_visits = fields.Integer(string='Total Visits', compute='_compute_kpis')
    completed_visits = fields.Integer(string='Completed Visits', compute='_compute_kpis')
    pending_visits = fields.Integer(string='Pending Visits', compute='_compute_kpis')
    cancelled_visits = fields.Integer(string='Cancelled Visits', compute='_compute_kpis')
    
    completion_rate = fields.Float(string='Completion Rate (%)', compute='_compute_kpis')
    success_rate = fields.Float(string='Success Rate (%)', compute='_compute_kpis')
    on_time_rate = fields.Float(string='On Time Rate (%)', compute='_compute_kpis')
    
    total_revenue = fields.Monetary(string='Total Revenue', compute='_compute_kpis')
    expected_revenue = fields.Monetary(string='Expected Revenue', compute='_compute_kpis')
    revenue_variance = fields.Monetary(string='Revenue Variance', compute='_compute_kpis')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    total_routes = fields.Integer(string='Total Routes', compute='_compute_kpis')
    active_routes = fields.Integer(string='Active Routes', compute='_compute_kpis')
    total_customers = fields.Integer(string='Total Customers', compute='_compute_kpis')
    
    @api.depends_context('date_from', 'date_to', 'sales_rep_ids', 'route_ids')
    def _compute_kpis(self):
        """Compute dashboard KPIs"""
        for dashboard in self:
            # Get context data
            date_from = self.env.context.get('date_from', fields.Date.today().replace(day=1))
            date_to = self.env.context.get('date_to', fields.Date.today())
            sales_rep_ids = self.env.context.get('sales_rep_ids', [])
            route_ids = self.env.context.get('route_ids', [])
            
            # Build domain
            visit_domain = [
                ('scheduled_date', '>=', date_from),
                ('scheduled_date', '<=', date_to)
            ]
            
            if sales_rep_ids:
                visit_domain.append(('sales_rep_id', 'in', sales_rep_ids))
            if route_ids:
                visit_domain.append(('route_id', 'in', route_ids))
            
            # Get visit data
            visits = self.env['customer.visit'].search(visit_domain)
            
            dashboard.total_visits = len(visits)
            dashboard.completed_visits = len(visits.filtered(lambda v: v.state == 'completed'))
            dashboard.pending_visits = len(visits.filtered(lambda v: v.state in ['draft', 'confirmed', 'in_progress']))
            dashboard.cancelled_visits = len(visits.filtered(lambda v: v.state == 'cancelled'))
            
            # Calculate rates
            if dashboard.total_visits > 0:
                dashboard.completion_rate = (dashboard.completed_visits / dashboard.total_visits) * 100
                successful_visits = len(visits.filtered(lambda v: v.visit_outcome in ['successful', 'partially_successful']))
                dashboard.success_rate = (successful_visits / dashboard.total_visits) * 100
                on_time_visits = len(visits.filtered(lambda v: v.actual_start_time and v.actual_start_time <= fields.Datetime.combine(v.scheduled_date, datetime.min.time())))
                dashboard.on_time_rate = (on_time_visits / dashboard.total_visits) * 100
            else:
                dashboard.completion_rate = 0
                dashboard.success_rate = 0
                dashboard.on_time_rate = 0
            
            # Revenue calculations
            dashboard.total_revenue = sum(visits.mapped('actual_revenue'))
            dashboard.expected_revenue = sum(visits.mapped('expected_revenue'))
            dashboard.revenue_variance = dashboard.total_revenue - dashboard.expected_revenue
            
            # Route data
            route_domain = []
            if sales_rep_ids:
                route_domain.append(('sales_rep_id', 'in', sales_rep_ids))
            if route_ids:
                route_domain.append(('id', 'in', route_ids))
            
            routes = self.env['sales.route'].search(route_domain)
            dashboard.total_routes = len(routes)
            dashboard.active_routes = len(routes.filtered(lambda r: r.state == 'active'))
            dashboard.total_customers = len(routes.mapped('customer_ids'))