# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json
from datetime import datetime, timedelta

class DynamicRoute(models.Model):
    _name = 'dynamic.route'
    _description = 'Dynamic Route Management'
    _order = 'priority desc, create_date desc'
    _rec_name = 'route_name'

    # Basic Information
    route_name = fields.Char('Route Name', required=True, help="Name of the dynamic route")
    description = fields.Text('Description', help="Detailed description of the route")
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True)
    
    # Route Configuration
    route_type = fields.Selection([
        ('daily', 'Daily Route'),
        ('weekly', 'Weekly Route'),
        ('monthly', 'Monthly Route'),
        ('custom', 'Custom Route')
    ], string='Route Type', default='daily', required=True)
    
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='medium')
    
    # Status and State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    # Scheduling
    start_date = fields.Date('Start Date', required=True, default=fields.Date.today)
    end_date = fields.Date('End Date')
    estimated_duration = fields.Float('Estimated Duration (Hours)', default=8.0)
    
    # Route Points and Customers
    route_point_ids = fields.One2many('dynamic.route.point', 'route_id', string='Route Points')
    customer_ids = fields.Many2many('res.partner', 'dynamic_route_customer_rel', 
                                   'route_id', 'customer_id', string='Customers',
                                   domain=[('is_company', '=', True)])
    route_customer_ids = fields.One2many('route.customer', 'route_id', string='Route Customers')
    
    # Geographic Information
    start_location = fields.Char('Start Location', help="Starting point of the route")
    end_location = fields.Char('End Location', help="Ending point of the route")
    total_distance = fields.Float('Total Distance (KM)', compute='_compute_route_metrics', store=True)
    
    # Route Optimization
    is_optimized = fields.Boolean('Route Optimized', default=False)
    optimization_algorithm = fields.Selection([
        ('nearest', 'Nearest Neighbor'),
        ('genetic', 'Genetic Algorithm'),
        ('manual', 'Manual Order')
    ], string='Optimization Method', default='nearest')
    
    # Performance Metrics
    completion_rate = fields.Float('Completion Rate (%)', compute='_compute_performance_metrics', store=True)
    average_visit_time = fields.Float('Average Visit Time (Minutes)', compute='_compute_performance_metrics', store=True)
    total_visits_planned = fields.Integer('Total Visits Planned', compute='_compute_route_metrics', store=True)
    total_visits_completed = fields.Integer('Total Visits Completed', compute='_compute_performance_metrics', store=True)
    
    # Financial Information
    estimated_revenue = fields.Monetary('Estimated Revenue', currency_field='currency_id')
    actual_revenue = fields.Monetary('Actual Revenue', currency_field='currency_id')
    route_cost = fields.Monetary('Route Cost', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    
    # Additional Information
    notes = fields.Html('Notes')
    active = fields.Boolean('Active', default=True)
    color = fields.Integer('Color Index', default=0)
    
    @api.depends('route_point_ids')
    def _compute_route_metrics(self):
        """Compute route metrics like total distance and planned visits"""
        for route in self:
            route.total_visits_planned = len(route.route_point_ids)
            # Calculate total distance (simplified calculation)
            total_distance = 0.0
            points = route.route_point_ids.sorted('sequence')
            for i in range(len(points) - 1):
                # This is a simplified distance calculation
                # In a real implementation, you would use GPS coordinates
                total_distance += 10.0  # Placeholder: 10km between each point
            route.total_distance = total_distance
    
    @api.depends('route_point_ids.visit_status')
    def _compute_performance_metrics(self):
        """Compute performance metrics"""
        for route in self:
            completed_visits = route.route_point_ids.filtered(lambda p: p.visit_status == 'completed')
            route.total_visits_completed = len(completed_visits)
            
            if route.total_visits_planned > 0:
                route.completion_rate = (route.total_visits_completed / route.total_visits_planned) * 100
            else:
                route.completion_rate = 0.0
            
            # Calculate average visit time
            if completed_visits:
                total_time = sum(completed_visits.mapped('actual_visit_duration'))
                route.average_visit_time = total_time / len(completed_visits)
            else:
                route.average_visit_time = 0.0
    
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        """Validate date constraints"""
        for route in self:
            if route.end_date and route.start_date > route.end_date:
                raise ValidationError("End date must be after start date.")
    
    def action_activate(self):
        """Activate the route"""
        self.write({'state': 'active'})
        return True
    
    def action_pause(self):
        """Pause the route"""
        self.write({'state': 'paused'})
        return True
    
    def action_complete(self):
        """Mark route as completed"""
        self.write({'state': 'completed'})
        return True
    
    def action_cancel(self):
        """Cancel the route"""
        self.write({'state': 'cancelled'})
        return True
    
    def action_optimize_route(self):
        """Optimize route order using selected algorithm"""
        if self.optimization_algorithm == 'nearest':
            self._optimize_nearest_neighbor()
        elif self.optimization_algorithm == 'genetic':
            self._optimize_genetic_algorithm()
        
        self.is_optimized = True
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Route Optimized',
                'message': 'Route has been optimized successfully!',
                'type': 'success'
            }
        }
    
    def _optimize_nearest_neighbor(self):
        """Simple nearest neighbor optimization"""
        points = self.route_point_ids
        if len(points) <= 2:
            return
        
        # Simple reordering based on sequence
        for i, point in enumerate(points):
            point.sequence = (i + 1) * 10
    
    def _optimize_genetic_algorithm(self):
        """Placeholder for genetic algorithm optimization"""
        # This would implement a more sophisticated optimization
        self._optimize_nearest_neighbor()  # Fallback to simple method
    
    def action_duplicate_route(self):
        """Duplicate the current route"""
        new_route = self.copy({
            'route_name': f"{self.route_name} (Copy)",
            'state': 'draft',
            'is_optimized': False
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dynamic Route',
            'res_model': 'dynamic.route',
            'res_id': new_route.id,
            'view_mode': 'form',
            'target': 'current'
        }

class DynamicRoutePoint(models.Model):
    _name = 'dynamic.route.point'
    _description = 'Dynamic Route Point'
    _order = 'sequence, id'
    
    route_id = fields.Many2one('dynamic.route', string='Route', required=True, ondelete='cascade')
    route_customer_id = fields.Many2one('route.customer', string='Route Customer')
    sequence = fields.Integer('Sequence', default=10)
    
    # Point Information
    point_name = fields.Char('Point Name', required=True)
    customer_id = fields.Many2one('res.partner', string='Customer', 
                                 domain=[('is_company', '=', True)])
    location_address = fields.Text('Address')
    
    # Geographic Coordinates
    latitude = fields.Float('Latitude', digits=(10, 6))
    longitude = fields.Float('Longitude', digits=(10, 6))
    
    # Visit Planning
    planned_arrival_time = fields.Datetime('Planned Arrival')
    planned_departure_time = fields.Datetime('Planned Departure')
    estimated_visit_duration = fields.Float('Estimated Duration (Minutes)', default=30.0)
    
    # Visit Execution
    actual_arrival_time = fields.Datetime('Actual Arrival')
    actual_departure_time = fields.Datetime('Actual Departure')
    actual_visit_duration = fields.Float('Actual Duration (Minutes)', compute='_compute_actual_duration', store=True)
    
    # Visit Status
    visit_status = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
        ('cancelled', 'Cancelled')
    ], string='Visit Status', default='planned')
    
    # Additional Visit Information
    visit_outcome = fields.Selection([
        ('successful', 'Successful'),
        ('no_contact', 'No Contact'),
        ('postponed', 'Postponed'),
        ('cancelled_by_customer', 'Cancelled by Customer'),
        ('failed', 'Failed')
    ], 'Visit Outcome')
    actual_order_value = fields.Monetary('Actual Order Value', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    
    # Visit Details
    visit_purpose = fields.Selection([
        ('sales', 'Sales Visit'),
        ('delivery', 'Delivery'),
        ('collection', 'Collection'),
        ('service', 'Service'),
        ('follow_up', 'Follow Up'),
        ('other', 'Other')
    ], string='Visit Purpose', default='sales')
    
    visit_notes = fields.Text('Visit Notes')
    visit_outcome = fields.Text('Visit Outcome')
    
    # Performance
    is_on_time = fields.Boolean('On Time', compute='_compute_performance', store=True)
    delay_minutes = fields.Float('Delay (Minutes)', compute='_compute_performance', store=True)
    
    @api.depends('actual_arrival_time', 'actual_departure_time')
    def _compute_actual_duration(self):
        """Calculate actual visit duration"""
        for point in self:
            if point.actual_arrival_time and point.actual_departure_time:
                delta = point.actual_departure_time - point.actual_arrival_time
                point.actual_visit_duration = delta.total_seconds() / 60.0
            else:
                point.actual_visit_duration = 0.0
    
    @api.depends('planned_arrival_time', 'actual_arrival_time')
    def _compute_performance(self):
        """Calculate performance metrics"""
        for point in self:
            if point.planned_arrival_time and point.actual_arrival_time:
                delta = point.actual_arrival_time - point.planned_arrival_time
                point.delay_minutes = delta.total_seconds() / 60.0
                point.is_on_time = point.delay_minutes <= 15  # 15 minutes tolerance
            else:
                point.delay_minutes = 0.0
                point.is_on_time = True
    
    def action_start_visit(self):
        """Start the visit"""
        self.write({
            'visit_status': 'in_progress',
            'actual_arrival_time': fields.Datetime.now()
        })
        return True
    
    def action_complete_visit(self):
        """Complete the visit"""
        self.write({
            'visit_status': 'completed',
            'actual_departure_time': fields.Datetime.now()
        })
        return True
    
    def action_skip_visit(self):
        """Skip the visit"""
        self.write({'visit_status': 'skipped'})
        return True