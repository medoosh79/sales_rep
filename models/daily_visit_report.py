# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools
from datetime import datetime, timedelta


class DailyVisitReport(models.Model):
    _name = 'daily.visit.report'
    _description = 'Daily Visit Report'
    _auto = False
    _rec_name = 'date'
    _order = 'date desc, sales_rep_id'

    # Date and Rep Info
    date = fields.Date('Date', readonly=True)
    sales_rep_id = fields.Many2one('res.users', 'Sales Representative', readonly=True)
    sales_rep_name = fields.Char('Sales Rep Name', readonly=True)
    
    # Visit Statistics
    total_visits = fields.Integer('Total Visits', readonly=True)
    completed_visits = fields.Integer('Completed Visits', readonly=True)
    cancelled_visits = fields.Integer('Cancelled Visits', readonly=True)
    in_progress_visits = fields.Integer('In Progress Visits', readonly=True)
    planned_visits = fields.Integer('Planned Visits', readonly=True)
    
    # Performance Metrics
    completion_rate = fields.Float('Completion Rate (%)', readonly=True)
    on_time_visits = fields.Integer('On Time Visits', readonly=True)
    late_visits = fields.Integer('Late Visits', readonly=True)
    punctuality_rate = fields.Float('Punctuality Rate (%)', readonly=True)
    
    # Financial Metrics
    expected_revenue = fields.Monetary('Expected Revenue', readonly=True, currency_field='currency_id')
    actual_revenue = fields.Monetary('Actual Revenue', readonly=True, currency_field='currency_id')
    total_revenue = fields.Monetary('Total Revenue', readonly=True, currency_field='currency_id')
    revenue_variance = fields.Monetary('Revenue Variance', readonly=True, currency_field='currency_id')
    revenue_achievement_rate = fields.Float('Revenue Achievement Rate (%)', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Currency', readonly=True)
    
    # Time Metrics
    total_planned_time = fields.Float('Total Planned Time (Hours)', readonly=True)
    total_actual_time = fields.Float('Total Actual Time (Hours)', readonly=True)
    time_efficiency = fields.Float('Time Efficiency (%)', readonly=True)
    average_visit_duration = fields.Float('Average Visit Duration (Hours)', readonly=True)
    
    # Travel Metrics
    total_distance = fields.Float('Total Distance (KM)', readonly=True)
    total_travel_time = fields.Float('Total Travel Time (Hours)', readonly=True)
    fuel_cost = fields.Monetary('Fuel Cost', readonly=True, currency_field='currency_id')
    
    # Customer Metrics
    unique_customers = fields.Integer('Unique Customers', readonly=True)
    new_customers = fields.Integer('New Customers', readonly=True)
    repeat_customers = fields.Integer('Repeat Customers', readonly=True)
    
    # Visit Type Distribution
    sales_visits = fields.Integer('Sales Visits', readonly=True)
    follow_up_visits = fields.Integer('Follow-up Visits', readonly=True)
    support_visits = fields.Integer('Support Visits', readonly=True)
    
    def init(self):
        """Create the view"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    row_number() OVER () AS id,
                    ds.visit_date AS date,
                    ds.sales_rep_id,
                    rp.name AS sales_rep_name,
                    
                    -- Visit Statistics
                    ds.total_visits,
                    ds.completed_visits,
                    COALESCE(cancelled_stats.cancelled_visits, 0) AS cancelled_visits,
                    (ds.total_visits - ds.completed_visits - COALESCE(cancelled_stats.cancelled_visits, 0)) AS in_progress_visits,
                    (ds.total_visits - ds.completed_visits - COALESCE(cancelled_stats.cancelled_visits, 0)) AS planned_visits,
                    
                    -- Performance Metrics
                    CASE 
                        WHEN ds.total_visits > 0 THEN 
                            ROUND(CAST((ds.completed_visits::float / ds.total_visits::float) * 100 AS NUMERIC), 2)
                        ELSE 0 
                    END AS completion_rate,
                    
                    COALESCE(on_time.count, 0) AS on_time_visits,
                    COALESCE(late.count, 0) AS late_visits,
                    
                    CASE 
                        WHEN ds.completed_visits > 0 THEN 
                            ROUND(CAST((COALESCE(on_time.count, 0)::float / ds.completed_visits::float) * 100 AS NUMERIC), 2)
                        ELSE 0 
                    END AS punctuality_rate,
                    
                    -- Financial Metrics
                    ds.expected_revenue,
                    ds.actual_revenue,
                    (ds.actual_revenue - ds.expected_revenue) AS revenue_variance,
                    
                    CASE 
                        WHEN ds.expected_revenue > 0 THEN 
                            ROUND(CAST((ds.actual_revenue / ds.expected_revenue) * 100 AS NUMERIC), 2)
                        ELSE 0 
                    END AS revenue_achievement_rate,
                    
                    rc.id AS currency_id,
                    
                    -- Time Metrics
                    COALESCE(time_stats.total_planned_time, 0) AS total_planned_time,
                    COALESCE(time_stats.total_actual_time, 0) AS total_actual_time,
                    
                    CASE 
                        WHEN time_stats.total_planned_time > 0 THEN 
                            ROUND(CAST((time_stats.total_actual_time / time_stats.total_planned_time) * 100 AS NUMERIC), 2)
                        ELSE 0 
                    END AS time_efficiency,
                    
                    CASE 
                        WHEN ds.completed_visits > 0 THEN 
                            ROUND(CAST(time_stats.total_actual_time / ds.completed_visits AS NUMERIC), 2)
                        ELSE 0 
                    END AS average_visit_duration,
                    
                    -- Travel Metrics
                    ds.total_distance,
                    ds.actual_travel_time,
                    0.0 AS fuel_cost,
                    
                    -- Customer Metrics
                    COALESCE(customer_stats.unique_customers, 0) AS unique_customers,
                    COALESCE(customer_stats.new_customers, 0) AS new_customers,
                    COALESCE(customer_stats.repeat_customers, 0) AS repeat_customers,
                    
                    -- Visit Type Distribution
                    COALESCE(visit_types.sales_visits, 0) AS sales_visits,
                    COALESCE(visit_types.follow_up_visits, 0) AS follow_up_visits,
                    COALESCE(visit_types.support_visits, 0) AS support_visits
                    
                FROM daily_visit_schedule ds
                LEFT JOIN res_users ru ON ds.sales_rep_id = ru.id
                LEFT JOIN res_partner rp ON ru.partner_id = rp.id
                LEFT JOIN res_company rc ON rc.id = (
                    SELECT company_id FROM res_users WHERE id = ds.sales_rep_id LIMIT 1
                )
                
                -- On-time visits subquery
                LEFT JOIN (
                    SELECT 
                        schedule_id,
                        COUNT(*) as count
                    FROM daily_visit_line dvl
                    WHERE dvl.state = 'completed' 
                        AND dvl.actual_start_time <= dvl.planned_time + 0.25  -- 15 minutes tolerance
                    GROUP BY schedule_id
                ) on_time ON ds.id = on_time.schedule_id
                
                -- Late visits subquery
                LEFT JOIN (
                    SELECT 
                        schedule_id,
                        COUNT(*) as count
                    FROM daily_visit_line dvl
                    WHERE dvl.state = 'completed' 
                        AND dvl.actual_start_time > dvl.planned_time + 0.25  -- 15 minutes tolerance
                    GROUP BY schedule_id
                ) late ON ds.id = late.schedule_id
                
                -- Time statistics subquery
                LEFT JOIN (
                    SELECT 
                        schedule_id,
                        SUM(planned_duration) as total_planned_time,
                        SUM(actual_duration) as total_actual_time
                    FROM daily_visit_line dvl
                    WHERE dvl.state = 'completed'
                    GROUP BY schedule_id
                ) time_stats ON ds.id = time_stats.schedule_id
                
                -- Cancelled visits subquery
                LEFT JOIN (
                    SELECT 
                        schedule_id,
                        COUNT(*) as cancelled_visits
                    FROM daily_visit_line dvl
                    WHERE dvl.state = 'cancelled'
                    GROUP BY schedule_id
                ) cancelled_stats ON ds.id = cancelled_stats.schedule_id
                
                -- Customer statistics subquery
                LEFT JOIN (
                    SELECT 
                        schedule_id,
                        COUNT(DISTINCT customer_id) as unique_customers,
                        COUNT(DISTINCT CASE 
                            WHEN NOT EXISTS (
                                SELECT 1 FROM daily_visit_line dvl2 
                                JOIN daily_visit_schedule ds2 ON dvl2.schedule_id = ds2.id
                                WHERE dvl2.customer_id = dvl.customer_id 
                                    AND ds2.visit_date < ds.visit_date
                            ) THEN customer_id 
                        END) as new_customers,
                        COUNT(DISTINCT CASE 
                            WHEN EXISTS (
                                SELECT 1 FROM daily_visit_line dvl2 
                                JOIN daily_visit_schedule ds2 ON dvl2.schedule_id = ds2.id
                                WHERE dvl2.customer_id = dvl.customer_id 
                                    AND ds2.visit_date < ds.visit_date
                            ) THEN customer_id 
                        END) as repeat_customers
                    FROM daily_visit_line dvl
                    JOIN daily_visit_schedule ds ON dvl.schedule_id = ds.id
                    GROUP BY schedule_id
                ) customer_stats ON ds.id = customer_stats.schedule_id
                
                -- Visit type distribution subquery
                LEFT JOIN (
                    SELECT 
                        schedule_id,
                        COUNT(CASE WHEN visit_type = 'sales' THEN 1 END) as sales_visits,
                        COUNT(CASE WHEN visit_type = 'follow_up' THEN 1 END) as follow_up_visits,
                        COUNT(CASE WHEN visit_type = 'support' THEN 1 END) as support_visits
                    FROM daily_visit_line
                    GROUP BY schedule_id
                ) visit_types ON ds.id = visit_types.schedule_id
                
                ORDER BY ds.visit_date DESC, ds.sales_rep_id
            )
        """ % self._table)


