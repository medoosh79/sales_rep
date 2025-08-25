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
    'external_dependencies': {
        'python': ['reportlab', 'xlsxwriter'],
    },
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/expense_sequences.xml',
        'data/leads_sequences.xml',
        'data/demo_data.xml',
        'views/sales_rep_views.xml',
        'views/sales_rep_assignment_views.xml',
        'views/commission_views.xml',
        'views/geo_node_views.xml',
        'views/product_line_views.xml',
        'views/territory_assignment_views.xml',
        # 'views/gps_tracking_views.xml',  # Temporarily disabled




        'views/dashboard_views.xml',
        'views/dynamic_route_views.xml',
        'views/route_customer_views.xml',
        'wizard/sales_dashboard_wizard_views.xml',
        'views/daily_visit_schedule_views.xml',
        'views/daily_visit_tracker_views.xml',
        'views/daily_visit_report_views.xml',
        'wizard/daily_visit_schedule_wizard_views.xml',
        'views/visit_analytics_dashboard_views.xml',
        'views/field_inventory_views.xml',
        'views/advanced_reports_views.xml',
        'views/expense_management_views.xml',
        'views/leads_management_views.xml',
        'views/training_evaluation_views.xml',
        'data/training_sequences.xml',
        'views/incentives_rewards_views.xml',
        'data/incentives_sequences.xml',


    ],
    'assets': {
        'web.assets_backend': [
            'sales_rep_mgmt_pro/static/src/css/main_theme.css',
            'sales_rep_mgmt_pro/static/src/css/enhanced_forms.css',
            'sales_rep_mgmt_pro/static/src/css/enhanced_lists.css',
            'sales_rep_mgmt_pro/static/src/css/responsive_mobile.css',
            'sales_rep_mgmt_pro/static/src/css/daily_visit_tracker.css',
            'sales_rep_mgmt_pro/static/src/css/visit_analytics_dashboard.css',
            'sales_rep_mgmt_pro/static/src/css/gps_interactive_maps.css',
            'sales_rep_mgmt_pro/static/src/js/interactive_charts.js',
            'sales_rep_mgmt_pro/static/src/js/real_time_notifications.js',
            'sales_rep_mgmt_pro/static/src/js/daily_visit_tracker.js',
            'sales_rep_mgmt_pro/static/src/js/visit_analytics_dashboard.js',
            'sales_rep_mgmt_pro/static/src/js/gps_interactive_maps.js',
            'sales_rep_mgmt_pro/static/src/xml/daily_visit_tracker.xml',
            'sales_rep_mgmt_pro/static/src/xml/visit_analytics_dashboard.xml',
            'sales_rep_mgmt_pro/static/src/xml/gps_interactive_maps.xml',
        ],
    },

    # 'images': ['static/description/icon.svg'],
    'installable': True,
    'application': True,
    'auto_install': False,
}