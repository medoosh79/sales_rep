/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Real-time Notifications Component
 * 
 * Features:
 * - Real-time push notifications via bus service
 * - Desktop notifications with permission handling
 * - Audio notifications with volume control
 * - Notification filtering and categorization
 * - Auto-refresh and periodic updates
 * - Notification history and read status
 * - Customizable notification settings
 * - Performance optimization with debouncing
 * - Error handling and recovery mechanisms
 * - Offline support and reconnection
 */
export class RealTimeNotifications extends Component {
    static template = "sales_rep_mgmt_pro.RealTimeNotifications";
    
    setup() {
        // Core services
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.bus = useService("bus_service");
        this.user = useService("user");
        this.router = useService("router");
        
        // Component state
        this.state = useState({
            // Loading and connection states
            isLoading: false,
            isConnected: false,
            connectionStatus: 'disconnected', // disconnected, connecting, connected, error
            error: null,
            
            // Notification data
            notifications: [],
            unreadCount: 0,
            totalCount: 0,
            lastUpdate: null,
            
            // Settings and preferences
            settings: {
                enableSound: true,
                enableDesktop: true,
                enableInApp: true,
                autoMarkRead: false,
                soundVolume: 0.5,
                maxNotifications: 100,
                refreshInterval: 30000, // 30 seconds
                notificationTypes: {
                    visitReminder: true,
                    visitCompleted: true,
                    targetAchieved: true,
                    customerFeedback: true,
                    systemAlert: true,
                    routeUpdate: true,
                    emergencyAlert: true
                }
            },
            
            // Filters and display options
            filters: {
                type: 'all',
                read: 'all',
                dateRange: 'today',
                priority: 'all',
                salesRep: 'all'
            },
            
            // UI state
            showPanel: false,
            expandedNotifications: new Set(),
            selectedNotifications: new Set()
        });
        
        // Internal properties
        this.eventListeners = new Map();
        this.notificationSound = null;
        this.refreshInterval = null;
        this.reconnectTimeout = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.debounceTimeout = null;
        
        // Performance tracking
        this.performanceMetrics = {
            notificationsReceived: 0,
            notificationsShown: 0,
            averageResponseTime: 0,
            lastPerformanceCheck: Date.now()
        };
        
        // Lifecycle hooks
        onMounted(() => {
            this.initializeComponent();
        });
        
        onWillUnmount(() => {
            this.cleanup();
        });
    }
    
    /**
     * Initialize the notification component
     */
    async initializeComponent() {
        try {
            this.state.isLoading = true;
            this.state.connectionStatus = 'connecting';
            this.state.error = null;
            
            // Load user settings
            await this.loadUserSettings();
            
            // Request desktop notification permission
            await this.requestNotificationPermission();
            
            // Load notification sound
            this.loadNotificationSound();
            
            // Connect to bus service for real-time updates
            await this.connectToBus();
            
            // Load existing notifications
            await this.loadNotifications();
            
            // Set up periodic refresh
            this.setupPeriodicRefresh();
            
            // Initialize performance monitoring
            this.initializePerformanceMonitoring();
            
            this.state.isConnected = true;
            this.state.connectionStatus = 'connected';
            this.state.isLoading = false;
            this.state.lastUpdate = new Date().toISOString();
            
            console.log('Real-time notifications initialized successfully');
            
        } catch (error) {
            this.handleError(error, 'Component Initialization');
        }
    }
    
    /**
     * Request desktop notification permission
     */
    async requestNotificationPermission() {
        try {
            if ('Notification' in window) {
                if (Notification.permission === 'default') {
                    const permission = await Notification.requestPermission();
                    console.log('Notification permission:', permission);
                }
                
                // Update settings based on permission
                this.state.settings.enableDesktop = Notification.permission === 'granted';
            } else {
                console.warn('Desktop notifications not supported');
                this.state.settings.enableDesktop = false;
            }
        } catch (error) {
            console.error('Error requesting notification permission:', error);
            this.state.settings.enableDesktop = false;
        }
    }
    
    /**
     * Load user-specific notification settings
     */
    async loadUserSettings() {
        try {
            const userSettings = await this.orm.call(
                'res.users',
                'get_notification_settings',
                [this.user.userId]
            );
            
            if (userSettings) {
                Object.assign(this.state.settings, userSettings);
            }
            
        } catch (error) {
            console.warn('Could not load user settings, using defaults:', error);
        }
    }
    
