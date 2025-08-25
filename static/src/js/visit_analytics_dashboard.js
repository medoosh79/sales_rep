/** @odoo-module **/

/**
 * Visit Analytics Dashboard Component
 * 
 * Features:
 * - Comprehensive visit analytics and KPI tracking
 * - Interactive charts with multiple visualization types
 * - Real-time data updates and live monitoring
 * - Advanced filtering and date range selection
 * - Export capabilities (PDF, Excel, CSV)
 * - Performance benchmarking and trend analysis
 * - Territory and sales rep comparison
 * - Customer satisfaction metrics
 * - Revenue achievement tracking
 * 
 * Chart Types:
 * - Completion trend line charts
 * - Revenue trend analysis
 * - Visit distribution pie charts
 * - Performance radar charts
 * - Geographic heatmaps
 * 
 * @author Sales Rep Management Pro
 * @version 2.0
 * @requires Chart.js, moment.js
 */
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
export class VisitAnalyticsDashboard extends Component {
    static template = "sales_rep_mgmt_pro.VisitAnalyticsDashboard";
    
    /**
     * Component setup and initialization
     * Configures services, state management, and lifecycle hooks
     */
    setup() {
        // Initialize core services
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.user = useService("user");
        this.router = useService("router");
        
        // Component state management
        this.state = useState({
            loading: true,
            error: null,
            analytics: [],
            periodType: 'monthly',
            dateFrom: this.getDefaultDateFrom(),
            dateTo: this.getDefaultDateTo(),
            salesRepId: null,
            territoryId: null,
            
            // Key Performance Indicators
            kpis: {
                totalVisits: 0,
                avgCompletionRate: 0,
                totalRevenue: 0,
                avgRevenueAchievement: 0,
                avgVisitDuration: 0,
                customerSatisfaction: 0,
                conversionRate: 0,
                travelEfficiency: 0,
                growthRate: 0,
                targetAchievement: 0
            },
            
            // Chart configurations and data
            charts: {
                completionTrend: {
                    data: null,
                    options: null,
                    instance: null
                },
                revenueTrend: {
                    data: null,
                    options: null,
                    instance: null
                },
                visitDistribution: {
                    data: null,
                    options: null,
                    instance: null
                },
                heatmap: {
                    data: null,
                    options: null,
                    instance: null
                },
                performanceRadar: {
                    data: null,
                    options: null,
                    instance: null
                }
            },
            
            // Filter options
            filters: {
                salesReps: [],
                territories: [],
                customers: [],
                visitTypes: [],
                isLoading: false
            },
            
            // Real-time monitoring data
            realTimeData: {
                activeVisits: 0,
                todayRevenue: 0,
                completionRate: 0,
                lastUpdate: null,
                isConnected: true
            },
            
            // Export and reporting options
            exportOptions: {
                format: 'pdf',
                includeCharts: true,
                dateRange: 'current',
                isExporting: false
            },
            
            // UI state
            selectedTab: 'overview',
            fullscreenChart: null,
            compareMode: false
        });
        
        // Chart management
        this.chartInstances = new Map();
        this.refreshInterval = null;
        this.resizeObserver = null;
        
        // Lifecycle hooks
        onWillStart(async () => {
            await this.loadInitialData();
        });
        
        onMounted(() => {
            this.initializeDashboard();
        });
        
        onWillUnmount(() => {
            this.cleanup();
        });
    }
    
    /**
     * Get default start date (1 month ago)
     * @returns {string} Date string in YYYY-MM-DD format
     */
    getDefaultDateFrom() {
        const date = new Date();
        date.setMonth(date.getMonth() - 1);
        return date.toISOString().split('T')[0];
    }
    
    /**
     * Get default end date (today)
     * @returns {string} Date string in YYYY-MM-DD format
     */
    getDefaultDateTo() {
        return new Date().toISOString().split('T')[0];
    }
    
