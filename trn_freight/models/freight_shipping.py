from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FreightShipping(models.Model):
    _name = 'freight.shipping'
    _description = 'Freight Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='New', required=True, copy=False, readonly=True, default='New')

    shipper_id = fields.Many2one('res.partner', string='Shipper')
    consignee_id = fields.Many2one('res.partner', string='Consignee')
    agent_id = fields.Many2one('res.partner', string='Agent')
    shipping_type = fields.Selection([
        ('import', 'Import'),
        ('export', 'Export'),
    ], string='Import/Export')
    order_date = fields.Datetime(string='Date', default=fields.Datetime.now)
    expected_date = fields.Datetime(string='Expected Date')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # child models
    cargo_line_ids = fields.One2many('freight.cargo.line', 'shipping_id', string='Cargo Lines')
    route_line_ids = fields.One2many('freight.route.line', 'shipping_id', string='Route Lines')
    service_line_ids = fields.One2many('freight.order.service', 'shipping_id', string='Service Lines')
    track_line_ids = fields.One2many('freight.track', 'shipping_id', string='Tracking Lines')

    transport = fields.Selection([
        ('land', 'Land'),
        ('air', 'Air'),
        ('water', 'Water'),
    ], string='Transport')

    land_type = fields.Selection([
        ('ftl', 'FTL'),
        ('ft', 'FT')
    ], string='Land Shipping')

    water_type = fields.Selection([
        ('fcl', 'FCl'),
        ('lcl', 'LCL'),
    ], string='Water Shipping')

    # Ports
    loading_port_id = fields.Many2one('freight.port', string='Loading Port')
    discharge_port_id = fields.Many2one('freight.port', string='Discharging Port')

    # work flow state and action buttons
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('confirmed', 'Confirmed'),
        ('invoiced', 'Invoiced'),
        ('cancel', 'Cancelled'),
        ('done', 'Done'),
    ], string='Status', default='draft', required=True)

    def action_submit(self):
        for record in self:
            record.state = 'submitted'

    def action_confirm(self):
        for record in self:
            record.state = 'confirmed'

    def action_invoice(self):
        for record in self:
            record.state = 'invoiced'

    def action_done(self):
        for record in self:
            record.state = 'done'

    def action_cancel(self):
        for record in self:
            record.state = 'cancelled'

    def action_tracking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tracking',
            'res_model': 'freight.track',
            'view_mode': 'list,form',
            'domain': [('shipping_id', '=', self.id)],
            'context': {'default_shipping_id': self.id},
        }

    def action_draft(self):
        for record in self:
            record.state = 'draft'

    # Smart button counters
    clearance_count = fields.Integer(string='Clearance Count', compute='_compute_clearance_count')
    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_count')

    def _compute_clearance_count(self):
        for record in self:
            record.clearance_count = 0

    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = 0

    def action_custom_clearance(self):
        self.ensure_one()
            # For Custom clearance action logic or opening view
        return {
            'type': 'ir.actions.act_window',
            'name': 'Custom Clearance',
            'res_model': 'freight.shipping',
            'view_mode': 'list,form',
            'domain': [('id', '=', self.id)],
        }

    # Footer
    total_volume = fields.Float(string='Total Volume', compute='_compute_cargo_totals', store=True)
    total_weight = fields.Float(string='Total Weight', compute='_compute_cargo_totals', store=True)
    total = fields.Float(string='Total', compute='_compute_cargo_totals', store=True)

    # routes total
    routes_total = fields.Float(string='Total Sale', compute='_compute_cargo_totals', store=True)

    # service total
    services_total = fields.Float(string='Services Total', compute='_compute_cargo_totals', store=True)

    @api.depends(
        'cargo_line_ids.volume',
        'cargo_line_ids.weight',
        'cargo_line_ids.total_price',
        'route_line_ids.sale_price',
        'service_line_ids.total_sale',
    )
    def _compute_cargo_totals(self):
        for record in self:
            # cargo totals
            record.total_volume = sum(line.volume for line in record.cargo_line_ids)
            record.total_weight = sum(line.weight for line in record.cargo_line_ids)
            record.total = sum(line.total_price for line in record.cargo_line_ids)
            # Route lines total
            record.routes_total = sum(line.sale_price for line in record.route_line_ids) if (
                    hasattr(record, 'route_line_ids') and record.route_line_ids) else 0.0
            # Services total
            record.services_total = sum(line.total_sale for line in record.service_line_ids) if (
                    hasattr(record, 'service_line_ids') and record.service_line_ids) else 0.0

            # Grand total
            record.total = record.total + record.routes_total

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('freight.shipping') or 'New'
                return super().create(vals_list)

    @api.constrains('loading_port_id', 'discharge_port_id', 'transport')
    def _check_port_transport(self):
        for order in self:
            for port in [order.loading_port_id, order.discharge_port_id]:
                if port and hasattr(port,
                                    'transport_type') and port.transport_type and port.transport_type != order.transport:
                    raise ValidationError(
                        f"The port '{port.name}' does not support the selected transport type '{order.transport}'.")


