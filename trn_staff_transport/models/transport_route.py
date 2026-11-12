from urllib.parse import quote_plus
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LogisticsTransportRoute(models.Model):
    _name = 'logistics.transport.route'
    _description = 'Staff Transport Route'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, id'

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True)
    code = fields.Char(string='Code', copy=False, required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    direction = fields.Selection([
        ('pickup', 'Pickup'),
        ('drop_off', 'Drop-off'),
        ('both', 'Both'),
    ], string='Direction', default='both', required=True, tracking=True)

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', tracking=True)
    driver_id = fields.Many2one(
        'res.partner',
        string='Driver',
        tracking=True,
        compute='_compute_driver_id',
        store=True,
        readonly=False,
        domain="[('is_driver', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    start_address_id = fields.Many2one('res.partner', string='Start Address', tracking=True)
    end_address_id = fields.Many2one('res.partner', string='End Address', tracking=True)

    stop_ids = fields.One2many('logistics.transport.stop', 'route_id', string='Stops')
    schedule_ids = fields.One2many('logistics.transport.schedule', 'route_id', string='Schedules')
    trip_ids = fields.One2many('logistics.transport.trip', 'route_id', string='Trips')
    schedules = fields.Char(
        string='Schedules Summary',
        help='Schedule details, e.g., Mon-Fri 08:00 AM / 05:00 PM',
        tracking=True,
    )
    employee_ids = fields.One2many(
        'hr.employee',
        'transport_route_id',
        string='Assigned Employees',
    )

    stop_count = fields.Integer(string='Stops Count', compute='_compute_stop_count', store=True)
    schedule_count = fields.Integer(string='Schedules Count', compute='_compute_schedule_count', store=True)
    trip_count = fields.Integer(string='Trips Count', compute='_compute_trip_count', store=True)
    employee_count = fields.Integer(string='Employee Count', compute='_compute_employee_count', store=True)

    capacity = fields.Integer(
        string='Capacity',
        compute='_compute_capacity',
        store=True,
        tracking=True,
        help='Effective seating capacity inherited from assigned vehicle',
    )
    occupancy_rate = fields.Float(
        string='Occupancy %',
        compute='_compute_occupancy_rate',
        store=True,
        digits=(5, 2),
        aggregator='avg',
    )
    distance = fields.Float(
        string='Planned Distance (km)',
        tracking=True,
        help='Planned distance in kilometers for this route',
    )
    notes = fields.Html(string='Notes')

    @api.depends('vehicle_id', 'vehicle_id.driver_id')
    def _compute_driver_id(self):
        for route in self:
            if route.vehicle_id and route.vehicle_id.driver_id:
                route.driver_id = route.vehicle_id.driver_id
            elif not route.driver_id:
                route.driver_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                name = vals.get('name') or 'RT'
                words = [w for w in name.split() if w]
                vals['code'] = ''.join([w[0].upper() for w in words])[:6] if words else 'ROUTE'
        return super().create(vals_list)

    @api.depends('stop_ids')
    def _compute_stop_count(self):
        for route in self:
            route.stop_count = len(route.stop_ids)

    @api.depends('schedule_ids')
    def _compute_schedule_count(self):
        for route in self:
            route.schedule_count = len(route.schedule_ids)

    @api.depends('trip_ids')
    def _compute_trip_count(self):
        for route in self:
            route.trip_count = len(route.trip_ids)

    @api.depends('employee_ids', 'employee_ids.transport_enabled', 'employee_ids.transport_route_id')
    def _compute_employee_count(self):
        for route in self:
            active_assigned = route.employee_ids.filtered(lambda e: e.transport_enabled)
            route.employee_count = len(active_assigned)

    @api.depends('vehicle_id', 'vehicle_id.effective_capacity')
    def _compute_capacity(self):
        for route in self:
            route.capacity = route.vehicle_id.effective_capacity if route.vehicle_id else 0

    @api.depends('employee_count', 'capacity')
    def _compute_occupancy_rate(self):
        for route in self:
            if route.capacity > 0:
                route.occupancy_rate = round((route.employee_count / route.capacity) * 100.0, 2)
            else:
                route.occupancy_rate = 0.0

    def action_view_stops(self):
        self.ensure_one()
        return {
            'name': _('Stops - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'logistics.transport.stop',
            'view_mode': 'list,map,form',
            'domain': [('route_id', '=', self.id)],
            'context': {'default_route_id': self.id},
        }

    def action_view_schedules(self):
        self.ensure_one()
        return {
            'name': _('Schedules - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'logistics.transport.schedule',
            'view_mode': 'list,form',
            'domain': [('route_id', '=', self.id)],
            'context': {'default_route_id': self.id},
        }

    def action_view_trips(self):
        self.ensure_one()
        return {
            'name': _('Trips - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'logistics.transport.trip',
            'view_mode': 'list,form',
            'domain': [('route_id', '=', self.id)],
            'context': {'default_route_id': self.id},
        }

    def action_view_stops_map(self):
        """Opens stops in a map view."""
        self.ensure_one()
        return {
            'name': _('Stops on Map - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'logistics.transport.stop',
            'view_mode': 'map,list,form',
            'domain': [('route_id', '=', self.id)],
            'context': {'default_route_id': self.id},
        }

    def action_generate_trips(self):
        """Open the trip generator wizard for this route."""
        self.ensure_one()
        return {
            'name': _('Generate Trips'),
            'type': 'ir.actions.act_window',
            'res_model': 'logistics.transport.generate.trips.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_route_ids': [self.id],
                'default_direction': self.direction if self.direction in ('pickup', 'drop_off') else 'all',
            },
        }

    def action_view_employees(self):
        self.ensure_one()
        return {
            'name': _('Assigned Employees - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('transport_route_id', '=', self.id), ('transport_enabled', '=', True)],
            'context': {
                'default_transport_route_id': self.id,
                'default_transport_enabled': True,
            },
        }

    def _format_partner_query(self, partner):
        if not partner:
            return ""
        if partner.partner_latitude and partner.partner_longitude:
            return f"{partner.partner_latitude},{partner.partner_longitude}"
        components = [partner.street, partner.street2, partner.city, partner.zip, partner.country_id.name]
        valid = [c.strip() for c in components if c and c.strip()]
        if valid:
            return ", ".join(valid)
        return partner.name or ""

    def action_open_google_maps(self):
        """Opens route in Google Maps Directions with waypoints."""
        self.ensure_one()
        origin = self._format_partner_query(self.start_address_id)
        destination = self._format_partner_query(self.end_address_id)

        stops_queries = [
            self._format_partner_query(stop.address_id)
            for stop in self.stop_ids
            if stop.address_id
        ]
        stops_queries = [q for q in stops_queries if q]

        # If origin not explicitly set, use the first stop
        if not origin and stops_queries:
            origin = stops_queries.pop(0)

        # If destination not explicitly set, use the last stop
        if not destination and stops_queries:
            destination = stops_queries.pop(-1)

        if not origin and not destination:
            raise UserError(_("Please define a start address, end address, or stops with valid addresses to view route in Google Maps."))

        base_url = "https://www.google.com/maps/dir/?api=1"
        params = ["travelmode=driving"]

        if origin:
            params.append(f"origin={quote_plus(origin)}")
        if destination:
            params.append(f"destination={quote_plus(destination)}")
        if stops_queries:
            waypoints_str = "|".join(stops_queries)
            params.append(f"waypoints={quote_plus(waypoints_str)}")

        url = f"{base_url}&{'&'.join(params)}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
