/**
 * Loading Manager for AI Secretary
 * Handles loading states and user feedback across the application
 */

class LoadingManager {
    constructor() {
        this.activeOperations = new Set();
        this.loadingIndicators = new Map();
        this.feedbackQueue = [];
        this.init();
    }

    init() {
        this.createGlobalLoadingOverlay();
        this.createToastContainer();
        this.setupEventListeners();
        console.log('Loading Manager initialized');
    }

    createGlobalLoadingOverlay() {
        // Create global loading overlay
        const overlay = document.createElement('div');
        overlay.id = 'global-loading-overlay';
        overlay.className = 'loading-overlay d-none';
        overlay.innerHTML = `
            <div class="loading-content">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="loading-message mt-3">Loading...</div>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    createToastContainer() {
        // Create toast container for notifications
        if (!document.getElementById('toast-container')) {
            const container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '1055';
            document.body.appendChild(container);
        }
    }

    setupEventListeners() {
        // Listen for authentication events
        document.addEventListener('auth:login_start', () => {
            this.showAuthenticationLoading('Signing in...');
        });

        document.addEventListener('auth:login_success', () => {
            this.hideAuthenticationLoading();
            this.showSuccessToast('Successfully signed in!');
        });

        document.addEventListener('auth:login_error', (event) => {
            this.hideAuthenticationLoading();
            this.showErrorToast(event.detail.message || 'Login failed');
        });

        document.addEventListener('auth:logout_start', () => {
            this.showAuthenticationLoading('Signing out...');
        });

        document.addEventListener('auth:logout_complete', () => {
            this.hideAuthenticationLoading();
            this.showInfoToast('Signed out successfully');
        });

        // Listen for language switching events
        document.addEventListener('language:switch_start', (event) => {
            this.showLanguageLoading(event.detail.language);
        });

        document.addEventListener('language:switch_success', (event) => {
            this.hideLanguageLoading();
            this.showSuccessToast(`Language changed to ${event.detail.languageName}`);
        });

        document.addEventListener('language:switch_error', (event) => {
            this.hideLanguageLoading();
            this.showErrorToast(event.detail.message || 'Failed to change language');
        });

        // Listen for WebSocket events
        document.addEventListener('websocket:connecting', () => {
            this.showConnectionStatus('connecting', 'Connecting to real-time services...');
        });

        document.addEventListener('websocket:connected', () => {
            this.showConnectionStatus('connected', 'Real-time features enabled');
            this.showSuccessToast('Connected to real-time services', { duration: 3000 });
        });

        document.addEventListener('websocket:disconnected', (event) => {
            this.showConnectionStatus('disconnected', 'Connection lost - attempting to reconnect');
            this.showWarningToast('Real-time connection lost', { duration: 5000 });
        });

        document.addEventListener('websocket:reconnecting', (event) => {
            const attempt = event.detail.attempt || 1;
            this.showConnectionStatus('reconnecting', `Reconnecting... (attempt ${attempt})`);
        });

        document.addEventListener('websocket:max_reconnect_attempts', () => {
            this.showConnectionStatus('failed', 'Connection failed - please refresh the page');
            this.showErrorToast('Unable to connect to real-time services', { 
                duration: 0, // Don't auto-hide
                action: {
                    text: 'Retry',
                    callback: () => {
                        if (window.wsClient) {
                            window.wsClient.reconnectManually();
                        }
                    }
                }
            });
        });

        // Listen for API operation events
        document.addEventListener('api:request_start', (event) => {
            this.showAPILoading(event.detail.operation);
        });

        document.addEventListener('api:request_complete', (event) => {
            this.hideAPILoading(event.detail.operation);
        });

        document.addEventListener('api:request_error', (event) => {
            this.hideAPILoading(event.detail.operation);
            this.showErrorToast(event.detail.message || 'Request failed');
        });
    }

    // Authentication Loading States
    showAuthenticationLoading(message = 'Authenticating...') {
        this.startOperation('authentication', message);
        
        // Show loading on login/logout buttons
        const authButtons = document.querySelectorAll('[data-action="login"], [data-action="logout"]');
        authButtons.forEach(button => {
            this.showButtonLoading(button, message);
        });

        // Show loading on login form
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            this.showFormLoading(loginForm, message);
        }
    }

    hideAuthenticationLoading() {
        this.endOperation('authentication');
        
        // Hide loading on auth buttons
        const authButtons = document.querySelectorAll('[data-action="login"], [data-action="logout"]');
        authButtons.forEach(button => {
            this.hideButtonLoading(button);
        });

        // Hide loading on login form
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            this.hideFormLoading(loginForm);
        }
    }

    // Language Switching Loading States
    showLanguageLoading(language) {
        const languageName = this.getLanguageName(language);
        const message = `Switching to ${languageName}...`;
        
        this.startOperation('language', message);
        
        // Show loading on language switcher
        const languageSwitcher = document.getElementById('language-switcher');
        if (languageSwitcher) {
            this.showElementLoading(languageSwitcher, message);
        }

        // Show loading indicator in language dropdown
        const languageDropdown = document.getElementById('languageDropdown');
        if (languageDropdown) {
            this.showButtonLoading(languageDropdown, message);
        }
    }

    hideLanguageLoading() {
        this.endOperation('language');
        
        // Hide loading on language switcher
        const languageSwitcher = document.getElementById('language-switcher');
        if (languageSwitcher) {
            this.hideElementLoading(languageSwitcher);
        }

        // Hide loading on language dropdown
        const languageDropdown = document.getElementById('languageDropdown');
        if (languageDropdown) {
            this.hideButtonLoading(languageDropdown);
        }
    }

    getLanguageName(code) {
        const languages = {
            'en': 'English',
            'de': 'Deutsch',
            'uk': 'Українська'
        };
        return languages[code] || code;
    }

    // WebSocket Connection Status
    showConnectionStatus(status, message) {
        let statusElement = document.getElementById('ws-connection-status');
        
        if (!statusElement) {
            statusElement = document.createElement('div');
            statusElement.id = 'ws-connection-status';
            statusElement.className = 'connection-status';
            document.body.appendChild(statusElement);
        }

        statusElement.className = `connection-status ${status}`;
        statusElement.innerHTML = `
            <div class="connection-status-content">
                <div class="connection-status-icon"></div>
                <div class="connection-status-message">${message}</div>
                ${status === 'failed' ? '<button class="btn btn-sm btn-outline-primary ms-2" onclick="window.wsClient?.reconnectManually()">Retry</button>' : ''}
            </div>
        `;

        statusElement.style.display = 'block';

        // Auto-hide success messages
        if (status === 'connected') {
            setTimeout(() => {
                if (statusElement.classList.contains('connected')) {
                    statusElement.style.display = 'none';
                }
            }, 3000);
        }
    }

    // API Loading States
    showAPILoading(operation) {
        this.startOperation(`api_${operation}`, `Processing ${operation}...`);
    }

    hideAPILoading(operation) {
        this.endOperation(`api_${operation}`);
    }

    // Generic Loading Methods
    startOperation(operationId, message = 'Loading...') {
        this.activeOperations.add(operationId);
        this.updateGlobalLoadingState(message);
    }

    endOperation(operationId) {
        this.activeOperations.delete(operationId);
        this.updateGlobalLoadingState();
    }

    updateGlobalLoadingState(message = 'Loading...') {
        const overlay = document.getElementById('global-loading-overlay');
        if (!overlay) return;

        if (this.activeOperations.size > 0) {
            const messageElement = overlay.querySelector('.loading-message');
            if (messageElement) {
                messageElement.textContent = message;
            }
            overlay.classList.remove('d-none');
        } else {
            overlay.classList.add('d-none');
        }
    }

    // Button Loading States
    showButtonLoading(button, message = 'Loading...') {
        if (!button) return;

        // Store original content
        button.dataset.originalContent = button.innerHTML;
        button.dataset.originalDisabled = button.disabled;

        // Show loading state
        button.disabled = true;
        button.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            ${message}
        `;
        button.classList.add('loading');
    }

