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
    ],

    'images': ['static/description/icon.svg'],
    'installable': True,
    'application': True,
    'auto_install': False,
}