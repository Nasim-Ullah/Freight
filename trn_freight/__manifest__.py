{
    'name': 'Freight Management System',
    # 'version': '19.0.1.0.5',
    'version': '19.0.1.0.6',
    'category': 'Logistics and Supply Chain',
    'summary': 'Manage Shippers,Consignee,Agents,Import/Export',
    'description': """
    Freight Management System (FMS)
    ===============================
    System for managing global and domestic freight operations:
    """,
    'author': 'Nasim Ullah',
    'depends': ['base', 'mail', 'uom', 'product', 'account'],
    'data': [
        'security/freight_security.xml',
        'security/ir.model.access.csv',
        'views/freight_port.xml',
        'views/freight_container.xml',
        'views/freight_price.xml',
        'views/freight_routes.xml',
        'views/freight_service.xml',
        'views/freight_shipping.xml',
        'views/freight_sequence.xml',
        'views/custom_clearance.xml',
        'views/custom_clearance_revision_wizard.xml',
        'views/freight_order_track_wizard.xml',
    ],
    'images':['static/description/icon.png'],
    'application':True,
    'installable':True,
    'license': 'LGPL-3',
}