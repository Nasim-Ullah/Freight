import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class LogisticsTransportTrip(models.Model):
    _name = 'logistics.transport.trip'
    _description = 'Staff Transport Daily Trip'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, planned_departure_time desc, id desc'

    name = fields.Char(
        string='Trip Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    route_id = fields.Many2one(
        'logistics.transport.route',
        string='Route',
        required=True,
        tracking=True,
    )
    schedule_id = fields.Many2one(
        'logistics.transport.schedule',
        string='Schedule',
        tracking=True,
        domain="[('route_id', '=', route_id)]",
    )
    direction = fields.Selection([
        ('pickup', 'Pickup'),
        ('drop_off', 'Drop-off'),
    ], string='Direction', required=True, default='pickup', tracking=True)

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', tracking=True)
    driver_id = fields.Many2one(
        'res.partner',
        string='Driver',
        tracking=True,
        domain="[('is_driver', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    planned_departure_time = fields.Datetime(
        string='Planned Departure',
        help='Planned departure date and time',
        tracking=True,
    )
    planned_arrival_time = fields.Datetime(
        string='Planned Arrival',
        help='Planned arrival date and time',
        tracking=True,
    )

    actual_departure_datetime = fields.Datetime(
        string='Actual Departure Time',
        readonly=True,
        copy=False,
        tracking=True,
    )
    actual_arrival_datetime = fields.Datetime(
        string='Actual Arrival Time',
        readonly=True,
        copy=False,
        tracking=True,
    )

    passenger_ids = fields.One2many(
        'logistics.transport.trip.passenger',
        'trip_id',
        string='Passengers',
    )

    passenger_count = fields.Integer(
        string='Passenger Count',
        compute='_compute_passenger_metrics',
        store=True,
        tracking=True,
    )
    capacity = fields.Integer(
        string='Capacity',
        compute='_compute_passenger_metrics',
        store=True,
        tracking=True,
    )
    free_seats = fields.Integer(
        string='Available Seats',
        compute='_compute_passenger_metrics',
        store=True,
    )
    occupancy_rate = fields.Float(
        string='Occupancy %',
        compute='_compute_passenger_metrics',
        store=True,
        digits=(5, 2),
    )
    is_over_capacity = fields.Boolean(
        string='Over Capacity',
        compute='_compute_passenger_metrics',
        store=True,
        tracking=True,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', required=True, tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    notes = fields.Text(string='Notes')

    @classmethod
    def _convert_float_to_datetime(cls, date_val, float_val):
        """Convert 24h float time (e.g. 8.5) and date into a python datetime."""
        if float_val is False or float_val is None:
            return False
        if not isinstance(float_val, (int, float)):
            return float_val
        if not date_val:
            date_val = fields.Date.today()
        elif isinstance(date_val, str):
            date_val = fields.Date.to_date(date_val)
        hours = int(float_val)
        minutes = int(round((float_val - hours) * 60))
        if minutes >= 60:
            hours += 1
            minutes = 0
        return datetime.datetime.combine(date_val, datetime.time(min(hours, 23), min(minutes, 59)))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') in ('/', 'New', _('New')):
                vals['name'] = self.env['ir.sequence'].next_by_code('logistics.transport.trip') or '/'
            if not vals.get('direction'):
                if vals.get('route_id'):
                    route = self.env['logistics.transport.route'].browse(vals['route_id'])
                    vals['direction'] = route.direction if route.direction in ('pickup', 'drop_off') else 'pickup'
                else:
                    vals['direction'] = 'pickup'
            d = vals.get('date')
            if 'planned_departure_time' in vals and isinstance(vals['planned_departure_time'], (int, float)):
                vals['planned_departure_time'] = self._convert_float_to_datetime(d, vals['planned_departure_time'])
            if 'planned_arrival_time' in vals and isinstance(vals['planned_arrival_time'], (int, float)):
                vals['planned_arrival_time'] = self._convert_float_to_datetime(d, vals['planned_arrival_time'])
        return super().create(vals_list)

    def write(self, vals):
        if 'planned_departure_time' in vals and isinstance(vals['planned_departure_time'], (int, float)):
            d = vals.get('date') or (self[:1].date if self else False)
            vals['planned_departure_time'] = self._convert_float_to_datetime(d, vals['planned_departure_time'])
        if 'planned_arrival_time' in vals and isinstance(vals['planned_arrival_time'], (int, float)):
            d = vals.get('date') or (self[:1].date if self else False)
            vals['planned_arrival_time'] = self._convert_float_to_datetime(d, vals['planned_arrival_time'])
        return super().write(vals)

    @api.onchange('route_id')
    def _onchange_route_id(self):
        if self.route_id:
            if not self.vehicle_id:
                self.vehicle_id = self.route_id.vehicle_id
            if not self.driver_id:
                self.driver_id = self.route_id.driver_id
            if not self.direction:
                self.direction = self.route_id.direction

    @api.onchange('schedule_id', 'date')
    def _onchange_schedule_id(self):
        if self.schedule_id:
            self.direction = self.schedule_id.direction
            trip_date = self.date or fields.Date.context_today(self)
            if self.schedule_id.departure_time is not False and self.schedule_id.departure_time is not None:
                self.planned_departure_time = self._convert_float_to_datetime(trip_date, self.schedule_id.departure_time)
            if self.schedule_id.arrival_time is not False and self.schedule_id.arrival_time is not None:
                self.planned_arrival_time = self._convert_float_to_datetime(trip_date, self.schedule_id.arrival_time)
            if self.schedule_id.vehicle_id:
                self.vehicle_id = self.schedule_id.vehicle_id
            elif self.schedule_id.route_id.vehicle_id and not self.vehicle_id:
                self.vehicle_id = self.schedule_id.route_id.vehicle_id

            if self.schedule_id.driver_id:
                self.driver_id = self.schedule_id.driver_id
            elif self.schedule_id.route_id.driver_id and not self.driver_id:
                self.driver_id = self.schedule_id.route_id.driver_id

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id and self.vehicle_id.driver_id and not self.driver_id:
            self.driver_id = self.vehicle_id.driver_id

    @api.depends('passenger_ids', 'passenger_ids.status', 'vehicle_id', 'vehicle_id.effective_capacity')
    def _compute_passenger_metrics(self):
        for trip in self:
            active_passengers = trip.passenger_ids.filtered(lambda p: p.status != 'cancelled')
            p_count = len(active_passengers)
            trip.passenger_count = p_count

            cap = trip.vehicle_id.effective_capacity if trip.vehicle_id else 0
            trip.capacity = cap
            trip.free_seats = max(0, cap - p_count)
            trip.occupancy_rate = round((p_count / cap * 100.0), 2) if cap > 0 else 0.0
            trip.is_over_capacity = p_count > cap if cap > 0 else False

    # Workflow Actions
    def action_plan(self):
        """Move trip to Planned state."""
        for trip in self:
            if trip.state != 'draft':
                raise UserError(_("Only draft trips can be marked as planned."))
            trip.state = 'planned'

    def action_start(self):
        """Start the trip and record actual departure timestamp."""
        for trip in self:
            if trip.state not in ('draft', 'planned'):
                raise UserError(_("Trip can only be started from Draft or Planned state."))
            trip.write({
                'state': 'in_progress',
                'actual_departure_datetime': fields.Datetime.now(),
            })

    def action_complete(self):
        """Complete the trip and record actual arrival timestamp."""
        for trip in self:
            if trip.state != 'in_progress':
                raise UserError(_("Only trips in progress can be marked as completed."))
            trip.write({
                'state': 'completed',
                'actual_arrival_datetime': fields.Datetime.now(),
            })

    def action_cancel(self):
        """Cancel the trip."""
        for trip in self:
            if trip.state == 'completed':
                raise UserError(_("Completed trips cannot be cancelled."))
            trip.write({'state': 'cancelled'})

    def action_reset_draft(self):
        """Reset cancelled trip to Draft."""
        for trip in self:
            if trip.state != 'cancelled':
                raise UserError(_("Only cancelled trips can be reset to draft."))
            trip.write({
                'state': 'draft',
                'actual_departure_datetime': False,
                'actual_arrival_datetime': False,
            })

    def action_open_google_maps(self):
        """Open Google Maps for the trip's route."""
        self.ensure_one()
        if not self.route_id:
            raise UserError(_("Please select a route first."))
        return self.route_id.action_open_google_maps()


class LogisticsTransportTripPassenger(models.Model):
    _name = 'logistics.transport.trip.passenger'
    _description = 'Trip Passenger Attendance'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=0, index=True)
    trip_id = fields.Many2one(
        'logistics.transport.trip',
        string='Trip',
        required=True,
        ondelete='cascade',
        index=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        index=True,
    )
    pickup_stop_id = fields.Many2one(
        'logistics.transport.stop',
        string='Pickup Stop',
        domain="[('route_id', '=', parent.route_id)]",
    )
    dropoff_stop_id = fields.Many2one(
        'logistics.transport.stop',
        string='Drop-off Stop',
        domain="[('route_id', '=', parent.route_id)]",
    )

    status = fields.Selection([
        ('expected', 'Expected'),
        ('boarded', 'Boarded'),
        ('no_show', 'No Show'),
        ('dropped', 'Dropped'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='expected', required=True)

    boarding_time = fields.Datetime(string='Boarding Time', readonly=True)
    drop_time = fields.Datetime(string='Drop Time', readonly=True)
    notes = fields.Char(string='Notes')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='trip_id.company_id',
        store=True,
        index=True,
    )

    @api.constrains('trip_id', 'employee_id')
    def _check_unique_employee_per_trip(self):
        for passenger in self:
            domain = [
                ('trip_id', '=', passenger.trip_id.id),
                ('employee_id', '=', passenger.employee_id.id),
                ('id', '!=', passenger.id),
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(_(
                    "Employee %(emp)s is already registered as a passenger for this trip.",
                    emp=passenger.employee_id.name,
                ))

    @api.constrains('pickup_stop_id', 'dropoff_stop_id', 'trip_id')
    def _check_stops_belong_to_route(self):
        for passenger in self:
            if passenger.trip_id.route_id:
                route = passenger.trip_id.route_id
                if passenger.pickup_stop_id and passenger.pickup_stop_id.route_id != route:
                    raise ValidationError(_(
                        "Pickup stop '%(stop)s' does not belong to the trip's route '%(route)s'.",
                        stop=passenger.pickup_stop_id.name,
                        route=route.name,
                    ))
                if passenger.dropoff_stop_id and passenger.dropoff_stop_id.route_id != route:
                    raise ValidationError(_(
                        "Drop-off stop '%(stop)s' does not belong to the trip's route '%(route)s'.",
                        stop=passenger.dropoff_stop_id.name,
                        route=route.name,
                    ))

    def action_board(self):
        """Mark passenger as boarded and set boarding timestamp."""
        for rec in self:
            rec.write({
                'status': 'boarded',
                'boarding_time': fields.Datetime.now(),
            })

    def action_no_show(self):
        """Mark passenger as no-show."""
        for rec in self:
            rec.write({
                'status': 'no_show',
            })

    def action_drop(self):
        """Mark passenger as dropped and set drop timestamp."""
        for rec in self:
            rec.write({
                'status': 'dropped',
                'drop_time': fields.Datetime.now(),
            })

    def action_cancel(self):
        """Mark passenger as cancelled."""
        for rec in self:
            rec.write({
                'status': 'cancelled',
            })

    def action_reset(self):
        """Reset passenger to Expected status and clear timestamps."""
        for rec in self:
            rec.write({
                'status': 'expected',
                'boarding_time': False,
                'drop_time': False,
            })
