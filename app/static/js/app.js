// AI Secretary Main Application JavaScript

class AISecretaryApp {
    constructor() {
        this.baseURL = window.location.origin;
        this.currentUser = null;
        this.authManager = null;
        this.uiStateManager = null;
        this.navigationController = null;
        this.dropdownManager = null;
        this.init();
    }

    async init() {
        console.log('Initializing AI Secretary App...');
        
        // Initialize UI state manager
        this.initUIState();
        
        // Initialize authentication manager
        await this.initAuth();
        
        // Initialize navigation controller
        this.initNavigation();
        
        // Initialize dropdown manager
        this.initDropdowns();
        
        // Initialize i18n system (now async)
        await this.initI18n();
        
        // Initialize API Tester (if on API tester page)
        if (document.querySelector('.api-tester')) {
            this.initAPITester();
        }
        
        // Initialize forms (excluding login form - handled by auth manager)
        this.initForms();
        
        console.log('AI Secretary App initialized');
    }

    initUIState() {
        // Initialize the UI state manager
        this.uiStateManager = new UIStateManager();
        this.uiStateManager.init();
        
        // Subscribe to UI state changes
        this.uiStateManager.subscribe((newState, oldState) => {
            this.onUIStateChange(newState, oldState);
        });

        // Make it globally available for other components
        window.uiStateManager = this.uiStateManager;
    }

    onUIStateChange(newState, oldState) {
        // Handle UI state changes
        if (newState.isWebSocketConnected !== oldState.isWebSocketConnected) {
            console.log('WebSocket connection state changed:', newState.isWebSocketConnected);
            
            // Update connection-dependent features
            if (newState.isWebSocketConnected) {
                this.enableRealtimeFeatures();
            } else {
                this.showConnectionLostWarning();
            }
        }
        
        if (newState.currentLanguage !== oldState.currentLanguage) {
            console.log('Language changed:', newState.currentLanguage);
            
            // Update translatable elements
            this.updateTranslatableElements();
            
            // Update date/time displays
            this.updateDateTimeDisplays();
        }

        if (newState.isAuthenticated !== oldState.isAuthenticated) {
            console.log('Authentication state changed:', newState.isAuthenticated);
            
            // Handle authentication state changes
            if (newState.isAuthenticated) {
                this.onUserAuthenticated(newState.currentUser);
            } else {
                this.onUserUnauthenticated();
            }
        }

        if (newState.activeNavItem !== oldState.activeNavItem) {
            console.log('Active navigation changed:', newState.activeNavItem);
            
            // Update page-specific features
            this.updatePageSpecificFeatures(newState.activeNavItem);
        }

        if (newState.notifications.length !== oldState.notifications.length) {
            console.log('Notifications updated:', newState.notifications.length);
            
            // Update notification display
            this.updateNotificationDisplay(newState.notifications);
        }

        if (newState.isLoading !== oldState.isLoading) {
            console.log('Loading state changed:', newState.isLoading);
            
            // Update loading indicators
            this.updateLoadingIndicators(newState.isLoading);
        }
    }

    async initAuth() {
        // Initialize the enhanced authentication manager
        this.authManager = new AuthenticationManager();
        await this.authManager.init();
        
        // Integrate with UI state manager
        if (this.uiStateManager) {
            this.uiStateManager.integrateWithAuthManager(this.authManager);
        }
        
        // Register for auth state changes
        this.authManager.onAuthStateChange((isAuthenticated, user) => {
            this.currentUser = user;
            this.onAuthStateChange(isAuthenticated, user);
        });
        
        // Set initial user state
        this.currentUser = this.authManager.getCurrentUser();
    }

    onAuthStateChange(isAuthenticated, user) {
        console.log('Auth state changed:', isAuthenticated, user);
        
        // Update UI state manager
        if (this.uiStateManager) {
            this.uiStateManager.updateAuthState(isAuthenticated, user);
        }
        
        // Update any app-specific UI elements
        if (isAuthenticated) {
            // Enable real-time features
            this.enableRealtimeFeatures();
        } else {
            // Disable real-time features
            this.disableRealtimeFeatures();
        }
    }

