# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta

class DailyVisitSchedule(models.Model):
    _name = 'daily.visit.schedule'
    _description = 'Daily Visit Schedule'
    _order = 'visit_date desc, sequence'
    _rec_name = 'display_name'

    # Basic Information
    name = fields.Char('Schedule Name', required=True, default=lambda self: self._get_default_name())
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True, default=lambda self: self._get_current_sales_rep())
    visit_date = fields.Date('Visit Date', required=True, default=fields.Date.today)
    sequence = fields.Integer('Sequence', default=10)
    
    # Schedule Details
    start_time = fields.Float('Start Time', default=8.0, help='Start time in 24-hour format (e.g., 8.5 for 8:30 AM)')
    end_time = fields.Float('End Time', default=17.0, help='End time in 24-hour format (e.g., 17.5 for 5:30 PM)')
    total_duration = fields.Float('Total Duration (Hours)', compute='_compute_total_duration', store=True)
    
    # Status and Progress
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    progress = fields.Float('Progress (%)', compute='_compute_progress', store=True)
    completed_visits = fields.Integer('Completed Visits', compute='_compute_visit_stats', store=True)
    total_visits = fields.Integer('Total Visits', compute='_compute_visit_stats', store=True)
    
    # Visit Lines (One2many relationship)
    visit_line_ids = fields.One2many('daily.visit.line', 'schedule_id', string='Visit Lines')
    
    # Notes and Comments
    notes = fields.Text('Notes')
    internal_notes = fields.Text('Internal Notes')
    
    # Computed Fields for Dashboard
    estimated_travel_time = fields.Float('Estimated Travel Time (Hours)', compute='_compute_travel_stats', store=True)
    actual_travel_time = fields.Float('Actual Travel Time (Hours)', compute='_compute_travel_stats', store=True)
    total_distance = fields.Float('Total Distance (KM)', compute='_compute_travel_stats', store=True)
    
    # Financial Information
    expected_revenue = fields.Monetary('Expected Revenue', compute='_compute_financial_stats', store=True)
    actual_revenue = fields.Monetary('Actual Revenue', compute='_compute_financial_stats', store=True)
    revenue_variance = fields.Monetary('Revenue Variance', compute='_compute_financial_stats', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Time Fields for Tracker
    planned_start_time = fields.Float('Planned Start Time', related='start_time', store=True)
    planned_end_time = fields.Float('Planned End Time', related='end_time', store=True)
    actual_start_time = fields.Float('Actual Start Time', compute='_compute_actual_times', store=True)
    actual_end_time = fields.Float('Actual End Time', compute='_compute_actual_times', store=True)
    
    # Travel and Cost Fields
    total_travel_time = fields.Float('Total Travel Time (Hours)', related='actual_travel_time', store=True)
    fuel_cost = fields.Monetary('Fuel Cost', compute='_compute_fuel_cost', store=True)
    
    @api.model
    def _get_default_name(self):
        today = fields.Date.today()
        return f"Daily Schedule - {today.strftime('%Y-%m-%d')}"
    
    @api.model
    def _get_current_sales_rep(self):
        # Try to get current user's sales rep record
        sales_rep = self.env['sales.rep'].search([('user_id', '=', self.env.user.id)], limit=1)
        return sales_rep.id if sales_rep else False
    
    @api.depends('name', 'visit_date', 'sales_rep_id')
    def _compute_display_name(self):
        for record in self:
            if record.sales_rep_id and record.visit_date:
                record.display_name = f"{record.sales_rep_id.name} - {record.visit_date.strftime('%Y-%m-%d')}"
            else:
                record.display_name = record.name or 'New Schedule'
    
    @api.depends('start_time', 'end_time')
    def _compute_total_duration(self):
        for record in self:
            if record.end_time > record.start_time:
                record.total_duration = record.end_time - record.start_time
            else:
                record.total_duration = 0.0
    
    @api.depends('visit_line_ids.state')
    def _compute_progress(self):
        for record in self:
            total_lines = len(record.visit_line_ids)
            if total_lines > 0:
                completed_lines = len(record.visit_line_ids.filtered(lambda l: l.state == 'completed'))
                record.progress = (completed_lines / total_lines) * 100
            else:
                record.progress = 0.0
    
    @api.depends('visit_line_ids', 'visit_line_ids.state')
    def _compute_visit_stats(self):
        for record in self:
            record.total_visits = len(record.visit_line_ids)
            record.completed_visits = len(record.visit_line_ids.filtered(lambda l: l.state == 'completed'))
    
    @api.depends('visit_line_ids.estimated_duration', 'visit_line_ids.actual_duration', 'visit_line_ids.travel_distance')
    def _compute_travel_stats(self):
        for record in self:
            record.estimated_travel_time = sum(record.visit_line_ids.mapped('estimated_duration'))
            record.actual_travel_time = sum(record.visit_line_ids.mapped('actual_duration'))
            record.total_distance = sum(record.visit_line_ids.mapped('travel_distance'))
    
    @api.depends('visit_line_ids.expected_amount', 'visit_line_ids.actual_amount')
    def _compute_financial_stats(self):
        for record in self:
            record.expected_revenue = sum(record.visit_line_ids.mapped('expected_amount'))
            record.actual_revenue = sum(record.visit_line_ids.mapped('actual_amount'))
            record.revenue_variance = record.actual_revenue - record.expected_revenue
    
    @api.depends('visit_line_ids.actual_start_time', 'visit_line_ids.actual_end_time')
    def _compute_actual_times(self):
        for record in self:
            visit_lines = record.visit_line_ids.filtered(lambda l: l.actual_start_time and l.actual_end_time)
            if visit_lines:
                record.actual_start_time = min(visit_lines.mapped('actual_start_time'))
                record.actual_end_time = max(visit_lines.mapped('actual_end_time'))
            else:
                record.actual_start_time = 0.0
                record.actual_end_time = 0.0
    
    @api.depends('total_distance')
    def _compute_fuel_cost(self):
        # Simple fuel cost calculation: distance * fuel_rate_per_km
        # You can customize this based on your business logic
        fuel_rate_per_km = 0.15  # Default rate per km
        for record in self:
            record.fuel_cost = record.total_distance * fuel_rate_per_km
    
    def action_confirm(self):
        """Confirm the daily schedule"""
        self.state = 'confirmed'
        return True
    
    def action_start(self):
        """Start the daily schedule"""
        self.state = 'in_progress'
        return True
    
    def action_complete(self):
        """Complete the daily schedule"""
        self.state = 'completed'
        return True
    
    @api.model
    def get_today_visits(self, sales_rep_id=None):
        """Get today's visits for real-time tracking"""
        if not sales_rep_id:
            sales_rep_id = self.env.user.id
        
        today = fields.Date.today()
        schedule = self.search([
            ('sales_rep_id', '=', sales_rep_id),
            ('visit_date', '=', today)
        ], limit=1)
        
        if not schedule:
            return {'visits': [], 'schedule_id': False}
        
        visits = []
        for line in schedule.visit_line_ids:
            visits.append({
                'id': line.id,
                'display_name': line.display_name,
                'customer_id': [line.customer_id.id, line.customer_id.name],
                'planned_time': line.planned_time,
                'planned_duration': line.planned_duration,
                'visit_type': line.visit_type,
                'state': line.state,
                'actual_start_time': line.actual_start_time,
                'actual_end_time': line.actual_end_time,
                'customer_address': line.customer_address,
                'phone': line.phone,
                'expected_amount': line.expected_amount,
            })
        
        return {
            'visits': visits,
            'schedule_id': schedule.id,
            'schedule_state': schedule.state,
        }
    
    @api.model
    def update_visit_status(self, visit_id, status, location=None):
        """Update visit status in real-time"""
        visit = self.env['daily.visit.line'].browse(visit_id)
        if not visit.exists():
            return {'success': False, 'message': 'Visit not found'}
        
        current_time = fields.Datetime.now().hour + fields.Datetime.now().minute / 60.0
        
        if status == 'in_progress':
            visit.write({
                'state': 'in_progress',
                'actual_start_time': current_time,
            })
        elif status == 'completed':
            visit.write({
                'state': 'completed',
                'actual_end_time': current_time,
                'visit_result': 'successful',
            })
        elif status == 'cancelled':
            visit.write({
                'state': 'cancelled',
                'visit_result': 'unsuccessful',
            })
        
        return {'success': True, 'message': 'Visit status updated successfully'}
    
    @api.model
    def reschedule_visit(self, visit_id, new_time):
        """Reschedule a visit"""
        visit = self.env['daily.visit.line'].browse(visit_id)
        if not visit.exists():
            return {'success': False, 'message': 'Visit not found'}
        
        if visit.state != 'planned':
            return {'success': False, 'message': 'Only planned visits can be rescheduled'}
        
        visit.write({'planned_time': new_time})
        
        return {'success': True, 'message': 'Visit rescheduled successfully'}
    
    def action_cancel(self):
        """Cancel the daily schedule"""
        self.state = 'cancelled'
        return True
    
    def action_reset_to_draft(self):
        """Reset to draft state"""
        self.state = 'draft'
        return True
    
    @api.model
    def create_daily_schedule_wizard(self):
        """Open wizard to create daily schedule"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Daily Schedule',
            'res_model': 'daily.visit.schedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sales_rep_id': self._get_current_sales_rep(),
                'default_visit_date': fields.Date.today(),
            }
        }

class DailyVisitLine(models.Model):
    _name = 'daily.visit.line'
    _description = 'Daily Visit Line'
    _order = 'sequence, planned_time'
    _rec_name = 'display_name'
    
    # Relationship
    schedule_id = fields.Many2one('daily.visit.schedule', string='Schedule', required=True, ondelete='cascade')
    
    # Basic Information
    sequence = fields.Integer('Sequence', default=10)
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    customer_id = fields.Many2one('res.partner', string='Customer', required=True, domain=[('is_company', '=', True)])
    contact_person = fields.Char('Contact Person')
    phone = fields.Char('Phone', related='customer_id.phone', readonly=True)
    email = fields.Char('Email', related='customer_id.email', readonly=True)
    
    # Visit Planning
    planned_time = fields.Float('Planned Time', required=True, help='Planned visit time in 24-hour format')
    planned_duration = fields.Float('Planned Duration (Hours)', default=1.0)
    visit_type = fields.Selection([
        ('sales', 'Sales Visit'),
        ('follow_up', 'Follow Up'),
        ('delivery', 'Delivery'),
        ('collection', 'Collection'),
        ('support', 'Support'),
        ('other', 'Other')
    ], string='Visit Type', default='sales', required=True)
    
    # Visit Execution
    actual_start_time = fields.Float('Actual Start Time')
    actual_end_time = fields.Float('Actual End Time')
    actual_duration = fields.Float('Actual Duration (Hours)', compute='_compute_actual_duration', store=True)
    
    # Status and Results
    state = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled')
    ], string='Status', default='planned', tracking=True)
    
    visit_result = fields.Selection([
        ('successful', 'Successful'),
        ('partial', 'Partial Success'),
        ('unsuccessful', 'Unsuccessful'),
        ('no_contact', 'No Contact')
    ], string='Visit Result')
    
    # Financial Information
    expected_amount = fields.Monetary('Expected Amount', currency_field='currency_id')
    actual_amount = fields.Monetary('Actual Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='schedule_id.currency_id', store=True)
    
    # Location and Travel
    customer_address = fields.Char('Customer Address', related='customer_id.contact_address', readonly=True)
    travel_distance = fields.Float('Travel Distance (KM)')
    estimated_duration = fields.Float('Estimated Travel Duration (Hours)', default=0.5)
    
    # Notes and Follow-up
    visit_notes = fields.Text('Visit Notes')
    follow_up_required = fields.Boolean('Follow-up Required')
    follow_up_date = fields.Date('Follow-up Date')
    follow_up_notes = fields.Text('Follow-up Notes')
    
    # Attachments
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    
    @api.depends('customer_id', 'planned_time', 'visit_type')
    def _compute_display_name(self):
        for record in self:
            if record.customer_id and record.planned_time:
                time_str = f"{int(record.planned_time):02d}:{int((record.planned_time % 1) * 60):02d}"
                record.display_name = f"{record.customer_id.name} - {time_str} ({record.visit_type})"
            else:
                record.display_name = 'New Visit'
    
    @api.depends('actual_start_time', 'actual_end_time')
    def _compute_actual_duration(self):
        for record in self:
            if record.actual_start_time and record.actual_end_time:
                record.actual_duration = record.actual_end_time - record.actual_start_time
            else:
                record.actual_duration = 0.0
    
    def action_start_visit(self):
        """Start the visit"""
        self.state = 'in_progress'
        self.actual_start_time = fields.Float.now()
        return True
    
    def action_complete_visit(self):
        """Complete the visit"""
        self.state = 'completed'
        if not self.actual_end_time:
            self.actual_end_time = fields.Float.now()
        return True
    
    def action_cancel_visit(self):
        """Cancel the visit"""
        self.state = 'cancelled'
        return True
    
    def action_reschedule_visit(self):
        """Reschedule the visit"""
        self.state = 'rescheduled'
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reschedule Visit',
            'res_model': 'visit.reschedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_visit_line_id': self.id,
                'default_customer_id': self.customer_id.id,
            }
        }
    
    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        if self.customer_id:
            # Auto-fill contact person if available
            contacts = self.customer_id.child_ids.filtered(lambda c: c.function)
            if contacts:
                self.contact_person = contacts[0].name