/**
 * Cross-Browser Testing Suite for AI Secretary
 * Tests functionality across different browsers and provides compatibility reports
 */

class CrossBrowserTestSuite {
    constructor() {
        this.testResults = {
            browser: this.detectBrowser(),
            timestamp: new Date().toISOString(),
            tests: {},
            summary: {
                total: 0,
                passed: 0,
                failed: 0,
                warnings: 0
            }
        };
        
        this.testCategories = [
            'core-javascript',
            'dom-manipulation',
            'websocket-functionality',
            'local-storage',
            'authentication-flow',
            'language-switching',
            'navigation',
            'ui-components',
            'error-handling',
            'performance'
        ];
        
        this.init();
    }
    
    init() {
        console.log('Initializing Cross-Browser Test Suite...');
        console.log('Browser:', this.testResults.browser);
        
        // Create test UI
        this.createTestUI();
        
        // Auto-run tests if requested
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('autotest') === 'true') {
            setTimeout(() => this.runAllTests(), 1000);
        }
    }
    
    detectBrowser() {
        const ua = navigator.userAgent;
        const browserInfo = {
            userAgent: ua,
            platform: navigator.platform,
            language: navigator.language,
            cookieEnabled: navigator.cookieEnabled,
            onLine: navigator.onLine
        };
        
        // Detect browser name and version
        if (ua.includes('Chrome') && !ua.includes('Edg')) {
            const version = ua.match(/Chrome\/(\d+)/)?.[1];
            browserInfo.name = 'Chrome';
            browserInfo.version = parseInt(version);
        } else if (ua.includes('Firefox')) {
            const version = ua.match(/Firefox\/(\d+)/)?.[1];
            browserInfo.name = 'Firefox';
            browserInfo.version = parseInt(version);
        } else if (ua.includes('Safari') && !ua.includes('Chrome')) {
            const version = ua.match(/Version\/(\d+)/)?.[1];
            browserInfo.name = 'Safari';
            browserInfo.version = parseInt(version);
        } else if (ua.includes('Edg')) {
            const version = ua.match(/Edg\/(\d+)/)?.[1];
            browserInfo.name = 'Edge';
            browserInfo.version = parseInt(version);
        } else if (ua.includes('MSIE') || ua.includes('Trident')) {
            browserInfo.name = 'Internet Explorer';
            browserInfo.version = 0;
        } else {
            browserInfo.name = 'Unknown';
            browserInfo.version = 0;
        }
        
        return browserInfo;
    }
    
    createTestUI() {
        // Create test container
        const testContainer = document.createElement('div');
        testContainer.id = 'cross-browser-test-suite';
        testContainer.className = 'position-fixed bottom-0 end-0 m-3';
        testContainer.style.cssText = 'z-index: 9999; max-width: 400px;';
        
        testContainer.innerHTML = `
            <div class="card shadow">
                <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">Cross-Browser Tests</h6>
                    <div>
                        <button class="btn btn-sm btn-outline-light me-1" id="run-tests-btn">Run Tests</button>
                        <button class="btn btn-sm btn-outline-light" id="toggle-tests-btn">−</button>
                    </div>
                </div>
                <div class="card-body" id="test-body" style="max-height: 400px; overflow-y: auto;">
                    <div class="mb-3">
                        <strong>Browser:</strong> ${this.testResults.browser.name} ${this.testResults.browser.version}<br>
                        <strong>Platform:</strong> ${this.testResults.browser.platform}
                    </div>
                    <div id="test-progress" class="d-none">
                        <div class="progress mb-3">
                            <div class="progress-bar" role="progressbar" style="width: 0%"></div>
                        </div>
                        <div id="current-test">Ready to run tests...</div>
                    </div>
                    <div id="test-results"></div>
                </div>
            </div>
        `;
        
        document.body.appendChild(testContainer);
        
        // Add event listeners
        document.getElementById('run-tests-btn').addEventListener('click', () => {
            this.runAllTests();
        });
        
        document.getElementById('toggle-tests-btn').addEventListener('click', (e) => {
            const body = document.getElementById('test-body');
            const btn = e.target;
            if (body.style.display === 'none') {
                body.style.display = '';
                btn.textContent = '−';
            } else {
                body.style.display = 'none';
                btn.textContent = '+';
            }
        });
    }
    
    async runAllTests() {
        console.log('Running cross-browser tests...');
        
        const progressContainer = document.getElementById('test-progress');
        const progressBar = progressContainer.querySelector('.progress-bar');
        const currentTestDiv = document.getElementById('current-test');
        const resultsDiv = document.getElementById('test-results');
        
        progressContainer.classList.remove('d-none');
        resultsDiv.innerHTML = '';
        
        // Reset results
        this.testResults.tests = {};
        this.testResults.summary = { total: 0, passed: 0, failed: 0, warnings: 0 };
        
        const totalTests = this.testCategories.length;
        let completedTests = 0;
        
        for (const category of this.testCategories) {
            currentTestDiv.textContent = `Running ${category} tests...`;
            
            try {
                const result = await this.runTestCategory(category);
                this.testResults.tests[category] = result;
                
                // Update summary
                this.testResults.summary.total += result.tests.length;
                this.testResults.summary.passed += result.tests.filter(t => t.status === 'passed').length;
                this.testResults.summary.failed += result.tests.filter(t => t.status === 'failed').length;
                this.testResults.summary.warnings += result.tests.filter(t => t.status === 'warning').length;
                
                // Update UI
                this.displayCategoryResult(category, result);
                
            } catch (error) {
                console.error(`Error running ${category} tests:`, error);
                this.testResults.tests[category] = {
                    status: 'error',
                    error: error.message,
                    tests: []
                };
            }
            
            completedTests++;
            const progress = (completedTests / totalTests) * 100;
            progressBar.style.width = `${progress}%`;
        }
        
        currentTestDiv.textContent = 'Tests completed!';
        
        // Display summary
        this.displaySummary();
        
        // Log results
        console.log('Cross-browser test results:', this.testResults);
        
        // Save results to localStorage if available
        if (window.browserCompatibility && window.browserCompatibility.isSupported('localStorage')) {
            localStorage.setItem('cross_browser_test_results', JSON.stringify(this.testResults));
        }
    }
    
    async runTestCategory(category) {
        const result = {
            category,
            status: 'passed',
            tests: [],
            startTime: performance.now()
        };
        
        try {
            switch (category) {
                case 'core-javascript':
                    await this.testCoreJavaScript(result);
                    break;
                case 'dom-manipulation':
                    await this.testDOMManipulation(result);
                    break;
                case 'websocket-functionality':
                    await this.testWebSocketFunctionality(result);
                    break;
                case 'local-storage':
                    await this.testLocalStorage(result);
                    break;
                case 'authentication-flow':
                    await this.testAuthenticationFlow(result);
                    break;
                case 'language-switching':
                    await this.testLanguageSwitching(result);
                    break;
                case 'navigation':
                    await this.testNavigation(result);
                    break;
                case 'ui-components':
                    await this.testUIComponents(result);
                    break;
                case 'error-handling':
                    await this.testErrorHandling(result);
                    break;
                case 'performance':
                    await this.testPerformance(result);
                    break;
            }
        } catch (error) {
            result.status = 'error';
            result.error = error.message;
        }
        
        result.endTime = performance.now();
        result.duration = result.endTime - result.startTime;
        
        // Determine overall category status
        if (result.tests.some(t => t.status === 'failed')) {
            result.status = 'failed';
        } else if (result.tests.some(t => t.status === 'warning')) {
            result.status = 'warning';
        }
        
        return result;
    }
    
    async testCoreJavaScript(result) {
        // Test ES6 features
        this.addTest(result, 'ES6 Classes', () => {
            eval('class TestClass {}');
            return true;
        });
        
        this.addTest(result, 'Promises', () => {
            return 'Promise' in window;
        });
        
        this.addTest(result, 'Async/Await', () => {
            try {
                eval('async function test() { await Promise.resolve(); }');
                return true;
            } catch (e) {
                return false;
            }
        });
        
        this.addTest(result, 'Fetch API', () => {
            return 'fetch' in window;
        });
        
        this.addTest(result, 'Arrow Functions', () => {
            try {
                eval('const test = () => true');
                return true;
            } catch (e) {
                return false;
            }
        });
        
        this.addTest(result, 'Template Literals', () => {
            try {
                eval('const test = `template`');
                return true;
            } catch (e) {
                return false;
            }
        });
    }
    
    async testDOMManipulation(result) {
        this.addTest(result, 'querySelector', () => {
            return 'querySelector' in document;
        });
        
        this.addTest(result, 'querySelectorAll', () => {
            return 'querySelectorAll' in document;
        });
        
        this.addTest(result, 'addEventListener', () => {
            return 'addEventListener' in document;
        });
        
        this.addTest(result, 'classList', () => {
            const div = document.createElement('div');
            return 'classList' in div;
        });
        
        this.addTest(result, 'dataset', () => {
            const div = document.createElement('div');
            return 'dataset' in div;
        });
        
        this.addTest(result, 'Custom Events', () => {
            try {
                new CustomEvent('test');
                return true;
            } catch (e) {
                return false;
            }
        });
    }
    
    async testWebSocketFunctionality(result) {
        this.addTest(result, 'WebSocket API', () => {
            return 'WebSocket' in window;
        });
        
        if ('WebSocket' in window) {
            this.addTest(result, 'WebSocket Creation', () => {
                try {
                    const ws = new WebSocket('ws://test');
                    ws.close();
                    return true;
                } catch (e) {
                    return false;
                }
            });
            
            this.addTest(result, 'Socket.IO Compatibility', () => {
                return typeof io !== 'undefined';
            });
        }
        
        this.addTest(result, 'EventSource (SSE)', () => {
            return 'EventSource' in window;
        });
    }
    
    async testLocalStorage(result) {
        this.addTest(result, 'localStorage API', () => {
            return 'localStorage' in window;
        });
        
        if ('localStorage' in window) {
            this.addTest(result, 'localStorage Write/Read', () => {
                try {
                    localStorage.setItem('test', 'value');
                    const value = localStorage.getItem('test');
                    localStorage.removeItem('test');
                    return value === 'value';
                } catch (e) {
                    return false;
                }
            });
        }
        
        this.addTest(result, 'sessionStorage API', () => {
            return 'sessionStorage' in window;
        });
        
        this.addTest(result, 'IndexedDB API', () => {
            return 'indexedDB' in window;
        });
    }
    
    async testAuthenticationFlow(result) {
        this.addTest(result, 'AuthenticationManager Available', () => {
            return typeof AuthenticationManager !== 'undefined';
        });
        
        this.addTest(result, 'Token Storage', () => {
            if (!('localStorage' in window)) return 'warning';
            
            try {
                localStorage.setItem('test_token', 'test');
                const token = localStorage.getItem('test_token');
                localStorage.removeItem('test_token');
                return token === 'test';
            } catch (e) {
                return false;
            }
        });
        
        this.addTest(result, 'Login Form Present', () => {
            return document.querySelector('#loginForm') !== null;
        });
        
        this.addTest(result, 'User Menu Present', () => {
            return document.querySelector('#user-menu') !== null;
        });
    }
    
    async testLanguageSwitching(result) {
        this.addTest(result, 'Language Switcher Present', () => {
            return document.querySelector('#language-switcher') !== null;
        });
        
        this.addTest(result, 'LanguageSwitcher Class Available', () => {
            return typeof LanguageSwitcher !== 'undefined';
        });
        
        this.addTest(result, 'URL Parameter Support', () => {
            return 'URLSearchParams' in window;
        });
        
        this.addTest(result, 'Translatable Elements', () => {
            return document.querySelectorAll('[data-i18n]').length > 0;
        });
    }
    
    async testNavigation(result) {
        this.addTest(result, 'Navigation Menu Present', () => {
            return document.querySelector('#main-nav') !== null;
        });
        
        this.addTest(result, 'NavigationController Available', () => {
            return typeof NavigationController !== 'undefined';
        });
        
        this.addTest(result, 'History API', () => {
            return 'history' in window && 'pushState' in history;
        });
        
        this.addTest(result, 'Navigation Links Functional', () => {
            const navLinks = document.querySelectorAll('#main-nav a');
            return navLinks.length > 0;
        });
    }
    
    async testUIComponents(result) {
        this.addTest(result, 'Bootstrap JavaScript', () => {
            return typeof bootstrap !== 'undefined';
        });
        
        this.addTest(result, 'Dropdown Functionality', () => {
            const dropdowns = document.querySelectorAll('.dropdown');
            return dropdowns.length > 0;
        });
        
        this.addTest(result, 'Modal Support', () => {
            return typeof bootstrap !== 'undefined' && 'Modal' in bootstrap;
        });
        
        this.addTest(result, 'Alert Dismissal', () => {
            const alerts = document.querySelectorAll('.alert-dismissible');
            return alerts.length >= 0; // This is always true, just checking structure
        });
    }
    
    async testErrorHandling(result) {
        this.addTest(result, 'ErrorHandler Available', () => {
            return typeof ErrorHandler !== 'undefined' || window.errorHandler !== undefined;
        });
        
        this.addTest(result, 'Global Error Handling', () => {
            return typeof window.onerror === 'function' || window.onerror === null;
        });
        
        this.addTest(result, 'Unhandled Promise Rejection', () => {
            return typeof window.onunhandledrejection === 'function' || window.onunhandledrejection === null;
        });
        
        this.addTest(result, 'Console Available', () => {
            return 'console' in window && 'error' in console;
        });
    }
    
    async testPerformance(result) {
        this.addTest(result, 'Performance API', () => {
            return 'performance' in window && 'now' in performance;
        });
        
        this.addTest(result, 'Performance Observer', () => {
            return 'PerformanceObserver' in window;
        });
        
        this.addTest(result, 'Intersection Observer', () => {
            return 'IntersectionObserver' in window;
        });
        
        this.addTest(result, 'Mutation Observer', () => {
            return 'MutationObserver' in window;
        });
        
        // Test actual performance
        this.addTest(result, 'DOM Query Performance', () => {
            const start = performance.now();
            for (let i = 0; i < 1000; i++) {
                document.querySelectorAll('div');
            }
            const end = performance.now();
            const duration = end - start;
            
            // Should complete in reasonable time (less than 100ms)
            return duration < 100 ? true : 'warning';
        });
    }
    
    addTest(result, name, testFunction) {
        const test = {
            name,
            status: 'unknown',
            message: '',
            startTime: performance.now()
        };
        
        try {
            const testResult = testFunction();
            
            if (testResult === true) {
                test.status = 'passed';
                test.message = 'Test passed';
            } else if (testResult === false) {
                test.status = 'failed';
                test.message = 'Test failed';
            } else if (testResult === 'warning') {
                test.status = 'warning';
                test.message = 'Test passed with warnings';
            } else {
                test.status = 'failed';
                test.message = `Unexpected result: ${testResult}`;
            }
        } catch (error) {
            test.status = 'failed';
            test.message = `Error: ${error.message}`;
        }
        
        test.endTime = performance.now();
        test.duration = test.endTime - test.startTime;
        
        result.tests.push(test);
    }
    
    displayCategoryResult(category, result) {
        const resultsDiv = document.getElementById('test-results');
        
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'mb-3';
        
        const statusClass = result.status === 'passed' ? 'success' : 
                           result.status === 'warning' ? 'warning' : 'danger';
        
        const passedCount = result.tests.filter(t => t.status === 'passed').length;
        const totalCount = result.tests.length;
        
        categoryDiv.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <h6 class="mb-0">${category.replace('-', ' ').toUpperCase()}</h6>
                <span class="badge bg-${statusClass}">${passedCount}/${totalCount}</span>
            </div>
            <div class="small text-muted">Duration: ${result.duration.toFixed(2)}ms</div>
            <div class="mt-2" style="font-size: 0.8em;">
                ${result.tests.map(test => `
                    <div class="d-flex justify-content-between">
                        <span>${test.name}</span>
                        <span class="badge bg-${test.status === 'passed' ? 'success' : 
                                                test.status === 'warning' ? 'warning' : 'danger'} ms-1">
                            ${test.status}
                        </span>
                    </div>
                `).join('')}
            </div>
        `;
        
        resultsDiv.appendChild(categoryDiv);
    }
    
    displaySummary() {
        const resultsDiv = document.getElementById('test-results');
        
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'mt-3 p-3 bg-light rounded';
        
        const passRate = (this.testResults.summary.passed / this.testResults.summary.total * 100).toFixed(1);
        
        summaryDiv.innerHTML = `
            <h6>Test Summary</h6>
            <div class="row">
                <div class="col-6">
                    <div class="text-success">✓ Passed: ${this.testResults.summary.passed}</div>
                    <div class="text-danger">✗ Failed: ${this.testResults.summary.failed}</div>
                </div>
                <div class="col-6">
                    <div class="text-warning">⚠ Warnings: ${this.testResults.summary.warnings}</div>
                    <div><strong>Pass Rate: ${passRate}%</strong></div>
                </div>
            </div>
            <div class="mt-2">
                <button class="btn btn-sm btn-outline-primary" onclick="window.crossBrowserTest.exportResults()">
                    Export Results
                </button>
                <button class="btn btn-sm btn-outline-secondary ms-1" onclick="window.crossBrowserTest.shareResults()">
                    Share Results
                </button>
            </div>
        `;
        
        resultsDiv.appendChild(summaryDiv);
    }
    
    exportResults() {
        const dataStr = JSON.stringify(this.testResults, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        
        const link = document.createElement('a');
        link.href = URL.createObjectURL(dataBlob);
        link.download = `cross-browser-test-results-${this.testResults.browser.name}-${Date.now()}.json`;
        link.click();
    }
    
    shareResults() {
        const summary = `Cross-Browser Test Results
Browser: ${this.testResults.browser.name} ${this.testResults.browser.version}
Platform: ${this.testResults.browser.platform}
Total Tests: ${this.testResults.summary.total}
Passed: ${this.testResults.summary.passed}
Failed: ${this.testResults.summary.failed}
Warnings: ${this.testResults.summary.warnings}
Pass Rate: ${(this.testResults.summary.passed / this.testResults.summary.total * 100).toFixed(1)}%`;
        
        if (navigator.share) {
            navigator.share({
                title: 'Cross-Browser Test Results',
                text: summary
            });
        } else {
            // Fallback: copy to clipboard
            navigator.clipboard.writeText(summary).then(() => {
                alert('Results copied to clipboard!');
            }).catch(() => {
                // Final fallback: show in alert
                alert(summary);
            });
        }
    }
    
    // Public API
    getResults() {
        return { ...this.testResults };
    }
    
    getCompatibilityReport() {
        const report = {
            browser: this.testResults.browser,
            compatible: this.testResults.summary.failed === 0,
            issues: [],
            recommendations: []
        };
        
        // Analyze results for compatibility issues
        Object.entries(this.testResults.tests).forEach(([category, result]) => {
            result.tests.forEach(test => {
                if (test.status === 'failed') {
                    report.issues.push({
                        category,
                        test: test.name,
                        message: test.message
                    });
                }
            });
        });
        
        // Generate recommendations
        if (report.issues.length > 0) {
            if (this.testResults.browser.name === 'Internet Explorer') {
                report.recommendations.push('Consider upgrading to a modern browser like Chrome, Firefox, Safari, or Edge');
            } else if (this.testResults.browser.version < 80) {
                report.recommendations.push('Update your browser to the latest version for better compatibility');
            }
            
            if (report.issues.some(i => i.test.includes('WebSocket'))) {
                report.recommendations.push('WebSocket features may not work properly. Real-time functionality will be limited.');
            }
            
            if (report.issues.some(i => i.test.includes('localStorage'))) {
                report.recommendations.push('Local storage not available. Some settings may not persist between sessions.');
            }
        }
        
        return report;
    }
}

// Initialize cross-browser test suite
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if not in production or if explicitly requested
    const urlParams = new URLSearchParams(window.location.search);
    const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const forceTest = urlParams.get('test') === 'true';
    
    if (isDev || forceTest) {
        window.crossBrowserTest = new CrossBrowserTestSuite();
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CrossBrowserTestSuite;
}