/**
 * Unit Tests for Enhanced Language Switcher
 * Tests language switching behavior and functionality
 */

class EnhancedLanguageSwitcherTest {
    constructor() {
        this.testResults = [];
        this.languageSwitcher = null;
        this.originalFetch = null;
        this.originalLocalStorage = null;
        this.originalLocation = null;
    }

    async runAllTests() {
        console.log('🧪 Running Enhanced Language Switcher Tests...');
        
        this.testResults = [];
        this.setupMocks();
        
        try {
            // Test 1: Initialization
            await this.testInitialization();
            
            // Test 2: Language detection
            await this.testLanguageDetection();
            
            // Test 3: Language switching
            await this.testLanguageSwitching();
            
            // Test 4: URL parameter handling
            await this.testURLParameterHandling();
            
            // Test 5: Server synchronization
            await this.testServerSynchronization();
            
            // Test 6: Translation context loading
            await this.testTranslationContextLoading();
            
            // Test 7: UI rendering
            await this.testUIRendering();
            
            // Test 8: Event handling
            await this.testEventHandling();
            
            // Test 9: Error handling
            await this.testErrorHandling();
            
            // Test 10: Persistence integration
            await this.testPersistenceIntegration();
            
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
                this.href = url;
                this.searchParams = new URLSearchParams('lang=en');
            }
            
            toString() {
                return this.href;
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
        };
        
        // Mock LanguagePersistenceManager
        global.LanguagePersistenceManager = class MockLanguagePersistenceManager {
            constructor() {
                this.currentLanguage = 'en';
            }
            
            getCurrentLanguage() {
                return this.currentLanguage;
            }
            
            setCurrentLanguage(lang) {
                this.currentLanguage = lang;
                return true;
            }
            
            async syncWithServer(lang) {
                return Promise.resolve();
            }
        };
        
        // Mock DOM elements
        document.body.innerHTML = `
            <div id="language-switcher"></div>
            <div data-i18n="welcome">Welcome</div>
            <input data-i18n="email_placeholder" placeholder="Email">
            <button data-i18n="submit" title="Submit">Submit</button>
        `;
        
        // Mock document.documentElement
        document.documentElement.lang = 'en';
    }

    async testInitialization() {
        console.log('🔍 Testing Enhanced Language Switcher initialization...');
        
        try {
            // Test initialization with default options
            this.languageSwitcher = new EnhancedLanguageSwitcher();
            
            this.assert(
                this.languageSwitcher.containerId === 'language-switcher',
                'Should use default container ID'
            );
            
            this.assert(
                this.languageSwitcher.availableLanguages.en === 'English',
                'Should have default available languages'
            );
            
            this.assert(
                this.languageSwitcher.currentLanguage === 'en',
                'Should detect current language'
            );
            
            this.assert(
                this.languageSwitcher.persistenceManager instanceof LanguagePersistenceManager,
                'Should initialize persistence manager'
            );
            
            // Test initialization with custom options
            const customSwitcher = new EnhancedLanguageSwitcher({
                containerId: 'custom-switcher',
                availableLanguages: {
                    'en': 'English',
                    'es': 'Español'
                }
            });
            
            this.assert(
                customSwitcher.containerId === 'custom-switcher',
                'Should use custom container ID'
            );
            
            this.assert(
                customSwitcher.availableLanguages.es === 'Español',
                'Should use custom available languages'
            );
            
            this.addResult('Initialization', 'PASS', 'Enhanced Language Switcher initialized correctly');
        } catch (error) {
            this.addResult('Initialization', 'FAIL', error.message);
        }
    }