    hideButtonLoading(button) {
        if (!button || !button.classList.contains('loading')) return;

        // Restore original content
        button.innerHTML = button.dataset.originalContent || button.innerHTML;
        button.disabled = button.dataset.originalDisabled === 'true';
        button.classList.remove('loading');

        // Clean up data attributes
        delete button.dataset.originalContent;
        delete button.dataset.originalDisabled;
    }

    // Form Loading States
    showFormLoading(form, message = 'Processing...') {
        if (!form) return;

        // Disable all form inputs
        const inputs = form.querySelectorAll('input, button, select, textarea');
        inputs.forEach(input => {
            input.dataset.originalDisabled = input.disabled;
            input.disabled = true;
        });

        // Show loading indicator
        let loadingIndicator = form.querySelector('.form-loading-indicator');
        if (!loadingIndicator) {
            loadingIndicator = document.createElement('div');
            loadingIndicator.className = 'form-loading-indicator text-center mt-3';
            form.appendChild(loadingIndicator);
        }

        loadingIndicator.innerHTML = `
            <div class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></div>
            <span>${message}</span>
        `;
        loadingIndicator.style.display = 'block';

        form.classList.add('loading');
    }

    hideFormLoading(form) {
        if (!form || !form.classList.contains('loading')) return;

        // Re-enable form inputs
        const inputs = form.querySelectorAll('input, button, select, textarea');
        inputs.forEach(input => {
            input.disabled = input.dataset.originalDisabled === 'true';
            delete input.dataset.originalDisabled;
        });

        // Hide loading indicator
        const loadingIndicator = form.querySelector('.form-loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.style.display = 'none';
        }

        form.classList.remove('loading');
    }

