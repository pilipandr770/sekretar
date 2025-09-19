/**
 * Navigation Controller
 * Handles navigation between application sections with proper authentication checks
 */

class NavigationController {
    constructor(authManager, uiStateManager) {
        this.authManager = authManager;
        this.uiStateManager = uiStateManager;
        this.protectedRoutes = ['/dashboard', '/inbox', '/crm', '/calendar', '/settings', '/users'];
        this.isInitialized = false;
        
        // Bind methods to preserve context
        this.handleNavigationClick = this.handleNavigationClick.bind(this);
        this.updateActiveNavItem = this.updateActiveNavItem.bind(this);
    }

    /**
     * Initialize the navigation controller
     */
    init() {
        if (this.isInitialized) {
            return;
        }

        console.log('Initializing Navigation Controller...');
        
        // Set up navigation event listeners
        this.setupNavigationListeners();
        
        // Initialize navigation state
        this.initializeNavigationState();
        
        // Listen for auth state changes
        if (this.authManager) {
            this.authManager.onAuthStateChange((isAuthenticated, user) => {
                this.onAuthStateChange(isAuthenticated, user);
            });
        }
        
        // Listen for popstate events (browser back/forward)
        window.addEventListener('popstate', (event) => {
            this.handleBrowserNavigation(event);
        });
        
        this.isInitialized = true;
        console.log('Navigation Controller initialized');
    }

    /**
     * Set up navigation event listeners
     */
    setupNavigationListeners() {
        // Handle main navigation links
        const navLinks = document.querySelectorAll('#main-nav .nav-link');
        navLinks.forEach(link => {
            // Skip dropdown toggles
            if (!link.classList.contains('dropdown-toggle')) {
                link.addEventListener('click', this.handleNavigationClick);
            }
        });

        // Handle dropdown navigation links
        const dropdownLinks = document.querySelectorAll('.dropdown-menu .dropdown-item');
        dropdownLinks.forEach(link => {
            link.addEventListener('click', this.handleNavigationClick);
        });
    }

    /**
     * Handle navigation link clicks
     */
    async handleNavigationClick(event) {
        const link = event.target.closest('a');
        if (!link || !link.href) {
            return;
        }

        const href = link.getAttribute('href');
        
        // Skip external links and anchors
        if (href.startsWith('http') || href.startsWith('#')) {
            return;
        }

        // Check if route requires authentication
        const requiresAuth = this.protectedRoutes.some(route => href.includes(route));
        
        if (requiresAuth) {
            // Check authentication status
            const isAuthenticated = this.authManager ? this.authManager.isAuthenticated() : false;
            
            if (!isAuthenticated) {
                event.preventDefault();
                
                // Show authentication required message
                this.showAuthRequiredMessage();
                
                // Redirect to login with return URL
                setTimeout(() => {
                    const returnUrl = encodeURIComponent(window.location.origin + href);
                    window.location.href = `/login?return_url=${returnUrl}`;
                }, 2000);
                
                return false;
            }
        }

        // For authenticated users or non-protected routes, handle navigation
        event.preventDefault();
        await this.navigateTo(href);
    }

    /**
     * Navigate to a specific URL
     */
    async navigateTo(href) {
        try {
            // Show loading state
            this.showNavigationLoading(true);
            
            // Update browser history
            history.pushState(null, '', href);
            
            // Update active navigation item
            this.updateActiveNavItem();
            
            // Load the new page content
            await this.loadPageContent(href);
            
        } catch (error) {
            console.error('Navigation error:', error);
            this.showNavigationError('Failed to navigate. Please try again.');
            
            // Fallback to full page navigation
            window.location.href = href;
        } finally {
            this.showNavigationLoading(false);
        }
    }

