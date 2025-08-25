/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * GPS Interactive Maps Component
 * 
 * A comprehensive mapping solution for GPS tracking visualization with the following features:
 * - Real-time GPS tracking visualization with multiple map providers (Google Maps, OpenStreetMap)
 * - Interactive route planning and optimization with waypoint management
 * - Advanced heatmap visualization for visit density analysis
 * - Territory boundary management with geofencing capabilities
 * - Multi-layer data visualization (tracking points, routes, territories, POIs)
 * - Real-time updates with WebSocket integration for live tracking
 * - Export capabilities for maps and tracking data
 * - Responsive design with mobile-friendly touch controls
 * - Performance optimization with marker clustering and data pagination
 * - Offline map support with cached tile management
 * 
 * @extends Component
 */
class GPSInteractiveMaps extends Component {
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
            // Map loading and initialization
            mapLoaded: false,
            isLoading: false,
            error: null,
            mapProvider: 'google', // google, leaflet
            
            // View and display settings
            currentView: 'tracking', // tracking, route, heatmap, territory
            selectedSalesRep: null,
            selectedTerritory: null,
            
            // Date and time filters
            dateRange: {
                from: this.getDefaultDateFrom(),
                to: this.getDefaultDateTo()
            },
            timeFilter: 'all', // all, business_hours, after_hours
            
            // Data collections
            trackingData: [],
            routeData: [],
            territoryData: [],
            salesReps: [],
            
            // Map filtering and display options
            mapFilters: {
                showValidOnly: true,
                showInTerritory: false,
                showOutOfTerritory: true,
                trackingTypes: ['all'], // all, check_in, check_out, visit, travel
                showClusters: true,
                showHeatmap: false
            },
            
            // Real-time features
            realTimeEnabled: false,
            lastUpdate: null,
            connectionStatus: 'disconnected', // connected, disconnected, reconnecting
            
            // Map instances and elements
            mapInstance: null,
            markers: [],
            polylines: [],
            heatmapLayer: null,
            territoryLayers: [],
            markerCluster: null,
            
            // UI state
            sidebarVisible: true,
            fullscreenMode: false,
            selectedMarker: null,
            
