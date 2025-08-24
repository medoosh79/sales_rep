/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Daily Visit Tracker Component
 * Real-time tracking and updating of visit status
 */
export class DailyVisitTracker extends Component {
    static template = "sales_rep_mgmt_pro.DailyVisitTracker";
    
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            visits: [],
            currentVisit: null,
            isTracking: false,
            location: null,
            timer: null,
            elapsedTime: 0
        });
        
        onWillStart(this.loadVisits);
        onMounted(this.initializeTracker);
    }
    
    async loadVisits() {
        try {
            const today = new Date().toISOString().split('T')[0];
            const visits = await this.orm.searchRead(
                "daily.visit.line",
                [["schedule_id.visit_date", "=", today], ["state", "in", ["planned", "in_progress"]]],
                ["id", "display_name", "customer_id", "planned_time", "state", "actual_start_time", "visit_type"]
            );
            this.state.visits = visits;
        } catch (error) {
            console.error("Error loading visits:", error);
            this.notification.add(_t("Error loading visits"), { type: "danger" });
        }
    }
    
    initializeTracker() {
        // Initialize geolocation if available
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    this.state.location = {
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude
                    };
                },
                (error) => {
                    console.warn("Geolocation not available:", error);
                }
            );
        }
        
        // Auto-refresh visits every 30 seconds
        setInterval(() => {
            if (!this.state.isTracking) {
                this.loadVisits();
            }
        }, 30000);
    }
    
    async startVisit(visitId) {
        try {
            const currentTime = this.getCurrentTimeFloat();
            
            await this.orm.write("daily.visit.line", [visitId], {
                state: "in_progress",
                actual_start_time: currentTime
            });
            
            this.state.currentVisit = visitId;
            this.state.isTracking = true;
            this.state.elapsedTime = 0;
            
            // Start timer
            this.state.timer = setInterval(() => {
                this.state.elapsedTime += 1;
            }, 1000);
            
            await this.loadVisits();
            this.notification.add(_t("Visit started successfully"), { type: "success" });
            
        } catch (error) {
            console.error("Error starting visit:", error);
            this.notification.add(_t("Error starting visit"), { type: "danger" });
        }
    }
    
    async completeVisit(visitId, result = "successful") {
        try {
            const currentTime = this.getCurrentTimeFloat();
            const visit = this.state.visits.find(v => v.id === visitId);
            const duration = visit.actual_start_time ? 
                (currentTime - visit.actual_start_time) : 0;
            
            await this.orm.write("daily.visit.line", [visitId], {
                state: "completed",
                actual_end_time: currentTime,
                actual_duration: duration,
                visit_result: result
            });
            
            this.stopTracking();
            await this.loadVisits();
            this.notification.add(_t("Visit completed successfully"), { type: "success" });
            
        } catch (error) {
            console.error("Error completing visit:", error);
            this.notification.add(_t("Error completing visit"), { type: "danger" });
        }
    }
    
    async cancelVisit(visitId, reason = "") {
        try {
            await this.orm.write("daily.visit.line", [visitId], {
                state: "cancelled",
                visit_notes: reason
            });
            
            this.stopTracking();
            await this.loadVisits();
            this.notification.add(_t("Visit cancelled"), { type: "warning" });
            
        } catch (error) {
            console.error("Error cancelling visit:", error);
            this.notification.add(_t("Error cancelling visit"), { type: "danger" });
        }
    }
    
    async rescheduleVisit(visitId, newTime) {
        try {
            await this.orm.write("daily.visit.line", [visitId], {
                state: "rescheduled",
                planned_time: newTime
            });
            
            await this.loadVisits();
            this.notification.add(_t("Visit rescheduled successfully"), { type: "info" });
            
        } catch (error) {
            console.error("Error rescheduling visit:", error);
            this.notification.add(_t("Error rescheduling visit"), { type: "danger" });
        }
    }
    
    stopTracking() {
        if (this.state.timer) {
            clearInterval(this.state.timer);
            this.state.timer = null;
        }
        this.state.isTracking = false;
        this.state.currentVisit = null;
        this.state.elapsedTime = 0;
    }
    
    getCurrentTimeFloat() {
        const now = new Date();
        return now.getHours() + (now.getMinutes() / 60) + (now.getSeconds() / 3600);
    }
    
    formatTime(timeFloat) {
        const hours = Math.floor(timeFloat);
        const minutes = Math.floor((timeFloat - hours) * 60);
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    }
    
    formatElapsedTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    
    getVisitStatusColor(state) {
        const colors = {
            'planned': 'info',
            'in_progress': 'warning',
            'completed': 'success',
            'cancelled': 'danger',
            'rescheduled': 'secondary'
        };
        return colors[state] || 'info';
    }
    
    async updateLocation() {
        if (navigator.geolocation && this.state.currentVisit) {
            navigator.geolocation.getCurrentPosition(
                async (position) => {
                    this.state.location = {
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude
                    };
                    
                    // Update visit location if tracking
                    try {
                        await this.orm.write("daily.visit.line", [this.state.currentVisit], {
                            'location_latitude': position.coords.latitude,
                            'location_longitude': position.coords.longitude
                        });
                    } catch (error) {
                        console.warn("Could not update location:", error);
                    }
                },
                (error) => {
                    console.warn("Geolocation error:", error);
                }
            );
        }
    }
}

// Register the component
registry.category("actions").add("daily_visit_tracker", DailyVisitTracker);