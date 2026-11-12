# -*- coding: utf-8 -*-
from datetime import date
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestStaffTransport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_a = cls.env.ref('base.main_company')
        cls.company_b = cls.env['res.company'].create({
            'name': 'Company B Logistics',
        })

        # Partners / Addresses
        cls.partner_driver = cls.env['res.partner'].create({
            'name': 'John Driver',
            'is_driver': True,
            'driver_license_number': 'DL-987654',
            'driver_license_type': 'htv',
        })
        cls.partner_start = cls.env['res.partner'].create({
            'name': 'Main Factory HQ',
            'street': '123 Industrial Blvd',
            'city': 'Metropolis',
            'partner_latitude': 40.7128,
            'partner_longitude': -74.0060,
        })
        cls.partner_stop1 = cls.env['res.partner'].create({
            'name': 'Subway Station Stop',
            'street': '5th Ave & 42nd St',
            'city': 'Metropolis',
            'partner_latitude': 40.7527,
            'partner_longitude': -73.9772,
        })
        cls.partner_stop2 = cls.env['res.partner'].create({
            'name': 'Residential Hub Stop',
            'street': '742 Evergreen Terrace',
            'city': 'Springfield',
            'partner_latitude': 40.7831,
            'partner_longitude': -73.9712,
        })
        cls.partner_end = cls.env['res.partner'].create({
            'name': 'Branch Plant Gate 3',
            'street': '99 Tech Zone Way',
            'city': 'Metropolis',
            'partner_latitude': 40.8000,
            'partner_longitude': -73.9500,
        })

        # Vehicle Model
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Ford'})
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'Transit Minibus',
            'brand_id': cls.brand.id,
        })

        # Vehicle
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': 'BUS-1001',
            'seats': 20,
            'driver_id': cls.partner_driver.id,
        })

        # Transport Route A
        cls.route_a = cls.env['logistics.transport.route'].create({
            'name': 'Morning Commute Line 1',
            'code': 'MCL-01',
            'direction': 'both',
            'vehicle_id': cls.vehicle.id,
            'start_address_id': cls.partner_start.id,
            'end_address_id': cls.partner_end.id,
            'distance': 35.5,
            'company_id': cls.company_a.id,
        })

        # Stops for Route A
        cls.stop_a1 = cls.env['logistics.transport.stop'].create({
            'name': 'Stop 1 - Subway',
            'route_id': cls.route_a.id,
            'address_id': cls.partner_stop1.id,
            'sequence': 10,
            'stop_type': 'both',
            'planned_time': 7.5,
        })
        cls.stop_a2 = cls.env['logistics.transport.stop'].create({
            'name': 'Stop 2 - Residential Hub',
            'route_id': cls.route_a.id,
            'address_id': cls.partner_stop2.id,
            'sequence': 20,
            'stop_type': 'both',
            'planned_time': 8.0,
        })

        # Route B (for isolation & cross-validation tests)
        cls.route_b = cls.env['logistics.transport.route'].create({
            'name': 'Line 2 Express',
            'code': 'L2-EXP',
            'direction': 'pickup',
            'company_id': cls.company_a.id,
        })
        cls.stop_b1 = cls.env['logistics.transport.stop'].create({
            'name': 'Stop B1',
            'route_id': cls.route_b.id,
            'address_id': cls.partner_stop1.id,
            'sequence': 10,
            'stop_type': 'pickup',
        })

        # Employees
        cls.employee_1 = cls.env['hr.employee'].create({
            'name': 'Alice Engineer',
            'company_id': cls.company_a.id,
        })
        cls.employee_2 = cls.env['hr.employee'].create({
            'name': 'Bob Analyst',
            'company_id': cls.company_a.id,
        })

        # Users for Security Tests
        cls.user_transport_user = cls.env['res.users'].create({
            'name': 'Transport Operational User',
            'login': 'transport_user_test',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('trn_staff_transport.group_transport_user').id,
            ])],
        })
        cls.user_transport_manager = cls.env['res.users'].create({
            'name': 'Transport Operational Manager',
            'login': 'transport_mgr_test',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('trn_staff_transport.group_transport_manager').id,
            ])],
        })
        cls.user_company_b = cls.env['res.users'].create({
            'name': 'Company B User',
            'login': 'comp_b_user_test',
            'company_id': cls.company_b.id,
            'company_ids': [(6, 0, [cls.company_b.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('trn_staff_transport.group_transport_user').id,
            ])],
        })

    def test_vehicle_capacity_override_and_trips(self):
        """Test fleet.vehicle seat capacity override, effective capacity and trip count."""
        # Initial seats = 20, no override -> effective = 20
        self.assertEqual(self.vehicle.effective_capacity, 20)
        self.assertEqual(self.vehicle.trip_count, 1)

        # Set seat capacity override = 25 -> effective = 25
        self.vehicle.write({'seat_capacity_override': 25})
        self.assertEqual(self.vehicle.effective_capacity, 25)

        # Clear override (0) -> effective falls back to seats = 20
        self.vehicle.write({'seat_capacity_override': 0})
        self.assertEqual(self.vehicle.effective_capacity, 20)

        # Test smart button action
        action = self.vehicle.action_view_transport_routes()
        self.assertEqual(action['res_model'], 'logistics.transport.route')
        self.assertEqual(action['domain'], [('vehicle_id', '=', self.vehicle.id)])

    def test_route_capacity_and_occupancy_rate(self):
        """Test route capacity inheritance from vehicle and dynamic occupancy % computation."""
        # Initial capacity = 20, employee_count = 0, occupancy_rate = 0.0
        self.assertEqual(self.route_a.capacity, 20)
        self.assertEqual(self.route_a.employee_count, 0)
        self.assertEqual(self.route_a.occupancy_rate, 0.0)

        # Assign employee 1
        self.employee_1.write({
            'transport_enabled': True,
            'transport_route_id': self.route_a.id,
            'pickup_stop_id': self.stop_a1.id,
            'dropoff_stop_id': self.stop_a2.id,
        })
        self.route_a.invalidate_recordset(['employee_count', 'occupancy_rate'])
        self.assertEqual(self.route_a.employee_count, 1)
        # 1 / 20 = 5%
        self.assertEqual(self.route_a.occupancy_rate, 5.0)

        # Assign employee 2
        self.employee_2.write({
            'transport_enabled': True,
            'transport_route_id': self.route_a.id,
            'pickup_stop_id': self.stop_a1.id,
        })
        self.route_a.invalidate_recordset(['employee_count', 'occupancy_rate'])
        self.assertEqual(self.route_a.employee_count, 2)
        # 2 / 20 = 10%
        self.assertEqual(self.route_a.occupancy_rate, 10.0)

        # Override vehicle capacity to 10
        self.vehicle.write({'seat_capacity_override': 10})
        self.route_a.invalidate_recordset(['capacity', 'occupancy_rate'])
        self.assertEqual(self.route_a.capacity, 10)
        # 2 / 10 = 20%
        self.assertEqual(self.route_a.occupancy_rate, 20.0)

    def test_stop_sequence_and_order(self):
        """Test that route stops are sorted by sequence."""
        stops = self.route_a.stop_ids
        self.assertEqual(stops[0].id, self.stop_a1.id)
        self.assertEqual(stops[1].id, self.stop_a2.id)

        # Swap sequences
        self.stop_a1.write({'sequence': 30})
        self.route_a.invalidate_recordset(['stop_ids'])
        reordered = self.route_a.stop_ids
        self.assertEqual(reordered[0].id, self.stop_a2.id)
        self.assertEqual(reordered[1].id, self.stop_a1.id)

    def test_employee_stop_constraints_rejected(self):
        """Test that assigning stops from another route raises ValidationError."""
        # Attempt to set pickup stop from route B while employee is on route A
        with self.assertRaises(ValidationError):
            self.employee_1.write({
                'transport_enabled': True,
                'transport_route_id': self.route_a.id,
                'pickup_stop_id': self.stop_b1.id,  # belongs to route B
            })

        # Attempt to set drop-off stop from route B while employee is on route A
        with self.assertRaises(ValidationError):
            self.employee_2.write({
                'transport_enabled': True,
                'transport_route_id': self.route_a.id,
                'dropoff_stop_id': self.stop_b1.id,  # belongs to route B
            })

    def test_employee_stop_type_constraints(self):
        """Test that pickup stops must support pickup and drop-off stops must support drop-off."""
        drop_only_stop = self.env['logistics.transport.stop'].create({
            'name': 'Drop-off Only Station',
            'route_id': self.route_a.id,
            'address_id': self.partner_stop1.id,
            'stop_type': 'drop_off',
        })

        pickup_only_stop = self.env['logistics.transport.stop'].create({
            'name': 'Pickup Only Station',
            'route_id': self.route_a.id,
            'address_id': self.partner_stop2.id,
            'stop_type': 'pickup',
        })

        # Setting drop-off only stop as pickup stop should fail
        with self.assertRaises(ValidationError):
            self.employee_1.write({
                'transport_enabled': True,
                'transport_route_id': self.route_a.id,
                'pickup_stop_id': drop_only_stop.id,
            })

        # Setting pickup only stop as dropoff stop should fail
        with self.assertRaises(ValidationError):
            self.employee_2.write({
                'transport_enabled': True,
                'transport_route_id': self.route_a.id,
                'dropoff_stop_id': pickup_only_stop.id,
            })

    def test_onchange_route_clears_incompatible_stops(self):
        """Test that changing an employee's route clears stops that belong to the previous route."""
        emp = self.env['hr.employee'].new({
            'name': 'Temp Employee',
            'transport_enabled': True,
            'transport_route_id': self.route_a.id,
            'pickup_stop_id': self.stop_a1.id,
            'dropoff_stop_id': self.stop_a2.id,
        })
        self.assertEqual(emp.pickup_stop_id, self.stop_a1)

        # Change route to route B
        emp.transport_route_id = self.route_b
        emp._onchange_transport_route_id()

        # Incompatible stops must be cleared
        self.assertFalse(emp.pickup_stop_id)
        self.assertFalse(emp.dropoff_stop_id)

    def test_google_maps_action(self):
        """Test generation of Google Maps Directions URL with origin, destination, and waypoints."""
        action = self.route_a.action_open_google_maps()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['target'], 'new')
        url = action['url']
        self.assertIn('https://www.google.com/maps/dir/?api=1', url)
        self.assertIn('origin=', url)
        self.assertIn('destination=', url)
        self.assertIn('waypoints=', url)

    def test_stop_google_maps_action(self):
        """Test generation of Google Maps Search URL for a single stop."""
        action = self.stop_a1.action_open_google_maps()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['target'], 'new')
        self.assertIn('https://www.google.com/maps/search/?api=1', action['url'])

    def test_stops_map_action(self):
        """Test action to open route stops in map view."""
        action = self.route_a.action_view_stops_map()
        self.assertEqual(action['res_model'], 'logistics.transport.stop')
        self.assertEqual(action['view_mode'], 'map,list,form')
        self.assertEqual(action['domain'], [('route_id', '=', self.route_a.id)])

    def test_multi_company_isolation(self):
        """Test multi-company record rule prevents cross-company data leakage."""
        # Create route in Company B
        route_comp_b = self.env['logistics.transport.route'].with_company(self.company_b).create({
            'name': 'Company B Exclusive Route',
            'company_id': self.company_b.id,
        })
        stop_comp_b = self.env['logistics.transport.stop'].with_company(self.company_b).create({
            'name': 'Company B Stop',
            'route_id': route_comp_b.id,
            'address_id': self.partner_stop1.id,
        })

        # User in Company A searching routes should NOT find Company B's route
        routes_user_a = self.env['logistics.transport.route'].with_user(self.user_transport_user).search([
            ('id', '=', route_comp_b.id)
        ])
        self.assertFalse(routes_user_a)

        # User in Company A searching stops should NOT find Company B's stop
        stops_user_a = self.env['logistics.transport.stop'].with_user(self.user_transport_user).search([
            ('id', '=', stop_comp_b.id)
        ])
        self.assertFalse(stops_user_a)

        # User in Company B CAN find Company B's route
        routes_user_b = self.env['logistics.transport.route'].with_user(self.user_company_b).search([
            ('id', '=', route_comp_b.id)
        ])
        self.assertEqual(routes_user_b.id, route_comp_b.id)

    def test_rbac_user_delete_blocked_manager_allowed(self):
        """Test RBAC: User cannot delete routes or stops, Manager can."""
        # Test route deletion blocked for normal user
        with self.assertRaises(AccessError):
            self.route_b.with_user(self.user_transport_user).unlink()

        # Test stop deletion blocked for normal user
        with self.assertRaises(AccessError):
            self.stop_b1.with_user(self.user_transport_user).unlink()

        # Manager can delete stop and route
        self.stop_b1.with_user(self.user_transport_manager).unlink()
        self.assertFalse(self.stop_b1.exists())

        self.route_b.with_user(self.user_transport_manager).unlink()
        self.assertFalse(self.route_b.exists())

    def test_schedule_creation_and_computed_name(self):
        """Test valid schedule creation, computed name, and days display."""
        schedule = self.env['logistics.transport.schedule'].create({
            'route_id': self.route_a.id,
            'direction': 'pickup',
            'departure_time': 7.5,   # 07:30
            'arrival_time': 8.75,   # 08:45
            'monday': True,
            'tuesday': True,
            'wednesday': True,
            'thursday': True,
            'friday': True,
            'saturday': False,
            'sunday': False,
        })
        self.assertTrue(schedule.id)
        self.assertIn('07:30', schedule.name)
        self.assertIn('08:45', schedule.name)
        self.assertEqual(schedule.days_display, 'Mon - Fri')
        self.assertEqual(self.route_a.schedule_count, 1)

    def test_schedule_arrival_time_must_be_after_departure(self):
        """Test constraint: arrival time must be strictly after departure time."""
        # Equal times
        with self.assertRaises(ValidationError):
            self.env['logistics.transport.schedule'].create({
                'route_id': self.route_a.id,
                'departure_time': 9.0,
                'arrival_time': 9.0,
                'monday': True,
            })

        # Arrival before departure
        with self.assertRaises(ValidationError):
            self.env['logistics.transport.schedule'].create({
                'route_id': self.route_a.id,
                'departure_time': 10.0,
                'arrival_time': 8.0,
                'monday': True,
            })

    def test_schedule_at_least_one_weekday_selected(self):
        """Test constraint: at least one weekday must be checked."""
        with self.assertRaises(ValidationError):
            self.env['logistics.transport.schedule'].create({
                'route_id': self.route_a.id,
                'departure_time': 8.0,
                'arrival_time': 9.0,
                'monday': False,
                'tuesday': False,
                'wednesday': False,
                'thursday': False,
                'friday': False,
                'saturday': False,
                'sunday': False,
            })

    def test_schedule_weekday_running_check(self):
        """Test helper to check if a schedule runs on a given day (0=Mon, 6=Sun)."""
        schedule = self.env['logistics.transport.schedule'].create({
            'route_id': self.route_a.id,
            'departure_time': 8.0,
            'arrival_time': 9.0,
            'monday': True,
            'tuesday': False,
            'wednesday': True,
            'thursday': False,
            'friday': True,
            'saturday': False,
            'sunday': False,
        })
        self.assertTrue(schedule.is_running_on_weekday(0))   # Monday
        self.assertFalse(schedule.is_running_on_weekday(1))  # Tuesday
        self.assertTrue(schedule.is_running_on_weekday(2))   # Wednesday
        self.assertFalse(schedule.is_running_on_weekday(3))  # Thursday
        self.assertTrue(schedule.is_running_on_weekday(4))   # Friday
        self.assertFalse(schedule.is_running_on_weekday(5))  # Saturday
        self.assertFalse(schedule.is_running_on_weekday(6))  # Sunday

    def test_trip_creation_and_sequence(self):
        """Test trip creation generates sequential reference starting with TRP/."""
        trip = self.env['logistics.transport.trip'].create({
            'route_id': self.route_a.id,
            'vehicle_id': self.vehicle.id,
            'direction': 'pickup',
            'planned_departure_time': 8.0,
            'planned_arrival_time': 9.0,
        })
        self.assertTrue(trip.name.startswith('TRP/'))
        self.assertEqual(trip.state, 'draft')
        self.assertEqual(self.route_a.trip_count, 1)

    def test_trip_workflow_timestamps(self):
        """Test Draft -> Planned -> In Progress (departure ts) -> Completed (arrival ts)."""
        trip = self.env['logistics.transport.trip'].create({
            'route_id': self.route_a.id,
            'vehicle_id': self.vehicle.id,
            'direction': 'pickup',
        })
        self.assertFalse(trip.actual_departure_datetime)
        self.assertFalse(trip.actual_arrival_datetime)

        # Plan
        trip.action_plan()
        self.assertEqual(trip.state, 'planned')

        # Start -> In Progress with timestamp
        trip.action_start()
        self.assertEqual(trip.state, 'in_progress')
        self.assertTrue(trip.actual_departure_datetime)
        self.assertFalse(trip.actual_arrival_datetime)

        # Complete -> Completed with timestamp
        trip.action_complete()
        self.assertEqual(trip.state, 'completed')
        self.assertTrue(trip.actual_arrival_datetime)

        # Cannot cancel completed trip
        with self.assertRaises(UserError):
            trip.action_cancel()

    def test_trip_passenger_boarding_and_drop_flow(self):
        """Test passenger attendance flow: expected -> boarded (ts) -> dropped (ts)."""
        trip = self.env['logistics.transport.trip'].create({
            'route_id': self.route_a.id,
            'vehicle_id': self.vehicle.id,
        })
        passenger = self.env['logistics.transport.trip.passenger'].create({
            'trip_id': trip.id,
            'employee_id': self.employee_1.id,
            'pickup_stop_id': self.stop_a1.id,
            'dropoff_stop_id': self.stop_a2.id,
        })
        self.assertEqual(passenger.status, 'expected')
        self.assertFalse(passenger.boarding_time)
        self.assertFalse(passenger.drop_time)

        # Board passenger
        passenger.action_board()
        self.assertEqual(passenger.status, 'boarded')
        self.assertTrue(passenger.boarding_time)

        # Drop passenger
        passenger.action_drop()
        self.assertEqual(passenger.status, 'dropped')
        self.assertTrue(passenger.drop_time)

    def test_trip_passenger_stop_constraint_and_unique_employee(self):
        """Test constraints: stop belongs to route and duplicate employee rejected."""
        trip = self.env['logistics.transport.trip'].create({
            'route_id': self.route_a.id,
            'vehicle_id': self.vehicle.id,
        })
        # Adding stop from Route B to Route A trip must be rejected
        with self.assertRaises(ValidationError):
            self.env['logistics.transport.trip.passenger'].create({
                'trip_id': trip.id,
                'employee_id': self.employee_1.id,
                'pickup_stop_id': self.stop_b1.id,
            })

        # Add valid passenger
        self.env['logistics.transport.trip.passenger'].create({
            'trip_id': trip.id,
            'employee_id': self.employee_1.id,
            'pickup_stop_id': self.stop_a1.id,
        })

        # Duplicate employee on same trip must raise ValidationError
        with self.assertRaises(ValidationError):
            self.env['logistics.transport.trip.passenger'].create({
                'trip_id': trip.id,
                'employee_id': self.employee_1.id,
                'pickup_stop_id': self.stop_a2.id,
            })

    def test_trip_capacity_and_occupancy_metrics(self):
        """Test capacity, occupancy rate %, and over capacity flag."""
        # Vehicle has 20 seats standard, override to 2
        self.vehicle.seat_capacity_override = 2
        trip = self.env['logistics.transport.trip'].create({
            'route_id': self.route_a.id,
            'vehicle_id': self.vehicle.id,
        })
        self.assertEqual(trip.capacity, 2)
        self.assertEqual(trip.passenger_count, 0)
        self.assertEqual(trip.free_seats, 2)
        self.assertEqual(trip.occupancy_rate, 0.0)
        self.assertFalse(trip.is_over_capacity)

        # Add 1 passenger -> 50%
        self.env['logistics.transport.trip.passenger'].create({
            'trip_id': trip.id,
            'employee_id': self.employee_1.id,
        })
        self.assertEqual(trip.passenger_count, 1)
        self.assertEqual(trip.free_seats, 1)
        self.assertEqual(trip.occupancy_rate, 50.0)
        self.assertFalse(trip.is_over_capacity)

        # Add 2nd passenger -> 100%
        self.env['logistics.transport.trip.passenger'].create({
            'trip_id': trip.id,
            'employee_id': self.employee_2.id,
        })
        self.assertEqual(trip.passenger_count, 2)
        self.assertEqual(trip.free_seats, 0)
        self.assertEqual(trip.occupancy_rate, 100.0)
        self.assertFalse(trip.is_over_capacity)

        # Add 3rd passenger -> 150%, over capacity!
        employee_3 = self.env['hr.employee'].create({'name': 'Charlie Tech'})
        self.env['logistics.transport.trip.passenger'].create({
            'trip_id': trip.id,
            'employee_id': employee_3.id,
        })
        self.assertEqual(trip.passenger_count, 3)
        self.assertEqual(trip.free_seats, 0)
        self.assertEqual(trip.occupancy_rate, 150.0)
        self.assertTrue(trip.is_over_capacity)

    def test_wizard_generate_trips_and_idempotency(self):
        """Test wizard generates trips on active weekday and running twice produces zero duplicates."""
        target_date = date(2026, 11, 9)  # Monday
        self.assertEqual(target_date.weekday(), 0)

        # Create Monday schedule for Route A
        schedule_mon = self.env['logistics.transport.schedule'].create({
            'route_id': self.route_a.id,
            'direction': 'pickup',
            'departure_time': 8.0,
            'arrival_time': 9.0,
            'monday': True,
            'tuesday': False,
            'wednesday': False,
            'thursday': False,
            'friday': False,
            'saturday': False,
            'sunday': False,
        })

        # Assign employee_1 to Route A with transport enabled
        self.employee_1.write({
            'transport_enabled': True,
            'transport_route_id': self.route_a.id,
            'pickup_stop_id': self.stop_a1.id,
            'transport_direction': 'pickup',
        })

        # Run wizard 1st time
        wizard = self.env['logistics.transport.generate.trips.wizard'].create({
            'date': target_date,
            'route_ids': [(6, 0, [self.route_a.id])],
            'direction': 'all',
        })
        wizard.action_generate_trips()

        trips = self.env['logistics.transport.trip'].search([
            ('date', '=', target_date),
            ('route_id', '=', self.route_a.id),
        ])
        self.assertEqual(len(trips), 1)
        trip = trips[0]
        self.assertEqual(trip.schedule_id.id, schedule_mon.id)
        self.assertEqual(trip.direction, 'pickup')
        self.assertEqual(trip.state, 'draft')

        # Check passenger was auto-assigned as expected
        self.assertEqual(len(trip.passenger_ids), 1)
        passenger = trip.passenger_ids[0]
        self.assertEqual(passenger.employee_id.id, self.employee_1.id)
        self.assertEqual(passenger.pickup_stop_id.id, self.stop_a1.id)
        self.assertEqual(passenger.status, 'expected')

        # Run wizard 2nd time (IDEMPOTENCY TEST)
        wizard_2 = self.env['logistics.transport.generate.trips.wizard'].create({
            'date': target_date,
            'route_ids': [(6, 0, [self.route_a.id])],
            'direction': 'all',
        })
        wizard_2.action_generate_trips()

        trips_after = self.env['logistics.transport.trip'].search([
            ('date', '=', target_date),
            ('route_id', '=', self.route_a.id),
        ])
        self.assertEqual(len(trips_after), 1, "Rerunning the wizard must NOT create duplicate trips.")

    def test_wizard_skips_archived_routes(self):
        """Test wizard skips archived routes during trip generation."""
        target_date = date(2026, 11, 9)  # Monday

        # Create an archived route with a schedule
        archived_route = self.env['logistics.transport.route'].create({
            'name': 'Archived Route X',
            'active': False,
            'company_id': self.company_a.id,
        })
        self.env['logistics.transport.schedule'].create({
            'route_id': archived_route.id,
            'direction': 'pickup',
            'departure_time': 7.0,
            'arrival_time': 8.0,
            'monday': True,
        })

        # Run wizard for all routes
        wizard = self.env['logistics.transport.generate.trips.wizard'].create({
            'date': target_date,
            'direction': 'all',
        })
        wizard.action_generate_trips()

        # Archived route must have 0 trips
        trips_archived = self.env['logistics.transport.trip'].search([
            ('date', '=', target_date),
            ('route_id', '=', archived_route.id),
        ])
        self.assertEqual(len(trips_archived), 0, "Archived routes must be skipped by the wizard.")

    def test_wizard_direction_filtering(self):
        """Test wizard filters schedules by specified direction."""
        target_date = date(2026, 11, 9)  # Monday

        route_c = self.env['logistics.transport.route'].create({
            'name': 'Route C Dual',
            'company_id': self.company_a.id,
        })
        # Pickup schedule
        self.env['logistics.transport.schedule'].create({
            'route_id': route_c.id,
            'direction': 'pickup',
            'departure_time': 8.0,
            'arrival_time': 9.0,
            'monday': True,
        })
        # Drop-off schedule
        self.env['logistics.transport.schedule'].create({
            'route_id': route_c.id,
            'direction': 'drop_off',
            'departure_time': 17.0,
            'arrival_time': 18.0,
            'monday': True,
        })

        # Run wizard with direction='drop_off' only
        wizard = self.env['logistics.transport.generate.trips.wizard'].create({
            'date': target_date,
            'route_ids': [(6, 0, [route_c.id])],
            'direction': 'drop_off',
        })
        wizard.action_generate_trips()

        trips = self.env['logistics.transport.trip'].search([
            ('date', '=', target_date),
            ('route_id', '=', route_c.id),
        ])
        self.assertEqual(len(trips), 1)
        self.assertEqual(trips.direction, 'drop_off')

    def test_vehicle_request_creation_and_date_validation(self):
        """Test vehicle request sequence, workflow, and date constraint."""
        req = self.env['logistics.transport.vehicle.request'].create({
            'employee_id': self.employee_1.id,
            'date_from': '2026-11-10 09:00:00',
            'date_to': '2026-11-10 12:00:00',
            'purpose': 'Factory inspection visit',
            'vehicle_id': self.vehicle.id,
        })
        self.assertTrue(req.name.startswith('VRQ/'))
        self.assertEqual(req.state, 'draft')

        # Invalid date: date_to <= date_from
        with self.assertRaises(ValidationError):
            self.env['logistics.transport.vehicle.request'].create({
                'employee_id': self.employee_1.id,
                'date_from': '2026-11-10 12:00:00',
                'date_to': '2026-11-10 09:00:00',
                'purpose': 'Invalid timing trip',
            })

    def test_vehicle_request_approval_rbac_and_self_approval_block(self):
        """Test non-managers cannot approve and managers cannot approve their own requests."""
        # Link user_transport_user to employee_1
        self.employee_1.user_id = self.user_transport_user

        # Create request by normal user
        req_user = self.env['logistics.transport.vehicle.request'].with_user(self.user_transport_user).create({
            'employee_id': self.employee_1.id,
            'date_from': '2026-11-10 09:00:00',
            'date_to': '2026-11-10 12:00:00',
            'purpose': 'Client office delivery',
            'vehicle_id': self.vehicle.id,
        })
        req_user.action_submit()
        self.assertEqual(req_user.state, 'submitted')

        # Non-manager attempts approval -> AccessError
        with self.assertRaises(AccessError):
            req_user.with_user(self.user_transport_user).action_approve()

        # Manager approves user's request -> Success
        req_user.with_user(self.user_transport_manager).action_approve()
        self.assertEqual(req_user.state, 'approved')
        self.assertEqual(req_user.approver_id, self.user_transport_manager)
        self.assertTrue(req_user.approval_date)

        # Manager creates their own request
        employee_mgr = self.env['hr.employee'].create({
            'name': 'Manager Employee',
            'user_id': self.user_transport_manager.id,
        })
        req_mgr = self.env['logistics.transport.vehicle.request'].with_user(self.user_transport_manager).create({
            'employee_id': employee_mgr.id,
            'date_from': '2026-11-11 09:00:00',
            'date_to': '2026-11-11 12:00:00',
            'purpose': 'Executive meeting',
            'vehicle_id': self.vehicle.id,
        })
        req_mgr.action_submit()

        # Manager attempts to self-approve -> ValidationError
        with self.assertRaises(ValidationError):
            req_mgr.with_user(self.user_transport_manager).action_approve()

    def test_vehicle_request_overlap_prevention(self):
        """Test that same vehicle cannot have overlapping approved/assigned bookings."""
        # Request 1: 09:00 - 13:00 (Approved)
        req1 = self.env['logistics.transport.vehicle.request'].create({
            'employee_id': self.employee_1.id,
            'date_from': '2026-11-12 09:00:00',
            'date_to': '2026-11-12 13:00:00',
            'purpose': 'Trip 1',
            'vehicle_id': self.vehicle.id,
        })
        req1.action_submit()
        req1.with_user(self.user_transport_manager).action_approve()
        self.assertEqual(req1.state, 'approved')

        # Request 2: 12:00 - 15:00 (Overlaps with 09:00-13:00 for same vehicle)
        req2 = self.env['logistics.transport.vehicle.request'].create({
            'employee_id': self.employee_2.id,
            'date_from': '2026-11-12 12:00:00',
            'date_to': '2026-11-12 15:00:00',
            'purpose': 'Trip 2 Overlapping',
            'vehicle_id': self.vehicle.id,
        })
        req2.action_submit()

        # Approving req2 must raise ValidationError due to conflict
        with self.assertRaises(ValidationError):
            req2.with_user(self.user_transport_manager).action_approve()

        # Request 3: 14:00 - 17:00 (Non-overlapping for same vehicle)
        req3 = self.env['logistics.transport.vehicle.request'].create({
            'employee_id': self.employee_2.id,
            'date_from': '2026-11-12 14:00:00',
            'date_to': '2026-11-12 17:00:00',
            'purpose': 'Trip 3 After first trip',
            'vehicle_id': self.vehicle.id,
        })
        req3.action_submit()
        req3.with_user(self.user_transport_manager).action_approve()
        self.assertEqual(req3.state, 'approved')

    def test_vehicle_request_delete_locks(self):
        """Test cannot delete approved, assigned, or done requests."""
        req = self.env['logistics.transport.vehicle.request'].create({
            'employee_id': self.employee_1.id,
            'date_from': '2026-11-13 09:00:00',
            'date_to': '2026-11-13 12:00:00',
            'purpose': 'Delete lock test',
            'vehicle_id': self.vehicle.id,
        })
        req.action_submit()
        req.with_user(self.user_transport_manager).action_approve()

        # Attempt to delete approved request -> UserError
        with self.assertRaises(UserError):
            req.unlink()

        # Assign vehicle -> Assigned state
        req.action_assign()
        with self.assertRaises(UserError):
            req.unlink()

        # Complete -> Done state
        req.action_done()
        with self.assertRaises(UserError):
            req.unlink()

    def test_driver_partner_creation_and_trip_count(self):
        """Test driver partner fields, trip count computation, and trip action."""
        driver = self.env['res.partner'].create({
            'name': 'Test Driver Ali',
            'is_driver': True,
            'driver_license_number': 'LIC-12345',
            'driver_license_type': 'psv',
            'driver_license_expiry': '2028-12-31',
        })
        self.assertTrue(driver.is_driver)
        self.assertEqual(driver.driver_license_number, 'LIC-12345')
        self.assertEqual(driver.trip_count, 0)

        # Create a trip with this driver
        trip = self.env['logistics.transport.trip'].create({
            'date': date.today(),
            'route_id': self.route_a.id,
            'driver_id': driver.id,
            'vehicle_id': self.vehicle.id,
        })
        driver._compute_trip_count()
        self.assertEqual(driver.trip_count, 1)

        # Action view driver trips
        action = driver.action_view_driver_trips()
        self.assertEqual(action['res_model'], 'logistics.transport.trip')
        self.assertIn(('driver_id', '=', driver.id), action['domain'])

    def test_driver_domain_filtering(self):
        """Test that only partners marked as is_driver match driver search domain."""
        non_driver = self.env['res.partner'].create({
            'name': 'Regular Customer',
            'is_driver': False,
        })
        driver = self.env['res.partner'].create({
            'name': 'Dedicated Driver',
            'is_driver': True,
        })

        driver_partners = self.env['res.partner'].search([('is_driver', '=', True)])
        self.assertIn(driver, driver_partners)
        self.assertNotIn(non_driver, driver_partners)





