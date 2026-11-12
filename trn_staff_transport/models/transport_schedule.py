from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LogisticsTransportSchedule(models.Model):
    _name = 'logistics.transport.schedule'
    _description = 'Staff Transport Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'route_id, departure_time, id'

    name = fields.Char(
        string='Schedule Name',
        compute='_compute_name',
        store=True,
        readonly=False,
        tracking=True,
    )
    route_id = fields.Many2one(
        'logistics.transport.route',
        string='Route',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    direction = fields.Selection([
        ('pickup', 'Pickup'),
        ('drop_off', 'Drop-off'),
        ('both', 'Both (Pickup & Drop-off)'),
    ], string='Direction', required=True, default=False, tracking=True)

    # Weekdays
    monday = fields.Boolean(string='Monday', default=True)
    tuesday = fields.Boolean(string='Tuesday', default=True)
    wednesday = fields.Boolean(string='Wednesday', default=True)
    thursday = fields.Boolean(string='Thursday', default=True)
    friday = fields.Boolean(string='Friday', default=True)
    saturday = fields.Boolean(string='Saturday', default=False)
    sunday = fields.Boolean(string='Sunday', default=False)

    days_display = fields.Char(
        string='Operating Days',
        compute='_compute_days_display',
        store=True,
    )

    departure_time = fields.Float(
        string='Departure Time',
        required=True,
        default=0.0,
        help='Departure time in 24h format (e.g., 8.5 for 08:30)',
        tracking=True,
    )
    arrival_time = fields.Float(
        string='Arrival Time',
        required=True,
        default=0.0,
        help='Arrival time in 24h format (e.g., 9.5 for 09:30)',
        tracking=True,
    )

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle Override',
        tracking=True,
        help='Overrides the default route vehicle for this schedule.',
    )
    driver_id = fields.Many2one(
        'res.partner',
        string='Driver Override',
        tracking=True,
        domain="[('is_driver', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Overrides the default route driver for this schedule.',
    )

    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='route_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('direction'):
                vals['direction'] = 'pickup'
        return super().create(vals_list)

    @api.depends('route_id.name', 'direction', 'departure_time', 'arrival_time')
    def _compute_name(self):
        for rec in self:
            dep_str = self._format_float_time(rec.departure_time)
            arr_str = self._format_float_time(rec.arrival_time)
            route_name = rec.route_id.name or _('New Schedule')
            direction_label = dict(rec._fields['direction'].selection).get(rec.direction, '')
            if direction_label:
                rec.name = f"{route_name} - {direction_label} ({dep_str} - {arr_str})"
            else:
                rec.name = f"{route_name} ({dep_str} - {arr_str})"

    @api.depends('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
    def _compute_days_display(self):
        day_labels = [
            ('monday', 'Mon'),
            ('tuesday', 'Tue'),
            ('wednesday', 'Wed'),
            ('thursday', 'Thu'),
            ('friday', 'Fri'),
            ('saturday', 'Sat'),
            ('sunday', 'Sun'),
        ]
        for rec in self:
            active_days = [short for field, short in day_labels if getattr(rec, field)]
            if len(active_days) == 7:
                rec.days_display = _('Everyday')
            elif active_days == ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']:
                rec.days_display = _('Mon - Fri')
            elif active_days == ['Sat', 'Sun']:
                rec.days_display = _('Weekends')
            elif active_days:
                rec.days_display = ', '.join(active_days)
            else:
                rec.days_display = _('None')

    @api.constrains('departure_time', 'arrival_time')
    def _check_departure_arrival_times(self):
        for schedule in self:
            if schedule.departure_time < 0 or schedule.departure_time >= 24:
                raise ValidationError(_("Departure time must be between 00:00 and 23:59."))
            if schedule.arrival_time <= 0 or schedule.arrival_time > 24:
                raise ValidationError(_("Arrival time must be between 00:01 and 24:00."))
            if schedule.arrival_time <= schedule.departure_time:
                dep_str = self._format_float_time(schedule.departure_time)
                arr_str = self._format_float_time(schedule.arrival_time)
                raise ValidationError(_(
                    "Arrival time (%(arr)s) must be strictly after departure time (%(dep)s).",
                    arr=arr_str,
                    dep=dep_str,
                ))

    @api.constrains('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
    def _check_weekdays(self):
        for schedule in self:
            if not any([
                schedule.monday, schedule.tuesday, schedule.wednesday,
                schedule.thursday, schedule.friday, schedule.saturday, schedule.sunday
            ]):
                raise ValidationError(_("At least one weekday must be selected for the schedule."))

    def is_running_on_weekday(self, weekday_int):
        """Check if schedule runs on given weekday integer (0=Monday, 6=Sunday)."""
        self.ensure_one()
        mapping = {
            0: self.monday,
            1: self.tuesday,
            2: self.wednesday,
            3: self.thursday,
            4: self.friday,
            5: self.saturday,
            6: self.sunday,
        }
        return mapping.get(weekday_int, False)

    @staticmethod
    def _format_float_time(value):
        hours = int(value or 0)
        minutes = int(round(((value or 0) - hours) * 60))
        if minutes >= 60:
            hours += 1
            minutes = 0
        return f"{hours:02d}:{minutes:02d}"
