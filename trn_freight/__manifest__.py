{
    'name': 'Freight Management System',
    'version': '19.0.1.0.0',
    'category': 'Logistics and Supply Chain',
    'summary': 'Manage Shippers,Consignee,Agents,Import/Export',
    'description': """
    Freight Management System (FMS)
    ===============================
    System for managing global and domestic freight operations:
    """,
    'author': 'Nasim Ullah',
    'depends': [],
    'data': [
        'security/ir.model.access.csv',
        'views/freight_port.xml',
        'views/freight_container.xml',
        'views/freight_price.xml',
        'views/freight_routes.xml',
        'views/freight_service.xml',
    ],
    'images':['static/description/icon.png'],
    'application':True,
    'installable':True,
    'license': 'LGPL-3',
}