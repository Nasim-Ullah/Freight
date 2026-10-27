from odoo import models, fields

class FreightContainer(models.Model):
    _name =  'freight.container'
    _description = 'Freight Container'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    size = fields.Float(string='Size', digits=(6,2))
    size_unit = fields.Selection([('ft', 'Feet'),('m', 'Meters')], string='Size Unit', default='ft')
    weight = fields.Float(string='Weight', digits=(6,2))
    weight_unit = fields.Selection([('kg','kilograms(KG)'),('lbs', 'Pounds(LBS)')], string='Weight Unit', default='kg')
    volume = fields.Float(string='Volume', digits=(6,2))
    volume_unit = fields.Selection([('cbm','Cubic Meters(CBM)'), ('cbft','Cubic Feet(CBFT)')], string='Volume Unit', default='cbm')
    state = fields.Selection([('available', 'Available'), ('reserved', 'Reserved')], string='status', default='available', tracking=True, required=True)
    active= fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self:self.env.company)





