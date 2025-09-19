/**
 * UI State Management System Test
 * Tests the centralized UI state manager functionality
 */

class UIStateTest {
    constructor() {
        this.testResults = [];
        this.uiStateManager = null;
    }

    async runTests() {
        console.log('Starting UI State Management System Tests...');
        
        // Initialize UI state manager for testing
        this.uiStateManager = new UIStateManager();
        this.uiStateManager.init();
        
        // Run individual tests
        this.testInitialization();
        this.testStateUpdates();
        this.testSubscriptions();
        this.testAuthStateIntegration();
        this.testLanguageStateIntegration();
        this.testWebSocketStateIntegration();
        this.testNotificationManagement();
        this.testStateValidation();
        this.testStateSynchronization();
        
        // Display results
        this.displayResults();
        
        // Cleanup
        this.cleanup();
    }

    testInitialization() {
        console.log('Testing UI State Manager initialization...');
        
        try {
            // Test initial state
            const initialState = this.uiStateManager.getState();
            
            this.assert(
                initialState.isAuthenticated === false,
                'Initial authentication state should be false'
            );
            
            this.assert(
                initialState.currentLanguage === 'en',
                'Initial language should be "en"'
            );
            
            this.assert(
                initialState.isWebSocketConnected === false,
                'Initial WebSocket state should be false'
            );
            
            this.assert(
                Array.isArray(initialState.notifications),
                'Notifications should be an array'
            );
            
            this.assert(
                initialState.notifications.length === 0,
                'Initial notifications should be empty'
            );
            
            console.log('✓ Initialization test passed');
        } catch (error) {
            console.error('✗ Initialization test failed:', error);
            this.testResults.push({ test: 'Initialization', passed: false, error: error.message });
        }
    }

    testStateUpdates() {
        console.log('Testing state updates...');
        
        try {
            const initialState = this.uiStateManager.getState();
            
            // Test updating authentication state
            this.uiStateManager.updateAuthState(true, { id: 1, email: 'test@example.com' });
            
            const updatedState = this.uiStateManager.getState();
            
            this.assert(
                updatedState.isAuthenticated === true,
                'Authentication state should be updated'
            );
            
            this.assert(
                updatedState.currentUser.email === 'test@example.com',
                'User data should be stored correctly'
            );
            
            // Test updating language state
            this.uiStateManager.updateLanguage('de');
            
            const languageUpdatedState = this.uiStateManager.getState();
            
            this.assert(
                languageUpdatedState.currentLanguage === 'de',
                'Language state should be updated'
            );
            
            // Test updating WebSocket state
            this.uiStateManager.updateWebSocketState(true);
            
            const wsUpdatedState = this.uiStateManager.getState();
            
            this.assert(
                wsUpdatedState.isWebSocketConnected === true,
                'WebSocket state should be updated'
            );
            
            console.log('✓ State updates test passed');
        } catch (error) {
            console.error('✗ State updates test failed:', error);
            this.testResults.push({ test: 'State Updates', passed: false, error: error.message });
        }
    }

    testSubscriptions() {
        console.log('Testing state subscriptions...');
        
        try {
            let callbackCalled = false;
            let receivedNewState = null;
            let receivedOldState = null;
            
            // Subscribe to state changes
            const callback = (newState, oldState) => {
                callbackCalled = true;
                receivedNewState = newState;
                receivedOldState = oldState;
            };
            
            this.uiStateManager.subscribe(callback);
            
            // Trigger a state change
            this.uiStateManager.setLoading(true);
            
            this.assert(
                callbackCalled === true,
                'Callback should be called on state change'
            );
            
            this.assert(
                receivedNewState.isLoading === true,
                'New state should reflect the change'
            );
            
            this.assert(
                receivedOldState.isLoading === false,
                'Old state should contain previous value'
            );
            
            // Test unsubscribe
            this.uiStateManager.unsubscribe(callback);
            
            callbackCalled = false;
            this.uiStateManager.setLoading(false);
            
            this.assert(
                callbackCalled === false,
                'Callback should not be called after unsubscribe'
            );
            
            console.log('✓ Subscriptions test passed');
        } catch (error) {
            console.error('✗ Subscriptions test failed:', error);
            this.testResults.push({ test: 'Subscriptions', passed: false, error: error.message });
        }
    }

