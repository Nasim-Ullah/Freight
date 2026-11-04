import base64
from odoo.exceptions import UserError
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestCustomClearance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_shipper = cls.env['res.partner'].create({
            'name': 'Test Shipper Global',
        })
        cls.partner_agent = cls.env['res.partner'].create({
            'name': 'Test Customs Agent Global',
        })

        cls.country = cls.env.ref('base.us')

        cls.port_origin = cls.env['freight.port'].create({
            'name': 'Clearance Origin Port',
            'code': 'COP01',
            'country_id': cls.country.id,
            'is_land': True,
        })
        cls.port_dest = cls.env['freight.port'].create({
            'name': 'Clearance Dest Port',
            'code': 'CDP01',
            'country_id': cls.country.id,
            'is_land': True,
        })

    def test_full_clearance_and_order_flow(self):
        """Test full flow: Order -> Create Clearance -> Upload doc -> Confirm clearance -> Confirm order."""
        # 1. Create Freight Order
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'agent_id': self.partner_agent.id,
            'transport': 'land',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
        })
        order.action_submit()
        self.assertEqual(order.clearance_count, 0)

        # 2. Click 'Create Clearance' button
        action = order.action_custom_clearance()
        self.assertEqual(action.get('res_model'), 'custom.clearance')
        self.assertEqual(order.clearance_count, 1)

        clearance = order.clearance_ids[0]
        self.assertEqual(clearance.shipping_id, order)
        self.assertEqual(clearance.agent_id, self.partner_agent)
        self.assertEqual(clearance.loading_port_id, self.port_origin)
        self.assertEqual(clearance.discharge_port_id, self.port_dest)
        self.assertEqual(clearance.state, 'draft')
        self.assertTrue(clearance.name.startswith('CLR/'))

        # Clicking 'Create Clearance' again should return action opening the existing clearance
        second_action = order.action_custom_clearance()
        self.assertEqual(second_action.get('res_id'), clearance.id)
        self.assertEqual(order.clearance_count, 1)

        # 3. Upload document lines with binary attachments
        dummy_file_content = base64.b64encode(b"Dummy Bill of Lading PDF Content").decode('utf-8')
        doc_line = self.env['custom.clearance.line'].create({
            'clearance_id': clearance.id,
            'name': 'Bill of Lading',
            'file': dummy_file_content,
            'file_name': 'bol.pdf',
        })
        self.assertEqual(len(clearance.line_ids), 1)
        self.assertEqual(doc_line.clearance_id, clearance)

        # 4. Attempt to confirm order while clearance is Draft -> Refused
        with self.assertRaises(UserError):
            order.action_confirm()

        # 5. Confirm Clearance
        clearance.action_confirm()
        self.assertEqual(clearance.state, 'confirmed')

        # 6. Confirm Order -> Now succeeds
        order.action_confirm()
        self.assertEqual(order.state, 'confirmed')

    def test_order_confirm_refused_without_clearance(self):
        """Order Confirm must refuse if there is no clearance."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'transport': 'land',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
        })
        order.action_submit()
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_draft_order_deletion_deletes_draft_clearance(self):
        """Deleting a Draft order also deletes its Draft clearance."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'transport': 'land',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
        })
        order.action_custom_clearance()
        self.assertEqual(len(order.clearance_ids), 1)
        clearance = order.clearance_ids[0]
        self.assertEqual(clearance.state, 'draft')

        # Delete Draft Order
        order.unlink()
        self.assertFalse(clearance.exists(), "Draft clearance should be deleted when Draft order is deleted.")

    def test_order_with_confirmed_clearance_cannot_be_deleted(self):
        """An order with a confirmed clearance cannot be deleted."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'transport': 'land',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
        })
        order.action_custom_clearance()
        clearance = order.clearance_ids[0]
        clearance.action_confirm()

        # Attempt to delete order with confirmed clearance -> Refused
        with self.assertRaises(UserError):
            order.unlink()

    def test_revision_wizard_creates_revision(self):
        """The revision wizard creates a revision with reason and updates count."""
        order = self.env['freight.shipping'].create({
            'shipper_id': self.partner_shipper.id,
            'transport': 'land',
            'loading_port_id': self.port_origin.id,
            'discharge_port_id': self.port_dest.id,
        })
        order.action_custom_clearance()
        clearance = order.clearance_ids[0]
        self.assertEqual(clearance.revision_count, 0)

        # Open and submit Revision Wizard
        wizard = self.env['custom.clearance.revision'].create({
            'clearance_id': clearance.id,
            'reason': 'Customs duty tariff rate adjustment requested by customs officer',
            'note': 'Verified with tax certificate 9923',
        })
        res = wizard.action_create_revision()
        self.assertEqual(res.get('type'), 'ir.actions.act_window_close')

        self.assertEqual(clearance.revision_count, 1)
        revision = clearance.revision_ids[0]
        self.assertEqual(revision.reason, 'Customs duty tariff rate adjustment requested by customs officer')
        self.assertEqual(revision.note, 'Verified with tax certificate 9923')
        self.assertTrue(revision.name.startswith('REV/'))
