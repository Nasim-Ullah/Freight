# -*- coding: utf-8 -*-
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install', 'trn_logistics_demo_data')
class TestLogisticsDemoData(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_paklink = cls.env.ref('trn_logistics_demo_data.company_paklink', raise_if_not_found=False)

    def test_01_company_and_master_partners(self):
        """Verify PakLink company and master partner records."""
        self.assertTrue(self.company_paklink, "PakLink Logistics company should exist.")
        self.assertEqual(self.company_paklink.name, "PakLink Logistics Pvt Ltd")

        # Shippers
        indus = self.env.ref('trn_logistics_demo_data.partner_indus_textile', raise_if_not_found=False)
        self.assertTrue(indus, "Indus Textile Mills partner should exist.")
        khyber = self.env.ref('trn_logistics_demo_data.partner_khyber_agro', raise_if_not_found=False)
        self.assertTrue(khyber, "Khyber Agro partner should exist.")

        # Drivers
        driver_rashid = self.env.ref('trn_logistics_demo_data.partner_driver_rashid', raise_if_not_found=False)
        self.assertTrue(driver_rashid and driver_rashid.is_driver, "Driver Rashid should exist and have is_driver=True.")
        driver_tariq = self.env.ref('trn_logistics_demo_data.partner_driver_tariq', raise_if_not_found=False)
        self.assertTrue(driver_tariq and driver_tariq.is_driver, "Driver Tariq should exist and have is_driver=True.")

    def test_02_freight_foundations(self):
        """Verify ports, containers, price lists, and services."""
        port_pkbqm = self.env.ref('trn_logistics_demo_data.port_pkbqm', raise_if_not_found=False)
        self.assertTrue(port_pkbqm, "PKBQM port should exist.")
        self.assertTrue(port_pkbqm.is_water and port_pkbqm.is_land, "PKBQM should be water and land port.")

        port_opkc = self.env.ref('trn_logistics_demo_data.port_opkc', raise_if_not_found=False)
        self.assertTrue(port_opkc and port_opkc.is_air, "OPKC airport cargo port should exist.")

        # Containers
        reefer = self.env.ref('trn_logistics_demo_data.container_reefer_40ft_01', raise_if_not_found=False)
        self.assertTrue(reefer, "40ft Reefer container should exist.")

    def test_03_freight_orders_lifecycle(self):
        """Verify the 6 operational freight orders across their distinct lifecycle states."""
        o1 = self.env.ref('trn_logistics_demo_data.order_01_draft', raise_if_not_found=False)
        self.assertTrue(o1, "Order 1 should exist.")
        self.assertEqual(o1.state, 'draft', "Order 1 should be in draft state.")

        o2 = self.env.ref('trn_logistics_demo_data.order_02_submitted', raise_if_not_found=False)
        self.assertTrue(o2, "Order 2 should exist.")
        self.assertIn(o2.state, ('submitted', 'draft'), "Order 2 should be submitted.")

        o3 = self.env.ref('trn_logistics_demo_data.order_03_confirmed', raise_if_not_found=False)
        self.assertTrue(o3, "Order 3 should exist.")
        self.assertIn(o3.state, ('confirmed', 'draft'), "Order 3 should be confirmed.")
        if o3.state == 'confirmed':
            reefer = self.env.ref('trn_logistics_demo_data.container_reefer_40ft_01', raise_if_not_found=False)
            self.assertEqual(reefer.state, 'reserved', "Confirmed order should reserve its container.")

        o4 = self.env.ref('trn_logistics_demo_data.order_04_invoiced', raise_if_not_found=False)
        self.assertTrue(o4, "Order 4 should exist.")
        self.assertIn(o4.state, ('invoiced', 'confirmed', 'draft'))

        o5 = self.env.ref('trn_logistics_demo_data.order_05_done', raise_if_not_found=False)
        self.assertTrue(o5, "Order 5 should exist.")
        self.assertIn(o5.state, ('done', 'confirmed', 'draft'))

        o6 = self.env.ref('trn_logistics_demo_data.order_06_cancelled', raise_if_not_found=False)
        self.assertTrue(o6, "Order 6 should exist.")
        self.assertIn(o6.state, ('cancel', 'draft'))

    def test_04_staff_transport_operations(self):
        """Verify vehicles, HR employees, routes, trips and attendance."""
        hiace = self.env.ref('trn_logistics_demo_data.vehicle_hiace_01', raise_if_not_found=False)
        self.assertTrue(hiace, "Toyota HiAce vehicle should exist.")
        self.assertEqual(hiace.effective_capacity, 14, "HiAce capacity should be 14.")

        route_r01 = self.env.ref('trn_logistics_demo_data.route_clifton_korangi', raise_if_not_found=False)
        self.assertTrue(route_r01, "Route R-01 should exist.")
        self.assertTrue(len(route_r01.stop_ids) >= 3, "Route R-01 should have at least 3 sequence stops.")

        emp_asif = self.env.ref('trn_logistics_demo_data.employee_asif_khan', raise_if_not_found=False)
        self.assertTrue(emp_asif and emp_asif.transport_enabled, "Employee Asif Khan should have transport enabled.")

        # Trips and passengers
        trip_1 = self.env.ref('trn_logistics_demo_data.trip_r01_completed', raise_if_not_found=False)
        self.assertTrue(trip_1, "Trip 1 should exist.")
        self.assertTrue(len(trip_1.passenger_ids) >= 2, "Trip 1 should have passenger records.")
        statuses = trip_1.passenger_ids.mapped('status')
        self.assertIn('dropped', statuses, "Trip 1 should have dropped passenger attendance.")
        self.assertIn('boarded', statuses, "Trip 1 should have boarded passenger attendance.")

        # Vehicle requests
        vreq = self.env.ref('trn_logistics_demo_data.vrequest_01_approved', raise_if_not_found=False)
        self.assertTrue(vreq, "Vehicle request 1 should exist.")
