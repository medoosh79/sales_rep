# -*- coding: utf-8 -*-
{
    'name': 'Sales Representative Management PRO',
    'summary': 'Phase 1: Foundation for advanced sales rep assignment, geo segmentation, and product lines',
    'version': '1.0.0',
    'category': 'Sales',
    'sequence': 0,
    'author': 'Custom',
    'website': 'http://localhost',
    'license': 'LGPL-3',
    'depends': ['sale', 'mail', 'hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/sales_rep_views.xml',
        'views/sales_rep_assignment_views.xml',
        'views/commission_views.xml',
        'views/geo_node_views.xml',
        'views/product_line_views.xml',
        'views/territory_assignment_views.xml',




        'views/dashboard_views.xml',
        'views/dynamic_route_views.xml',
        'views/route_customer_views.xml',
        'wizard/sales_dashboard_wizard_views.xml',
        'views/daily_visit_schedule_views.xml',
        'views/daily_visit_tracker_views.xml',
        'views/daily_visit_report_views.xml',
        'wizard/daily_visit_schedule_wizard_views.xml',
        'views/visit_analytics_dashboard_views.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'sales_rep_mgmt_pro/static/src/css/daily_visit_tracker.css',
            'sales_rep_mgmt_pro/static/src/js/daily_visit_tracker.js',
            'sales_rep_mgmt_pro/static/src/xml/daily_visit_tracker.xml',
            'sales_rep_mgmt_pro/static/src/js/visit_analytics_dashboard.js',
            'sales_rep_mgmt_pro/static/src/xml/visit_analytics_dashboard.xml',
            'sales_rep_mgmt_pro/static/src/css/visit_analytics_dashboard.css',

        ],
    },

    'images': ['static/description/icon.svg'],
    'installable': True,
    'application': True,
    'auto_install': False,
}