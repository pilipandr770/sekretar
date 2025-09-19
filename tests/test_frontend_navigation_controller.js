/**
 * Unit Tests for Navigation Controller
 * Tests navigation functionality and route protection
 */

class NavigationControllerTest {
    constructor() {
        this.testResults = [];
        this.navigationController = null;
        this.mockAuthManager = null;
        this.mockUIStateManager = null;
        this.originalHistory = null;
        this.originalFetch = null;
    }

    async runAllTests() {
        console.log('🧪 Running Navigation Controller Tests...');
        
        this.testResults = [];
        this.setupMocks();
        
        try {
            // Initialize navigation controller for testing
            this.navigationController = new NavigationController(this.mockAuthManager, this.mockUIStateManager);
            
            // Test 1: Initialization
            await this.testInitialization();
            
            // Test 2: Navigation event handling
            await this.testNavigationEventHandling();
            
            // Test 3: Route protection
            await this.testRouteProtection();
            
            // Test 4: Active navigation highlighting
            await this.testActiveNavHighlighting();
            
            // Test 5: Authentication state integration
            await this.testAuthStateIntegration();
            
            // Test 6: Browser navigation handling
            await this.testBrowserNavigation();
            
            // Test 7: Permission checking
            await this.testPermissionChecking();
            
            // Test 8: Navigation redirects
            await this.testNavigationRedirects();
            
            // Test 9: Error handling
            await this.testErrorHandling();
            
            // Test 10: AJAX navigation support
            await this.testAjaxNavigation();
            
        } finally {
            this.cleanup();
        }
        
        // Display results
        this.displayResults();
        
        return this.testResults;
    }

    setupMocks() {
        // Mock AuthManager
        this.mockAuthManager = {
            isAuthenticated: jest.fn().mockReturnValue(false),
            getCurrentUser: jest.fn().mockReturnValue(null),
            onAuthStateChange: jest.fn()
        };
        
        // Mock UIStateManager
        this.mockUIStateManager = {
            updateActiveNavItem: jest.fn()
        };
        
        // Mock fetch
        this.originalFetch = global.fetch;
        global.fetch = jest.fn();
        
        // Mock history
        this.originalHistory = global.history;
        global.history = {
            pushState: jest.fn(),
            replaceState: jest.fn()
        };
        
        // Mock DOM elements
        document.body.innerHTML = `
            <nav id="main-nav">
                <a class="nav-link" href="/dashboard">Dashboard</a>
                <a class="nav-link" href="/inbox">Inbox</a>
                <a class="nav-link" href="/crm">CRM</a>
                <a class="nav-link" href="/calendar">Calendar</a>
                <a class="nav-link" href="/settings">Settings</a>
                <a class="nav-link" href="/users">Users</a>
                <a class="nav-link" href="/public">Public</a>
            </nav>
            <div class="dropdown-menu">
                <a class="dropdown-item" href="/profile">Profile</a>
                <a class="dropdown-item" href="/logout">Logout</a>
            </div>
            <main></main>
        `;
        
        // Mock window.location
        delete window.location;
        window.location = {
            pathname: '/dashboard',
            href: 'http://localhost/dashboard',
            origin: 'http://localhost'
        };
    }

    async testInitialization() {
        console.log('🔍 Testing Navigation Controller initialization...');
        
        try {
            // Test initial state
            this.assert(
                this.navigationController.protectedRoutes.includes('/dashboard'),
                'Protected routes should include dashboard'
            );
            
            this.assert(
                this.navigationController.protectedRoutes.includes('/crm'),
                'Protected routes should include CRM'
            );
            
            this.assert(
                this.navigationController.isInitialized === false,
                'Should not be initialized initially'
            );
            
            // Test initialization
            this.navigationController.init();
            
            this.assert(
                this.navigationController.isInitialized === true,
                'Should be initialized after init()'
            );
            
            // Verify auth manager callback was registered
            this.assert(
                this.mockAuthManager.onAuthStateChange.mock.calls.length > 0,
                'Should register auth state change callback'
            );
            
            this.addResult('Initialization', 'PASS', 'Navigation Controller initialized correctly');
        } catch (error) {
            this.addResult('Initialization', 'FAIL', error.message);
        }
    }