    enableRealtimeFeatures() {
        // Initialize WebSocket connection if authenticated
        if (window.WebSocketClient && !window.wsClient) {
            window.wsClient = new WebSocketClient();
            
            // Integrate with UI state manager
            if (this.uiStateManager) {
                this.uiStateManager.integrateWithWebSocketClient(window.wsClient);
            }
        }
    }

    disableRealtimeFeatures() {
        // Disconnect WebSocket if connected
        if (window.wsClient) {
            window.wsClient.disconnect();
            window.wsClient = null;
        }
    }



    initNavigation() {
        // Initialize the enhanced navigation controller
        if (window.NavigationController) {
            this.navigationController = new NavigationController(this.authManager, this.uiStateManager);
            this.navigationController.init();
            
            // Integrate with UI state manager
            if (this.uiStateManager) {
                this.uiStateManager.integrateWithNavigationController(this.navigationController);
            }
        } else {
            console.warn('NavigationController not available');
        }
        
        console.log('Navigation initialized');
    }

    initDropdowns() {
        // Initialize the dropdown manager
        if (window.DropdownManager) {
            this.dropdownManager = new DropdownManager();
            this.dropdownManager.init();
        } else {
            console.warn('DropdownManager not available');
        }
        
        console.log('Dropdowns initialized');
    }

    async initI18n() {
        // Initialize language persistence manager first
        if (window.LanguagePersistenceManager) {
            window.languagePersistence = new LanguagePersistenceManager();
            
            // Initialize with server preference if available
            await window.languagePersistence.initializeWithServerPreference();
        }
        
        // Get current language from persistence manager or fallback
        const currentLang = window.languagePersistence ? 
            window.languagePersistence.getCurrentLanguage() : 
            (document.documentElement.lang || 'en');
        
        // Use enhanced language switcher if available, fallback to simple one
        if (window.EnhancedLanguageSwitcher) {
            window.languageSwitcher = new EnhancedLanguageSwitcher({
                containerId: 'language-switcher',
                currentLanguage: currentLang,
                availableLanguages: {
                    'en': 'English',
                    'de': 'Deutsch',
                    'uk': 'Українська'
                }
            });
        } else if (window.LanguageSwitcher) {
            window.languageSwitcher = new LanguageSwitcher({
                containerId: 'language-switcher',
                currentLanguage: currentLang,
                availableLanguages: {
                    'en': 'English',
                    'de': 'Deutsch',
                    'uk': 'Українська'
                }
            });
        }

        // Integrate language switcher with UI state manager
        if (this.uiStateManager && window.languageSwitcher) {
            this.uiStateManager.integrateWithLanguageSwitcher(window.languageSwitcher);
        }
        
        // Try to load i18n context from server
        this.loadI18nContext();
        
        // Listen for language change events
        this.setupLanguageChangeListeners();
    }

    async loadI18nContext() {
        try {
            const response = await fetch('/api/v1/i18n/context');
            if (response.ok) {
                const data = await response.json();
                if (data.success && window.I18nClient) {
                    window.i18n = new I18nClient(
                        data.data.current_language,
                        data.data.translations
                    );
                    console.log('i18n system loaded successfully');
                }
            }
        } catch (error) {
            console.log('i18n context not available, using fallback');
        }
    }

    setupLanguageChangeListeners() {
        // Listen for language changes and update UI
        window.addEventListener('localechange', (event) => {
            console.log('Locale changed to:', event.detail.locale);
            
            // Update translatable elements
            this.updateTranslatableElements();
            
            // Update date/time displays
            this.updateDateTimeDisplays();
            
            // Update HTML lang attribute
            document.documentElement.lang = event.detail.locale;
            
            // Update page title if it has translation key
            const titleElement = document.querySelector('title');
            if (titleElement && titleElement.dataset.i18nKey) {
                titleElement.textContent = window._ ? window._(titleElement.dataset.i18nKey) : titleElement.dataset.i18nKey;
            }
        });

        // Listen for language persistence manager events
        window.addEventListener('languagechange', (event) => {
            console.log('Language changed via persistence manager:', event.detail.language);
            
            // Update UI state manager if available
            if (this.uiStateManager) {
                this.uiStateManager.updateState({
                    currentLanguage: event.detail.language
                });
            }
            
            // Update translatable elements
            this.updateTranslatableElements();
            
            // Update date/time displays
            this.updateDateTimeDisplays();
        });

        // Listen for storage events (multi-tab synchronization)
        window.addEventListener('storage', (event) => {
            if (event.key === 'preferred_language' && event.newValue) {
                console.log('Language preference changed in another tab:', event.newValue);
                
                // Update current page language without reload
                if (window.languageSwitcher && typeof window.languageSwitcher.updateCurrentLanguage === 'function') {
                    window.languageSwitcher.updateCurrentLanguage(event.newValue);
                }
            }
        });
    }

