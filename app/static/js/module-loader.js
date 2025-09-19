/**
 * Module Loader for AI Secretary
 * Handles lazy loading and dependency management for JavaScript modules
 */

class ModuleLoader {
    constructor() {
        this.loadedModules = new Set();
        this.loadingModules = new Map(); // Promise cache for modules being loaded
        this.dependencies = new Map();
        this.moduleCache = new Map();
        this.baseUrl = '/static/js/';
        
        // Browser compatibility checks
        this.browserSupport = this.checkBrowserSupport();
        
        // Performance monitoring
        this.loadTimes = new Map();
        
        this.init();
    }
    
    init() {
        // Define module dependencies
        this.defineDependencies();
        
        // Preload critical modules
        this.preloadCriticalModules();
        
        // Setup performance observer if available
        this.setupPerformanceMonitoring();
    }
    
    defineDependencies() {
        // Define which modules depend on others
        this.dependencies.set('auth-manager', ['error-handler', 'loading-manager']);
        this.dependencies.set('navigation-controller', ['auth-manager', 'ui-state-manager']);
        this.dependencies.set('websocket-client', ['auth-manager', 'error-handler']);
        this.dependencies.set('enhanced-language-switcher', ['language-switcher', 'language-persistence-manager']);
        this.dependencies.set('app', ['ui-state-manager', 'auth-manager', 'navigation-controller']);
        
        // Define optional modules (loaded on demand)
        this.dependencies.set('websocket-status-dashboard', ['websocket-client']);
        this.dependencies.set('api-tester', ['auth-manager']);
        this.dependencies.set('calendar-integration', ['auth-manager']);
        this.dependencies.set('crm-features', ['auth-manager']);
        this.dependencies.set('inbox-features', ['auth-manager']);
    }
    
    preloadCriticalModules() {
        // These modules are always needed
        const criticalModules = [
            'error-handler',
            'loading-manager',
            'ui-state-manager'
        ];
        
        criticalModules.forEach(module => {
            this.loadModule(module, { priority: 'high' });
        });
    }
    
    async loadModule(moduleName, options = {}) {
        const { priority = 'normal', timeout = 10000 } = options;
        
        // Return cached module if already loaded
        if (this.loadedModules.has(moduleName)) {
            return this.moduleCache.get(moduleName);
        }
        
        // Return existing promise if module is currently loading
        if (this.loadingModules.has(moduleName)) {
            return this.loadingModules.get(moduleName);
        }
        
        // Start loading process
        const loadPromise = this.doLoadModule(moduleName, { priority, timeout });
        this.loadingModules.set(moduleName, loadPromise);
        
        try {
            const result = await loadPromise;
            this.loadingModules.delete(moduleName);
            return result;
        } catch (error) {
            this.loadingModules.delete(moduleName);
            throw error;
        }
    }
    
    async doLoadModule(moduleName, options) {
        const startTime = performance.now();
        
        try {
            // Load dependencies first
            await this.loadDependencies(moduleName);
            
            // Load the module
            const moduleUrl = `${this.baseUrl}${moduleName}.js`;
            await this.loadScript(moduleUrl, options);
            
            // Mark as loaded
            this.loadedModules.add(moduleName);
            
            // Record load time
            const loadTime = performance.now() - startTime;
            this.loadTimes.set(moduleName, loadTime);
            
            console.log(`Module '${moduleName}' loaded in ${loadTime.toFixed(2)}ms`);
            
            // Cache the module if it exports something
            const moduleExport = window[this.getModuleGlobalName(moduleName)];
            if (moduleExport) {
                this.moduleCache.set(moduleName, moduleExport);
            }
            
            // Emit module loaded event
            this.emitModuleEvent('module:loaded', { moduleName, loadTime });
            
            return moduleExport;
            
        } catch (error) {
            console.error(`Failed to load module '${moduleName}':`, error);
            this.emitModuleEvent('module:error', { moduleName, error: error.message });
            throw error;
        }
    }
    
    async loadDependencies(moduleName) {
        const deps = this.dependencies.get(moduleName) || [];
        
        if (deps.length === 0) {
            return;
        }
        
        // Load dependencies in parallel
        const depPromises = deps.map(dep => this.loadModule(dep));
        await Promise.all(depPromises);
    }
    
    loadScript(url, options = {}) {
        return new Promise((resolve, reject) => {
            const { priority = 'normal', timeout = 10000 } = options;
            
            // Check if script is already loaded
            const existingScript = document.querySelector(`script[src="${url}"]`);
            if (existingScript) {
                if (existingScript.dataset.loaded === 'true') {
                    resolve();
                    return;
                } else {
                    // Wait for existing script to load
                    existingScript.addEventListener('load', resolve);
                    existingScript.addEventListener('error', reject);
                    return;
                }
            }
            
            const script = document.createElement('script');
            script.src = url;
            script.async = true;
            script.dataset.loaded = 'false';
            
            // Set loading priority if supported
            if ('importance' in script) {
                script.importance = priority === 'high' ? 'high' : 'auto';
            }
            
            // Set timeout
            const timeoutId = setTimeout(() => {
                script.remove();
                reject(new Error(`Script loading timeout: ${url}`));
            }, timeout);
            
            script.onload = () => {
                clearTimeout(timeoutId);
                script.dataset.loaded = 'true';
                resolve();
            };
            
            script.onerror = () => {
                clearTimeout(timeoutId);
                script.remove();
                reject(new Error(`Failed to load script: ${url}`));
            };
            
            // Insert script with appropriate priority
            if (priority === 'high') {
                document.head.insertBefore(script, document.head.firstChild);
            } else {
                document.head.appendChild(script);
            }
        });
    }
    