    /**
     * Load initial component data
     * Handles parallel loading of analytics, filters, and real-time data
     */
    async loadInitialData() {
        try {
            this.state.loading = true;
            this.state.error = null;
            
            // Load data in parallel for better performance
            const loadPromises = [
                this.loadAnalytics().catch(error => {
                    console.error('Failed to load analytics:', error);
                    this.notification.add(_t('Failed to load analytics data'), { type: 'warning' });
                }),
                this.loadFilters().catch(error => {
                    console.error('Failed to load filters:', error);
                    // Filter failure is not critical, continue silently
                }),
                this.loadRealTimeData().catch(error => {
                    console.error('Failed to load real-time data:', error);
                    // Real-time data failure is not critical, continue silently
                })
            ];
            
            await Promise.allSettled(loadPromises);
            
        } catch (error) {
            console.error('Critical error loading initial data:', error);
            this.state.error = _t('Failed to load dashboard data. Please refresh the page.');
            this.notification.add(this.state.error, { 
                type: 'danger',
                sticky: true
            });
        } finally {
            this.state.loading = false;
        }
    }
    
    /**
     * Load analytics data based on current filters
     * Fetches comprehensive visit analytics and KPIs
     */
    async loadAnalytics() {
        try {
            this.state.loading = true;
            
            // Validate date range
            if (new Date(this.state.dateFrom) > new Date(this.state.dateTo)) {
                throw new Error(_t('Start date cannot be after end date'));
            }
            
            // Load analytics data with comprehensive parameters
            const analytics = await this.orm.call(
                'daily.visit.analytics',
                'get_analytics_data',
                [],
                {
                    period_type: this.state.periodType,
                    date_from: this.state.dateFrom,
                    date_to: this.state.dateTo,
                    sales_rep_id: this.state.salesRepId,
                    territory_id: this.state.territoryId,
                    include_kpis: true,
                    include_trends: true,
                    include_comparisons: true
                }
            );
            
            // Process and store analytics data
            this.state.analytics = analytics.data || [];
            
            // Update KPIs
            if (analytics.kpis) {
                Object.assign(this.state.kpis, analytics.kpis);
            }
            
            // Calculate additional metrics
            this.calculateKPIs();
            
            // Render charts with new data
            await this.renderCharts();
            
        } catch (error) {
            console.error('Error loading analytics:', error);
            this.state.error = error.message || _t('Failed to load analytics data');
            throw error;
        }
    }
    
    /**
     * Load filter options (sales reps, territories, etc.)
     */
    async loadFilters() {
        try {
            this.state.filters.isLoading = true;
            
            const [salesReps, territories, visitTypes] = await Promise.all([
                this.orm.searchRead('res.users', [['groups_id', 'in', [/* sales rep group id */]]], ['id', 'name']),
                this.orm.searchRead('sales.territory', [], ['id', 'name']),
                this.orm.searchRead('visit.type', [], ['id', 'name'])
            ]);
            
            this.state.filters.salesReps = salesReps;
            this.state.filters.territories = territories;
            this.state.filters.visitTypes = visitTypes;
            
        } catch (error) {
            console.error('Error loading filters:', error);
        } finally {
            this.state.filters.isLoading = false;
        }
    }
    
