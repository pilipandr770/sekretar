/**
 * Browser Compatibility Fixes for AI Secretary
 * Handles cross-browser compatibility issues and provides polyfills
 */

class BrowserCompatibilityManager {
    constructor() {
        this.browserInfo = this.detectBrowser();
        this.appliedFixes = [];
        this.polyfillsLoaded = [];
        this.init();
    }
    
    init() {
        console.log('🔧 Initializing browser compatibility fixes...');
        console.log('Browser detected:', this.browserInfo.name, this.browserInfo.version);
        
        // Apply fixes based on browser detection
        this.applyBrowserSpecificFixes();
        
        // Apply general compatibility fixes
        this.applyGeneralFixes();
        
        console.log('✅ Browser compatibility fixes applied:', this.appliedFixes.join(', '));
    }
    
    detectBrowser() {
        const userAgent = navigator.userAgent;
        const vendor = navigator.vendor || '';
        
        let browser = 'Unknown';
        let version = 'Unknown';
        let majorVersion = 0;
        
        // Chrome detection
        if (userAgent.includes('Chrome') && vendor.includes('Google')) {
            browser = 'Chrome';
            const match = userAgent.match(/Chrome\/(\d+)\.(\d+)/);
            if (match) {
                version = `${match[1]}.${match[2]}`;
                majorVersion = parseInt(match[1]);
            }
        }
        // Firefox detection
        else if (userAgent.includes('Firefox')) {
            browser = 'Firefox';
            const match = userAgent.match(/Firefox\/(\d+)\.(\d+)/);
            if (match) {
                version = `${match[1]}.${match[2]}`;
                majorVersion = parseInt(match[1]);
            }
        }
        // Safari detection
        else if (userAgent.includes('Safari') && !userAgent.includes('Chrome')) {
            browser = 'Safari';
            const match = userAgent.match(/Version\/(\d+)\.(\d+)/);
            if (match) {
                version = `${match[1]}.${match[2]}`;
                majorVersion = parseInt(match[1]);
            }
        }
        // Edge detection (Chromium-based)
        else if (userAgent.includes('Edg')) {
            browser = 'Edge';
            const match = userAgent.match(/Edg\/(\d+)\.(\d+)/);
            if (match) {
                version = `${match[1]}.${match[2]}`;
                majorVersion = parseInt(match[1]);
            }
        }
        // Legacy Edge detection
        else if (userAgent.includes('Edge')) {
            browser = 'EdgeLegacy';
            const match = userAgent.match(/Edge\/(\d+)\.(\d+)/);
            if (match) {
                version = `${match[1]}.${match[2]}`;
                majorVersion = parseInt(match[1]);
            }
        }
        // Internet Explorer detection
        else if (userAgent.includes('Trident') || userAgent.includes('MSIE')) {
            browser = 'IE';
            const match = userAgent.match(/(?:MSIE |rv:)(\d+)\.(\d+)/);
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
            isModern: this.isModernBrowser(browser, majorVersion),
            supportsES6: this.supportsES6(browser, majorVersion),
            supportsWebSocket: this.supportsWebSocket(browser, majorVersion)
        };
    }
    
    isModernBrowser(browser, majorVersion) {
        const modernVersions = {
            'Chrome': 60,
            'Firefox': 55,
            'Safari': 12,
            'Edge': 79,
            'EdgeLegacy': 18
        };
        
        return majorVersion >= (modernVersions[browser] || 999);
    }
    
    supportsES6(browser, majorVersion) {
        const es6Versions = {
            'Chrome': 51,
            'Firefox': 45,
            'Safari': 10,
            'Edge': 79,
            'EdgeLegacy': 14
        };
        
        return majorVersion >= (es6Versions[browser] || 999);
    }
    
    supportsWebSocket(browser, majorVersion) {
        const webSocketVersions = {
            'Chrome': 16,
            'Firefox': 11,
            'Safari': 7,
            'Edge': 79,
            'EdgeLegacy': 12,
            'IE': 10
        };
        
        return majorVersion >= (webSocketVersions[browser] || 999);
    }
    