    getModuleGlobalName(moduleName) {
        // Convert module name to expected global variable name
        const nameMap = {
            'auth-manager': 'AuthenticationManager',
            'ui-state-manager': 'UIStateManager',
            'navigation-controller': 'NavigationController',
            'dropdown-manager': 'DropdownManager',
            'websocket-client': 'WebSocketClient',
            'language-switcher': 'LanguageSwitcher',
            'enhanced-language-switcher': 'EnhancedLanguageSwitcher',
            'language-persistence-manager': 'LanguagePersistenceManager',
            'error-handler': 'ErrorHandler',
            'loading-manager': 'LoadingManager'
        };
        
        return nameMap[moduleName] || moduleName;
    }
    
    // Lazy loading for page-specific features
    async loadPageFeatures(pageName) {
        const pageModules = {
            'inbox': ['inbox-features'],
            'crm': ['crm-features'],
            'calendar': ['calendar-features', 'calendar-integration'],
            'api-tester': ['api-tester'],
            'dashboard': ['websocket-status-dashboard']
        };
        
        const modules = pageModules[pageName] || [];
        
        if (modules.length > 0) {
            console.log(`Loading features for page: ${pageName}`);
            
            try {
                await Promise.all(modules.map(module => this.loadModule(module)));
                console.log(`Page features loaded for: ${pageName}`);
            } catch (error) {
                console.error(`Failed to load features for page ${pageName}:`, error);
            }
        }
    }
    
    // Browser compatibility checks
    checkBrowserSupport() {
        const support = {
            webSocket: 'WebSocket' in window,
            localStorage: 'localStorage' in window,
            fetch: 'fetch' in window,
            promises: 'Promise' in window,
            es6Classes: (() => {
                try {
                    eval('class Test {}');
                    return true;
                } catch (e) {
                    return false;
                }
            })(),
            modules: 'noModule' in document.createElement('script'),
            intersectionObserver: 'IntersectionObserver' in window,
            performanceObserver: 'PerformanceObserver' in window
        };
        
        // Log compatibility issues
        const unsupported = Object.entries(support)
            .filter(([feature, supported]) => !supported)
            .map(([feature]) => feature);
            
        if (unsupported.length > 0) {
            console.warn('Unsupported browser features:', unsupported);
        }
        
        return support;
    }
    
    // WebSocket compatibility check
    checkWebSocketSupport() {
        if (!this.browserSupport.webSocket) {
            console.warn('WebSocket not supported in this browser');
            return false;
        }
        
        // Check for specific WebSocket features
        try {
            const testSocket = new WebSocket('ws://test');
            testSocket.close();
            return true;
        } catch (error) {
            console.warn('WebSocket creation failed:', error);
            return false;
        }
    }
    
    // Performance monitoring
    setupPerformanceMonitoring() {
        if (!this.browserSupport.performanceObserver) {
            return;
        }
        
        try {
            const observer = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                entries.forEach(entry => {
                    if (entry.entryType === 'resource' && entry.name.includes('/static/js/')) {
                        const moduleName = entry.name.split('/').pop().replace('.js', '');
                        console.log(`Resource timing for ${moduleName}:`, {
                            duration: entry.duration,
                            transferSize: entry.transferSize,
                            encodedBodySize: entry.encodedBodySize
                        });
                    }
                });
            });
            
            observer.observe({ entryTypes: ['resource'] });
        } catch (error) {
            console.warn('Performance monitoring setup failed:', error);
        }
    }
    
    // Event system
    emitModuleEvent(eventName, data) {
        const event = new CustomEvent(eventName, { detail: data });
        document.dispatchEvent(event);
    }
    
    // Public API
    isModuleLoaded(moduleName) {
        return this.loadedModules.has(moduleName);
    }
    
    getLoadedModules() {
        return Array.from(this.loadedModules);
    }
    
    getLoadTimes() {
        return Object.fromEntries(this.loadTimes);
    }
    
    getBrowserSupport() {
        return { ...this.browserSupport };
    }
    
    // Preload modules for better performance
    preloadModules(moduleNames) {
        moduleNames.forEach(moduleName => {
            this.loadModule(moduleName, { priority: 'low' }).catch(error => {
                console.warn(`Preload failed for ${moduleName}:`, error);
            });
        });
    }
    
    // Clean up resources
    cleanup() {
        // Clear caches
        this.loadedModules.clear();
        this.loadingModules.clear();
        this.moduleCache.clear();
        this.loadTimes.clear();
    }
}

// Initialize module loader
window.moduleLoader = new ModuleLoader();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModuleLoader;
}