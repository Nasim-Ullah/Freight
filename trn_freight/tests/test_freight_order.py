from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestFreightOrder(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.country = cls.env.ref('base.us')

        cls.partner_shipper = cls.env['res.partner'].create({
            'name': 'Test Shipper Partner',
        })

        cls.land_port_origin = cls.env['freight.port'].create({
            'name': 'Origin Land Port',
            'code': 'OLP01',
            'country_id': cls.country.id,
            'is_land': True,
            'is_air': False,
            'is_water': False,
        })

        cls.land_port_dest = cls.env['freight.port'].create({
            'name': 'Destination Land Port',
            'code': 'DLP01',
            'country_id': cls.country.id,
            'is_land': True,
            'is_air': False,
            'is_water': False,
        })

        cls.sea_port = cls.env['freight.port'].create({
            'name': 'Deep Sea Port',
            'code': 'DSP01',
            'country_id': cls.country.id,
            'is_land': False,
            'is_air': False,
            'is_water': True,
        })

        cls.container = cls.env['freight.container'].create({
            'name': 'Standard 20ft Container',
            'code': 'CONT20',
            'state': 'available',
        })

    def test_totals_calculated_correctly(self):
        """Test 1: Verify freight order cargo volume, weight, and price totals."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'transport': 'land',
            'loading_port_id': self.land_port_origin.id,
            'discharge_port_id': self.land_port_dest.id,
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
            ]
        })

        # Line 1: 100.0 * 50.0 = 5000.0
        # Line 2: 5.0 * 200.0 = 1000.0
        # Total weight: 120.0
        # Total volume: 15.0
        # Grand total: 6000.0
        self.assertEqual(order.total_weight, 120.0, "Total weight calculation is incorrect.")
        self.assertEqual(order.total_volume, 15.0, "Total volume calculation is incorrect.")
        self.assertEqual(order.total, 6000.0, "Order total price calculation is incorrect.")

    def test_order_workflow_and_container_state(self):
        """Test 2: Submit -> Confirm -> Done state machine and container state transitions."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'transport': 'land',
            'loading_port_id': self.land_port_origin.id,
            'discharge_port_id': self.land_port_dest.id,
            'cargo_line_ids': [
                (0, 0, {
                    'container_id': self.container.id,
                    'billing_on': 'weight',
                    'weight': 50.0,
                    'volume': 5.0,
                    'unit_price': 10.0,
                }),
            ]
        })

        # Initial states
        self.assertEqual(order.state, 'draft', "Initial order state should be draft.")
        self.assertEqual(self.container.state, 'available', "Container should initially be available.")

        # Submit
        order.action_submit()
        self.assertEqual(order.state, 'submitted', "Order state should transition to submitted.")
        self.assertEqual(self.container.state, 'available', "Container should remain available on submit.")

        # Confirm -> container becomes reserved
        order.action_confirm()
        self.assertEqual(order.state, 'confirmed', "Order state should transition to confirmed.")
        self.assertEqual(self.container.state, 'reserved', "Container should become reserved upon confirmation.")

        # Done -> container is released back to available
        order.action_done()
        self.assertEqual(order.state, 'done', "Order state should transition to done.")
        self.assertEqual(self.container.state, 'available', "Container should be released back to available upon completion.")

    def test_wrong_port_refused(self):
        """Test 3: Wrong port for selected transport type raises ValidationError."""
        # Attempt to create land shipping order with a sea port
        with self.assertRaises(ValidationError):
            self.env['freight.shipping'].create({
                'shipper_id': self.partner_shipper.id,
                'transport': 'land',
                'loading_port_id': self.land_port_origin.id,
                'discharge_port_id': self.sea_port.id,  # Sea port does not support land
            })

    def test_deleting_confirmed_order_refused(self):
        """Test 4: Deleting a confirmed order raises UserError."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'transport': 'land',
            'loading_port_id': self.land_port_origin.id,
            'discharge_port_id': self.land_port_dest.id,
        })
        order.action_submit()
        order.action_confirm()
        self.assertEqual(order.state, 'confirmed')

        # Deleting confirmed order must raise UserError
        with self.assertRaises(UserError):
            order.unlink()

        # Draft order can be deleted by authorized user
        draft_order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'transport': 'land',
            'loading_port_id': self.land_port_origin.id,
            'discharge_port_id': self.land_port_dest.id,
        })
        draft_order.unlink()
        self.assertFalse(draft_order.exists(), "Draft order should be successfully deleted.")
