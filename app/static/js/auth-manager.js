/**
 * Enhanced Authentication Manager
 * Handles authentication state management and UI synchronization
 */

class AuthenticationManager {
    constructor() {
        this.currentUser = null;
        this.authCallbacks = [];
        this.isInitialized = false;
        this.baseURL = window.location.origin;
        
        // Bind methods to preserve context
        this.checkAuthStatus = this.checkAuthStatus.bind(this);
        this.handleLogin = this.handleLogin.bind(this);
        this.handleLogout = this.handleLogout.bind(this);
        this.showAuthenticatedUI = this.showAuthenticatedUI.bind(this);
        this.showUnauthenticatedUI = this.showUnauthenticatedUI.bind(this);
    }

    /**
     * Initialize the authentication manager
     */
    async init() {
        if (this.isInitialized) {
            return;
        }

        console.log('Initializing Authentication Manager...');
        
        // Check current authentication status
        await this.checkAuthStatus();
        
        // Set up event listeners
        this.setupEventListeners();
        
        this.isInitialized = true;
        console.log('Authentication Manager initialized');
    }

    /**
     * Set up event listeners for authentication-related events
     */
    setupEventListeners() {
        // Listen for storage changes (for multi-tab synchronization)
        window.addEventListener('storage', (e) => {
            if (e.key === 'access_token') {
                if (e.newValue === null) {
                    // Token was removed in another tab
                    this.handleLogout(false); // Don't make API call
                } else if (e.oldValue === null) {
                    // Token was added in another tab
                    this.checkAuthStatus();
                }
            }
        });

        // Listen for beforeunload to clean up
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });

        // Set up login form handler if present
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', this.handleLogin);
        }

        // Set up logout handlers
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="logout"]') || 
                e.target.closest('[data-action="logout"]')) {
                e.preventDefault();
                this.handleLogout();
            }
        });
    }

    /**
     * Check current authentication status
     */
    async checkAuthStatus() {
        const token = localStorage.getItem('access_token');
        
        if (!token) {
            this.showUnauthenticatedUI();
            return false;
        }

        try {
            const response = await fetch('/api/v1/auth/me', {
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.data?.user) {
                    this.currentUser = data.data.user;
                    this.showAuthenticatedUI(this.currentUser);
                    this.notifyAuthStateChange(true, this.currentUser);
                    return true;
                }
            } else if (response.status === 401) {
                // Token is invalid, try to refresh
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    return await this.checkAuthStatus();
                }
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            
            // Use error handler if available
            if (window.errorHandler) {
                window.errorHandler.handleNetworkError({
                    url: '/api/v1/auth/me',
                    error: error,
                    isOnline: navigator.onLine
                });
            }
        }
        
        // If we get here, authentication failed
        this.clearTokens();
        this.showUnauthenticatedUI();
        this.notifyAuthStateChange(false, null);
        return false;
    }

    /**
     * Attempt to refresh the access token
     */
    async refreshToken() {
        const refreshToken = localStorage.getItem('refresh_token');
        
        if (!refreshToken) {
            return false;
        }

        try {
            const response = await fetch('/api/v1/auth/refresh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${refreshToken}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success && data.data?.access_token) {
                    localStorage.setItem('access_token', data.data.access_token);
                    if (data.data.refresh_token) {
                        localStorage.setItem('refresh_token', data.data.refresh_token);
                    }
                    return true;
                }
            }
        } catch (error) {
            console.error('Token refresh failed:', error);
            
            // Use error handler if available
            if (window.errorHandler) {
                window.errorHandler.handleNetworkError({
                    url: '/api/v1/auth/refresh',
                    error: error,
                    isOnline: navigator.onLine
                });
            }
        }

        return false;
    }

    /**
     * Handle login form submission
     */
    async handleLogin(e) {
        e.preventDefault();
        
        const form = e.target;
        const submitBtn = form.querySelector('button[type="submit"]');
        const spinner = submitBtn.querySelector('.spinner-border');
        
        // Emit loading start event
        this.emitEvent('auth:login_start');
        
        // Show loading state
        this.setLoadingState(submitBtn, spinner, true);
        
        // Clear previous errors
        this.clearFormErrors(form);
        
        try {
            const formData = new FormData(form);
            const response = await fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: formData.get('email'),
                    password: formData.get('password')
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Store tokens
                localStorage.setItem('access_token', data.data.access_token);
                if (data.data.refresh_token) {
                    localStorage.setItem('refresh_token', data.data.refresh_token);
                }
                
                // Update current user
                this.currentUser = data.data.user;
                
                // Emit success event
                this.emitEvent('auth:login_success', { user: this.currentUser });
                
                // Show success message
                this.showAlert('success', data.message || 'Login successful');
                
                // Update UI immediately
                this.showAuthenticatedUI(this.currentUser);
                
                // Notify listeners
                this.notifyAuthStateChange(true, this.currentUser);
                
                // Hide login form if on same page
                this.hideLoginForm();
                
                // Redirect to dashboard after a short delay
                setTimeout(() => {
                    const returnUrl = new URLSearchParams(window.location.search).get('return_url');
                    window.location.href = returnUrl || '/dashboard';
                }, 1000);
                
            } else {
                // Emit error event
                this.emitEvent('auth:login_error', { 
                    message: data.error?.message || 'Login failed' 
                });
                
                // Show error message
                this.showAlert('danger', data.error?.message || 'Login failed');
                
                // Show field-specific errors
                this.showFormErrors(form, data.error?.details?.validation_errors);
            }
            
        } catch (error) {
            console.error('Login error:', error);
            
            // Emit error event
            this.emitEvent('auth:login_error', { 
                message: 'An error occurred. Please try again.',
                error: error
            });
            
            // Use error handler for better user feedback
            if (window.errorHandler) {
                window.errorHandler.handleNetworkError({
                    url: '/api/v1/auth/login',
                    error: error,
                    isOnline: navigator.onLine
                });
            } else {
                this.showAlert('danger', 'An error occurred. Please try again.');
            }
        } finally {
            // Hide loading state
            this.setLoadingState(submitBtn, spinner, false);
        }
    }

    /**
     * Handle logout
     */
    async handleLogout(makeApiCall = true) {
        // Emit logout start event
        this.emitEvent('auth:logout_start');
        
        try {
            if (makeApiCall) {
                const token = localStorage.getItem('access_token');
                
                if (token) {
                    await fetch('/api/v1/auth/logout', {
                        method: 'POST',
                        headers: { 
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        }
                    });
                }
            }
        } catch (error) {
            console.error('Logout error:', error);
            
            // Use error handler if available
            if (window.errorHandler) {
                window.errorHandler.handleNetworkError({
                    url: '/api/v1/auth/logout',
                    error: error,
                    isOnline: navigator.onLine
                });
            }
        } finally {
            // Clear tokens and user data
            this.clearTokens();
            this.currentUser = null;
            
            // Update UI
            this.showUnauthenticatedUI();
            
            // Emit logout complete event
            this.emitEvent('auth:logout_complete');
            
            // Notify listeners
            this.notifyAuthStateChange(false, null);
            
            // Redirect to login if not already there
            if (!window.location.pathname.includes('/login')) {
                window.location.href = '/login';
            }
        }
    }

    /**
     * Show authenticated UI state
     */
    showAuthenticatedUI(user) {
        console.log('Showing authenticated UI for:', user.email);
        
        // Update user name in navbar
        const userNameElement = document.getElementById('userName');
        if (userNameElement) {
            userNameElement.textContent = user.first_name || user.email;
        }
        
        // Show/hide menu items
        this.toggleElement('auth-links', false);
        this.toggleElement('auth-links-register', false);
        this.toggleElement('user-links', true);
        this.toggleElement('user-links-divider', true);
        this.toggleElement('user-links-logout', true);
        
        // Show user management for owners/managers
        if (user.role === 'owner' || user.role === 'manager') {
            this.toggleElement('user-links-users', true);
        }
        
        // Enable main navigation
        this.enableMainNavigation();
        
        // Hide login form if present
        this.hideLoginForm();
        
        // Show main content if hidden
        this.showMainContent();
    }

    /**
     * Show unauthenticated UI state
     */
    showUnauthenticatedUI() {
        console.log('Showing unauthenticated UI');
        
        // Show login/register links
        this.toggleElement('auth-links', true);
        this.toggleElement('auth-links-register', true);
        this.toggleElement('user-links', false);
        this.toggleElement('user-links-users', false);
        this.toggleElement('user-links-divider', false);
        this.toggleElement('user-links-logout', false);
        
        // Reset user name
        const userNameElement = document.getElementById('userName');
        if (userNameElement) {
            userNameElement.textContent = 'Account';
        }
        
        // Disable main navigation for unauthenticated users
        this.disableMainNavigation();
        
        // Show login form if on protected page
        this.showLoginFormIfNeeded();
    }

    /**
     * Hide login form after successful authentication
     */
    hideLoginForm() {
        const loginForm = document.getElementById('loginForm');
        const loginCard = loginForm?.closest('.card');
        
        if (loginCard) {
            loginCard.style.transition = 'opacity 0.3s ease-out';
            loginCard.style.opacity = '0';
            
            setTimeout(() => {
                loginCard.style.display = 'none';
            }, 300);
        }
    }

    /**
     * Show login form if needed
     */
    showLoginFormIfNeeded() {
        // Only show login form on protected pages if user is not authenticated
        const protectedRoutes = ['/dashboard', '/inbox', '/crm', '/calendar', '/settings'];
        const currentPath = window.location.pathname;
        
        if (protectedRoutes.some(route => currentPath.includes(route))) {
            // Redirect to login page with return URL
            const returnUrl = encodeURIComponent(window.location.href);
            window.location.href = `/login?return_url=${returnUrl}`;
        }
    }

    /**
     * Show main content
     */
    showMainContent() {
        const mainContent = document.querySelector('main');
        if (mainContent) {
            mainContent.style.display = 'block';
        }
    }

    /**
     * Enable main navigation (handled by NavigationController)
     */
    enableMainNavigation() {
        // Navigation is now handled by NavigationController
        // This method is kept for backward compatibility
        console.log('Navigation enabled for authenticated user');
    }

    /**
     * Disable main navigation (handled by NavigationController)
     */
    disableMainNavigation() {
        // Navigation is now handled by NavigationController
        // This method is kept for backward compatibility
        console.log('Navigation disabled for unauthenticated user');
    }

    /**
     * Register callback for authentication state changes
     */
    onAuthStateChange(callback) {
        if (typeof callback === 'function') {
            this.authCallbacks.push(callback);
        }
    }

    /**
     * Notify all registered callbacks of authentication state change
     */
    notifyAuthStateChange(isAuthenticated, user) {
        this.authCallbacks.forEach(callback => {
            try {
                callback(isAuthenticated, user);
            } catch (error) {
                console.error('Auth callback error:', error);
            }
        });
    }

    /**
     * Get current authentication state
     */
    getAuthState() {
        return {
            isAuthenticated: !!this.currentUser,
            user: this.currentUser,
            token: localStorage.getItem('access_token')
        };
    }

    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        return !!this.currentUser;
    }

    /**
     * Get current user
     */
    getCurrentUser() {
        return this.currentUser;
    }

    /**
     * Utility methods
     */
    toggleElement(id, show) {
        const element = document.getElementById(id);
        if (element) {
            if (show) {
                element.classList.remove('d-none');
            } else {
                element.classList.add('d-none');
            }
        }
    }

    setLoadingState(button, spinner, loading) {
        if (button) {
            button.disabled = loading;
        }
        if (spinner) {
            if (loading) {
                spinner.classList.remove('d-none');
            } else {
                spinner.classList.add('d-none');
            }
        }
    }

    clearFormErrors(form) {
        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        form.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');
    }

    showFormErrors(form, errors) {
        if (errors) {
            for (const [field, messages] of Object.entries(errors)) {
                const input = form.querySelector(`[name="${field}"]`);
                if (input) {
                    input.classList.add('is-invalid');
                    const feedback = input.nextElementSibling;
                    if (feedback && feedback.classList.contains('invalid-feedback')) {
                        feedback.textContent = messages[0];
                    }
                }
            }
        }
    }

    showAlert(type, message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container') || document.querySelector('main');
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

    clearTokens() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    }

    cleanup() {
        this.authCallbacks = [];
    }
}

    /**
     * Emit custom events for loading states and user feedback
     */
    emitEvent(eventName, data = {}) {
        const event = new CustomEvent(eventName, { detail: data });
        document.dispatchEvent(event);
    }
}

// Export for use in other modules
window.AuthenticationManager = AuthenticationManager;