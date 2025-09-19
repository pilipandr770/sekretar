/**
 * Unit Tests for Authentication Manager
 * Tests authentication state management functionality
 */

class AuthenticationManagerTest {
    constructor() {
        this.testResults = [];
        this.authManager = null;
        this.originalFetch = null;
        this.originalLocalStorage = null;
    }

    async runAllTests() {
        console.log('🧪 Running Authentication Manager Tests...');
        
        this.testResults = [];
        this.setupMocks();
        
        try {
            // Initialize auth manager for testing
            this.authManager = new AuthenticationManager();
            
            // Test 1: Initialization
            await this.testInitialization();
            
            // Test 2: Authentication state management
            await this.testAuthStateManagement();
            
            // Test 3: Login functionality
            await this.testLoginFunctionality();
            
            // Test 4: Logout functionality
            await this.testLogoutFunctionality();
            
            // Test 5: Token refresh
            await this.testTokenRefresh();
            
            // Test 6: Auth status checking
            await this.testAuthStatusCheck();
            
            // Test 7: UI state synchronization
            await this.testUIStateSynchronization();
            
            // Test 8: Event handling
            await this.testEventHandling();
            
            // Test 9: Error handling
            await this.testErrorHandling();
            
            // Test 10: Multi-tab synchronization
            await this.testMultiTabSync();
            
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
        
        // Mock DOM elements
        document.body.innerHTML = `
            <form id="loginForm">
                <input name="email" type="email" value="test@example.com">
                <input name="password" type="password" value="password123">
                <button type="submit">
                    <span class="spinner-border d-none"></span>
                    Login
                </button>
            </form>
            <div id="userName"></div>
            <div id="auth-links"></div>
            <div id="user-links"></div>
            <div id="user-links-users"></div>
            <div id="user-links-divider"></div>
            <div id="user-links-logout"></div>
            <main style="display: none;"></main>
        `;
    }

    async testInitialization() {
        console.log('🔍 Testing Authentication Manager initialization...');
        
        try {
            // Test initial state
            this.assert(
                this.authManager.currentUser === null,
                'Initial user should be null'
            );
            
            this.assert(
                Array.isArray(this.authManager.authCallbacks),
                'Auth callbacks should be an array'
            );
            
            this.assert(
                this.authManager.isInitialized === false,
                'Should not be initialized initially'
            );
            
            // Test initialization
            await this.authManager.init();
            
            this.assert(
                this.authManager.isInitialized === true,
                'Should be initialized after init()'
            );
            
            this.addResult('Initialization', 'PASS', 'Authentication Manager initialized correctly');
        } catch (error) {
            this.addResult('Initialization', 'FAIL', error.message);
        }
    }

    async testAuthStateManagement() {
        console.log('🔐 Testing authentication state management...');
        
        try {
            // Test initial authentication state
            this.assert(
                this.authManager.isAuthenticated() === false,
                'Should not be authenticated initially'
            );
            
            this.assert(
                this.authManager.getCurrentUser() === null,
                'Current user should be null initially'
            );
            
            // Test setting authenticated state
            const testUser = {
                id: 1,
                email: 'test@example.com',
                first_name: 'Test',
                last_name: 'User',
                role: 'user'
            };
            
            this.authManager.currentUser = testUser;
            
            this.assert(
                this.authManager.isAuthenticated() === true,
                'Should be authenticated after setting user'
            );
            
            this.assert(
                this.authManager.getCurrentUser().email === 'test@example.com',
                'Should return correct user data'
            );
            
            const authState = this.authManager.getAuthState();
            this.assert(
                authState.isAuthenticated === true,
                'Auth state should reflect authenticated status'
            );
            
            this.assert(
                authState.user.email === 'test@example.com',
                'Auth state should contain user data'
            );
            
            this.addResult('Auth State Management', 'PASS', 'Authentication state managed correctly');
        } catch (error) {
            this.addResult('Auth State Management', 'FAIL', error.message);
        }
    }

    async testLoginFunctionality() {
        console.log('🔑 Testing login functionality...');
        
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
                            role: 'user'
                        }
                    },
                    message: 'Login successful'
                })
            });
            
            // Create login form event
            const form = document.getElementById('loginForm');
            const event = new Event('submit', { bubbles: true, cancelable: true });
            
            // Test login handling
            await this.authManager.handleLogin(event);
            
            // Verify API call was made
            this.assert(
                global.fetch.mock.calls.length > 0,
                'Login API should be called'
            );
            
            const lastCall = global.fetch.mock.calls[global.fetch.mock.calls.length - 1];
            this.assert(
                lastCall[0] === '/api/v1/auth/login',
                'Should call correct login endpoint'
            );
            
            // Verify tokens were stored
            this.assert(
                global.localStorage.setItem.mock.calls.some(call => 
                    call[0] === 'access_token' && call[1] === 'test_access_token'
                ),
                'Access token should be stored'
            );
            
            this.assert(
                global.localStorage.setItem.mock.calls.some(call => 
                    call[0] === 'refresh_token' && call[1] === 'test_refresh_token'
                ),
                'Refresh token should be stored'
            );
            
            this.addResult('Login Functionality', 'PASS', 'Login handled correctly');
        } catch (error) {
            this.addResult('Login Functionality', 'FAIL', error.message);
        }
    }

    async testLogoutFunctionality() {
        console.log('🚪 Testing logout functionality...');
        
        try {
            // Set up authenticated state
            this.authManager.currentUser = { id: 1, email: 'test@example.com' };
            global.localStorage.getItem.mockReturnValue('test_token');
            
            // Mock logout response
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ success: true })
            });
            
            // Test logout
            await this.authManager.handleLogout();
            
            // Verify API call was made
            const logoutCall = global.fetch.mock.calls.find(call => 
                call[0] === '/api/v1/auth/logout'
            );
            this.assert(
                logoutCall !== undefined,
                'Logout API should be called'
            );
            
            // Verify tokens were cleared
            this.assert(
                global.localStorage.removeItem.mock.calls.some(call => 
                    call[0] === 'access_token'
                ),
                'Access token should be removed'
            );
            
            this.assert(
                global.localStorage.removeItem.mock.calls.some(call => 
                    call[0] === 'refresh_token'
                ),
                'Refresh token should be removed'
            );
            
            // Verify user state was cleared
            this.assert(
                this.authManager.currentUser === null,
                'Current user should be cleared'
            );
            
            this.addResult('Logout Functionality', 'PASS', 'Logout handled correctly');
        } catch (error) {
            this.addResult('Logout Functionality', 'FAIL', error.message);
        }
    }

    async testTokenRefresh() {
        console.log('🔄 Testing token refresh...');
        
        try {
            // Mock refresh token
            global.localStorage.getItem.mockImplementation(key => {
                if (key === 'refresh_token') return 'test_refresh_token';
                return null;
            });
            
            // Mock successful refresh response
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
            
            // Test token refresh
            const result = await this.authManager.refreshToken();
            
            this.assert(
                result === true,
                'Token refresh should return true on success'
            );
            
            // Verify API call was made
            const refreshCall = global.fetch.mock.calls.find(call => 
                call[0] === '/api/v1/auth/refresh'
            );
            this.assert(
                refreshCall !== undefined,
                'Refresh API should be called'
            );
            
            // Verify new tokens were stored
            this.assert(
                global.localStorage.setItem.mock.calls.some(call => 
                    call[0] === 'access_token' && call[1] === 'new_access_token'
                ),
                'New access token should be stored'
            );
            
            this.addResult('Token Refresh', 'PASS', 'Token refresh handled correctly');
        } catch (error) {
            this.addResult('Token Refresh', 'FAIL', error.message);
        }
    }

    async testAuthStatusCheck() {
        console.log('✅ Testing authentication status check...');
        
        try {
            // Test with no token
            global.localStorage.getItem.mockReturnValue(null);
            
            const result1 = await this.authManager.checkAuthStatus();
            this.assert(
                result1 === false,
                'Should return false when no token'
            );
            
            // Test with valid token
            global.localStorage.getItem.mockReturnValue('valid_token');
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
            
            const result2 = await this.authManager.checkAuthStatus();
            this.assert(
                result2 === true,
                'Should return true with valid token'
            );
            
            this.assert(
                this.authManager.currentUser.email === 'test@example.com',
                'Should set current user from response'
            );
            
            this.addResult('Auth Status Check', 'PASS', 'Auth status check works correctly');
        } catch (error) {
            this.addResult('Auth Status Check', 'FAIL', error.message);
        }
    }

    async testUIStateSynchronization() {
        console.log('🎨 Testing UI state synchronization...');
        
        try {
            const testUser = {
                id: 1,
                email: 'test@example.com',
                first_name: 'Test User',
                role: 'user'
            };
            
            // Test showing authenticated UI
            this.authManager.showAuthenticatedUI(testUser);
            
            const userNameElement = document.getElementById('userName');
            this.assert(
                userNameElement.textContent === 'Test User',
                'User name should be displayed'
            );
            
            const authLinks = document.getElementById('auth-links');
            this.assert(
                authLinks.classList.contains('d-none'),
                'Auth links should be hidden'
            );
            
            const userLinks = document.getElementById('user-links');
            this.assert(
                !userLinks.classList.contains('d-none'),
                'User links should be visible'
            );
            
            // Test showing unauthenticated UI
            this.authManager.showUnauthenticatedUI();
            
            this.assert(
                !authLinks.classList.contains('d-none'),
                'Auth links should be visible'
            );
            
            this.assert(
                userLinks.classList.contains('d-none'),
                'User links should be hidden'
            );
            
            this.addResult('UI State Synchronization', 'PASS', 'UI state synchronized correctly');
        } catch (error) {
            this.addResult('UI State Synchronization', 'FAIL', error.message);
        }
    }

    async testEventHandling() {
        console.log('📡 Testing event handling...');
        
        try {
            let callbackCalled = false;
            let receivedAuth = false;
            let receivedUser = null;
            
            // Register callback
            this.authManager.onAuthStateChange((isAuthenticated, user) => {
                callbackCalled = true;
                receivedAuth = isAuthenticated;
                receivedUser = user;
            });
            
            // Trigger auth state change
            const testUser = { id: 1, email: 'test@example.com' };
            this.authManager.notifyAuthStateChange(true, testUser);
            
            this.assert(
                callbackCalled === true,
                'Auth state change callback should be called'
            );
            
            this.assert(
                receivedAuth === true,
                'Callback should receive correct auth state'
            );
            
            this.assert(
                receivedUser.email === 'test@example.com',
                'Callback should receive correct user data'
            );
            
            this.addResult('Event Handling', 'PASS', 'Event handling works correctly');
        } catch (error) {
            this.addResult('Event Handling', 'FAIL', error.message);
        }
    }

    async testErrorHandling() {
        console.log('⚠️ Testing error handling...');
        
        try {
            // Test login error handling
            global.fetch.mockRejectedValueOnce(new Error('Network error'));
            
            const form = document.getElementById('loginForm');
            const event = new Event('submit', { bubbles: true, cancelable: true });
            
            // Should not throw error
            await this.authManager.handleLogin(event);
            
            // Test auth check with network error
            global.localStorage.getItem.mockReturnValue('test_token');
            global.fetch.mockRejectedValueOnce(new Error('Network error'));
            
            const result = await this.authManager.checkAuthStatus();
            this.assert(
                result === false,
                'Should return false on network error'
            );
            
            // Test token refresh error
            global.fetch.mockRejectedValueOnce(new Error('Refresh failed'));
            
            const refreshResult = await this.authManager.refreshToken();
            this.assert(
                refreshResult === false,
                'Should return false on refresh error'
            );
            
            this.addResult('Error Handling', 'PASS', 'Error handling works correctly');
        } catch (error) {
            this.addResult('Error Handling', 'FAIL', error.message);
        }
    }

    async testMultiTabSync() {
        console.log('🔄 Testing multi-tab synchronization...');
        
        try {
            // Set up initial state
            await this.authManager.init();
            
            let logoutCalled = false;
            const originalHandleLogout = this.authManager.handleLogout;
            this.authManager.handleLogout = () => {
                logoutCalled = true;
                return Promise.resolve();
            };
            
            // Simulate token removal in another tab
            const storageEvent = new StorageEvent('storage', {
                key: 'access_token',
                newValue: null,
                oldValue: 'some_token'
            });
            
            window.dispatchEvent(storageEvent);
            
            // Give event time to process
            await new Promise(resolve => setTimeout(resolve, 10));
            
            this.assert(
                logoutCalled === true,
                'Should handle logout when token removed in another tab'
            );
            
            // Restore original method
            this.authManager.handleLogout = originalHandleLogout;
            
            this.addResult('Multi-tab Sync', 'PASS', 'Multi-tab synchronization works correctly');
        } catch (error) {
            this.addResult('Multi-tab Sync', 'FAIL', error.message);
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
        console.log('\n📊 Authentication Manager Test Results:');
        console.log('=========================================');
        
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
            console.log('🎉 All Authentication Manager tests passed!');
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
        
        // Clean up auth manager
        if (this.authManager) {
            this.authManager.cleanup();
        }
        
        // Clear DOM
        document.body.innerHTML = '';
    }

    // Quick test function for console use
    static async quickTest() {
        const tester = new AuthenticationManagerTest();
        return await tester.runAllTests();
    }
}

// Mock jest functions if not available
if (typeof jest === 'undefined') {
    global.jest = {
        fn: () => {
            const mockFn = function(...args) {
                mockFn.mock.calls.push(args);
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
            mockFn.mockResolvedValueOnce = (value) => {
                mockFn.mockResolvedValue = value;
                return mockFn;
            };
            mockFn.mockRejectedValueOnce = (value) => {
                mockFn.mockRejectedValue = value;
                return mockFn;
            };
            mockFn.mockImplementation = (fn) => {
                mockFn.mockReturnValue = fn;
                return mockFn;
            };
            return mockFn;
        }
    };
}

// Export for use in other modules
window.AuthenticationManagerTest = AuthenticationManagerTest;

// Add console helper
window.testAuthManager = () => AuthenticationManagerTest.quickTest();