    applyBrowserSpecificFixes() {
        switch (this.browserInfo.name) {
            case 'Safari':
                this.applySafariFixes();
                break;
            case 'Firefox':
                this.applyFirefoxFixes();
                break;
            case 'Edge':
            case 'EdgeLegacy':
                this.applyEdgeFixes();
                break;
            case 'IE':
                this.applyIEFixes();
                break;
            case 'Chrome':
                this.applyChromeFixes();
                break;
        }
    }
    
    applySafariFixes() {
        console.log('🍎 Applying Safari-specific fixes...');
        
        // Safari WebSocket connection fix
        if (this.browserInfo.majorVersion < 14) {
            this.fixSafariWebSocketConnection();
        }
        
        // Safari localStorage in private mode fix
        this.fixSafariPrivateModeStorage();
        
        // Safari date parsing fix
        this.fixSafariDateParsing();
        
        // Safari fetch credentials fix
        this.fixSafariFetchCredentials();
        
        this.appliedFixes.push('Safari-specific');
    }
    
    applyFirefoxFixes() {
        console.log('🦊 Applying Firefox-specific fixes...');
        
        // Firefox WebSocket connection fix
        if (this.browserInfo.majorVersion < 60) {
            this.fixFirefoxWebSocketConnection();
        }
        
        // Firefox custom event fix
        if (this.browserInfo.majorVersion < 50) {
            this.fixFirefoxCustomEvents();
        }
        
        // Firefox fetch fix
        if (this.browserInfo.majorVersion < 40) {
            this.loadFetchPolyfill();
        }
        
        this.appliedFixes.push('Firefox-specific');
    }
    
    applyEdgeFixes() {
        console.log('🔷 Applying Edge-specific fixes...');
        
        // Legacy Edge WebSocket fix
        if (this.browserInfo.name === 'EdgeLegacy') {
            this.fixEdgeLegacyWebSocket();
        }
        
        // Edge fetch credentials fix
        this.fixEdgeFetchCredentials();
        
        // Edge Promise fix for older versions
        if (this.browserInfo.majorVersion < 15) {
            this.loadPromisePolyfill();
        }
        
        this.appliedFixes.push('Edge-specific');
    }
    
    applyIEFixes() {
        console.log('🌐 Applying Internet Explorer fixes...');
        
        // IE is not supported, but provide graceful degradation
        this.showIEUnsupportedMessage();
        
        // Load all necessary polyfills
        this.loadES5Polyfills();
        this.loadFetchPolyfill();
        this.loadPromisePolyfill();
        this.loadCustomEventPolyfill();
        
        this.appliedFixes.push('IE-compatibility');
    }
    
    applyChromeFixes() {
        console.log('🟢 Applying Chrome-specific fixes...');
        
        // Chrome-specific WebSocket optimization
        this.optimizeChromeWebSocket();
        
        // Chrome memory management for WebSocket
        this.fixChromeWebSocketMemory();
        
        this.appliedFixes.push('Chrome-specific');
    }
    
    applyGeneralFixes() {
        console.log('🔧 Applying general compatibility fixes...');
        
        // Fix console methods for older browsers
        this.fixConsole();
        
        // Fix addEventListener for older browsers
        this.fixEventListeners();
        
        // Fix JSON for older browsers
        this.fixJSON();
        
        // Fix Array methods for older browsers
        this.fixArrayMethods();
        
        // Fix Object methods for older browsers
        this.fixObjectMethods();
        
        this.appliedFixes.push('General-compatibility');
    }
    
    // Safari-specific fixes
    fixSafariWebSocketConnection() {
        console.log('🔧 Fixing Safari WebSocket connection issues...');
        
        // Safari has issues with WebSocket connections over HTTPS with self-signed certificates
        const originalWebSocket = window.WebSocket;
        
        window.WebSocket = function(url, protocols) {
            // Convert ws:// to wss:// for Safari if on HTTPS
            if (location.protocol === 'https:' && url.startsWith('ws://')) {
                url = url.replace('ws://', 'wss://');
                console.log('🔧 Safari: Converted WebSocket URL to secure connection');
            }
            
            const ws = new originalWebSocket(url, protocols);
            
            // Add Safari-specific error handling
            const originalOnError = ws.onerror;
            ws.onerror = function(event) {
                console.warn('🍎 Safari WebSocket error detected, attempting fallback...');
                if (originalOnError) originalOnError.call(this, event);
            };
            
            return ws;
        };
        
        // Copy static properties
        Object.setPrototypeOf(window.WebSocket, originalWebSocket);
        window.WebSocket.prototype = originalWebSocket.prototype;
        
        this.polyfillsLoaded.push('Safari-WebSocket-fix');
    }
    
