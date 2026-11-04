from odoo import models, fields, api


class CustomClearanceRevisionWizard(models.TransientModel):
    _name = 'custom.clearance.revision'
    _description = 'Clearance Revision Wizard'

    clearance_id = fields.Many2one('custom.clearance', string='Customs Clearance', required=True)
    reason = fields.Text(string='Reason', required=True)
    note = fields.Text(string='Note')

    def action_create_revision(self):
        self.ensure_one()
        rev_count = len(self.clearance_id.revision_ids) + 1
        clearance_name = self.clearance_id.name or f"CLR/{self.clearance_id.id}"
        rev_name = f"REV/{clearance_name}/{rev_count:02d}"

        self.env['clearance.revision'].create({
            'name': rev_name,
            'clearance_id': self.clearance_id.id,
            'reason': self.reason,
            'note': self.note,
        })
        return {'type': 'ir.actions.act_window_close'}
