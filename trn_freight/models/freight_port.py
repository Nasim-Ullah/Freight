from odoo import models, fields

class FreightPorts(models.Model):
    _name = 'freight.port'
    _description = 'Freight Port'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True, size=6)
    country_id = fields.Many2one('res.country', string='Country', required=True)
    state_id = fields.Many2one('res.country.state', string='State', domain="[('country_id','=',country_id)]")
    active = fields.Boolean(string='Active', default=True)

    #Transport Flags
    is_land = fields.Boolean(string='Land', default=False)
    is_air = fields.Boolean(string='Air', default=False)
    is_water = fields.Boolean(string='Water', default=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)