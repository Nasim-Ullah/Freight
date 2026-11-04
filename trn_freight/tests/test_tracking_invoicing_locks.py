from odoo.exceptions import UserError
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestTrackingInvoicingLocks(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.country = cls.env.ref('base.us')
        cls.partner_shipper = cls.env['res.partner'].create({'name': 'Shipper Alpha'})
        cls.partner_consignee = cls.env['res.partner'].create({'name': 'Consignee Beta'})
        cls.partner_agent = cls.env['res.partner'].create({'name': 'Agent Gamma'})

        cls.port_origin = cls.env['freight.port'].create({
            'name': 'Origin Test Port',
            'code': 'OTP01',
            'country_id': cls.country.id,
            'is_land': True,
        })
        cls.port_dest = cls.env['freight.port'].create({
            'name': 'Dest Test Port',
            'code': 'DTP01',
            'country_id': cls.country.id,
            'is_land': True,
        })

        cls.route = cls.env['freight.routes'].create({
            'name': 'Test Land Route',
            'land_price': 500.0,
        })

        cls.service = cls.env['freight.service'].create({
            'name': 'Cargo Inspection Service',
        })

    def _create_and_confirm_clearance(self, order):
        clearance = self.env['custom.clearance'].create({
            'shipping_id': order.id,
            'loading_port_id': order.loading_port_id.id,
            'discharge_port_id': order.discharge_port_id.id,
            'agent_id': order.agent_id.id,
            'company_id': order.company_id.id,
        })
        clearance.action_confirm()
        return clearance

    def test_invoice_creation_and_matching_totals_weight_and_volume(self):
        """Test invoice creation with one line per cargo, route and service line. Invoice total == order total."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'consignee_id': self.partner_consignee.id,
            'agent_id': self.partner_agent.id,
            'transport': 'land',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
            'cargo_line_ids': [
                (0, 0, {
                    'billing_on': 'weight',
                    'weight': 100.0,
                    'volume': 10.0,
                    'unit_price': 50.0,
                }),
                (0, 0, {
                    'billing_on': 'volume',
                    'weight': 20.0,
                    'volume': 5.0,
                    'unit_price': 200.0,
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
        })

        # Expected totals:
        # Cargo 1: 100.0 * 50.0 = 5000.0
        # Cargo 2: 5.0 * 200.0 = 1000.0
        # Route 1: 500.0
        # Service 1: 2.0 * 150.0 = 300.0
        # Grand Total = 6800.0
        self.assertEqual(order.total, 6800.0, "Freight order total was calculated incorrectly.")

        # Confirm order workflow
        self._create_and_confirm_clearance(order)
        order.action_submit()
        order.action_confirm()
        self.assertEqual(order.state, 'confirmed')

        # Create Invoice
        action = order.action_create_invoice()
        self.assertEqual(order.state, 'invoiced')
        self.assertEqual(order.invoice_count, 1)

        invoice = order.invoice_ids[0]
        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(invoice.partner_id, self.partner_shipper)
        self.assertEqual(invoice.invoice_origin, order.name)
        self.assertEqual(len(invoice.invoice_line_ids), 4, "Invoice should have 4 lines (2 cargo, 1 route, 1 service).")

        # Crucial requirement: Invoice total MUST equal order total
        self.assertEqual(invoice.amount_total, order.total, "Invoice total does not equal the order total.")
        self.assertEqual(invoice.amount_total, 6800.0)

    def test_cargo_line_locks(self):
        """Cargo lines cannot be added, changed or removed once the order is Confirmed or later."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'transport': 'land',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
            'cargo_line_ids': [
                (0, 0, {
                    'billing_on': 'weight',
                    'weight': 50.0,
                    'volume': 5.0,
                    'unit_price': 20.0,
                }),
            ]
        })
        cargo_line = order.cargo_line_ids[0]

        # In Draft state, modifications are allowed
        cargo_line.write({'weight': 60.0})
        self.assertEqual(cargo_line.weight, 60.0)

        # Transition to Confirmed
        self._create_and_confirm_clearance(order)
        order.action_submit()
        order.action_confirm()
        self.assertEqual(order.state, 'confirmed')

        # 1. Direct write must be refused
        with self.assertRaises(UserError):
            cargo_line.write({'weight': 80.0})

        # 2. Direct create of new line must be refused
        with self.assertRaises(UserError):
            self.env['freight.cargo.line'].create({
                'shipping_id': order.id,
                'billing_on': 'weight',
                'weight': 10.0,
                'volume': 1.0,
                'unit_price': 10.0,
            })

        # 3. Direct unlink must be refused
        with self.assertRaises(UserError):
            cargo_line.unlink()

    def test_route_and_service_line_locks(self):
        """Route and service lines cannot be changed once the order is Invoiced or later."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'transport': 'land',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
            'cargo_line_ids': [
                (0, 0, {
                    'billing_on': 'weight',
                    'weight': 50.0,
                    'volume': 5.0,
                    'unit_price': 20.0,
                }),
            ],
            'route_line_ids': [
                (0, 0, {
                    'route_id': self.route.id,
                    'transport': 'land',
                    'sale_price': 250.0,
                }),
            ],
            'service_line_ids': [
                (0, 0, {
                    'service_id': self.service.id,
                    'quantity': 1.0,
                    'sale': 100.0,
                }),
            ],
        })
        route_line = order.route_line_ids[0]
        service_line = order.service_line_ids[0]

        self._create_and_confirm_clearance(order)
        order.action_submit()
        order.action_confirm()

        # In Confirmed state, route and service lines can still be modified
        route_line.write({'sale_price': 300.0})
        service_line.write({'quantity': 2.0})

        # Invoice the order
        order.action_create_invoice()
        self.assertEqual(order.state, 'invoiced')

        # 1. Route line locked on write, create, unlink
        with self.assertRaises(UserError):
            route_line.write({'sale_price': 400.0})

        with self.assertRaises(UserError):
            self.env['freight.route.line'].create({
                'shipping_id': order.id,
                'route_id': self.route.id,
                'transport': 'land',
            })

        with self.assertRaises(UserError):
            route_line.unlink()

        # 2. Service line locked on write, create, unlink
        with self.assertRaises(UserError):
            service_line.write({'quantity': 5.0})

        with self.assertRaises(UserError):
            self.env['freight.order.service'].create({
                'shipping_id': order.id,
                'service_id': self.service.id,
            })

        with self.assertRaises(UserError):
            service_line.unlink()

    def test_tracking_wizard_and_partner_notifications(self):
        """Track button opens popup (freight.order.track), adds tracking line, posts chatter message."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'consignee_id': self.partner_consignee.id,
            'agent_id': self.partner_agent.id,
            'transport': 'land',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
        })

        initial_msg_count = len(order.message_ids)

        # Open and execute tracking wizard
        wizard = self.env['freight.order.track'].create({
            'shipping_id': order.id,
            'source_port_id': self.port_origin.id,
            'destination_port_id': self.port_dest.id,
            'transport': 'land',
            'received_delivered': 'received',
        })
        wizard.action_add_tracking()

        # Tracking line created
        self.assertEqual(len(order.track_line_ids), 1)
        track_line = order.track_line_ids[0]
        self.assertEqual(track_line.received_delivered, 'received')
        self.assertEqual(track_line.source_port_id, self.port_origin)
        self.assertEqual(track_line.destination_port_id, self.port_dest)

        # Chatter message posted
        self.assertGreater(len(order.message_ids), initial_msg_count)
        latest_message = order.message_ids[0]
        self.assertIn("Tracking Update", latest_message.body)
        self.assertTrue(set(latest_message.partner_ids.ids).issuperset({
            self.partner_shipper.id,
            self.partner_consignee.id,
            self.partner_agent.id,
        }))

    def test_notifications_on_submit_confirm_done(self):
        """Submit, Confirm and Done post chatter messages to order partners."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'consignee_id': self.partner_consignee.id,
            'agent_id': self.partner_agent.id,
            'transport': 'land',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
        })
        self._create_and_confirm_clearance(order)

        # Submit
        order.action_submit()
        msg_submit = order.message_ids[0]
        self.assertIn("submitted", msg_submit.body)
        self.assertTrue(set(msg_submit.partner_ids.ids).issuperset({
            self.partner_shipper.id, self.partner_consignee.id, self.partner_agent.id
        }))

        # Confirm
        order.action_confirm()
        msg_confirm = order.message_ids[0]
        self.assertIn("confirmed", msg_confirm.body)
        self.assertTrue(set(msg_confirm.partner_ids.ids).issuperset({
            self.partner_shipper.id, self.partner_consignee.id, self.partner_agent.id
        }))

        # Done
        order.action_done()
        msg_done = order.message_ids[0]
        self.assertIn("Done", msg_done.body)
        self.assertTrue(set(msg_done.partner_ids.ids).issuperset({
            self.partner_shipper.id, self.partner_consignee.id, self.partner_agent.id
        }))
