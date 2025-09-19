/**
 * Integration Tests for Authentication Flow
 * Tests complete authentication flow including UI updates
 */

class AuthenticationFlowIntegrationTest {
    constructor() {
        this.testResults = [];
        this.authManager = null;
        this.navigationController = null;
        this.uiStateManager = null;
        this.originalFetch = null;
        this.originalLocalStorage = null;
    }

    async runAllTests() {
        console.log('🧪 Running Authentication Flow Integration Tests...');
        
        this.testResults = [];
        this.setupMocks();
        
        try {
            // Initialize components
            this.initializeComponents();
            
            // Test 1: Complete login flow
            await this.testCompleteLoginFlow();
            
            // Test 2: Authentication state synchronization
            await this.testAuthStateSynchronization();
            
            // Test 3: Navigation after authentication
            await this.testNavigationAfterAuth();
            
            // Test 4: UI updates during authentication
            await this.testUIUpdatesDuringAuth();
            
            // Test 5: Complete logout flow
            await this.testCompleteLogoutFlow();
            
            // Test 6: Multi-component integration
            await this.testMultiComponentIntegration();
            
            // Test 7: Error handling integration
            await this.testErrorHandlingIntegration();
            
            // Test 8: Token refresh integration
            await this.testTokenRefreshIntegration();
            
        } finally {
            this.cleanup();
        }
        
        // Display results
        this.displayResults();
        
        return this.testResults;
    }

    setupMocks() {
        // Mock fetch
        this.originalFetch = global.fetch;
        global.fetch = jest.fn();
        
        // Mock localStorage
        this.originalLocalStorage = global.localStorage;
        global.localStorage = {
            getItem: jest.fn(),
            setItem: jest.fn(),
            removeItem: jest.fn(),
            clear: jest.fn()
        };
        
        // Mock DOM elements for complete authentication flow
        document.body.innerHTML = `
            <nav id="main-nav">
                <a class="nav-link" href="/dashboard">Dashboard</a>
                <a class="nav-link" href="/inbox">Inbox</a>
                <a class="nav-link" href="/crm">CRM</a>
                <a class="nav-link" href="/calendar">Calendar</a>
            </nav>
            
            <div id="auth-links" class="">
                <a href="/login">Login</a>
                <a href="/register">Register</a>
            </div>
            
            <div id="user-links" class="d-none">
                <span id="userName">Account</span>
                <a href="/profile">Profile</a>
            </div>
            
            <div id="user-links-users" class="d-none">
                <a href="/users">Users</a>
            </div>
            
            <div id="user-links-divider" class="d-none">
                <hr>
            </div>
            
            <div id="user-links-logout" class="d-none">
                <a href="#" data-action="logout">Logout</a>
            </div>
            
            <form id="loginForm">
                <input name="email" type="email" value="test@example.com">
                <input name="password" type="password" value="password123">
                <button type="submit">
                    <span class="spinner-border d-none"></span>
                    Login
                </button>
                <div class="invalid-feedback"></div>
            </form>
            
            <main style="display: none;">
                <div class="container">
                    <h1>Dashboard</h1>
                </div>
            </main>
            
            <div id="language-switcher"></div>
        `;
        
        // Mock window.location
        delete window.location;
        window.location = {
            pathname: '/login',
            search: '',
            href: 'http://localhost/login',
            origin: 'http://localhost'
        };
        
        // Mock history
        global.history = {
            pushState: jest.fn(),
            replaceState: jest.fn()
        };
        
        // Mock document.documentElement
        document.documentElement.lang = 'en';
    }

    initializeComponents() {
        // Initialize UI State Manager
        this.uiStateManager = new UIStateManager();
        this.uiStateManager.init();
        
        // Initialize Authentication Manager
        this.authManager = new AuthenticationManager();
        
        // Initialize Navigation Controller
        this.navigationController = new NavigationController(this.authManager, this.uiStateManager);
        
        // Integrate components
        this.uiStateManager.integrateWithAuthManager(this.authManager);
        this.uiStateManager.integrateWithNavigationController(this.navigationController);
        
        // Initialize all components
        this.authManager.init();
        this.navigationController.init();
    }

