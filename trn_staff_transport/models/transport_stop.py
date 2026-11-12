from urllib.parse import quote_plus

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LogisticsTransportStop(models.Model):
    _name = 'logistics.transport.stop'
    _description = 'Staff Transport Stop'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True)
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
        string='Address',
        required=True,
    )
    planned_time = fields.Float(
        string='Planned Time',
        help='Planned arrival/departure time in hours (e.g. 8.5 for 08:30)',
    )
    stop_type = fields.Selection([
        ('pickup', 'Pickup'),
        ('drop_off', 'Drop-off'),
        ('both', 'Both'),
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

    def action_open_google_maps(self):
        """Opens stop location in Google Maps."""
        self.ensure_one()
        query = ""
        partner = self.address_id
        if partner:
            if partner.partner_latitude and partner.partner_longitude:
                query = f"{partner.partner_latitude},{partner.partner_longitude}"
            else:
                components = [
                    partner.street,
                    partner.street2,
                    partner.city,
                    partner.zip,
                    partner.country_id.name if partner.country_id else "",
                ]
                valid = [c.strip() for c in components if c and c.strip()]
                if valid:
                    query = ", ".join(valid)
                else:
                    query = partner.name or ""
        if not query and self.name:
            query = self.name

        if not query:
            raise UserError(_("Please define an address or name for this stop to view it in Google Maps."))

        url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
