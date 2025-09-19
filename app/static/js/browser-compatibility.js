/**
 * Browser Compatibility Checker for AI Secretary
 * Detects browser capabilities and provides fallbacks
 */

class BrowserCompatibility {
    constructor() {
        this.userAgent = navigator.userAgent;
        this.browserInfo = this.detectBrowser();
        this.features = this.checkFeatures();
        this.webSocketSupport = this.checkWebSocketSupport();
        
        this.init();
    }
    
    init() {
        // Log browser information
        console.log('Browser detected:', this.browserInfo);
        console.log('Feature support:', this.features);
        console.log('WebSocket support:', this.webSocketSupport);
        
        // Show warnings for unsupported features
        this.showCompatibilityWarnings();
        
        // Apply polyfills if needed
        this.applyPolyfills();
        
        // Setup fallbacks
        this.setupFallbacks();
    }
    
    detectBrowser() {
        const ua = this.userAgent;
        
        // Chrome
        if (ua.includes('Chrome') && !ua.includes('Edg')) {
            const version = ua.match(/Chrome\/(\d+)/)?.[1];
            return { name: 'Chrome', version: parseInt(version), isSupported: parseInt(version) >= 80 };
        }
        
        // Firefox
        if (ua.includes('Firefox')) {
            const version = ua.match(/Firefox\/(\d+)/)?.[1];
            return { name: 'Firefox', version: parseInt(version), isSupported: parseInt(version) >= 75 };
        }
        
        // Safari
        if (ua.includes('Safari') && !ua.includes('Chrome')) {
            const version = ua.match(/Version\/(\d+)/)?.[1];
            return { name: 'Safari', version: parseInt(version), isSupported: parseInt(version) >= 13 };
        }
        
        // Edge
        if (ua.includes('Edg')) {
            const version = ua.match(/Edg\/(\d+)/)?.[1];
            return { name: 'Edge', version: parseInt(version), isSupported: parseInt(version) >= 80 };
        }
        
        // Internet Explorer
        if (ua.includes('MSIE') || ua.includes('Trident')) {
            return { name: 'Internet Explorer', version: 0, isSupported: false };
        }
        
        return { name: 'Unknown', version: 0, isSupported: false };
    }
    
    checkFeatures() {
        return {
            // Core JavaScript features
            es6Classes: this.checkES6Classes(),
            es6Modules: this.checkES6Modules(),
            promises: 'Promise' in window,
            asyncAwait: this.checkAsyncAwait(),
            fetch: 'fetch' in window,
            
            // DOM features
            customElements: 'customElements' in window,
            shadowDOM: 'attachShadow' in Element.prototype,
            
            // Storage
            localStorage: this.checkLocalStorage(),
            sessionStorage: this.checkSessionStorage(),
            indexedDB: 'indexedDB' in window,
            
            // Network
            webSocket: 'WebSocket' in window,
            eventSource: 'EventSource' in window,
            
            // Modern APIs
            intersectionObserver: 'IntersectionObserver' in window,
            mutationObserver: 'MutationObserver' in window,
            performanceObserver: 'PerformanceObserver' in window,
            
            // CSS features
            cssGrid: this.checkCSSGrid(),
            cssFlexbox: this.checkCSSFlexbox(),
            cssCustomProperties: this.checkCSSCustomProperties(),
            
            // Media
            webRTC: this.checkWebRTC(),
            mediaDevices: 'mediaDevices' in navigator,
            
            // Security
            crypto: 'crypto' in window && 'subtle' in window.crypto,
            
            // Notifications
            notifications: 'Notification' in window,
            
            // Service Worker
            serviceWorker: 'serviceWorker' in navigator
        };
    }
    
    checkES6Classes() {
        try {
            eval('class Test {}');
            return true;
        } catch (e) {
            return false;
        }
    }
    
    checkES6Modules() {
        return 'noModule' in document.createElement('script');
    }
    
    checkAsyncAwait() {
        try {
            eval('async function test() { await Promise.resolve(); }');
            return true;
        } catch (e) {
            return false;
        }
    }
    
    checkLocalStorage() {
        try {
            const test = 'test';
            localStorage.setItem(test, test);
            localStorage.removeItem(test);
            return true;
        } catch (e) {
            return false;
        }
    }
    
    checkSessionStorage() {
        try {
            const test = 'test';
            sessionStorage.setItem(test, test);
            sessionStorage.removeItem(test);
            return true;
        } catch (e) {
            return false;
        }
    }
    
    checkCSSGrid() {
        return CSS.supports('display', 'grid');
    }
    
    checkCSSFlexbox() {
        return CSS.supports('display', 'flex');
    }
    
    checkCSSCustomProperties() {
        return CSS.supports('--test', 'test');
    }
    
    checkWebRTC() {
        return 'RTCPeerConnection' in window || 'webkitRTCPeerConnection' in window;
    }
    
