/**
 * Language Persistence Manager
 * Handles language selection persistence across sessions and proper detection
 */

class LanguagePersistenceManager {
    constructor() {
        this.storageKey = 'preferred_language';
        this.sessionKey = 'session_language';
        this.availableLanguages = ['en', 'de', 'uk'];
        this.defaultLanguage = 'en';
        
        this.init();
    }

    init() {
        // Detect and set initial language
        const detectedLanguage = this.detectLanguage();
        this.setCurrentLanguage(detectedLanguage);
        
        // Listen for storage changes (for multi-tab synchronization)
        window.addEventListener('storage', (e) => {
            if (e.key === this.storageKey && e.newValue) {
                this.handleLanguageChangeFromStorage(e.newValue);
            }
        });

        // Listen for beforeunload to save session state
        window.addEventListener('beforeunload', () => {
            this.saveSessionState();
        });
    }

    detectLanguage() {
        console.log('Detecting language from multiple sources...');

        // 1. Check URL parameter (highest priority)
        const urlLanguage = this.getLanguageFromURL();
        if (urlLanguage) {
            console.log('Language detected from URL:', urlLanguage);
            this.persistLanguage(urlLanguage);
            return urlLanguage;
        }

        // 2. Check localStorage (user preference)
        const storedLanguage = this.getStoredLanguage();
        if (storedLanguage) {
            console.log('Language detected from localStorage:', storedLanguage);
            return storedLanguage;
        }

        // 3. Check sessionStorage (session preference)
        const sessionLanguage = this.getSessionLanguage();
        if (sessionLanguage) {
            console.log('Language detected from sessionStorage:', sessionLanguage);
            return sessionLanguage;
        }

        // 4. Check HTML lang attribute (server-side detection)
        const htmlLanguage = this.getHTMLLanguage();
        if (htmlLanguage) {
            console.log('Language detected from HTML lang attribute:', htmlLanguage);
            this.persistLanguage(htmlLanguage);
            return htmlLanguage;
        }

        // 5. Check browser language
        const browserLanguage = this.getBrowserLanguage();
        if (browserLanguage) {
            console.log('Language detected from browser:', browserLanguage);
            this.persistLanguage(browserLanguage);
            return browserLanguage;
        }

        // 6. Use default language
        console.log('Using default language:', this.defaultLanguage);
        this.persistLanguage(this.defaultLanguage);
        return this.defaultLanguage;
    }

    getLanguageFromURL() {
        try {
            const urlParams = new URLSearchParams(window.location.search);
            const lang = urlParams.get('lang');
            return this.validateLanguage(lang) ? lang : null;
        } catch (error) {
            console.warn('Error reading URL parameters:', error);
            return null;
        }
    }

