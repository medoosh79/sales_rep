/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Interactive Charts Component
 * Advanced chart rendering with Chart.js integration for sales analytics
 * 
 * Features:
 * - Multiple chart types (Line, Bar, Doughnut, Radar)
 * - Responsive design with modern styling
 * - Export functionality
 * - Real-time data updates
 * - Customizable color schemes
 * - Error handling and loading states
 */
export class InteractiveCharts extends Component {
    static template = "sales_rep_mgmt_pro.InteractiveCharts";
    
    setup() {
        // Initialize services
        this.notification = useService("notification");
        
        // Component state management
        this.state = useState({
            charts: {},
            isLoading: false,
            error: null,
            chartOptions: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: 20,
                            font: {
                                family: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
                                size: 12,
                                weight: '500'
                            },
                            color: '#374151'
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(17, 24, 39, 0.95)',
                        titleColor: '#F9FAFB',
                        bodyColor: '#F9FAFB',
                        borderColor: '#6366F1',
                        borderWidth: 1,
                        cornerRadius: 8,
                        displayColors: true,
                        padding: 12,
                        titleFont: {
                            size: 14,
                            weight: '600'
                        },
                        bodyFont: {
                            size: 13
                        },
                        callbacks: {
                            label: function(context) {
                                const label = context.dataset.label || '';
                                const value = context.formattedValue;
                                return `${label}: ${value}`;
                            },
                            afterLabel: function(context) {
                                // Add percentage for pie/doughnut charts
                                if (context.chart.config.type === 'doughnut' || context.chart.config.type === 'pie') {
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((context.raw / total) * 100).toFixed(1);
                                    return `(${percentage}%)`;
                                }
                                return '';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)',
                            borderDash: [2, 2]
                        },
                        ticks: {
                            font: {
                                family: 'Inter, sans-serif',
                                size: 11
                            },
                            color: '#6b7280'
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)',
                            borderDash: [2, 2]
                        },
                        ticks: {
                            font: {
                                family: 'Inter, sans-serif',
                                size: 11
                            },
                            color: '#6b7280'
                        }
                    }
                },
                animation: {
                    duration: 1000,
                    easing: 'easeInOutQuart'
                }
            }
        });
        
        this.chartInstances = new Map();
        
        onMounted(() => {
            this.loadChartLibrary();
        });
        
        onWillUnmount(() => {
            this.destroyAllCharts();
        });
    }
    
    /**
     * Load Chart.js library dynamically
     * Handles CDN fallback and error states
     */
    async loadChartLibrary() {
        try {
            this.state.isLoading = true;
            this.state.error = null;
            
            if (typeof Chart === 'undefined') {
                // Try primary CDN
                try {
                    await this.loadScript('https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js');
                } catch (primaryError) {
                    console.warn('Primary CDN failed, trying fallback:', primaryError);
                    // Fallback CDN
                    await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.js');
                }
            }
            
            // Verify Chart.js loaded successfully
            if (typeof Chart === 'undefined') {
                throw new Error('Chart.js failed to load from all sources');
            }
            
            // Register Chart.js components
            Chart.register(
                Chart.CategoryScale,
                Chart.LinearScale,
                Chart.PointElement,
                Chart.LineElement,
                Chart.BarElement,
                Chart.Title,
                Chart.Tooltip,
                Chart.Legend,
                Chart.ArcElement
            );
            
            this.state.isLoading = false;
        } catch (error) {
            console.error('Failed to load Chart.js:', error);
            this.state.error = _t('Failed to load chart library. Please check your internet connection.');
            this.state.isLoading = false;
            
            this.notification.add(this.state.error, {
                type: 'danger',
                sticky: true
            });
            throw error;
        }
    }
    
    loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
    
    /**
     * Create a line chart with enhanced styling and error handling
     * @param {string} canvasId - Canvas element ID
     * @param {Object} data - Chart data
     * @param {Object} options - Additional chart options
     * @returns {Chart|null} Chart instance or null if failed
     */
    createLineChart(canvasId, data, options = {}) {
        try {
            const canvas = document.getElementById(canvasId);
            if (!canvas) {
                console.error(`Canvas with id '${canvasId}' not found`);
                this.notification.add(_t('Chart canvas not found'), { type: 'warning' });
                return null;
            }

            if (typeof Chart === 'undefined') {
                console.error('Chart.js library not loaded');
                this.notification.add(_t('Chart library not available'), { type: 'danger' });
                return null;
            }

            // Destroy existing chart if present
            if (this.chartInstances.has(canvasId)) {
                this.chartInstances.get(canvasId).destroy();
            }

            const ctx = canvas.getContext('2d');
            const chartOptions = {
                ...this.state.chartOptions,
                ...options,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(156, 163, 175, 0.2)',
                            borderDash: [2, 2]
                        },
                        ticks: {
                            color: '#6B7280',
                            font: {
                                size: 11
                            }
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(156, 163, 175, 0.2)',
                            borderDash: [2, 2]
                        },
                        ticks: {
                            color: '#6B7280',
                            font: {
                                size: 11
                            }
                        }
                    }
                },
                elements: {
                    line: {
                        tension: 0.4,
                        borderWidth: 3
                    },
                    point: {
                        radius: 4,
                        hoverRadius: 6,
                        borderWidth: 2
                    }
                }
            };

            const chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: data.datasets.map(dataset => ({
                        ...dataset,
                        borderWidth: 3,
                        pointRadius: 5,
                        pointHoverRadius: 8,
                        tension: 0.4,
                        fill: false
                    }))
                },
                options: chartOptions
            });

            this.chartInstances.set(canvasId, chart);
            return chart;
        } catch (error) {
            console.error('Error creating line chart:', error);
            this.notification.add(_t('Failed to create line chart'), { type: 'danger' });
            return null;
        }
    }
    
    /**
     * Create a bar chart with enhanced styling and error handling
     * @param {string} canvasId - Canvas element ID
     * @param {Object} data - Chart data
     * @param {Object} options - Additional chart options
     * @returns {Chart|null} Chart instance or null if failed
     */
    createBarChart(canvasId, data, options = {}) {
        try {
            const canvas = document.getElementById(canvasId);
            if (!canvas) {
                console.error(`Canvas with id '${canvasId}' not found`);
                this.notification.add(_t('Chart canvas not found'), { type: 'warning' });
                return null;
            }

            if (typeof Chart === 'undefined') {
                console.error('Chart.js library not loaded');
                this.notification.add(_t('Chart library not available'), { type: 'danger' });
                return null;
            }

            // Destroy existing chart if present
            if (this.chartInstances.has(canvasId)) {
                this.chartInstances.get(canvasId).destroy();
            }

            const ctx = canvas.getContext('2d');
            const chartOptions = {
                ...this.state.chartOptions,
                ...options,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(156, 163, 175, 0.2)',
                            borderDash: [2, 2]
                        },
                        ticks: {
                            color: '#6B7280',
                            font: {
                                size: 11
                            }
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#6B7280',
                            font: {
                                size: 11
                            }
                        }
                    }
                },
                elements: {
                    bar: {
                        borderRadius: 4,
                        borderSkipped: false
                    }
                }
            };

            const chart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: data.datasets.map(dataset => ({
                        ...dataset,
                        borderWidth: 2,
                        borderRadius: 6,
                        borderSkipped: false
                    }))
                },
                options: chartOptions
            });

            this.chartInstances.set(canvasId, chart);
            return chart;
        } catch (error) {
            console.error('Error creating bar chart:', error);
            this.notification.add(_t('Failed to create bar chart'), { type: 'danger' });
            return null;
        }
    }
    
    createDoughnutChart(canvasId, data, options = {}) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || typeof Chart === 'undefined') return null;
        
        const ctx = canvas.getContext('2d');
        const chartOptions = {
            ...this.state.chartOptions,
            ...options,
            type: 'doughnut',
            plugins: {
                ...this.state.chartOptions.plugins,
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                }
            }
        };
        
        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: data.datasets.map(dataset => ({
                    ...dataset,
                    borderWidth: 3,
                    hoverBorderWidth: 5
                }))
            },
            options: chartOptions
        });
        
        this.chartInstances.set(canvasId, chart);
        return chart;
    }
    
    createRadarChart(canvasId, data, options = {}) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || typeof Chart === 'undefined') return null;
        
        const ctx = canvas.getContext('2d');
        const chartOptions = {
            ...this.state.chartOptions,
            ...options,
            type: 'radar',
            scales: {
                r: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    pointLabels: {
                        font: {
                            family: 'Inter, sans-serif',
                            size: 11
                        },
                        color: '#6b7280'
                    }
                }
            }
        };
        
        const chart = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: data.labels,
                datasets: data.datasets.map(dataset => ({
                    ...dataset,
                    borderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }))
            },
            options: chartOptions
        });
        
        this.chartInstances.set(canvasId, chart);
        return chart;
    }
    
    updateChart(canvasId, newData) {
        const chart = this.chartInstances.get(canvasId);
        if (!chart) return;
        
        chart.data = newData;
        chart.update('active');
    }
    
    /**
     * Enhance chart data with better styling and colors
     * @param {Object} data - Original chart data
     * @param {string} chartType - Type of chart (line, bar, pie, etc.)
     * @returns {Object} Enhanced chart data
     */
    enhanceChartData(data, chartType) {
        const colorPalette = [
            '#3B82F6', '#EF4444', '#10B981', '#F59E0B',
            '#8B5CF6', '#06B6D4', '#F97316', '#84CC16'
        ];

        const enhancedData = { ...data };
        
        if (enhancedData.datasets) {
            enhancedData.datasets = enhancedData.datasets.map((dataset, index) => {
                const color = dataset.backgroundColor || colorPalette[index % colorPalette.length];
                
                const enhanced = {
                    ...dataset,
                    backgroundColor: chartType === 'pie' || chartType === 'doughnut' 
                        ? colorPalette.slice(0, data.labels?.length || 8)
                        : color + '20', // Add transparency
                    borderColor: color,
                    borderWidth: chartType === 'line' ? 3 : 2
                };

                // Chart-specific enhancements
                if (chartType === 'line') {
                    enhanced.tension = 0.4;
                    enhanced.pointBackgroundColor = color;
                    enhanced.pointBorderColor = '#ffffff';
                    enhanced.pointBorderWidth = 2;
                    enhanced.pointRadius = 4;
                    enhanced.pointHoverRadius = 6;
                } else if (chartType === 'bar') {
                    enhanced.borderRadius = 4;
                    enhanced.borderSkipped = false;
                }

                return enhanced;
            });
        }

        return enhancedData;
    }

    /**
     * Destroy a specific chart instance
     * @param {string} canvasId - Canvas element ID
     */
    destroyChart(canvasId) {
        try {
            if (this.chartInstances.has(canvasId)) {
                this.chartInstances.get(canvasId).destroy();
                this.chartInstances.delete(canvasId);
            }
        } catch (error) {
            console.error(`Error destroying chart ${canvasId}:`, error);
        }
    }

    /**
     * Destroy all chart instances
     */
    destroyAllCharts() {
        try {
            this.chartInstances.forEach((chart, canvasId) => {
                try {
                    chart.destroy();
                } catch (error) {
                    console.error(`Error destroying chart ${canvasId}:`, error);
                }
            });
            this.chartInstances.clear();
        } catch (error) {
            console.error('Error destroying all charts:', error);
        }
    }

    /**
     * Update chart data with animation
     * @param {string} canvasId - Canvas element ID
     * @param {Object} newData - New chart data
     */
    updateChartData(canvasId, newData) {
        try {
            const chart = this.chartInstances.get(canvasId);
            if (chart) {
                chart.data = this.enhanceChartData(newData, chart.config.type);
                chart.update('active');
            }
        } catch (error) {
            console.error(`Error updating chart ${canvasId}:`, error);
        }
    }

    /**
     * Export chart as image
     * @param {string} canvasId - Canvas element ID
     * @param {string} filename - Export filename
     */
    exportChart(canvasId, filename = 'chart') {
        try {
            const chart = this.chartInstances.get(canvasId);
            if (chart) {
                const url = chart.toBase64Image();
                const link = document.createElement('a');
                link.download = `${filename}.png`;
                link.href = url;
                link.click();
            }
        } catch (error) {
            console.error(`Error exporting chart ${canvasId}:`, error);
            this.notification.add(_t('Failed to export chart'), { type: 'danger' });
        }
    }
    
    // Predefined color schemes
    getColorScheme(name = 'default') {
        const schemes = {
            default: [
                'var(--primary-color)',
                'var(--success-color)',
                'var(--warning-color)',
                'var(--info-color)',
                'var(--secondary-color)'
            ],
            sales: [
                '#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6',
                '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6366f1'
            ],
            performance: [
                '#059669', '#0891b2', '#d97706', '#dc2626', '#7c3aed'
            ]
        };
        
        return schemes[name] || schemes.default;
    }
}

// Register the component
registry.category("public_components").add("interactive_charts", InteractiveCharts);