    updateTranslatableElements() {
        if (window.languageSwitcher && typeof window.languageSwitcher.updateTranslatableElements === 'function') {
            window.languageSwitcher.updateTranslatableElements();
        } else {
            // Fallback implementation
            const elements = document.querySelectorAll('[data-i18n]');
            elements.forEach(element => {
                const key = element.dataset.i18n;
                const params = element.dataset.i18nParams ? 
                    JSON.parse(element.dataset.i18nParams) : {};
                
                const translation = window._ ? window._(key, params) : key;
                
                if (element.tagName === 'INPUT' && (element.type === 'submit' || element.type === 'button')) {
                    element.value = translation;
                } else if (element.hasAttribute('placeholder')) {
                    element.placeholder = translation;
                } else if (element.hasAttribute('title')) {
                    element.title = translation;
                } else {
                    element.textContent = translation;
                }
            });
        }
    }

    updateDateTimeDisplays() {
        const dateElements = document.querySelectorAll('[data-date], [data-datetime], [data-relative-time]');
        
        dateElements.forEach(element => {
            if (element.dataset.date) {
                const date = new Date(element.dataset.date);
                element.textContent = window.formatDate ? window.formatDate(date) : date.toLocaleDateString();
            } else if (element.dataset.datetime) {
                const date = new Date(element.dataset.datetime);
                element.textContent = window.formatDate ? window.formatDate(date, 'datetime') : date.toLocaleString();
            } else if (element.dataset.relativeTime) {
                const date = new Date(element.dataset.relativeTime);
                element.textContent = window.formatRelativeTime ? window.formatRelativeTime(date) : date.toLocaleDateString();
            }
        });
    }

    initForms() {
        // Login form is now handled by AuthenticationManager
        
        // Handle register form
        const registerForm = document.getElementById('registerForm');
        if (registerForm) {
            registerForm.addEventListener('submit', (e) => this.handleRegister(e));
        }
    }



    async handleRegister(e) {
        e.preventDefault();
        
        const form = e.target;
        const submitBtn = form.querySelector('button[type="submit"]');
        const spinner = submitBtn.querySelector('.spinner-border');
        
        // Show loading state
        submitBtn.disabled = true;
        if (spinner) spinner.classList.remove('d-none');
        
        try {
            const formData = new FormData(form);
            const response = await fetch('/api/v1/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: formData.get('email'),
                    password: formData.get('password'),
                    first_name: formData.get('first_name'),
                    last_name: formData.get('last_name')
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showAlert('success', data.message || 'Registration successful');
                
                // Redirect to login
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
                
            } else {
                this.showAlert('danger', data.error?.message || 'Registration failed');
            }
            
        } catch (error) {
            console.error('Registration error:', error);
            
            // Use error handler for better user feedback
            if (window.errorHandler) {
                window.errorHandler.handleNetworkError({
                    url: '/api/v1/auth/register',
                    error: error,
                    isOnline: navigator.onLine
                });
            } else {
                this.showAlert('danger', 'An error occurred. Please try again.');
            }
        } finally {
            // Hide loading state
            submitBtn.disabled = false;
            if (spinner) spinner.classList.add('d-none');
        }
    }

    async logout() {
        // Delegate to authentication manager
        if (this.authManager) {
            await this.authManager.handleLogout();
        }
    }

