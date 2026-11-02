from odoo.exceptions import AccessError
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestFreightSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_a = cls.env.ref('base.main_company')
        cls.company_b = cls.env['res.company'].create({
            'name': 'Test Freight Company B Security',
        })

        cls.user_freight_user_a = cls.env['res.users'].create({
            'name': 'Freight User Company A',
            'login': 'freight_user_sec_a',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('trn_freight.group_freight_user').id,
            ])],
        })

        cls.user_freight_user_b = cls.env['res.users'].create({
            'name': 'Freight User Company B',
            'login': 'freight_user_sec_b',
            'company_id': cls.company_b.id,
            'company_ids': [(6, 0, [cls.company_b.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('trn_freight.group_freight_user').id,
            ])],
        })

        cls.manager_freight_a = cls.env['res.users'].create({
            'name': 'Freight Manager Company A',
            'login': 'freight_mgr_sec_a',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('trn_freight.group_freight_manager').id,
            ])],
        })

    def test_multi_company_isolation(self):
        """Test 1: User of Company B cannot read or search orders belonging to Company A."""
        # Create order in Company A
        order_comp_a = self.env['freight.shipping'].with_company(self.company_a).create({
            'company_id': self.company_a.id,
            'transport': 'land',
        })

        # Add child cargo line
        cargo_line = self.env['freight.cargo.line'].with_company(self.company_a).create({
            'shipping_id': order_comp_a.id,
            'weight': 100.0,
            'volume': 10.0,
        })
        self.assertEqual(
            cargo_line.company_id, self.company_a,
            "Cargo line should inherit company_id from parent order via stored related field."
        )

        # User of Company B searches for orders in Company A
        orders_visible_to_b = self.env['freight.shipping'].with_user(
            self.user_freight_user_b
        ).with_company(self.company_b).search([('id', '=', order_comp_a.id)])

        self.assertFalse(
            orders_visible_to_b,
            "Security Breach: User of Company B was able to find Company A order via search!"
        )

        # User of Company B directly reads Company A order -> AccessError
        with self.assertRaises(AccessError):
            order_comp_a.with_user(self.user_freight_user_b).with_company(self.company_b).read(['name'])

        # User of Company B searches for child line -> cannot find it
        lines_visible_to_b = self.env['freight.cargo.line'].with_user(
            self.user_freight_user_b
        ).with_company(self.company_b).search([('id', '=', cargo_line.id)])

        self.assertFalse(
            lines_visible_to_b,
            "Security Breach: User of Company B was able to find child cargo line of Company A order!"
        )

    def test_normal_user_delete_blocked_manager_allowed(self):
        """Test 2: Normal user cannot delete orders (unlink = 0), Manager has full unlink access."""
        order = self.env['freight.shipping'].with_user(self.user_freight_user_a).create({
            'company_id': self.company_a.id,
            'transport': 'land',
        })

        # Normal user attempts to unlink -> AccessError
        with self.assertRaises(AccessError):
            order.with_user(self.user_freight_user_a).unlink()

        # Freight Manager unlinks -> Success
        order.with_user(self.manager_freight_a).unlink()
        self.assertFalse(order.exists(), "Freight Manager should be allowed to delete the order.")