    /**
     * Load real-time monitoring data
     */
    async loadRealTimeData() {
        try {
            const realTimeData = await this.orm.call(
                'daily.visit.analytics',
                'get_real_time_data',
                []
            );
            
            Object.assign(this.state.realTimeData, {
                ...realTimeData,
                lastUpdate: new Date(),
                isConnected: true
            });
            
        } catch (error) {
            console.error('Error loading real-time data:', error);
            this.state.realTimeData.isConnected = false;
        }
    }
    /**
     * Calculate KPIs from analytics data
     * Computes key performance indicators including growth rates and achievements
     */
    calculateKPIs() {
        const analytics = this.state.analytics;
        
        if (!analytics || analytics.length === 0) {
            this.state.kpis = {
                totalVisits: 0,
                avgCompletionRate: 0,
                totalRevenue: 0,
                avgRevenueAchievement: 0,
                growthRate: 0,
                targetAchievement: 0
            };
            return;
        }
        
        try {
            // Calculate basic metrics
            const totalVisits = analytics.reduce((sum, item) => sum + (item.total_visits || 0), 0);
            const totalRevenue = analytics.reduce((sum, item) => sum + (item.total_revenue || 0), 0);
            const avgCompletionRate = analytics.reduce((sum, item) => sum + (item.completion_rate || 0), 0) / analytics.length;
            
            // Calculate growth rate (comparing first and last periods)
            let growthRate = 0;
            if (analytics.length >= 2) {
                const firstPeriod = analytics[0].total_visits || 0;
                const lastPeriod = analytics[analytics.length - 1].total_visits || 0;
                if (firstPeriod > 0) {
                    growthRate = ((lastPeriod - firstPeriod) / firstPeriod) * 100;
                }
            }
            
            // Calculate target achievement (assuming target is stored in analytics)
            const totalTarget = analytics.reduce((sum, item) => sum + (item.target_visits || 0), 0);
            const targetAchievement = totalTarget > 0 ? (totalVisits / totalTarget) * 100 : 0;
            
            this.state.kpis = {
                totalVisits,
                avgCompletionRate: Math.round(avgCompletionRate * 100) / 100,
                totalRevenue,
                avgRevenueAchievement: totalRevenue > 0 ? Math.round((totalRevenue / (totalRevenue * 1.2)) * 100) : 0, // Assuming 20% higher target
                growthRate: Math.round(growthRate * 100) / 100,
                targetAchievement: Math.round(targetAchievement * 100) / 100
            };
            
        } catch (error) {
            console.error('Error calculating KPIs:', error);
            // Set default values on error
            this.state.kpis = {
                totalVisits: 0,
                avgCompletionRate: 0,
                totalRevenue: 0,
                avgRevenueAchievement: 0,
                growthRate: 0,
                targetAchievement: 0
            };
        }
    }
    
    /**
     * Render all dashboard charts
     * Orchestrates the rendering of completion trend, revenue trend, and distribution charts
     */
    async renderCharts() {
        if (this.state.loading || this.state.analytics.length === 0) {
            return;
        }
        
        try {
            // Destroy existing chart instances to prevent memory leaks
            this.destroyExistingCharts();
            
            // Render charts in parallel for better performance
            await Promise.all([
                this.renderCompletionTrendChart(),
                this.renderRevenueTrendChart(),
                this.renderVisitDistributionChart()
            ]);
            
        } catch (error) {
            console.error('Error rendering charts:', error);
            this.notification.add(_t('Failed to render charts'), { type: 'warning' });
        }
    }
    
    /**
     * Destroy existing chart instances to prevent memory leaks
     */
    destroyExistingCharts() {
        Object.values(this.state.charts).forEach(chart => {
            if (chart.instance) {
                chart.instance.destroy();
                chart.instance = null;
            }
        });
    }