    /**
     * Load page content via AJAX (if supported)
     */
    async loadPageContent(href) {
        // Check if AJAX navigation is supported for this route
        if (this.supportsAjaxNavigation(href)) {
            try {
                const response = await fetch(href, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'text/html'
                    }
                });

                if (response.ok) {
                    const html = await response.text();
                    this.updatePageContent(html);
                    return;
                }
            } catch (error) {
                console.warn('AJAX navigation failed, falling back to full page load:', error);
            }
        }

        // Fallback to full page navigation
        window.location.href = href;
    }

    /**
     * Check if AJAX navigation is supported for a route
     */
    supportsAjaxNavigation(href) {
        // For now, disable AJAX navigation to ensure stability
        // This can be enabled later after implementing proper server-side support
        return false;
        
        // Future implementation:
        // const ajaxSupportedRoutes = ['/dashboard', '/inbox', '/crm', '/calendar'];
        // return ajaxSupportedRoutes.some(route => href.includes(route));
    }

    /**
     * Update page content with new HTML
     */
    updatePageContent(html) {
        // Parse the new HTML
        const parser = new DOMParser();
        const newDoc = parser.parseFromString(html, 'text/html');
        
        // Update the main content area
        const newMain = newDoc.querySelector('main');
        const currentMain = document.querySelector('main');
        
        if (newMain && currentMain) {
            currentMain.innerHTML = newMain.innerHTML;
            
            // Update page title
            const newTitle = newDoc.querySelector('title');
            if (newTitle) {
                document.title = newTitle.textContent;
            }
            
            // Re-initialize any JavaScript components in the new content
            this.reinitializePageComponents();
        }
    }

    /**
     * Re-initialize JavaScript components after AJAX navigation
     */
    reinitializePageComponents() {
        // Trigger custom event for other components to reinitialize
        document.dispatchEvent(new CustomEvent('page:loaded', {
            detail: { 
                url: window.location.href,
                timestamp: Date.now()
            }
        }));
        
        // Re-initialize Bootstrap components
        if (window.bootstrap) {
            // Initialize tooltips
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
            
            // Initialize popovers
            const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
            popoverTriggerList.map(function (popoverTriggerEl) {
                return new bootstrap.Popover(popoverTriggerEl);
            });
        }
    }

    /**
     * Update active navigation item based on current URL
     */
    updateActiveNavItem() {
        const currentPath = window.location.pathname;
        
        // Remove active class from all nav items
        document.querySelectorAll('#main-nav .nav-link').forEach(link => {
            link.classList.remove('active');
        });

        // Add active class to current nav item
        let activeLink = null;
        
        if (currentPath.includes('/dashboard')) {
            activeLink = document.querySelector('#main-nav .nav-link[href*="dashboard"]');
        } else if (currentPath.includes('/inbox')) {
            activeLink = document.querySelector('#main-nav .nav-link[href*="inbox"]');
        } else if (currentPath.includes('/crm')) {
            activeLink = document.querySelector('#main-nav .nav-link[href*="crm"]');
        } else if (currentPath.includes('/calendar')) {
            activeLink = document.querySelector('#main-nav .nav-link[href*="calendar"]');
        }

        if (activeLink) {
            activeLink.classList.add('active');
        }

        // Update UI state manager
        if (this.uiStateManager) {
            this.uiStateManager.updateActiveNavItem();
        }
    }

    /**
     * Handle authentication state changes
     */
    onAuthStateChange(isAuthenticated, user) {
        if (isAuthenticated) {
            this.enableNavigation();
        } else {
            this.handleUnauthenticatedNavigation();
        }
    }

    /**
     * Enable navigation for authenticated users
     */
    enableNavigation() {
        const navLinks = document.querySelectorAll('#main-nav .nav-link');
        navLinks.forEach(link => {
            link.classList.remove('disabled');
            link.style.pointerEvents = 'auto';
            link.style.opacity = '1';
            
            // Remove any disabled tooltips
            link.removeAttribute('title');
        });
    }

    /**
     * Handle navigation for unauthenticated users
     */
    handleUnauthenticatedNavigation() {
        const navLinks = document.querySelectorAll('#main-nav .nav-link');
        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            const requiresAuth = this.protectedRoutes.some(route => href && href.includes(route));
            
            if (requiresAuth) {
                // Add visual indication that authentication is required
                link.style.opacity = '0.6';
                link.setAttribute('title', 'Login required to access this feature');
                link.classList.add('auth-required');
            } else {
                // Remove auth required styling for public routes
                link.style.opacity = '1';
                link.removeAttribute('title');
                link.classList.remove('auth-required');
            }
        });
    }

    /**
     * Check if user has permission to access a route
     */
    hasRoutePermission(href, user = null) {
        const currentUser = user || (this.authManager ? this.authManager.getCurrentUser() : null);
        
        // Check if route requires authentication
        const requiresAuth = this.protectedRoutes.some(route => href.includes(route));
        if (requiresAuth && !currentUser) {
            return false;
        }
        
        // Check role-based permissions
        if (href.includes('/users') && currentUser) {
            // User management requires owner or manager role
            return currentUser.role === 'owner' || currentUser.role === 'manager';
        }
        
        return true;
    }

    /**
     * Redirect to appropriate page based on authentication status
     */
    redirectToAppropriateRoute() {
        const currentPath = window.location.pathname;
        const isAuthenticated = this.authManager ? this.authManager.isAuthenticated() : false;
        
        // If on login page and authenticated, redirect to dashboard
        if (currentPath.includes('/login') && isAuthenticated) {
            const returnUrl = new URLSearchParams(window.location.search).get('return_url');
            window.location.href = returnUrl || '/dashboard';
            return;
        }
        
        // If on protected route and not authenticated, redirect to login
        if (this.isProtectedRoute(currentPath) && !isAuthenticated) {
            const returnUrl = encodeURIComponent(window.location.href);
            window.location.href = `/login?return_url=${returnUrl}`;
            return;
        }
        
        // If on root path, redirect based on auth status
        if (currentPath === '/') {
            window.location.href = isAuthenticated ? '/dashboard' : '/login';
            return;
        }
    }

    /**
     * Show authentication required message
     */
    showAuthRequiredMessage() {
        this.showAlert('warning', 'Please log in to access this feature.');
    }

    /**
     * Show navigation loading state
     */
    showNavigationLoading(loading) {
        if (loading) {
            // Add loading indicator to navbar
            const navbar = document.querySelector('.navbar');
            if (navbar && !navbar.querySelector('.nav-loading')) {
                const loadingDiv = document.createElement('div');
                loadingDiv.className = 'nav-loading';
                loadingDiv.innerHTML = '<div class="spinner-border spinner-border-sm text-light" role="status"></div>';
                loadingDiv.style.cssText = 'position: absolute; top: 50%; right: 20px; transform: translateY(-50%);';
                navbar.style.position = 'relative';
                navbar.appendChild(loadingDiv);
            }
        } else {
            // Remove loading indicator
            const loadingDiv = document.querySelector('.nav-loading');
            if (loadingDiv) {
                loadingDiv.remove();
            }
        }
    }

    /**
     * Show navigation error
     */
    showNavigationError(message) {
        this.showAlert('danger', message);
    }

    /**
     * Show alert message
     */
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

    /**
     * Check if current route requires authentication
     */
    isProtectedRoute(path = window.location.pathname) {
        return this.protectedRoutes.some(route => path.includes(route));
    }

    /**
     * Get current active navigation item
     */
    getActiveNavItem() {
        const currentPath = window.location.pathname;
        
        if (currentPath.includes('/dashboard')) return 'dashboard';
        if (currentPath.includes('/inbox')) return 'inbox';
        if (currentPath.includes('/crm')) return 'crm';
        if (currentPath.includes('/calendar')) return 'calendar';
        if (currentPath.includes('/settings')) return 'settings';
        if (currentPath.includes('/users')) return 'users';
        
        return null;
    }

    /**
     * Handle browser navigation (back/forward buttons)
     */
    handleBrowserNavigation(event) {
        // Update active navigation item
        this.updateActiveNavItem();
        
        // Check if current route requires authentication
        const currentPath = window.location.pathname;
        const isAuthenticated = this.authManager ? this.authManager.isAuthenticated() : false;
        
        if (this.isProtectedRoute(currentPath) && !isAuthenticated) {
            // Redirect to login if accessing protected route without authentication
            const returnUrl = encodeURIComponent(window.location.href);
            window.location.href = `/login?return_url=${returnUrl}`;
        }
    }

    /**
     * Initialize navigation state on page load
     */
    initializeNavigationState() {
        // Update active navigation item
        this.updateActiveNavItem();
        
        // Handle authentication-based redirects
        this.redirectToAppropriateRoute();
        
        // Set up navigation state based on current auth status
        const isAuthenticated = this.authManager ? this.authManager.isAuthenticated() : false;
        if (isAuthenticated) {
            this.enableNavigation();
        } else {
            this.handleUnauthenticatedNavigation();
        }
    }

    /**
     * Cleanup
     */
    cleanup() {
        // Remove event listeners
        const navLinks = document.querySelectorAll('#main-nav .nav-link, .dropdown-menu .dropdown-item');
        navLinks.forEach(link => {
            link.removeEventListener('click', this.handleNavigationClick);
        });
        
        window.removeEventListener('popstate', this.handleBrowserNavigation);
    }
}

// Export for use in other modules
window.NavigationController = NavigationController;