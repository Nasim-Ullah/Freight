# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError


class LogisticsTransportVehicleRequest(models.Model):
    _name = 'logistics.transport.vehicle.request'
    _description = 'Employee Vehicle Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(
        string='Request Number',
        required=True,
        copy=False,
        readonly=True,
        default='/',
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Requester',
        required=True,
        default=lambda self: self.env.user.employee_id,
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        readonly=True,
    )
    date_from = fields.Datetime(
        string='From',
        required=True,
        tracking=True,
    )
    date_to = fields.Datetime(
        string='To',
        required=True,
        tracking=True,
    )
    purpose = fields.Text(
        string='Purpose / Destination',
        required=True,
        tracking=True,
    )

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        tracking=True,
    )
    driver_id = fields.Many2one(
        'res.partner',
        string='Driver',
        tracking=True,
    )

    approver_id = fields.Many2one(
        'res.users',
        string='Approver',
        readonly=True,
        copy=False,
        tracking=True,
    )
    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True,
        copy=False,
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        tracking=True,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('assigned', 'Assigned'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', required=True, tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('logistics.transport.vehicle.request') or '/'
        return super().create(vals_list)

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id and self.vehicle_id.driver_id and not self.driver_id:
            self.driver_id = self.vehicle_id.driver_id

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for req in self:
            if req.date_from and req.date_to and req.date_to <= req.date_from:
                raise ValidationError(_("'To' datetime must be strictly after 'From' datetime."))

    @api.constrains('vehicle_id', 'date_from', 'date_to', 'state')
    def _check_vehicle_overlap(self):
        """Ensure no vehicle has overlapping approved or assigned requests."""
        for req in self:
            if req.vehicle_id and req.state in ('approved', 'assigned'):
                domain = [
                    ('id', '!=', req.id),
                    ('vehicle_id', '=', req.vehicle_id.id),
                    ('state', 'in', ('approved', 'assigned')),
                    ('date_from', '<', req.date_to),
                    ('date_to', '>', req.date_from),
                ]
                overlapping = self.search(domain, limit=1)
                if overlapping:
                    raise ValidationError(_(
                        "Vehicle %(vehicle)s is already reserved for request %(req)s "
                        "from %(start)s to %(end)s. Overlapping bookings are not allowed.",
                        vehicle=req.vehicle_id.name,
                        req=overlapping.name,
                        start=fields.Datetime.to_string(overlapping.date_from),
                        end=fields.Datetime.to_string(overlapping.date_to),
                    ))

    def unlink(self):
        for req in self:
            if req.state in ('approved', 'assigned', 'done'):
                raise UserError(_(
                    "You cannot delete vehicle request %(name)s while in '%(state)s' state.",
                    name=req.name,
                    state=dict(req._fields['state'].selection).get(req.state, req.state),
                ))
        return super().unlink()

    # Workflow Actions
    def action_submit(self):
        """Submit draft request for approval."""
        for req in self:
            if req.state != 'draft':
                raise UserError(_("Only draft requests can be submitted."))
            req.state = 'submitted'

    def action_approve(self):
        """Approve vehicle request:
        - Must be transport manager
        - Cannot approve own request
        """
        if not self.env.user.has_group('trn_staff_transport.group_transport_manager'):
            raise AccessError(_("Only transport managers are authorized to approve vehicle requests."))

        for req in self:
            if req.state != 'submitted':
                raise UserError(_("Only submitted requests can be approved."))
            if req.user_id == self.env.user or (req.sudo().employee_id and req.sudo().employee_id.user_id == self.env.user):
                raise ValidationError(_("You cannot approve your own vehicle request."))
            req.write({
                'state': 'approved',
                'approver_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })

    def action_reject(self):
        """Reject vehicle request:
        - Must be transport manager
        - Cannot reject own request
        """
        if not self.env.user.has_group('trn_staff_transport.group_transport_manager'):
            raise AccessError(_("Only transport managers are authorized to reject vehicle requests."))

        for req in self:
            if req.state != 'submitted':
                raise UserError(_("Only submitted requests can be rejected."))
            if req.user_id == self.env.user or (req.sudo().employee_id and req.sudo().employee_id.user_id == self.env.user):
                raise ValidationError(_("You cannot reject your own vehicle request."))
            req.write({
                'state': 'rejected',
                'approver_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })

    def action_assign(self):
        """Assign vehicle and move to Assigned state."""
        for req in self:
            if req.state != 'approved':
                raise UserError(_("Only approved requests can be assigned."))
            if not req.vehicle_id:
                raise UserError(_("Please select a vehicle before assigning."))
            req.state = 'assigned'

    def action_done(self):
        """Mark assigned request as Done/Completed."""
        for req in self:
            if req.state != 'assigned':
                raise UserError(_("Only assigned requests can be completed."))
            req.state = 'done'

    def action_cancel(self):
        """Cancel request."""
        for req in self:
            if req.state == 'done':
                raise UserError(_("Completed requests cannot be cancelled."))
            req.state = 'cancelled'

    def action_reset_draft(self):
        """Reset cancelled or rejected request to draft."""
        for req in self:
            if req.state not in ('cancelled', 'rejected'):
                raise UserError(_("Only cancelled or rejected requests can be reset to draft."))
            req.write({
                'state': 'draft',
                'approver_id': False,
                'approval_date': False,
            })
