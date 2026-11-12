from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LogisticsTransportGenerateTripsWizard(models.TransientModel):
    _name = 'logistics.transport.generate.trips.wizard'
    _description = 'Generate Daily Transport Trips Wizard'

    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        help='Date for which trips should be generated.',
    )
    route_ids = fields.Many2many(
        'logistics.transport.route',
        'transport_gen_trips_route_rel',
        'wizard_id',
        'route_id',
        string='Routes',
        domain="[('active', '=', True)]",
        help='Select specific routes or leave empty to process all active routes.',
    )
    direction = fields.Selection([
        ('all', 'All'),
        ('pickup', 'Pickup'),
        ('drop_off', 'Drop-off'),
    ], string='Direction', default='all', required=True)

    def action_generate_trips(self):
        self.ensure_one()
        target_date = self.date
        target_weekday = target_date.weekday()  # 0=Monday, 6=Sunday

        # Select routes (skip archived routes)
        if self.route_ids:
            routes = self.route_ids.filtered(lambda r: r.active)
        else:
            routes = self.env['logistics.transport.route'].search([('active', '=', True)])

        if not routes:
            raise UserError(_("No active routes found to generate trips for."))

        created_trips = self.env['logistics.transport.trip']

        for route in routes:
            # Active schedules matching weekday and direction
            schedules = route.schedule_ids.filtered(
                lambda s: s.active and s.is_running_on_weekday(target_weekday)
            )
            if self.direction != 'all':
                schedules = schedules.filtered(lambda s: s.direction == self.direction)

            for schedule in schedules:
                # Idempotency check: check if trip already exists for this date, route, and schedule
                existing_trip = self.env['logistics.transport.trip'].search([
                    ('date', '=', target_date),
                    ('route_id', '=', route.id),
                    ('schedule_id', '=', schedule.id),
                ], limit=1)

                if existing_trip:
                    # Skip duplicate generation
                    continue

                # Determine vehicle and driver (schedule override or route fallback)
                vehicle = schedule.vehicle_id or route.vehicle_id
                driver = schedule.driver_id or route.driver_id or (vehicle.driver_id if vehicle else False)

                # Create trip
                trip = self.env['logistics.transport.trip'].create({
                    'date': target_date,
                    'route_id': route.id,
                    'schedule_id': schedule.id,
                    'direction': schedule.direction,
                    'vehicle_id': vehicle.id if vehicle else False,
                    'driver_id': driver.id if driver else False,
                    'planned_departure_time': schedule.departure_time,
                    'planned_arrival_time': schedule.arrival_time,
                    'state': 'draft',
                    'company_id': route.company_id.id,
                })
                created_trips |= trip

                # Find assigned route employees with transport enabled
                assigned_employees = route.employee_ids.filtered(lambda e: e.transport_enabled)

                # Direction compatibility filter
                if schedule.direction == 'pickup':
                    eligible_employees = assigned_employees.filtered(
                        lambda e: not e.transport_direction or e.transport_direction in ('pickup', 'both')
                    )
                elif schedule.direction == 'drop_off':
                    eligible_employees = assigned_employees.filtered(
                        lambda e: not e.transport_direction or e.transport_direction in ('drop_off', 'both')
                    )
                else:
                    eligible_employees = assigned_employees

                # Add eligible employees as expected passengers
                passenger_vals = []
                for emp in eligible_employees:
                    pickup_stop = emp.pickup_stop_id if emp.pickup_stop_id and emp.pickup_stop_id.route_id == route else False
                    dropoff_stop = emp.dropoff_stop_id if emp.dropoff_stop_id and emp.dropoff_stop_id.route_id == route else False
                    passenger_vals.append({
                        'trip_id': trip.id,
                        'employee_id': emp.id,
                        'pickup_stop_id': pickup_stop.id if pickup_stop else False,
                        'dropoff_stop_id': dropoff_stop.id if dropoff_stop else False,
                        'status': 'expected',
                    })

                if passenger_vals:
                    self.env['logistics.transport.trip.passenger'].create(passenger_vals)

        # Return action to view trips for the target date
        action = self.env['ir.actions.actions']._for_xml_id('trn_staff_transport.action_logistics_transport_trip')
        action['domain'] = [('date', '=', target_date)]
        action['context'] = {'search_default_filter_today': 0, 'default_date': target_date}
        return action