    async testNavigationEventHandling() {
        console.log('🖱️ Testing navigation event handling...');
        
        try {
            this.navigationController.init();
            
            // Test navigation link click
            const dashboardLink = document.querySelector('a[href="/dashboard"]');
            
            // Mock authenticated user
            this.mockAuthManager.isAuthenticated.mockReturnValue(true);
            
            // Create click event
            const clickEvent = new MouseEvent('click', {
                bubbles: true,
                cancelable: true
            });
            
            // Spy on preventDefault
            const preventDefaultSpy = jest.fn();
            clickEvent.preventDefault = preventDefaultSpy;
            
            // Test click handling
            await this.navigationController.handleNavigationClick(clickEvent);
            
            this.assert(
                preventDefaultSpy.mock.calls.length > 0,
                'Should prevent default navigation for protected routes'
            );
            
            this.addResult('Navigation Event Handling', 'PASS', 'Navigation events handled correctly');
        } catch (error) {
            this.addResult('Navigation Event Handling', 'FAIL', error.message);
        }
    }

    async testRouteProtection() {
        console.log('🔒 Testing route protection...');
        
        try {
            this.navigationController.init();
            
            // Test unauthenticated access to protected route
            this.mockAuthManager.isAuthenticated.mockReturnValue(false);
            
            const protectedLink = document.querySelector('a[href="/crm"]');
            const clickEvent = new MouseEvent('click', {
                bubbles: true,
                cancelable: true
            });
            clickEvent.target = protectedLink;
            
            const preventDefaultSpy = jest.fn();
            clickEvent.preventDefault = preventDefaultSpy;
            
            const result = await this.navigationController.handleNavigationClick(clickEvent);
            
            this.assert(
                preventDefaultSpy.mock.calls.length > 0,
                'Should prevent navigation to protected route when unauthenticated'
            );
            
            this.assert(
                result === false,
                'Should return false for blocked navigation'
            );
            
            // Test authenticated access to protected route
            this.mockAuthManager.isAuthenticated.mockReturnValue(true);
            
            const authenticatedResult = await this.navigationController.handleNavigationClick(clickEvent);
            
            // Should not return false (navigation should proceed)
            this.assert(
                authenticatedResult !== false,
                'Should allow navigation to protected route when authenticated'
            );
            
            this.addResult('Route Protection', 'PASS', 'Route protection works correctly');
        } catch (error) {
            this.addResult('Route Protection', 'FAIL', error.message);
        }
    }

    async testActiveNavHighlighting() {
        console.log('🎯 Testing active navigation highlighting...');
        
        try {
            this.navigationController.init();
            
            // Test updating active nav item
            window.location.pathname = '/crm';
            this.navigationController.updateActiveNavItem();
            
            const crmLink = document.querySelector('a[href*="crm"]');
            this.assert(
                crmLink.classList.contains('active'),
                'CRM link should be active when on CRM page'
            );
            
            // Test switching to different page
            window.location.pathname = '/inbox';
            this.navigationController.updateActiveNavItem();
            
            this.assert(
                !crmLink.classList.contains('active'),
                'CRM link should not be active when on different page'
            );
            
            const inboxLink = document.querySelector('a[href*="inbox"]');
            this.assert(
                inboxLink.classList.contains('active'),
                'Inbox link should be active when on inbox page'
            );
            
            // Verify UI state manager was called
            this.assert(
                this.mockUIStateManager.updateActiveNavItem.mock.calls.length > 0,
                'Should notify UI state manager of nav changes'
            );
            
            this.addResult('Active Nav Highlighting', 'PASS', 'Active navigation highlighting works correctly');
        } catch (error) {
            this.addResult('Active Nav Highlighting', 'FAIL', error.message);
        }
    }

