/**
 * WebSocket Compatibility Layer
 * Handles browser-specific WebSocket issues and provides fallbacks
 */

class WebSocketCompatibility {
    constructor() {
        this.browserInfo = this.detectBrowser();
        this.compatibility = this.checkCompatibility();
        this.fallbackStrategies = [];
        
        this.init();
    }
    
    init() {
        console.log('WebSocket Compatibility Layer initialized');
        console.log('Browser:', this.browserInfo);
        console.log('WebSocket support:', this.compatibility);
        
        // Apply browser-specific fixes
        this.applyBrowserFixes();
        
        // Setup fallback strategies
        this.setupFallbacks();
    }
    
    detectBrowser() {
        const ua = navigator.userAgent;
        
        if (ua.includes('Chrome') && !ua.includes('Edg')) {
            const version = ua.match(/Chrome\/(\d+)/)?.[1];
            return { name: 'Chrome', version: parseInt(version) };
        } else if (ua.includes('Firefox')) {
            const version = ua.match(/Firefox\/(\d+)/)?.[1];
            return { name: 'Firefox', version: parseInt(version) };
        } else if (ua.includes('Safari') && !ua.includes('Chrome')) {
            const version = ua.match(/Version\/(\d+)/)?.[1];
            return { name: 'Safari', version: parseInt(version) };
        } else if (ua.includes('Edg')) {
            const version = ua.match(/Edg\/(\d+)/)?.[1];
            return { name: 'Edge', version: parseInt(version) };
        }
        
        return { name: 'Unknown', version: 0 };
    }
    
    checkCompatibility() {
        const support = {
            webSocket: 'WebSocket' in window,
            binaryType: false,
            extensions: false,
            protocol: false,
            closeEvent: false,
            issues: []
        };
        
        if (support.webSocket) {
            // Test WebSocket features
            try {
                const testWs = new WebSocket('ws://test');
                
                support.binaryType = 'binaryType' in testWs;
                support.extensions = 'extensions' in testWs;
                support.protocol = 'protocol' in testWs;
                
                // Test close event
                testWs.addEventListener('close', () => {
                    support.closeEvent = true;
                });
                
                testWs.close();
            } catch (error) {
                support.issues.push(`WebSocket creation failed: ${error.message}`);
            }
            
            // Browser-specific issues
            this.checkBrowserSpecificIssues(support);
        } else {
            support.issues.push('WebSocket API not available');
        }
        
        return support;
    }
    
    checkBrowserSpecificIssues(support) {
        const { name, version } = this.browserInfo;
        
        // Chrome-specific issues
        if (name === 'Chrome') {
            if (version < 80) {
                support.issues.push('Chrome version may have WebSocket connection issues');
            }
            
            // Chrome has issues with certain WebSocket headers
            support.chromeHeaderIssue = true;
        }
        
        // Firefox-specific issues
        if (name === 'Firefox') {
            if (version < 75) {
                support.issues.push('Firefox version may have WebSocket security issues');
            }
            
            // Firefox has stricter CORS policies for WebSocket
            support.strictCORS = true;
        }
        
        // Safari-specific issues
        if (name === 'Safari') {
            if (version < 13) {
                support.issues.push('Safari version may have WebSocket compatibility issues');
            }
            
            // Safari has issues with WebSocket over HTTP in some cases
            support.httpsRequired = true;
        }
        
        // Edge-specific issues
        if (name === 'Edge') {
            if (version < 80) {
                support.issues.push('Edge Legacy may have WebSocket issues');
            }
        }
    }
    
    applyBrowserFixes() {
        const { name, version } = this.browserInfo;
        
        // Chrome fixes
        if (name === 'Chrome' && this.compatibility.chromeHeaderIssue) {
            this.applyChromeHeaderFix();
        }
        
        // Firefox fixes
        if (name === 'Firefox' && this.compatibility.strictCORS) {
            this.applyFirefoxCORSFix();
        }
        
        // Safari fixes
        if (name === 'Safari' && this.compatibility.httpsRequired) {
            this.applySafariHTTPSFix();
        }
    }
    
