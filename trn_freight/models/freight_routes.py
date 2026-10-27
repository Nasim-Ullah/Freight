from odoo import models, fields

class FreightRoutes(models.Model):
    _name  = 'freight.routes'
    _description = 'Freight Routes'
    _order = 'name'

    name = fields.Char(string='Route Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    land_price = fields.Float(string='Land Price', digits=(6,2))
    air_price = fields.Float(string='Air Price', digits=(6,2))
    water_price = fields.Float(string='Water Price', digits=(6,2))
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