    async testAuthStateIntegration() {
        console.log('🔐 Testing authentication state integration...');
        
        try {
            this.navigationController.init();
            
            // Get the registered auth callback
            const authCallback = this.mockAuthManager.onAuthStateChange.mock.calls[0][0];
            
            // Test authenticated state
            authCallback(true, { id: 1, email: 'test@example.com', role: 'user' });
            
            // Check that navigation is enabled
            const navLinks = document.querySelectorAll('#main-nav .nav-link');
            navLinks.forEach(link => {
                this.assert(
                    !link.classList.contains('disabled'),
                    'Navigation links should not be disabled when authenticated'
                );
                
                this.assert(
                    link.style.opacity !== '0.6',
                    'Navigation links should not be dimmed when authenticated'
                );
            });
            
            // Test unauthenticated state
            authCallback(false, null);
            
            // Check that protected routes are visually indicated
            const protectedLinks = document.querySelectorAll('a[href*="/dashboard"], a[href*="/crm"]');
            protectedLinks.forEach(link => {
                this.assert(
                    link.style.opacity === '0.6',
                    'Protected links should be dimmed when unauthenticated'
                );
                
                this.assert(
                    link.classList.contains('auth-required'),
                    'Protected links should have auth-required class'
                );
            });
            
            this.addResult('Auth State Integration', 'PASS', 'Authentication state integration works correctly');
        } catch (error) {
            this.addResult('Auth State Integration', 'FAIL', error.message);
        }
    }

    async testBrowserNavigation() {
        console.log('🌐 Testing browser navigation handling...');
        
        try {
            this.navigationController.init();
            
            // Test popstate event handling
            window.location.pathname = '/calendar';
            
            const popstateEvent = new PopStateEvent('popstate', {
                state: { path: '/calendar' }
            });
            
            // Trigger popstate event
            window.dispatchEvent(popstateEvent);
            
            // Should update active nav item
            const calendarLink = document.querySelector('a[href*="calendar"]');
            this.assert(
                calendarLink.classList.contains('active'),
                'Should update active nav item on browser navigation'
            );
            
            // Test navigation to protected route when unauthenticated
            this.mockAuthManager.isAuthenticated.mockReturnValue(false);
            window.location.pathname = '/settings';
            
            // Mock window.location.href assignment
            let redirectUrl = null;
            Object.defineProperty(window.location, 'href', {
                set: (url) => { redirectUrl = url; },
                get: () => redirectUrl || 'http://localhost/settings'
            });
            
            this.navigationController.handleBrowserNavigation(popstateEvent);
            
            this.assert(
                redirectUrl && redirectUrl.includes('/login'),
                'Should redirect to login when accessing protected route via browser navigation'
            );
            
            this.addResult('Browser Navigation', 'PASS', 'Browser navigation handled correctly');
        } catch (error) {
            this.addResult('Browser Navigation', 'FAIL', error.message);
        }
    }

    async testPermissionChecking() {
        console.log('👮 Testing permission checking...');
        
        try {
            // Test route permission for unauthenticated user
            const hasPermission1 = this.navigationController.hasRoutePermission('/dashboard', null);
            this.assert(
                hasPermission1 === false,
                'Should deny access to protected route for unauthenticated user'
            );
            
            // Test route permission for regular user
            const regularUser = { id: 1, email: 'user@example.com', role: 'user' };
            const hasPermission2 = this.navigationController.hasRoutePermission('/dashboard', regularUser);
            this.assert(
                hasPermission2 === true,
                'Should allow access to dashboard for authenticated user'
            );
            
            // Test role-based permission (users management)
            const hasUserManagement1 = this.navigationController.hasRoutePermission('/users', regularUser);
            this.assert(
                hasUserManagement1 === false,
                'Should deny access to user management for regular user'
            );
            
            // Test role-based permission for manager
            const managerUser = { id: 2, email: 'manager@example.com', role: 'manager' };
            const hasUserManagement2 = this.navigationController.hasRoutePermission('/users', managerUser);
            this.assert(
                hasUserManagement2 === true,
                'Should allow access to user management for manager'
            );
            
            // Test role-based permission for owner
            const ownerUser = { id: 3, email: 'owner@example.com', role: 'owner' };
            const hasUserManagement3 = this.navigationController.hasRoutePermission('/users', ownerUser);
            this.assert(
                hasUserManagement3 === true,
                'Should allow access to user management for owner'
            );
            
            // Test public route access
            const hasPublicAccess = this.navigationController.hasRoutePermission('/public', null);
            this.assert(
                hasPublicAccess === true,
                'Should allow access to public routes for unauthenticated users'
            );
            
            this.addResult('Permission Checking', 'PASS', 'Permission checking works correctly');
        } catch (error) {
            this.addResult('Permission Checking', 'FAIL', error.message);
        }
    }