    checkWebSocketSupport() {
        if (!this.features.webSocket) {
            return {
                supported: false,
                reason: 'WebSocket API not available'
            };
        }
        
        // Check for specific WebSocket features
        const support = {
            supported: true,
            features: {
                basicWebSocket: true,
                binaryType: 'binaryType' in WebSocket.prototype,
                extensions: 'extensions' in WebSocket.prototype,
                protocol: 'protocol' in WebSocket.prototype
            }
        };
        
        // Test WebSocket creation (without actually connecting)
        try {
            const testSocket = new WebSocket('ws://test');
            testSocket.close();
            support.canCreate = true;
        } catch (error) {
            support.canCreate = false;
            support.createError = error.message;
        }
        
        return support;
    }
    
    showCompatibilityWarnings() {
        const warnings = [];
        
        // Browser support warning
        if (!this.browserInfo.isSupported) {
            warnings.push({
                type: 'browser',
                message: `Your browser (${this.browserInfo.name}) may not be fully supported. Please consider upgrading to a modern browser.`,
                severity: 'high'
            });
        }
        
        // Critical feature warnings
        if (!this.features.promises) {
            warnings.push({
                type: 'feature',
                message: 'Promise support is required for this application to work properly.',
                severity: 'high'
            });
        }
        
        if (!this.features.fetch) {
            warnings.push({
                type: 'feature',
                message: 'Fetch API not supported. Using XMLHttpRequest fallback.',
                severity: 'medium'
            });
        }
        
        if (!this.features.localStorage) {
            warnings.push({
                type: 'feature',
                message: 'Local storage not available. Some features may not work properly.',
                severity: 'medium'
            });
        }
        
        if (!this.webSocketSupport.supported) {
            warnings.push({
                type: 'websocket',
                message: 'WebSocket not supported. Real-time features will be disabled.',
                severity: 'medium'
            });
        }
        
        // Show warnings to user
        this.displayWarnings(warnings);
    }
    
    displayWarnings(warnings) {
        const highSeverityWarnings = warnings.filter(w => w.severity === 'high');
        const mediumSeverityWarnings = warnings.filter(w => w.severity === 'medium');
        
        // Show high severity warnings immediately
        if (highSeverityWarnings.length > 0) {
            this.showWarningModal(highSeverityWarnings);
        }
        
        // Log medium severity warnings
        mediumSeverityWarnings.forEach(warning => {
            console.warn(`Compatibility warning (${warning.type}):`, warning.message);
        });
        
        // Emit compatibility event
        document.dispatchEvent(new CustomEvent('browser:compatibility', {
            detail: { warnings, browserInfo: this.browserInfo, features: this.features }
        }));
    }
    
    showWarningModal(warnings) {
        // Create modal for critical warnings
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'compatibilityModal';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-warning">
                        <h5 class="modal-title">Browser Compatibility Warning</h5>
                    </div>
                    <div class="modal-body">
                        <p>Your browser may not support all features of this application:</p>
                        <ul>
                            ${warnings.map(w => `<li>${w.message}</li>`).join('')}
                        </ul>
                        <p>For the best experience, please use a modern browser like Chrome, Firefox, Safari, or Edge.</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-warning" data-bs-dismiss="modal">Continue Anyway</button>
                        <a href="https://browsehappy.com/" class="btn btn-primary" target="_blank">Update Browser</a>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Show modal if Bootstrap is available
        if (window.bootstrap) {
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
        } else {
            // Fallback: show as alert
            alert(warnings.map(w => w.message).join('\n\n'));
            modal.remove();
        }
    }
    
    applyPolyfills() {
        // Fetch polyfill
        if (!this.features.fetch) {
            this.loadFetchPolyfill();
        }
        
        // Promise polyfill
        if (!this.features.promises) {
            this.loadPromisePolyfill();
        }
        
        // Custom Elements polyfill
        if (!this.features.customElements) {
            this.loadCustomElementsPolyfill();
        }
        
        // IntersectionObserver polyfill
        if (!this.features.intersectionObserver) {
            this.loadIntersectionObserverPolyfill();
        }
    }
    