    testAuthStateIntegration() {
        console.log('Testing authentication state integration...');
        
        try {
            // Test authentication state methods
            this.assert(
                typeof this.uiStateManager.isAuthenticated === 'function',
                'isAuthenticated method should exist'
            );
            
            this.assert(
                typeof this.uiStateManager.getCurrentUser === 'function',
                'getCurrentUser method should exist'
            );
            
            // Test authentication state
            this.uiStateManager.updateAuthState(true, { id: 2, email: 'auth@test.com' });
            
            this.assert(
                this.uiStateManager.isAuthenticated() === true,
                'isAuthenticated should return true'
            );
            
            this.assert(
                this.uiStateManager.getCurrentUser().email === 'auth@test.com',
                'getCurrentUser should return correct user'
            );
            
            console.log('✓ Auth state integration test passed');
        } catch (error) {
            console.error('✗ Auth state integration test failed:', error);
            this.testResults.push({ test: 'Auth State Integration', passed: false, error: error.message });
        }
    }

    testLanguageStateIntegration() {
        console.log('Testing language state integration...');
        
        try {
            // Test language state methods
            this.assert(
                typeof this.uiStateManager.getCurrentLanguage === 'function',
                'getCurrentLanguage method should exist'
            );
            
            // Test language state
            this.uiStateManager.updateLanguage('uk');
            
            this.assert(
                this.uiStateManager.getCurrentLanguage() === 'uk',
                'getCurrentLanguage should return correct language'
            );
            
            console.log('✓ Language state integration test passed');
        } catch (error) {
            console.error('✗ Language state integration test failed:', error);
            this.testResults.push({ test: 'Language State Integration', passed: false, error: error.message });
        }
    }

    testWebSocketStateIntegration() {
        console.log('Testing WebSocket state integration...');
        
        try {
            // Test WebSocket state methods
            this.assert(
                typeof this.uiStateManager.isWebSocketConnected === 'function',
                'isWebSocketConnected method should exist'
            );
            
            // Test WebSocket state
            this.uiStateManager.updateWebSocketState(true);
            
            this.assert(
                this.uiStateManager.isWebSocketConnected() === true,
                'isWebSocketConnected should return true'
            );
            
            this.uiStateManager.updateWebSocketState(false);
            
            this.assert(
                this.uiStateManager.isWebSocketConnected() === false,
                'isWebSocketConnected should return false'
            );
            
            console.log('✓ WebSocket state integration test passed');
        } catch (error) {
            console.error('✗ WebSocket state integration test failed:', error);
            this.testResults.push({ test: 'WebSocket State Integration', passed: false, error: error.message });
        }
    }

    testNotificationManagement() {
        console.log('Testing notification management...');
        
        try {
            // Test adding notifications
            this.uiStateManager.addNotification({
                type: 'info',
                title: 'Test Notification',
                message: 'This is a test notification'
            });
            
            const notifications = this.uiStateManager.getNotifications();
            
            this.assert(
                notifications.length === 1,
                'Notification should be added'
            );
            
            this.assert(
                notifications[0].title === 'Test Notification',
                'Notification should have correct title'
            );
            
            // Test removing notifications
            const notificationId = notifications[0].id;
            this.uiStateManager.removeNotification(notificationId);
            
            const updatedNotifications = this.uiStateManager.getNotifications();
            
            this.assert(
                updatedNotifications.length === 0,
                'Notification should be removed'
            );
            
            // Test clearing all notifications
            this.uiStateManager.addNotification({ title: 'Test 1' });
            this.uiStateManager.addNotification({ title: 'Test 2' });
            
            this.uiStateManager.clearNotifications();
            
            const clearedNotifications = this.uiStateManager.getNotifications();
            
            this.assert(
                clearedNotifications.length === 0,
                'All notifications should be cleared'
            );
            
            console.log('✓ Notification management test passed');
        } catch (error) {
            console.error('✗ Notification management test failed:', error);
            this.testResults.push({ test: 'Notification Management', passed: false, error: error.message });
        }
    }