    getStoredLanguage() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            return this.validateLanguage(stored) ? stored : null;
        } catch (error) {
            console.warn('Error reading from localStorage:', error);
            return null;
        }
    }

    getSessionLanguage() {
        try {
            const session = sessionStorage.getItem(this.sessionKey);
            return this.validateLanguage(session) ? session : null;
        } catch (error) {
            console.warn('Error reading from sessionStorage:', error);
            return null;
        }
    }

    getHTMLLanguage() {
        try {
            const htmlLang = document.documentElement.lang;
            return this.validateLanguage(htmlLang) ? htmlLang : null;
        } catch (error) {
            console.warn('Error reading HTML lang attribute:', error);
            return null;
        }
    }

    getBrowserLanguage() {
        try {
            // Check navigator.language and navigator.languages
            const languages = [
                navigator.language,
                ...(navigator.languages || [])
            ];

            for (const lang of languages) {
                if (lang) {
                    // Extract language code (e.g., 'en-US' -> 'en')
                    const langCode = lang.split('-')[0].toLowerCase();
                    if (this.validateLanguage(langCode)) {
                        return langCode;
                    }
                }
            }
        } catch (error) {
            console.warn('Error detecting browser language:', error);
        }
        return null;
    }

    validateLanguage(language) {
        return language && this.availableLanguages.includes(language.toLowerCase());
    }

    persistLanguage(language) {
        if (!this.validateLanguage(language)) {
            console.warn('Invalid language for persistence:', language);
            return false;
        }

        try {
            // Store in localStorage for long-term persistence
            localStorage.setItem(this.storageKey, language);
            
            // Store in sessionStorage for session-level tracking
            sessionStorage.setItem(this.sessionKey, language);
            
            // Update HTML lang attribute
            document.documentElement.lang = language;
            
            console.log('Language persisted:', language);
            return true;
        } catch (error) {
            console.error('Error persisting language:', error);
            return false;
        }
    }

    setCurrentLanguage(language) {
        if (!this.validateLanguage(language)) {
            console.warn('Invalid language:', language);
            return false;
        }

        // Persist the language
        this.persistLanguage(language);

        // Dispatch language change event
        this.dispatchLanguageChangeEvent(language);

        return true;
    }

    getCurrentLanguage() {
        return this.getStoredLanguage() || this.defaultLanguage;
    }

    clearLanguagePreference() {
        try {
            localStorage.removeItem(this.storageKey);
            sessionStorage.removeItem(this.sessionKey);
            console.log('Language preference cleared');
            return true;
        } catch (error) {
            console.error('Error clearing language preference:', error);
            return false;
        }
    }

    handleLanguageChangeFromStorage(newLanguage) {
        if (this.validateLanguage(newLanguage)) {
            console.log('Language changed from another tab:', newLanguage);
            
            // Update current page without reload
            document.documentElement.lang = newLanguage;
            sessionStorage.setItem(this.sessionKey, newLanguage);
            
            // Dispatch event for UI updates
            this.dispatchLanguageChangeEvent(newLanguage);
            
            // Update language switcher if available
            if (window.languageSwitcher && typeof window.languageSwitcher.updateCurrentLanguage === 'function') {
                window.languageSwitcher.updateCurrentLanguage(newLanguage);
            }
        }
    }

    saveSessionState() {
        const currentLanguage = this.getCurrentLanguage();
        if (currentLanguage) {
            sessionStorage.setItem(this.sessionKey, currentLanguage);
        }
    }

    dispatchLanguageChangeEvent(language) {
        const event = new CustomEvent('languagechange', {
            detail: { 
                language,
                source: 'persistence-manager',
                timestamp: Date.now()
            }
        });
        window.dispatchEvent(event);
    }

    // Method to sync with server-side language preference
    async syncWithServer(language) {
        if (!this.validateLanguage(language)) {
            return false;
        }

        try {
            const response = await fetch('/api/v1/user/language', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ language })
            });

            if (response.ok) {
                console.log('Language preference synced with server');
                return true;
            } else {
                console.warn('Failed to sync language preference with server:', response.status);
                return false;
            }
        } catch (error) {
            console.warn('Error syncing language preference with server:', error);
            return false;
        }
    }

    // Method to get language preference from server
    async getServerLanguagePreference() {
        try {
            const response = await fetch('/api/v1/user/language');
            
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.data.language) {
                    const serverLanguage = data.data.language;
                    if (this.validateLanguage(serverLanguage)) {
                        console.log('Server language preference:', serverLanguage);
                        return serverLanguage;
                    }
                }
            }
        } catch (error) {
            console.warn('Error getting server language preference:', error);
        }
        
        return null;
    }

    // Method to initialize with server preference
    async initializeWithServerPreference() {
        const serverLanguage = await this.getServerLanguagePreference();
        
        if (serverLanguage) {
            const currentLanguage = this.getCurrentLanguage();
            
            // If server preference differs from local, use server preference
            if (serverLanguage !== currentLanguage) {
                console.log('Using server language preference:', serverLanguage);
                this.setCurrentLanguage(serverLanguage);
                return serverLanguage;
            }
        }
        
        return this.getCurrentLanguage();
    }

    // Debug method to get current state
    getDebugInfo() {
        return {
            currentLanguage: this.getCurrentLanguage(),
            urlLanguage: this.getLanguageFromURL(),
            storedLanguage: this.getStoredLanguage(),
            sessionLanguage: this.getSessionLanguage(),
            htmlLanguage: this.getHTMLLanguage(),
            browserLanguage: this.getBrowserLanguage(),
            availableLanguages: this.availableLanguages,
            defaultLanguage: this.defaultLanguage
        };
    }
}

// Export for global use
window.LanguagePersistenceManager = LanguagePersistenceManager;