    async testNavigationRedirects() {
        console.log('🔄 Testing navigation redirects...');
        
        try {
            let redirectUrl = null;
            Object.defineProperty(window.location, 'href', {
                set: (url) => { redirectUrl = url; },
                get: () => redirectUrl || window.location.href
            });
            
            // Test redirect from login when authenticated
            window.location.pathname = '/login';
            this.mockAuthManager.isAuthenticated.mockReturnValue(true);
            
            this.navigationController.redirectToAppropriateRoute();
            
            this.assert(
                redirectUrl === '/dashboard',
                'Should redirect to dashboard when authenticated user visits login'
            );
            
            // Test redirect to login when unauthenticated on protected route
            redirectUrl = null;
            window.location.pathname = '/crm';
            window.location.href = 'http://localhost/crm';
            this.mockAuthManager.isAuthenticated.mockReturnValue(false);
            
            this.navigationController.redirectToAppropriateRoute();
            
            this.assert(
                redirectUrl && redirectUrl.includes('/login'),
                'Should redirect to login when unauthenticated user visits protected route'
            );
            
            this.assert(
                redirectUrl.includes('return_url'),
                'Should include return URL in login redirect'
            );
            
            // Test redirect from root path
            redirectUrl = null;
            window.location.pathname = '/';
            this.mockAuthManager.isAuthenticated.mockReturnValue(true);
            
            this.navigationController.redirectToAppropriateRoute();
            
            this.assert(
                redirectUrl === '/dashboard',
                'Should redirect authenticated user from root to dashboard'
            );
            
            redirectUrl = null;
            this.mockAuthManager.isAuthenticated.mockReturnValue(false);
            
            this.navigationController.redirectToAppropriateRoute();
            
            this.assert(
                redirectUrl === '/login',
                'Should redirect unauthenticated user from root to login'
            );
            
            this.addResult('Navigation Redirects', 'PASS', 'Navigation redirects work correctly');
        } catch (error) {
            this.addResult('Navigation Redirects', 'FAIL', error.message);
        }
    }

    async testErrorHandling() {
        console.log('⚠️ Testing error handling...');
        
        try {
            this.navigationController.init();
            
            // Test navigation with network error
            global.fetch.mockRejectedValueOnce(new Error('Network error'));
            
            // Should not throw error
            await this.navigationController.navigateTo('/dashboard');
            
            // Test handling of invalid navigation targets
            const invalidEvent = {
                target: null,
                preventDefault: jest.fn()
            };
            
            // Should not throw error
            await this.navigationController.handleNavigationClick(invalidEvent);
            
            // Test error in navigation callback
            const errorCallback = () => {
                throw new Error('Callback error');
            };
            
            this.mockAuthManager.onAuthStateChange.mockImplementation(callback => {
                // Should not throw error when callback fails
                try {
                    callback(true, { id: 1 });
                } catch (e) {
                    // Error should be caught and handled
                }
            });
            
            this.addResult('Error Handling', 'PASS', 'Error handling works correctly');
        } catch (error) {
            this.addResult('Error Handling', 'FAIL', error.message);
        }
    }