    fixSafariPrivateModeStorage() {
        console.log('🔧 Fixing Safari private mode localStorage...');
        
        // Test if localStorage is available (Safari private mode blocks it)
        try {
            localStorage.setItem('test', 'test');
            localStorage.removeItem('test');
        } catch (e) {
            console.warn('🍎 Safari private mode detected, implementing memory storage fallback');
            
            // Implement in-memory storage fallback
            const memoryStorage = {};
            
            window.localStorage = {
                setItem: function(key, value) {
                    memoryStorage[key] = String(value);
                },
                getItem: function(key) {
                    return memoryStorage[key] || null;
                },
                removeItem: function(key) {
                    delete memoryStorage[key];
                },
                clear: function() {
                    Object.keys(memoryStorage).forEach(key => delete memoryStorage[key]);
                },
                get length() {
                    return Object.keys(memoryStorage).length;
                },
                key: function(index) {
                    return Object.keys(memoryStorage)[index] || null;
                }
            };
            
            this.polyfillsLoaded.push('Safari-localStorage-fallback');
        }
    }
    
    fixSafariDateParsing() {
        console.log('🔧 Fixing Safari date parsing...');
        
        // Safari has issues with certain date formats
        const originalDateParse = Date.parse;
        
        Date.parse = function(dateString) {
            // Fix ISO date strings for Safari
            if (typeof dateString === 'string' && dateString.includes('T') && !dateString.includes('Z') && !dateString.includes('+')) {
                dateString = dateString + 'Z';
            }
            
            return originalDateParse.call(this, dateString);
        };
        
        this.polyfillsLoaded.push('Safari-date-parsing-fix');
    }
    
    fixSafariFetchCredentials() {
        console.log('🔧 Fixing Safari fetch credentials...');
        
        // Safari has different default behavior for fetch credentials
        if (window.fetch) {
            const originalFetch = window.fetch;
            
            window.fetch = function(input, init = {}) {
                // Ensure credentials are included by default for same-origin requests
                if (!init.credentials && typeof input === 'string' && !input.startsWith('http')) {
                    init.credentials = 'same-origin';
                }
                
                return originalFetch.call(this, input, init);
            };
            
            this.polyfillsLoaded.push('Safari-fetch-credentials-fix');
        }
    }
    
    // Firefox-specific fixes
    fixFirefoxWebSocketConnection() {
        console.log('🔧 Fixing Firefox WebSocket connection issues...');
        
        // Firefox older versions have issues with WebSocket connection timing
        const originalWebSocket = window.WebSocket;
        
        window.WebSocket = function(url, protocols) {
            const ws = new originalWebSocket(url, protocols);
            
            // Add Firefox-specific connection delay
            const originalConnect = ws.connect;
            if (originalConnect) {
                ws.connect = function() {
                    setTimeout(() => originalConnect.call(this), 100);
                };
            }
            
            return ws;
        };
        
        Object.setPrototypeOf(window.WebSocket, originalWebSocket);
        window.WebSocket.prototype = originalWebSocket.prototype;
        
        this.polyfillsLoaded.push('Firefox-WebSocket-fix');
    }
    
    fixFirefoxCustomEvents() {
        console.log('🔧 Fixing Firefox CustomEvent support...');
        
        if (!window.CustomEvent || typeof window.CustomEvent !== 'function') {
            window.CustomEvent = function(event, params) {
                params = params || { bubbles: false, cancelable: false, detail: undefined };
                const evt = document.createEvent('CustomEvent');
                evt.initCustomEvent(event, params.bubbles, params.cancelable, params.detail);
                return evt;
            };
            
            window.CustomEvent.prototype = window.Event.prototype;
            this.polyfillsLoaded.push('Firefox-CustomEvent-polyfill');
        }
    }
    