class FreightCargoLine(models.Model):
    _name = 'freight.cargo.line'
    _description = 'Freight Cargo Line'

    shipping_id = fields.Many2one('freight.shipping', string='Freight Order', ondelete='cascade')
    container_id = fields.Many2one('freight.container', string='Container')
    product_id = fields.Many2one('product.product', string='Goods')
    billing_on = fields.Selection([
        ('weight', 'Weight'),
        ('volume', 'Volume'),
    ], string='Billing On')

    pricing = fields.Float(string='Pricing')
    weight = fields.Float(string='Weight', digits=(6, 2))
    volume = fields.Float(string='Volume', digits=(6, 2))
    unit_price = fields.Float(string='Unit Price', digits=(6, 2), compute='_compute_unit_price', store=True,
                              readonly=False)
    total_price = fields.Float(string='Total Price', digits=(6, 2), compute='_compute_total_price', store=True)

    @api.constrains('weight', 'volume')
    def _check_weight_volume(self):
        for line in self:
            if line.weight < 0 or line.volume < 0:
                raise ValidationError("Weight and Volume cannot be negative values.")

    @api.depends('container_id', 'billing_on')
    def _compute_unit_price(self):
        for line in self:
            # Yahan aap pricing model ya container ke mutabiq unit price compute kar sakte hain
            line.unit_price = 0.0

    @api.depends('weight', 'volume', 'unit_price', 'billing_on')
    def _compute_total_price(self):
        for line in self:
            if line.billing_on == 'weight':
                line.total_price = line.unit_price * line.weight
            else:
                line.total_price = line.unit_price * line.volume


class FreightRouteLine(models.Model):
    _name = 'freight.route.line'
    _description = 'Freight Route Line'

    shipping_id = fields.Many2one('freight.shipping', string='Freight Order', ondelete='cascade')
    route_id = fields.Many2one('freight.routes', string='Route', required=True)
    source_port_id = fields.Many2one('freight.port', string='Source Location')
    destination_port_id = fields.Many2one('freight.port', string='Destination Location')
    transport = fields.Selection([
        ('land', 'Land'),
        ('air', 'Air'),
        ('water', 'Water'),
    ], string='Transport', required=True)

    sale_price = fields.Float(string='Sale', digits=(6, 2), compute='_compute_route_sale', store=True)

    @api.depends('route_id', 'transport')
    def _compute_route_sale(self):
        for line in self:
            line.sale_price = 0.0


class FreightOrderService(models.Model):
    _name = 'freight.order.service'
    _description = 'Freight Order Service Line'

    shipping_id = fields.Many2one('freight.shipping', string='Freight Order', ondelete='cascade')
    service_id = fields.Many2one('freight.service', string='Service', required=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    quantity = fields.Float(string='Quantity', default=0.0)
    sale = fields.Float(string='Sale')
    total_sale = fields.Float(string='Total Sale', compute='_compute_total_sale', store=True)

    @api.depends('quantity', 'sale')
    def _compute_total_sale(self):
        for line in self:
            line.total_sale = line.quantity * line.sale


class FreightTrack(models.Model):
    _name = 'freight.track'
    _description = 'Freight Tracking Line'

    shipping_id = fields.Many2one('freight.shipping', string='Freight Order', ondelete='cascade')
    source_port_id = fields.Many2one('freight.port', string='Source Location', required=True)
    destination_port_id = fields.Many2one('freight.port', string='Destination Location', required=True)
    transport = fields.Selection([
        ('land', 'Land'),
        ('air', 'Air'),
        ('water', 'Water')
    ], string='Transport', default='land', required=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    received_delivered = fields.Selection([
        ('received', 'Received'),
        ('delivered', 'Delivered')
    ], string='Received/Delivered')
