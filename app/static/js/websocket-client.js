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
        
        // Event handlers
        this.messageHandlers = new Map();
        this.notificationHandlers = [];
        
        this.init();
    }
    
    init() {
        // Only initialize if Socket.IO is available
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not loaded, real-time features disabled');
            return;
        }
        
        this.connect();
    }
    
    connect() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            console.debug('No access token available for WebSocket connection');
            return;
        }
        
        try {
            this.socket = io({
                auth: {
                    token: token
                },
                transports: ['websocket', 'polling'],
                autoConnect: false  // Don't auto-connect, we'll connect manually
            });
            
            this.setupEventHandlers();
            
            // Only connect if we have a valid token
            this.socket.connect();
            
        } catch (error) {
            console.error('Failed to initialize WebSocket connection:', error);
        }
    }
    
    setupEventHandlers() {
        if (!this.socket) return;
        
        this.socket.on('connect', () => {
            console.log('WebSocket connected');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.reconnectDelay = 1000;
            
            // Emit custom event for UI updates
            this.emitCustomEvent('websocket:connected');
        });
        
        this.socket.on('disconnect', (reason) => {
            console.log('WebSocket disconnected:', reason);
            this.isConnected = false;
            
            // Emit custom event for UI updates
            this.emitCustomEvent('websocket:disconnected', { reason });
            
            // Attempt to reconnect if not a manual disconnect
            if (reason !== 'io client disconnect') {
                this.scheduleReconnect();
            }
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('WebSocket connection error:', error);
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
            // Connection is alive
        });
        
        // Start ping interval
        this.startPingInterval();
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this.emitCustomEvent('websocket:max_reconnect_attempts');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
        
        console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
        
        setTimeout(() => {
            if (!this.isConnected) {
                this.connect();
            }
        }, delay);
    }
    
    startPingInterval() {
        // Send ping every 30 seconds to keep connection alive
        setInterval(() => {
            if (this.isConnected && this.socket) {
                this.socket.emit('ping');
            }
        }, 30000);
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
    
    // Cleanup
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
        this.isConnected = false;
        this.currentConversation = null;
        
        if (this.typingTimer) {
            clearTimeout(this.typingTimer);
            this.typingTimer = null;
        }
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