    // Edge-specific fixes
    fixEdgeLegacyWebSocket() {
        console.log('🔧 Fixing Edge Legacy WebSocket issues...');
        
        // Edge Legacy has issues with WebSocket binary data
        const originalWebSocket = window.WebSocket;
        
        window.WebSocket = function(url, protocols) {
            const ws = new originalWebSocket(url, protocols);
            
            // Override binaryType for Edge Legacy
            ws.binaryType = 'arraybuffer';
            
            return ws;
        };
        
        Object.setPrototypeOf(window.WebSocket, originalWebSocket);
        window.WebSocket.prototype = originalWebSocket.prototype;
        
        this.polyfillsLoaded.push('EdgeLegacy-WebSocket-fix');
    }
    
    fixEdgeFetchCredentials() {
        console.log('🔧 Fixing Edge fetch credentials...');
        
        // Similar to Safari fix but for Edge
        if (window.fetch) {
            const originalFetch = window.fetch;
            
            window.fetch = function(input, init = {}) {
                if (!init.credentials) {
                    init.credentials = 'same-origin';
                }
                
                return originalFetch.call(this, input, init);
            };
            
            this.polyfillsLoaded.push('Edge-fetch-credentials-fix');
        }
    }
    
    // Chrome-specific optimizations
    optimizeChromeWebSocket() {
        console.log('🔧 Optimizing Chrome WebSocket performance...');
        
        // Chrome-specific WebSocket optimizations
        const originalWebSocket = window.WebSocket;
        
        window.WebSocket = function(url, protocols) {
            const ws = new originalWebSocket(url, protocols);
            
            // Optimize Chrome WebSocket buffer sizes
            if (ws.bufferedAmount !== undefined) {
                const originalSend = ws.send;
                ws.send = function(data) {
                    // Check buffer before sending in Chrome
                    if (this.bufferedAmount > 1024 * 1024) { // 1MB buffer limit
                        console.warn('🟢 Chrome: WebSocket buffer full, queuing message');
                        setTimeout(() => this.send(data), 10);
                        return;
                    }
                    originalSend.call(this, data);
                };
            }
            
            return ws;
        };
        
        Object.setPrototypeOf(window.WebSocket, originalWebSocket);
        window.WebSocket.prototype = originalWebSocket.prototype;
        
        this.polyfillsLoaded.push('Chrome-WebSocket-optimization');
    }
    
    fixChromeWebSocketMemory() {
        console.log('🔧 Fixing Chrome WebSocket memory management...');
        
        // Chrome-specific memory management for WebSocket connections
        let activeConnections = new Set();
        
        const originalWebSocket = window.WebSocket;
        
        window.WebSocket = function(url, protocols) {
            const ws = new originalWebSocket(url, protocols);
            
            activeConnections.add(ws);
            
            const originalClose = ws.close;
            ws.close = function(code, reason) {
                activeConnections.delete(this);
                originalClose.call(this, code, reason);
            };
            
            // Auto-cleanup on page unload
            window.addEventListener('beforeunload', () => {
                activeConnections.forEach(connection => {
                    if (connection.readyState === WebSocket.OPEN) {
                        connection.close();
                    }
                });
            });
            
            return ws;
        };
        
        Object.setPrototypeOf(window.WebSocket, originalWebSocket);
        window.WebSocket.prototype = originalWebSocket.prototype;
        
        this.polyfillsLoaded.push('Chrome-WebSocket-memory-fix');
    }
    
    // General polyfills and fixes
    fixConsole() {
        if (!window.console) {
            window.console = {
                log: function() {},
                error: function() {},
                warn: function() {},
                info: function() {},
                debug: function() {}
            };
            this.polyfillsLoaded.push('console-polyfill');
        }
    }
    
    fixEventListeners() {
        // Fix addEventListener for IE8 and below
        if (!Element.prototype.addEventListener) {
            Element.prototype.addEventListener = function(event, handler, useCapture) {
                this.attachEvent('on' + event, handler);
            };
            
            Element.prototype.removeEventListener = function(event, handler, useCapture) {
                this.detachEvent('on' + event, handler);
            };
            
            this.polyfillsLoaded.push('addEventListener-polyfill');
        }
    }
    
    fixJSON() {
        if (!window.JSON) {
            // Load JSON2 polyfill for very old browsers
            console.warn('JSON not supported, loading polyfill...');
            this.loadJSONPolyfill();
        }
    }
    
