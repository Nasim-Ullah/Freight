{
    'name': 'Freight Operations Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Freight/Logistics',
    'summary': 'Custom OWL Dashboard for Freight Operations',
    'description': """
Freight Operations Dashboard (OWL)
==================================
Interactive analytics dashboard for freight operations powered by Odoo 19 OWL framework:
- Real-time KPI summary cards (Orders, Revenue, Expense, Net Margin).
- State-wise order counts with click-to-filter drill-down.
- Monthly revenue vs. expense 6-month comparative trend chart.
- Responsive modern interface supporting desktop and mobile viewports.
    """,
    'author': 'Nasim Ullah',
    'depends': [
        'trn_freight',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/freight_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'trn_freight_dashboard/static/src/**/*.scss',
            'trn_freight_dashboard/static/src/**/*.js',
            'trn_freight_dashboard/static/src/**/*.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
