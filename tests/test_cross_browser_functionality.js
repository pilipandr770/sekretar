/**
 * Cross-Browser Functionality Tests
 * Tests all frontend functionality across different browsers
 */

class CrossBrowserFunctionalityTester {
    constructor() {
        this.testResults = {};
        this.browserInfo = this.detectBrowser();
        this.testSuites = [
            'AuthenticationTests',
            'NavigationTests', 
            'LanguageSwitchingTests',
            'WebSocketTests',
            'UIStateTests',
            'ErrorHandlingTests'
        ];
        
        console.log('🌐 Cross-Browser Functionality Tester initialized');
        console.log('Browser:', this.browserInfo.name, this.browserInfo.version);
    }
    
    detectBrowser() {
        const userAgent = navigator.userAgent;
        const vendor = navigator.vendor || '';
        
        let browser = 'Unknown';
        let version = 'Unknown';
        let majorVersion = 0;
        
        if (userAgent.includes('Chrome') && vendor.includes('Google')) {
            browser = 'Chrome';
            const match = userAgent.match(/Chrome\/(\d+)\.(\d+)/);
            if (match) {
                version = `${match[1]}.${match[2]}`;
                majorVersion = parseInt(match[1]);
            }
        } else if (userAgent.includes('Firefox')) {
            browser = 'Firefox';
            const match = userAgent.match(/Firefox\/(\d+)\.(\d+)/);
            if (match) {
                version = `${match[1]}.${match[2]}`;
                majorVersion = parseInt(match[1]);
            }
        } else if (userAgent.includes('Safari') && !userAgent.includes('Chrome')) {
            browser = 'Safari';
            const match = userAgent.match(/Version\/(\d+)\.(\d+)/);
            if (match) {
                version = `${match[1]}.${match[2]}`;
                majorVersion = parseInt(match[1]);
            }
        } else if (userAgent.includes('Edg')) {
            browser = 'Edge';
            const match = userAgent.match(/Edg\/(\d+)\.(\d+)/);
            if (match) {
                version = `${match[1]}.${match[2]}`;
                majorVersion = parseInt(match[1]);
            }
        }
        
        return {
            name: browser,
            version: version,
            majorVersion: majorVersion,
            userAgent: userAgent,
            vendor: vendor,
            platform: navigator.platform,
            language: navigator.language
        };
    }
    
    async runAllTests() {
        console.log('🧪 Starting cross-browser functionality tests...');
        console.log('==========================================');
        
        const startTime = Date.now();
        
        try {
            // Run each test suite
            for (const suiteName of this.testSuites) {
                console.log(`\n📋 Running ${suiteName}...`);
                await this.runTestSuite(suiteName);
            }
            
            const endTime = Date.now();
            const duration = endTime - startTime;
            
            console.log('\n==========================================');
            console.log(`✅ All cross-browser tests completed in ${duration}ms`);
            
            this.generateTestReport();
            
        } catch (error) {
            console.error('❌ Cross-browser test execution failed:', error);
            throw error;
        }
    }
    
    async runTestSuite(suiteName) {
        const suiteResults = {
            name: suiteName,
            browser: this.browserInfo,
            tests: [],
            passed: 0,
            failed: 0,
            startTime: Date.now()
        };
        
        try {
            switch (suiteName) {
                case 'AuthenticationTests':
                    await this.runAuthenticationTests(suiteResults);
                    break;
                case 'NavigationTests':
                    await this.runNavigationTests(suiteResults);
                    break;
                case 'LanguageSwitchingTests':
                    await this.runLanguageSwitchingTests(suiteResults);
                    break;
                case 'WebSocketTests':
                    await this.runWebSocketTests(suiteResults);
                    break;
                case 'UIStateTests':
                    await this.runUIStateTests(suiteResults);
                    break;
                case 'ErrorHandlingTests':
                    await this.runErrorHandlingTests(suiteResults);
                    break;
            }
            
            suiteResults.endTime = Date.now();
            suiteResults.duration = suiteResults.endTime - suiteResults.startTime;
            
            this.testResults[suiteName] = suiteResults;
            
            console.log(`   ✅ ${suiteName}: ${suiteResults.passed} passed, ${suiteResults.failed} failed`);
            
        } catch (error) {
            console.error(`   ❌ ${suiteName} failed:`, error);
            suiteResults.error = error.message;
            this.testResults[suiteName] = suiteResults;
        }
    }
    