    // Element Loading States
    showElementLoading(element, message = 'Loading...') {
        if (!element) return;

        element.dataset.originalContent = element.innerHTML;
        element.innerHTML = `
            <div class="d-flex align-items-center justify-content-center">
                <div class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></div>
                <span>${message}</span>
            </div>
        `;
        element.classList.add('loading');
    }

    hideElementLoading(element) {
        if (!element || !element.classList.contains('loading')) return;

        element.innerHTML = element.dataset.originalContent || element.innerHTML;
        element.classList.remove('loading');
        delete element.dataset.originalContent;
    }

    // Toast Notifications
    showSuccessToast(message, options = {}) {
        this.showToast(message, 'success', options);
    }

    showErrorToast(message, options = {}) {
        this.showToast(message, 'danger', options);
    }

    showWarningToast(message, options = {}) {
        this.showToast(message, 'warning', options);
    }

    showInfoToast(message, options = {}) {
        this.showToast(message, 'info', options);
    }

    showToast(message, type = 'info', options = {}) {
        const {
            duration = 5000,
            action = null,
            icon = null
        } = options;

        const toastId = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const container = document.getElementById('toast-container');
        
        if (!container) return;

        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `toast align-items-center text-bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');

        const iconHtml = icon ? `<i class="${icon} me-2"></i>` : this.getTypeIcon(type);
        const actionHtml = action ? `
            <button type="button" class="btn btn-sm btn-outline-light ms-2" onclick="${action.callback.toString()}()">
                ${action.text}
            </button>
        ` : '';

        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body d-flex align-items-center">
                    ${iconHtml}
                    ${message}
                    ${actionHtml}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

        container.appendChild(toast);

        // Initialize Bootstrap toast
        const bsToast = new bootstrap.Toast(toast, {
            autohide: duration > 0,
            delay: duration
        });

        bsToast.show();

        // Clean up after toast is hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });

        return toastId;
    }

    getTypeIcon(type) {
        const icons = {
            'success': '<i class="fas fa-check-circle me-2"></i>',
            'danger': '<i class="fas fa-exclamation-circle me-2"></i>',
            'warning': '<i class="fas fa-exclamation-triangle me-2"></i>',
            'info': '<i class="fas fa-info-circle me-2"></i>'
        };
        return icons[type] || icons.info;
    }

    // Page Loading States
    showPageLoading(message = 'Loading page...') {
        this.startOperation('page', message);
    }

    hidePageLoading() {
        this.endOperation('page');
    }

    // Navigation Loading States
    showNavigationLoading(targetPage) {
        const message = `Loading ${targetPage}...`;
        this.startOperation('navigation', message);
        
        // Show loading in navigation
        const navElement = document.getElementById('main-nav');
        if (navElement) {
            const loadingIndicator = document.createElement('li');
            loadingIndicator.className = 'nav-item nav-loading';
            loadingIndicator.innerHTML = `
                <span class="nav-link">
                    <div class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></div>
                    ${message}
                </span>
            `;
            navElement.appendChild(loadingIndicator);
        }
    }

    hideNavigationLoading() {
        this.endOperation('navigation');
        
        // Remove loading indicator from navigation
        const loadingIndicator = document.querySelector('.nav-loading');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
    }

    // Utility Methods
    isOperationActive(operationId) {
        return this.activeOperations.has(operationId);
    }

    getActiveOperations() {
        return Array.from(this.activeOperations);
    }

    clearAllOperations() {
        this.activeOperations.clear();
        this.updateGlobalLoadingState();
    }

    // Cleanup
    destroy() {
        this.clearAllOperations();
        
        // Remove global elements
        const overlay = document.getElementById('global-loading-overlay');
        if (overlay) overlay.remove();
        
        const toastContainer = document.getElementById('toast-container');
        if (toastContainer) toastContainer.remove();
        
        const connectionStatus = document.getElementById('ws-connection-status');
        if (connectionStatus) connectionStatus.remove();
    }
}

// Export for global use
window.LoadingManager = LoadingManager;

// Auto-initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (!window.loadingManager) {
        window.loadingManager = new LoadingManager();
    }
});