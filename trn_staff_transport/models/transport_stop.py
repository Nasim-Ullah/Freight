from odoo import api, fields, models


class LogisticsTransportStop(models.Model):
    _name = 'logistics.transport.stop'
    _description = 'Staff Transport Stop'
    _order = 'sequence, id'

    name = fields.Char(string='Stop Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10, index=True)
    route_id = fields.Many2one(
        'logistics.transport.route',
        string='Route',
        required=True,
        ondelete='cascade',
        index=True,
    )
    address_id = fields.Many2one(
        'res.partner',
        string='Stop Address',
        required=True,
    )
    planned_time = fields.Float(
        string='Planned Time',
        help='Planned arrival/departure time in hours (e.g. 8.5 for 08:30)',
    )
    stop_type = fields.Selection([
        ('pickup', 'Pickup'),
        ('drop_off', 'Drop-off'),
        ('both', 'Both (Pickup & Drop-off)'),
    ], string='Stop Type', default='both', required=True)

    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='route_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