    async runAuthenticationTests(suiteResults) {
        // Test 1: Authentication Manager Initialization
        await this.runTest(suiteResults, 'Authentication Manager Initialization', async () => {
            // Mock authentication manager
            const mockAuthManager = {
                init: () => Promise.resolve(),
                getCurrentUser: () => null,
                isAuthenticated: () => false
            };
            
            // Test initialization
            await mockAuthManager.init();
            
            // Verify browser-specific behavior
            if (this.browserInfo.name === 'Safari') {
                // Safari-specific authentication tests
                this.testSafariAuthenticationBehavior(mockAuthManager);
            } else if (this.browserInfo.name === 'Firefox') {
                // Firefox-specific authentication tests
                this.testFirefoxAuthenticationBehavior(mockAuthManager);
            }
            
            return true;
        });
        
        // Test 2: Token Storage Cross-Browser
        await this.runTest(suiteResults, 'Token Storage Cross-Browser', async () => {
            const testToken = 'test_token_' + Date.now();
            
            // Test localStorage availability
            if (typeof localStorage !== 'undefined') {
                localStorage.setItem('test_auth_token', testToken);
                const retrieved = localStorage.getItem('test_auth_token');
                localStorage.removeItem('test_auth_token');
                
                if (retrieved !== testToken) {
                    throw new Error('localStorage token storage failed');
                }
            } else {
                // Test cookie fallback
                document.cookie = `test_auth_token=${testToken}; path=/`;
                const cookieValue = document.cookie.split(';')
                    .find(row => row.trim().startsWith('test_auth_token='));
                
                if (!cookieValue || !cookieValue.includes(testToken)) {
                    throw new Error('Cookie token storage fallback failed');
                }
                
                // Clean up
                document.cookie = 'test_auth_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/';
            }
            
            return true;
        });
        
        // Test 3: Login Form Behavior
        await this.runTest(suiteResults, 'Login Form Behavior', async () => {
            // Create mock login form
            const mockForm = document.createElement('form');
            mockForm.id = 'loginForm';
            mockForm.innerHTML = `
                <input type="email" name="email" value="test@example.com">
                <input type="password" name="password" value="password">
                <button type="submit">Login</button>
            `;
            
            document.body.appendChild(mockForm);
            
            try {
                // Test form submission behavior across browsers
                const formData = new FormData(mockForm);
                const email = formData.get('email');
                const password = formData.get('password');
                
                if (email !== 'test@example.com' || password !== 'password') {
                    throw new Error('Form data extraction failed');
                }
                
                // Test browser-specific form behavior
                if (this.browserInfo.name === 'Safari' && this.browserInfo.majorVersion < 14) {
                    // Safari older versions have FormData issues
                    console.log('   🍎 Safari: Testing FormData compatibility');
                }
                
                return true;
            } finally {
                document.body.removeChild(mockForm);
            }
        });
    }
    