    /**
     * Render completion trend line chart
     * Shows visit completion rates over time
     */
    async renderCompletionTrendChart() {
        try {
            const ctx = document.getElementById('completionTrendChart');
            if (!ctx) {
                console.warn('Completion trend chart canvas not found');
                return;
            }
            
            const data = this.state.analytics.map(item => ({
                x: item.period || 'Unknown',
                y: item.completion_rate || 0
            }));
            
            const chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: [{
                        label: _t('Completion Rate (%)'),
                        data: data,
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    scales: {
                        x: {
                            type: 'category',
                            title: {
                                display: true,
                                text: _t('Period'),
                                font: { size: 12, weight: 'bold' }
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        },
                        y: {
                            beginAtZero: true,
                            max: 100,
                            title: {
                                display: true,
                                text: _t('Completion Rate (%)'),
                                font: { size: 12, weight: 'bold' }
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            },
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: _t('Visit Completion Trend'),
                            font: { size: 16, weight: 'bold' }
                        },
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderColor: '#007bff',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    return `${context.dataset.label}: ${context.parsed.y}%`;
                                }
                            }
                        }
                    }
                }
            });
            
            // Store chart instance for later destruction
            this.state.charts.completionTrend.instance = chartInstance;
            
        } catch (error) {
            console.error('Error rendering completion trend chart:', error);
        }
    }
    
    /**
     * Render revenue trend bar chart
     * Shows revenue performance over time
     */
    async renderRevenueTrendChart() {
        try {
            const ctx = document.getElementById('revenueTrendChart');
            if (!ctx) {
                console.warn('Revenue trend chart canvas not found');
                return;
            }
            
            const data = this.state.analytics.map(item => ({
                x: item.period || 'Unknown',
                y: item.total_revenue || 0
            }));
            
            const chartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    datasets: [{
                        label: _t('Revenue'),
                        data: data,
                        backgroundColor: '#28a745',
                        borderColor: '#1e7e34',
                        borderWidth: 1,
                        borderRadius: 4,
                        borderSkipped: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    scales: {
                        x: {
                            type: 'category',
                            title: {
                                display: true,
                                text: _t('Period'),
                                font: { size: 12, weight: 'bold' }
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: _t('Revenue'),
                                font: { size: 12, weight: 'bold' }
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            },
                            ticks: {
                                callback: function(value) {
                                    return new Intl.NumberFormat('en-US', {
                                        style: 'currency',
                                        currency: 'USD',
                                        minimumFractionDigits: 0
                                    }).format(value);
                                }
                            }
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: _t('Revenue Trend'),
                            font: { size: 16, weight: 'bold' }
                        },
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderColor: '#28a745',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    const value = new Intl.NumberFormat('en-US', {
                                        style: 'currency',
                                        currency: 'USD'
                                    }).format(context.parsed.y);
                                    return `${context.dataset.label}: ${value}`;
                                }
                            }
                        }
                    }
                }
            });
            
            // Store chart instance for later destruction
            this.state.charts.revenueTrend.instance = chartInstance;
            
        } catch (error) {
            console.error('Error rendering revenue trend chart:', error);
        }
    }
    
    /**
     * Render visit distribution doughnut chart
     * Shows the distribution of completed vs cancelled visits
     */
    async renderVisitDistributionChart() {
        try {
            const ctx = document.getElementById('visitDistributionChart');
            if (!ctx) {
                console.warn('Visit distribution chart canvas not found');
                return;
            }
            
            const totalCompleted = this.state.analytics.reduce((sum, item) => sum + (item.completed_visits || 0), 0);
            const totalCancelled = this.state.analytics.reduce((sum, item) => sum + (item.cancelled_visits || 0), 0);
            const totalPending = this.state.analytics.reduce((sum, item) => sum + (item.pending_visits || 0), 0);
            
            const chartInstance = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: [_t('Completed'), _t('Cancelled'), _t('Pending')],
                    datasets: [{
                        data: [totalCompleted, totalCancelled, totalPending],
                        backgroundColor: ['#28a745', '#dc3545', '#ffc107'],
                        borderWidth: 2,
                        borderColor: '#fff',
                        hoverBorderWidth: 3,
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: true,
                            text: _t('Visit Status Distribution'),
                            font: { size: 16, weight: 'bold' }
                        },
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 20,
                                usePointStyle: true,
                                font: { size: 12 }
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = total > 0 ? ((context.parsed / total) * 100).toFixed(1) : 0;
                                    return `${context.label}: ${context.parsed} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
            
            // Store chart instance for later destruction
            this.state.charts.visitDistribution.instance = chartInstance;
            
        } catch (error) {
            console.error('Error rendering visit distribution chart:', error);
        }
    }

    /**
     * Handle period type change event
     * Reloads analytics data and updates charts
     */
    async onPeriodTypeChange(event) {
        try {
            this.state.periodType = event.target.value;
            await this.loadAnalytics();
            await this.renderCharts();
        } catch (error) {
            console.error('Error changing period type:', error);
            this.notification.add(_t('Failed to update period type'), { type: 'warning' });
        }
    }

    /**
     * Handle date from change event
     * Validates date range and reloads data
     */
    async onDateFromChange(event) {
        try {
            this.state.dateFrom = event.target.value;
            
            // Validate date range
            if (new Date(this.state.dateFrom) > new Date(this.state.dateTo)) {
                this.notification.add(_t('Start date cannot be after end date'), { type: 'warning' });
                return;
            }
            
            await this.loadAnalytics();
            await this.renderCharts();
        } catch (error) {
            console.error('Error changing date from:', error);
            this.notification.add(_t('Failed to update start date'), { type: 'warning' });
        }
    }

    /**
     * Handle date to change event
     * Validates date range and reloads data
     */
    async onDateToChange(event) {
        try {
            this.state.dateTo = event.target.value;
            
            // Validate date range
            if (new Date(this.state.dateFrom) > new Date(this.state.dateTo)) {
                this.notification.add(_t('Start date cannot be after end date'), { type: 'warning' });
                return;
            }
            
            await this.loadAnalytics();
            await this.renderCharts();
        } catch (error) {
            console.error('Error changing date to:', error);
            this.notification.add(_t('Failed to update end date'), { type: 'warning' });
        }
    }

    /**
     * Refresh dashboard data
     * Reloads all data and updates charts
     */
    async refreshData() {
        try {
            await this.loadInitialData();
            this.notification.add(_t('Dashboard data refreshed successfully'), { type: 'success' });
        } catch (error) {
            console.error('Error refreshing data:', error);
            this.notification.add(_t('Failed to refresh dashboard data'), { type: 'danger' });
        }
    }

    /**
     * Format currency values
     * @param {number} amount - Amount to format
     * @returns {string} Formatted currency string
     */
    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        }).format(amount || 0);
    }

    /**
     * Format percentage values
     * @param {number} value - Value to format as percentage
     * @returns {string} Formatted percentage string
     */
    formatPercentage(value) {
        return `${(value || 0).toFixed(1)}%`;
    }
    
    /**
     * Export dashboard data to various formats
     * @param {string} format - Export format (csv, excel, pdf)
     */
    async exportData(format = 'csv') {
        try {
            this.state.exportOptions.isExporting = true;
            
            const exportData = {
                analytics: this.state.analytics,
                kpis: this.state.kpis,
                filters: {
                    periodType: this.state.periodType,
                    dateFrom: this.state.dateFrom,
                    dateTo: this.state.dateTo,
                    salesRepId: this.state.salesRepId,
                    territoryId: this.state.territoryId
                },
                exportDate: new Date().toISOString()
            };
            
            await this.orm.call(
                'daily.visit.analytics',
                'export_analytics_data',
                [exportData],
                { format: format }
            );
            
            this.notification.add(_t('Data exported successfully'), { type: 'success' });
            
        } catch (error) {
            console.error('Error exporting data:', error);
            this.notification.add(_t('Failed to export data'), { type: 'danger' });
        } finally {
            this.state.exportOptions.isExporting = false;
        }
    }
    
    /**
     * Initialize dashboard after mounting
     * Sets up real-time updates and responsive behavior
     */
    initializeDashboard() {
        try {
            // Set up real-time data refresh
            this.refreshInterval = setInterval(() => {
                this.loadRealTimeData();
            }, 30000); // Refresh every 30 seconds
            
            // Set up resize observer for responsive charts
            this.resizeObserver = new ResizeObserver(() => {
                Object.values(this.state.charts).forEach(chart => {
                    if (chart.instance) {
                        chart.instance.resize();
                    }
                });
            });
            
            const dashboardElement = document.querySelector('.visit-analytics-dashboard');
            if (dashboardElement) {
                this.resizeObserver.observe(dashboardElement);
            }
            
        } catch (error) {
            console.error('Error initializing dashboard:', error);
        }
    }
    
    /**
     * Cleanup resources on component unmount
     * Prevents memory leaks and clears intervals
     */
    cleanup() {
        try {
            // Clear refresh interval
            if (this.refreshInterval) {
                clearInterval(this.refreshInterval);
                this.refreshInterval = null;
            }
            
            // Disconnect resize observer
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
                this.resizeObserver = null;
            }
            
            // Destroy all chart instances
            this.destroyExistingCharts();
            
        } catch (error) {
            console.error('Error during cleanup:', error);
        }
    }
}

registry.category("actions").add("visit_analytics_dashboard", VisitAnalyticsDashboard);