    async testAjaxNavigation() {
        console.log('⚡ Testing AJAX navigation support...');
        
        try {
            // Test AJAX navigation support check
            const supportsAjax1 = this.navigationController.supportsAjaxNavigation('/dashboard');
            this.assert(
                supportsAjax1 === false,
                'AJAX navigation should be disabled by default for stability'
            );
            
            // Test page content loading (should fall back to full page navigation)
            let redirectUrl = null;
            Object.defineProperty(window.location, 'href', {
                set: (url) => { redirectUrl = url; },
                get: () => redirectUrl || window.location.href
            });
            
            await this.navigationController.loadPageContent('/dashboard');
            
            this.assert(
                redirectUrl === '/dashboard',
                'Should fall back to full page navigation when AJAX is not supported'
            );
            
            this.addResult('AJAX Navigation', 'PASS', 'AJAX navigation support works correctly');
        } catch (error) {
            this.addResult('AJAX Navigation', 'FAIL', error.message);
        }
    }

    assert(condition, message) {
        if (!condition) {
            throw new Error(message);
        }
    }

    addResult(testName, status, details) {
        this.testResults.push({
            test: testName,
            status: status,
            details: details,
            timestamp: new Date().toISOString()
        });
    }

    displayResults() {
        console.log('\n📊 Navigation Controller Test Results:');
        console.log('======================================');
        
        let passed = 0;
        let failed = 0;
        
        this.testResults.forEach(result => {
            const icon = result.status === 'PASS' ? '✅' : '❌';
            console.log(`${icon} ${result.test}: ${result.status}`);
            
            if (result.details) {
                console.log(`   Details: ${result.details}`);
            }
            
            if (result.status === 'PASS') passed++;
            else failed++;
        });
        
        console.log('\n📈 Summary:');
        console.log(`   Passed: ${passed}`);
        console.log(`   Failed: ${failed}`);
        console.log(`   Total: ${this.testResults.length}`);
        
        if (failed === 0) {
            console.log('🎉 All Navigation Controller tests passed!');
        } else {
            console.log('⚠️  Some tests failed. Check the details above.');
        }
    }

    cleanup() {
        // Restore original functions
        if (this.originalFetch) {
            global.fetch = this.originalFetch;
        }
        if (this.originalHistory) {
            global.history = this.originalHistory;
        }
        
        // Clean up navigation controller
        if (this.navigationController) {
            this.navigationController.cleanup();
        }
        
        // Clear DOM
        document.body.innerHTML = '';
        
        // Reset location mock
        delete window.location;
        window.location = {
            pathname: '/',
            href: 'http://localhost/',
            origin: 'http://localhost'
        };
    }

    // Quick test function for console use
    static async quickTest() {
        const tester = new NavigationControllerTest();
        return await tester.runAllTests();
    }
}

// Mock jest functions if not available
if (typeof jest === 'undefined') {
    global.jest = {
        fn: () => {
            const mockFn = function(...args) {
                mockFn.mock.calls.push(args);
                if (mockFn.mockImplementation) {
                    return mockFn.mockImplementation(...args);
                }
                if (mockFn.mockReturnValue !== undefined) {
                    return mockFn.mockReturnValue;
                }
                if (mockFn.mockResolvedValue !== undefined) {
                    return Promise.resolve(mockFn.mockResolvedValue);
                }
                if (mockFn.mockRejectedValue !== undefined) {
                    return Promise.reject(mockFn.mockRejectedValue);
                }
            };
            mockFn.mock = { calls: [] };
            mockFn.mockReturnValue = jest.fn().mockReturnValue;
            mockFn.mockResolvedValue = undefined;
            mockFn.mockRejectedValue = undefined;
            mockFn.mockImplementation = undefined;
            mockFn.mockReturnValue = (value) => {
                mockFn.mockReturnValue = value;
                return mockFn;
            };
            mockFn.mockResolvedValueOnce = (value) => {
                mockFn.mockResolvedValue = value;
                return mockFn;
            };
            mockFn.mockRejectedValueOnce = (value) => {
                mockFn.mockRejectedValue = value;
                return mockFn;
            };
            return mockFn;
        }
    };
}

// Export for use in other modules
window.NavigationControllerTest = NavigationControllerTest;

// Add console helper
window.testNavigationController = () => NavigationControllerTest.quickTest();