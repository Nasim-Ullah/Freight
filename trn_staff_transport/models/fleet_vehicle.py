from odoo import api, fields, models, _


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    seat_capacity_override = fields.Integer(
        string='Seat Capacity Override',
        default=0,
        help='Override the vehicle seating capacity specifically for staff transport. Set 0 to use standard seats.',
    )
    effective_capacity = fields.Integer(
        string='Effective Capacity',
        compute='_compute_effective_capacity',
        store=True,
        readonly=True,
        help='Effective passenger capacity: override capacity if set (>0), otherwise vehicle seats.',
    )
    trip_count = fields.Integer(
        string='Trips Count',
        compute='_compute_trip_count',
        help='Total transport routes assigned to this vehicle',
    )

    @api.depends('seat_capacity_override', 'seats')
    def _compute_effective_capacity(self):
        for vehicle in self:
            if vehicle.seat_capacity_override > 0:
                vehicle.effective_capacity = vehicle.seat_capacity_override
            else:
                vehicle.effective_capacity = vehicle.seats or 0

    def _compute_trip_count(self):
        route_data = self.env['logistics.transport.route']._read_group(
            [('vehicle_id', 'in', self.ids)],
            groupby=['vehicle_id'],
            aggregates=['__count'],
        )
        count_map = {vehicle.id: count for vehicle, count in route_data}
        for vehicle in self:
            vehicle.trip_count = count_map.get(vehicle.id, 0)

    def action_view_transport_routes(self):
        self.ensure_one()
        return {
            'name': _('Transport Routes - %s', self.display_name),
            'type': 'ir.actions.act_window',
            'res_model': 'logistics.transport.route',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {
                'default_vehicle_id': self.id,
            },
        }
