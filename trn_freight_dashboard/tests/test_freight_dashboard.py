from odoo.tests.common import TransactionCase


class TestFreightDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dashboard = cls.env['freight.dashboard']
        cls.Shipping = cls.env['freight.shipping']

    def test_get_dashboard_data_structure(self):
        """Test that get_dashboard_data returns all expected keys and types."""
        data = self.Dashboard.get_dashboard_data()

        self.assertIn('state_counts', data)
        self.assertIn('state_labels', data)
        self.assertIn('kpis', data)
        self.assertIn('monthly_trend', data)
        self.assertIn('currency', data)

        # Check state counts keys
        for st in ('draft', 'submitted', 'confirmed', 'invoiced', 'done', 'cancel'):
            self.assertIn(st, data['state_counts'])
            self.assertIsInstance(data['state_counts'][st], int)

        # Check KPIs keys
        kpis = data['kpis']
        self.assertIn('active_orders', kpis)
        self.assertIn('total_orders', kpis)
        self.assertIn('revenue', kpis)
        self.assertIn('expense', kpis)
        self.assertIn('margin', kpis)
        self.assertIn('margin_pct', kpis)

        # Check monthly trend structure (6 months)
        trend = data['monthly_trend']
        self.assertEqual(len(trend['labels']), 6)
        self.assertEqual(len(trend['full_labels']), 6)
        self.assertEqual(len(trend['revenues']), 6)
        self.assertEqual(len(trend['expenses']), 6)

        # Check currency
        self.assertIn('symbol', data['currency'])
        self.assertIn('position', data['currency'])

    def test_kpi_margin_calculation(self):
        """Verify margin is mathematically equal to revenue minus expense."""
        data = self.Dashboard.get_dashboard_data()
        kpis = data['kpis']
        expected_margin = round(kpis['revenue'] - kpis['expense'], 2)
        self.assertAlmostEqual(kpis['margin'], expected_margin, places=2)

    def test_client_action_and_menu_configuration(self):
        """Verify client action and menu exist with correct sequence and tag."""
        action = self.env.ref('trn_freight_dashboard.action_freight_dashboard')
        self.assertEqual(action._name, 'ir.actions.client')
        self.assertEqual(action.tag, 'trn_freight_dashboard.dashboard')

        menu = self.env.ref('trn_freight_dashboard.menu_freight_dashboard')
        self.assertEqual(menu.name, 'Dashboard')
        self.assertEqual(menu.sequence, 1)
        self.assertEqual(menu.parent_id, self.env.ref('trn_freight.menu_freight_root'))
        self.assertEqual(menu.action, action)

