{
    'name': 'Staff Transport Management',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Fleet',
    'summary': 'Manage staff transport routes, stops, vehicle assignments, and map views',
    'description': """
Staff Transport Management System
=================================
Extends Fleet and Employees modules to provide end-to-end staff transport operations:
- Transport routes with direction, vehicle assignment, capacity, and occupancy tracking.
- Sequence-ordered stops with map view integration (web_map) and drag-and-drop ordering.
- Google Maps directions generation with waypoints.
- Extended fleet.vehicle with seat capacity override and trip tracking.
- Extended hr.employee with transport enablement, route assignments, and stop constraints.
- Multi-company data isolation and role-based access control.
    """,
    'author': 'Nasim Ullah',
    'depends': [
        'hr',
        'fleet',
        'contacts',
        'mail',
        'web_map',
    ],
    'data': [
        'security/transport_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/transport_trip_views.xml',
        'views/generate_trips_wizard_views.xml',
        'views/transport_vehicle_request_views.xml',
        'views/transport_schedule_views.xml',
        'views/transport_stop_views.xml',
        'views/transport_route_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/hr_employee_views.xml',
        'views/transport_menu_views.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
