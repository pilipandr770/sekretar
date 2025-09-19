/**
 * UI State Manager
 * Manages centralized UI state and synchronization across components
 */

class UIStateManager {
    constructor() {
        this.state = {
            isAuthenticated: false,
            currentUser: null,
            currentLanguage: 'en',
            isWebSocketConnected: false,
            activeNavItem: null,
            notifications: [],
            isLoading: false
        };
        this.subscribers = [];
        this.isInitialized = false;
    }

    /**
     * Initialize the UI state manager
     */
    init() {
        if (this.isInitialized) {
            return;
        }

        console.log('Initializing UI State Manager...');
        
        // Detect current language
        this.state.currentLanguage = document.documentElement.lang || 'en';
        
        // Detect active navigation item
        this.updateActiveNavItem();
        
        // Set up event listeners
        this.setupEventListeners();
        
        this.isInitialized = true;
        console.log('UI State Manager initialized');
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Listen for navigation changes
        window.addEventListener('popstate', () => {
            this.updateActiveNavItem();
        });

        // Listen for language changes
        window.addEventListener('localechange', (event) => {
            this.updateState({
                currentLanguage: event.detail.locale
            });
        });

        // Listen for language persistence manager events
        window.addEventListener('languagechange', (event) => {
            this.updateState({
                currentLanguage: event.detail.language
            });
        });

        // Listen for WebSocket events
        document.addEventListener('websocket:connected', () => {
            this.updateState({
                isWebSocketConnected: true
            });
        });

        document.addEventListener('websocket:disconnected', () => {
            this.updateState({
                isWebSocketConnected: false
            });
        });

        // Listen for WebSocket status changes
        document.addEventListener('websocket:status_change', (event) => {
            this.updateState({
                isWebSocketConnected: event.detail.status === 'connected'
            });
        });

        // Listen for authentication events
        document.addEventListener('user:login', (event) => {
            this.updateState({
                isAuthenticated: true,
                currentUser: event.detail.user
            });
        });

        document.addEventListener('user:logout', () => {
            this.updateState({
                isAuthenticated: false,
                currentUser: null
            });
        });

        // Listen for page load events (for AJAX navigation)
        document.addEventListener('page:loaded', () => {
            this.updateActiveNavItem();
        });

        // Listen for notification events
        document.addEventListener('notification:received', (event) => {
            this.addNotification({
                type: 'info',
                title: event.detail.title || 'Notification',
                message: event.detail.message,
                source: 'websocket'
            });
        });

        document.addEventListener('notification:tenant', (event) => {
            this.addNotification({
                type: 'warning',
                title: event.detail.title || 'System Notification',
                message: event.detail.message,
                source: 'system'
            });
        });

        document.addEventListener('alert:system', (event) => {
            this.addNotification({
                type: 'danger',
                title: event.detail.title || 'System Alert',
                message: event.detail.message,
                urgent: event.detail.urgent,
                source: 'system'
            });
        });
    }

    /**
     * Update the UI state
     */
    updateState(newState) {
        const oldState = { ...this.state };
        this.state = { ...this.state, ...newState };
        
        // Notify subscribers of state change
        this.notifySubscribers(this.state, oldState);
    }

    /**
     * Get current state
     */
    getState() {
        return { ...this.state };
    }

    /**
     * Subscribe to state changes
     */
    subscribe(callback) {
        if (typeof callback === 'function') {
            this.subscribers.push(callback);
        }
    }

    /**
     * Unsubscribe from state changes
     */
    unsubscribe(callback) {
        const index = this.subscribers.indexOf(callback);
        if (index > -1) {
            this.subscribers.splice(index, 1);
        }
    }

    /**
     * Notify all subscribers of state changes
     */
    notifySubscribers(newState, oldState) {
        this.subscribers.forEach(callback => {
            try {
                callback(newState, oldState);
            } catch (error) {
                console.error('UI state subscriber error:', error);
            }
        });
    }

    /**
     * Update authentication state
     */
    updateAuthState(isAuthenticated, user) {
        this.updateState({
            isAuthenticated,
            currentUser: user
        });
    }

