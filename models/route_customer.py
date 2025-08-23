# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class RouteCustomer(models.Model):
    """Model to manage customers associated with dynamic routes"""
    _name = 'route.customer'
    _description = 'Route Customer Management'
    _order = 'priority desc, sequence, name'
    _rec_name = 'display_name'

    # Basic Information
    name = fields.Char('Customer Name', required=True)
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    customer_id = fields.Many2one('res.partner', 'Customer', required=True, 
                                 domain=[('is_company', '=', True)])
    route_id = fields.Many2one('dynamic.route', 'Route', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], 'Priority', default='medium', required=True)
    
    # Visit Information
    visit_type = fields.Selection([
        ('sales', 'Sales Visit'),
        ('delivery', 'Delivery'),
        ('support', 'Support'),
        ('collection', 'Collection'),
        ('survey', 'Survey'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other')
    ], 'Visit Type', default='sales', required=True)
    
    visit_purpose = fields.Text('Visit Purpose')
    expected_duration = fields.Float('Expected Duration (Hours)', default=1.0)
    visit_frequency = fields.Selection([
        ('once', 'One Time'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly')
    ], 'Visit Frequency', default='once')
    
    # Location Information
    address = fields.Char('Address', related='customer_id.contact_address', readonly=True)
    latitude = fields.Float('Latitude', digits=(10, 7))
    longitude = fields.Float('Longitude', digits=(10, 7))
    location_verified = fields.Boolean('Location Verified', default=False)
    
    # Contact Information
    contact_person = fields.Char('Contact Person')
    contact_phone = fields.Char('Contact Phone', related='customer_id.phone', readonly=True)
    contact_email = fields.Char('Contact Email', related='customer_id.email', readonly=True)
    
    # Visit Status
    visit_status = fields.Selection([
        ('planned', 'Planned'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled')
    ], 'Visit Status', default='planned', required=True)
    
    # Scheduling
    preferred_time_start = fields.Float('Preferred Start Time', help='Preferred visit start time (24h format)')
    preferred_time_end = fields.Float('Preferred End Time', help='Preferred visit end time (24h format)')
    avoid_days = fields.Selection([
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday')
    ], 'Avoid Day')
    
    # Business Information
    customer_category = fields.Many2many('res.partner.category', related='customer_id.category_id', readonly=True)
    customer_type = fields.Selection([
        ('prospect', 'Prospect'),
        ('customer', 'Customer'),
        ('vip', 'VIP Customer'),
        ('inactive', 'Inactive')
    ], 'Customer Type', default='customer')
    
    # Financial Information
    currency_id = fields.Many2one('res.currency', 'Currency', 
                                 default=lambda self: self.env.company.currency_id)
    expected_order_value = fields.Monetary('Expected Order Value', currency_field='currency_id')
    last_order_amount = fields.Monetary('Last Order Amount', currency_field='currency_id')
    credit_limit = fields.Float('Credit Limit', 
                                  related='customer_id.credit_limit', readonly=True)
    
    # Performance Metrics
    total_visits = fields.Integer('Total Visits', compute='_compute_visit_stats', store=True)
    successful_visits = fields.Integer('Successful Visits', compute='_compute_visit_stats', store=True)
    success_rate = fields.Float('Success Rate (%)', compute='_compute_visit_stats', store=True)
    average_order_value = fields.Monetary('Average Order Value', currency_field='currency_id',
                                         compute='_compute_financial_stats', store=True)
    
    # Special Requirements
    special_instructions = fields.Text('Special Instructions')
    requires_appointment = fields.Boolean('Requires Appointment', default=False)
    parking_available = fields.Boolean('Parking Available', default=True)
    accessibility_notes = fields.Text('Accessibility Notes')
    
    # Relationship Fields
    route_point_ids = fields.One2many('dynamic.route.point', 'route_customer_id', 'Route Points')
    sales_rep_id = fields.Many2one('hr.employee', 'Sales Representative', 
                                  related='route_id.sales_rep_id', readonly=True)
    
    # Status and Control
    active = fields.Boolean('Active', default=True)
    is_mandatory = fields.Boolean('Mandatory Visit', default=False, 
                                 help='This customer must be visited in the route')
    can_reschedule = fields.Boolean('Can Reschedule', default=True)
    
    # Computed Fields
    @api.depends('name', 'customer_id.name', 'visit_type')
    def _compute_display_name(self):
        for record in self:
            if record.customer_id:
                record.display_name = f"{record.customer_id.name} - {record.visit_type.title()}"
            else:
                record.display_name = record.name or 'New Route Customer'
    
    @api.depends('route_point_ids', 'route_point_ids.visit_status')
    def _compute_visit_stats(self):
        for record in self:
            points = record.route_point_ids
            record.total_visits = len(points)
            record.successful_visits = len(points.filtered(lambda p: p.visit_status == 'completed'))
            record.success_rate = (record.successful_visits / record.total_visits * 100) if record.total_visits > 0 else 0
    
    @api.depends('route_point_ids', 'route_point_ids.actual_order_value')
    def _compute_financial_stats(self):
        for record in self:
            completed_points = record.route_point_ids.filtered(lambda p: p.visit_status == 'completed')
            if completed_points:
                total_value = sum(completed_points.mapped('actual_order_value'))
                record.average_order_value = total_value / len(completed_points)
            else:
                record.average_order_value = 0
    
    # Constraints
    @api.constrains('preferred_time_start', 'preferred_time_end')
    def _check_preferred_times(self):
        for record in self:
            if record.preferred_time_start and record.preferred_time_end:
                if record.preferred_time_start >= record.preferred_time_end:
                    raise ValidationError("Preferred start time must be before end time.")
                if record.preferred_time_start < 0 or record.preferred_time_end > 24:
                    raise ValidationError("Preferred times must be between 0 and 24 hours.")
    
    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        for record in self:
            if record.latitude and (record.latitude < -90 or record.latitude > 90):
                raise ValidationError("Latitude must be between -90 and 90 degrees.")
            if record.longitude and (record.longitude < -180 or record.longitude > 180):
                raise ValidationError("Longitude must be between -180 and 180 degrees.")
    
    # Business Methods
    def action_confirm_visit(self):
        """Confirm the planned visit"""
        self.ensure_one()
        if self.visit_status == 'planned':
            self.visit_status = 'confirmed'
            self._log_status_change('confirmed')
        return True
    
    def action_start_visit(self):
        """Start the visit"""
        self.ensure_one()
        if self.visit_status in ['planned', 'confirmed']:
            self.visit_status = 'in_progress'
            self._log_status_change('in_progress')
        return True
    
    def action_complete_visit(self):
        """Complete the visit"""
        self.ensure_one()
        if self.visit_status == 'in_progress':
            self.visit_status = 'completed'
            self._log_status_change('completed')
        return True
    
    def action_cancel_visit(self):
        """Cancel the visit"""
        self.ensure_one()
        if self.visit_status not in ['completed', 'cancelled']:
            self.visit_status = 'cancelled'
            self._log_status_change('cancelled')
        return True
    
    def action_reschedule_visit(self):
        """Reschedule the visit"""
        self.ensure_one()
        if self.can_reschedule and self.visit_status not in ['completed', 'cancelled']:
            self.visit_status = 'rescheduled'
            self._log_status_change('rescheduled')
        return True
    
    def action_verify_location(self):
        """Verify customer location coordinates"""
        self.ensure_one()
        # Here you could integrate with geocoding services
        # For now, we'll just mark as verified if coordinates exist
        if self.latitude and self.longitude:
            self.location_verified = True
            self.message_post(body="Location coordinates verified.")
        return True
    
    def action_get_directions(self):
        """Get directions to customer location"""
        self.ensure_one()
        if self.latitude and self.longitude:
            # This could open a map application or return directions
            url = f"https://www.google.com/maps/dir/?api=1&destination={self.latitude},{self.longitude}"
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new'
            }
        else:
            raise ValidationError("Customer location coordinates are not available.")
    
    def _log_status_change(self, new_status):
        """Log status changes in chatter"""
        self.message_post(
            body=f"Visit status changed to: {new_status.title()}",
            message_type='notification'
        )
    
    # Utility Methods
    def get_distance_from_point(self, lat, lng):
        """Calculate distance from given coordinates"""
        if not (self.latitude and self.longitude and lat and lng):
            return 0
        
        # Simple distance calculation (you might want to use a more accurate method)
        import math
        
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(lat), math.radians(lng)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        r = 6371
        
        return r * c
    
    @api.model
    def create_from_customer(self, customer_id, route_id, visit_type='sales'):
        """Create route customer from existing customer"""
        customer = self.env['res.partner'].browse(customer_id)
        if not customer.exists():
            raise ValidationError("Customer not found.")
        
        vals = {
            'name': customer.name,
            'customer_id': customer_id,
            'route_id': route_id,
            'visit_type': visit_type,
            'contact_person': customer.name,
        }
        
        return self.create(vals)
    
    # Override Methods
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set default values"""
        for vals in vals_list:
            if 'name' not in vals and 'customer_id' in vals:
                customer = self.env['res.partner'].browse(vals['customer_id'])
                vals['name'] = customer.name
        
        return super().create(vals_list)
    
    def write(self, vals):
        """Override write to log important changes"""
        if 'visit_status' in vals:
            for record in self:
                if record.visit_status != vals['visit_status']:
                    record._log_status_change(vals['visit_status'])
        
        return super().write(vals)

class RouteCustomerWizard(models.TransientModel):
    """Wizard to add multiple customers to a route"""
    _name = 'route.customer.wizard'
    _description = 'Add Customers to Route Wizard'
    
    route_id = fields.Many2one('dynamic.route', 'Route', required=True)
    customer_ids = fields.Many2many('res.partner', 'route_customer_wizard_partner_rel', 
                                   'wizard_id', 'partner_id', 'Customers',
                                   domain=[('is_company', '=', True)])
    visit_type = fields.Selection([
        ('sales', 'Sales Visit'),
        ('delivery', 'Delivery'),
        ('support', 'Support'),
        ('collection', 'Collection'),
        ('survey', 'Survey'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other')
    ], 'Default Visit Type', default='sales', required=True)
    
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], 'Default Priority', default='medium', required=True)
    
    expected_duration = fields.Float('Default Expected Duration (Hours)', default=1.0)
    
    def action_add_customers(self):
        """Add selected customers to the route"""
        route_customer_obj = self.env['route.customer']
        
        for customer in self.customer_ids:
            # Check if customer is already in the route
            existing = route_customer_obj.search([
                ('route_id', '=', self.route_id.id),
                ('customer_id', '=', customer.id)
            ])
            
            if not existing:
                route_customer_obj.create({
                    'name': customer.name,
                    'customer_id': customer.id,
                    'route_id': self.route_id.id,
                    'visit_type': self.visit_type,
                    'priority': self.priority,
                    'expected_duration': self.expected_duration,
                })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dynamic.route',
            'res_id': self.route_id.id,
            'view_mode': 'form',
            'target': 'current',
        }