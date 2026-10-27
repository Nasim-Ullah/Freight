from odoo import models, fields

class FreightPrice(models.Model):
    _name = 'freight.price'
    _description= 'Freight Price'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    volume_price = fields.Float(string='Volume Price', required=True, digits=(6,2))
    weight_price = fields.Float(string='Weight Price', required=True, digits=(6,2))
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)