    fixArrayMethods() {
        // Fix Array.prototype methods for older browsers
        if (!Array.prototype.forEach) {
            Array.prototype.forEach = function(callback, thisArg) {
                for (let i = 0; i < this.length; i++) {
                    callback.call(thisArg, this[i], i, this);
                }
            };
            this.polyfillsLoaded.push('Array.forEach-polyfill');
        }
        
        if (!Array.prototype.map) {
            Array.prototype.map = function(callback, thisArg) {
                const result = [];
                for (let i = 0; i < this.length; i++) {
                    result[i] = callback.call(thisArg, this[i], i, this);
                }
                return result;
            };
            this.polyfillsLoaded.push('Array.map-polyfill');
        }
        
        if (!Array.prototype.filter) {
            Array.prototype.filter = function(callback, thisArg) {
                const result = [];
                for (let i = 0; i < this.length; i++) {
                    if (callback.call(thisArg, this[i], i, this)) {
                        result.push(this[i]);
                    }
                }
                return result;
            };
            this.polyfillsLoaded.push('Array.filter-polyfill');
        }
    }
    
    fixObjectMethods() {
        // Fix Object methods for older browsers
        if (!Object.keys) {
            Object.keys = function(obj) {
                const keys = [];
                for (const key in obj) {
                    if (obj.hasOwnProperty(key)) {
                        keys.push(key);
                    }
                }
                return keys;
            };
            this.polyfillsLoaded.push('Object.keys-polyfill');
        }
    }
    
    // Polyfill loaders
    loadFetchPolyfill() {
        console.log('📦 Loading fetch polyfill...');
        
        if (!window.fetch) {
            // Simple fetch polyfill using XMLHttpRequest
            window.fetch = function(url, options = {}) {
                return new Promise((resolve, reject) => {
                    const xhr = new XMLHttpRequest();
                    
                    xhr.open(options.method || 'GET', url);
                    
                    // Set headers
                    if (options.headers) {
                        Object.keys(options.headers).forEach(key => {
                            xhr.setRequestHeader(key, options.headers[key]);
                        });
                    }
                    
                    // Set credentials
                    if (options.credentials === 'include') {
                        xhr.withCredentials = true;
                    }
                    
                    xhr.onload = function() {
                        const response = {
                            ok: xhr.status >= 200 && xhr.status < 300,
                            status: xhr.status,
                            statusText: xhr.statusText,
                            text: () => Promise.resolve(xhr.responseText),
                            json: () => Promise.resolve(JSON.parse(xhr.responseText))
                        };
                        resolve(response);
                    };
                    
                    xhr.onerror = () => reject(new Error('Network error'));
                    
                    xhr.send(options.body);
                });
            };
            
            this.polyfillsLoaded.push('fetch-polyfill');
        }
    }
    
    loadPromisePolyfill() {
        console.log('📦 Loading Promise polyfill...');
        
        if (!window.Promise) {
            // Simple Promise polyfill
            window.Promise = function(executor) {
                const self = this;
                self.state = 'pending';
                self.value = undefined;
                self.handlers = [];
                
                function resolve(result) {
                    if (self.state === 'pending') {
                        self.state = 'fulfilled';
                        self.value = result;
                        self.handlers.forEach(handle);
                        self.handlers = null;
                    }
                }
                
                function reject(error) {
                    if (self.state === 'pending') {
                        self.state = 'rejected';
                        self.value = error;
                        self.handlers.forEach(handle);
                        self.handlers = null;
                    }
                }
                
                function handle(handler) {
                    if (self.state === 'pending') {
                        self.handlers.push(handler);
                    } else {
                        if (self.state === 'fulfilled' && typeof handler.onFulfilled === 'function') {
                            handler.onFulfilled(self.value);
                        }
                        if (self.state === 'rejected' && typeof handler.onRejected === 'function') {
                            handler.onRejected(self.value);
                        }
                    }
                }
                
                this.then = function(onFulfilled, onRejected) {
                    return new Promise((resolve, reject) => {
                        handle({
                            onFulfilled: function(result) {
                                try {
                                    resolve(onFulfilled ? onFulfilled(result) : result);
                                } catch (ex) {
                                    reject(ex);
                                }
                            },
                            onRejected: function(error) {
                                try {
                                    resolve(onRejected ? onRejected(error) : error);
                                } catch (ex) {
                                    reject(ex);
                                }
                            }
                        });
                    });
                };
                
                executor(resolve, reject);
            };
            
            this.polyfillsLoaded.push('Promise-polyfill');
        }
    }
    
