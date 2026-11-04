from odoo import models, fields, api
# from odoo.exceptions import ValidationError
from odoo.exceptions import ValidationError, UserError
try:
    from odoo import Command
except ImportError:
    from odoo.orm.commands import Command


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
    clearance_ids = fields.One2many('custom.clearance', 'shipping_id', string='Customs Clearances')
    invoice_ids = fields.Many2many('account.move', string='Invoices', copy=False)

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
            partners = (record.shipper_id | record.consignee_id | record.agent_id).ids
            if partners:
                record.message_post(
                    body=f"Freight Order {record.name} has been submitted.",
                    partner_ids=partners,
                )

    def action_confirm(self):
        for record in self:
            if not record.clearance_ids:
                raise UserError("A customs clearance is required before confirming the freight order.")
            if any(clearance.state == 'draft' for clearance in record.clearance_ids):
                raise UserError("Cannot confirm order: Customs clearance is still in Draft state. Please confirm the clearance first.")
            record.state = 'confirmed'
            containers = record.cargo_line_ids.mapped('container_id')
            if containers:
                containers.write({'state': 'reserved'})
            partners = (record.shipper_id | record.consignee_id | record.agent_id).ids
            if partners:
                record.message_post(
                    body=f"Freight Order {record.name} has been confirmed.",
                    partner_ids=partners,
                )

    def action_invoice(self):
        return self.action_create_invoice()

    def action_done(self):
        for record in self:
            record.state = 'done'
            containers = record.cargo_line_ids.mapped('container_id')
            if containers:
                containers.write({'state': 'available'})
            partners = (record.shipper_id | record.consignee_id | record.agent_id).ids
            if partners:
                record.message_post(
                    body=f"Freight Order {record.name} has been marked as Done.",
                    partner_ids=partners,
                )

    def action_cancel(self):
        for record in self:
            record.state = 'cancelled'
            containers = record.cargo_line_ids.mapped('container_id')
            if containers:
                containers.write({'state': 'available'})

    def action_tracking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Track Order',
            'res_model': 'freight.order.track',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_shipping_id': self.id,
                'default_transport': self.transport or 'land',
                'default_source_port_id': self.loading_port_id.id if self.loading_port_id else False,
                'default_destination_port_id': self.discharge_port_id.id if self.discharge_port_id else False,
            },
        }

    def action_draft(self):
        for record in self:
            record.state = 'draft'
            containers = record.cargo_line_ids.mapped('container_id')
            if containers:
                containers.write({'state': 'available'})

    # Smart button counters
    clearance_count = fields.Integer(string='Clearance Count', compute='_compute_clearance_count')
    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_count')

    @api.depends('clearance_ids')
    def _compute_clearance_count(self):
        for record in self:
            record.clearance_count = len(record.clearance_ids)

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = len(record.invoice_ids)

    def action_create_invoice(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError("Invoices can only be created when the order is Confirmed.")
        if not self.shipper_id:
            raise UserError("A Shipper partner is required to create a customer invoice.")

        invoice_lines = []
        # Cargo lines
        for line in self.cargo_line_ids:
            qty = line.weight if line.billing_on == 'weight' else line.volume
            desc = f"Cargo: {line.product_id.name or 'Goods'} ({line.billing_on.capitalize() if line.billing_on else ''})"
            invoice_lines.append(Command.create({
                'name': desc,
                'quantity': qty,
                'price_unit': line.unit_price,
                'tax_ids': [Command.clear()],
            }))

        # Route lines
        for line in self.route_line_ids:
            desc = f"Route: {line.source_port_id.name or ''} to {line.destination_port_id.name or ''}"
            invoice_lines.append(Command.create({
                'name': desc,
                'quantity': 1.0,
                'price_unit': line.sale_price,
                'tax_ids': [Command.clear()],
            }))

        # Service lines
        for line in self.service_line_ids:
            desc = f"Service: {line.service_id.name or ''}"
            invoice_lines.append(Command.create({
                'name': desc,
                'quantity': line.quantity,
                'price_unit': line.sale,
                'tax_ids': [Command.clear()],
            }))

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.shipper_id.id,
            'invoice_origin': self.name,
            'company_id': self.company_id.id,
            'invoice_line_ids': invoice_lines,
        })

        self.invoice_ids = [Command.link(invoice.id)]
        self.state = 'invoiced'

        return {
            'type': 'ir.actions.act_window',
            'name': 'Customer Invoice',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }

    def action_view_invoice(self):
        self.ensure_one()
        if len(self.invoice_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Customer Invoice',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.invoice_ids[0].id,
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Customer Invoices',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
        }

    def action_custom_clearance(self):
        self.ensure_one()
        # If the clearance already exists, the button opens it
        if self.clearance_ids:
            clearance = self.clearance_ids[0]
            return {
                'type': 'ir.actions.act_window',
                'name': 'Customs Clearance',
                'res_model': 'custom.clearance',
                'view_mode': 'form',
                'res_id': clearance.id,
                'target': 'current',
            }
        # Otherwise, create the clearance with order's ports, agent and date
        clearance_date = self.order_date.date() if self.order_date else fields.Date.context_today(self)
        clearance = self.env['custom.clearance'].create({
            'shipping_id': self.id,
            'loading_port_id': self.loading_port_id.id,
            'discharge_port_id': self.discharge_port_id.id,
            'agent_id': self.agent_id.id,
            'date': clearance_date,
            'company_id': self.company_id.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Customs Clearance',
            'res_model': 'custom.clearance',
            'view_mode': 'form',
            'res_id': clearance.id,
            'target': 'current',
        }

    def action_view_clearance(self):
        self.ensure_one()
        if len(self.clearance_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Customs Clearance',
                'res_model': 'custom.clearance',
                'view_mode': 'form',
                'res_id': self.clearance_ids[0].id,
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Customs Clearances',
            'res_model': 'custom.clearance',
            'view_mode': 'list,form',
            'domain': [('shipping_id', '=', self.id)],
            'context': {'default_shipping_id': self.id},
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
            record.total = record.total + record.routes_total + record.services_total

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('freight.shipping') or 'New'
        return super().create(vals_list)

    def unlink(self):
        for record in self:
            if record.state in ('confirmed', 'done'):
                raise UserError("Deleting a confirmed order is refused.")
            if any(clearance.state in ('confirmed', 'done') for clearance in record.clearance_ids):
                raise UserError("Deleting an order with a confirmed clearance is refused.")
            draft_clearances = record.clearance_ids.filtered(lambda c: c.state == 'draft')
            draft_clearances.unlink()
        return super().unlink()

    @api.constrains('loading_port_id', 'discharge_port_id', 'transport')
    def _check_port_transport(self):
        for order in self:
            if not order.transport:
                continue
            for port in [order.loading_port_id, order.discharge_port_id]:
                if not port:
                    continue
                if order.transport == 'land' and not port.is_land:
                    raise ValidationError(f"The port '{port.name}' does not support the selected transport type '{order.transport}'.")
                elif order.transport == 'air' and not port.is_air:
                    raise ValidationError(f"The port '{port.name}' does not support the selected transport type '{order.transport}'.")
                elif order.transport == 'water' and not port.is_water:
                    raise ValidationError(f"The port '{port.name}' does not support the selected transport type '{order.transport}'.")


class FreightCargoLine(models.Model):
    _name = 'freight.cargo.line'
    _description = 'Freight Cargo Line'

    shipping_id = fields.Many2one('freight.shipping', string='Freight Order', ondelete='cascade')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='shipping_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
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
            # here you can compute pricing model or unit price according to container
            line.unit_price = 0.0

    @api.depends('weight', 'volume', 'unit_price', 'billing_on')
    def _compute_total_price(self):
        for line in self:
            if line.billing_on == 'weight':
                line.total_price = line.unit_price * line.weight
            else:
                line.total_price = line.unit_price * line.volume

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('shipping_id'):
                shipping = self.env['freight.shipping'].browse(vals['shipping_id'])
                if shipping.state in ('confirmed', 'invoiced', 'done'):
                    raise UserError("Cargo lines cannot be added once the order is Confirmed or later.")
        return super().create(vals_list)

    def write(self, vals):
        for line in self:
            if line.shipping_id and line.shipping_id.state in ('confirmed', 'invoiced', 'done'):
                raise UserError("Cargo lines cannot be changed once the order is Confirmed or later.")
        return super().write(vals)

    def unlink(self):
        for line in self:
            if line.shipping_id and line.shipping_id.state in ('confirmed', 'invoiced', 'done'):
                raise UserError("Cargo lines cannot be removed once the order is Confirmed or later.")
        return super().unlink()


class FreightRouteLine(models.Model):
    _name = 'freight.route.line'
    _description = 'Freight Route Line'

    shipping_id = fields.Many2one('freight.shipping', string='Freight Order', ondelete='cascade')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='shipping_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
    route_id = fields.Many2one('freight.routes', string='Route', required=True)
    source_port_id = fields.Many2one('freight.port', string='Source Location')
    destination_port_id = fields.Many2one('freight.port', string='Destination Location')
    transport = fields.Selection([
        ('land', 'Land'),
        ('air', 'Air'),
        ('water', 'Water'),
    ], string='Transport', required=True)

    sale_price = fields.Float(string='Sale', digits=(6, 2), compute='_compute_route_sale', store=True, readonly=False)

    @api.depends('route_id', 'transport')
    def _compute_route_sale(self):
        for line in self:
            if line.route_id and line.transport:
                if line.transport == 'land':
                    line.sale_price = line.route_id.land_price
                elif line.transport == 'air':
                    line.sale_price = line.route_id.air_price
                elif line.transport == 'water':
                    line.sale_price = line.route_id.water_price
            elif not line.sale_price:
                line.sale_price = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('shipping_id'):
                shipping = self.env['freight.shipping'].browse(vals['shipping_id'])
                if shipping.state in ('invoiced', 'done'):
                    raise UserError("Route lines cannot be added once the order is Invoiced or later.")
        return super().create(vals_list)

    def write(self, vals):
        for line in self:
            if line.shipping_id and line.shipping_id.state in ('invoiced', 'done'):
                raise UserError("Route lines cannot be changed once the order is Invoiced or later.")
        return super().write(vals)

    def unlink(self):
        for line in self:
            if line.shipping_id and line.shipping_id.state in ('invoiced', 'done'):
                raise UserError("Route lines cannot be removed once the order is Invoiced or later.")
        return super().unlink()


class FreightOrderService(models.Model):
    _name = 'freight.order.service'
    _description = 'Freight Order Service Line'

    shipping_id = fields.Many2one('freight.shipping', string='Freight Order', ondelete='cascade')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='shipping_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
    service_id = fields.Many2one('freight.service', string='Service', required=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    quantity = fields.Float(string='Quantity', default=0.0)
    sale = fields.Float(string='Sale')
    total_sale = fields.Float(string='Total Sale', compute='_compute_total_sale', store=True)

    @api.depends('quantity', 'sale')
    def _compute_total_sale(self):
        for line in self:
            line.total_sale = line.quantity * line.sale

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('shipping_id'):
                shipping = self.env['freight.shipping'].browse(vals['shipping_id'])
                if shipping.state in ('invoiced', 'done'):
                    raise UserError("Service lines cannot be added once the order is Invoiced or later.")
        return super().create(vals_list)

    def write(self, vals):
        for line in self:
            if line.shipping_id and line.shipping_id.state in ('invoiced', 'done'):
                raise UserError("Service lines cannot be changed once the order is Invoiced or later.")
        return super().write(vals)

    def unlink(self):
        for line in self:
            if line.shipping_id and line.shipping_id.state in ('invoiced', 'done'):
                raise UserError("Service lines cannot be removed once the order is Invoiced or later.")
        return super().unlink()


class FreightTrack(models.Model):
    _name = 'freight.track'
    _description = 'Freight Tracking Line'

    shipping_id = fields.Many2one('freight.shipping', string='Freight Order', ondelete='cascade')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='shipping_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
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
