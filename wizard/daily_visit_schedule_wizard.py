# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta

class DailyVisitScheduleWizard(models.TransientModel):
    _name = 'daily.visit.schedule.wizard'
    _description = 'Daily Visit Schedule Wizard'
    
    # Basic Information
    name = fields.Char('Schedule Name', required=True)
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True, default=lambda self: self._get_current_sales_rep())
    visit_date = fields.Date('Visit Date', required=True, default=fields.Date.today)
    start_time = fields.Float('Start Time', default=8.0, help='Start time in 24-hour format')
    end_time = fields.Float('End Time', default=17.0, help='End time in 24-hour format')
    
    # Template Options
    use_template = fields.Boolean('Use Template', default=False)
    template_type = fields.Selection([
        ('route_based', 'Based on Route'),
        ('customer_based', 'Based on Customer List'),
        ('previous_schedule', 'Copy from Previous Schedule'),
        ('manual', 'Manual Entry')
    ], string='Template Type', default='manual')
    
    # Route-based options
    route_id = fields.Many2one('dynamic.route', string='Route')
    include_all_customers = fields.Boolean('Include All Route Customers', default=True)
    
    # Customer-based options
    customer_ids = fields.Many2many('res.partner', string='Customers', domain=[('is_company', '=', True)])
    
    # Previous schedule options
    previous_schedule_id = fields.Many2one('daily.visit.schedule', string='Previous Schedule')
    copy_notes = fields.Boolean('Copy Notes', default=True)
    copy_timing = fields.Boolean('Copy Timing', default=True)
    
    # Visit Lines
    visit_line_ids = fields.One2many('daily.visit.schedule.wizard.line', 'wizard_id', string='Visit Lines')
    
    # Auto-scheduling options
    auto_schedule = fields.Boolean('Auto Schedule Times', default=True)
    visit_duration = fields.Float('Default Visit Duration (Hours)', default=1.0)
    travel_time = fields.Float('Default Travel Time (Hours)', default=0.5)
    
    @api.model
    def _get_current_sales_rep(self):
        sales_rep = self.env['sales.rep'].search([('user_id', '=', self.env.user.id)], limit=1)
        return sales_rep.id if sales_rep else False
    
    @api.onchange('visit_date', 'sales_rep_id')
    def _onchange_visit_info(self):
        if self.visit_date and self.sales_rep_id:
            self.name = f"Daily Schedule - {self.sales_rep_id.name} - {self.visit_date.strftime('%Y-%m-%d')}"
    
    @api.onchange('template_type')
    def _onchange_template_type(self):
        if self.template_type != 'route_based':
            self.route_id = False
        if self.template_type != 'customer_based':
            self.customer_ids = [(5, 0, 0)]
        if self.template_type != 'previous_schedule':
            self.previous_schedule_id = False
    
    @api.onchange('route_id', 'include_all_customers')
    def _onchange_route_id(self):
        if self.route_id and self.include_all_customers:
            # Get customers from route
            route_customers = self.route_id.route_point_ids.mapped('customer_id')
            self._generate_visit_lines_from_customers(route_customers)
    
    @api.onchange('customer_ids')
    def _onchange_customer_ids(self):
        if self.customer_ids and self.template_type == 'customer_based':
            self._generate_visit_lines_from_customers(self.customer_ids)
    
    @api.onchange('previous_schedule_id')
    def _onchange_previous_schedule_id(self):
        if self.previous_schedule_id:
            self._copy_from_previous_schedule()
    
    def _generate_visit_lines_from_customers(self, customers):
        """Generate visit lines from customer list"""
        lines = []
        current_time = self.start_time
        
        for i, customer in enumerate(customers):
            lines.append((0, 0, {
                'customer_id': customer.id,
                'sequence': (i + 1) * 10,
                'planned_time': current_time,
                'planned_duration': self.visit_duration,
                'visit_type': 'sales',
                'expected_amount': 0.0,
            }))
            
            if self.auto_schedule:
                current_time += self.visit_duration + self.travel_time
                if current_time > self.end_time:
                    break
        
        self.visit_line_ids = lines
    
    def _copy_from_previous_schedule(self):
        """Copy visit lines from previous schedule"""
        if not self.previous_schedule_id:
            return
        
        lines = []
        for line in self.previous_schedule_id.visit_line_ids:
            line_data = {
                'customer_id': line.customer_id.id,
                'sequence': line.sequence,
                'planned_time': line.planned_time if self.copy_timing else self.start_time,
                'planned_duration': line.planned_duration if self.copy_timing else self.visit_duration,
                'visit_type': line.visit_type,
                'expected_amount': line.expected_amount,
                'travel_distance': line.travel_distance,
                'estimated_duration': line.estimated_duration,
            }
            
            if self.copy_notes:
                line_data.update({
                    'visit_notes': line.visit_notes,
                    'follow_up_notes': line.follow_up_notes,
                })
            
            lines.append((0, 0, line_data))
        
        self.visit_line_ids = lines
    
    def action_create_schedule(self):
        """Create the daily visit schedule"""
        # Create the main schedule
        schedule_vals = {
            'name': self.name,
            'sales_rep_id': self.sales_rep_id.id,
            'visit_date': self.visit_date,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'state': 'draft',
        }
        
        schedule = self.env['daily.visit.schedule'].create(schedule_vals)
        
        # Create visit lines
        for line in self.visit_line_ids:
            line_vals = {
                'schedule_id': schedule.id,
                'customer_id': line.customer_id.id,
                'sequence': line.sequence,
                'planned_time': line.planned_time,
                'planned_duration': line.planned_duration,
                'visit_type': line.visit_type,
                'expected_amount': line.expected_amount,
                'travel_distance': line.travel_distance,
                'estimated_duration': line.estimated_duration,
                'visit_notes': line.visit_notes,
                'follow_up_notes': line.follow_up_notes,
            }
            
            self.env['daily.visit.line'].create(line_vals)
        
        # Return action to open the created schedule
        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily Visit Schedule',
            'res_model': 'daily.visit.schedule',
            'res_id': schedule.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_preview_schedule(self):
        """Preview the schedule before creating"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Preview Schedule',
            'res_model': 'daily.visit.schedule.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'preview_mode': True}
        }

class DailyVisitScheduleWizardLine(models.TransientModel):
    _name = 'daily.visit.schedule.wizard.line'
    _description = 'Daily Visit Schedule Wizard Line'
    _order = 'sequence, planned_time'
    
    wizard_id = fields.Many2one('daily.visit.schedule.wizard', string='Wizard', required=True, ondelete='cascade')
    
    # Basic Information
    sequence = fields.Integer('Sequence', default=10)
    customer_id = fields.Many2one('res.partner', string='Customer', required=True, domain=[('is_company', '=', True)])
    contact_person = fields.Char('Contact Person')
    
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
    
    # Financial Information
    expected_amount = fields.Monetary('Expected Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    # Location and Travel
    travel_distance = fields.Float('Travel Distance (KM)')
    estimated_duration = fields.Float('Estimated Travel Duration (Hours)', default=0.5)
    
    # Notes
    visit_notes = fields.Text('Visit Notes')
    follow_up_notes = fields.Text('Follow-up Notes')
    
    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        if self.customer_id:
            # Auto-fill contact person if available
            contacts = self.customer_id.child_ids.filtered(lambda c: c.function)
            if contacts:
                self.contact_person = contacts[0].name

class VisitRescheduleWizard(models.TransientModel):
    _name = 'visit.reschedule.wizard'
    _description = 'Visit Reschedule Wizard'
    
    visit_line_id = fields.Many2one('daily.visit.line', string='Visit Line', required=True)
    customer_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    current_date = fields.Date('Current Date', readonly=True)
    current_time = fields.Float('Current Time', readonly=True)
    
    new_date = fields.Date('New Date', required=True, default=fields.Date.today)
    new_time = fields.Float('New Time', required=True, default=9.0)
    reason = fields.Text('Reason for Reschedule', required=True)
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_visit_line_id'):
            visit_line = self.env['daily.visit.line'].browse(self.env.context['default_visit_line_id'])
            res.update({
                'customer_id': visit_line.customer_id.id,
                'current_date': visit_line.schedule_id.visit_date,
                'current_time': visit_line.planned_time,
            })
        return res
    
    def action_reschedule(self):
        """Reschedule the visit"""
        # Create new schedule for the new date if it doesn't exist
        new_schedule = self.env['daily.visit.schedule'].search([
            ('sales_rep_id', '=', self.visit_line_id.schedule_id.sales_rep_id.id),
            ('visit_date', '=', self.new_date)
        ], limit=1)
        
        if not new_schedule:
            # Create new schedule
            new_schedule = self.env['daily.visit.schedule'].create({
                'name': f"Daily Schedule - {self.new_date.strftime('%Y-%m-%d')}",
                'sales_rep_id': self.visit_line_id.schedule_id.sales_rep_id.id,
                'visit_date': self.new_date,
                'start_time': 8.0,
                'end_time': 17.0,
                'state': 'draft',
            })
        
        # Update the visit line
        self.visit_line_id.write({
            'schedule_id': new_schedule.id,
            'planned_time': self.new_time,
            'state': 'planned',
            'visit_notes': (self.visit_line_id.visit_notes or '') + f"\n\nRescheduled from {self.current_date} {self.current_time:02.0f}:{(self.current_time % 1 * 60):02.0f}. Reason: {self.reason}"
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily Visit Schedule',
            'res_model': 'daily.visit.schedule',
            'res_id': new_schedule.id,
            'view_mode': 'form',
            'target': 'current',
        }