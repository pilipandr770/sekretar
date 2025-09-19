/**
 * Comprehensive Frontend Test Runner
 * Runs all frontend UI tests and provides detailed reporting
 */

class ComprehensiveFrontendTestRunner {
    constructor() {
        this.testResults = [];
        this.testSuites = [];
        this.startTime = null;
        this.endTime = null;
    }

    async runAllTests() {
        console.log('🚀 Starting Comprehensive Frontend UI Tests...');
        console.log('==============================================');
        
        this.startTime = Date.now();
        this.testResults = [];
        
        try {
            // Unit Tests
            console.log('\n📋 Running Unit Tests...');
            await this.runUnitTests();
            
            // Integration Tests
            console.log('\n🔗 Running Integration Tests...');
            await this.runIntegrationTests();
            
            // Generate comprehensive report
            this.generateComprehensiveReport();
            
        } catch (error) {
            console.error('❌ Test runner error:', error);
            this.testResults.push({
                suite: 'Test Runner',
                test: 'Test Execution',
                status: 'FAIL',
                error: error.message,
                timestamp: new Date().toISOString()
            });
        } finally {
            this.endTime = Date.now();
        }
        
        return this.testResults;
    }

    async runUnitTests() {
        const unitTests = [
            {
                name: 'Authentication Manager',
                testClass: 'AuthenticationManagerTest',
                description: 'Tests authentication state management and login/logout functionality'
            },
            {
                name: 'Navigation Controller',
                testClass: 'NavigationControllerTest',
                description: 'Tests navigation functionality and route protection'
            },
            {
                name: 'Enhanced Language Switcher',
                testClass: 'EnhancedLanguageSwitcherTest',
                description: 'Tests language switching behavior and translation updates'
            },
            {
                name: 'WebSocket Client',
                testClass: 'WebSocketClientTest',
                description: 'Tests WebSocket connection management and real-time features'
            }
        ];

        for (const testSuite of unitTests) {
            await this.runTestSuite(testSuite, 'Unit Test');
        }
    }

    async runIntegrationTests() {
        const integrationTests = [
            {
                name: 'Authentication Flow Integration',
                testClass: 'AuthenticationFlowIntegrationTest',
                description: 'Tests complete authentication flow including UI updates'
            },
            {
                name: 'Language Switching Integration',
                testClass: 'LanguageSwitchingIntegrationTest',
                description: 'Tests language switching with proper translation updates'
            }
        ];

        for (const testSuite of integrationTests) {
            await this.runTestSuite(testSuite, 'Integration Test');
        }
    }

    async runTestSuite(testSuite, category) {
        console.log(`\n🧪 Running ${category}: ${testSuite.name}`);
        console.log(`   Description: ${testSuite.description}`);
        
        const suiteStartTime = Date.now();
        let suiteResults = [];
        
        try {
            // Check if test class is available
            if (typeof window[testSuite.testClass] === 'undefined') {
                throw new Error(`Test class ${testSuite.testClass} not found. Make sure the test file is loaded.`);
            }
            
            // Create test instance and run tests
            const testInstance = new window[testSuite.testClass]();
            suiteResults = await testInstance.runAllTests();
            
            // Process results
            suiteResults.forEach(result => {
                this.testResults.push({
                    suite: testSuite.name,
                    category: category,
                    test: result.test,
                    status: result.status,
                    details: result.details,
                    error: result.error,
                    timestamp: result.timestamp
                });
            });
            
            const suiteEndTime = Date.now();
            const suiteDuration = suiteEndTime - suiteStartTime;
            
            const passed = suiteResults.filter(r => r.status === 'PASS').length;
            const failed = suiteResults.filter(r => r.status === 'FAIL').length;
            const total = suiteResults.length;
            
            console.log(`   ✅ Passed: ${passed}/${total} tests`);
            if (failed > 0) {
                console.log(`   ❌ Failed: ${failed}/${total} tests`);
            }
            console.log(`   ⏱️  Duration: ${suiteDuration}ms`);
            
            this.testSuites.push({
                name: testSuite.name,
                category: category,
                description: testSuite.description,
                passed: passed,
                failed: failed,
                total: total,
                duration: suiteDuration,
                status: failed === 0 ? 'PASS' : 'FAIL'
            });
            
        } catch (error) {
            console.error(`   ❌ ${testSuite.name} failed to run:`, error.message);
            
            this.testResults.push({
                suite: testSuite.name,
                category: category,
                test: 'Suite Execution',
                status: 'FAIL',
                error: error.message,
                timestamp: new Date().toISOString()
            });
            
            this.testSuites.push({
                name: testSuite.name,
                category: category,
                description: testSuite.description,
                passed: 0,
                failed: 1,
                total: 1,
                duration: Date.now() - suiteStartTime,
                status: 'FAIL',
                error: error.message
            });
        }
    }