    testStateValidation() {
        console.log('Testing state validation...');
        
        try {
            // Test state validation
            const validation = this.uiStateManager.validateState();
            
            this.assert(
                typeof validation === 'object',
                'Validation should return an object'
            );
            
            this.assert(
                typeof validation.isValid === 'boolean',
                'Validation should have isValid property'
            );
            
            this.assert(
                Array.isArray(validation.issues),
                'Validation should have issues array'
            );
            
            // Test state snapshot
            const snapshot = this.uiStateManager.getStateSnapshot();
            
            this.assert(
                typeof snapshot === 'object',
                'Snapshot should return an object'
            );
            
            this.assert(
                typeof snapshot.timestamp === 'string',
                'Snapshot should have timestamp'
            );
            
            this.assert(
                typeof snapshot.state === 'object',
                'Snapshot should have state object'
            );
            
            console.log('✓ State validation test passed');
        } catch (error) {
            console.error('✗ State validation test failed:', error);
            this.testResults.push({ test: 'State Validation', passed: false, error: error.message });
        }
    }

    testStateSynchronization() {
        console.log('Testing state synchronization...');
        
        try {
            // Test synchronization method
            this.assert(
                typeof this.uiStateManager.synchronizeState === 'function',
                'synchronizeState method should exist'
            );
            
            // Test UI element update method
            this.assert(
                typeof this.uiStateManager.updateUIElements === 'function',
                'updateUIElements method should exist'
            );
            
            // Test integration methods
            this.assert(
                typeof this.uiStateManager.integrateWithAuthManager === 'function',
                'integrateWithAuthManager method should exist'
            );
            
            this.assert(
                typeof this.uiStateManager.integrateWithNavigationController === 'function',
                'integrateWithNavigationController method should exist'
            );
            
            this.assert(
                typeof this.uiStateManager.integrateWithWebSocketClient === 'function',
                'integrateWithWebSocketClient method should exist'
            );
            
            this.assert(
                typeof this.uiStateManager.integrateWithLanguageSwitcher === 'function',
                'integrateWithLanguageSwitcher method should exist'
            );
            
            console.log('✓ State synchronization test passed');
        } catch (error) {
            console.error('✗ State synchronization test failed:', error);
            this.testResults.push({ test: 'State Synchronization', passed: false, error: error.message });
        }
    }

    assert(condition, message) {
        if (!condition) {
            throw new Error(message);
        }
        this.testResults.push({ test: message, passed: true });
    }

    displayResults() {
        console.log('\n=== UI State Management System Test Results ===');
        
        const passedTests = this.testResults.filter(result => result.passed).length;
        const totalTests = this.testResults.length;
        
        console.log(`Passed: ${passedTests}/${totalTests} tests`);
        
        if (passedTests === totalTests) {
            console.log('🎉 All tests passed! UI State Management System is working correctly.');
        } else {
            console.log('❌ Some tests failed. Check the details above.');
            
            const failedTests = this.testResults.filter(result => !result.passed);
            failedTests.forEach(test => {
                console.error(`Failed: ${test.test} - ${test.error}`);
            });
        }
        
        console.log('=== End Test Results ===\n');
    }

    cleanup() {
        if (this.uiStateManager) {
            this.uiStateManager.cleanup();
        }
    }
}

// Export for use in other modules
window.UIStateTest = UIStateTest;

// Auto-run tests if this script is loaded directly
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Only run tests if explicitly requested (e.g., via URL parameter)
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('test') === 'ui-state') {
            const test = new UIStateTest();
            test.runTests();
        }
    });
} else {
    // DOM is already loaded
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('test') === 'ui-state') {
        const test = new UIStateTest();
        test.runTests();
    }
}