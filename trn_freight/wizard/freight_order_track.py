from odoo import models, fields, api


class FreightOrderTrack(models.TransientModel):
    _name = 'freight.order.track'
    _description = 'Freight Order Tracking Wizard'

    shipping_id = fields.Many2one('freight.shipping', string='Freight Order', required=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now, required=True)
    source_port_id = fields.Many2one('freight.port', string='Source Port', required=True)
    destination_port_id = fields.Many2one('freight.port', string='Destination Port', required=True)
    transport = fields.Selection([
        ('land', 'Land'),
        ('air', 'Air'),
        ('water', 'Water')
    ], string='Transport Type', default='land', required=True)
    received_delivered = fields.Selection([
        ('received', 'Received'),
        ('delivered', 'Delivered')
    ], string='Received / Delivered', required=True)

    def action_add_tracking(self):
        self.ensure_one()
        self.env['freight.track'].create({
            'shipping_id': self.shipping_id.id,
            'date': self.date,
            'source_port_id': self.source_port_id.id,
            'destination_port_id': self.destination_port_id.id,
            'transport': self.transport,
            'received_delivered': self.received_delivered,
        })

        order = self.shipping_id
        partners = (order.shipper_id | order.consignee_id | order.agent_id).ids
        status_label = dict(self._fields['received_delivered'].selection).get(self.received_delivered, self.received_delivered)
        transport_label = dict(self._fields['transport'].selection).get(self.transport, self.transport)
        body = (
            f"Tracking Update: {status_label} at {self.source_port_id.name} to {self.destination_port_id.name} "
            f"via {transport_label} on {self.date}."
        )
        order.message_post(
            body=body,
            partner_ids=partners,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        return {'type': 'ir.actions.act_window_close'}