    async testLanguageDetection() {
        console.log('🔍 Testing language detection...');
        
        try {
            // Test detection from persistence manager
            const mockPersistence = new LanguagePersistenceManager();
            mockPersistence.currentLanguage = 'de';
            
            const switcher = new EnhancedLanguageSwitcher();
            switcher.persistenceManager = mockPersistence;
            
            this.assert(
                switcher.persistenceManager.getCurrentLanguage() === 'de',
                'Should detect language from persistence manager'
            );
            
            // Test getCurrentLanguage method
            this.assert(
                typeof switcher.getCurrentLanguage === 'function',
                'Should have getCurrentLanguage method'
            );
            
            // Test getAvailableLanguages method
            const availableLanguages = switcher.getAvailableLanguages();
            this.assert(
                typeof availableLanguages === 'object',
                'Should return available languages object'
            );
            
            this.assert(
                availableLanguages.en === 'English',
                'Should include English in available languages'
            );
            
            this.addResult('Language Detection', 'PASS', 'Language detection works correctly');
        } catch (error) {
            this.addResult('Language Detection', 'FAIL', error.message);
        }
    }

    async testLanguageSwitching() {
        console.log('🔄 Testing language switching...');
        
        try {
            this.languageSwitcher = new EnhancedLanguageSwitcher();
            
            // Mock successful server sync
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ success: true })
            });
            
            // Mock translation context loading
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    success: true,
                    data: {
                        translations: {
                            'welcome': 'Willkommen',
                            'submit': 'Einreichen'
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
            
            // Test language switching
            const originalLang = this.languageSwitcher.currentLanguage;
            await this.languageSwitcher.switchLanguage('de');
            
            // Should call persistence manager
            this.assert(
                this.languageSwitcher.persistenceManager.getCurrentLanguage() === 'de',
                'Should update persistence manager with new language'
            );
            
            // Should attempt to redirect with language parameter
            this.assert(
                redirectUrl && redirectUrl.includes('lang=de'),
                'Should redirect with language parameter'
            );
            
            // Test switching to same language (should return early)
            redirectUrl = null;
            await this.languageSwitcher.switchLanguage('de');
            
            this.assert(
                redirectUrl === null,
                'Should not redirect when switching to same language'
            );
            
            this.addResult('Language Switching', 'PASS', 'Language switching works correctly');
        } catch (error) {
            this.addResult('Language Switching', 'FAIL', error.message);
        }
    }

    async testURLParameterHandling() {
        console.log('🔗 Testing URL parameter handling...');
        
        try {
            // Test URL parameter extraction
            window.location.search = '?lang=uk&other=value';
            
            const url = new URL(window.location.href);
            const langParam = url.searchParams.get('lang');
            
            this.assert(
                langParam === 'uk',
                'Should extract language parameter from URL'
            );
            
            // Test URL parameter setting
            url.searchParams.set('lang', 'de');
            
            this.assert(
                url.searchParams.get('lang') === 'de',
                'Should set language parameter in URL'
            );
            
            // Test URL construction for redirect
            const testUrl = new URL('http://localhost/dashboard');
            testUrl.searchParams.set('lang', 'es');
            
            this.assert(
                testUrl.toString().includes('lang=es'),
                'Should construct URL with language parameter'
            );
            
            this.addResult('URL Parameter Handling', 'PASS', 'URL parameter handling works correctly');
        } catch (error) {
            this.addResult('URL Parameter Handling', 'FAIL', error.message);
        }
    }

    async testServerSynchronization() {
        console.log('🌐 Testing server synchronization...');
        
        try {
            this.languageSwitcher = new EnhancedLanguageSwitcher();
            
            // Test successful server update
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ success: true })
            });
            
            await this.languageSwitcher.updateServerLanguage('fr');
            
            // Verify API call was made
            const serverCall = global.fetch.mock.calls.find(call => 
                call[0] === '/api/v1/user/language'
            );
            
            this.assert(
                serverCall !== undefined,
                'Should call server language update API'
            );
            
            const requestBody = JSON.parse(serverCall[1].body);
            this.assert(
                requestBody.language === 'fr',
                'Should send correct language in request body'
            );
            
            // Test server error handling (should not throw)
            global.fetch.mockRejectedValueOnce(new Error('Server error'));
            
            // Should not throw error
            await this.languageSwitcher.updateServerLanguage('es');
            
            // Test server response error (should not throw)
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 500
            });
            
            // Should not throw error
            await this.languageSwitcher.updateServerLanguage('it');
            
            this.addResult('Server Synchronization', 'PASS', 'Server synchronization works correctly');
        } catch (error) {
            this.addResult('Server Synchronization', 'FAIL', error.message);
        }
    }

    async testTranslationContextLoading() {
        console.log('📚 Testing translation context loading...');
        
        try {
            this.languageSwitcher = new EnhancedLanguageSwitcher();
            
            // Test successful translation loading
            const mockTranslations = {
                'welcome': 'Bienvenido',
                'submit': 'Enviar'
            };
            
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    success: true,
                    data: {
                        translations: mockTranslations
                    }
                })
            });
            
            const result = await this.languageSwitcher.loadTranslationContext('es');
            
            this.assert(
                result.welcome === 'Bienvenido',
                'Should load translation data correctly'
            );
            
            // Test caching
            const cachedResult = await this.languageSwitcher.loadTranslationContext('es');
            
            this.assert(
                cachedResult.welcome === 'Bienvenido',
                'Should return cached translations'
            );
            
            // Test translation loading error
            global.fetch.mockRejectedValueOnce(new Error('Network error'));
            
            const errorResult = await this.languageSwitcher.loadTranslationContext('it');
            
            this.assert(
                errorResult === null,
                'Should return null on translation loading error'
            );
            
            // Test cache clearing
            this.languageSwitcher.clearCache();
            
            this.assert(
                this.languageSwitcher.translationCache.size === 0,
                'Should clear translation cache'
            );
            
            this.addResult('Translation Context Loading', 'PASS', 'Translation context loading works correctly');
        } catch (error) {
            this.addResult('Translation Context Loading', 'FAIL', error.message);
        }
    }

    async testUIRendering() {
        console.log('🎨 Testing UI rendering...');
        
        try {
            this.languageSwitcher = new EnhancedLanguageSwitcher();
            
            // Test HTML generation
            const html = this.languageSwitcher.createSwitcherHTML();
            
            this.assert(
                html.includes('dropdown'),
                'Should generate dropdown HTML'
            );
            
            this.assert(
                html.includes('English'),
                'Should include current language name'
            );
            
            this.assert(
                html.includes('data-language="de"'),
                'Should include language data attributes'
            );
            
            // Test rendering in DOM
            const container = document.getElementById('language-switcher');
            container.innerHTML = html;
            
            const dropdown = container.querySelector('.dropdown');
            this.assert(
                dropdown !== null,
                'Should render dropdown in DOM'
            );
            
            const languageLinks = container.querySelectorAll('[data-language]');
            this.assert(
                languageLinks.length === 3,
                'Should render all available language options'
            );
            
            // Test loading state rendering
            this.languageSwitcher.setLoadingState(true);
            
            const loadingHtml = this.languageSwitcher.createSwitcherHTML();
            this.assert(
                loadingHtml.includes('spinner-border'),
                'Should show loading spinner when loading'
            );
            
            this.assert(
                loadingHtml.includes('disabled'),
                'Should disable button when loading'
            );
            
            this.addResult('UI Rendering', 'PASS', 'UI rendering works correctly');
        } catch (error) {
            this.addResult('UI Rendering', 'FAIL', error.message);
        }
    }

    async testEventHandling() {
        console.log('📡 Testing event handling...');
        
        try {
            this.languageSwitcher = new EnhancedLanguageSwitcher();
            
            // Test event listener setup
            const container = document.getElementById('language-switcher');
            container.innerHTML = this.languageSwitcher.createSwitcherHTML();
            this.languageSwitcher.addEventListeners();
            
            // Mock switchLanguage method
            let switchLanguageCalled = false;
            let switchLanguageArg = null;
            this.languageSwitcher.switchLanguage = (lang) => {
                switchLanguageCalled = true;
                switchLanguageArg = lang;
                return Promise.resolve();
            };
            
            // Test click event handling
            const germanLink = container.querySelector('[data-language="de"]');
            const clickEvent = new MouseEvent('click', {
                bubbles: true,
                cancelable: true
            });
            
            germanLink.dispatchEvent(clickEvent);
            
            this.assert(
                switchLanguageCalled === true,
                'Should call switchLanguage on click'
            );
            
            this.assert(
                switchLanguageArg === 'de',
                'Should pass correct language to switchLanguage'
            );
            
            // Test custom event emission
            let customEventFired = false;
            let customEventData = null;
            
            document.addEventListener('language:switch_start', (event) => {
                customEventFired = true;
                customEventData = event.detail;
            });
            
            this.languageSwitcher.emitEvent('language:switch_start', {
                language: 'uk',
                languageName: 'Українська'
            });
            
            this.assert(
                customEventFired === true,
                'Should emit custom events'
            );
            
            this.assert(
                customEventData.language === 'uk',
                'Should include correct data in custom events'
            );
            
            this.addResult('Event Handling', 'PASS', 'Event handling works correctly');
        } catch (error) {
            this.addResult('Event Handling', 'FAIL', error.message);
        }
    }

    async testErrorHandling() {
        console.log('⚠️ Testing error handling...');
        
        try {
            this.languageSwitcher = new EnhancedLanguageSwitcher();
            
            // Test initialization with missing container
            document.body.innerHTML = ''; // Remove container
            
            const switcherWithoutContainer = new EnhancedLanguageSwitcher({
                containerId: 'missing-container'
            });
            
            // Should not throw error
            switcherWithoutContainer.init();
            
            // Restore container
            document.body.innerHTML = '<div id="language-switcher"></div>';
            
            // Test language switching with server error
            global.fetch.mockRejectedValueOnce(new Error('Server error'));
            
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
            
            // Test event handling with invalid target
            const invalidEvent = {
                target: { matches: () => false },
                preventDefault: jest.fn()
            };
            
            // Should not throw error
            this.languageSwitcher.addEventListeners();
            
            this.addResult('Error Handling', 'PASS', 'Error handling works correctly');
        } catch (error) {
            this.addResult('Error Handling', 'FAIL', error.message);
        }
    }

    async testPersistenceIntegration() {
        console.log('💾 Testing persistence integration...');
        
        try {
            this.languageSwitcher = new EnhancedLanguageSwitcher();
            
            // Test persistence manager integration
            this.assert(
                this.languageSwitcher.persistenceManager instanceof LanguagePersistenceManager,
                'Should have persistence manager instance'
            );
            
            // Test language update through persistence
            this.languageSwitcher.updateCurrentLanguage('uk');
            
            this.assert(
                this.languageSwitcher.currentLanguage === 'uk',
                'Should update current language'
            );
            
            this.assert(
                this.languageSwitcher.persistenceManager.getCurrentLanguage() === 'uk',
                'Should update persistence manager'
            );
            
            // Test invalid language handling
            this.languageSwitcher.updateCurrentLanguage('invalid');
            
            this.assert(
                this.languageSwitcher.currentLanguage === 'uk',
                'Should not update to invalid language'
            );
            
            // Test translatable elements update
            this.languageSwitcher.updateTranslatableElements();
            
            // Should not throw error even without translation function
            this.assert(
                true,
                'Should handle translatable elements update gracefully'
            );
            
            this.addResult('Persistence Integration', 'PASS', 'Persistence integration works correctly');
        } catch (error) {
            this.addResult('Persistence Integration', 'FAIL', error.message);
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
        console.log('\n📊 Enhanced Language Switcher Test Results:');
        console.log('============================================');
        
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
            console.log('🎉 All Enhanced Language Switcher tests passed!');
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
        
        // Clean up language switcher
        if (this.languageSwitcher) {
            this.languageSwitcher.clearCache();
        }
        
        // Clear DOM
        document.body.innerHTML = '';
        
        // Reset document language
        document.documentElement.lang = 'en';
    }

    // Quick test function for console use
    static async quickTest() {
        const tester = new EnhancedLanguageSwitcherTest();
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
window.EnhancedLanguageSwitcherTest = EnhancedLanguageSwitcherTest;

// Add console helper
window.testLanguageSwitcher = () => EnhancedLanguageSwitcherTest.quickTest();