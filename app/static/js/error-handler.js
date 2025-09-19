/**
 * Enhanced Error Handler
 * Provides comprehensive JavaScript error handling with user-friendly feedback
 */

class ErrorHandler {
    constructor() {
        this.errorQueue = [];
        this.maxErrorQueue = 50;
        this.isOnline = navigator.onLine;
        this.errorCounts = new Map();
        this.maxSameErrorCount = 5;
        this.notificationContainer = null;
        
        // Initialize error handling
        this.init();
    }

    /**
     * Initialize error handling system
     */
    init() {
        console.log('Initializing Error Handler...');
        
        // Set up global error handlers
        this.setupGlobalErrorHandlers();
        
        // Set up network monitoring
        this.setupNetworkMonitoring();
        
        // Create notification container
        this.createNotificationContainer();
        
        // Set up periodic error reporting
        this.setupErrorReporting();
        
        console.log('Error Handler initialized');
    }

    /**
     * Set up global JavaScript error handlers
     */
    setupGlobalErrorHandlers() {
        // Handle uncaught JavaScript errors
        window.addEventListener('error', (event) => {
            this.handleJavaScriptError({
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                error: event.error,
                type: 'javascript'
            });
        });

        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.handlePromiseRejection({
                reason: event.reason,
                promise: event.promise,
                type: 'promise'
            });
        });

        // Handle resource loading errors
        window.addEventListener('error', (event) => {
            if (event.target !== window) {
                this.handleResourceError({
                    element: event.target,
                    source: event.target.src || event.target.href,
                    type: 'resource'
                });
            }
        }, true);
    }

    /**
     * Set up network monitoring
     */
    setupNetworkMonitoring() {
        // Monitor online/offline status
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.showNotification('success', 'Connection restored', 'You are back online');
            this.hideOfflineIndicator();
            this.retryFailedRequests();
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.showNotification('warning', 'Connection lost', 'You are currently offline. Some features may not work.');
            this.showOfflineIndicator();
        });

        // Monitor fetch requests for network errors
        this.interceptFetchRequests();
        
        // Set up graceful degradation
        this.setupGracefulDegradation();
    }

    /**
     * Intercept fetch requests to handle API errors
     */
    interceptFetchRequests() {
        const originalFetch = window.fetch;
        
        window.fetch = async (...args) => {
            try {
                const response = await originalFetch.apply(this, args);
                
                // Handle HTTP error responses
                if (!response.ok) {
                    this.handleAPIError({
                        url: args[0],
                        status: response.status,
                        statusText: response.statusText,
                        response: response.clone()
                    });
                }
                
                return response;
            } catch (error) {
                // Handle network errors
                this.handleNetworkError({
                    url: args[0],
                    error: error,
                    isOnline: this.isOnline
                });
                
                // Add to retry queue if it's a network error and we're offline
                if (!this.isOnline && error.name === 'TypeError') {
                    this.addFailedRequest(args[0], args[1]);
                }
                
                throw error; // Re-throw to maintain original behavior
            }
        };
    }

    /**
     * Handle JavaScript errors
     */
    handleJavaScriptError(errorInfo) {
        const errorKey = `${errorInfo.filename}:${errorInfo.lineno}:${errorInfo.message}`;
        
        // Prevent spam of same error
        if (this.shouldIgnoreError(errorKey)) {
            return;
        }

        // Log error details
        console.error('JavaScript Error:', errorInfo);
        
        // Add to error queue
        this.addToErrorQueue({
            ...errorInfo,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            url: window.location.href
        });

        // Show user-friendly message
        const userMessage = this.getUserFriendlyMessage(errorInfo);
        this.showNotification('error', 'Application Error', userMessage);

        // Report error if critical
        if (this.isCriticalError(errorInfo)) {
            this.reportError(errorInfo);
        }
    }

    /**
     * Handle promise rejections
     */
    handlePromiseRejection(rejectionInfo) {
        const errorKey = `promise:${rejectionInfo.reason}`;
        
        if (this.shouldIgnoreError(errorKey)) {
            return;
        }

        console.error('Unhandled Promise Rejection:', rejectionInfo);
        
        // Add to error queue
        this.addToErrorQueue({
            ...rejectionInfo,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            url: window.location.href
        });

        // Show user-friendly message for promise rejections
        let userMessage = 'An operation failed to complete';
        
        if (rejectionInfo.reason && typeof rejectionInfo.reason === 'string') {
            if (rejectionInfo.reason.includes('fetch')) {
                userMessage = 'Failed to load data. Please check your connection.';
            } else if (rejectionInfo.reason.includes('auth')) {
                userMessage = 'Authentication failed. Please log in again.';
            }
        }

        this.showNotification('error', 'Operation Failed', userMessage);
    }

    /**
     * Handle resource loading errors
     */
    handleResourceError(errorInfo) {
        console.error('Resource Loading Error:', errorInfo);
        
        const resourceType = this.getResourceType(errorInfo.element);
        let userMessage = `Failed to load ${resourceType}`;
        
        if (!this.isOnline) {
            userMessage += ' (you are offline)';
        }

        // Add to error queue
        this.addToErrorQueue({
            ...errorInfo,
            resourceType,
            timestamp: new Date().toISOString(),
            url: window.location.href
        });

        // Only show notification for critical resources
        if (this.isCriticalResource(errorInfo.element)) {
            this.showNotification('warning', 'Loading Error', userMessage);
        }
    }

    /**
     * Handle API errors
     */
    async handleAPIError(errorInfo) {
        let errorData = null;
        
        try {
            errorData = await errorInfo.response.json();
        } catch (e) {
            // Response is not JSON
        }

        console.error('API Error:', {
            url: errorInfo.url,
            status: errorInfo.status,
            statusText: errorInfo.statusText,
            data: errorData
        });

        // Add to error queue
        this.addToErrorQueue({
            ...errorInfo,
            data: errorData,
            timestamp: new Date().toISOString(),
            url: window.location.href
        });

        // Show user-friendly message based on status code
        const userMessage = this.getAPIErrorMessage(errorInfo.status, errorData);
        const severity = this.getAPIErrorSeverity(errorInfo.status);
        
        this.showNotification(severity, 'Request Failed', userMessage);

        // Handle specific error cases
        if (errorInfo.status === 401) {
            this.handleAuthenticationError();
        } else if (errorInfo.status >= 500) {
            this.handleServerError(errorInfo);
        }
    }

    /**
     * Handle network errors
     */
    handleNetworkError(errorInfo) {
        console.error('Network Error:', errorInfo);
        
        // Add to error queue
        this.addToErrorQueue({
            ...errorInfo,
            timestamp: new Date().toISOString(),
            url: window.location.href
        });

        let userMessage = 'Network request failed';
        
        if (!errorInfo.isOnline) {
            userMessage = 'You are offline. Please check your internet connection.';
        } else if (errorInfo.error.name === 'TypeError') {
            userMessage = 'Unable to connect to server. Please try again.';
        } else if (errorInfo.error.name === 'AbortError') {
            userMessage = 'Request was cancelled or timed out.';
        }

        this.showNotification('error', 'Connection Error', userMessage);
    }

    /**
     * Get user-friendly error message
     */
    getUserFriendlyMessage(errorInfo) {
        // Check for common error patterns
        if (errorInfo.message.includes('is not defined')) {
            return 'A required component failed to load. Please refresh the page.';
        } else if (errorInfo.message.includes('Cannot read property')) {
            return 'An unexpected error occurred. Please try again.';
        } else if (errorInfo.message.includes('fetch')) {
            return 'Failed to load data. Please check your connection.';
        } else if (errorInfo.message.includes('Permission denied')) {
            return 'Permission denied. Please check your access rights.';
        } else if (errorInfo.message.includes('Network Error')) {
            return 'Network connection failed. Please check your internet connection.';
        }
        
        return 'An unexpected error occurred. Please refresh the page if the problem persists.';
    }

    /**
     * Get API error message based on status code
     */
    getAPIErrorMessage(status, errorData) {
        const messages = {
            400: 'Invalid request. Please check your input.',
            401: 'Authentication required. Please log in.',
            403: 'Access denied. You don\'t have permission for this action.',
            404: 'The requested resource was not found.',
            409: 'Conflict occurred. The resource may have been modified.',
            422: 'Validation failed. Please check your input.',
            429: 'Too many requests. Please wait a moment and try again.',
            500: 'Server error occurred. Please try again later.',
            502: 'Service temporarily unavailable. Please try again.',
            503: 'Service maintenance in progress. Please try again later.',
            504: 'Request timed out. Please try again.'
        };

        // Use specific error message from API if available
        if (errorData && errorData.error && errorData.error.message) {
            return errorData.error.message;
        }

        return messages[status] || `Request failed with status ${status}`;
    }

    /**
     * Get API error severity
     */
    getAPIErrorSeverity(status) {
        if (status >= 500) return 'error';
        if (status === 401 || status === 403) return 'warning';
        if (status === 429) return 'info';
        return 'warning';
    }

    /**
     * Handle authentication errors
     */
    handleAuthenticationError() {
        // Clear tokens
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        
        // Notify auth manager if available
        if (window.aiSecretaryApp && window.aiSecretaryApp.authManager) {
            window.aiSecretaryApp.authManager.showUnauthenticatedUI();
        }
        
        // Redirect to login after a delay
        setTimeout(() => {
            const returnUrl = encodeURIComponent(window.location.href);
            window.location.href = `/login?return_url=${returnUrl}`;
        }, 2000);
    }

    /**
     * Handle server errors
     */
    handleServerError(errorInfo) {
        // Report critical server errors
        this.reportError({
            type: 'server_error',
            status: errorInfo.status,
            url: errorInfo.url,
            timestamp: new Date().toISOString()
        });
    }

    /**
     * Check if error should be ignored (to prevent spam)
     */
    shouldIgnoreError(errorKey) {
        const count = this.errorCounts.get(errorKey) || 0;
        this.errorCounts.set(errorKey, count + 1);
        
        return count >= this.maxSameErrorCount;
    }

    /**
     * Check if error is critical
     */
    isCriticalError(errorInfo) {
        const criticalPatterns = [
            'ReferenceError',
            'TypeError: Cannot read property',
            'SecurityError',
            'Authentication',
            'Authorization'
        ];
        
        return criticalPatterns.some(pattern => 
            errorInfo.message.includes(pattern)
        );
    }

    /**
     * Get resource type from element
     */
    getResourceType(element) {
        const tagName = element.tagName.toLowerCase();
        
        switch (tagName) {
            case 'script': return 'JavaScript file';
            case 'link': return 'stylesheet';
            case 'img': return 'image';
            case 'video': return 'video';
            case 'audio': return 'audio';
            default: return 'resource';
        }
    }

    /**
     * Check if resource is critical
     */
    isCriticalResource(element) {
        const tagName = element.tagName.toLowerCase();
        
        // Critical resources that affect functionality
        if (tagName === 'script') {
            const src = element.src;
            return src.includes('app.js') || 
                   src.includes('auth-manager.js') || 
                   src.includes('bootstrap') ||
                   src.includes('socket.io');
        }
        
        if (tagName === 'link' && element.rel === 'stylesheet') {
            return element.href.includes('bootstrap') || 
                   element.href.includes('app.css');
        }
        
        return false;
    }

    /**
     * Add error to queue
     */
    addToErrorQueue(error) {
        this.errorQueue.push(error);
        
        // Limit queue size
        if (this.errorQueue.length > this.maxErrorQueue) {
            this.errorQueue.shift();
        }
    }

    /**
     * Create notification container
     */
    createNotificationContainer() {
        if (document.getElementById('error-notifications')) {
            return;
        }

        const container = document.createElement('div');
        container.id = 'error-notifications';
        container.className = 'error-notifications';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 400px;
        `;
        
        document.body.appendChild(container);
        this.notificationContainer = container;
    }

    /**
     * Show notification to user
     */
    showNotification(type, title, message, duration = 5000) {
        if (!this.notificationContainer) {
            this.createNotificationContainer();
        }

        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show error-notification`;
        notification.style.cssText = `
            margin-bottom: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        `;
        
        notification.innerHTML = `
            <strong>${title}</strong>
            <div>${message}</div>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        this.notificationContainer.appendChild(notification);
        
        // Auto-remove notification
        if (duration > 0) {
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, duration);
        }
        
        // Limit number of notifications
        const notifications = this.notificationContainer.querySelectorAll('.error-notification');
        if (notifications.length > 5) {
            notifications[0].remove();
        }
    }

    /**
     * Retry failed requests when connection is restored
     */
    retryFailedRequests() {
        // This would integrate with a request queue system
        // For now, just show a message
        console.log('Connection restored - you may retry failed operations');
    }

    /**
     * Report error to server (if reporting endpoint exists)
     */
    async reportError(errorInfo) {
        try {
            const token = localStorage.getItem('access_token');
            if (!token) return;

            await fetch('/api/v1/errors/report', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    error: errorInfo,
                    timestamp: new Date().toISOString(),
                    user_agent: navigator.userAgent,
                    url: window.location.href
                })
            });
        } catch (e) {
            // Silently fail - don't create error loops
            console.debug('Error reporting failed:', e);
        }
    }

    /**
     * Set up periodic error reporting
     */
    setupErrorReporting() {
        // Report accumulated errors every 5 minutes
        setInterval(() => {
            if (this.errorQueue.length > 0) {
                this.reportBatchErrors();
            }
        }, 5 * 60 * 1000);
    }

    /**
     * Report batch of errors
     */
    async reportBatchErrors() {
        if (this.errorQueue.length === 0) return;

        try {
            const token = localStorage.getItem('access_token');
            if (!token) return;

            const errors = [...this.errorQueue];
            this.errorQueue = []; // Clear queue

            await fetch('/api/v1/errors/batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    errors: errors,
                    session_id: this.getSessionId(),
                    timestamp: new Date().toISOString()
                })
            });
        } catch (e) {
            // Silently fail - don't create error loops
            console.debug('Batch error reporting failed:', e);
        }
    }

    /**
     * Get or create session ID
     */
    getSessionId() {
        let sessionId = sessionStorage.getItem('error_session_id');
        if (!sessionId) {
            sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            sessionStorage.setItem('error_session_id', sessionId);
        }
        return sessionId;
    }

    /**
     * Get error statistics
     */
    getErrorStats() {
        return {
            totalErrors: this.errorQueue.length,
            errorCounts: Object.fromEntries(this.errorCounts),
            isOnline: this.isOnline,
            sessionId: this.getSessionId()
        };
    }

    /**
     * Clear error queue
     */
    clearErrors() {
        this.errorQueue = [];
        this.errorCounts.clear();
    }

    /**
     * Enable/disable error notifications
     */
    setNotificationsEnabled(enabled) {
        this.notificationsEnabled = enabled;
        
        if (!enabled && this.notificationContainer) {
            this.notificationContainer.style.display = 'none';
        } else if (enabled && this.notificationContainer) {
            this.notificationContainer.style.display = 'block';
        }
    }

    /**
     * Set up graceful degradation for network issues
     */
    setupGracefulDegradation() {
        // Disable real-time features when offline
        this.setupOfflineMode();
        
        // Set up retry mechanisms
        this.setupRetryMechanisms();
        
        // Set up fallback UI states
        this.setupFallbackStates();
    }

    /**
     * Set up offline mode handling
     */
    setupOfflineMode() {
        const handleOfflineMode = () => {
            // Disable WebSocket features
            if (window.wsClient) {
                window.wsClient.disconnect();
            }
            
            // Show offline indicators on interactive elements
            this.markOfflineElements();
            
            // Cache current page state
            this.cachePageState();
        };

        const handleOnlineMode = () => {
            // Re-enable WebSocket features
            if (window.wsClient) {
                window.wsClient.reconnectManually();
            }
            
            // Remove offline indicators
            this.unmarkOfflineElements();
            
            // Restore cached state if needed
            this.restorePageState();
        };

        if (!this.isOnline) {
            handleOfflineMode();
        }

        window.addEventListener('offline', handleOfflineMode);
        window.addEventListener('online', handleOnlineMode);
    }

    /**
     * Set up retry mechanisms for failed requests
     */
    setupRetryMechanisms() {
        this.failedRequests = [];
        this.maxRetries = 3;
        this.retryDelay = 1000;
    }

    /**
     * Set up fallback UI states
     */
    setupFallbackStates() {
        // Set up fallback for missing JavaScript dependencies
        this.checkDependencies();
        
        // Set up fallback for failed CSS loading
        this.checkStylesheets();
    }

    /**
     * Check for missing JavaScript dependencies
     */
    checkDependencies() {
        const requiredDependencies = [
            { name: 'Bootstrap', check: () => typeof bootstrap !== 'undefined' },
            { name: 'Socket.IO', check: () => typeof io !== 'undefined' }
        ];

        requiredDependencies.forEach(dep => {
            if (!dep.check()) {
                console.warn(`${dep.name} not loaded - some features may not work`);
                this.showNotification('warning', 'Feature Unavailable', 
                    `${dep.name} failed to load. Some features may not work properly.`);
            }
        });
    }

    /**
     * Check for failed stylesheet loading
     */
    checkStylesheets() {
        const stylesheets = document.querySelectorAll('link[rel="stylesheet"]');
        
        stylesheets.forEach(link => {
            link.addEventListener('error', () => {
                console.warn('Stylesheet failed to load:', link.href);
                this.showNotification('warning', 'Styling Issue', 
                    'Some styles failed to load. The page may not look correct.');
            });
        });
    }

    /**
     * Show offline indicator
     */
    showOfflineIndicator() {
        let indicator = document.getElementById('offline-indicator');
        
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'offline-indicator';
            indicator.className = 'offline-indicator';
            indicator.textContent = 'You are offline - some features may not work';
            document.body.insertBefore(indicator, document.body.firstChild);
        }
        
        indicator.style.display = 'block';
    }

    /**
     * Hide offline indicator
     */
    hideOfflineIndicator() {
        const indicator = document.getElementById('offline-indicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    /**
     * Mark elements as offline
     */
    markOfflineElements() {
        // Disable buttons that require network
        const networkButtons = document.querySelectorAll('[data-requires-network]');
        networkButtons.forEach(button => {
            button.disabled = true;
            button.title = 'This feature requires an internet connection';
            button.classList.add('offline-disabled');
        });

        // Show offline messages on forms
        const forms = document.querySelectorAll('form[data-requires-network]');
        forms.forEach(form => {
            let offlineMsg = form.querySelector('.offline-message');
            if (!offlineMsg) {
                offlineMsg = document.createElement('div');
                offlineMsg.className = 'alert alert-warning offline-message';
                offlineMsg.textContent = 'This form requires an internet connection to submit.';
                form.insertBefore(offlineMsg, form.firstChild);
            }
        });
    }

    /**
     * Remove offline markers from elements
     */
    unmarkOfflineElements() {
        // Re-enable network buttons
        const networkButtons = document.querySelectorAll('.offline-disabled');
        networkButtons.forEach(button => {
            button.disabled = false;
            button.title = '';
            button.classList.remove('offline-disabled');
        });

        // Remove offline messages
        const offlineMessages = document.querySelectorAll('.offline-message');
        offlineMessages.forEach(msg => msg.remove());
    }

    /**
     * Cache current page state
     */
    cachePageState() {
        try {
            const state = {
                url: window.location.href,
                timestamp: Date.now(),
                formData: this.getFormData(),
                scrollPosition: window.scrollY
            };
            
            sessionStorage.setItem('offline_page_state', JSON.stringify(state));
        } catch (e) {
            console.debug('Failed to cache page state:', e);
        }
    }

    /**
     * Restore cached page state
     */
    restorePageState() {
        try {
            const cached = sessionStorage.getItem('offline_page_state');
            if (cached) {
                const state = JSON.parse(cached);
                
                // Only restore if it's recent (within 5 minutes)
                if (Date.now() - state.timestamp < 5 * 60 * 1000) {
                    this.restoreFormData(state.formData);
                    window.scrollTo(0, state.scrollPosition);
                }
                
                sessionStorage.removeItem('offline_page_state');
            }
        } catch (e) {
            console.debug('Failed to restore page state:', e);
        }
    }

    /**
     * Get form data for caching
     */
    getFormData() {
        const forms = document.querySelectorAll('form');
        const formData = {};
        
        forms.forEach((form, index) => {
            const data = new FormData(form);
            const formObj = {};
            
            for (let [key, value] of data.entries()) {
                formObj[key] = value;
            }
            
            if (Object.keys(formObj).length > 0) {
                formData[`form_${index}`] = formObj;
            }
        });
        
        return formData;
    }

    /**
     * Restore form data from cache
     */
    restoreFormData(formData) {
        if (!formData) return;
        
        const forms = document.querySelectorAll('form');
        
        forms.forEach((form, index) => {
            const cached = formData[`form_${index}`];
            if (cached) {
                Object.entries(cached).forEach(([name, value]) => {
                    const input = form.querySelector(`[name="${name}"]`);
                    if (input && input.type !== 'password') {
                        input.value = value;
                    }
                });
            }
        });
    }

    /**
     * Retry failed requests when connection is restored
     */
    retryFailedRequests() {
        if (this.failedRequests.length === 0) return;
        
        console.log(`Retrying ${this.failedRequests.length} failed requests...`);
        
        const requests = [...this.failedRequests];
        this.failedRequests = [];
        
        requests.forEach(async (request, index) => {
            try {
                // Add delay between retries to avoid overwhelming the server
                await new Promise(resolve => setTimeout(resolve, index * 100));
                
                const response = await fetch(request.url, request.options);
                
                if (response.ok) {
                    console.log('Successfully retried request:', request.url);
                } else {
                    // Add back to failed requests if still failing
                    if (request.retryCount < this.maxRetries) {
                        request.retryCount = (request.retryCount || 0) + 1;
                        this.failedRequests.push(request);
                    }
                }
            } catch (error) {
                // Add back to failed requests if still failing
                if (request.retryCount < this.maxRetries) {
                    request.retryCount = (request.retryCount || 0) + 1;
                    this.failedRequests.push(request);
                }
            }
        });
    }

    /**
     * Add failed request to retry queue
     */
    addFailedRequest(url, options = {}) {
        this.failedRequests.push({
            url,
            options,
            timestamp: Date.now(),
            retryCount: 0
        });
    }
}

// Initialize error handler when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.errorHandler = new ErrorHandler();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ErrorHandler;
}