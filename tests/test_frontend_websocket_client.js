/**
 * Unit Tests for WebSocket Client
 * Tests WebSocket connection management and real-time features
 */

class WebSocketClientTest {
    constructor() {
        this.testResults = [];
        this.wsClient = null;
        this.originalLocalStorage = null;
        this.mockSocket = null;
    }

    async runAllTests() {
        console.log('🧪 Running WebSocket Client Tests...');
        
        this.testResults = [];
        this.setupMocks();
        
        try {
            // Test 1: Initialization
            await this.testInitialization();
            
            // Test 2: Connection establishment
            await this.testConnectionEstablishment();
            
            // Test 3: Authentication handling
            await this.testAuthenticationHandling();
            
            // Test 4: Event handling
            await this.testEventHandling();
            
            // Test 5: Message handling
            await this.testMessageHandling();
            
            // Test 6: Reconnection logic
            await this.testReconnectionLogic();
            
            // Test 7: Connection quality monitoring
            await this.testConnectionQualityMonitoring();
            
            // Test 8: Notification handling
            await this.testNotificationHandling();
            
            // Test 9: Error handling
            await this.testErrorHandling();
            
            // Test 10: Cleanup and disconnection
            await this.testCleanupAndDisconnection();
            
        } finally {
            this.cleanup();
        }
        
        // Display results
        this.displayResults();
        
        return this.testResults;
    }

    setupMocks() {
        // Mock localStorage
        this.originalLocalStorage = global.localStorage;
        global.localStorage = {
            getItem: jest.fn().mockReturnValue('test_access_token'),
            setItem: jest.fn(),
            removeItem: jest.fn(),
            clear: jest.fn()
        };
        
        // Mock Socket.IO
        this.mockSocket = {
            connect: jest.fn(),
            disconnect: jest.fn(),
            emit: jest.fn(),
            on: jest.fn(),
            connected: false,
            id: 'test-socket-id'
        };
        
        global.io = jest.fn().mockReturnValue(this.mockSocket);
        
        // Mock Notification API
        global.Notification = class MockNotification {
            constructor(title, options) {
                this.title = title;
                this.options = options;
                MockNotification.instances.push(this);
            }
            
            close() {
                this.closed = true;
            }
            
            static requestPermission() {
                return Promise.resolve('granted');
            }
            
            static permission = 'granted';
            static instances = [];
        };
        
        // Mock DOM elements
        document.body.innerHTML = `
            <div id="ws-status" style="display: none;">
                <span class="ws-status-message"></span>
            </div>
        `;
        
        // Mock window.errorHandler
        window.errorHandler = {
            handleJavaScriptError: jest.fn(),
            handleNetworkError: jest.fn()
        };
        
        // Mock custom events
        global.CustomEvent = class MockCustomEvent {
            constructor(type, options) {
                this.type = type;
                this.detail = options?.detail || {};
            }
        };
        
        // Mock document.dispatchEvent
        document.dispatchEvent = jest.fn();
    }

    async testInitialization() {
        console.log('🔍 Testing WebSocket Client initialization...');
        
        try {
            // Test initialization without Socket.IO
            delete global.io;
            
            this.wsClient = new WebSocketClient();
            
            this.assert(
                this.wsClient.socket === null,
                'Should not initialize socket when Socket.IO is not available'
            );
            
            this.assert(
                this.wsClient.isConnected === false,
                'Should not be connected initially'
            );
            
            // Restore Socket.IO and test proper initialization
            global.io = jest.fn().mockReturnValue(this.mockSocket);
            
            this.wsClient = new WebSocketClient();
            
            this.assert(
                this.wsClient.reconnectAttempts === 0,
                'Should initialize with zero reconnect attempts'
            );
            
            this.assert(
                this.wsClient.maxReconnectAttempts === 5,
                'Should have default max reconnect attempts'
            );
            
            this.assert(
                this.wsClient.connectionQuality === 'unknown',
                'Should initialize with unknown connection quality'
            );
            
            this.assert(
                Array.isArray(this.wsClient.pingTimes),
                'Should initialize ping times array'
            );
            
            this.addResult('Initialization', 'PASS', 'WebSocket Client initialized correctly');
        } catch (error) {
            this.addResult('Initialization', 'FAIL', error.message);
        }
    }

