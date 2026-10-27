from odoo import models, fields

class FreightContainer(models.Model):
    _name =  'freight.container'
    _description = 'Freight Container'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)

    size = fields.Float(string='Size', digits=(6,2))
    size_unit = fields.Many2one('uom.uom', string= 'Size UOM')

    weight = fields.Float(string='Weight', digits=(6,2))
    weight_unit = fields.Many2one('uom.uom', string='weight UOM')

    volume = fields.Float(string='Volume', digits=(6,2))
    volume_unit = fields.Many2one('uom.uom', string='Volume UOM')

    active = fields.Boolean(string='Active', default=True)
    state = fields.Selection([('available', 'Available'), ('reserved', 'Reserved')], string='status', default='available', tracking=True, required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self:self.env.company)