    applyChromeHeaderFix() {
        console.log('Applying Chrome WebSocket header fix');
        
        // Store original WebSocket
        const OriginalWebSocket = window.WebSocket;
        
        // Create wrapper that handles Chrome-specific header issues
        window.WebSocket = function(url, protocols) {
            const ws = new OriginalWebSocket(url, protocols);
            
            // Chrome sometimes has issues with certain headers
            const originalSend = ws.send;
            ws.send = function(data) {
                try {
                    return originalSend.call(this, data);
                } catch (error) {
                    console.warn('Chrome WebSocket send error, retrying:', error);
                    // Retry after a short delay
                    setTimeout(() => {
                        try {
                            originalSend.call(this, data);
                        } catch (retryError) {
                            console.error('Chrome WebSocket retry failed:', retryError);
                        }
                    }, 100);
                }
            };
            
            return ws;
        };
        
        // Copy static properties
        Object.setPrototypeOf(window.WebSocket, OriginalWebSocket);
        window.WebSocket.CONNECTING = OriginalWebSocket.CONNECTING;
        window.WebSocket.OPEN = OriginalWebSocket.OPEN;
        window.WebSocket.CLOSING = OriginalWebSocket.CLOSING;
        window.WebSocket.CLOSED = OriginalWebSocket.CLOSED;
    }
    
    applyFirefoxCORSFix() {
        console.log('Applying Firefox CORS fix for WebSocket');
        
        // Firefox is stricter about CORS, so we need to ensure proper origin handling
        const OriginalWebSocket = window.WebSocket;
        
        window.WebSocket = function(url, protocols) {
            // Ensure URL is properly formatted for Firefox
            let fixedUrl = url;
            
            // Firefox requires explicit protocol specification in some cases
            if (url.startsWith('//')) {
                fixedUrl = (window.location.protocol === 'https:' ? 'wss:' : 'ws:') + url;
            }
            
            const ws = new OriginalWebSocket(fixedUrl, protocols);
            
            // Firefox sometimes needs explicit error handling
            const originalAddEventListener = ws.addEventListener;
            ws.addEventListener = function(type, listener, options) {
                if (type === 'error') {
                    const wrappedListener = function(event) {
                        console.log('Firefox WebSocket error handled:', event);
                        listener(event);
                    };
                    return originalAddEventListener.call(this, type, wrappedListener, options);
                }
                return originalAddEventListener.call(this, type, listener, options);
            };
            
            return ws;
        };
        
        // Copy static properties
        Object.setPrototypeOf(window.WebSocket, OriginalWebSocket);
        window.WebSocket.CONNECTING = OriginalWebSocket.CONNECTING;
        window.WebSocket.OPEN = OriginalWebSocket.OPEN;
        window.WebSocket.CLOSING = OriginalWebSocket.CLOSING;
        window.WebSocket.CLOSED = OriginalWebSocket.CLOSED;
    }
    
    applySafariHTTPSFix() {
        console.log('Applying Safari HTTPS fix for WebSocket');
        
        const OriginalWebSocket = window.WebSocket;
        
        window.WebSocket = function(url, protocols) {
            let fixedUrl = url;
            
            // Safari may require HTTPS for WebSocket in certain contexts
            if (window.location.protocol === 'https:' && url.startsWith('ws:')) {
                console.warn('Safari: Converting ws:// to wss:// for HTTPS compatibility');
                fixedUrl = url.replace('ws:', 'wss:');
            }
            
            const ws = new OriginalWebSocket(fixedUrl, protocols);
            
            // Safari sometimes has timing issues with WebSocket connections
            const originalClose = ws.close;
            ws.close = function(code, reason) {
                // Add small delay for Safari
                setTimeout(() => {
                    originalClose.call(this, code, reason);
                }, 10);
            };
            
            return ws;
        };
        
        // Copy static properties
        Object.setPrototypeOf(window.WebSocket, OriginalWebSocket);
        window.WebSocket.CONNECTING = OriginalWebSocket.CONNECTING;
        window.WebSocket.OPEN = OriginalWebSocket.OPEN;
        window.WebSocket.CLOSING = OriginalWebSocket.CLOSING;
        window.WebSocket.CLOSED = OriginalWebSocket.CLOSED;
    }
    
