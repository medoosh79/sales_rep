from odoo import models, fields, api
from datetime import datetime, timedelta


class SalesDashboardWizard(models.TransientModel):
    _name = 'sales.dashboard.wizard'
    _description = 'Sales Dashboard Report Wizard'

    # Date Range Options
    date_range = fields.Selection([
        ('today', 'Today'),
        ('this_week', 'This Week'),
        ('this_month', 'This Month'),
        ('this_quarter', 'This Quarter'),
        ('this_year', 'This Year'),
        ('custom', 'Custom Range')
    ], string='Date Range', default='this_month', required=True)
    
    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date')
    
    # Report Options
    report_type = fields.Selection([
        ('visit', 'Visit Report'),

    ], string='Report Type', default='visit', required=True)
    
    group_by = fields.Selection([
        ('sales_rep', 'Sales Representative'),

        ('customer', 'Customer'),
        ('date', 'Date'),
        ('state', 'State')
    ], string='Group By', default='sales_rep')
    
    # Filters
    sales_rep_ids = fields.Many2many('sales.rep', string='Sales Representatives')

    customer_ids = fields.Many2many('res.partner', string='Customers')
    visit_states = fields.Selection([
        ('all', 'All States'),
        ('scheduled', 'Scheduled Only'),
        ('completed', 'Completed Only'),
        ('cancelled', 'Cancelled Only')
    ], string='Visit States', default='all')
    
    include_charts = fields.Boolean(string='Include Charts', default=True)
    
    @api.onchange('date_range')
    def _onchange_date_range(self):
        """Set date_from and date_to based on selected range"""
        today = datetime.now().date()
        
        if self.date_range == 'today':
            self.date_from = self.date_to = today
        elif self.date_range == 'this_week':
            start_of_week = today - timedelta(days=today.weekday())
            self.date_from = start_of_week
            self.date_to = start_of_week + timedelta(days=6)
        elif self.date_range == 'this_month':
            self.date_from = today.replace(day=1)
            next_month = today.replace(day=28) + timedelta(days=4)
            self.date_to = next_month - timedelta(days=next_month.day)
        elif self.date_range == 'this_quarter':
            quarter = (today.month - 1) // 3 + 1
            self.date_from = today.replace(month=(quarter - 1) * 3 + 1, day=1)
            self.date_to = today.replace(month=quarter * 3, day=1) + timedelta(days=32)
            self.date_to = self.date_to.replace(day=1) - timedelta(days=1)
        elif self.date_range == 'this_year':
            self.date_from = today.replace(month=1, day=1)
            self.date_to = today.replace(month=12, day=31)
    
    def _get_domain(self):
        """Build domain for filtering records"""
        domain = []
        
        # Date filters
        if self.date_from:
            domain.append(('scheduled_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('scheduled_date', '<=', self.date_to))
        
        # Sales rep filter
        if self.sales_rep_ids:
            domain.append(('sales_rep_id', 'in', self.sales_rep_ids.ids))
        
        # Customer filter
        if self.customer_ids:
            domain.append(('customer_id', 'in', self.customer_ids.ids))
        
        # State filter
        if self.visit_states != 'all':
            domain.append(('state', '=', self.visit_states))
        
        return domain
    
    def action_generate_report(self):
        """Generate and open the selected report"""
        self.ensure_one()
        
        if self.report_type == 'visit':
            action = self.env.ref('sales_rep_mgmt_pro.action_visit_report').read()[0]
        else:
            action = self.env.ref('sales_rep_mgmt_pro.action_route_report').read()[0]
        
        # Apply filters to the action context
        context = action.get('context', {})
        if isinstance(context, str):
            context = eval(context)
        
        # Add date filters
        if self.date_range == 'custom':
            context.update({
                'search_default_date_from': self.date_from,
                'search_default_date_to': self.date_to,
            })
        elif self.date_range == 'today':
            context['search_default_today'] = 1
        elif self.date_range == 'this_week':
            context['search_default_this_week'] = 1
        elif self.date_range == 'this_month':
            context['search_default_this_month'] = 1
        
        # Add other filters
        if self.sales_rep_ids:
            context['search_default_sales_rep_ids'] = self.sales_rep_ids.ids
        if self.route_ids:
            context['search_default_route_ids'] = self.route_ids.ids
        if self.customer_ids:
            context['search_default_customer_ids'] = self.customer_ids.ids
        
        action['context'] = context
        return action
    
    def action_open_dashboard(self):
        """Open the dashboard with current filters"""
        self.ensure_one()
        
        # Create dashboard record
        dashboard = self.env['sales.dashboard'].create({
            'name': f'Dashboard - {self.date_range.title()}',
            'sales_rep_ids': [(6, 0, self.sales_rep_ids.ids)],
            'route_ids': [(6, 0, self.route_ids.ids)],
            'customer_ids': [(6, 0, self.customer_ids.ids)],
            'date_from': self.date_from,
            'date_to': self.date_to,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Dashboard',
            'res_model': 'sales.dashboard',
            'res_id': dashboard.id,
            'view_mode': 'form',
            'target': 'current',
        }


class SalesDashboard(models.TransientModel):
    _name = 'sales.dashboard'
    _description = 'Sales Representative Dashboard'

    name = fields.Char(string='Dashboard Name', required=True)
    
    # Filters (for context)
    sales_rep_ids = fields.Many2many('sales.rep', string='Sales Representatives')

    customer_ids = fields.Many2many('res.partner', string='Customers')
    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date')
    
    # KPI Fields
    total_visits = fields.Integer(string='Total Visits', compute='_compute_kpis')
    completed_visits = fields.Integer(string='Completed Visits', compute='_compute_kpis')
    pending_visits = fields.Integer(string='Pending Visits', compute='_compute_kpis')
    cancelled_visits = fields.Integer(string='Cancelled Visits', compute='_compute_kpis')
    
    # Performance Metrics
    completion_rate = fields.Float(string='Completion Rate (%)', compute='_compute_kpis')
    success_rate = fields.Float(string='Success Rate (%)', compute='_compute_kpis')
    on_time_rate = fields.Float(string='On Time Rate (%)', compute='_compute_kpis')
    
    # Revenue Metrics
    total_revenue = fields.Monetary(string='Total Revenue', compute='_compute_kpis')
    expected_revenue = fields.Monetary(string='Expected Revenue', compute='_compute_kpis')
    revenue_variance = fields.Monetary(string='Revenue Variance', compute='_compute_kpis')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    # Customer Statistics
    total_customers = fields.Integer(string='Total Customers', compute='_compute_kpis')
    
    def _get_domain(self):
        """Build domain for filtering records"""
        domain = []
        
        # Date filters
        if self.date_from:
            domain.append(('scheduled_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('scheduled_date', '<=', self.date_to))
        
        # Sales rep filter
        if self.sales_rep_ids:
            domain.append(('route_id.sales_rep_id', 'in', self.sales_rep_ids.ids))
        
        # Route filter
        if self.route_ids:
            domain.append(('route_id', 'in', self.route_ids.ids))
        
        # Customer filter
        if self.customer_ids:
            domain.append(('customer_id', 'in', self.customer_ids.ids))
        
        return domain
    
    @api.depends('sales_rep_ids', 'customer_ids', 'date_from', 'date_to')
    def _compute_kpis(self):
        """Compute KPI values based on filters"""
        for record in self:
            domain = record._get_domain()
            
            # Visit statistics - placeholder values since visit model is removed
            record.total_visits = 0
            record.completed_visits = 0
            record.pending_visits = 0
            record.cancelled_visits = 0
            
            # Rates
            record.completion_rate = 0.0
            record.success_rate = 0.0
            record.on_time_rate = 0.0
            
            # Revenue
            record.total_revenue = 0.0
            record.expected_revenue = 0.0
            record.revenue_variance = 0.0
            
            # Customer statistics
            customers = self.env['res.partner'].search([('is_company', '=', False)])
            if record.customer_ids:
                customers = customers.filtered(lambda c: c.id in record.customer_ids.ids)
            
            record.total_customers = len(customers)