    loadCustomEventPolyfill() {
        console.log('📦 Loading CustomEvent polyfill...');
        
        if (!window.CustomEvent || typeof window.CustomEvent !== 'function') {
            window.CustomEvent = function(event, params) {
                params = params || { bubbles: false, cancelable: false, detail: undefined };
                const evt = document.createEvent('CustomEvent');
                evt.initCustomEvent(event, params.bubbles, params.cancelable, params.detail);
                return evt;
            };
            
            window.CustomEvent.prototype = window.Event.prototype;
            this.polyfillsLoaded.push('CustomEvent-polyfill');
        }
    }
    
    loadES5Polyfills() {
        console.log('📦 Loading ES5 polyfills...');
        
        // This would load a comprehensive ES5 polyfill library
        // In a real implementation, you would load es5-shim or similar
        console.log('   • ES5 polyfills would be loaded from CDN');
        this.polyfillsLoaded.push('ES5-polyfills');
    }
    
    loadJSONPolyfill() {
        console.log('📦 Loading JSON polyfill...');
        
        // This would load JSON2 polyfill
        console.log('   • JSON2 polyfill would be loaded from CDN');
        this.polyfillsLoaded.push('JSON-polyfill');
    }
    
    showIEUnsupportedMessage() {
        console.warn('⚠️ Internet Explorer detected - limited support available');
        
        // Show user-friendly message about IE support
        const ieWarning = document.createElement('div');
        ieWarning.id = 'ie-warning';
        ieWarning.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            text-align: center;
            z-index: 10000;
            border-bottom: 1px solid #f5c6cb;
        `;
        ieWarning.innerHTML = `
            <strong>⚠️ Limited Browser Support</strong><br>
            You are using Internet Explorer, which has limited support for modern web features.
            For the best experience, please use Chrome, Firefox, Safari, or Edge.
            <button onclick="this.parentNode.style.display='none'" style="margin-left: 15px; padding: 5px 10px;">Dismiss</button>
        `;
        
        document.body.insertBefore(ieWarning, document.body.firstChild);
    }
    
    // Public API
    getBrowserInfo() {
        return this.browserInfo;
    }
    
    getAppliedFixes() {
        return this.appliedFixes;
    }
    
    getLoadedPolyfills() {
        return this.polyfillsLoaded;
    }
    
    isFeatureSupported(feature) {
        switch (feature) {
            case 'websocket':
                return this.browserInfo.supportsWebSocket;
            case 'es6':
                return this.browserInfo.supportsES6;
            case 'fetch':
                return typeof fetch !== 'undefined';
            case 'localStorage':
                return typeof localStorage !== 'undefined';
            case 'customEvents':
                return typeof CustomEvent !== 'undefined';
            default:
                return false;
        }
    }
    
    generateCompatibilityReport() {
        return {
            browser: this.browserInfo,
            appliedFixes: this.appliedFixes,
            loadedPolyfills: this.polyfillsLoaded,
            featureSupport: {
                websocket: this.isFeatureSupported('websocket'),
                es6: this.isFeatureSupported('es6'),
                fetch: this.isFeatureSupported('fetch'),
                localStorage: this.isFeatureSupported('localStorage'),
                customEvents: this.isFeatureSupported('customEvents')
            },
            timestamp: new Date().toISOString()
        };
    }
}

// Initialize browser compatibility manager
let browserCompatibilityManager;

document.addEventListener('DOMContentLoaded', function() {
    browserCompatibilityManager = new BrowserCompatibilityManager();
    
    // Make it globally available
    window.browserCompatibilityManager = browserCompatibilityManager;
    
    // Emit compatibility ready event
    const compatibilityEvent = new CustomEvent('browser:compatibility:ready', {
        detail: browserCompatibilityManager.generateCompatibilityReport()
    });
    document.dispatchEvent(compatibilityEvent);
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BrowserCompatibilityManager;
}