    showAlert(type, message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);
        }
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }

    // UI State Change Handlers
    showConnectionLostWarning() {
        // Show a subtle warning about lost real-time connection
        const existingWarning = document.getElementById('connection-warning');
        if (existingWarning) return; // Don't show multiple warnings

        const warningDiv = document.createElement('div');
        warningDiv.id = 'connection-warning';
        warningDiv.className = 'alert alert-warning alert-dismissible fade show position-fixed';
        warningDiv.style.cssText = 'top: 20px; right: 20px; z-index: 1050; max-width: 300px;';
        warningDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle me-2"></i>
            Real-time features temporarily unavailable
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(warningDiv);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (warningDiv.parentNode) {
                warningDiv.remove();
            }
        }, 10000);
    }

    onUserAuthenticated(user) {
        console.log('User authenticated:', user?.email);
        
        // Enable authenticated features
        this.enableAuthenticatedFeatures();
        
        // Initialize real-time features
        this.enableRealtimeFeatures();
        
        // Update user-specific UI elements
        this.updateUserSpecificUI(user);
    }

    onUserUnauthenticated() {
        console.log('User unauthenticated');
        
        // Disable authenticated features
        this.disableAuthenticatedFeatures();
        
        // Disable real-time features
        this.disableRealtimeFeatures();
        
        // Clear user-specific UI elements
        this.clearUserSpecificUI();
    }

    enableAuthenticatedFeatures() {
        // Enable features that require authentication
        const authRequiredElements = document.querySelectorAll('[data-auth-required]');
        authRequiredElements.forEach(element => {
            element.style.display = '';
            element.removeAttribute('disabled');
        });
    }

    disableAuthenticatedFeatures() {
        // Disable features that require authentication
        const authRequiredElements = document.querySelectorAll('[data-auth-required]');
        authRequiredElements.forEach(element => {
            element.style.display = 'none';
            element.setAttribute('disabled', 'true');
        });
    }

    updateUserSpecificUI(user) {
        if (!user) return;

        // Update user name displays
        const userNameElements = document.querySelectorAll('[data-user-name]');
        userNameElements.forEach(element => {
            element.textContent = user.first_name || user.email;
        });

        // Update user email displays
        const userEmailElements = document.querySelectorAll('[data-user-email]');
        userEmailElements.forEach(element => {
            element.textContent = user.email;
        });

        // Show/hide role-specific elements
        const roleElements = document.querySelectorAll('[data-required-role]');
        roleElements.forEach(element => {
            const requiredRole = element.dataset.requiredRole;
            if (user.role === requiredRole || user.role === 'owner') {
                element.style.display = '';
            } else {
                element.style.display = 'none';
            }
        });
    }

    clearUserSpecificUI() {
        // Clear user name displays
        const userNameElements = document.querySelectorAll('[data-user-name]');
        userNameElements.forEach(element => {
            element.textContent = 'Account';
        });

        // Clear user email displays
        const userEmailElements = document.querySelectorAll('[data-user-email]');
        userEmailElements.forEach(element => {
            element.textContent = '';
        });

        // Hide role-specific elements
        const roleElements = document.querySelectorAll('[data-required-role]');
        roleElements.forEach(element => {
            element.style.display = 'none';
        });
    }

    updatePageSpecificFeatures(activeNavItem) {
        // Update page-specific features based on active navigation
        if (activeNavItem === 'inbox') {
            this.initializeInboxFeatures();
        } else if (activeNavItem === 'crm') {
            this.initializeCRMFeatures();
        } else if (activeNavItem === 'calendar') {
            this.initializeCalendarFeatures();
        }
    }

    initializeInboxFeatures() {
        // Initialize inbox-specific features
        console.log('Initializing inbox features');
    }

    initializeCRMFeatures() {
        // Initialize CRM-specific features
        console.log('Initializing CRM features');
    }

    initializeCalendarFeatures() {
        // Initialize calendar-specific features
        console.log('Initializing calendar features');
    }

    updateNotificationDisplay(notifications) {
        // Update notification badge count
        const notificationBadge = document.querySelector('.notification-badge');
        if (notificationBadge) {
            const unreadCount = notifications.filter(n => !n.read).length;
            if (unreadCount > 0) {
                notificationBadge.textContent = unreadCount > 99 ? '99+' : unreadCount;
                notificationBadge.style.display = 'inline-block';
            } else {
                notificationBadge.style.display = 'none';
            }
        }

        // Update notification dropdown
        const notificationDropdown = document.querySelector('.notification-dropdown');
        if (notificationDropdown) {
            this.renderNotifications(notificationDropdown, notifications);
        }
    }

    renderNotifications(container, notifications) {
        // Clear existing notifications
        container.innerHTML = '';

        if (notifications.length === 0) {
            container.innerHTML = '<div class="dropdown-item text-muted">No notifications</div>';
            return;
        }

        // Show recent notifications (max 5)
        const recentNotifications = notifications.slice(-5).reverse();
        
        recentNotifications.forEach(notification => {
            const notificationElement = document.createElement('div');
            notificationElement.className = `dropdown-item ${notification.read ? '' : 'fw-bold'}`;
            notificationElement.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <div class="small">${notification.title || 'Notification'}</div>
                        <div class="text-muted small">${notification.message}</div>
                    </div>
                    <small class="text-muted">${this.formatNotificationTime(notification.timestamp)}</small>
                </div>
            `;
            container.appendChild(notificationElement);
        });

        // Add "View all" link if there are more notifications
        if (notifications.length > 5) {
            const viewAllElement = document.createElement('div');
            viewAllElement.className = 'dropdown-divider';
            container.appendChild(viewAllElement);

            const viewAllLink = document.createElement('a');
            viewAllLink.className = 'dropdown-item text-center';
            viewAllLink.href = '/notifications';
            viewAllLink.textContent = 'View all notifications';
            container.appendChild(viewAllLink);
        }
    }

    formatNotificationTime(timestamp) {
        if (!timestamp) return '';
        
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString();
    }

    updateLoadingIndicators(isLoading) {
        // Update global loading indicators
        const loadingOverlay = document.getElementById('loading-overlay');
        if (isLoading) {
            if (!loadingOverlay) {
                const overlay = document.createElement('div');
                overlay.id = 'loading-overlay';
                overlay.className = 'position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center';
                overlay.style.cssText = 'background: rgba(0,0,0,0.1); z-index: 9999;';
                overlay.innerHTML = `
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                `;
                document.body.appendChild(overlay);
            }
        } else {
            if (loadingOverlay) {
                loadingOverlay.remove();
            }
        }

        // Update page-specific loading indicators
        const pageLoadingIndicators = document.querySelectorAll('.page-loading');
        pageLoadingIndicators.forEach(indicator => {
            if (isLoading) {
                indicator.style.display = 'block';
            } else {
                indicator.style.display = 'none';
            }
        });
    }

    // API Tester functionality (for API tester page)
    initAPITester() {
        // Toggle endpoint details
        document.querySelectorAll('.endpoint-header').forEach(header => {
            header.addEventListener('click', () => {
                const body = header.nextElementSibling;
                body.classList.toggle('show');
            });
        });

        // Test buttons
        document.querySelectorAll('.btn-test').forEach(button => {
            button.addEventListener('click', (e) => {
                const endpoint = e.target.dataset.endpoint;
                this.testEndpoint(endpoint, e.target);
            });
        });

        // Auto-refresh health status every 30 seconds
        setInterval(() => {
            const healthButton = document.querySelector('[data-endpoint="/api/v1/health"]');
            if (healthButton) {
                healthButton.click();
            }
        }, 30000);
    }

    async testEndpoint(endpoint, button) {
        const responseBox = button.parentElement.querySelector('.response-box');
        const statusBadge = button.parentElement.querySelector('.status-badge');
        
        button.disabled = true;
        button.textContent = 'Testing...';
        responseBox.textContent = 'Loading...';

        try {
            const headers = {};
            const token = localStorage.getItem('access_token');
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${this.baseURL}${endpoint}`, { headers });
            const data = await response.json();
            
            // Update status badge
            statusBadge.textContent = response.status;
            statusBadge.className = `status-badge status-${response.status}`;
            
            // Update response box
            responseBox.textContent = JSON.stringify(data, null, 2);
            
        } catch (error) {
            statusBadge.textContent = 'ERROR';
            statusBadge.className = 'status-badge status-500';
            responseBox.textContent = `Error: ${error.message}`;
            
            // Use error handler for API testing errors
            if (window.errorHandler) {
                window.errorHandler.handleNetworkError({
                    url: `${this.baseURL}${endpoint}`,
                    error: error,
                    isOnline: navigator.onLine
                });
            }
        } finally {
            button.disabled = false;
            button.textContent = 'Test';
        }
    }
}

// Global logout function for navbar
window.logout = function() {
    if (window.aiSecretaryApp && window.aiSecretaryApp.authManager) {
        window.aiSecretaryApp.authManager.handleLogout();
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.aiSecretaryApp = new AISecretaryApp();
});