    /**
     * Load notification sound with error handling
     */
    loadNotificationSound() {
        try {
            // Create audio element for notification sound
            this.notificationSound = new Audio('/sales_rep_mgmt_pro/static/src/sounds/notification.mp3');
            this.notificationSound.volume = this.state.settings.soundVolume;
            this.notificationSound.preload = 'auto';
            
            // Handle audio loading errors
            this.notificationSound.addEventListener('error', (error) => {
                console.warn('Could not load notification sound:', error);
                this.notificationSound = null;
            });
            
        } catch (error) {
            console.warn('Could not create notification sound:', error);
            this.notificationSound = null;
        }
    }
    
    /**
     * Connect to bus service for real-time updates
     */
    async connectToBus() {
        try {
            this.state.connectionStatus = 'connecting';
            
            // Subscribe to bus channels for real-time updates
            this.bus.subscribe('sales_rep_notifications', (message) => {
                this.handleBusMessage(message);
            });
            
            this.bus.subscribe('visit_updates', (message) => {
                this.handleVisitUpdate(message);
            });
            
            this.bus.subscribe('target_alerts', (message) => {
                this.handleTargetAlert(message);
            });
            
            this.bus.subscribe('system_notifications', (message) => {
                this.handleSystemNotification(message);
            });
            
            // Add connection status listeners
            this.bus.addEventListener('connect', () => {
                this.state.connectionStatus = 'connected';
                this.state.isConnected = true;
                this.reconnectAttempts = 0;
                console.log('Bus service connected');
            });
            
            this.bus.addEventListener('disconnect', () => {
                this.state.connectionStatus = 'disconnected';
                this.state.isConnected = false;
                this.attemptReconnection();
                console.log('Bus service disconnected');
            });
            
            this.bus.addEventListener('error', (error) => {
                this.state.connectionStatus = 'error';
                this.handleError(error, 'Bus Service');
            });
            
        } catch (error) {
            this.state.connectionStatus = 'error';
            throw error;
        }
    }
    