    async testCompleteLoginFlow() {
        console.log('🔑 Testing complete login flow...');
        
        try {
            // Mock successful login response
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    success: true,
                    data: {
                        access_token: 'test_access_token',
                        refresh_token: 'test_refresh_token',
                        user: {
                            id: 1,
                            email: 'test@example.com',
                            first_name: 'Test',
                            last_name: 'User',
                            role: 'user'
                        }
                    },
                    message: 'Login successful'
                })
            });
            
            // Track UI state changes
            let authStateChanged = false;
            let finalAuthState = null;
            
            this.uiStateManager.subscribe((newState, oldState) => {
                if (newState.isAuthenticated !== oldState.isAuthenticated) {
                    authStateChanged = true;
                    finalAuthState = newState;
                }
            });
            
            // Simulate login form submission
            const form = document.getElementById('loginForm');
            const event = new Event('submit', { bubbles: true, cancelable: true });
            
            await this.authManager.handleLogin(event);
            
            // Verify authentication state
            this.assert(
                this.authManager.isAuthenticated() === true,
                'Authentication manager should show authenticated state'
            );
            
            this.assert(
                this.authManager.getCurrentUser().email === 'test@example.com',
                'Should store correct user data'
            );
            
            // Verify UI state manager integration
            this.assert(
                authStateChanged === true,
                'UI state manager should receive auth state change'
            );
            
            this.assert(
                finalAuthState.isAuthenticated === true,
                'UI state should reflect authenticated status'
            );
            
            // Verify UI updates
            const authLinks = document.getElementById('auth-links');
            const userLinks = document.getElementById('user-links');
            const userName = document.getElementById('userName');
            
            this.assert(
                authLinks.classList.contains('d-none'),
                'Auth links should be hidden after login'
            );
            
            this.assert(
                !userLinks.classList.contains('d-none'),
                'User links should be visible after login'
            );
            
            this.assert(
                userName.textContent === 'Test',
                'User name should be displayed correctly'
            );
            
            // Verify navigation is enabled
            const navLinks = document.querySelectorAll('#main-nav .nav-link');
            navLinks.forEach(link => {
                this.assert(
                    !link.classList.contains('disabled'),
                    'Navigation links should be enabled after login'
                );
            });
            
            // Verify tokens were stored
            this.assert(
                global.localStorage.setItem.mock.calls.some(call => 
                    call[0] === 'access_token' && call[1] === 'test_access_token'
                ),
                'Access token should be stored'
            );
            
            this.addResult('Complete Login Flow', 'PASS', 'Complete login flow works correctly');
        } catch (error) {
            this.addResult('Complete Login Flow', 'FAIL', error.message);
        }
    }

    async testAuthStateSynchronization() {
        console.log('🔄 Testing authentication state synchronization...');
        
        try {
            // Set up authenticated state
            const testUser = {
                id: 1,
                email: 'test@example.com',
                first_name: 'Test',
                role: 'manager'
            };
            
            this.authManager.currentUser = testUser;
            this.authManager.showAuthenticatedUI(testUser);
            
            // Verify UI state manager receives the change
            this.uiStateManager.updateAuthState(true, testUser);
            
            const uiState = this.uiStateManager.getState();
            this.assert(
                uiState.isAuthenticated === true,
                'UI state should reflect authentication'
            );
            
            this.assert(
                uiState.currentUser.email === 'test@example.com',
                'UI state should contain user data'
            );
            
            // Verify navigation controller receives the change
            const authCallback = this.authManager.authCallbacks[0];
            if (authCallback) {
                authCallback(true, testUser);
            }
            
            // Check role-based UI updates
            const userManagementLink = document.getElementById('user-links-users');
            this.assert(
                !userManagementLink.classList.contains('d-none'),
                'User management should be visible for manager role'
            );
            
            // Test state synchronization across components
            this.uiStateManager.synchronizeState();
            
            // Verify body classes are updated
            this.assert(
                document.body.classList.contains('authenticated'),
                'Body should have authenticated class'
            );
            
            this.assert(
                !document.body.classList.contains('unauthenticated'),
                'Body should not have unauthenticated class'
            );
            
            this.addResult('Auth State Synchronization', 'PASS', 'Authentication state synchronization works correctly');
        } catch (error) {
            this.addResult('Auth State Synchronization', 'FAIL', error.message);
        }
    }

    async testNavigationAfterAuth() {
        console.log('🧭 Testing navigation after authentication...');
        
        try {
            // Set up authenticated state
            this.authManager.currentUser = {
                id: 1,
                email: 'test@example.com',
                role: 'user'
            };
            
            // Test navigation to protected route
            const crmLink = document.querySelector('a[href="/crm"]');
            const clickEvent = new MouseEvent('click', {
                bubbles: true,
                cancelable: true
            });
            
            Object.defineProperty(clickEvent, 'target', {
                value: crmLink,
                writable: false
            });
            
            const preventDefaultSpy = jest.fn();
            clickEvent.preventDefault = preventDefaultSpy;
            
            // Mock window.location.href assignment
            let redirectUrl = null;
            Object.defineProperty(window.location, 'href', {
                set: (url) => { redirectUrl = url; },
                get: () => redirectUrl || window.location.href
            });
            
            await this.navigationController.handleNavigationClick(clickEvent);
            
            // Should allow navigation for authenticated user
            this.assert(
                preventDefaultSpy.mock.calls.length > 0,
                'Should prevent default to handle navigation programmatically'
            );
            
            // Test active navigation highlighting
            window.location.pathname = '/crm';
            this.navigationController.updateActiveNavItem();
            
            this.assert(
                crmLink.classList.contains('active'),
                'CRM link should be highlighted when active'
            );
            
            // Verify UI state manager is notified
            const activeNavItem = this.uiStateManager.getActiveNavItem();
            this.assert(
                activeNavItem === 'crm',
                'UI state manager should track active navigation'
            );
            
            this.addResult('Navigation After Auth', 'PASS', 'Navigation after authentication works correctly');
        } catch (error) {
            this.addResult('Navigation After Auth', 'FAIL', error.message);
        }
    }

    async testUIUpdatesDuringAuth() {
        console.log('🎨 Testing UI updates during authentication...');
        
        try {
            // Test loading states during login
            const form = document.getElementById('loginForm');
            const submitButton = form.querySelector('button[type="submit"]');
            const spinner = submitButton.querySelector('.spinner-border');
            
            // Mock delayed login response
            global.fetch.mockImplementation(() => 
                new Promise(resolve => {
                    setTimeout(() => {
                        resolve({
                            ok: true,
                            json: () => Promise.resolve({
                                success: true,
                                data: {
                                    access_token: 'test_token',
                                    user: { id: 1, email: 'test@example.com', first_name: 'Test' }
                                }
                            })
                        });
                    }, 100);
                })
            );
            
            // Start login process
            const event = new Event('submit', { bubbles: true, cancelable: true });
            const loginPromise = this.authManager.handleLogin(event);
            
            // Check loading state immediately
            this.assert(
                submitButton.disabled === true,
                'Submit button should be disabled during login'
            );
            
            this.assert(
                !spinner.classList.contains('d-none'),
                'Loading spinner should be visible during login'
            );
            
            // Wait for login to complete
            await loginPromise;
            
            // Check that loading state is cleared
            this.assert(
                submitButton.disabled === false,
                'Submit button should be enabled after login'
            );
            
            this.assert(
                spinner.classList.contains('d-none'),
                'Loading spinner should be hidden after login'
            );
            
            // Test form hiding after successful login
            const loginCard = form.closest('.card');
            if (loginCard) {
                // Should have transition styles applied
                this.assert(
                    loginCard.style.transition.includes('opacity'),
                    'Login form should have fade transition'
                );
            }
            
            // Test main content visibility
            const mainContent = document.querySelector('main');
            this.assert(
                mainContent.style.display === 'block',
                'Main content should be visible after login'
            );
            
            this.addResult('UI Updates During Auth', 'PASS', 'UI updates during authentication work correctly');
        } catch (error) {
            this.addResult('UI Updates During Auth', 'FAIL', error.message);
        }
    }

    async testCompleteLogoutFlow() {
        console.log('🚪 Testing complete logout flow...');
        
        try {
            // Set up authenticated state
            this.authManager.currentUser = {
                id: 1,
                email: 'test@example.com',
                first_name: 'Test'
            };
            
            global.localStorage.getItem.mockReturnValue('test_token');
            
            // Mock logout response
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ success: true })
            });
            
            // Track UI state changes
            let authStateChanged = false;
            let finalAuthState = null;
            
            this.uiStateManager.subscribe((newState, oldState) => {
                if (newState.isAuthenticated !== oldState.isAuthenticated) {
                    authStateChanged = true;
                    finalAuthState = newState;
                }
            });
            
            // Mock window.location.href assignment
            let redirectUrl = null;
            Object.defineProperty(window.location, 'href', {
                set: (url) => { redirectUrl = url; },
                get: () => redirectUrl || window.location.href
            });
            
            // Perform logout
            await this.authManager.handleLogout();
            
            // Verify authentication state
            this.assert(
                this.authManager.isAuthenticated() === false,
                'Authentication manager should show unauthenticated state'
            );
            
            this.assert(
                this.authManager.getCurrentUser() === null,
                'Current user should be cleared'
            );
            
            // Verify UI state manager integration
            this.assert(
                authStateChanged === true,
                'UI state manager should receive auth state change'
            );
            
            this.assert(
                finalAuthState.isAuthenticated === false,
                'UI state should reflect unauthenticated status'
            );
            
            // Verify UI updates
            const authLinks = document.getElementById('auth-links');
            const userLinks = document.getElementById('user-links');
            const userName = document.getElementById('userName');
            
            this.assert(
                !authLinks.classList.contains('d-none'),
                'Auth links should be visible after logout'
            );
            
            this.assert(
                userLinks.classList.contains('d-none'),
                'User links should be hidden after logout'
            );
            
            this.assert(
                userName.textContent === 'Account',
                'User name should be reset after logout'
            );
            
            // Verify tokens were cleared
            this.assert(
                global.localStorage.removeItem.mock.calls.some(call => 
                    call[0] === 'access_token'
                ),
                'Access token should be removed'
            );
            
            // Verify redirect to login
            this.assert(
                redirectUrl === '/login',
                'Should redirect to login page after logout'
            );
            
            this.addResult('Complete Logout Flow', 'PASS', 'Complete logout flow works correctly');
        } catch (error) {
            this.addResult('Complete Logout Flow', 'FAIL', error.message);
        }
    }

    async testMultiComponentIntegration() {
        console.log('🔗 Testing multi-component integration...');
        
        try {
            // Test component communication during authentication
            let uiStateUpdates = 0;
            let navStateUpdates = 0;
            
            this.uiStateManager.subscribe(() => {
                uiStateUpdates++;
            });
            
            // Simulate authentication state change
            const testUser = {
                id: 1,
                email: 'integration@test.com',
                first_name: 'Integration',
                role: 'owner'
            };
            
            // Update auth manager
            this.authManager.currentUser = testUser;
            this.authManager.notifyAuthStateChange(true, testUser);
            
            // Verify all components received the update
            this.assert(
                uiStateUpdates > 0,
                'UI state manager should receive auth updates'
            );
            
            // Test navigation state synchronization
            window.location.pathname = '/dashboard';
            this.navigationController.updateActiveNavItem();
            
            const uiActiveNav = this.uiStateManager.getActiveNavItem();
            this.assert(
                uiActiveNav === 'dashboard',
                'UI state should sync with navigation state'
            );
            
            // Test role-based UI updates across components
            const userManagementLink = document.getElementById('user-links-users');
            this.assert(
                !userManagementLink.classList.contains('d-none'),
                'Owner role should have access to user management'
            );
            
            // Test component cleanup integration
            this.authManager.cleanup();
            this.navigationController.cleanup();
            this.uiStateManager.cleanup();
            
            this.assert(
                this.authManager.authCallbacks.length === 0,
                'Auth manager should clear callbacks on cleanup'
            );
            
            this.addResult('Multi-Component Integration', 'PASS', 'Multi-component integration works correctly');
        } catch (error) {
            this.addResult('Multi-Component Integration', 'FAIL', error.message);
        }
    }

    async testErrorHandlingIntegration() {
        console.log('⚠️ Testing error handling integration...');
        
        try {
            // Test login error handling with UI updates
            global.fetch.mockRejectedValueOnce(new Error('Network error'));
            
            const form = document.getElementById('loginForm');
            const event = new Event('submit', { bubbles: true, cancelable: true });
            
            // Should not throw error
            await this.authManager.handleLogin(event);
            
            // Verify error state is handled
            this.assert(
                this.authManager.isAuthenticated() === false,
                'Should remain unauthenticated on login error'
            );
            
            // Test navigation error handling
            global.fetch.mockRejectedValueOnce(new Error('Navigation error'));
            
            // Should not throw error
            await this.navigationController.navigateTo('/dashboard');
            
            // Test auth check error handling
            global.localStorage.getItem.mockReturnValue('invalid_token');
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 401
            });
            
            const authResult = await this.authManager.checkAuthStatus();
            
            this.assert(
                authResult === false,
                'Should handle auth check errors gracefully'
            );
            
            // Verify UI state remains consistent
            const uiState = this.uiStateManager.getState();
            this.assert(
                typeof uiState.isAuthenticated === 'boolean',
                'UI state should maintain type consistency during errors'
            );
            
            this.addResult('Error Handling Integration', 'PASS', 'Error handling integration works correctly');
        } catch (error) {
            this.addResult('Error Handling Integration', 'FAIL', error.message);
        }
    }

    async testTokenRefreshIntegration() {
        console.log('🔄 Testing token refresh integration...');
        
        try {
            // Set up expired token scenario
            global.localStorage.getItem.mockImplementation(key => {
                if (key === 'access_token') return 'expired_token';
                if (key === 'refresh_token') return 'valid_refresh_token';
                return null;
            });
            
            // Mock auth check with 401 response
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 401
            });
            
            // Mock successful token refresh
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    success: true,
                    data: {
                        access_token: 'new_access_token',
                        refresh_token: 'new_refresh_token'
                    }
                })
            });
            
            // Mock successful auth check with new token
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    success: true,
                    data: {
                        user: {
                            id: 1,
                            email: 'test@example.com',
                            first_name: 'Test'
                        }
                    }
                })
            });
            
            // Perform auth check (should trigger refresh)
            const authResult = await this.authManager.checkAuthStatus();
            
            this.assert(
                authResult === true,
                'Should successfully authenticate after token refresh'
            );
            
            // Verify new tokens were stored
            this.assert(
                global.localStorage.setItem.mock.calls.some(call => 
                    call[0] === 'access_token' && call[1] === 'new_access_token'
                ),
                'New access token should be stored'
            );
            
            // Verify UI state is updated
            this.assert(
                this.authManager.isAuthenticated() === true,
                'Should be authenticated after successful refresh'
            );
            
            this.addResult('Token Refresh Integration', 'PASS', 'Token refresh integration works correctly');
        } catch (error) {
            this.addResult('Token Refresh Integration', 'FAIL', error.message);
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
        console.log('\n📊 Authentication Flow Integration Test Results:');
        console.log('================================================');
        
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
            console.log('🎉 All Authentication Flow Integration tests passed!');
        } else {
            console.log('⚠️  Some tests failed. Check the details above.');
        }
    }

    cleanup() {
        // Restore original functions
        if (this.originalFetch) {
            global.fetch = this.originalFetch;
        }
        if (this.originalLocalStorage) {
            global.localStorage = this.originalLocalStorage;
        }
        
        // Clean up components
        if (this.authManager) {
            this.authManager.cleanup();
        }
        if (this.navigationController) {
            this.navigationController.cleanup();
        }
        if (this.uiStateManager) {
            this.uiStateManager.cleanup();
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
        const tester = new AuthenticationFlowIntegrationTest();
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
            mockFn.mockReturnValue = undefined;
            mockFn.mockResolvedValue = undefined;
            mockFn.mockRejectedValue = undefined;
            mockFn.mockImplementation = undefined;
            mockFn.mockResolvedValueOnce = (value) => {
                mockFn.mockResolvedValue = value;
                return mockFn;
            };
            mockFn.mockRejectedValueOnce = (value) => {
                mockFn.mockRejectedValue = value;
                return mockFn;
            };
            mockFn.mockImplementation = (fn) => {
                mockFn.mockImplementation = fn;
                return mockFn;
            };
            return mockFn;
        }
    };
}

// Export for use in other modules
window.AuthenticationFlowIntegrationTest = AuthenticationFlowIntegrationTest;

// Add console helper
window.testAuthFlowIntegration = () => AuthenticationFlowIntegrationTest.quickTest();