    async testConnectionEstablishment() {
        console.log('🔌 Testing connection establishment...');
        
        try {
            this.wsClient = new WebSocketClient();
            
            // Test connection with token
            global.localStorage.getItem.mockReturnValue('test_token');
            
            this.wsClient.connect();
            
            // Verify Socket.IO was called with correct options
            this.assert(
                global.io.mock.calls.length > 0,
                'Should call Socket.IO constructor'
            );
            
            const ioOptions = global.io.mock.calls[0][0];
            this.assert(
                ioOptions.auth.token === 'test_token',
                'Should pass authentication token'
            );
            
            this.assert(
                ioOptions.transports.includes('websocket'),
                'Should include websocket transport'
            );
            
            this.assert(
                ioOptions.autoConnect === false,
                'Should not auto-connect'
            );
            
            // Verify socket.connect was called
            this.assert(
                this.mockSocket.connect.mock.calls.length > 0,
                'Should call socket.connect()'
            );
            
            // Test connection without token
            global.localStorage.getItem.mockReturnValue(null);
            
            const wsClientNoToken = new WebSocketClient();
            
            // Should not attempt connection without token
            this.assert(
                wsClientNoToken.socket === null,
                'Should not create socket without token'
            );
            
            this.addResult('Connection Establishment', 'PASS', 'Connection establishment works correctly');
        } catch (error) {
            this.addResult('Connection Establishment', 'FAIL', error.message);
        }
    }

    async testAuthenticationHandling() {
        console.log('🔐 Testing authentication handling...');
        
        try {
            this.wsClient = new WebSocketClient();
            
            // Test event handler setup
            this.wsClient.setupEventHandlers();
            
            // Verify authentication-related event handlers were registered
            const onCalls = this.mockSocket.on.mock.calls;
            
            const connectHandler = onCalls.find(call => call[0] === 'connect');
            this.assert(
                connectHandler !== undefined,
                'Should register connect event handler'
            );
            
            const connectedHandler = onCalls.find(call => call[0] === 'connected');
            this.assert(
                connectedHandler !== undefined,
                'Should register connected event handler'
            );
            
            const connectErrorHandler = onCalls.find(call => call[0] === 'connect_error');
            this.assert(
                connectErrorHandler !== undefined,
                'Should register connect_error event handler'
            );
            
            // Test successful connection
            const connectCallback = connectHandler[1];
            connectCallback();
            
            this.assert(
                this.wsClient.isConnected === true,
                'Should set connected state on successful connection'
            );
            
            this.assert(
                this.wsClient.reconnectAttempts === 0,
                'Should reset reconnect attempts on successful connection'
            );
            
            // Test connection error
            const connectErrorCallback = connectErrorHandler[1];
            connectErrorCallback({ message: 'Authentication failed' });
            
            // Should emit custom event
            this.assert(
                document.dispatchEvent.mock.calls.some(call => 
                    call[0].type === 'websocket:connection_error'
                ),
                'Should emit connection error event'
            );
            
            this.addResult('Authentication Handling', 'PASS', 'Authentication handling works correctly');
        } catch (error) {
            this.addResult('Authentication Handling', 'FAIL', error.message);
        }
    }

    async testEventHandling() {
        console.log('📡 Testing event handling...');
        
        try {
            this.wsClient = new WebSocketClient();
            this.wsClient.setupEventHandlers();
            
            // Test disconnect event handling
            const disconnectHandler = this.mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')[1];
            
            disconnectHandler('io server disconnect');
            
            this.assert(
                this.wsClient.isConnected === false,
                'Should set disconnected state on disconnect'
            );
            
            // Should emit custom event
            this.assert(
                document.dispatchEvent.mock.calls.some(call => 
                    call[0].type === 'websocket:disconnected'
                ),
                'Should emit disconnected event'
            );
            
            // Test custom event emission
            this.wsClient.emitCustomEvent('test:event', { data: 'test' });
            
            const customEventCall = document.dispatchEvent.mock.calls.find(call => 
                call[0].type === 'test:event'
            );
            
            this.assert(
                customEventCall !== undefined,
                'Should emit custom events'
            );
            
            this.assert(
                customEventCall[0].detail.data === 'test',
                'Should include correct data in custom events'
            );
            
            // Test event listener registration
            let eventReceived = false;
            const testHandler = () => { eventReceived = true; };
            
            this.wsClient.on('test:event', testHandler);
            
            // Simulate event
            const testEvent = new CustomEvent('test:event');
            document.dispatchEvent(testEvent);
            
            this.addResult('Event Handling', 'PASS', 'Event handling works correctly');
        } catch (error) {
            this.addResult('Event Handling', 'FAIL', error.message);
        }
    }