    setupFallbacks() {
        // If WebSocket is not supported, setup fallbacks
        if (!this.compatibility.webSocket) {
            this.setupPollingFallback();
            this.setupServerSentEventsFallback();
        }
        
        // Setup connection quality monitoring
        this.setupConnectionMonitoring();
    }
    
    setupPollingFallback() {
        console.log('Setting up polling fallback for WebSocket');
        
        window.WebSocketPollingFallback = class {
            constructor(url) {
                this.url = url.replace('ws://', 'http://').replace('wss://', 'https://');
                this.readyState = 0; // CONNECTING
                this.onopen = null;
                this.onmessage = null;
                this.onerror = null;
                this.onclose = null;
                
                this.pollingInterval = null;
                this.connected = false;
                
                this.startPolling();
            }
            
            startPolling() {
                // Simulate connection
                setTimeout(() => {
                    this.readyState = 1; // OPEN
                    this.connected = true;
                    if (this.onopen) {
                        this.onopen({ type: 'open' });
                    }
                    
                    // Start polling for messages
                    this.pollingInterval = setInterval(() => {
                        this.pollForMessages();
                    }, 1000);
                }, 100);
            }
            
            async pollForMessages() {
                if (!this.connected) return;
                
                try {
                    const response = await fetch(`${this.url}/poll`, {
                        method: 'GET',
                        headers: {
                            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                        }
                    });
                    
                    if (response.ok) {
                        const messages = await response.json();
                        messages.forEach(message => {
                            if (this.onmessage) {
                                this.onmessage({ data: JSON.stringify(message) });
                            }
                        });
                    }
                } catch (error) {
                    console.error('Polling error:', error);
                    if (this.onerror) {
                        this.onerror({ type: 'error', error });
                    }
                }
            }
            
            send(data) {
                if (!this.connected) return;
                
                // Send via HTTP POST
                fetch(`${this.url}/send`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                    },
                    body: data
                }).catch(error => {
                    console.error('Send error:', error);
                    if (this.onerror) {
                        this.onerror({ type: 'error', error });
                    }
                });
            }
            
            close() {
                this.connected = false;
                this.readyState = 3; // CLOSED
                
                if (this.pollingInterval) {
                    clearInterval(this.pollingInterval);
                    this.pollingInterval = null;
                }
                
                if (this.onclose) {
                    this.onclose({ type: 'close' });
                }
            }
            
