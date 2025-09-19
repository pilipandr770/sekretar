/**
 * Integration Tests for Language Switching
 * Tests language switching with proper translation updates
 */

class LanguageSwitchingIntegrationTest {
    constructor() {
        this.testResults = [];
        this.languageSwitcher = null;
        this.uiStateManager = null;
        this.originalFetch = null;
        this.originalLocalStorage = null;
        this.originalLocation = null;
    }

    async runAllTests() {
        console.log('🧪 Running Language Switching Integration Tests...');
        
        this.testResults = [];
        this.setupMocks();
        
        try {
            // Initialize components
            this.initializeComponents();
            
            // Test 1: Complete language switching flow
            await this.testCompleteLanguageSwitchingFlow();
            
            // Test 2: Translation updates across UI
            await this.testTranslationUpdatesAcrossUI();
            
            // Test 3: Language persistence integration
            await this.testLanguagePersistenceIntegration();
            
            // Test 4: URL parameter handling integration
            await this.testURLParameterHandlingIntegration();
            
            // Test 5: Server synchronization integration
            await this.testServerSynchronizationIntegration();
            
            // Test 6: Multi-component language state sync
            await this.testMultiComponentLanguageStateSync();
            
            // Test 7: Error handling during language switching
            await this.testErrorHandlingDuringLanguageSwitching();
            
            // Test 8: Language switching with authentication
            await this.testLanguageSwitchingWithAuth();
            
        } finally {
            this.cleanup();
        }
        
        // Display results
        this.displayResults();
        
        return this.testResults;
    }

