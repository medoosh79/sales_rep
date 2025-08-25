# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import json
import math

class GPSTracking(models.Model):
    _name = 'gps.tracking'
    _description = 'GPS Tracking System'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'timestamp desc'
    _rec_name = 'display_name'
    
    # Basic Information
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True, tracking=True)
    timestamp = fields.Datetime('Timestamp', required=True, default=fields.Datetime.now, tracking=True)
    
    # Location Data
    latitude = fields.Float('Latitude', digits=(10, 7), required=True)
    longitude = fields.Float('Longitude', digits=(10, 7), required=True)
    altitude = fields.Float('Altitude (m)', digits=(8, 2))
    accuracy = fields.Float('Accuracy (m)', digits=(8, 2))
    speed = fields.Float('Speed (km/h)', digits=(8, 2))
    heading = fields.Float('Heading (degrees)', digits=(8, 2))
    
    # Address Information
    address = fields.Char('Address', compute='_compute_address', store=True)
    city = fields.Char('City')
    state = fields.Char('State')
    country = fields.Char('Country')
    postal_code = fields.Char('Postal Code')
    
    # Tracking Context
    tracking_type = fields.Selection([
        ('manual', 'Manual Check-in'),
        ('automatic', 'Automatic Tracking'),
        ('visit_start', 'Visit Start'),
        ('visit_end', 'Visit End'),
        ('route_tracking', 'Route Tracking'),
        ('emergency', 'Emergency')
    ], string='Tracking Type', default='automatic', required=True)
    
    # Related Records
    visit_line_id = fields.Many2one('daily.visit.line', string='Related Visit')
    customer_id = fields.Many2one('res.partner', string='Nearby Customer')
    
    # Status and Validation
    is_valid = fields.Boolean('Valid Location', default=True)
    validation_notes = fields.Text('Validation Notes')
    
    # Distance Calculations
    distance_from_previous = fields.Float('Distance from Previous (km)', compute='_compute_distances', store=True)
    distance_to_customer = fields.Float('Distance to Customer (km)', compute='_compute_customer_distance', store=True)
    
    # Battery and Device Info
    battery_level = fields.Integer('Battery Level (%)')
    device_info = fields.Char('Device Information')
    network_type = fields.Selection([
        ('wifi', 'WiFi'),
        ('cellular', 'Cellular'),
        ('gps', 'GPS Only')
    ], string='Network Type')
    
    # Geofencing
    is_in_territory = fields.Boolean('In Assigned Territory', compute='_compute_territory_status', store=True)
    territory_id = fields.Many2one('territory.assignment', string='Current Territory')
    
    @api.depends('sales_rep_id', 'timestamp', 'tracking_type')
    def _compute_display_name(self):
        for record in self:
            if record.sales_rep_id and record.timestamp:
                record.display_name = f"{record.sales_rep_id.name} - {record.timestamp.strftime('%Y-%m-%d %H:%M')}"
            else:
                record.display_name = 'GPS Tracking'
    
    @api.depends('latitude', 'longitude')
    def _compute_address(self):
        # This would integrate with a geocoding service
        for record in self:
            if record.latitude and record.longitude:
                # Placeholder for reverse geocoding
                record.address = f"Lat: {record.latitude:.6f}, Lng: {record.longitude:.6f}"
            else:
                record.address = ''
    
    @api.depends('sales_rep_id', 'timestamp', 'latitude', 'longitude')
    def _compute_distances(self):
        for record in self:
            if not record.sales_rep_id or not record.latitude or not record.longitude:
                record.distance_from_previous = 0
                continue
            
            # Find previous location
            previous = self.search([
                ('sales_rep_id', '=', record.sales_rep_id.id),
                ('timestamp', '<', record.timestamp),
                ('id', '!=', record.id)
            ], limit=1, order='timestamp desc')
            
            if previous and previous.latitude and previous.longitude:
                record.distance_from_previous = self._calculate_distance(
                    record.latitude, record.longitude,
                    previous.latitude, previous.longitude
                )
            else:
                record.distance_from_previous = 0
    
    @api.depends('latitude', 'longitude', 'customer_id')
    def _compute_customer_distance(self):
        for record in self:
            if record.customer_id and record.latitude and record.longitude:
                if record.customer_id.partner_latitude and record.customer_id.partner_longitude:
                    record.distance_to_customer = self._calculate_distance(
                        record.latitude, record.longitude,
                        record.customer_id.partner_latitude,
                        record.customer_id.partner_longitude
                    )
                else:
                    record.distance_to_customer = 0
            else:
                record.distance_to_customer = 0
    
    @api.depends('latitude', 'longitude', 'sales_rep_id')
    def _compute_territory_status(self):
        for record in self:
            if not record.latitude or not record.longitude or not record.sales_rep_id:
                record.is_in_territory = False
                record.territory_id = False
                continue
            
            # Check if location is within assigned territories
            territories = self.env['territory.assignment'].search([
                ('sales_rep_id', '=', record.sales_rep_id.id),
                ('active', '=', True)
            ])
            
            in_territory = False
            territory_found = False
            
            for territory in territories:
                if self._point_in_territory(record.latitude, record.longitude, territory):
                    record.territory_id = territory.id
                    in_territory = True
                    territory_found = True
                    break
            
            record.is_in_territory = in_territory
            if not territory_found:
                record.territory_id = False
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _point_in_territory(self, lat, lng, territory):
        """Check if a point is within a territory boundary"""
        # This would implement point-in-polygon algorithm
        # For now, return True as placeholder
        return True
    
    @api.model
    def create_tracking_point(self, vals):
        """API method to create tracking point from mobile app"""
        # Validate required fields
        required_fields = ['sales_rep_id', 'latitude', 'longitude']
        for field in required_fields:
            if field not in vals:
                raise ValidationError(_(f"Missing required field: {field}"))
        
        # Auto-detect nearby customers
        if 'customer_id' not in vals:
            customer = self._find_nearby_customer(vals['latitude'], vals['longitude'])
            if customer:
                vals['customer_id'] = customer.id
        
        return self.create(vals)
    
    def _find_nearby_customer(self, lat, lng, radius_km=1.0):
        """Find nearby customers within specified radius"""
        customers = self.env['res.partner'].search([
            ('is_company', '=', True),
            ('customer_rank', '>', 0),
            ('partner_latitude', '!=', 0),
            ('partner_longitude', '!=', 0)
        ])
        
        for customer in customers:
            distance = self._calculate_distance(
                lat, lng,
                customer.partner_latitude,
                customer.partner_longitude
            )
            if distance <= radius_km:
                return customer
        
        return None
    
    @api.model
    def get_route_data(self, sales_rep_id, date_from=None, date_to=None):
        """Get route data for mapping"""
        domain = [('sales_rep_id', '=', sales_rep_id)]
        
        if date_from:
            domain.append(('timestamp', '>=', date_from))
        if date_to:
            domain.append(('timestamp', '<=', date_to))
        
        tracking_points = self.search(domain, order='timestamp')
        
        route_data = []
        for point in tracking_points:
            route_data.append({
                'id': point.id,
                'lat': point.latitude,
                'lng': point.longitude,
                'timestamp': point.timestamp.isoformat(),
                'type': point.tracking_type,
                'address': point.address,
                'customer': point.customer_id.name if point.customer_id else None,
                'speed': point.speed,
                'accuracy': point.accuracy
            })
        
        return route_data
    
    def action_validate_location(self):
        """Validate location manually"""
        self.is_valid = True
        self.validation_notes = f"Validated by {self.env.user.name} on {fields.Datetime.now()}"
    
    def action_invalidate_location(self):
        """Mark location as invalid"""
        self.is_valid = False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invalidate Location',
            'res_model': 'gps.tracking.invalidate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_tracking_id': self.id}
        }