    /**
     * Update active navigation item
     */
    updateActiveNavItem() {
        const currentPath = window.location.pathname;
        let activeItem = null;

        // Determine active nav item based on current path
        if (currentPath.includes('/dashboard')) {
            activeItem = 'dashboard';
        } else if (currentPath.includes('/inbox')) {
            activeItem = 'inbox';
        } else if (currentPath.includes('/crm')) {
            activeItem = 'crm';
        } else if (currentPath.includes('/calendar')) {
            activeItem = 'calendar';
        } else if (currentPath.includes('/settings')) {
            activeItem = 'settings';
        } else if (currentPath.includes('/users')) {
            activeItem = 'users';
        }

        if (activeItem !== this.state.activeNavItem) {
            this.updateState({ activeNavItem: activeItem });
        }
    }

    /**
     * Highlight active navigation item (now handled by NavigationController)
     */
    highlightActiveNavItem(activeItem) {
        // This is now handled by NavigationController
        // Method kept for backward compatibility
        console.log('Active nav item:', activeItem);
    }

    /**
     * Add notification
     */
    addNotification(notification) {
        const notifications = [...this.state.notifications, {
            id: Date.now(),
            timestamp: new Date(),
            ...notification
        }];
        
        this.updateState({ notifications });
    }

    /**
     * Remove notification
     */
    removeNotification(id) {
        const notifications = this.state.notifications.filter(n => n.id !== id);
        this.updateState({ notifications });
    }

    /**
     * Clear all notifications
     */
    clearNotifications() {
        this.updateState({ notifications: [] });
    }

    /**
     * Set loading state
     */
    setLoading(isLoading) {
        this.updateState({ isLoading });
    }

    /**
     * Update language state
     */
    updateLanguage(language) {
        this.updateState({ currentLanguage: language });
    }

    /**
     * Update WebSocket connection state
     */
    updateWebSocketState(isConnected) {
        this.updateState({ isWebSocketConnected: isConnected });
    }