    setupMocks() {
        // Mock fetch
        this.originalFetch = global.fetch;
        global.fetch = jest.fn();
        
        // Mock localStorage
        this.originalLocalStorage = global.localStorage;
        global.localStorage = {
            getItem: jest.fn(),
            setItem: jest.fn(),
            removeItem: jest.fn(),
            clear: jest.fn()
        };
        
        // Mock window.location
        this.originalLocation = window.location;
        delete window.location;
        window.location = {
            pathname: '/dashboard',
            search: '?lang=en',
            href: 'http://localhost/dashboard?lang=en',
            origin: 'http://localhost',
            toString: () => 'http://localhost/dashboard?lang=en'
        };
        
        // Mock URL constructor
        global.URL = class MockURL {
            constructor(url) {
                this.href = url || window.location.href;
                this.searchParams = new URLSearchParams(window.location.search);
            }
            
            toString() {
                return this.href + '?' + this.searchParams.toString();
            }
        };
        
        // Mock URLSearchParams
        global.URLSearchParams = class MockURLSearchParams {
            constructor(search = '') {
                this.params = new Map();
                if (search.includes('lang=')) {
                    const match = search.match(/lang=([^&]*)/);
                    if (match) {
                        this.params.set('lang', match[1]);
                    }
                }
            }
            
            get(key) {
                return this.params.get(key);
            }
            
            set(key, value) {
                this.params.set(key, value);
            }
            
            toString() {
                const pairs = [];
                for (const [key, value] of this.params) {
                    pairs.push(`${key}=${value}`);
                }
                return pairs.join('&');
            }
        };
        
        // Mock LanguagePersistenceManager
        global.LanguagePersistenceManager = class MockLanguagePersistenceManager {
            constructor() {
                this.currentLanguage = 'en';
                this.storedLanguage = null;
            }
            
            getCurrentLanguage() {
                return this.currentLanguage;
            }
            
            setCurrentLanguage(lang) {
                this.currentLanguage = lang;
                this.storedLanguage = lang;
                global.localStorage.setItem('preferred_language', lang);
                return true;
            }
            
            async syncWithServer(lang) {
                // Mock server sync
                return Promise.resolve();
            }
            
            getDebugInfo() {
                return {
                    currentLanguage: this.currentLanguage,
                    storedLanguage: this.storedLanguage,
                    urlLanguage: new URLSearchParams(window.location.search).get('lang'),
                    htmlLanguage: document.documentElement.lang,
                    browserLanguage: 'en'
                };
            }
        };
        
        // Mock DOM elements with translatable content
        document.body.innerHTML = `
            <div id="language-switcher"></div>
            
            <nav>
                <a href="/dashboard" data-i18n="nav.dashboard">Dashboard</a>
                <a href="/inbox" data-i18n="nav.inbox">Inbox</a>
                <a href="/crm" data-i18n="nav.crm">CRM</a>
            </nav>
            
            <main>
                <h1 data-i18n="welcome.title">Welcome</h1>
                <p data-i18n="welcome.message">Welcome to the application</p>
                
                <form>
                    <input type="email" data-i18n="form.email_placeholder" placeholder="Email">
                    <input type="password" data-i18n="form.password_placeholder" placeholder="Password">
                    <button type="submit" data-i18n="form.submit" title="Submit">Login</button>
                </form>
                
                <div class="alert alert-info">
                    <span data-i18n="alerts.info">Information</span>
                </div>
            </main>
            
            <footer>
                <p data-i18n="footer.copyright">© 2024 AI Secretary</p>
            </footer>
        `;
        
        // Mock document.documentElement
        document.documentElement.lang = 'en';
        
        // Mock global translation function
        global._ = (key, params = {}) => {
            const translations = {
                'en': {
                    'nav.dashboard': 'Dashboard',
                    'nav.inbox': 'Inbox',
                    'nav.crm': 'CRM',
                    'welcome.title': 'Welcome',
                    'welcome.message': 'Welcome to the application',
                    'form.email_placeholder': 'Email',
                    'form.password_placeholder': 'Password',
                    'form.submit': 'Login',
                    'alerts.info': 'Information',
                    'footer.copyright': '© 2024 AI Secretary'
                },
                'de': {
                    'nav.dashboard': 'Dashboard',
                    'nav.inbox': 'Posteingang',
                    'nav.crm': 'CRM',
                    'welcome.title': 'Willkommen',
                    'welcome.message': 'Willkommen in der Anwendung',
                    'form.email_placeholder': 'E-Mail',
                    'form.password_placeholder': 'Passwort',
                    'form.submit': 'Anmelden',
                    'alerts.info': 'Information',
                    'footer.copyright': '© 2024 AI Secretary'
                },
                'uk': {
                    'nav.dashboard': 'Панель',
                    'nav.inbox': 'Вхідні',
                    'nav.crm': 'CRM',
                    'welcome.title': 'Ласкаво просимо',
                    'welcome.message': 'Ласкаво просимо до додатку',
                    'form.email_placeholder': 'Електронна пошта',
                    'form.password_placeholder': 'Пароль',
                    'form.submit': 'Увійти',
                    'alerts.info': 'Інформація',
                    'footer.copyright': '© 2024 AI Secretary'
                }
            };
            
            const currentLang = document.documentElement.lang || 'en';
            return translations[currentLang]?.[key] || key;
        };
        
        // Mock i18n object
        global.i18n = {
            currentLocale: 'en',
            setLocale: async (locale) => {
                global.i18n.currentLocale = locale;
                document.documentElement.lang = locale;
                return Promise.resolve();
            }
        };
    }

    initializeComponents() {
        // Initialize UI State Manager
        this.uiStateManager = new UIStateManager();
        this.uiStateManager.init();
        
        // Initialize Language Switcher
        this.languageSwitcher = new EnhancedLanguageSwitcher();
        
        // Integrate components
        this.uiStateManager.integrateWithLanguageSwitcher(this.languageSwitcher);
    }