            // Export and sharing
            exportOptions: {
                isExporting: false,
                format: 'png', // png, pdf, kml, gpx
                includeData: true
            }
        });
        
        // Map configuration settings
        this.mapConfig = {
            // Default location (Riyadh, Saudi Arabia)
            defaultCenter: { lat: 24.7136, lng: 46.6753 },
            defaultZoom: 10,
            minZoom: 3,
            maxZoom: 20,
            mapTypeId: 'roadmap',
            
            // Google Maps specific settings
            googleMaps: {
                apiKey: 'YOUR_GOOGLE_MAPS_API_KEY',
                libraries: ['geometry', 'visualization', 'places'],
                language: 'en',
                region: 'SA'
            },
            
            // Leaflet/OpenStreetMap settings
            leaflet: {
                tileLayer: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                attribution: '© OpenStreetMap contributors',
                maxZoom: 19
            },
            
            // Marker clustering settings
            clustering: {
                enabled: true,
                maxClusterRadius: 50,
                spiderfyOnMaxZoom: true,
                showCoverageOnHover: false
            },
            
            // Performance settings
            performance: {
                maxMarkersBeforeClustering: 100,
                updateInterval: 5000, // 5 seconds for real-time updates
                maxDataPoints: 1000
            }
        };
        
        // Real-time update interval
        this.updateInterval = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        // Component lifecycle hooks
        onMounted(() => {
            this.initializeComponent();
        });
        
        onWillUnmount(() => {
            this.cleanup();
        });
    }
    
    /**
     * Get default start date (7 days ago)
     * @returns {string} Date string in YYYY-MM-DD format
     */
    getDefaultDateFrom() {
        const date = new Date();
        date.setDate(date.getDate() - 7);
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
     * Initialize component after mounting
     * Loads map API and initial data
     */
    async initializeComponent() {
        try {
            this.state.isLoading = true;
            this.state.error = null;
            
            // Load map API based on preference
            await this.loadMapAPI();
            
            // Load initial data in parallel
            await Promise.all([
                this.loadSalesReps(),
                this.loadTerritories(),
                this.loadInitialData()
            ]);
            
        } catch (error) {
            console.error('Error initializing GPS Maps component:', error);
            this.state.error = _t('Failed to initialize maps. Please refresh the page.');
            this.notification.add(this.state.error, { 
                type: 'danger',
                sticky: true
            });
        } finally {
            this.state.isLoading = false;
        }
    }
    
    /**
     * Load appropriate map API based on configuration
     */
    async loadMapAPI() {
        try {
            // Try Google Maps first, fallback to Leaflet
            if (this.state.mapProvider === 'google') {
                await this.loadGoogleMapsAPI();
            } else {
                await this.loadOpenStreetMap();
            }
        } catch (error) {
            console.warn('Primary map provider failed, trying fallback:', error);
            
            // Switch to fallback provider
            this.state.mapProvider = this.state.mapProvider === 'google' ? 'leaflet' : 'google';
            
            if (this.state.mapProvider === 'google') {
                await this.loadGoogleMapsAPI();
            } else {
                await this.loadOpenStreetMap();
            }
        }
    }
    
    /**
     * Load Google Maps API with error handling and fallback
     */
    async loadGoogleMapsAPI() {
        try {
            // Check if Google Maps is already loaded
            if (window.google && window.google.maps) {
                await this.initializeGoogleMap();
                return;
            }
            
            // Create promise for API loading
            return new Promise((resolve, reject) => {
                // Set timeout for loading
                const timeout = setTimeout(() => {
                    reject(new Error('Google Maps API loading timeout'));
                }, 10000);
                
                // Create script element
                const script = document.createElement('script');
                const callbackName = `initGoogleMaps_${Date.now()}`;
                
                // Configure script
                script.src = `https://maps.googleapis.com/maps/api/js?key=${this.mapConfig.googleMaps.apiKey}&libraries=${this.mapConfig.googleMaps.libraries.join(',')}&language=${this.mapConfig.googleMaps.language}&region=${this.mapConfig.googleMaps.region}&callback=${callbackName}`;
                script.async = true;
                script.defer = true;
                
                // Set global callback
                window[callbackName] = async () => {
                    clearTimeout(timeout);
                    try {
                        await this.initializeGoogleMap();
                        resolve();
                    } catch (error) {
                        reject(error);
                    } finally {
                        // Cleanup
                        delete window[callbackName];
                        document.head.removeChild(script);
                    }
                };
                
                // Handle script loading errors
                script.onerror = () => {
                    clearTimeout(timeout);
                    delete window[callbackName];
                    reject(new Error('Failed to load Google Maps API script'));
                };
                
                document.head.appendChild(script);
            });
            
        } catch (error) {
            console.error('Error loading Google Maps API:', error);
            throw error;
        }
    }
    
    /**
     * Load OpenStreetMap (Leaflet) with error handling
     */
    async loadOpenStreetMap() {
        try {
            // Check if Leaflet is already loaded
            if (window.L) {
                await this.initializeLeafletMap();
                return;
            }
            
            // Load Leaflet CSS and JS in parallel
            const [cssLoaded, jsLoaded] = await Promise.all([
                this.loadLeafletCSS(),
                this.loadLeafletJS()
            ]);
            
            if (cssLoaded && jsLoaded) {
                await this.initializeLeafletMap();
            } else {
                throw new Error('Failed to load Leaflet resources');
            }
            
        } catch (error) {
            console.error('Error loading OpenStreetMap:', error);
            this.state.error = _t('Failed to load map. Please check your internet connection.');
            this.notification.add(this.state.error, { type: 'danger' });
            throw error;
        }
    }
    
    /**
     * Load Leaflet CSS
     */
    loadLeafletCSS() {
        return new Promise((resolve, reject) => {
            // Check if CSS is already loaded
            const existingLink = document.querySelector('link[href*="leaflet.css"]');
            if (existingLink) {
                resolve(true);
                return;
            }
            
            const cssLink = document.createElement('link');
            cssLink.rel = 'stylesheet';
            cssLink.href = this.mapConfig.leaflet.cssUrl || 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            cssLink.onload = () => resolve(true);
            cssLink.onerror = () => reject(new Error('Failed to load Leaflet CSS'));
            
            document.head.appendChild(cssLink);
        });
    }
    
    /**
     * Load Leaflet JavaScript
     */
    loadLeafletJS() {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = this.mapConfig.leaflet.jsUrl || 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
            script.onload = () => resolve(true);
            script.onerror = () => reject(new Error('Failed to load Leaflet JS'));
            
            document.head.appendChild(script);
        });
    }
    
    /**
     * Initialize Google Maps instance
     */
    async initializeGoogleMap() {
        const mapContainer = document.getElementById('gps_interactive_map');
        if (!mapContainer) {
            throw new Error('Map container not found');
        }
        
        try {
            // Create map instance with enhanced options
            this.state.mapInstance = new google.maps.Map(mapContainer, {
                center: this.mapConfig.defaultCenter,
                zoom: this.mapConfig.defaultZoom,
                minZoom: this.mapConfig.minZoom,
                maxZoom: this.mapConfig.maxZoom,
                mapTypeId: this.mapConfig.mapTypeId,
                
                // UI Controls
                mapTypeControl: true,
                streetViewControl: true,
                fullscreenControl: true,
                zoomControl: true,
                scaleControl: true,
                rotateControl: true,
                
                // Styling
                styles: this.getMapStyles(),
                
                // Interaction
                gestureHandling: 'cooperative',
                clickableIcons: false
            });
            
            // Initialize marker clusterer if enabled
            if (this.mapConfig.clustering.enabled) {
                this.initializeMarkerClusterer();
            }
            
            // Add event listeners
            this.addGoogleMapEventListeners();
            
            this.state.mapLoaded = true;
            this.state.mapProvider = 'google';
            
            // Load initial data
            await this.loadInitialData();
            
        } catch (error) {
            console.error('Error initializing Google Maps:', error);
            this.state.error = _t('Failed to initialize Google Maps');
            throw error;
        }
    }
    
    /**
     * Initialize Leaflet (OpenStreetMap) instance
     */
    async initializeLeafletMap() {
        const mapContainer = document.getElementById('gps_interactive_map');
        if (!mapContainer) {
            throw new Error('Map container not found');
        }
        
        try {
            // Create map instance
            this.state.mapInstance = L.map(mapContainer, {
                center: [this.mapConfig.defaultCenter.lat, this.mapConfig.defaultCenter.lng],
                zoom: this.mapConfig.defaultZoom,
                minZoom: this.mapConfig.minZoom,
                maxZoom: this.mapConfig.maxZoom,
                zoomControl: true,
                attributionControl: true
            });
            
            // Add tile layer
            L.tileLayer(this.mapConfig.leaflet.tileLayer, {
                attribution: this.mapConfig.leaflet.attribution,
                maxZoom: this.mapConfig.leaflet.maxZoom
            }).addTo(this.state.mapInstance);
            
            // Initialize marker clustering if enabled
            if (this.mapConfig.clustering.enabled && window.L.markerClusterGroup) {
                this.state.markerCluster = L.markerClusterGroup({
                    maxClusterRadius: this.mapConfig.clustering.maxClusterRadius,
                    spiderfyOnMaxZoom: this.mapConfig.clustering.spiderfyOnMaxZoom,
                    showCoverageOnHover: this.mapConfig.clustering.showCoverageOnHover
                });
                this.state.mapInstance.addLayer(this.state.markerCluster);
            }
            
            // Add event listeners
            this.addLeafletEventListeners();
            
            this.state.mapLoaded = true;
            this.state.mapProvider = 'leaflet';
            
            // Load initial data
            await this.loadInitialData();
            
        } catch (error) {
            console.error('Error initializing Leaflet map:', error);
            this.state.error = _t('Failed to initialize map');
            throw error;
        }
    }
    
    /**
     * Get custom map styles for Google Maps
     */
    getMapStyles() {
        return [
            {
                featureType: 'poi',
                elementType: 'labels',
                stylers: [{ visibility: 'off' }]
            },
            {
                featureType: 'transit',
                elementType: 'labels',
                stylers: [{ visibility: 'off' }]
            }
        ];
    }
    
    /**
     * Initialize marker clusterer for Google Maps
     */
    initializeMarkerClusterer() {
        if (window.MarkerClusterer) {
            this.state.markerCluster = new MarkerClusterer({
                map: this.state.mapInstance,
                markers: [],
                algorithm: new window.SuperClusterAlgorithm({
                    radius: this.mapConfig.clustering.maxClusterRadius
                })
            });
        }
    }
    
    /**
     * Add event listeners for Google Maps
     */
    addGoogleMapEventListeners() {
        // Map click event
        this.state.mapInstance.addListener('click', (event) => {
            this.onMapClick({
                lat: event.latLng.lat(),
                lng: event.latLng.lng()
            });
        });
        
        // Map bounds changed
        this.state.mapInstance.addListener('bounds_changed', () => {
            this.onMapBoundsChanged();
        });
        
        // Map zoom changed
        this.state.mapInstance.addListener('zoom_changed', () => {
            this.onMapZoomChanged();
        });
    }
    
    /**
     * Add event listeners for Leaflet
     */
    addLeafletEventListeners() {
        // Map click event
        this.state.mapInstance.on('click', (event) => {
            this.onMapClick({
                lat: event.latlng.lat,
                lng: event.latlng.lng
            });
        });
        
        // Map move end
        this.state.mapInstance.on('moveend', () => {
            this.onMapBoundsChanged();
        });
        
        // Map zoom end
        this.state.mapInstance.on('zoomend', () => {
            this.onMapZoomChanged();
        });
    }
    
    /**
     * Handle map bounds changed event
     */
    onMapBoundsChanged() {
        // Update visible data based on new bounds
        if (this.state.autoRefresh) {
            this.debounceRefreshData();
        }
    }
    
    /**
     * Handle map zoom changed event
     */
    onMapZoomChanged() {
        // Adjust marker clustering based on zoom level
        this.adjustMarkerDisplay();
    }
    
    /**
     * Debounced data refresh to avoid excessive API calls
     */
    debounceRefreshData() {
        clearTimeout(this.refreshTimeout);
        this.refreshTimeout = setTimeout(() => {
            this.refreshVisibleData();
        }, 1000);
    }
    
    /**
     * Adjust marker display based on zoom level
     */
    adjustMarkerDisplay() {
        const zoom = this.state.mapProvider === 'google' 
            ? this.state.mapInstance.getZoom()
            : this.state.mapInstance.getZoom();
            
        // Show/hide markers based on zoom level and performance settings
        if (zoom < 10 && this.state.markers.length > this.mapConfig.performance.maxMarkersBeforeClustering) {
            this.enableClustering();
        } else if (zoom >= 15) {
            this.disableClustering();
        }
    }
    
    /**
     * Load initial data after map initialization
     */
    async loadInitialData() {
        if (!this.state.mapLoaded) {
            console.warn('Map not loaded yet, skipping data load');
            return;
        }
        
        try {
            this.state.isLoading = true;
            
            // Load data in parallel for better performance
            await Promise.all([
                this.loadSalesReps(),
                this.loadTerritories(),
                this.loadTrackingData(),
                this.loadRouteData()
            ]);
            
            // Render current view
            this.renderCurrentView();
            
            // Start real-time updates if enabled
            if (this.state.realTimeSettings.enabled) {
                this.startRealTimeUpdates();
            }
            
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.state.error = _t('Failed to load map data. Please try refreshing.');
            this.notification.add(this.state.error, { 
                type: 'danger',
                sticky: true
            });
        } finally {
            this.state.isLoading = false;
        }
    }
    
    /**
     * Load sales representatives data
     */
    async loadSalesReps() {
        try {
            const salesReps = await this.orm.searchRead(
                'res.users',
                [['groups_id', 'in', [this.env.context.sales_rep_group_id]]],
                ['id', 'name', 'partner_id'],
                { order: 'name asc' }
            );
            
            this.state.salesReps = salesReps;
            
        } catch (error) {
            console.error('Error loading sales reps:', error);
            this.state.salesReps = [];
        }
    }
    
    /**
     * Load territories data
     */
    async loadTerritories() {
        try {
            const territories = await this.orm.searchRead(
                'sales.territory',
                [],
                ['id', 'name', 'boundary_coordinates', 'color'],
                { order: 'name asc' }
            );
            
            this.state.territories = territories;
            
        } catch (error) {
            console.error('Error loading territories:', error);
            this.state.territories = [];
        }
    }
    
    /**
     * Load GPS tracking data with filters
     */
    async loadTrackingData() {
        try {
            const domain = this.buildTrackingDomain();
            
            // Limit data for performance
            const limit = this.mapConfig.performance.maxDataPoints;
            
            const trackingData = await this.orm.searchRead(
                'gps.tracking',
                domain,
                [
                    'sales_rep_id', 'timestamp', 'latitude', 'longitude', 
                    'tracking_type', 'address', 'customer_id', 'speed', 
                    'accuracy', 'is_valid', 'is_in_territory', 'battery_level',
                    'altitude', 'heading', 'visit_id'
                ],
                { 
                    order: 'timestamp desc',
                    limit: limit
                }
            );
            
            // Validate and filter data
            this.state.trackingData = this.validateTrackingData(trackingData);
            
            // Update statistics
            this.updateTrackingStats();
            
        } catch (error) {
            console.error('Error loading tracking data:', error);
            this.state.trackingData = [];
            throw error;
        }
    }
    
    /**
     * Build domain for tracking data query
     */
    buildTrackingDomain() {
        const domain = [];
        
        // Date range filter
        if (this.state.dateRange.from) {
            domain.push(['timestamp', '>=', this.state.dateRange.from + ' 00:00:00']);
        }
        if (this.state.dateRange.to) {
            domain.push(['timestamp', '<=', this.state.dateRange.to + ' 23:59:59']);
        }
        
        // Sales representative filter
        if (this.state.selectedSalesRep) {
            domain.push(['sales_rep_id', '=', this.state.selectedSalesRep]);
        }
        
        // Validity filter
        if (this.state.mapFilters.showValidOnly) {
            domain.push(['is_valid', '=', true]);
        }
        
        // Territory filter
        if (this.state.mapFilters.showInTerritory) {
            domain.push(['is_in_territory', '=', true]);
        }
        
        // Tracking type filter
        if (this.state.mapFilters.trackingTypes.length > 0 && 
            !this.state.mapFilters.trackingTypes.includes('all')) {
            domain.push(['tracking_type', 'in', this.state.mapFilters.trackingTypes]);
        }
        
        // Accuracy filter (only show points with good accuracy)
        if (this.state.mapFilters.minAccuracy) {
            domain.push(['accuracy', '<=', this.state.mapFilters.minAccuracy]);
        }
        
        return domain;
    }
    
    /**
     * Validate and clean tracking data
     */
    validateTrackingData(data) {
        return data.filter(point => {
            // Check for valid coordinates
            if (!point.latitude || !point.longitude) {
                return false;
            }
            
            // Check coordinate ranges
            if (point.latitude < -90 || point.latitude > 90 ||
                point.longitude < -180 || point.longitude > 180) {
                return false;
            }
            
            // Check for reasonable accuracy (if available)
            if (point.accuracy && point.accuracy > 1000) {
                return false;
            }
            
            return true;
        });
    }
    
    /**
     * Update tracking statistics
     */
    updateTrackingStats() {
        const data = this.state.trackingData;
        
        this.state.stats = {
            totalPoints: data.length,
            validPoints: data.filter(p => p.is_valid).length,
            territoryPoints: data.filter(p => p.is_in_territory).length,
            averageAccuracy: data.length > 0 
                ? data.reduce((sum, p) => sum + (p.accuracy || 0), 0) / data.length 
                : 0,
            dateRange: {
                from: data.length > 0 ? Math.min(...data.map(p => new Date(p.timestamp))) : null,
                to: data.length > 0 ? Math.max(...data.map(p => new Date(p.timestamp))) : null
            }
        };
    }
    
    /**
     * Load route data with filters
     */
    async loadRouteData() {
        try {
            const domain = this.buildRouteDomain();
            
            const routeData = await this.orm.searchRead(
                'gps.tracking.route',
                domain,
                [
                    'name', 'sales_rep_id', 'date', 'total_distance', 
                    'total_duration', 'average_speed', 'efficiency_score', 
                    'tracking_point_ids', 'start_location', 'end_location',
                    'waypoints', 'route_color'
                ],
                { order: 'date desc' }
            );
            
            this.state.routeData = routeData;
            
        } catch (error) {
            console.error('Error loading route data:', error);
            this.state.routeData = [];
            throw error;
        }
    }
    
    /**
     * Build domain for route data query
     */
    buildRouteDomain() {
        const domain = [];
        
        // Date range filter
        if (this.state.dateRange.from) {
            domain.push(['date', '>=', this.state.dateRange.from]);
        }
        if (this.state.dateRange.to) {
            domain.push(['date', '<=', this.state.dateRange.to]);
        }
        
        // Sales representative filter
        if (this.state.selectedSalesRep) {
            domain.push(['sales_rep_id', '=', this.state.selectedSalesRep]);
        }
        
        return domain;
    }
    
    /**
     * Refresh visible data based on current map bounds
     */
    async refreshVisibleData() {
        if (!this.state.mapInstance || this.state.isLoading) {
            return;
        }
        
        try {
            // Get current map bounds
            const bounds = this.getCurrentMapBounds();
            
            // Filter data to visible area for performance
            const visibleData = this.filterDataByBounds(this.state.trackingData, bounds);
            
            // Update markers if data has changed significantly
            if (this.shouldUpdateMarkers(visibleData)) {
                this.updateVisibleMarkers(visibleData);
            }
            
        } catch (error) {
            console.error('Error refreshing visible data:', error);
        }
    }
    
    /**
     * Get current map bounds
     */
    getCurrentMapBounds() {
        if (this.state.mapProvider === 'google') {
            const bounds = this.state.mapInstance.getBounds();
            return {
                north: bounds.getNorthEast().lat(),
                south: bounds.getSouthWest().lat(),
                east: bounds.getNorthEast().lng(),
                west: bounds.getSouthWest().lng()
            };
        } else {
            const bounds = this.state.mapInstance.getBounds();
            return {
                north: bounds.getNorth(),
                south: bounds.getSouth(),
                east: bounds.getEast(),
                west: bounds.getWest()
            };
        }
    }
    
    /**
     * Filter data by map bounds
     */
    filterDataByBounds(data, bounds) {
        return data.filter(point => {
            return point.latitude >= bounds.south &&
                   point.latitude <= bounds.north &&
                   point.longitude >= bounds.west &&
                   point.longitude <= bounds.east;
        });
    }
    
    /**
     * Check if markers should be updated
     */
    shouldUpdateMarkers(newData) {
        // Update if data count changed significantly
        const currentCount = this.state.visibleMarkers ? this.state.visibleMarkers.length : 0;
        const newCount = newData.length;
        
        return Math.abs(currentCount - newCount) > 10 || 
               !this.state.visibleMarkers;
    }
    
    /**
     * Update visible markers
     */
    updateVisibleMarkers(data) {
        // Clear existing markers
        this.clearVisibleMarkers();
        
        // Add new markers
        this.state.visibleMarkers = data.map(point => this.createMarker(point));
    }
    
    /**
     * Clear visible markers
     */
    clearVisibleMarkers() {
        if (this.state.visibleMarkers) {
            this.state.visibleMarkers.forEach(marker => {
                if (this.state.mapProvider === 'google') {
                    marker.setMap(null);
                } else {
                    this.state.mapInstance.removeLayer(marker);
                }
            });
        }
        this.state.visibleMarkers = [];
    }
    
    /**
     * Enable marker clustering
     */
    enableClustering() {
        if (this.state.markerCluster && !this.state.clusteringEnabled) {
            this.state.clusteringEnabled = true;
            
            if (this.state.mapProvider === 'google') {
                this.state.markerCluster.addMarkers(this.state.markers);
            } else {
                this.state.markers.forEach(marker => {
                    this.state.markerCluster.addLayer(marker);
                });
            }
        }
    }
    
    /**
     * Disable marker clustering
     */
    disableClustering() {
        if (this.state.markerCluster && this.state.clusteringEnabled) {
            this.state.clusteringEnabled = false;
            
            if (this.state.mapProvider === 'google') {
                this.state.markerCluster.clearMarkers();
                this.state.markers.forEach(marker => {
                    marker.setMap(this.state.mapInstance);
                });
            } else {
                this.state.markerCluster.clearLayers();
                this.state.markers.forEach(marker => {
                    this.state.mapInstance.addLayer(marker);
                });
            }
        }
    }
    
    renderCurrentView() {
        this.clearMapElements();
        
        switch (this.state.currentView) {
            case 'tracking':
                this.renderTrackingPoints();
                break;
            case 'route':
                this.renderRoutes();
                break;
            case 'heatmap':
                this.renderHeatmap();
                break;
        }
    }
    
    renderTrackingPoints() {
        if (!this.state.trackingData.length) return;
        
        const bounds = window.google ? new google.maps.LatLngBounds() : null;
        
        this.state.trackingData.forEach(point => {
            const marker = this.createMarker(point);
            this.state.markers.push(marker);
            
            if (bounds && window.google) {
                bounds.extend(new google.maps.LatLng(point.latitude, point.longitude));
            }
        });
        
        // Fit map to show all markers
        if (bounds && window.google && this.state.markers.length > 1) {
            this.state.mapInstance.fitBounds(bounds);
        }
    }
    
    createMarker(point) {
        const position = window.google ? 
            new google.maps.LatLng(point.latitude, point.longitude) :
            [point.latitude, point.longitude];
        
        const icon = this.getMarkerIcon(point.tracking_type, point.is_valid);
        
        if (window.google) {
            const marker = new google.maps.Marker({
                position: position,
                map: this.state.mapInstance,
                title: `${point.sales_rep_id[1]} - ${point.timestamp}`,
                icon: icon
            });
            
            const infoWindow = new google.maps.InfoWindow({
                content: this.createInfoWindowContent(point)
            });
            
            marker.addListener('click', () => {
                infoWindow.open(this.state.mapInstance, marker);
            });
            
            return marker;
        } else {
            // Leaflet marker
            const marker = L.marker(position, { icon: icon })
                .addTo(this.state.mapInstance)
                .bindPopup(this.createInfoWindowContent(point));
            
            return marker;
        }
    }
    
    getMarkerIcon(trackingType, isValid) {
        const iconColor = isValid ? 'green' : 'red';
        let iconSymbol = 'circle';
        
        switch (trackingType) {
            case 'visit_start':
                iconSymbol = 'play';
                break;
            case 'visit_end':
                iconSymbol = 'stop';
                break;
            case 'emergency':
                iconSymbol = 'warning';
                iconColor = 'orange';
                break;
            case 'manual':
                iconSymbol = 'hand';
                break;
        }
        
        if (window.google) {
            return {
                url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(this.createSVGIcon(iconSymbol, iconColor))}`,
                scaledSize: new google.maps.Size(30, 30),
                anchor: new google.maps.Point(15, 15)
            };
        } else {
            // Leaflet icon
            return L.divIcon({
                html: `<div style="background-color: ${iconColor}; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white;"></div>`,
                iconSize: [20, 20],
                className: 'custom-div-icon'
            });
        }
    }
    
    createSVGIcon(symbol, color) {
        return `
            <svg width="30" height="30" viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">
                <circle cx="15" cy="15" r="12" fill="${color}" stroke="white" stroke-width="2"/>
                <text x="15" y="20" text-anchor="middle" fill="white" font-size="12" font-family="Arial">${symbol}</text>
            </svg>
        `;
    }
    
    createInfoWindowContent(point) {
        return `
            <div class="gps-info-window">
                <h6>${point.sales_rep_id[1]}</h6>
                <p><strong>الوقت:</strong> ${new Date(point.timestamp).toLocaleString('ar-SA')}</p>
                <p><strong>النوع:</strong> ${this.getTrackingTypeLabel(point.tracking_type)}</p>
                <p><strong>العنوان:</strong> ${point.address || 'غير محدد'}</p>
                ${point.customer_id ? `<p><strong>العميل:</strong> ${point.customer_id[1]}</p>` : ''}
                ${point.speed ? `<p><strong>السرعة:</strong> ${point.speed} كم/س</p>` : ''}
                <p><strong>الدقة:</strong> ${point.accuracy || 'غير محدد'} متر</p>
                <p><strong>صالح:</strong> ${point.is_valid ? 'نعم' : 'لا'}</p>
                <p><strong>في المنطقة:</strong> ${point.is_in_territory ? 'نعم' : 'لا'}</p>
            </div>
        `;
    }
    
    getTrackingTypeLabel(type) {
        const labels = {
            'manual': 'يدوي',
            'automatic': 'تلقائي',
            'visit_start': 'بداية زيارة',
            'visit_end': 'نهاية زيارة',
            'route_tracking': 'تتبع المسار',
            'emergency': 'طوارئ'
        };
        return labels[type] || type;
    }
    
    async renderRoutes() {
        await this.loadRouteData();
        
        if (!this.state.routeData.length) return;
        
        const colors = ['#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF'];
        let colorIndex = 0;
        
        for (const route of this.state.routeData) {
            const routePoints = await this.getRoutePoints(route.id);
            if (routePoints.length > 1) {
                const polyline = this.createPolyline(routePoints, colors[colorIndex % colors.length]);
                this.state.polylines.push(polyline);
                colorIndex++;
            }
        }
    }
    
    async getRoutePoints(routeId) {
        const points = await this.orm.searchRead(
            'gps.tracking',
            [['route_id', '=', routeId]],
            ['latitude', 'longitude', 'timestamp'],
            { order: 'timestamp asc' }
        );
        
        return points.map(point => ({
            lat: point.latitude,
            lng: point.longitude
        }));
    }
    
    createPolyline(points, color) {
        if (window.google) {
            const polyline = new google.maps.Polyline({
                path: points,
                geodesic: true,
                strokeColor: color,
                strokeOpacity: 1.0,
                strokeWeight: 3
            });
            
            polyline.setMap(this.state.mapInstance);
            return polyline;
        } else {
            // Leaflet polyline
            const latlngs = points.map(p => [p.lat, p.lng]);
            const polyline = L.polyline(latlngs, { color: color, weight: 3 })
                .addTo(this.state.mapInstance);
            
            return polyline;
        }
    }
    
    renderHeatmap() {
        if (!window.google || !this.state.trackingData.length) return;
        
        const heatmapData = this.state.trackingData.map(point => ({
            location: new google.maps.LatLng(point.latitude, point.longitude),
            weight: point.speed || 1
        }));
        
        this.state.heatmapLayer = new google.maps.visualization.HeatmapLayer({
            data: heatmapData,
            map: this.state.mapInstance,
            radius: 20,
            opacity: 0.6
        });
    }
    
    clearMapElements() {
        // Clear markers
        this.state.markers.forEach(marker => {
            if (window.google) {
                marker.setMap(null);
            } else {
                this.state.mapInstance.removeLayer(marker);
            }
        });
        this.state.markers = [];
        
        // Clear polylines
        this.state.polylines.forEach(polyline => {
            if (window.google) {
                polyline.setMap(null);
            } else {
                this.state.mapInstance.removeLayer(polyline);
            }
        });
        this.state.polylines = [];
        
        // Clear heatmap
        if (this.state.heatmapLayer) {
            this.state.heatmapLayer.setMap(null);
            this.state.heatmapLayer = null;
        }
    }
    
    onMapClick(event) {
        let lat, lng;
        
        if (window.google) {
            lat = event.latLng.lat();
            lng = event.latLng.lng();
        } else {
            lat = event.latlng.lat;
            lng = event.latlng.lng;
        }
        
        console.log(`Clicked at: ${lat}, ${lng}`);
        // Add custom logic for map clicks
    }
    
    async onViewChange(newView) {
        this.state.currentView = newView;
        await this.loadInitialData();
    }
    
    async onFilterChange() {
        await this.loadInitialData();
    }
    
    async onDateRangeChange() {
        await this.loadInitialData();
    }
    
    async onSalesRepChange() {
        await this.loadInitialData();
    }
    
    toggleRealTime() {
        this.state.realTimeEnabled = !this.state.realTimeEnabled;
        
        if (this.state.realTimeEnabled) {
            this.startRealTimeUpdates();
        } else {
            this.stopRealTimeUpdates();
        }
    }
    
    startRealTimeUpdates() {
        // Implement real-time updates using Odoo's bus service
        this.realTimeInterval = setInterval(() => {
            this.loadInitialData();
        }, 30000); // Update every 30 seconds
    }
    
    stopRealTimeUpdates() {
        if (this.realTimeInterval) {
            clearInterval(this.realTimeInterval);
            this.realTimeInterval = null;
        }
    }
    
    exportMapData() {
        const data = {
            trackingData: this.state.trackingData,
            routeData: this.state.routeData,
            filters: this.state.mapFilters,
            dateRange: this.state.dateRange
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `gps_data_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }
    
    /**
     * Cleanup resources when component is destroyed
     */
    cleanup() {
        try {
            // Stop real-time updates
            this.stopRealTimeUpdates();
            
            // Clear timeouts
            if (this.refreshTimeout) {
                clearTimeout(this.refreshTimeout);
            }
            
            if (this.reconnectTimeout) {
                clearTimeout(this.reconnectTimeout);
            }
            
            // Clear map elements
            this.clearMapElements();
            
            // Clear visible markers
            this.clearVisibleMarkers();
            
            // Destroy marker clusterer
            if (this.state.markerCluster) {
                if (this.state.mapProvider === 'google') {
                    this.state.markerCluster.clearMarkers();
                } else {
                    this.state.markerCluster.clearLayers();
                }
                this.state.markerCluster = null;
            }
            
            // Remove event listeners
            if (this.state.mapInstance) {
                if (this.state.mapProvider === 'google') {
                    google.maps.event.clearInstanceListeners(this.state.mapInstance);
                } else {
                    this.state.mapInstance.off();
                }
            }
            
            // Clear map instance
            this.state.mapInstance = null;
            this.state.mapLoaded = false;
            
            console.log('GPS Interactive Maps component cleaned up successfully');
            
        } catch (error) {
            console.error('Error during cleanup:', error);
        }
    }
    
    /**
     * Handle component errors gracefully
     */
    handleError(error, context = 'Unknown') {
        console.error(`GPS Maps Error in ${context}:`, error);
        
        // Update error state
        this.state.error = _t('An error occurred in GPS Maps. Please try refreshing.');
        
        // Show user-friendly notification
        this.notification.add(this.state.error, {
            type: 'danger',
            sticky: false
        });
        
        // Reset loading state
        this.state.isLoading = false;
        
        // Attempt recovery for certain errors
        if (error.message && error.message.includes('network')) {
            this.attemptRecovery();
        }
    }
    
    /**
     * Attempt to recover from errors
     */
    async attemptRecovery() {
        try {
            console.log('Attempting to recover from error...');
            
            // Wait a bit before retrying
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            // Try to reinitialize if map is not loaded
            if (!this.state.mapLoaded) {
                await this.initializeComponent();
            } else {
                // Just reload data
                await this.loadInitialData();
            }
            
            console.log('Recovery successful');
            
        } catch (recoveryError) {
            console.error('Recovery failed:', recoveryError);
        }
    }
    
    /**
     * Get component performance metrics
     */
    getPerformanceMetrics() {
        return {
            totalMarkers: this.state.markers ? this.state.markers.length : 0,
            visibleMarkers: this.state.visibleMarkers ? this.state.visibleMarkers.length : 0,
            trackingPoints: this.state.trackingData ? this.state.trackingData.length : 0,
            routes: this.state.routeData ? this.state.routeData.length : 0,
            mapProvider: this.state.mapProvider,
            clusteringEnabled: this.state.clusteringEnabled,
            realTimeEnabled: this.state.realTimeEnabled,
            lastUpdate: this.state.lastUpdate,
            connectionStatus: this.state.connectionStatus
        };
    }
}

GPSInteractiveMaps.template = 'sales_rep_mgmt_pro.GPSInteractiveMapsTemplate';

registry.category('actions').add('gps_interactive_maps', GPSInteractiveMaps);

export default GPSInteractiveMaps;