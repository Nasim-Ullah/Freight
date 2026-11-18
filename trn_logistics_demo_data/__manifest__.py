# -*- coding: utf-8 -*-
{
    'name': 'Logistics & Staff Transport Demo Data',
    'version': '19.0.1.0.0',
    'category': 'Logistics/Demo',
    'summary': 'Comprehensive end-to-end demo data for PakLink Logistics Pvt Ltd',
    'description': """
PakLink Logistics Demo Data & Enterprise Scenario
=================================================
Final training milestone module providing master records, operational freight
shipments, customs clearances, milestone tracking events, and staff transport
schedules/trips across synchronized operational workflows.
    """,
    'author': 'Nasim Ullah',
    'depends': [
        'trn_freight',
        'trn_staff_transport',
        'trn_freight_dashboard',
    ],
    'data': [
        'data/master_company_partner_data.xml',
        'data/master_freight_foundations_data.xml',
        'data/master_transport_routes_stops_data.xml',
        'data/operational_freight_orders_data.xml',
        'data/staff_transport_operations_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