    async testMessageHandling() {
        console.log('💬 Testing message handling...');
        
        try {
            this.wsClient = new WebSocketClient();
            this.wsClient.setupEventHandlers();
            
            // Test new message handling
            const newMessageHandler = this.mockSocket.on.mock.calls.find(call => call[0] === 'new_message')[1];
            
            const testMessage = {
                conversation_id: 'conv123',
                message: {
                    id: 'msg456',
                    content: 'Test message'
                }
            };
            
            newMessageHandler(testMessage);
            
            // Should emit custom event
            const messageEvent = document.dispatchEvent.mock.calls.find(call => 
                call[0].type === 'message:new'
            );
            
            this.assert(
                messageEvent !== undefined,
                'Should emit message:new event'
            );
            
            this.assert(
                messageEvent[0].detail.message.content === 'Test message',
                'Should include message data in event'
            );
            
            // Test conversation methods
            this.wsClient.isConnected = true;
            this.wsClient.joinConversation('conv123');
            
            this.assert(
                this.wsClient.currentConversation === 'conv123',
                'Should set current conversation'
            );
            
            this.assert(
                this.mockSocket.emit.mock.calls.some(call => 
                    call[0] === 'join_conversation' && call[1].conversation_id === 'conv123'
                ),
                'Should emit join_conversation event'
            );
            
            // Test typing indicators
            this.wsClient.startTyping('conv123');
            
            this.assert(
                this.mockSocket.emit.mock.calls.some(call => 
                    call[0] === 'typing_start' && call[1].conversation_id === 'conv123'
                ),
                'Should emit typing_start event'
            );
            
            this.wsClient.stopTyping('conv123');
            
            this.assert(
                this.mockSocket.emit.mock.calls.some(call => 
                    call[0] === 'typing_stop' && call[1].conversation_id === 'conv123'
                ),
                'Should emit typing_stop event'
            );
            
            this.addResult('Message Handling', 'PASS', 'Message handling works correctly');
        } catch (error) {
            this.addResult('Message Handling', 'FAIL', error.message);
        }
    }

    async testReconnectionLogic() {
        console.log('🔄 Testing reconnection logic...');
        
        try {
            this.wsClient = new WebSocketClient();
            
            // Test reconnection scheduling
            this.wsClient.reconnectAttempts = 0;
            this.wsClient.scheduleReconnect();
            
            this.assert(
                this.wsClient.reconnectAttempts === 1,
                'Should increment reconnect attempts'
            );
            
            // Test max reconnection attempts
            this.wsClient.reconnectAttempts = this.wsClient.maxReconnectAttempts;
            this.wsClient.scheduleReconnect();
            
            // Should emit max attempts event
            this.assert(
                document.dispatchEvent.mock.calls.some(call => 
                    call[0].type === 'websocket:max_reconnect_attempts'
                ),
                'Should emit max reconnect attempts event'
            );
            
            // Test manual reconnection
            this.wsClient.reconnectAttempts = 3;
            this.wsClient.reconnectManually();
            
            this.assert(
                this.wsClient.reconnectAttempts === 0,
                'Should reset reconnect attempts on manual reconnection'
            );
            
            // Test stale connection handling
            this.wsClient.isConnected = true;
            this.wsClient.handleStaleConnection();
            
            this.assert(
                this.mockSocket.disconnect.mock.calls.length > 0,
                'Should disconnect stale connection'
            );
            
            this.assert(
                this.wsClient.isConnected === false,
                'Should set disconnected state for stale connection'
            );
            
            this.addResult('Reconnection Logic', 'PASS', 'Reconnection logic works correctly');
        } catch (error) {
            this.addResult('Reconnection Logic', 'FAIL', error.message);
        }
    }

