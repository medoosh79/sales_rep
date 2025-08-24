# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class DailyVisitScheduleWizard(models.TransientModel):
    _name = 'daily.visit.schedule.wizard'
    _description = 'Daily Visit Schedule Wizard'

    name = fields.Char('Schedule Name', required=True)
    sales_rep_id = fields.Many2one('sales.rep', 'Sales Representative', required=True)
    visit_date = fields.Date('Visit Date', required=True, default=fields.Date.today)
    start_time = fields.Float('Start Time', default=8.0)
    end_time = fields.Float('End Time', default=17.0)
    
    # Template options
    use_template = fields.Boolean('Use Template', default=False)
    template_type = fields.Selection([
        ('route_based', 'Route Based'),
        ('customer_based', 'Customer Based'),
        ('previous_schedule', 'Previous Schedule')
    ], 'Template Type')
    auto_schedule = fields.Boolean('Auto Schedule', default=False)
    visit_duration = fields.Float('Default Visit Duration', default=1.0)
    travel_time = fields.Float('Default Travel Time', default=0.5)
    
    # Route-based template
    route_id = fields.Many2one('dynamic.route', 'Route')
    include_all_customers = fields.Boolean('Include All Customers', default=True)
    
    # Customer-based template
    customer_ids = fields.Many2many('res.partner', 'wizard_customer_rel', 'wizard_id', 'customer_id', 'Customers')
    
    # Previous schedule template
    previous_schedule_id = fields.Many2one('daily.visit.schedule', 'Previous Schedule')
    copy_notes = fields.Boolean('Copy Notes', default=True)
    copy_timing = fields.Boolean('Copy Timing', default=True)
    
    # Visit lines
    visit_line_ids = fields.One2many('daily.visit.schedule.wizard.line', 'wizard_id', 'Visit Lines')
    
    @api.onchange('sales_rep_id')
    def _onchange_sales_rep_id(self):
        if self.sales_rep_id:
            self.name = f"Daily Schedule - {self.sales_rep_id.name} - {self.visit_date}"
    
    @api.onchange('visit_date')
    def _onchange_visit_date(self):
        if self.sales_rep_id and self.visit_date:
            self.name = f"Daily Schedule - {self.sales_rep_id.name} - {self.visit_date}"
    
    @api.onchange('template_type', 'route_id', 'customer_ids', 'previous_schedule_id')
    def _onchange_template_options(self):
        if self.use_template:
            self._generate_visit_lines_from_template()
    
    def _generate_visit_lines_from_template(self):
        """Generate visit lines based on selected template"""
        lines = []
        
        if self.template_type == 'route_based' and self.route_id:
            # Get customers from route
            customers = self.route_id.customer_ids if self.include_all_customers else []
            for i, customer in enumerate(customers):
                lines.append((0, 0, {
                    'sequence': i + 1,
                    'customer_id': customer.id,
                    'planned_time': self.start_time + (i * (self.visit_duration + self.travel_time)),
                    'planned_duration': self.visit_duration,
                    'visit_type': 'sales_call',
                }))
        
        elif self.template_type == 'customer_based' and self.customer_ids:
            for i, customer in enumerate(self.customer_ids):
                lines.append((0, 0, {
                    'sequence': i + 1,
                    'customer_id': customer.id,
                    'planned_time': self.start_time + (i * (self.visit_duration + self.travel_time)),
                    'planned_duration': self.visit_duration,
                    'visit_type': 'sales_call',
                }))
        
        elif self.template_type == 'previous_schedule' and self.previous_schedule_id:
            for i, line in enumerate(self.previous_schedule_id.visit_line_ids):
                line_data = {
                    'sequence': i + 1,
                    'customer_id': line.customer_id.id,
                    'visit_type': line.visit_type,
                }
                
                if self.copy_timing:
                    line_data.update({
                        'planned_time': line.planned_time,
                        'planned_duration': line.planned_duration,
                    })
                else:
                    line_data.update({
                        'planned_time': self.start_time + (i * (self.visit_duration + self.travel_time)),
                        'planned_duration': self.visit_duration,
                    })
                
                if self.copy_notes:
                    line_data.update({
                        'visit_notes': line.visit_notes,
                        'follow_up_notes': line.follow_up_notes,
                    })
                
                lines.append((0, 0, line_data))
        
        self.visit_line_ids = lines
    
    def action_create_schedule(self):
        """Create the daily visit schedule"""
        if not self.visit_line_ids:
            raise UserError(_("Please add at least one visit line."))
        
        # Create the schedule
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
                'sequence': line.sequence,
                'customer_id': line.customer_id.id,
                'contact_person': line.contact_person,
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
        if not self.visit_line_ids:
            raise UserError(_("Please add at least one visit line."))
        
        # Return a view showing the preview
        return {
            'type': 'ir.actions.act_window',
            'name': 'Schedule Preview',
            'res_model': 'daily.visit.schedule.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'preview_mode': True},
        }