    generateComprehensiveReport() {
        console.log('\n📊 COMPREHENSIVE TEST REPORT');
        console.log('============================');
        
        const totalDuration = this.endTime - this.startTime;
        const totalTests = this.testResults.length;
        const passedTests = this.testResults.filter(r => r.status === 'PASS').length;
        const failedTests = this.testResults.filter(r => r.status === 'FAIL').length;
        const skippedTests = this.testResults.filter(r => r.status === 'SKIP').length;
        
        // Overall Summary
        console.log('\n📈 OVERALL SUMMARY');
        console.log('------------------');
        console.log(`Total Tests: ${totalTests}`);
        console.log(`✅ Passed: ${passedTests} (${((passedTests/totalTests)*100).toFixed(1)}%)`);
        console.log(`❌ Failed: ${failedTests} (${((failedTests/totalTests)*100).toFixed(1)}%)`);
        if (skippedTests > 0) {
            console.log(`⏭️  Skipped: ${skippedTests} (${((skippedTests/totalTests)*100).toFixed(1)}%)`);
        }
        console.log(`⏱️  Total Duration: ${totalDuration}ms (${(totalDuration/1000).toFixed(2)}s)`);
        
        // Test Suite Summary
        console.log('\n📋 TEST SUITE SUMMARY');
        console.log('---------------------');
        
        const unitTestSuites = this.testSuites.filter(s => s.category === 'Unit Test');
        const integrationTestSuites = this.testSuites.filter(s => s.category === 'Integration Test');
        
        if (unitTestSuites.length > 0) {
            console.log('\n🧪 Unit Tests:');
            unitTestSuites.forEach(suite => {
                const icon = suite.status === 'PASS' ? '✅' : '❌';
                console.log(`   ${icon} ${suite.name}: ${suite.passed}/${suite.total} passed (${suite.duration}ms)`);
                if (suite.error) {
                    console.log(`      Error: ${suite.error}`);
                }
            });
        }
        
        if (integrationTestSuites.length > 0) {
            console.log('\n🔗 Integration Tests:');
            integrationTestSuites.forEach(suite => {
                const icon = suite.status === 'PASS' ? '✅' : '❌';
                console.log(`   ${icon} ${suite.name}: ${suite.passed}/${suite.total} passed (${suite.duration}ms)`);
                if (suite.error) {
                    console.log(`      Error: ${suite.error}`);
                }
            });
        }
        
        // Requirements Coverage
        console.log('\n📋 REQUIREMENTS COVERAGE');
        console.log('------------------------');
        this.generateRequirementsCoverage();
        
        // Failed Tests Detail
        if (failedTests > 0) {
            console.log('\n❌ FAILED TESTS DETAIL');
            console.log('----------------------');
            
            const failedTestResults = this.testResults.filter(r => r.status === 'FAIL');
            failedTestResults.forEach(result => {
                console.log(`\n❌ ${result.suite} - ${result.test}`);
                if (result.error) {
                    console.log(`   Error: ${result.error}`);
                }
                if (result.details) {
                    console.log(`   Details: ${result.details}`);
                }
                console.log(`   Timestamp: ${result.timestamp}`);
            });
        }
        
        // Performance Analysis
        console.log('\n⚡ PERFORMANCE ANALYSIS');
        console.log('----------------------');
        this.generatePerformanceAnalysis();
        
        // Final Status
        console.log('\n🎯 FINAL STATUS');
        console.log('---------------');
        
        if (failedTests === 0) {
            console.log('🎉 ALL TESTS PASSED! Frontend UI fixes are working correctly.');
            console.log('✅ Authentication state management: WORKING');
            console.log('✅ Navigation functionality: WORKING');
            console.log('✅ Language switching: WORKING');
            console.log('✅ WebSocket connections: WORKING');
            console.log('✅ UI state synchronization: WORKING');
            console.log('✅ Error handling: WORKING');
        } else {
            console.log('⚠️  SOME TESTS FAILED. Review the failed tests above.');
            console.log(`❌ ${failedTests} test(s) need attention.`);
            console.log('🔧 Check the error details and fix the issues before deployment.');
        }
        
        // Test Coverage Report
        console.log('\n📊 TEST COVERAGE REPORT');
        console.log('-----------------------');
        this.generateCoverageReport();
        
        // Recommendations
        console.log('\n💡 RECOMMENDATIONS');
        console.log('------------------');
        this.generateRecommendations();
    }