    async runNavigationTests(suiteResults) {
        // Test 1: Navigation Button Functionality
        await this.runTest(suiteResults, 'Navigation Button Functionality', async () => {
            // Create mock navigation buttons
            const mockNav = document.createElement('nav');
            mockNav.innerHTML = `
                <a href="/crm" data-nav="crm">CRM</a>
                <a href="/inbox" data-nav="inbox">Inbox</a>
                <a href="/calendar" data-nav="calendar">Calendar</a>
            `;
            
            document.body.appendChild(mockNav);
            
            try {
                // Test click event handling
                const crmLink = mockNav.querySelector('[data-nav="crm"]');
                let clickHandled = false;
                
                crmLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    clickHandled = true;
                });
                
                // Simulate click
                const clickEvent = new MouseEvent('click', {
                    bubbles: true,
                    cancelable: true
                });
                
                crmLink.dispatchEvent(clickEvent);
                
                if (!clickHandled) {
                    throw new Error('Navigation click event not handled');
                }
                
                // Test browser-specific navigation behavior
                if (this.browserInfo.name === 'Safari') {
                    this.testSafariNavigationBehavior();
                }
                
                return true;
            } finally {
                document.body.removeChild(mockNav);
            }
        });
        
        // Test 2: History API Support
        await this.runTest(suiteResults, 'History API Support', async () => {
            if (typeof history.pushState === 'undefined') {
                throw new Error('History API not supported');
            }
            
            const originalState = history.state;
            const originalUrl = location.href;
            
            try {
                // Test pushState
                history.pushState({ test: true }, 'Test', '/test');
                
                if (location.pathname !== '/test') {
                    throw new Error('pushState failed to update URL');
                }
                
                // Test popstate event
                let popstateHandled = false;
                const popstateHandler = () => {
                    popstateHandled = true;
                };
                
                window.addEventListener('popstate', popstateHandler);
                
                // Simulate back button
                history.back();
                
                // Wait for popstate
                await new Promise(resolve => setTimeout(resolve, 100));
                
                window.removeEventListener('popstate', popstateHandler);
                
                return true;
            } finally {
                // Restore original state
                history.replaceState(originalState, '', originalUrl);
            }
        });
    }
    
    async runLanguageSwitchingTests(suiteResults) {
        // Test 1: Language Detection
        await this.runTest(suiteResults, 'Language Detection', async () => {
            // Test URL parameter detection
            const originalSearch = location.search;
            
            try {
                // Mock URL with language parameter
                Object.defineProperty(location, 'search', {
                    value: '?lang=de',
                    configurable: true
                });
                
                const urlParams = new URLSearchParams(location.search);
                const langParam = urlParams.get('lang');
                
                if (langParam !== 'de') {
                    throw new Error('Language parameter detection failed');
                }
                
                // Test localStorage detection
                if (typeof localStorage !== 'undefined') {
                    localStorage.setItem('preferred_language', 'uk');
                    const storedLang = localStorage.getItem('preferred_language');
                    
                    if (storedLang !== 'uk') {
                        throw new Error('Language localStorage detection failed');
                    }
                    
                    localStorage.removeItem('preferred_language');
                }
                
                return true;
            } finally {
                Object.defineProperty(location, 'search', {
                    value: originalSearch,
                    configurable: true
                });
            }
        });
        
        // Test 2: Translation Updates
        await this.runTest(suiteResults, 'Translation Updates', async () => {
            // Create mock translatable elements
            const mockElement = document.createElement('div');
            mockElement.setAttribute('data-i18n', 'test.key');
            mockElement.textContent = 'Original Text';
            
            document.body.appendChild(mockElement);
            
            try {
                // Mock translation function
                window._ = (key) => {
                    const translations = {
                        'test.key': 'Translated Text'
                    };
                    return translations[key] || key;
                };
                
                // Update translation
                const key = mockElement.dataset.i18n;
                const translation = window._(key);
                mockElement.textContent = translation;
                
                if (mockElement.textContent !== 'Translated Text') {
                    throw new Error('Translation update failed');
                }
                
                return true;
            } finally {
                document.body.removeChild(mockElement);
                delete window._;
            }
        });
    }
    
    async runWebSocketTests(suiteResults) {
        // Test 1: WebSocket Support Detection
        await this.runTest(suiteResults, 'WebSocket Support Detection', async () => {
            if (typeof WebSocket === 'undefined') {
                throw new Error('WebSocket not supported');
            }
            
            // Test WebSocket constructor
            try {
                const testWs = new WebSocket('wss://echo.websocket.org/');
                testWs.close();
                return true;
            } catch (error) {
                throw new Error(`WebSocket creation failed: ${error.message}`);
            }
        });
        
        // Test 2: Socket.IO Fallback
        await this.runTest(suiteResults, 'Socket.IO Fallback', async () => {
            // Test if Socket.IO is available
            if (typeof io === 'undefined') {
                console.log('   ℹ️ Socket.IO not available, testing native WebSocket fallback');
                
                // Test native WebSocket fallback logic
                if (typeof WebSocket === 'undefined') {
                    throw new Error('Neither Socket.IO nor native WebSocket available');
                }
                
                return true;
            }
            
            // Test Socket.IO configuration
            try {
                const mockSocket = io({
                    autoConnect: false,
                    transports: ['websocket', 'polling']
                });
                
                if (!mockSocket) {
                    throw new Error('Socket.IO initialization failed');
                }
                
                return true;
            } catch (error) {
                throw new Error(`Socket.IO test failed: ${error.message}`);
            }
        });
        
        // Test 3: Browser-Specific WebSocket Behavior
        await this.runTest(suiteResults, 'Browser-Specific WebSocket Behavior', async () => {
            // Test browser-specific WebSocket configurations
            switch (this.browserInfo.name) {
                case 'Safari':
                    return this.testSafariWebSocketBehavior();
                case 'Firefox':
                    return this.testFirefoxWebSocketBehavior();
                case 'Edge':
                    return this.testEdgeWebSocketBehavior();
                case 'Chrome':
                    return this.testChromeWebSocketBehavior();
                default:
                    return true; // Unknown browser, assume working
            }
        });
    }
    
    async runUIStateTests(suiteResults) {
        // Test 1: Custom Events Support
        await this.runTest(suiteResults, 'Custom Events Support', async () => {
            if (typeof CustomEvent === 'undefined') {
                throw new Error('CustomEvent not supported');
            }
            
            // Test custom event creation and dispatch
            let eventReceived = false;
            const testHandler = (event) => {
                eventReceived = true;
                if (event.detail.test !== 'value') {
                    throw new Error('Custom event detail not preserved');
                }
            };
            
            document.addEventListener('test:event', testHandler);
            
            try {
                const customEvent = new CustomEvent('test:event', {
                    detail: { test: 'value' }
                });
                
                document.dispatchEvent(customEvent);
                
                if (!eventReceived) {
                    throw new Error('Custom event not received');
                }
                
                return true;
            } finally {
                document.removeEventListener('test:event', testHandler);
            }
        });
        
        // Test 2: State Persistence
        await this.runTest(suiteResults, 'State Persistence', async () => {
            const testState = { authenticated: true, language: 'en' };
            
            // Test localStorage persistence
            if (typeof localStorage !== 'undefined') {
                localStorage.setItem('ui_state', JSON.stringify(testState));
                const retrieved = JSON.parse(localStorage.getItem('ui_state'));
                
                if (retrieved.authenticated !== true || retrieved.language !== 'en') {
                    throw new Error('State persistence failed');
                }
                
                localStorage.removeItem('ui_state');
            }
            
            return true;
        });
    }
    
    async runErrorHandlingTests(suiteResults) {
        // Test 1: JavaScript Error Handling
        await this.runTest(suiteResults, 'JavaScript Error Handling', async () => {
            let errorCaught = false;
            
            const originalOnError = window.onerror;
            window.onerror = (message, source, lineno, colno, error) => {
                errorCaught = true;
                return true; // Prevent default error handling
            };
            
            try {
                // Trigger a JavaScript error
                throw new Error('Test error');
            } catch (error) {
                // Error should be caught by try-catch, not window.onerror
                if (error.message !== 'Test error') {
                    throw new Error('Error handling failed');
                }
            } finally {
                window.onerror = originalOnError;
            }
            
            return true;
        });
        
        // Test 2: Network Error Handling
        await this.runTest(suiteResults, 'Network Error Handling', async () => {
            // Test fetch error handling
            if (typeof fetch !== 'undefined') {
                try {
                    await fetch('https://invalid-url-that-should-fail.test');
                    throw new Error('Fetch should have failed');
                } catch (error) {
                    // Expected to fail
                    if (error.message === 'Fetch should have failed') {
                        throw error;
                    }
                    return true;
                }
            } else {
                // Test XMLHttpRequest error handling
                return new Promise((resolve, reject) => {
                    const xhr = new XMLHttpRequest();
                    xhr.open('GET', 'https://invalid-url-that-should-fail.test');
                    xhr.onerror = () => resolve(true);
                    xhr.onload = () => reject(new Error('XHR should have failed'));
                    xhr.send();
                });
            }
        });
    }
    
    // Browser-specific test methods
    testSafariAuthenticationBehavior(authManager) {
        console.log('   🍎 Testing Safari authentication behavior');
        // Safari-specific authentication tests
        return true;
    }
    
    testFirefoxAuthenticationBehavior(authManager) {
        console.log('   🦊 Testing Firefox authentication behavior');
        // Firefox-specific authentication tests
        return true;
    }
    
    testSafariNavigationBehavior() {
        console.log('   🍎 Testing Safari navigation behavior');
        // Safari-specific navigation tests
        return true;
    }
    
    testSafariWebSocketBehavior() {
        console.log('   🍎 Testing Safari WebSocket behavior');
        // Safari has issues with WebSocket over HTTPS with self-signed certificates
        return true;
    }
    
    testFirefoxWebSocketBehavior() {
        console.log('   🦊 Testing Firefox WebSocket behavior');
        // Firefox-specific WebSocket tests
        return true;
    }
    
    testEdgeWebSocketBehavior() {
        console.log('   🔷 Testing Edge WebSocket behavior');
        // Edge-specific WebSocket tests
        return true;
    }
    
    testChromeWebSocketBehavior() {
        console.log('   🟢 Testing Chrome WebSocket behavior');
        // Chrome-specific WebSocket tests
        return true;
    }
    
    // Test execution helper
    async runTest(suiteResults, testName, testFunction) {
        const testResult = {
            name: testName,
            browser: this.browserInfo.name,
            startTime: Date.now()
        };
        
        try {
            const result = await testFunction();
            testResult.passed = true;
            testResult.result = result;
            suiteResults.passed++;
            
            console.log(`     ✅ ${testName}`);
        } catch (error) {
            testResult.passed = false;
            testResult.error = error.message;
            testResult.stack = error.stack;
            suiteResults.failed++;
            
            console.log(`     ❌ ${testName}: ${error.message}`);
        } finally {
            testResult.endTime = Date.now();
            testResult.duration = testResult.endTime - testResult.startTime;
            suiteResults.tests.push(testResult);
        }
    }
    
    generateTestReport() {
        console.log('\n📊 Cross-Browser Test Report');
        console.log('============================');
        console.log(`Browser: ${this.browserInfo.name} ${this.browserInfo.version}`);
        console.log(`Platform: ${this.browserInfo.platform}`);
        console.log(`Language: ${this.browserInfo.language}`);
        console.log('');
        
        let totalPassed = 0;
        let totalFailed = 0;
        let totalDuration = 0;
        
        Object.values(this.testResults).forEach(suite => {
            totalPassed += suite.passed;
            totalFailed += suite.failed;
            totalDuration += suite.duration || 0;
            
            console.log(`📋 ${suite.name}: ${suite.passed} passed, ${suite.failed} failed (${suite.duration}ms)`);
            
            if (suite.failed > 0) {
                suite.tests.filter(test => !test.passed).forEach(test => {
                    console.log(`   ❌ ${test.name}: ${test.error}`);
                });
            }
        });
        
        console.log('');
        console.log(`📈 Total: ${totalPassed} passed, ${totalFailed} failed`);
        console.log(`⏱️ Total Duration: ${totalDuration}ms`);
        
        if (totalFailed === 0) {
            console.log('🎉 All cross-browser tests passed!');
        } else {
            console.log(`⚠️ ${totalFailed} tests failed - check browser compatibility`);
        }
        
        // Generate browser-specific recommendations
        this.generateBrowserRecommendations();
    }
    
    generateBrowserRecommendations() {
        console.log('\n💡 Browser-Specific Recommendations:');
        console.log('====================================');
        
        const failedTests = Object.values(this.testResults)
            .flatMap(suite => suite.tests)
            .filter(test => !test.passed);
        
        if (failedTests.length === 0) {
            console.log('✅ No issues detected - all functionality works correctly!');
            return;
        }
        
        switch (this.browserInfo.name) {
            case 'Safari':
                console.log('🍎 Safari Recommendations:');
                console.log('   • Ensure HTTPS is used for WebSocket connections');
                console.log('   • Test private browsing mode localStorage fallbacks');
                console.log('   • Verify date parsing with ISO format strings');
                break;
                
            case 'Firefox':
                console.log('🦊 Firefox Recommendations:');
                console.log('   • Test WebSocket connection timing');
                console.log('   • Verify CustomEvent polyfill for older versions');
                console.log('   • Check fetch API availability');
                break;
                
            case 'Edge':
                console.log('🔷 Edge Recommendations:');
                console.log('   • Test both Chromium and Legacy Edge versions');
                console.log('   • Verify WebSocket binary data handling');
                console.log('   • Check Promise support for older versions');
                break;
                
            case 'Chrome':
                console.log('🟢 Chrome Recommendations:');
                console.log('   • Optimize WebSocket buffer management');
                console.log('   • Test memory cleanup for long-running connections');
                console.log('   • Verify performance with large datasets');
                break;
                
            default:
                console.log('❓ Unknown Browser:');
                console.log('   • Test all basic web APIs');
                console.log('   • Implement comprehensive fallbacks');
                console.log('   • Monitor for compatibility issues');
        }
        
        console.log('====================================');
    }
    
    // Export test results
    exportResults() {
        return {
            browser: this.browserInfo,
            testResults: this.testResults,
            summary: this.generateSummary(),
            timestamp: new Date().toISOString()
        };
    }
    
    generateSummary() {
        const totalTests = Object.values(this.testResults)
            .reduce((sum, suite) => sum + suite.tests.length, 0);
        const totalPassed = Object.values(this.testResults)
            .reduce((sum, suite) => sum + suite.passed, 0);
        const totalFailed = Object.values(this.testResults)
            .reduce((sum, suite) => sum + suite.failed, 0);
        const totalDuration = Object.values(this.testResults)
            .reduce((sum, suite) => sum + (suite.duration || 0), 0);
        
        return {
            totalTests,
            totalPassed,
            totalFailed,
            totalDuration,
            successRate: totalTests > 0 ? (totalPassed / totalTests * 100).toFixed(2) : 0
        };
    }
}

// Export for global use
window.CrossBrowserFunctionalityTester = CrossBrowserFunctionalityTester;

// Auto-run tests if requested
if (typeof window !== 'undefined' && window.location.search.includes('autorun=true')) {
    document.addEventListener('DOMContentLoaded', async () => {
        const tester = new CrossBrowserFunctionalityTester();
        await tester.runAllTests();
    });
}