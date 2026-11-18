/** @odoo-module **/

import { loadBundle } from "@web/core/assets";
import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class FreightDashboard extends Component {
    static template = "trn_freight_dashboard.FreightDashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.canvasRef = useRef("monthlyChart");
        this.chartInstance = null;

        this.state = useState({
            loading: true,
            data: null,
            lastUpdated: null,
        });

        // Load Chart.js library bundle and initial dashboard metrics
        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadDashboardData();
        });

        // Lifecycle hook to render/update Chart when data changes
        useEffect(
            () => {
                if (this.canvasRef.el && this.state.data?.monthly_trend) {
                    this.renderChart();
                }
                return () => {
                    if (this.chartInstance) {
                        this.chartInstance.destroy();
                        this.chartInstance = null;
                    }
                };
            },
            () => [this.state.data]
        );
    }

    async loadDashboardData() {
        try {
            this.state.loading = true;
            const data = await this.orm.call("freight.dashboard", "get_dashboard_data", []);
            this.state.data = data;
            const now = new Date();
            this.state.lastUpdated = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } catch (error) {
            console.error("Failed to load Freight Dashboard data:", error);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Opens filtered freight.shipping list view (drill-down)
     * @param {Array} domain Odoo domain filter
     * @param {string} name Action display title
     */
    openOrders(domain = [], name = "Freight Orders") {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "freight.shipping",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: domain,
        });
    }

    /**
     * Click handlers for KPI cards
     */
    onActiveOrdersClick() {
        this.openOrders([["state", "!=", "cancel"]], "Active Freight Orders");
    }

    onRevenueClick() {
        this.openOrders([["state", "!=", "cancel"]], "Active Freight Orders (Revenue)");
    }

    onExpenseClick() {
        this.openOrders([["state", "!=", "cancel"], ["service_line_ids", "!=", false]], "Freight Orders with Service Expenses");
    }

    onMarginClick() {
        this.openOrders([["state", "!=", "cancel"]], "Active Freight Orders (Profitability)");
    }

    onAllOrdersClick(ev) {
        ev.stopPropagation();
        this.openOrders([], "All Freight Orders");
    }

    /**
     * Click handler for status cards
     */
    onStateCardClick(stateKey) {
        const stateLabel = this.state.data?.state_labels?.[stateKey] || stateKey;
        this.openOrders([["state", "=", stateKey]], `${stateLabel} Freight Orders`);
    }

    /**
     * Renders or updates the 6-month Revenue vs. Expense Chart.js bar chart
     */
    renderChart() {
        if (this.chartInstance) {
            this.chartInstance.destroy();
            this.chartInstance = null;
        }

        const canvas = this.canvasRef.el;
        if (!canvas) {
            return;
        }

        const trend = this.state.data.monthly_trend;
        const currencySymbol = this.state.data.currency?.symbol || "$";

        const config = {
            type: "bar",
            data: {
                labels: trend.full_labels,
                datasets: [
                    {
                        label: "Revenue",
                        data: trend.revenues,
                        backgroundColor: "rgba(25, 135, 84, 0.75)",
                        borderColor: "#198754",
                        borderWidth: 1.5,
                        borderRadius: 6,
                        maxBarThickness: 45,
                    },
                    {
                        label: "Expense",
                        data: trend.expenses,
                        backgroundColor: "rgba(220, 53, 69, 0.75)",
                        borderColor: "#dc3545",
                        borderWidth: 1.5,
                        borderRadius: 6,
                        maxBarThickness: 45,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 600,
                },
                interaction: {
                    intersect: false,
                    mode: "index",
                },
                plugins: {
                    legend: {
                        position: "top",
                        labels: {
                            boxWidth: 14,
                            usePointStyle: true,
                            font: {
                                size: 12,
                                weight: "500",
                            },
                        },
                    },
                    tooltip: {
                        backgroundColor: "rgba(33, 37, 41, 0.95)",
                        padding: 10,
                        cornerRadius: 6,
                        callbacks: {
                            label: (context) => {
                                const label = context.dataset.label || "";
                                const val = context.parsed.y || 0;
                                return ` ${label}: ${this.formatCurrency(val)}`;
                            },
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: "rgba(0, 0, 0, 0.06)",
                        },
                        ticks: {
                            callback: (value) => {
                                if (value >= 1e6) {
                                    return `${currencySymbol}${(value / 1e6).toFixed(1)}M`;
                                } else if (value >= 1e3) {
                                    return `${currencySymbol}${(value / 1e3).toFixed(0)}k`;
                                }
                                return `${currencySymbol}${value}`;
                            },
                        },
                    },
                    x: {
                        grid: {
                            display: false,
                        },
                    },
                },
            },
        };

        if (window.Chart) {
            this.chartInstance = new window.Chart(canvas, config);
        }
    }

    /**
     * Formats numeric amounts using company currency symbol and position
     */
    formatCurrency(amount) {
        if (amount === undefined || amount === null) {
            return "0.00";
        }
        const currency = this.state.data?.currency || { symbol: "$", position: "before" };
        const formattedNumber = Number(amount).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        return currency.position === "before"
            ? `${currency.symbol} ${formattedNumber}`
            : `${formattedNumber} ${currency.symbol}`;
    }

    /**
     * Maps each order state to a visual color and FontAwesome icon
     */
    getStateConfig(stateKey) {
        const config = {
            draft: { color: "secondary", icon: "fa-file-text-o", bgClass: "bg-secondary-subtle" },
            submitted: { color: "info", icon: "fa-paper-plane-o", bgClass: "bg-info-subtle" },
            confirmed: { color: "primary", icon: "fa-check-circle-o", bgClass: "bg-primary-subtle" },
            invoiced: { color: "warning", icon: "fa-dollar", bgClass: "bg-warning-subtle" },
            done: { color: "success", icon: "fa-flag-checkered", bgClass: "bg-success-subtle" },
            cancel: { color: "danger", icon: "fa-times-circle-o", bgClass: "bg-danger-subtle" },
        };
        return config[stateKey] || { color: "secondary", icon: "fa-circle-o", bgClass: "bg-light" };
    }
}

registry.category("actions").add("trn_freight_dashboard.dashboard", FreightDashboard);