class DailyVisitAnalytics(models.Model):
    _name = 'daily.visit.analytics'
    _description = 'Daily Visit Analytics'
    _auto = False
    _rec_name = 'period'
    _order = 'period desc'

    period = fields.Char('Period', readonly=True)
    period_type = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ], 'Period Type', readonly=True)
    
    sales_rep_id = fields.Many2one('res.users', 'Sales Representative', readonly=True)
    
    # Aggregated Metrics
    total_schedules = fields.Integer('Total Schedules', readonly=True)
    total_visits = fields.Integer('Total Visits', readonly=True)
    avg_completion_rate = fields.Float('Average Completion Rate (%)', readonly=True)
    avg_revenue_achievement = fields.Float('Average Revenue Achievement (%)', readonly=True)
    total_revenue = fields.Monetary('Total Revenue', readonly=True, currency_field='currency_id')
    total_distance = fields.Float('Total Distance (KM)', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Currency', readonly=True)
    
    @api.model
    def get_analytics_data(self, period_type='monthly', sales_rep_id=None, date_from=None, date_to=None):
        """Get analytics data for charts and reports"""
        domain = []
        
        if sales_rep_id:
            domain.append(('sales_rep_id', '=', sales_rep_id))
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        
        reports = self.env['daily.visit.report'].search(domain)
        
        # Group data by period
        analytics = {}
        for report in reports:
            if period_type == 'daily':
                period_key = report.date.strftime('%Y-%m-%d')
            elif period_type == 'weekly':
                week_start = report.date - timedelta(days=report.date.weekday())
                period_key = week_start.strftime('%Y-W%U')
            elif period_type == 'monthly':
                period_key = report.date.strftime('%Y-%m')
            elif period_type == 'quarterly':
                quarter = (report.date.month - 1) // 3 + 1
                period_key = f"{report.date.year}-Q{quarter}"
            
            if period_key not in analytics:
                analytics[period_key] = {
                    'period': period_key,
                    'total_visits': 0,
                    'completed_visits': 0,
                    'total_revenue': 0,
                    'total_distance': 0,
                    'schedules_count': 0,
                }
            
            analytics[period_key]['total_visits'] += report.total_visits
            analytics[period_key]['completed_visits'] += report.completed_visits
            analytics[period_key]['total_revenue'] += report.actual_revenue or 0
            analytics[period_key]['total_distance'] += report.total_distance or 0
            analytics[period_key]['schedules_count'] += 1
        
        # Calculate completion rates
        for data in analytics.values():
            if data['total_visits'] > 0:
                data['completion_rate'] = (data['completed_visits'] / data['total_visits']) * 100
            else:
                data['completion_rate'] = 0
        
        return list(analytics.values())