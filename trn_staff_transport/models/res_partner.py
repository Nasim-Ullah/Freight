# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_driver = fields.Boolean(
        string='Is Driver',
        default=False,
        index=True,
        tracking=True,
        help='Check this box if this contact is a driver.',
    )
    driver_license_number = fields.Char(
        string='License Number',
        tracking=True,
        help='Driving license number of the driver.',
    )
    driver_license_type = fields.Selection([
        ('motorcycle', 'Motorcycle'),
        ('ltv', 'LTV (Light Transport Vehicle)'),
        ('htv', 'HTV (Heavy Transport Vehicle)'),
        ('psv', 'PSV (Public Service Vehicle)'),
        ('commercial', 'Commercial'),
        ('other', 'Other'),
    ], string='License Type', default='ltv', tracking=True)
    driver_license_expiry = fields.Date(
        string='License Expiry Date',
        tracking=True,
    )
    trip_count = fields.Integer(
        string='Trips Count',
        compute='_compute_trip_count',
    )

    def _compute_trip_count(self):
        trip_data = self.env['logistics.transport.trip']._read_group(
            [('driver_id', 'in', self.ids)],
            groupby=['driver_id'],
            aggregates=['__count'],
        )
        count_map = {driver.id: count for driver, count in trip_data}
        for partner in self:
            partner.trip_count = count_map.get(partner.id, 0)

    def action_view_driver_trips(self):
        self.ensure_one()
        return {
            'name': 'Trips',
            'type': 'ir.actions.act_window',
            'res_model': 'logistics.transport.trip',
            'view_mode': 'list,form',
            'domain': [('driver_id', '=', self.id)],
            'context': {'default_driver_id': self.id},
        }