    /**
     * Get specific state property
     */
    get(property) {
        return this.state[property];
    }

    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        return this.state.isAuthenticated;
    }

    /**
     * Get current user
     */
    getCurrentUser() {
        return this.state.currentUser;
    }

    /**
     * Get current language
     */
    getCurrentLanguage() {
        return this.state.currentLanguage;
    }

    /**
     * Check WebSocket connection status
     */
    isWebSocketConnected() {
        return this.state.isWebSocketConnected;
    }

    /**
     * Get active navigation item
     */
    getActiveNavItem() {
        return this.state.activeNavItem;
    }

    /**
     * Get notifications
     */
    getNotifications() {
        return [...this.state.notifications];
    }

    /**
     * Check if loading
     */
    isLoading() {
        return this.state.isLoading;
    }

    /**
     * Integrate with authentication manager
     */
    integrateWithAuthManager(authManager) {
        if (!authManager) return;

        // Subscribe to auth state changes
        authManager.onAuthStateChange((isAuthenticated, user) => {
            this.updateAuthState(isAuthenticated, user);
        });

        // Set initial auth state
        const authState = authManager.getAuthState();
        this.updateAuthState(authState.isAuthenticated, authState.user);
    }

    /**
     * Integrate with navigation controller
     */
    integrateWithNavigationController(navigationController) {
        if (!navigationController) return;

        // Subscribe to navigation changes
        this.subscribe((newState, oldState) => {
            if (newState.activeNavItem !== oldState.activeNavItem) {
                // Notify navigation controller of state changes if needed
                console.log('Navigation state updated:', newState.activeNavItem);
            }
        });
    }

    /**
     * Integrate with WebSocket client
     */
    integrateWithWebSocketClient(wsClient) {
        if (!wsClient) return;

        // Subscribe to WebSocket events
        wsClient.on('websocket:connected', () => {
            this.updateWebSocketState(true);
        });

        wsClient.on('websocket:disconnected', () => {
            this.updateWebSocketState(false);
        });

        wsClient.on('websocket:status_change', (event) => {
            this.updateWebSocketState(event.detail.status === 'connected');
        });
    }

    /**
     * Integrate with language switcher
     */
    integrateWithLanguageSwitcher(languageSwitcher) {
        if (!languageSwitcher) return;

        // Subscribe to language changes
        this.subscribe((newState, oldState) => {
            if (newState.currentLanguage !== oldState.currentLanguage) {
                // Emit language change event for other components
                document.dispatchEvent(new CustomEvent('ui:language_changed', {
                    detail: { 
                        language: newState.currentLanguage,
                        previousLanguage: oldState.currentLanguage
                    }
                }));
            }
        });
    }

    /**
     * Synchronize state with all integrated components
     */
    synchronizeState() {
        // Emit state synchronization event
        document.dispatchEvent(new CustomEvent('ui:state_sync', {
            detail: { state: this.getState() }
        }));

        // Update all UI elements based on current state
        this.updateUIElements();
    }

    /**
     * Update UI elements based on current state
     */
    updateUIElements() {
        // Update authentication-related UI
        if (this.state.isAuthenticated) {
            document.body.classList.add('authenticated');
            document.body.classList.remove('unauthenticated');
        } else {
            document.body.classList.add('unauthenticated');
            document.body.classList.remove('authenticated');
        }

        // Update WebSocket connection indicator
        if (this.state.isWebSocketConnected) {
            document.body.classList.add('websocket-connected');
            document.body.classList.remove('websocket-disconnected');
        } else {
            document.body.classList.add('websocket-disconnected');
            document.body.classList.remove('websocket-connected');
        }

        // Update language attribute
        if (this.state.currentLanguage) {
            document.documentElement.lang = this.state.currentLanguage;
        }

        // Update loading state
        if (this.state.isLoading) {
            document.body.classList.add('loading');
        } else {
            document.body.classList.remove('loading');
        }

        // Update active navigation
        this.highlightActiveNavigation();
    }

    /**
     * Highlight active navigation item
     */
    highlightActiveNavigation() {
        // Remove active class from all nav items
        document.querySelectorAll('#main-nav .nav-link').forEach(link => {
            link.classList.remove('active');
        });

        // Add active class to current nav item
        if (this.state.activeNavItem) {
            const activeLink = document.querySelector(`#main-nav .nav-link[href*="${this.state.activeNavItem}"]`);
            if (activeLink) {
                activeLink.classList.add('active');
            }
        }
    }

    /**
     * Get state snapshot for debugging
     */
    getStateSnapshot() {
        return {
            timestamp: new Date().toISOString(),
            state: { ...this.state },
            subscriberCount: this.subscribers.length,
            isInitialized: this.isInitialized
        };
    }

    /**
     * Validate state integrity
     */
    validateState() {
        const issues = [];

        // Check for required properties
        const requiredProps = ['isAuthenticated', 'currentLanguage', 'isWebSocketConnected'];
        requiredProps.forEach(prop => {
            if (this.state[prop] === undefined) {
                issues.push(`Missing required property: ${prop}`);
            }
        });

        // Check data types
        if (typeof this.state.isAuthenticated !== 'boolean') {
            issues.push('isAuthenticated must be boolean');
        }

        if (typeof this.state.isWebSocketConnected !== 'boolean') {
            issues.push('isWebSocketConnected must be boolean');
        }

        if (typeof this.state.currentLanguage !== 'string') {
            issues.push('currentLanguage must be string');
        }

        if (!Array.isArray(this.state.notifications)) {
            issues.push('notifications must be array');
        }

        return {
            isValid: issues.length === 0,
            issues: issues
        };
    }

    /**
     * Reset state to defaults
     */
    resetState() {
        this.state = {
            isAuthenticated: false,
            currentUser: null,
            currentLanguage: 'en',
            isWebSocketConnected: false,
            activeNavItem: null,
            notifications: [],
            isLoading: false
        };

        this.notifySubscribers(this.state, {});
        this.updateUIElements();
    }

    /**
     * Cleanup
     */
    cleanup() {
        // Remove all event listeners
        window.removeEventListener('popstate', this.updateActiveNavItem);
        
        // Clear subscribers
        this.subscribers = [];
        
        // Reset state
        this.isInitialized = false;
        
        console.log('UI State Manager cleaned up');
    }
}

// Export for use in other modules
window.UIStateManager = UIStateManager;