    loadFetchPolyfill() {
        console.log('Loading fetch polyfill...');
        
        // Simple fetch polyfill using XMLHttpRequest
        window.fetch = function(url, options = {}) {
            return new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                const method = options.method || 'GET';
                
                xhr.open(method, url);
                
                // Set headers
                if (options.headers) {
                    Object.entries(options.headers).forEach(([key, value]) => {
                        xhr.setRequestHeader(key, value);
                    });
                }
                
                xhr.onload = () => {
                    const response = {
                        ok: xhr.status >= 200 && xhr.status < 300,
                        status: xhr.status,
                        statusText: xhr.statusText,
                        json: () => Promise.resolve(JSON.parse(xhr.responseText)),
                        text: () => Promise.resolve(xhr.responseText)
                    };
                    resolve(response);
                };
                
                xhr.onerror = () => reject(new Error('Network error'));
                xhr.ontimeout = () => reject(new Error('Request timeout'));
                
                if (options.timeout) {
                    xhr.timeout = options.timeout;
                }
                
                xhr.send(options.body);
            });
        };
    }
    
    loadPromisePolyfill() {
        console.log('Loading Promise polyfill...');
        // This would typically load a Promise polyfill from a CDN
        // For now, we'll just warn that the app may not work
        console.error('Promise polyfill needed but not implemented');
    }
    
    loadCustomElementsPolyfill() {
        console.log('Custom Elements not supported, some features may not work');
    }
    
    loadIntersectionObserverPolyfill() {
        console.log('IntersectionObserver not supported, lazy loading may not work optimally');
    }
    
    setupFallbacks() {
        // WebSocket fallback
        if (!this.webSocketSupport.supported) {
            this.setupWebSocketFallback();
        }
        
        // Local storage fallback
        if (!this.features.localStorage) {
            this.setupLocalStorageFallback();
        }
        
        // Notification fallback
        if (!this.features.notifications) {
            this.setupNotificationFallback();
        }
    }
    
    setupWebSocketFallback() {
        console.log('Setting up WebSocket fallback using polling');
        
        // Create a polling-based WebSocket-like interface
        window.WebSocketFallback = class {
            constructor(url) {
                this.url = url;
                this.readyState = 0; // CONNECTING
                this.onopen = null;
                this.onmessage = null;
                this.onerror = null;
                this.onclose = null;
                
                // Start polling
                this.startPolling();
            }
            
            startPolling() {
                // This would implement long-polling or server-sent events
                console.log('WebSocket fallback: polling not implemented');
                
                // Simulate connection failure
                setTimeout(() => {
                    this.readyState = 3; // CLOSED
                    if (this.onerror) {
                        this.onerror(new Error('WebSocket not supported'));
                    }
                }, 100);
            }
            
            send(data) {
                console.log('WebSocket fallback: send not implemented');
            }
            
            close() {
                this.readyState = 3; // CLOSED
                if (this.onclose) {
                    this.onclose();
                }
            }
        };
    }
    
    setupLocalStorageFallback() {
        console.log('Setting up localStorage fallback using cookies');
        
        // Simple cookie-based storage fallback
        window.localStorage = {
            getItem: (key) => {
                const cookies = document.cookie.split(';');
                for (let cookie of cookies) {
                    const [name, value] = cookie.trim().split('=');
                    if (name === key) {
                        return decodeURIComponent(value);
                    }
                }
                return null;
            },
            
            setItem: (key, value) => {
                document.cookie = `${key}=${encodeURIComponent(value)}; path=/; max-age=31536000`;
            },
            
            removeItem: (key) => {
                document.cookie = `${key}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
            },
            
            clear: () => {
                const cookies = document.cookie.split(';');
                for (let cookie of cookies) {
                    const name = cookie.split('=')[0].trim();
                    document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
                }
            }
        };
    }
    
    setupNotificationFallback() {
        console.log('Setting up notification fallback using alerts');
        
        window.Notification = class {
            constructor(title, options = {}) {
                // Fallback to alert for critical notifications
                if (options.requireInteraction) {
                    alert(`${title}: ${options.body || ''}`);
                } else {
                    console.log(`Notification: ${title}`, options.body);
                }
            }
            
            static requestPermission() {
                return Promise.resolve('denied');
            }
            
            close() {
                // No-op
            }
        };
        
        window.Notification.permission = 'denied';
    }
    
    // Public API
    isSupported(feature) {
        return this.features[feature] || false;
    }
    
    getBrowserInfo() {
        return { ...this.browserInfo };
    }
    
    getFeatures() {
        return { ...this.features };
    }
    
    getWebSocketSupport() {
        return { ...this.webSocketSupport };
    }
    
    // Check if the browser is considered modern
    isModernBrowser() {
        return this.browserInfo.isSupported && 
               this.features.es6Classes && 
               this.features.promises && 
               this.features.fetch;
    }
    
    // Get recommended actions for better compatibility
    getRecommendations() {
        const recommendations = [];
        
        if (!this.browserInfo.isSupported) {
            recommendations.push({
                type: 'browser',
                action: 'Update your browser to the latest version',
                priority: 'high'
            });
        }
        
        if (!this.features.webSocket) {
            recommendations.push({
                type: 'feature',
                action: 'Real-time features will be limited without WebSocket support',
                priority: 'medium'
            });
        }
        
        if (!this.features.localStorage) {
            recommendations.push({
                type: 'feature',
                action: 'Some settings may not persist without localStorage support',
                priority: 'medium'
            });
        }
        
        return recommendations;
    }
}

// Initialize browser compatibility checker
window.browserCompatibility = new BrowserCompatibility();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BrowserCompatibility;
}