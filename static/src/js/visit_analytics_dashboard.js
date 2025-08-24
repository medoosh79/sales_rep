/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class VisitAnalyticsDashboard extends Component {
    static template = "sales_rep_mgmt_pro.VisitAnalyticsDashboard";
    
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            loading: true,
            analytics: [],
            periodType: 'monthly',
            dateFrom: null,
            dateTo: null,
            salesRepId: null,
            kpis: {
                totalVisits: 0,
                avgCompletionRate: 0,
                totalRevenue: 0,
                avgRevenueAchievement: 0,
            },
            charts: {
                completionTrend: null,
                revenueTrend: null,
                visitDistribution: null,
            }
        });
        
        onWillStart(async () => {
            await this.loadAnalytics();
        });
        
        onMounted(() => {
            this.renderCharts();
        });
    }
    
    async loadAnalytics() {
        try {
            this.state.loading = true;
            
            // Load analytics data
            const analytics = await this.orm.call(
                'daily.visit.analytics',
                'get_analytics_data',
                [],
                {
                    period_type: this.state.periodType,
                    sales_rep_id: this.state.salesRepId,
                    date_from: this.state.dateFrom,
                    date_to: this.state.dateTo,
                }
            );
            
            this.state.analytics = analytics;
            this.calculateKPIs();
            
        } catch (error) {
            console.error('Error loading analytics:', error);
            this.notification.add(
                _t('Failed to load analytics data'),
                { type: 'danger' }
            );
        } finally {
            this.state.loading = false;
        }
    }
    
    calculateKPIs() {
        const analytics = this.state.analytics;
        
        if (analytics.length === 0) {
            this.state.kpis = {
                totalVisits: 0,
                avgCompletionRate: 0,
                totalRevenue: 0,
                avgRevenueAchievement: 0,
            };
            return;
        }
        
        const totalVisits = analytics.reduce((sum, item) => sum + item.total_visits, 0);
        const totalRevenue = analytics.reduce((sum, item) => sum + item.total_revenue, 0);
        const avgCompletionRate = analytics.reduce((sum, item) => sum + item.completion_rate, 0) / analytics.length;
        
        this.state.kpis = {
            totalVisits,
            avgCompletionRate: Math.round(avgCompletionRate * 100) / 100,
            totalRevenue,
            avgRevenueAchievement: 0, // Calculate based on expected vs actual
        };
    }
    
    renderCharts() {
        if (this.state.loading || this.state.analytics.length === 0) {
            return;
        }
        
        this.renderCompletionTrendChart();
        this.renderRevenueTrendChart();
        this.renderVisitDistributionChart();
    }
    
    renderCompletionTrendChart() {
        const ctx = document.getElementById('completionTrendChart');
        if (!ctx) return;
        
        const data = this.state.analytics.map(item => ({
            x: item.period,
            y: item.completion_rate
        }));
        
        new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Completion Rate (%)',
                    data: data,
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'category',
                        title: {
                            display: true,
                            text: 'Period'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: {
                            display: true,
                            text: 'Completion Rate (%)'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Visit Completion Trend'
                    },
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    renderRevenueTrendChart() {
        const ctx = document.getElementById('revenueTrendChart');
        if (!ctx) return;
        
        const data = this.state.analytics.map(item => ({
            x: item.period,
            y: item.total_revenue
        }));
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                datasets: [{
                    label: 'Revenue',
                    data: data,
                    backgroundColor: '#28a745',
                    borderColor: '#1e7e34',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'category',
                        title: {
                            display: true,
                            text: 'Period'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Revenue'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Revenue Trend'
                    },
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    renderVisitDistributionChart() {
        const ctx = document.getElementById('visitDistributionChart');
        if (!ctx) return;
        
        const totalCompleted = this.state.analytics.reduce((sum, item) => sum + item.completed_visits, 0);
        const totalCancelled = this.state.analytics.reduce((sum, item) => sum + (item.total_visits - item.completed_visits), 0);
        
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Completed', 'Not Completed'],
                datasets: [{
                    data: [totalCompleted, totalCancelled],
                    backgroundColor: ['#28a745', '#dc3545'],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Visit Status Distribution'
                    },
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    async onPeriodTypeChange(event) {
        this.state.periodType = event.target.value;
        await this.loadAnalytics();
        this.renderCharts();
    }
    
    async onDateFromChange(event) {
        this.state.dateFrom = event.target.value;
        await this.loadAnalytics();
        this.renderCharts();
    }
    
    async onDateToChange(event) {
        this.state.dateTo = event.target.value;
        await this.loadAnalytics();
        this.renderCharts();
    }
    
    async refreshData() {
        await this.loadAnalytics();
        this.renderCharts();
    }
    
    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(amount || 0);
    }
    
    formatPercentage(value) {
        return `${(value || 0).toFixed(1)}%`;
    }
}

registry.category("actions").add("visit_analytics_dashboard", VisitAnalyticsDashboard);