class DailyVisitScheduleWizardLine(models.TransientModel):
    _name = 'daily.visit.schedule.wizard.line'
    _description = 'Daily Visit Schedule Wizard Line'
    _order = 'sequence, id'
    
    wizard_id = fields.Many2one('daily.visit.schedule.wizard', 'Wizard', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    customer_id = fields.Many2one('res.partner', 'Customer', required=True, domain=[('is_company', '=', True)])
    contact_person = fields.Char('Contact Person')
    planned_time = fields.Float('Planned Time')
    planned_duration = fields.Float('Planned Duration', default=1.0)
    visit_type = fields.Selection([
        ('sales_call', 'Sales Call'),
        ('delivery', 'Delivery'),
        ('support', 'Support'),
        ('follow_up', 'Follow Up'),
        ('meeting', 'Meeting'),
        ('other', 'Other')
    ], 'Visit Type', default='sales_call')
    expected_amount = fields.Monetary('Expected Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    travel_distance = fields.Float('Travel Distance (km)')
    estimated_duration = fields.Float('Estimated Duration')
    visit_notes = fields.Text('Visit Notes')
    follow_up_notes = fields.Text('Follow-up Notes')
    
    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        if self.customer_id:
            # Set default contact person if available
            contacts = self.customer_id.child_ids.filtered(lambda c: c.function and 'manager' in c.function.lower())
            if contacts:
                self.contact_person = contacts[0].name


class VisitRescheduleWizard(models.TransientModel):
    _name = 'visit.reschedule.wizard'
    _description = 'Visit Reschedule Wizard'
    
    visit_line_id = fields.Many2one('daily.visit.line', 'Visit Line', required=True)
    customer_id = fields.Many2one('res.partner', 'Customer', related='visit_line_id.customer_id', readonly=True)
    current_date = fields.Date('Current Date', related='visit_line_id.schedule_id.visit_date', readonly=True)
    current_time = fields.Float('Current Time', related='visit_line_id.planned_time', readonly=True)
    new_date = fields.Date('New Date', required=True)
    new_time = fields.Float('New Time', required=True)
    reason = fields.Text('Reason', required=True)
    
    def action_reschedule(self):
        """Reschedule the visit"""
        if self.new_date == self.current_date and self.new_time == self.current_time:
            raise UserError(_("Please select a different date or time."))
        
        # Update the visit line
        self.visit_line_id.write({
            'planned_time': self.new_time,
            'visit_notes': (self.visit_line_id.visit_notes or '') + f"\n\nRescheduled: {self.reason}"
        })
        
        # If date changed, we might need to move to different schedule
        if self.new_date != self.current_date:
            # Find or create schedule for new date
            schedule = self.env['daily.visit.schedule'].search([
                ('sales_rep_id', '=', self.visit_line_id.schedule_id.sales_rep_id.id),
                ('visit_date', '=', self.new_date)
            ], limit=1)
            
            if not schedule:
                # Create new schedule for the new date
                schedule = self.env['daily.visit.schedule'].create({
                    'name': f"Daily Schedule - {self.visit_line_id.schedule_id.sales_rep_id.name} - {self.new_date}",
                    'sales_rep_id': self.visit_line_id.schedule_id.sales_rep_id.id,
                    'visit_date': self.new_date,
                    'state': 'draft',
                })
            
            self.visit_line_id.schedule_id = schedule.id
        
        return {'type': 'ir.actions.act_window_close'}