class GPSTrackingRoute(models.Model):
    _name = 'gps.tracking.route'
    _description = 'GPS Tracking Route'
    _order = 'date desc'
    
    name = fields.Char('Route Name', required=True)
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True)
    date = fields.Date('Date', required=True, default=fields.Date.today)
    
    # Route Statistics
    total_distance = fields.Float('Total Distance (km)', compute='_compute_route_stats', store=True)
    total_duration = fields.Float('Total Duration (hours)', compute='_compute_route_stats', store=True)
    average_speed = fields.Float('Average Speed (km/h)', compute='_compute_route_stats', store=True)
    
    # Route Points
    tracking_point_ids = fields.One2many('gps.tracking', 'route_id', string='Tracking Points')
    point_count = fields.Integer('Point Count', compute='_compute_point_count')
    
    # Route Analysis
    efficiency_score = fields.Float('Efficiency Score', compute='_compute_efficiency', store=True)
    fuel_consumption = fields.Float('Estimated Fuel Consumption (L)', compute='_compute_fuel_consumption', store=True)
    
    @api.depends('tracking_point_ids')
    def _compute_point_count(self):
        for route in self:
            route.point_count = len(route.tracking_point_ids)
    
    @api.depends('tracking_point_ids.distance_from_previous', 'tracking_point_ids.timestamp')
    def _compute_route_stats(self):
        for route in self:
            if not route.tracking_point_ids:
                route.total_distance = 0
                route.total_duration = 0
                route.average_speed = 0
                continue
            
            # Calculate total distance
            route.total_distance = sum(route.tracking_point_ids.mapped('distance_from_previous'))
            
            # Calculate duration
            points = route.tracking_point_ids.sorted('timestamp')
            if len(points) > 1:
                start_time = points[0].timestamp
                end_time = points[-1].timestamp
                duration = (end_time - start_time).total_seconds() / 3600  # Convert to hours
                route.total_duration = duration
                
                # Calculate average speed
                if duration > 0:
                    route.average_speed = route.total_distance / duration
                else:
                    route.average_speed = 0
            else:
                route.total_duration = 0
                route.average_speed = 0
    
    @api.depends('total_distance', 'total_duration')
    def _compute_efficiency(self):
        for route in self:
            # Simple efficiency calculation based on distance vs time
            if route.total_duration > 0:
                # Efficiency score: higher is better (more distance covered in less time)
                route.efficiency_score = (route.total_distance / route.total_duration) * 10
            else:
                route.efficiency_score = 0
    
    @api.depends('total_distance')
    def _compute_fuel_consumption(self):
        for route in self:
            # Estimate fuel consumption (assuming 8L/100km average)
            route.fuel_consumption = (route.total_distance * 8) / 100

# Add route_id field to GPS Tracking
class GPSTrackingExtended(models.Model):
    _inherit = 'gps.tracking'
    
    route_id = fields.Many2one('gps.tracking.route', string='Route')