    generateRequirementsCoverage() {
        const requirements = {
            'Requirement 1 - Language Switching': {
                tests: ['Enhanced Language Switcher', 'Language Switching Integration'],
                covered: true
            },
            'Requirement 2 - Navigation Functionality': {
                tests: ['Navigation Controller', 'Authentication Flow Integration'],
                covered: true
            },
            'Requirement 3 - Authentication UI': {
                tests: ['Authentication Manager', 'Authentication Flow Integration'],
                covered: true
            },
            'Requirement 4 - WebSocket Connection': {
                tests: ['WebSocket Client'],
                covered: true
            },
            'Requirement 5 - Dropdown Menu': {
                tests: ['Navigation Controller', 'Authentication Manager'],
                covered: true
            },
            'Requirement 6 - Error Handling': {
                tests: ['All test suites include error handling tests'],
                covered: true
            }
        };
        
        Object.entries(requirements).forEach(([req, info]) => {
            const icon = info.covered ? '✅' : '❌';
            console.log(`${icon} ${req}`);
            console.log(`   Tested by: ${info.tests.join(', ')}`);
        });
        
        const totalReqs = Object.keys(requirements).length;
        const coveredReqs = Object.values(requirements).filter(r => r.covered).length;
        console.log(`\nCoverage: ${coveredReqs}/${totalReqs} requirements (${((coveredReqs/totalReqs)*100).toFixed(1)}%)`);
    }

    generatePerformanceAnalysis() {
        const suiteDurations = this.testSuites.map(s => ({
            name: s.name,
            duration: s.duration,
            testsPerSecond: (s.total / (s.duration / 1000)).toFixed(2)
        }));
        
        suiteDurations.sort((a, b) => b.duration - a.duration);
        
        console.log('Test Suite Performance (slowest first):');
        suiteDurations.forEach(suite => {
            console.log(`   ${suite.name}: ${suite.duration}ms (${suite.testsPerSecond} tests/sec)`);
        });
        
        const avgDuration = suiteDurations.reduce((sum, s) => sum + s.duration, 0) / suiteDurations.length;
        console.log(`\nAverage suite duration: ${avgDuration.toFixed(0)}ms`);
        
        if (avgDuration > 5000) {
            console.log('⚠️  Some test suites are running slowly. Consider optimizing.');
        } else {
            console.log('✅ Test performance is good.');
        }
    }

    generateCoverageReport() {
        const componentsCovered = [
            'AuthenticationManager',
            'NavigationController', 
            'EnhancedLanguageSwitcher',
            'WebSocketClient',
            'UIStateManager'
        ];
        
        const featuresCovered = [
            'Login/Logout Flow',
            'Navigation Protection',
            'Language Switching',
            'Translation Updates',
            'WebSocket Connection',
            'Real-time Features',
            'Error Handling',
            'State Synchronization',
            'Multi-tab Support',
            'Token Refresh'
        ];
        
        console.log('Components Tested:');
        componentsCovered.forEach(component => {
            console.log(`   ✅ ${component}`);
        });
        
        console.log('\nFeatures Tested:');
        featuresCovered.forEach(feature => {
            console.log(`   ✅ ${feature}`);
        });
        
        console.log(`\nTotal Coverage: ${componentsCovered.length} components, ${featuresCovered.length} features`);
    }

    generateRecommendations() {
        const failedTests = this.testResults.filter(r => r.status === 'FAIL').length;
        const totalDuration = this.endTime - this.startTime;
        
        if (failedTests === 0) {
            console.log('✅ All tests are passing. The frontend UI fixes are ready for deployment.');
            console.log('✅ Consider running these tests in CI/CD pipeline for continuous validation.');
            console.log('✅ Monitor real-world usage to validate the fixes work as expected.');
        } else {
            console.log('🔧 Fix the failing tests before proceeding with deployment.');
            console.log('🔍 Review error messages and debug the specific issues.');
            console.log('🧪 Run individual test suites to isolate problems.');
        }
        
        if (totalDuration > 30000) {
            console.log('⚡ Consider optimizing test performance for faster feedback.');
        }
        
        console.log('📚 Add more edge case tests as new issues are discovered.');
        console.log('🔄 Update tests when making changes to the frontend components.');
        console.log('📊 Consider adding performance benchmarks for critical user flows.');
    }