    async testConnectionQualityMonitoring() {
        console.log('📊 Testing connection quality monitoring...');
        
        try {
            this.wsClient = new WebSocketClient();
            this.wsClient.setupEventHandlers();
            
            // Test ping/pong handling
            const pongHandler = this.mockSocket.on.mock.calls.find(call => call[0] === 'pong')[1];
            
            // Simulate ping
            this.wsClient.lastPingTime = Date.now() - 50; // 50ms ago
            pongHandler();
            
            this.assert(
                this.wsClient.pingTimes.length > 0,
                'Should record ping times'
            );
            
            this.assert(
                this.wsClient.pingTimes[0] >= 50,
                'Should calculate ping time correctly'
            );
            
            // Test connection quality calculation
            this.wsClient.pingTimes = [50, 60, 70]; // Excellent quality
            this.wsClient.updateConnectionQuality();
            
            this.assert(
                this.wsClient.connectionQuality === 'excellent',
                'Should calculate excellent connection quality'
            );
            
            this.wsClient.pingTimes = [200, 250, 300]; // Good quality
            this.wsClient.updateConnectionQuality();
            
            this.assert(
                this.wsClient.connectionQuality === 'good',
                'Should calculate good connection quality'
            );
            
            this.wsClient.pingTimes = [500, 600, 700]; // Fair quality
            this.wsClient.updateConnectionQuality();
            
            this.assert(
                this.wsClient.connectionQuality === 'fair',
                'Should calculate fair connection quality'
            );
            
            this.wsClient.pingTimes = [1500, 2000, 2500]; // Poor quality
            this.wsClient.updateConnectionQuality();
            
            this.assert(
                this.wsClient.connectionQuality === 'poor',
                'Should calculate poor connection quality'
            );
            
            // Test connection statistics
            const stats = this.wsClient.getConnectionStats();
            
            this.assert(
                typeof stats === 'object',
                'Should return connection statistics object'
            );
            
            this.assert(
                typeof stats.isConnected === 'boolean',
                'Should include connection status'
            );
            
            this.assert(
                typeof stats.connectionQuality === 'string',
                'Should include connection quality'
            );
            
            this.assert(
                typeof stats.averagePing === 'number',
                'Should include average ping'
            );
            
            this.addResult('Connection Quality Monitoring', 'PASS', 'Connection quality monitoring works correctly');
        } catch (error) {
            this.addResult('Connection Quality Monitoring', 'FAIL', error.message);
        }
    }

    async testNotificationHandling() {
        console.log('🔔 Testing notification handling...');
        
        try {
            this.wsClient = new WebSocketClient();
            this.wsClient.setupEventHandlers();
            
            // Test notification event handling
            const notificationHandler = this.mockSocket.on.mock.calls.find(call => call[0] === 'notification')[1];
            
            const testNotification = {
                id: 'notif123',
                title: 'Test Notification',
                message: 'This is a test notification',
                icon: '/test-icon.png'
            };
            
            notificationHandler(testNotification);
            
            // Should emit custom event
            const notificationEvent = document.dispatchEvent.mock.calls.find(call => 
                call[0].type === 'notification:received'
            );
            
            this.assert(
                notificationEvent !== undefined,
                'Should emit notification:received event'
            );
            
            this.assert(
                notificationEvent[0].detail.title === 'Test Notification',
                'Should include notification data in event'
            );
            
            // Test browser notification
            const browserNotification = await this.wsClient.showNotification('Test Title', {
                body: 'Test body',
                icon: '/test.png'
            });
            
            this.assert(
                Notification.instances.length > 0,
                'Should create browser notification'
            );
            
            const createdNotification = Notification.instances[Notification.instances.length - 1];
            this.assert(
                createdNotification.title === 'Test Title',
                'Should set correct notification title'
            );
            
            // Test tenant notification handling
            const tenantNotificationHandler = this.mockSocket.on.mock.calls.find(call => call[0] === 'tenant_notification')[1];
            
            tenantNotificationHandler({
                id: 'tenant123',
                title: 'System Update',
                message: 'System will be updated'
            });
            
            // Should emit custom event
            const tenantEvent = document.dispatchEvent.mock.calls.find(call => 
                call[0].type === 'notification:tenant'
            );
            
            this.assert(
                tenantEvent !== undefined,
                'Should emit tenant notification event'
            );
            
            // Test system alert handling
            const systemAlertHandler = this.mockSocket.on.mock.calls.find(call => call[0] === 'system_alert')[1];
            
            systemAlertHandler({
                id: 'alert123',
                title: 'System Alert',
                message: 'Critical system alert',
                urgent: true
            });
            
            // Should emit custom event
            const alertEvent = document.dispatchEvent.mock.calls.find(call => 
                call[0].type === 'alert:system'
            );
            
            this.assert(
                alertEvent !== undefined,
                'Should emit system alert event'
            );
            
            this.addResult('Notification Handling', 'PASS', 'Notification handling works correctly');
        } catch (error) {
            this.addResult('Notification Handling', 'FAIL', error.message);
        }
    }

