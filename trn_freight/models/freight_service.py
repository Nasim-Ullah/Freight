from odoo import models, fields

class FreightService(models.Model):
    _name = 'freight.service'
    _description = 'Freight Service'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    sale_price = fields.Float(string='Sale Price', digits=(6,2))
    line_ids = fields.One2many('freight.service.line', 'service_id', string='Vendor Lines')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

class FreightServiceLine(models.Model):
    _name = 'freight.service.line'
    _description = 'Freight Service Vendor Line'

    service_id = fields.Many2one('freight.service', string='Service Reference', ondelete='cascade')
    vendor_id = fields.Many2one('res.partner', string='Vendor', required=True)
    sale_price = fields.Float(string='Sale Price', digits=(6,2))