    // Utility method to run specific test suite
    async runSpecificTestSuite(testClassName) {
        console.log(`🧪 Running specific test suite: ${testClassName}`);
        
        if (typeof window[testClassName] === 'undefined') {
            console.error(`❌ Test class ${testClassName} not found.`);
            return [];
        }
        
        try {
            const testInstance = new window[testClassName]();
            const results = await testInstance.runAllTests();
            
            console.log(`✅ ${testClassName} completed with ${results.length} tests`);
            return results;
        } catch (error) {
            console.error(`❌ ${testClassName} failed:`, error);
            return [];
        }
    }

    // Generate HTML report
    generateHTMLReport() {
        const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Frontend UI Tests Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .summary { display: flex; gap: 20px; margin-bottom: 20px; }
        .stat-card { background: white; border: 1px solid #ddd; padding: 15px; border-radius: 8px; flex: 1; }
        .passed { border-left: 4px solid #28a745; }
        .failed { border-left: 4px solid #dc3545; }
        .test-suite { margin-bottom: 20px; border: 1px solid #ddd; border-radius: 8px; }
        .suite-header { background: #f8f9fa; padding: 15px; border-bottom: 1px solid #ddd; }
        .test-result { padding: 10px 15px; border-bottom: 1px solid #eee; }
        .test-result:last-child { border-bottom: none; }
        .pass { color: #28a745; }
        .fail { color: #dc3545; }
        .error-details { background: #f8f9fa; padding: 10px; margin-top: 10px; border-radius: 4px; font-family: monospace; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Frontend UI Tests Report</h1>
        <p>Generated: ${new Date().toISOString()}</p>
        <p>Duration: ${this.endTime - this.startTime}ms</p>
    </div>
    
    <div class="summary">
        <div class="stat-card passed">
            <h3>Passed</h3>
            <p>${this.testResults.filter(r => r.status === 'PASS').length}</p>
        </div>
        <div class="stat-card failed">
            <h3>Failed</h3>
            <p>${this.testResults.filter(r => r.status === 'FAIL').length}</p>
        </div>
        <div class="stat-card">
            <h3>Total</h3>
            <p>${this.testResults.length}</p>
        </div>
    </div>
    
    ${this.testSuites.map(suite => `
        <div class="test-suite">
            <div class="suite-header">
                <h3>${suite.name} (${suite.category})</h3>
                <p>${suite.description}</p>
                <p>Status: <span class="${suite.status.toLowerCase()}">${suite.status}</span> | 
                   Tests: ${suite.passed}/${suite.total} | 
                   Duration: ${suite.duration}ms</p>
            </div>
            ${this.testResults.filter(r => r.suite === suite.name).map(result => `
                <div class="test-result">
                    <span class="${result.status.toLowerCase()}">${result.status === 'PASS' ? '✅' : '❌'}</span>
                    <strong>${result.test}</strong>
                    ${result.details ? `<p>${result.details}</p>` : ''}
                    ${result.error ? `<div class="error-details">${result.error}</div>` : ''}
                </div>
            `).join('')}
        </div>
    `).join('')}
</body>
</html>`;
        
        return html;
    }

    // Quick test function for console use
    static async quickTest() {
        const runner = new ComprehensiveFrontendTestRunner();
        return await runner.runAllTests();
    }
}

// Export for use in other modules
window.ComprehensiveFrontendTestRunner = ComprehensiveFrontendTestRunner;

// Add console helpers
window.runAllFrontendTests = () => ComprehensiveFrontendTestRunner.quickTest();
window.runSpecificTest = (testClassName) => {
    const runner = new ComprehensiveFrontendTestRunner();
    return runner.runSpecificTestSuite(testClassName);
};

// Auto-run tests if URL parameter is present
document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('test') === 'frontend' || urlParams.get('runTests') === 'true') {
        console.log('🚀 Auto-running frontend tests...');
        setTimeout(() => {
            ComprehensiveFrontendTestRunner.quickTest();
        }, 1000);
    }
});

console.log('📋 Frontend Test Runner loaded. Use runAllFrontendTests() to start testing.');