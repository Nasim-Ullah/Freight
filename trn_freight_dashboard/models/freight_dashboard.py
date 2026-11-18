from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class FreightDashboard(models.AbstractModel):
    _name = 'freight.dashboard'
    _description = 'Freight Operations Dashboard Aggregator'

    @api.model
    def get_dashboard_data(self):
        """
        Returns all aggregated figures required by the OWL Freight Dashboard:
        - state_counts: Count of freight orders per state (draft, submitted, confirmed, invoiced, done, cancel).
        - kpis: Active orders metrics (active_orders, total_orders, revenue, expense, margin, margin_pct).
        - monthly_trend: Revenue and expense per month for the last 6 months.
        - currency: Active company currency symbol and position.
        """
        Shipping = self.env['freight.shipping']
        company = self.env.company
        currency = company.currency_id

        # 1. Orders per State (Server-side aggregation via _read_group)
        state_labels = dict(Shipping._fields['state'].selection)
        state_counts = {state: 0 for state in state_labels}

        counts_by_state = Shipping._read_group(
            domain=[],
            groupby=['state'],
            aggregates=['__count'],
        )
        for state, count in counts_by_state:
            if state in state_counts:
                state_counts[state] = count

        # 2. Active Orders KPIs (revenue, expense, margin)
        # Active orders = non-cancelled orders
        active_domain = [('state', '!=', 'cancel')]
        active_aggregates = Shipping._read_group(
            domain=active_domain,
            groupby=[],
            aggregates=['total:sum', 'services_total:sum', '__count'],
        )

        if active_aggregates and active_aggregates[0]:
            revenue = active_aggregates[0][0] or 0.0
            expense = active_aggregates[0][1] or 0.0
            active_orders_count = active_aggregates[0][2] or 0
        else:
            revenue = 0.0
            expense = 0.0
            active_orders_count = 0

        margin = revenue - expense
        margin_pct = round((margin / revenue * 100.0), 2) if revenue > 0 else 0.0

        # 3. Monthly Revenue vs Expense for the Last 6 Months
        today = date.today()
        month_keys = []
        for i in range(5, -1, -1):
            m_date = today - relativedelta(months=i)
            month_keys.append({
                'year': m_date.year,
                'month': m_date.month,
                'key': m_date.strftime('%Y-%m'),
                'label': m_date.strftime('%b %Y'),
                'short_label': m_date.strftime('%b'),
                'revenue': 0.0,
                'expense': 0.0,
            })

        month_map = {m['key']: m for m in month_keys}

        start_date = (today - relativedelta(months=5)).replace(day=1)
        monthly_domain = [
            ('state', '!=', 'cancel'),
            ('order_date', '>=', fields.Datetime.to_string(start_date)),
        ]

        monthly_groups = Shipping._read_group(
            domain=monthly_domain,
            groupby=['order_date:month'],
            aggregates=['total:sum', 'services_total:sum'],
        )

        for dt_val, m_revenue, m_expense in monthly_groups:
            if dt_val:
                key = dt_val.strftime('%Y-%m')
                if key in month_map:
                    month_map[key]['revenue'] = round(m_revenue or 0.0, 2)
                    month_map[key]['expense'] = round(m_expense or 0.0, 2)

        # 4. Formatted response payload
        return {
            'state_counts': state_counts,
            'state_labels': state_labels,
            'kpis': {
                'active_orders': active_orders_count,
                'total_orders': sum(state_counts.values()),
                'revenue': round(revenue, 2),
                'expense': round(expense, 2),
                'margin': round(margin, 2),
                'margin_pct': margin_pct,
            },
            'monthly_trend': {
                'labels': [m['short_label'] for m in month_keys],
                'full_labels': [m['label'] for m in month_keys],
                'revenues': [m['revenue'] for m in month_keys],
                'expenses': [m['expense'] for m in month_keys],
            },
            'currency': {
                'symbol': currency.symbol or '$',
                'position': currency.position or 'after',
            },
        }