            addEventListener(type, listener) {
                if (type === 'open') this.onopen = listener;
                else if (type === 'message') this.onmessage = listener;
                else if (type === 'error') this.onerror = listener;
                else if (type === 'close') this.onclose = listener;
            }
        };
        
        this.fallbackStrategies.push('polling');
    }
    
    setupServerSentEventsFallback() {
        if (!('EventSource' in window)) {
            console.log('EventSource not available, skipping SSE fallback');
            return;
        }
        
        console.log('Setting up Server-Sent Events fallback for WebSocket');
        
        window.WebSocketSSEFallback = class {
            constructor(url) {
                this.url = url.replace('ws://', 'http://').replace('wss://', 'https://');
                this.readyState = 0; // CONNECTING
                this.onopen = null;
                this.onmessage = null;
                this.onerror = null;
                this.onclose = null;
                
                this.eventSource = null;
                this.setupEventSource();
            }
            
            setupEventSource() {
                const sseUrl = `${this.url}/events?token=${localStorage.getItem('access_token')}`;
                this.eventSource = new EventSource(sseUrl);
                
                this.eventSource.onopen = () => {
                    this.readyState = 1; // OPEN
                    if (this.onopen) {
                        this.onopen({ type: 'open' });
                    }
                };
                
                this.eventSource.onmessage = (event) => {
                    if (this.onmessage) {
                        this.onmessage({ data: event.data });
                    }
                };
                
                this.eventSource.onerror = (error) => {
                    this.readyState = 3; // CLOSED
                    if (this.onerror) {
                        this.onerror({ type: 'error', error });
                    }
                };
            }
            
            send(data) {
                // Send via HTTP POST (SSE is unidirectional)
                fetch(`${this.url}/send`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                    },
                    body: data
                }).catch(error => {
                    console.error('SSE send error:', error);
                    if (this.onerror) {
                        this.onerror({ type: 'error', error });
                    }
                });
            }
            
            close() {
                if (this.eventSource) {
                    this.eventSource.close();
                    this.eventSource = null;
                }
                
                this.readyState = 3; // CLOSED
                if (this.onclose) {
                    this.onclose({ type: 'close' });
                }
            }
            
            addEventListener(type, listener) {
                if (type === 'open') this.onopen = listener;
                else if (type === 'message') this.onmessage = listener;
                else if (type === 'error') this.onerror = listener;
                else if (type === 'close') this.onclose = listener;
            }
        };
        
        this.fallbackStrategies.push('server-sent-events');
    }
    
    setupConnectionMonitoring() {
        // Monitor WebSocket connection quality across browsers
        const originalWebSocket = window.WebSocket;
        
        if (!originalWebSocket) return;
        
        window.WebSocket = function(url, protocols) {
            const ws = new originalWebSocket(url, protocols);
            
            // Add connection quality monitoring
            ws._connectionStart = performance.now();
            ws._pingTimes = [];
            
            const originalAddEventListener = ws.addEventListener;
            ws.addEventListener = function(type, listener, options) {
                if (type === 'open') {
                    const wrappedListener = function(event) {
                        ws._connectionTime = performance.now() - ws._connectionStart;
                        console.log(`WebSocket connected in ${ws._connectionTime.toFixed(2)}ms`);
                        listener(event);
                    };
                    return originalAddEventListener.call(this, type, wrappedListener, options);
                }
                
                if (type === 'error') {
                    const wrappedListener = function(event) {
                        console.error('WebSocket error detected:', event);
                        
                        // Browser-specific error handling
                        const browserInfo = window.webSocketCompatibility?.browserInfo;
                        if (browserInfo) {
                            console.log(`Browser-specific error handling for ${browserInfo.name}`);
                        }
                        
                        listener(event);
                    };
                    return originalAddEventListener.call(this, type, wrappedListener, options);
                }
                
                return originalAddEventListener.call(this, type, listener, options);
            };
            
            return ws;
        };
        
        // Copy static properties
        Object.setPrototypeOf(window.WebSocket, originalWebSocket);
        window.WebSocket.CONNECTING = originalWebSocket.CONNECTING;
        window.WebSocket.OPEN = originalWebSocket.OPEN;
        window.WebSocket.CLOSING = originalWebSocket.CLOSING;
        window.WebSocket.CLOSED = originalWebSocket.CLOSED;
    }
    
    // Public API
    isWebSocketSupported() {
        return this.compatibility.webSocket;
    }
    
    getCompatibilityInfo() {
        return {
            browser: this.browserInfo,
            compatibility: this.compatibility,
            fallbackStrategies: this.fallbackStrategies
        };
    }
    
    getBestWebSocketImplementation() {
        if (this.compatibility.webSocket && this.compatibility.issues.length === 0) {
            return window.WebSocket;
        }
        
        // Return best fallback
        if (this.fallbackStrategies.includes('server-sent-events') && 'EventSource' in window) {
            return window.WebSocketSSEFallback;
        }
        
        if (this.fallbackStrategies.includes('polling')) {
            return window.WebSocketPollingFallback;
        }
        
        return null;
    }
    
    testWebSocketConnection(url) {
        return new Promise((resolve, reject) => {
            const testWs = new WebSocket(url);
            const timeout = setTimeout(() => {
                testWs.close();
                reject(new Error('WebSocket connection test timeout'));
            }, 5000);
            
            testWs.onopen = () => {
                clearTimeout(timeout);
                testWs.close();
                resolve({
                    success: true,
                    connectionTime: performance.now() - startTime
                });
            };
            
            testWs.onerror = (error) => {
                clearTimeout(timeout);
                reject(error);
            };
            
            const startTime = performance.now();
        });
    }
}

// Initialize WebSocket compatibility layer
window.webSocketCompatibility = new WebSocketCompatibility();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebSocketCompatibility;
}