    async testErrorHandling() {
        console.log('⚠️ Testing error handling...');
        
        try {
            this.wsClient = new WebSocketClient();
            
            // Test initialization error handling
            global.io = () => {
                throw new Error('Socket.IO initialization failed');
            };
            
            // Should not throw error
            this.wsClient.connect();
            
            // Should call error handler
            this.assert(
                window.errorHandler.handleJavaScriptError.mock.calls.length > 0,
                'Should call error handler for initialization errors'
            );
            
            // Restore Socket.IO
            global.io = jest.fn().mockReturnValue(this.mockSocket);
            
            // Test connection without token
            global.localStorage.getItem.mockReturnValue(null);
            
            const wsClientNoToken = new WebSocketClient();
            
            // Should not attempt connection
            this.assert(
                wsClientNoToken.socket === null,
                'Should handle missing token gracefully'
            );
            
            // Test notification permission denied
            Notification.permission = 'denied';
            
            const notification = await this.wsClient.showNotification('Test');
            
            this.assert(
                notification === undefined,
                'Should handle denied notification permission'
            );
            
            // Restore notification permission
            Notification.permission = 'granted';
            
            // Test connection status display with missing element
            document.body.innerHTML = '';
            
            // Should not throw error
            this.wsClient.showConnectionStatus('connected', 'Connected');
            
            this.addResult('Error Handling', 'PASS', 'Error handling works correctly');
        } catch (error) {
            this.addResult('Error Handling', 'FAIL', error.message);
        }
    }

    async testCleanupAndDisconnection() {
        console.log('🧹 Testing cleanup and disconnection...');
        
        try {
            this.wsClient = new WebSocketClient();
            this.wsClient.isConnected = true;
            this.wsClient.currentConversation = 'conv123';
            
            // Set up some timers
            this.wsClient.typingTimer = setTimeout(() => {}, 1000);
            this.wsClient.pingInterval = setInterval(() => {}, 1000);
            this.wsClient.pongTimeout = setTimeout(() => {}, 1000);
            
            // Test disconnection
            this.wsClient.disconnect();
            
            this.assert(
                this.mockSocket.disconnect.mock.calls.length > 0,
                'Should call socket.disconnect()'
            );
            
            this.assert(
                this.wsClient.socket === null,
                'Should clear socket reference'
            );
            
            this.assert(
                this.wsClient.isConnected === false,
                'Should set disconnected state'
            );
            
            this.assert(
                this.wsClient.currentConversation === null,
                'Should clear current conversation'
            );
            
            this.assert(
                this.wsClient.typingTimer === null,
                'Should clear typing timer'
            );
            
            this.assert(
                this.wsClient.pingInterval === null,
                'Should clear ping interval'
            );
            
            this.assert(
                this.wsClient.pongTimeout === null,
                'Should clear pong timeout'
            );
            
            // Test connection status update
            const statusElement = document.getElementById('ws-status');
            if (statusElement) {
                this.assert(
                    statusElement.classList.contains('disconnected'),
                    'Should update connection status display'
                );
            }
            
            this.addResult('Cleanup and Disconnection', 'PASS', 'Cleanup and disconnection work correctly');
        } catch (error) {
            this.addResult('Cleanup and Disconnection', 'FAIL', error.message);
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
        console.log('\n📊 WebSocket Client Test Results:');
        console.log('==================================');
        
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
            console.log('🎉 All WebSocket Client tests passed!');
        } else {
            console.log('⚠️  Some tests failed. Check the details above.');
        }
    }

    cleanup() {
        // Restore original functions
        if (this.originalLocalStorage) {
            global.localStorage = this.originalLocalStorage;
        }
        
        // Clean up WebSocket client
        if (this.wsClient) {
            this.wsClient.disconnect();
        }
        
        // Clear DOM
        document.body.innerHTML = '';
        
        // Clear notification instances
        if (Notification.instances) {
            Notification.instances = [];
        }
        
        // Clear mocks
        delete global.io;
        delete window.errorHandler;
    }

    // Quick test function for console use
    static async quickTest() {
        const tester = new WebSocketClientTest();
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
window.WebSocketClientTest = WebSocketClientTest;

// Add console helper
window.testWebSocketClient = () => WebSocketClientTest.quickTest();