    /**
     * Attempt to reconnect to bus service
     */
    async attemptReconnection() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this.state.connectionStatus = 'error';
            return;
        }
        
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000); // Exponential backoff
        
        console.log(`Attempting reconnection ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`);
        
        this.reconnectTimeout = setTimeout(async () => {
            try {
                await this.connectToBus();
            } catch (error) {
                console.error('Reconnection failed:', error);
                this.attemptReconnection();
            }
        }, delay);
    }
    
    /**
     * Initialize performance monitoring
     */
    initializePerformanceMonitoring() {
        // Reset performance metrics
        this.performanceMetrics = {
            notificationsReceived: 0,
            notificationsShown: 0,
            averageResponseTime: 0,
            lastPerformanceCheck: Date.now()
        };
        
        // Set up periodic performance logging
        setInterval(() => {
            this.logPerformanceMetrics();
        }, 300000); // Every 5 minutes
    }
    
    /**
     * Log performance metrics
     */
    logPerformanceMetrics() {
        const now = Date.now();
        const timeDiff = now - this.performanceMetrics.lastPerformanceCheck;
        
        console.log('Notification Performance Metrics:', {
            ...this.performanceMetrics,
            timeWindow: `${timeDiff / 1000}s`,
            notificationsPerMinute: (this.performanceMetrics.notificationsReceived / (timeDiff / 60000)).toFixed(2)
        });
        
        this.performanceMetrics.lastPerformanceCheck = now;
    }
    
    /**
     * Load notifications from the server
     */
    async loadNotifications() {
        try {
            this.state.isLoading = true;
            
            const notifications = await this.orm.searchRead(
                'sales.rep.notification',
                this.getNotificationDomain(),
                [
                    'id', 'title', 'message', 'notification_type', 'priority',
                    'is_read', 'created_date', 'action_url', 'related_record_id',
                    'related_model', 'icon', 'color', 'sales_rep_id'
                ],
                { 
                    order: 'created_date desc', 
                    limit: this.state.settings.maxNotifications 
                }
            );
            
            // Process notifications with additional metadata
            this.state.notifications = notifications.map(notif => ({
                ...notif,
                timeAgo: this.getTimeAgo(notif.created_date),
                isNew: this.isRecentNotification(notif.created_date),
                formattedDate: this.formatDate(notif.created_date)
            }));
            
            this.state.totalCount = this.state.notifications.length;
            this.updateUnreadCount();
            this.state.lastUpdate = new Date().toISOString();
            
        } catch (error) {
            this.handleError(error, 'Loading Notifications');
        } finally {
            this.state.isLoading = false;
        }
    }
    
    /**
     * Format date for display
     */
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }
    
    getNotificationDomain() {
        const domain = [];
        
        // Filter by type
        if (this.state.filters.type !== 'all') {
            domain.push(['notification_type', '=', this.state.filters.type]);
        }
        
        // Filter by read status
        if (this.state.filters.read === 'unread') {
            domain.push(['is_read', '=', false]);
        } else if (this.state.filters.read === 'read') {
            domain.push(['is_read', '=', true]);
        }
        
        // Filter by date range
        if (this.state.filters.dateRange === 'today') {
            const today = new Date().toISOString().split('T')[0];
            domain.push(['created_date', '>=', today]);
        } else if (this.state.filters.dateRange === 'week') {
            const weekAgo = new Date();
            weekAgo.setDate(weekAgo.getDate() - 7);
            domain.push(['created_date', '>=', weekAgo.toISOString().split('T')[0]]);
        }
        
        return domain;
    }
    
    handleBusMessage(message) {
        const { type, data } = message;
        
        switch (type) {
            case 'new_notification':
                this.addNewNotification(data);
                break;
            case 'notification_read':
                this.markNotificationRead(data.id);
                break;
            case 'bulk_notification':
                this.handleBulkNotification(data);
                break;
        }
    }
    
    handleVisitUpdate(message) {
        const { visit_id, status, customer_name } = message;
        
        if (this.state.settings.notificationTypes.visitCompleted && status === 'completed') {
            this.createNotification({
                title: _t('Visit Completed'),
                message: _t('Visit to %s has been completed', customer_name),
                type: 'visit_completed',
                priority: 'medium',
                icon: 'fa-check-circle',
                color: 'success'
            });
        }
    }
    
    handleTargetAlert(message) {
        const { target_type, achievement_percentage, period } = message;
        
        if (this.state.settings.notificationTypes.targetAchieved && achievement_percentage >= 100) {
            this.createNotification({
                title: _t('Target Achieved!'),
                message: _t('%s target for %s achieved (%s%%)', target_type, period, achievement_percentage),
                type: 'target_achieved',
                priority: 'high',
                icon: 'fa-trophy',
                color: 'warning'
            });
        }
    }
    
    addNewNotification(notificationData) {
        const notification = {
            ...notificationData,
            timeAgo: _t('Just now'),
            isNew: true
        };
        
        this.state.notifications.unshift(notification);
        this.updateUnreadCount();
        
        // Show notification based on settings
        this.showNotification(notification);
        
        // Auto-mark as read if enabled
        if (this.state.settings.autoMarkRead) {
            setTimeout(() => {
                this.markAsRead(notification.id);
            }, 3000);
        }
    }
    
    showNotification(notification) {
        // Play sound if enabled
        if (this.state.settings.enableSound && this.notificationSound) {
            this.notificationSound.play().catch(e => console.warn('Could not play sound:', e));
        }
        
        // Show desktop notification if enabled and permitted
        if (this.state.settings.enableDesktop && 'Notification' in window && Notification.permission === 'granted') {
            const desktopNotif = new Notification(notification.title, {
                body: notification.message,
                icon: '/sales_rep_mgmt_pro/static/src/img/notification-icon.png',
                badge: '/sales_rep_mgmt_pro/static/src/img/badge-icon.png',
                tag: notification.id,
                requireInteraction: notification.priority === 'high'
            });
            
            desktopNotif.onclick = () => {
                window.focus();
                this.handleNotificationClick(notification);
                desktopNotif.close();
            };
            
            // Auto-close after 5 seconds for non-high priority
            if (notification.priority !== 'high') {
                setTimeout(() => desktopNotif.close(), 5000);
            }
        }
        
        // Show in-app notification if enabled
        if (this.state.settings.enableInApp) {
            this.notification.add(notification.message, {
                type: this.getNotificationType(notification.priority),
                title: notification.title,
                sticky: notification.priority === 'high'
            });
        }
    }
    
    getNotificationType(priority) {
        switch (priority) {
            case 'high': return 'danger';
            case 'medium': return 'warning';
            case 'low': return 'info';
            default: return 'info';
        }
    }
    
    async markAsRead(notificationId) {
        try {
            await this.orm.write('sales.rep.notification', [notificationId], { is_read: true });
            
            const notification = this.state.notifications.find(n => n.id === notificationId);
            if (notification) {
                notification.is_read = true;
                notification.isNew = false;
            }
            
            this.updateUnreadCount();
        } catch (error) {
            console.error('Error marking notification as read:', error);
        }
    }
    
    async markAllAsRead() {
        try {
            const unreadIds = this.state.notifications
                .filter(n => !n.is_read)
                .map(n => n.id);
            
            if (unreadIds.length > 0) {
                await this.orm.write('sales.rep.notification', unreadIds, { is_read: true });
                
                this.state.notifications.forEach(notification => {
                    if (unreadIds.includes(notification.id)) {
                        notification.is_read = true;
                        notification.isNew = false;
                    }
                });
                
                this.updateUnreadCount();
                this.notification.add(_t('All notifications marked as read'), { type: 'success' });
            }
        } catch (error) {
            console.error('Error marking all notifications as read:', error);
            this.notification.add(_t('Error marking notifications as read'), { type: 'danger' });
        }
    }
    
    updateUnreadCount() {
        this.state.unreadCount = this.state.notifications.filter(n => !n.is_read).length;
    }
    
    handleNotificationClick(notification) {
        // Mark as read
        if (!notification.is_read) {
            this.markAsRead(notification.id);
        }
        
        // Navigate to related record if available
        if (notification.action_url) {
            window.location.href = notification.action_url;
        } else if (notification.related_model && notification.related_record_id) {
            // Open related record in form view
            this.openRecord(notification.related_model, notification.related_record_id);
        }
    }
    
    openRecord(model, recordId) {
        // Implementation depends on your Odoo setup
        // This is a placeholder for opening records
        console.log(`Opening ${model} record ${recordId}`);
    }
    
    setupPeriodicRefresh() {
        // Refresh notifications every 30 seconds
        this.refreshInterval = setInterval(() => {
            this.loadNotifications();
        }, 30000);
    }
    
    getTimeAgo(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);
        
        if (diffInSeconds < 60) {
            return _t('Just now');
        } else if (diffInSeconds < 3600) {
            const minutes = Math.floor(diffInSeconds / 60);
            return _t('%s minutes ago', minutes);
        } else if (diffInSeconds < 86400) {
            const hours = Math.floor(diffInSeconds / 3600);
            return _t('%s hours ago', hours);
        } else {
            const days = Math.floor(diffInSeconds / 86400);
            return _t('%s days ago', days);
        }
    }
    
    isRecentNotification(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffInMinutes = (now - date) / 1000 / 60;
        return diffInMinutes <= 5; // Consider notifications new for 5 minutes
    }
    
    /**
     * Handle component errors gracefully
     */
    handleError(error, context = 'Unknown') {
        console.error(`Notification Error in ${context}:`, error);
        
        // Update error state
        this.state.error = _t('An error occurred in notifications. Please try refreshing.');
        this.state.connectionStatus = 'error';
        
        // Show user-friendly notification
        this.notification.add(this.state.error, {
            type: 'danger',
            sticky: false
        });
        
        // Reset loading state
        this.state.isLoading = false;
        
        // Attempt recovery for certain errors
        if (error.message && error.message.includes('network')) {
            this.attemptReconnection();
        }
    }
    
    /**
     * Handle system notifications
     */
    handleSystemNotification(message) {
        const { title, message: content, priority = 'medium', type = 'system' } = message;
        
        if (this.state.settings.notificationTypes.systemAlert) {
            this.addNewNotification({
                title: title || _t('System Notification'),
                message: content,
                notification_type: type,
                priority: priority,
                icon: 'fa-info-circle',
                color: priority === 'high' ? 'danger' : 'info'
            });
        }
    }
    
    /**
     * Create a new notification
     */
    createNotification(data) {
        const notification = {
            id: `temp_${Date.now()}`,
            title: data.title,
            message: data.message,
            notification_type: data.type,
            priority: data.priority || 'medium',
            icon: data.icon || 'fa-bell',
            color: data.color || 'primary',
            is_read: false,
            created_date: new Date().toISOString(),
            timeAgo: _t('Just now'),
            isNew: true
        };
        
        this.addNewNotification(notification);
    }
    
    /**
     * Mark notification as read locally
     */
    markNotificationRead(notificationId) {
        const notification = this.state.notifications.find(n => n.id === notificationId);
        if (notification && !notification.is_read) {
            notification.is_read = true;
            this.updateUnreadCount();
        }
    }
    
    /**
     * Handle bulk notifications
     */
    handleBulkNotification(data) {
        const { notifications } = data;
        
        if (Array.isArray(notifications)) {
            notifications.forEach(notif => {
                this.addNewNotification(notif);
            });
        }
    }
    
    /**
     * Debounced refresh function
     */
    debouncedRefresh() {
        if (this.debounceTimeout) {
            clearTimeout(this.debounceTimeout);
        }
        
        this.debounceTimeout = setTimeout(() => {
            this.loadNotifications();
        }, 1000);
    }
    
    /**
     * Get component performance metrics
     */
    getPerformanceMetrics() {
        return {
            ...this.performanceMetrics,
            totalNotifications: this.state.totalCount,
            unreadNotifications: this.state.unreadCount,
            connectionStatus: this.state.connectionStatus,
            lastUpdate: this.state.lastUpdate
        };
    }
    
    /**
     * Cleanup resources when component is destroyed
     */
    cleanup() {
        try {
            // Clear intervals and timeouts
            if (this.refreshInterval) {
                clearInterval(this.refreshInterval);
            }
            
            if (this.reconnectTimeout) {
                clearTimeout(this.reconnectTimeout);
            }
            
            if (this.debounceTimeout) {
                clearTimeout(this.debounceTimeout);
            }
            
            // Unsubscribe from bus events
            if (this.bus) {
                this.bus.unsubscribe('sales_rep_notifications');
                this.bus.unsubscribe('visit_updates');
                this.bus.unsubscribe('target_alerts');
                this.bus.unsubscribe('system_notifications');
            }
            
            // Remove event listeners
            this.eventListeners.forEach((listener, element) => {
                element.removeEventListener('click', listener);
            });
            this.eventListeners.clear();
            
            // Clean up audio
            if (this.notificationSound) {
                this.notificationSound.pause();
                this.notificationSound = null;
            }
            
            console.log('Real-time notifications component cleaned up successfully');
            
        } catch (error) {
            console.error('Error during cleanup:', error);
        }
    }
    
    /**
     * Update notification settings
     */
    async updateSettings(newSettings) {
        try {
            this.state.settings = { ...this.state.settings, ...newSettings };
            
            // Update sound volume if changed
            if (this.notificationSound && newSettings.soundVolume !== undefined) {
                this.notificationSound.volume = newSettings.soundVolume;
            }
            
            // Save to server
            await this.orm.call(
                'res.users',
                'save_notification_settings',
                [this.user.userId, this.state.settings]
            );
            
            // Save to localStorage as backup
            localStorage.setItem('sales_rep_notification_settings', JSON.stringify(this.state.settings));
            
            this.notification.add(_t('Settings saved successfully'), { type: 'success' });
            
        } catch (error) {
            console.error('Error saving settings:', error);
            this.notification.add(_t('Error saving settings'), { type: 'danger' });
        }
    }
    
    /**
     * Load settings from localStorage as fallback
     */
    loadSettings() {
        try {
            const savedSettings = localStorage.getItem('sales_rep_notification_settings');
            if (savedSettings) {
                const parsed = JSON.parse(savedSettings);
                this.state.settings = { ...this.state.settings, ...parsed };
            }
        } catch (error) {
            console.warn('Could not load notification settings from localStorage:', error);
        }
    }
}

// Register the component
registry.category("public_components").add("real_time_notifications", RealTimeNotifications);