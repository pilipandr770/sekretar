/**
 * WebSocket client for real-time features
 */
class WebSocketClient {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.currentConversation = null;
        this.typingTimer = null;
        this.typingTimeout = 3000; // 3 seconds
        
        // Connection quality monitoring
        this.connectionQuality = 'unknown';
        this.pingTimes = [];
        this.maxPingHistory = 10;
        this.lastPingTime = null;
        this.pingInterval = null;
        this.pongTimeout = null;
        
        // Event handlers
        this.messageHandlers = new Map();
        this.notificationHandlers = [];
        
        this.init();
    }
    
    init() {
        // Check browser compatibility first
        this.checkBrowserCompatibility();
        
        // Only initialize if Socket.IO is available
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not loaded, real-time features disabled');
            this.initWebSocketFallback();
            return;
        }
        
        this.connect();
    }
    
    checkBrowserCompatibility() {
        // Get browser info from compatibility manager if available
        if (window.browserCompatibilityManager) {
            this.browserInfo = window.browserCompatibilityManager.getBrowserInfo();
        } else {
            // Fallback browser detection
            this.browserInfo = this.detectBrowser();
        }
        
        console.log('🌐 WebSocket client browser:', this.browserInfo.name, this.browserInfo.version);
        
        // Apply browser-specific configurations
        this.applyBrowserSpecificConfig();
    }
    
    detectBrowser() {
        const userAgent = navigator.userAgent;
        let browser = 'Unknown';
        let version = 'Unknown';
        
        if (userAgent.includes('Chrome')) {
            browser = 'Chrome';
            const match = userAgent.match(/Chrome\/(\d+)/);
            version = match ? match[1] : 'Unknown';
        } else if (userAgent.includes('Firefox')) {
            browser = 'Firefox';
            const match = userAgent.match(/Firefox\/(\d+)/);
            version = match ? match[1] : 'Unknown';
        } else if (userAgent.includes('Safari') && !userAgent.includes('Chrome')) {
            browser = 'Safari';
            const match = userAgent.match(/Version\/(\d+)/);
            version = match ? match[1] : 'Unknown';
        } else if (userAgent.includes('Edg')) {
            browser = 'Edge';
            const match = userAgent.match(/Edg\/(\d+)/);
            version = match ? match[1] : 'Unknown';
        }
        
        return { name: browser, version: version, majorVersion: parseInt(version) };
    }
    
    applyBrowserSpecificConfig() {
        if (!this.browserInfo) return;
        
        switch (this.browserInfo.name) {
            case 'Safari':
                this.applySafariConfig();
                break;
            case 'Firefox':
                this.applyFirefoxConfig();
                break;
            case 'Edge':
                this.applyEdgeConfig();
                break;
            case 'Chrome':
                this.applyChromeConfig();
                break;
        }
    }
    
    applySafariConfig() {
        console.log('🍎 Applying Safari WebSocket configuration...');
        
        // Safari-specific timeout adjustments
        this.connectionTimeout = 15000; // Longer timeout for Safari
        this.maxReconnectAttempts = 3; // Fewer attempts for Safari
        
        // Safari WebSocket connection delay
        this.connectionDelay = 500;
    }
    
    applyFirefoxConfig() {
        console.log('🦊 Applying Firefox WebSocket configuration...');
        
        // Firefox-specific configurations
        this.connectionTimeout = 12000;
        this.maxReconnectAttempts = 5;
        
        // Firefox connection optimization
        this.connectionDelay = 200;
    }
    
    applyEdgeConfig() {
        console.log('🔷 Applying Edge WebSocket configuration...');
        
        // Edge-specific configurations
        this.connectionTimeout = 10000;
        this.maxReconnectAttempts = 4;
        
        // Edge connection settings
        this.connectionDelay = 100;
    }
    
    applyChromeConfig() {
        console.log('🟢 Applying Chrome WebSocket configuration...');
        
        // Chrome-specific optimizations
        this.connectionTimeout = 8000;
        this.maxReconnectAttempts = 6;
        
        // Chrome connection settings
        this.connectionDelay = 0; // No delay needed for Chrome
    }
    
    initWebSocketFallback() {
        console.log('🔄 Initializing WebSocket fallback without Socket.IO...');
        
        // Try native WebSocket as fallback
        if (typeof WebSocket !== 'undefined') {
            this.useNativeWebSocket = true;
            this.connectNativeWebSocket();
        } else {
            console.error('❌ No WebSocket support available');
            this.emitCustomEvent('websocket:not_supported');
        }
    }
    
    connectNativeWebSocket() {
        console.log('🔌 Connecting with native WebSocket...');
        
        const token = localStorage.getItem('access_token');
        if (!token) {
            console.debug('No access token available for WebSocket connection');
            return;
        }
        
        try {
            // Determine WebSocket URL
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${location.host}/ws?token=${encodeURIComponent(token)}`;
            
            this.nativeSocket = new WebSocket(wsUrl);
            this.setupNativeWebSocketHandlers();
            
        } catch (error) {
            console.error('Failed to create native WebSocket:', error);
            this.emitCustomEvent('websocket:initialization_failed', { error: error.message });
        }
    }
    
    setupNativeWebSocketHandlers() {
        if (!this.nativeSocket) return;
        
        this.nativeSocket.onopen = () => {
            console.log('Native WebSocket connected');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.emitCustomEvent('websocket:connected');
        };
        
        this.nativeSocket.onclose = (event) => {
            console.log('Native WebSocket disconnected:', event.code, event.reason);
            this.isConnected = false;
            this.emitCustomEvent('websocket:disconnected', { code: event.code, reason: event.reason });
            
            if (event.code !== 1000) { // Not a normal closure
                this.scheduleReconnect();
            }
        };
        
        this.nativeSocket.onerror = (error) => {
            console.error('Native WebSocket error:', error);
            this.emitCustomEvent('websocket:connection_error', { error: 'Native WebSocket error' });
        };
        
        this.nativeSocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleNativeWebSocketMessage(data);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };
    }
    
    handleNativeWebSocketMessage(data) {
        // Handle different message types
        switch (data.type) {
            case 'new_message':
                this.handleNewMessage(data.payload);
                break;
            case 'notification':
                this.handleNotification(data.payload);
                break;
            case 'system_alert':
                this.handleSystemAlert(data.payload);
                break;
            default:
                console.log('Unknown native WebSocket message type:', data.type);
        }
    }
    
    connect() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            console.debug('No access token available for WebSocket connection');
            return;
        }
        
        // Apply connection delay if configured
        if (this.connectionDelay > 0) {
            console.log(`⏱️ Applying ${this.connectionDelay}ms connection delay for ${this.browserInfo?.name}`);
            setTimeout(() => this.performConnection(token), this.connectionDelay);
        } else {
            this.performConnection(token);
        }
    }
    
    performConnection(token) {
        // Emit connecting event
        this.emitCustomEvent('websocket:connecting');
        
        try {
            // Browser-specific Socket.IO configuration
            const socketConfig = this.getBrowserSpecificSocketConfig();
            
            this.socket = io({
                auth: {
                    token: token
                },
                ...socketConfig
            });
            
            this.setupEventHandlers();
            
            // Only connect if we have a valid token
            this.socket.connect();
            
        } catch (error) {
            console.error('Failed to initialize WebSocket connection:', error);
            this.emitCustomEvent('websocket:initialization_failed', { error: error.message });
            
            // Try native WebSocket fallback
            if (!this.useNativeWebSocket) {
                console.log('🔄 Attempting native WebSocket fallback...');
                this.initWebSocketFallback();
            }
            
            // Use error handler for WebSocket initialization errors
            if (window.errorHandler) {
                window.errorHandler.handleJavaScriptError({
                    message: `WebSocket initialization failed: ${error.message}`,
                    filename: 'websocket-client.js',
                    error: error,
                    type: 'websocket'
                });
            }
        }
    }
    
    getBrowserSpecificSocketConfig() {
        const baseConfig = {
            transports: ['websocket', 'polling'],
            autoConnect: false,
            path: '/socket.io/',
            timeout: this.connectionTimeout || 10000,
            forceNew: true
        };
        
        if (!this.browserInfo) return baseConfig;
        
        switch (this.browserInfo.name) {
            case 'Safari':
                return {
                    ...baseConfig,
                    transports: ['polling', 'websocket'], // Prefer polling for Safari
                    timeout: 15000,
                    upgrade: true,
                    rememberUpgrade: false // Don't remember upgrade for Safari
                };
                
            case 'Firefox':
                return {
                    ...baseConfig,
                    timeout: 12000,
                    pingTimeout: 60000,
                    pingInterval: 25000
                };
                
            case 'Edge':
                return {
                    ...baseConfig,
                    timeout: 10000,
                    transports: ['websocket', 'polling'],
                    upgrade: true
                };
                
            case 'Chrome':
                return {
                    ...baseConfig,
                    timeout: 8000,
                    transports: ['websocket', 'polling'],
                    upgrade: true,
                    rememberUpgrade: true
                };
                
            default:
                return baseConfig;
        }
    }
    
    setupEventHandlers() {
        if (!this.socket) return;
        
        this.socket.on('connect', () => {
            console.log('WebSocket connected');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.reconnectDelay = 1000;
            
            // Show connection status
            this.showConnectionStatus('connected', 'Real-time features enabled');
            
            // Emit custom event for UI updates
            this.emitCustomEvent('websocket:connected');
        });
        
        this.socket.on('disconnect', (reason) => {
            console.log('WebSocket disconnected:', reason);
            this.isConnected = false;
            
            // Show disconnection status
            let statusMessage = 'Connection lost';
            if (reason === 'io server disconnect') {
                statusMessage = 'Server disconnected - trying to reconnect';
            } else if (reason === 'io client disconnect') {
                statusMessage = 'Disconnected';
            } else if (reason === 'ping timeout') {
                statusMessage = 'Connection timeout - reconnecting';
            } else if (reason === 'transport close') {
                statusMessage = 'Connection closed - reconnecting';
            }
            
            this.showConnectionStatus('disconnected', statusMessage);
            
            // Emit custom event for UI updates
            this.emitCustomEvent('websocket:disconnected', { reason });
            
            // Attempt to reconnect if not a manual disconnect
            if (reason !== 'io client disconnect') {
                this.scheduleReconnect();
            }
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('WebSocket connection error:', error);
            
            // Log detailed error information
            if (error.description) {
                console.error('Error description:', error.description);
            }
            if (error.context) {
                console.error('Error context:', error.context);
            }
            if (error.type) {
                console.error('Error type:', error.type);
            }
            
            // Emit custom event with error details
            this.emitCustomEvent('websocket:connection_error', { 
                error: error.message || error.description || 'Unknown connection error',
                type: error.type,
                context: error.context
            });
            
            this.scheduleReconnect();
        });
        
        this.socket.on('connected', (data) => {
            console.log('WebSocket authentication successful:', data);
        });
        
        // Message events
        this.socket.on('new_message', (data) => {
            this.handleNewMessage(data);
        });
        
        this.socket.on('message_updated', (data) => {
            this.handleMessageUpdate(data);
        });
        
        this.socket.on('conversation_updated', (data) => {
            this.handleConversationUpdate(data);
        });
        
        // Typing indicators
        this.socket.on('user_typing', (data) => {
            this.handleTypingIndicator(data);
        });
        
        // Notifications
        this.socket.on('notification', (data) => {
            this.handleNotification(data);
        });
        
        this.socket.on('tenant_notification', (data) => {
            this.handleTenantNotification(data);
        });
        
        // Lead updates
        this.socket.on('lead_updated', (data) => {
            this.handleLeadUpdate(data);
        });
        
        // Appointment updates
        this.socket.on('appointment_updated', (data) => {
            this.handleAppointmentUpdate(data);
        });
        
        // System alerts
        this.socket.on('system_alert', (data) => {
            this.handleSystemAlert(data);
        });
        
        // Ping/pong for keepalive
        this.socket.on('pong', () => {
            // Connection is alive - clear the pong timeout
            if (this.pongTimeout) {
                clearTimeout(this.pongTimeout);
                this.pongTimeout = null;
            }
            
            // Calculate ping time and update connection quality
            if (this.lastPingTime) {
                const pingTime = Date.now() - this.lastPingTime;
                console.debug(`WebSocket ping: ${pingTime}ms`);
                
                // Store ping time for quality calculation
                this.pingTimes.push(pingTime);
                if (this.pingTimes.length > this.maxPingHistory) {
                    this.pingTimes.shift();
                }
                
                // Update connection quality
                this.updateConnectionQuality();
            }
        });
        
        // Start ping interval
        this.startPingInterval();
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this.emitCustomEvent('websocket:max_reconnect_attempts');
            this.showConnectionStatus('failed', 'Connection failed - please refresh the page');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000); // Cap at 30 seconds
        
        console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
        
        // Emit reconnecting event
        this.emitCustomEvent('websocket:reconnecting', { attempt: this.reconnectAttempts });
        
        this.showConnectionStatus('reconnecting', `Reconnecting in ${Math.ceil(delay/1000)}s (attempt ${this.reconnectAttempts})`);
        
        // Show countdown
        this.showReconnectCountdown(delay);
        
        setTimeout(() => {
            if (!this.isConnected) {
                this.showConnectionStatus('connecting', 'Attempting to reconnect...');
                this.connect();
            }
        }, delay);
    }
    
    showReconnectCountdown(totalDelay) {
        const startTime = Date.now();
        const updateInterval = 1000; // Update every second
        
        const updateCountdown = () => {
            const elapsed = Date.now() - startTime;
            const remaining = Math.max(0, totalDelay - elapsed);
            const secondsRemaining = Math.ceil(remaining / 1000);
            
            if (remaining > 0 && !this.isConnected) {
                this.showConnectionStatus('reconnecting', `Reconnecting in ${secondsRemaining}s (attempt ${this.reconnectAttempts})`);
                setTimeout(updateCountdown, updateInterval);
            }
        };
        
        updateCountdown();
    }
    
    showConnectionStatus(status, message) {
        // Emit custom event for UI updates
        this.emitCustomEvent('websocket:status_change', { status, message });
        
        // Also update any existing status indicators
        const statusElement = document.getElementById('ws-status');
        if (statusElement) {
            const messageElement = statusElement.querySelector('.ws-status-message');
            if (messageElement) {
                statusElement.className = `ws-status ${status}`;
                messageElement.textContent = message;
                statusElement.style.display = 'block';
                
                // Auto-hide success messages
                if (status === 'connected') {
                    setTimeout(() => {
                        if (statusElement.classList.contains('connected')) {
                            statusElement.style.display = 'none';
                        }
                    }, 3000);
                }
            }
        }
    }
    
    startPingInterval() {
        // Send ping every 30 seconds to keep connection alive
        this.pingInterval = setInterval(() => {
            if (this.isConnected && this.socket) {
                this.lastPingTime = Date.now();
                this.socket.emit('ping');
                
                // Set timeout to detect if pong is not received
                this.pongTimeout = setTimeout(() => {
                    console.warn('Pong not received within timeout, connection may be stale');
                    this.handleStaleConnection();
                }, 10000); // 10 second timeout for pong response
            }
        }, 30000);
    }
    
    handleStaleConnection() {
        console.log('Handling stale connection');
        if (this.socket && this.isConnected) {
            // Force disconnect and reconnect
            this.socket.disconnect();
            this.isConnected = false;
            this.showConnectionStatus('reconnecting', 'Connection appears stale - reconnecting');
            this.scheduleReconnect();
        }
    }
    
    // Conversation methods
    joinConversation(conversationId) {
        if (!this.isConnected || !this.socket) {
            console.warn('Cannot join conversation: WebSocket not connected');
            return;
        }
        
        // Leave current conversation if any
        if (this.currentConversation && this.currentConversation !== conversationId) {
            this.leaveConversation(this.currentConversation);
        }
        
        this.currentConversation = conversationId;
        this.socket.emit('join_conversation', { conversation_id: conversationId });
    }
    
    leaveConversation(conversationId) {
        if (!this.isConnected || !this.socket) {
            return;
        }
        
        this.socket.emit('leave_conversation', { conversation_id: conversationId });
        
        if (this.currentConversation === conversationId) {
            this.currentConversation = null;
        }
    }
    
    // Typing indicators
    startTyping(conversationId) {
        if (!this.isConnected || !this.socket) {
            return;
        }
        
        this.socket.emit('typing_start', { conversation_id: conversationId });
        
        // Clear existing timer
        if (this.typingTimer) {
            clearTimeout(this.typingTimer);
        }
        
        // Auto-stop typing after timeout
        this.typingTimer = setTimeout(() => {
            this.stopTyping(conversationId);
        }, this.typingTimeout);
    }
    
    stopTyping(conversationId) {
        if (!this.isConnected || !this.socket) {
            return;
        }
        
        this.socket.emit('typing_stop', { conversation_id: conversationId });
        
        if (this.typingTimer) {
            clearTimeout(this.typingTimer);
            this.typingTimer = null;
        }
    }
    
    // Event handlers
    handleNewMessage(data) {
        console.log('New message received:', data);
        this.emitCustomEvent('message:new', data);
        
        // Show notification if not in current conversation
        if (data.conversation_id !== this.currentConversation) {
            this.showNotification('New Message', {
                body: data.message.content,
                icon: '/static/images/message-icon.png',
                tag: `message-${data.message.id}`
            });
        }
    }
    
    handleMessageUpdate(data) {
        console.log('Message updated:', data);
        this.emitCustomEvent('message:updated', data);
    }
    
    handleConversationUpdate(data) {
        console.log('Conversation updated:', data);
        this.emitCustomEvent('conversation:updated', data);
    }
    
    handleTypingIndicator(data) {
        console.log('Typing indicator:', data);
        this.emitCustomEvent('typing:indicator', data);
    }
    
    handleNotification(data) {
        console.log('Notification received:', data);
        this.emitCustomEvent('notification:received', data);
        
        // Show browser notification
        this.showNotification(data.title || 'Notification', {
            body: data.message,
            icon: data.icon || '/static/images/notification-icon.png',
            tag: data.id
        });
    }
    
    handleTenantNotification(data) {
        console.log('Tenant notification received:', data);
        this.emitCustomEvent('notification:tenant', data);
        
        // Show browser notification
        this.showNotification(data.title || 'System Notification', {
            body: data.message,
            icon: '/static/images/system-icon.png',
            tag: `tenant-${data.id}`
        });
    }
    
    handleLeadUpdate(data) {
        console.log('Lead updated:', data);
        this.emitCustomEvent('lead:updated', data);
    }
    
    handleAppointmentUpdate(data) {
        console.log('Appointment updated:', data);
        this.emitCustomEvent('appointment:updated', data);
        
        // Show notification for appointment changes
        this.showNotification('Appointment Update', {
            body: `Appointment "${data.appointment.title}" has been updated`,
            icon: '/static/images/calendar-icon.png',
            tag: `appointment-${data.appointment.id}`
        });
    }
    
    handleSystemAlert(data) {
        console.log('System alert:', data);
        this.emitCustomEvent('alert:system', data);
        
        // Show urgent notification
        this.showNotification(data.title || 'System Alert', {
            body: data.message,
            icon: '/static/images/alert-icon.png',
            tag: `alert-${data.id}`,
            requireInteraction: data.urgent
        });
    }
    
    // Notification methods
    async showNotification(title, options = {}) {
        // Check if notifications are supported and permitted
        if (!('Notification' in window)) {
            console.warn('Browser does not support notifications');
            return;
        }
        
        let permission = Notification.permission;
        
        if (permission === 'default') {
            permission = await Notification.requestPermission();
        }
        
        if (permission === 'granted') {
            const notification = new Notification(title, {
                ...options,
                badge: '/static/images/badge-icon.png'
            });
            
            // Auto-close after 5 seconds unless requireInteraction is true
            if (!options.requireInteraction) {
                setTimeout(() => {
                    notification.close();
                }, 5000);
            }
            
            return notification;
        }
    }
    
    // Custom event system
    emitCustomEvent(eventName, data = {}) {
        const event = new CustomEvent(eventName, { detail: data });
        document.dispatchEvent(event);
    }
    
    // Public API methods
    on(eventName, handler) {
        document.addEventListener(eventName, handler);
    }
    
    off(eventName, handler) {
        document.removeEventListener(eventName, handler);
    }
    
    // Connection status
    isConnectedToWebSocket() {
        return this.isConnected;
    }
    
    // Manual reconnection
    reconnectManually() {
        console.log('Manual reconnection requested');
        this.reconnectAttempts = 0; // Reset attempts
        this.showConnectionStatus('connecting', 'Connecting...');
        
        if (this.socket) {
            this.socket.disconnect();
        }
        
        setTimeout(() => {
            this.connect();
        }, 1000);
    }
    
    // Update connection quality based on ping times
    updateConnectionQuality() {
        if (this.pingTimes.length === 0) {
            this.connectionQuality = 'unknown';
            return;
        }
        
        const avgPing = this.pingTimes.reduce((a, b) => a + b, 0) / this.pingTimes.length;
        
        if (avgPing < 100) {
            this.connectionQuality = 'excellent';
        } else if (avgPing < 300) {
            this.connectionQuality = 'good';
        } else if (avgPing < 1000) {
            this.connectionQuality = 'fair';
        } else {
            this.connectionQuality = 'poor';
        }
        
        // Emit quality change event
        this.emitCustomEvent('websocket:quality_change', {
            quality: this.connectionQuality,
            avgPing: Math.round(avgPing),
            pingTimes: [...this.pingTimes]
        });
    }
    
    // Get connection statistics
    getConnectionStats() {
        const avgPing = this.pingTimes.length > 0 
            ? Math.round(this.pingTimes.reduce((a, b) => a + b, 0) / this.pingTimes.length)
            : null;
            
        return {
            isConnected: this.isConnected,
            reconnectAttempts: this.reconnectAttempts,
            maxReconnectAttempts: this.maxReconnectAttempts,
            currentConversation: this.currentConversation,
            connectionQuality: this.connectionQuality,
            averagePing: avgPing,
            recentPingTimes: [...this.pingTimes]
        };
    }
    
    // Cleanup
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
        this.isConnected = false;
        this.currentConversation = null;
        
        // Clear all timers and intervals
        if (this.typingTimer) {
            clearTimeout(this.typingTimer);
            this.typingTimer = null;
        }
        
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
        
        if (this.pongTimeout) {
            clearTimeout(this.pongTimeout);
            this.pongTimeout = null;
        }
        
        // Clear connection status
        this.showConnectionStatus('disconnected', 'Disconnected');
    }
}

// Global WebSocket client instance
let wsClient = null;

// Initialize WebSocket client when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if user is authenticated
    const token = localStorage.getItem('access_token');
    if (token) {
        wsClient = new WebSocketClient();
        
        // Make it globally available
        window.wsClient = wsClient;
    } else {
        console.debug('WebSocket client not initialized - no authentication token');
    }
});

// Reinitialize when user logs in
document.addEventListener('user:login', () => {
    if (!wsClient) {
        wsClient = new WebSocketClient();
        window.wsClient = wsClient;
    }
});

// Cleanup when user logs out
document.addEventListener('user:logout', () => {
    if (wsClient) {
        wsClient.disconnect();
        wsClient = null;
        window.wsClient = null;
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebSocketClient;
}