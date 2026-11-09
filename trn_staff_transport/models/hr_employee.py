from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    transport_enabled = fields.Boolean(
        string='Transport Enabled',
        default=False,
        tracking=True,
        help='Indicates if this employee uses company staff transportation',
    )
    transport_route_id = fields.Many2one(
        'logistics.transport.route',
        string='Transport Route',
        tracking=True,
        index=True,
    )
    pickup_stop_id = fields.Many2one(
        'logistics.transport.stop',
        string='Pickup Stop',
        tracking=True,
        domain="[('route_id', '=', transport_route_id), ('stop_type', 'in', ('pickup', 'both'))]",
    )
    dropoff_stop_id = fields.Many2one(
        'logistics.transport.stop',
        string='Drop off',
        tracking=True,
        domain="[('route_id', '=', transport_route_id), ('stop_type', 'in', ('drop_off', 'both'))]",
    )
    transport_direction = fields.Selection([
        ('pickup', 'Pickup'),
        ('drop_off', 'Drop off'),
        ('both', 'Both (Pickup & Drop off)'),
    ], string='Direction', default='both', tracking=True)

    transport_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        related='transport_route_id.vehicle_id',
        readonly=True,
    )
    transport_driver_id = fields.Many2one(
        'res.partner',
        string='Driver',
        related='transport_route_id.driver_id',
        readonly=True,
    )

    @api.constrains('transport_enabled', 'transport_route_id', 'pickup_stop_id', 'dropoff_stop_id', 'transport_direction')
    def _check_transport_route_and_stops(self):
        for employee in self:
            if not employee.transport_enabled:
                continue

            if employee.pickup_stop_id:
                if not employee.transport_route_id:
                    raise ValidationError(_("Employee '%s' cannot have a pickup stop without an assigned route.", employee.name))
                if employee.pickup_stop_id.route_id != employee.transport_route_id:
                    raise ValidationError(_(
                        "Pickup stop '%(stop)s' does not belong to the assigned route '%(route)s' for employee '%(emp)s'.",
                        stop=employee.pickup_stop_id.name,
                        route=employee.transport_route_id.name,
                        emp=employee.name,
                    ))
                if employee.pickup_stop_id.stop_type not in ('pickup', 'both'):
                    raise ValidationError(_(
                        "Stop '%(stop)s' is not configured as a pickup stop.",
                        stop=employee.pickup_stop_id.name,
                    ))

            if employee.dropoff_stop_id:
                if not employee.transport_route_id:
                    raise ValidationError(_("Employee '%s' cannot have a drop-off stop without an assigned route.", employee.name))
                if employee.dropoff_stop_id.route_id != employee.transport_route_id:
                    raise ValidationError(_(
                        "Drop-off stop '%(stop)s' does not belong to the assigned route '%(route)s' for employee '%(emp)s'.",
                        stop=employee.dropoff_stop_id.name,
                        route=employee.transport_route_id.name,
                        emp=employee.name,
                    ))
                if employee.dropoff_stop_id.stop_type not in ('drop_off', 'both'):
                    raise ValidationError(_(
                        "Stop '%(stop)s' is not configured as a drop-off stop.",
                        stop=employee.dropoff_stop_id.name,
                    ))

    @api.onchange('transport_route_id')
    def _onchange_transport_route_id(self):
        """Changing an employee's route clears stops that no longer fit."""
        if self.pickup_stop_id and self.pickup_stop_id.route_id != self.transport_route_id:
            self.pickup_stop_id = False
        if self.dropoff_stop_id and self.dropoff_stop_id.route_id != self.transport_route_id:
            self.dropoff_stop_id = False

    @api.onchange('transport_enabled')
    def _onchange_transport_enabled(self):
        if not self.transport_enabled:
            self.transport_route_id = False
            self.pickup_stop_id = False
            self.dropoff_stop_id = False

    @api.model
    def _get_public_fields(self):
        fields_list = super()._get_public_fields()
        return fields_list + [
            'transport_enabled',
            'transport_route_id',
            'pickup_stop_id',
            'dropoff_stop_id',
            'transport_direction',
            'transport_vehicle_id',
            'transport_driver_id',
        ]

    @api.onchange('transport_direction')
    def _onchange_transport_direction(self):
        if self.transport_direction == 'pickup':
            self.dropoff_stop_id = False
        elif self.transport_direction == 'drop_off':
            self.pickup_stop_id = False
