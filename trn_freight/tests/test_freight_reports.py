from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestFreightReports(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_shipper = cls.env['res.partner'].create({
            'name': 'Apex Logistics Shipper Ltd',
            'street': '123 Port Road',
            'city': 'Karachi',
        })
        cls.partner_consignee = cls.env['res.partner'].create({
            'name': 'Global Importers Inc',
            'street': '456 Commercial Ave',
            'city': 'Lahore',
        })
        cls.partner_agent = cls.env['res.partner'].create({
            'name': 'Premier Customs Brokerage',
        })

        cls.country = cls.env.ref('base.us')

        cls.port_origin = cls.env['freight.port'].create({
            'name': 'Port of Karachi',
            'code': 'KHI01',
            'country_id': cls.country.id,
            'is_land': True,
            'is_water': True,
        })
        cls.port_dest = cls.env['freight.port'].create({
            'name': 'Port of Lahore Dryport',
            'code': 'LHE01',
            'country_id': cls.country.id,
            'is_land': True,
            'is_water': True,
        })

        cls.container = cls.env['freight.container'].create({
            'name': '40FT Standard Container',
            'code': '40FT-STD',
            'state': 'available',
        })

        cls.route = cls.env['freight.routes'].create({
            'name': 'Karachi to Lahore Highway Express',
            'land_price': 500.0,
            'air_price': 1200.0,
            'water_price': 800.0,
        })

        cls.service = cls.env['freight.service'].create({
            'name': 'Port Handling & Documentation',
            'sale_price': 150.0,
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Industrial Machinery Parts',
        })

    def _create_sample_order(self):
        """Helper to create a populated freight order with cargo, routes, services and tracking."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'consignee_id': self.partner_consignee.id,
            'agent_id': self.partner_agent.id,
            'transport': 'land',
            'land_type': 'ftl',
            'shipping_type': 'export',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
            'cargo_line_ids': [
                (0, 0, {
                    'container_id': self.container.id,
                    'product_id': self.product.id,
                    'billing_on': 'weight',
                    'weight': 100.0,
                    'volume': 10.0,
                    'unit_price': 50.0,
                }),
            ],
            'route_line_ids': [
                (0, 0, {
                    'route_id': self.route.id,
                    'source_port_id': self.port_origin.id,
                    'destination_port_id': self.port_dest.id,
                    'transport': 'land',
                    'sale_price': 500.0,
                }),
            ],
            'service_line_ids': [
                (0, 0, {
                    'service_id': self.service.id,
                    'quantity': 2.0,
                    'sale': 150.0,
                }),
            ],
            'track_line_ids': [
                (0, 0, {
                    'source_port_id': self.port_origin.id,
                    'destination_port_id': self.port_dest.id,
                    'transport': 'land',
                    'received_delivered': 'received',
                }),
                (0, 0, {
                    'source_port_id': self.port_origin.id,
                    'destination_port_id': self.port_dest.id,
                    'transport': 'land',
                    'received_delivered': 'delivered',
                }),
            ],
        })
        return order

    def test_report_actions_binding(self):
        """Verify both reports are properly registered in Print menu and configured."""
        report_order = self.env.ref('trn_freight.action_report_freight_order')
        report_tracking = self.env.ref('trn_freight.action_report_freight_tracking')

        # Check Freight Order report binding
        self.assertEqual(report_order.model, 'freight.shipping')
        self.assertEqual(report_order.report_type, 'qweb-pdf')
        self.assertEqual(report_order.binding_type, 'report')
        self.assertEqual(report_order.binding_model_id.model, 'freight.shipping')

        # Check Tracking report binding
        self.assertEqual(report_tracking.model, 'freight.shipping')
        self.assertEqual(report_tracking.report_type, 'qweb-pdf')
        self.assertEqual(report_tracking.binding_type, 'report')
        self.assertEqual(report_tracking.binding_model_id.model, 'freight.shipping')

    def test_freight_order_pdf_report_generation(self):
        """Verify Freight Order PDF generates cleanly with valid PDF bytes."""
        order = self._create_sample_order()
        self.assertEqual(order.total, 5800.0)  # 5000 (cargo) + 500 (route) + 300 (services)

        report = self.env.ref('trn_freight.action_report_freight_order').with_context(force_report_rendering=True)
        pdf_content, _ = report._render_qweb_pdf('trn_freight.report_freight_order_template', res_ids=order.ids)

        self.assertTrue(pdf_content, "PDF content should not be empty")
        self.assertTrue(len(pdf_content) > 1000, "PDF content should contain binary data")
        self.assertTrue(pdf_content.startswith(b'%PDF-'), "Output must be a valid PDF binary")

    def test_freight_tracking_pdf_report_generation(self):
        """Verify Tracking PDF report generates cleanly with valid PDF bytes."""
        order = self._create_sample_order()
        self.assertEqual(len(order.track_line_ids), 2)

        report = self.env.ref('trn_freight.action_report_freight_tracking').with_context(force_report_rendering=True)
        pdf_content, _ = report._render_qweb_pdf('trn_freight.report_freight_tracking_template', res_ids=order.ids)

        self.assertTrue(pdf_content, "Tracking PDF content should not be empty")
        self.assertTrue(len(pdf_content) > 1000, "Tracking PDF content should contain binary data")
        self.assertTrue(pdf_content.startswith(b'%PDF-'), "Output must be a valid PDF binary")

    def test_long_order_pagination_25_lines(self):
        """Verify long order (25+ cargo lines) renders and paginates cleanly without crashing."""
        cargo_lines = []
        for i in range(1, 26):
            cargo_lines.append((0, 0, {
                'container_id': self.container.id,
                'product_id': self.product.id,
                'billing_on': 'weight',
                'weight': float(i * 10),
                'volume': float(i),
                'unit_price': 25.0,
            }))

        long_order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'consignee_id': self.partner_consignee.id,
            'agent_id': self.partner_agent.id,
            'transport': 'land',
            'land_type': 'ftl',
            'shipping_type': 'export',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
            'cargo_line_ids': cargo_lines,
        })
        self.assertEqual(len(long_order.cargo_line_ids), 25)

        # Render QWeb HTML
        report = self.env.ref('trn_freight.action_report_freight_order')
        html_content, _ = report._render_qweb_html('trn_freight.report_freight_order_template', docids=long_order.ids)
        self.assertTrue(html_content)

        # Render Multi-Page PDF
        pdf_content, _ = report.with_context(force_report_rendering=True)._render_qweb_pdf(
            'trn_freight.report_freight_order_template',
            res_ids=long_order.ids
        )
        self.assertTrue(pdf_content.startswith(b'%PDF-'))
        # Multi-page PDF should be substantially sized
        self.assertTrue(len(pdf_content) > 5000)
