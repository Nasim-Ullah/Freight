from odoo import models, fields, api


class CustomClearance(models.Model):
    _name = 'custom.clearance'
    _description = 'Customs Clearance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Clearance Reference', compute='_compute_name', store=True, readonly=True)
    shipping_id = fields.Many2one(
        'freight.shipping',
        string='Freight Order',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    date = fields.Date(string='Date', default=fields.Date.context_today)
    agent_id = fields.Many2one('res.partner', string='Customs Agent')
    loading_port_id = fields.Many2one('freight.port', string='Loading Port')
    discharge_port_id = fields.Many2one('freight.port', string='Discharge Port')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
    ], string='Status', default='draft', required=True)

    line_ids = fields.One2many('custom.clearance.line', 'clearance_id', string='Document Lines')
    revision_ids = fields.One2many('clearance.revision', 'clearance_id', string='Revisions')
    revision_count = fields.Integer(string='Revision Count', compute='_compute_revision_count')

    @api.depends('shipping_id', 'shipping_id.name')
    def _compute_name(self):
        for record in self:
            if record.shipping_id and record.shipping_id.name and record.shipping_id.name != 'New':
                record.name = f"CLR/{record.shipping_id.name}"
            elif record.id:
                record.name = f"CLR/{record.id}"
            else:
                record.name = "CLR/New"

    @api.depends('revision_ids')
    def _compute_revision_count(self):
        for record in self:
            record.revision_count = len(record.revision_ids)

    def action_confirm(self):
        for record in self:
            record.state = 'confirmed'

    def action_done(self):
        for record in self:
            record.state = 'done'

    def action_draft(self):
        for record in self:
            record.state = 'draft'

    def action_view_revisions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Revisions',
            'res_model': 'clearance.revision',
            'view_mode': 'list,form',
            'domain': [('clearance_id', '=', self.id)],
            'context': {'default_clearance_id': self.id},
        }

    def action_open_revision_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Revision',
            'res_model': 'custom.clearance.revision',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_clearance_id': self.id},
        }


class CustomClearanceLine(models.Model):
    _name = 'custom.clearance.line'
    _description = 'Customs Clearance Document Line'

    clearance_id = fields.Many2one(
        'custom.clearance',
        string='Customs Clearance',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(string='Document Name', required=True)
    file = fields.Binary(string='File', attachment=True, required=True)
    file_name = fields.Char(string='File Name')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='clearance_id.company_id',
        store=True,
        readonly=True,
    )


class ClearanceRevision(models.Model):
    _name = 'clearance.revision'
    _description = 'Clearance Revision'
    _order = 'id desc'

    name = fields.Char(string='Revision Name', required=True, copy=False)
    reason = fields.Text(string='Reason', required=True)
    note = fields.Text(string='Note')
    clearance_id = fields.Many2one(
        'custom.clearance',
        string='Customs Clearance',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='clearance_id.company_id',
        store=True,
        readonly=True,
    )
    date = fields.Datetime(string='Date', default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one('res.users', string='Author', default=lambda self: self.env.user, readonly=True)