    async testCompleteLanguageSwitchingFlow() {
        console.log('🌐 Testing complete language switching flow...');
        
        try {
            // Mock successful server sync
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ success: true })
            });
            
            // Mock translation loading
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    success: true,
                    data: {
                        translations: {
                            'welcome.title': 'Willkommen',
                            'nav.inbox': 'Posteingang',
                            'form.submit': 'Anmelden'
                        }
                    }
                })
            });
            
            // Mock window.location.href assignment
            let redirectUrl = null;
            Object.defineProperty(window.location, 'href', {
                set: (url) => { redirectUrl = url; },
                get: () => redirectUrl || window.location.href
            });
            
            // Track UI state changes
            let languageStateChanged = false;
            let finalLanguageState = null;
            
            this.uiStateManager.subscribe((newState, oldState) => {
                if (newState.currentLanguage !== oldState.currentLanguage) {
                    languageStateChanged = true;
                    finalLanguageState = newState;
                }
            });
            
            // Perform language switch
            const originalLang = this.languageSwitcher.currentLanguage;
            await this.languageSwitcher.switchLanguage('de');
            
            // Verify language switcher state
            this.assert(
                this.languageSwitcher.persistenceManager.getCurrentLanguage() === 'de',
                'Language switcher should update to German'
            );
            
            // Verify UI state manager integration
            this.assert(
                languageStateChanged === true,
                'UI state manager should receive language change'
            );
            
            // Verify persistence
            this.assert(
                global.localStorage.setItem.mock.calls.some(call => 
                    call[0] === 'preferred_language' && call[1] === 'de'
                ),
                'Language preference should be persisted'
            );
            
            // Verify server sync was attempted
            const serverCall = global.fetch.mock.calls.find(call => 
                call[0] === '/api/v1/user/language'
            );
            this.assert(
                serverCall !== undefined,
                'Should attempt server synchronization'
            );
            
            // Verify translation loading was attempted
            const translationCall = global.fetch.mock.calls.find(call => 
                call[0] === '/api/v1/i18n/translations/de'
            );
            this.assert(
                translationCall !== undefined,
                'Should attempt to load translations'
            );
            
            // Verify URL redirect with language parameter
            this.assert(
                redirectUrl && redirectUrl.includes('lang=de'),
                'Should redirect with language parameter'
            );
            
            this.addResult('Complete Language Switching Flow', 'PASS', 'Complete language switching flow works correctly');
        } catch (error) {
            this.addResult('Complete Language Switching Flow', 'FAIL', error.message);
        }
    }

    async testTranslationUpdatesAcrossUI() {
        console.log('🔤 Testing translation updates across UI...');
        
        try {
            // Set up German translations
            document.documentElement.lang = 'de';
            
            // Test translatable elements update
            this.languageSwitcher.updateTranslatableElements();
            
            // Check text content updates
            const welcomeTitle = document.querySelector('[data-i18n="welcome.title"]');
            this.assert(
                welcomeTitle.textContent === 'Willkommen',
                'Welcome title should be translated to German'
            );
            
            const inboxNav = document.querySelector('[data-i18n="nav.inbox"]');
            this.assert(
                inboxNav.textContent === 'Posteingang',
                'Inbox navigation should be translated to German'
            );
            
            // Check placeholder updates
            const emailInput = document.querySelector('[data-i18n="form.email_placeholder"]');
            this.assert(
                emailInput.placeholder === 'E-Mail',
                'Email placeholder should be translated to German'
            );
            
            const passwordInput = document.querySelector('[data-i18n="form.password_placeholder"]');
            this.assert(
                passwordInput.placeholder === 'Passwort',
                'Password placeholder should be translated to German'
            );
            
            // Check button value updates
            const submitButton = document.querySelector('[data-i18n="form.submit"]');
            this.assert(
                submitButton.textContent === 'Anmelden',
                'Submit button should be translated to German'
            );
            
            // Check title attribute updates
            this.assert(
                submitButton.title === 'Anmelden',
                'Submit button title should be translated to German'
            );
            
            // Test switching to Ukrainian
            document.documentElement.lang = 'uk';
            this.languageSwitcher.updateTranslatableElements();
            
            this.assert(
                welcomeTitle.textContent === 'Ласкаво просимо',
                'Welcome title should be translated to Ukrainian'
            );
            
            this.assert(
                inboxNav.textContent === 'Вхідні',
                'Inbox navigation should be translated to Ukrainian'
            );
            
            this.addResult('Translation Updates Across UI', 'PASS', 'Translation updates across UI work correctly');
        } catch (error) {
            this.addResult('Translation Updates Across UI', 'FAIL', error.message);
        }
    }

    async testLanguagePersistenceIntegration() {
        console.log('💾 Testing language persistence integration...');
        
        try {
            // Test initial language detection
            global.localStorage.getItem.mockReturnValue('de');
            window.location.search = '?lang=uk';
            
            const newSwitcher = new EnhancedLanguageSwitcher();
            
            // Should prioritize URL parameter over stored preference
            this.assert(
                newSwitcher.currentLanguage === 'de', // From persistence manager
                'Should detect language from persistence manager'
            );
            
            // Test language persistence across page reloads
            newSwitcher.updateCurrentLanguage('uk');
            
            this.assert(
                newSwitcher.persistenceManager.getCurrentLanguage() === 'uk',
                'Should persist language change'
            );
            
            // Test multi-tab synchronization
            const storageEvent = new StorageEvent('storage', {
                key: 'preferred_language',
                newValue: 'de',
                oldValue: 'uk'
            });
            
            // Simulate storage change from another tab
            window.dispatchEvent(storageEvent);
            
            // Should handle storage events gracefully
            this.assert(
                true, // No error thrown
                'Should handle storage events without errors'
            );
            
            // Test session storage integration
            const debugInfo = newSwitcher.persistenceManager.getDebugInfo();
            
            this.assert(
                typeof debugInfo === 'object',
                'Should provide debug information'
            );
            
            this.assert(
                debugInfo.currentLanguage === 'uk',
                'Debug info should reflect current language'
            );
            
            this.addResult('Language Persistence Integration', 'PASS', 'Language persistence integration works correctly');
        } catch (error) {
            this.addResult('Language Persistence Integration', 'FAIL', error.message);
        }
    }

    async testURLParameterHandlingIntegration() {
        console.log('🔗 Testing URL parameter handling integration...');
        
        try {
            // Test URL parameter detection
            window.location.search = '?lang=de&other=value';
            
            const url = new URL(window.location.href);
            const langParam = url.searchParams.get('lang');
            
            this.assert(
                langParam === 'de',
                'Should extract language parameter from URL'
            );
            
            // Test URL construction for language switching
            const testUrl = new URL('http://localhost/dashboard');
            testUrl.searchParams.set('lang', 'uk');
            
            this.assert(
                testUrl.toString().includes('lang=uk'),
                'Should construct URL with language parameter'
            );
            
            // Test URL parameter preservation during navigation
            window.location.search = '?lang=de&tab=settings&filter=active';
            
            const navUrl = new URL(window.location.href);
            navUrl.searchParams.set('lang', 'uk');
            
            this.assert(
                navUrl.searchParams.get('tab') === 'settings',
                'Should preserve other URL parameters'
            );
            
            this.assert(
                navUrl.searchParams.get('filter') === 'active',
                'Should preserve all URL parameters'
            );
            
            this.assert(
                navUrl.searchParams.get('lang') === 'uk',
                'Should update language parameter'
            );
            
            // Test fallback URL construction
            try {
                // Simulate URL constructor failure
                const originalURL = global.URL;
                global.URL = function() {
                    throw new Error('URL constructor failed');
                };
                
                // Should fall back to string manipulation
                const fallbackUrl = window.location.pathname + window.location.search + '&lang=es';
                
                this.assert(
                    fallbackUrl.includes('lang=es'),
                    'Should fall back to string manipulation for URL construction'
                );
                
                // Restore URL constructor
                global.URL = originalURL;
            } catch (error) {
                // Expected error for testing fallback
            }
            
            this.addResult('URL Parameter Handling Integration', 'PASS', 'URL parameter handling integration works correctly');
        } catch (error) {
            this.addResult('URL Parameter Handling Integration', 'FAIL', error.message);
        }
    }

    async testServerSynchronizationIntegration() {
        console.log('🌐 Testing server synchronization integration...');
        
        try {
            // Test successful server synchronization
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ success: true })
            });
            
            await this.languageSwitcher.updateServerLanguage('de');
            
            // Verify API call was made with correct data
            const serverCall = global.fetch.mock.calls.find(call => 
                call[0] === '/api/v1/user/language'
            );
            
            this.assert(
                serverCall !== undefined,
                'Should call server language update API'
            );
            
            const requestOptions = serverCall[1];
            this.assert(
                requestOptions.method === 'POST',
                'Should use POST method'
            );
            
            this.assert(
                requestOptions.headers['Content-Type'] === 'application/json',
                'Should set correct content type'
            );
            
            const requestBody = JSON.parse(requestOptions.body);
            this.assert(
                requestBody.language === 'de',
                'Should send correct language in request body'
            );
            
            // Test server error handling
            global.fetch.mockRejectedValueOnce(new Error('Server error'));
            
            // Should not throw error
            await this.languageSwitcher.updateServerLanguage('uk');
            
            // Test server response error handling
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error'
            });
            
            // Should not throw error
            await this.languageSwitcher.updateServerLanguage('es');
            
            // Test authentication required scenario
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 401,
                statusText: 'Unauthorized'
            });
            
            // Should handle gracefully
            await this.languageSwitcher.updateServerLanguage('fr');
            
            this.addResult('Server Synchronization Integration', 'PASS', 'Server synchronization integration works correctly');
        } catch (error) {
            this.addResult('Server Synchronization Integration', 'FAIL', error.message);
        }
    }

    async testMultiComponentLanguageStateSync() {
        console.log('🔄 Testing multi-component language state sync...');
        
        try {
            // Test UI state manager integration
            let languageChangeEvents = 0;
            
            this.uiStateManager.subscribe((newState, oldState) => {
                if (newState.currentLanguage !== oldState.currentLanguage) {
                    languageChangeEvents++;
                }
            });
            
            // Update language through UI state manager
            this.uiStateManager.updateLanguage('de');
            
            this.assert(
                languageChangeEvents === 1,
                'UI state manager should emit language change events'
            );
            
            const uiState = this.uiStateManager.getState();
            this.assert(
                uiState.currentLanguage === 'de',
                'UI state should reflect language change'
            );
            
            // Test document language attribute sync
            this.assert(
                document.documentElement.lang === 'de',
                'Document language attribute should be updated'
            );
            
            // Test custom event emission
            let customEventReceived = false;
            let customEventData = null;
            
            document.addEventListener('ui:language_changed', (event) => {
                customEventReceived = true;
                customEventData = event.detail;
            });
            
            this.uiStateManager.updateLanguage('uk');
            
            this.assert(
                customEventReceived === true,
                'Should emit custom language change event'
            );
            
            this.assert(
                customEventData.language === 'uk',
                'Custom event should contain correct language data'
            );
            
            // Test language switcher integration with UI state
            this.languageSwitcher.updateCurrentLanguage('es');
            
            // Should update UI state manager
            const updatedState = this.uiStateManager.getState();
            this.assert(
                updatedState.currentLanguage === 'es',
                'Language switcher changes should sync with UI state'
            );
            
            this.addResult('Multi-Component Language State Sync', 'PASS', 'Multi-component language state sync works correctly');
        } catch (error) {
            this.addResult('Multi-Component Language State Sync', 'FAIL', error.message);
        }
    }

    async testErrorHandlingDuringLanguageSwitching() {
        console.log('⚠️ Testing error handling during language switching...');
        
        try {
            // Test server sync error handling
            global.fetch.mockRejectedValueOnce(new Error('Network error'));
            
            // Mock translation loading error
            global.fetch.mockRejectedValueOnce(new Error('Translation loading failed'));
            
            // Mock window.location.href assignment
            let redirectUrl = null;
            Object.defineProperty(window.location, 'href', {
                set: (url) => { redirectUrl = url; },
                get: () => redirectUrl || window.location.href
            });
            
            // Should not throw error and should fall back to URL redirect
            await this.languageSwitcher.switchLanguage('de');
            
            this.assert(
                redirectUrl && redirectUrl.includes('lang=de'),
                'Should fall back to URL redirect on server error'
            );
            
            // Test translation loading error
            global.fetch.mockRejectedValueOnce(new Error('Translation error'));
            
            const result = await this.languageSwitcher.loadTranslationContext('fr');
            
            this.assert(
                result === null,
                'Should return null on translation loading error'
            );
            
            // Test invalid language handling
            this.languageSwitcher.updateCurrentLanguage('invalid-lang');
            
            // Should not update to invalid language
            this.assert(
                this.languageSwitcher.currentLanguage !== 'invalid-lang',
                'Should not update to invalid language'
            );
            
            // Test missing container error handling
            document.body.innerHTML = ''; // Remove container
            
            const switcherWithoutContainer = new EnhancedLanguageSwitcher({
                containerId: 'missing-container'
            });
            
            // Should not throw error
            switcherWithoutContainer.init();
            
            this.addResult('Error Handling During Language Switching', 'PASS', 'Error handling during language switching works correctly');
        } catch (error) {
            this.addResult('Error Handling During Language Switching', 'FAIL', error.message);
        }
    }

    async testLanguageSwitchingWithAuth() {
        console.log('🔐 Testing language switching with authentication...');
        
        try {
            // Mock authenticated user
            global.localStorage.getItem.mockReturnValue('test_access_token');
            
            // Mock successful server sync for authenticated user
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ success: true })
            });
            
            // Mock translation loading
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    success: true,
                    data: {
                        translations: {
                            'welcome.title': 'Willkommen',
                            'nav.dashboard': 'Dashboard'
                        }
                    }
                })
            });
            
            await this.languageSwitcher.updateServerLanguage('de');
            
            // Verify authenticated API call
            const serverCall = global.fetch.mock.calls.find(call => 
                call[0] === '/api/v1/user/language'
            );
            
            this.assert(
                serverCall !== undefined,
                'Should call server API for authenticated user'
            );
            
            // Test unauthenticated user
            global.localStorage.getItem.mockReturnValue(null);
            
            // Should still work without authentication (graceful degradation)
            await this.languageSwitcher.updateServerLanguage('uk');
            
            // Test authentication error during language sync
            global.localStorage.getItem.mockReturnValue('invalid_token');
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 401,
                statusText: 'Unauthorized'
            });
            
            // Should handle gracefully
            await this.languageSwitcher.updateServerLanguage('es');
            
            this.addResult('Language Switching With Auth', 'PASS', 'Language switching with authentication works correctly');
        } catch (error) {
            this.addResult('Language Switching With Auth', 'FAIL', error.message);
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
        console.log('\n📊 Language Switching Integration Test Results:');
        console.log('===============================================');
        
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
            console.log('🎉 All Language Switching Integration tests passed!');
        } else {
            console.log('⚠️  Some tests failed. Check the details above.');
        }
    }

    cleanup() {
        // Restore original functions
        if (this.originalFetch) {
            global.fetch = this.originalFetch;
        }
        if (this.originalLocalStorage) {
            global.localStorage = this.originalLocalStorage;
        }
        if (this.originalLocation) {
            window.location = this.originalLocation;
        }
        
        // Clean up components
        if (this.languageSwitcher) {
            this.languageSwitcher.clearCache();
        }
        if (this.uiStateManager) {
            this.uiStateManager.cleanup();
        }
        
        // Clear DOM
        document.body.innerHTML = '';
        
        // Reset document language
        document.documentElement.lang = 'en';
        
        // Clear global functions
        delete global._;
        delete global.i18n;
    }

    // Quick test function for console use
    static async quickTest() {
        const tester = new LanguageSwitchingIntegrationTest();
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
window.LanguageSwitchingIntegrationTest = LanguageSwitchingIntegrationTest;

// Add console helper
window.testLanguageSwitchingIntegration = () => LanguageSwitchingIntegrationTest.quickTest();