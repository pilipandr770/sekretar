/**
 * Enhanced Language Switcher for AI Secretary
 * Handles language switching with proper URL parameter handling,
 * translation context loading, and persistence across sessions
 */

class EnhancedLanguageSwitcher {
    constructor(options = {}) {
        this.containerId = options.containerId || 'language-switcher';
        this.availableLanguages = options.availableLanguages || {
            'en': 'English',
            'de': 'Deutsch', 
            'uk': 'Українська'
        };
        
        // Initialize persistence manager
        this.persistenceManager = new LanguagePersistenceManager();
        
        // Detect current language using persistence manager
        this.currentLanguage = this.persistenceManager.getCurrentLanguage();
        
        // State management
        this.isLoading = false;
        this.translationCache = new Map();
        
        this.init();
    }



    init() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.warn('Language switcher container not found:', this.containerId);
            return;
        }

        // Create language switcher HTML
        container.innerHTML = this.createSwitcherHTML();
        
        // Add event listeners
        this.addEventListeners();
        
        // Update HTML lang attribute
        document.documentElement.lang = this.currentLanguage;
        
        // Load translation context for current language
        this.loadTranslationContext();
    }

    createSwitcherHTML() {
        const currentLangName = this.availableLanguages[this.currentLanguage] || 'English';
        
        let html = `
            <div class="dropdown">
                <button class="btn btn-outline-light btn-sm dropdown-toggle" type="button" 
                        id="languageDropdown" data-bs-toggle="dropdown" aria-expanded="false"
                        ${this.isLoading ? 'disabled' : ''}>
                    ${this.isLoading ? '<span class="spinner-border spinner-border-sm me-1"></span>' : '🌐'} 
                    ${currentLangName}
                </button>
                <ul class="dropdown-menu" aria-labelledby="languageDropdown">
        `;
        
        for (const [code, name] of Object.entries(this.availableLanguages)) {
            const isActive = code === this.currentLanguage;
            html += `
                <li>
                    <a class="dropdown-item ${isActive ? 'active' : ''}" 
                       href="#" data-language="${code}"
                       ${this.isLoading ? 'style="pointer-events: none; opacity: 0.6;"' : ''}>
                        ${name} ${isActive ? '✓' : ''}
                    </a>
                </li>
            `;
        }
        
        html += `
                </ul>
            </div>
        `;
        
        return html;
    }

    addEventListeners() {
        const container = document.getElementById(this.containerId);
        if (!container) return;

        // Add click listeners to language links
        container.addEventListener('click', (e) => {
            if (e.target.matches('[data-language]')) {
                e.preventDefault();
                const language = e.target.dataset.language;
                this.switchLanguage(language);
            }
        });
    }

    async switchLanguage(language) {
        if (language === this.currentLanguage || this.isLoading) {
            return;
        }

        console.log(`Switching language from ${this.currentLanguage} to ${language}`);
        
        // Emit loading start event
        this.emitEvent('language:switch_start', { 
            language: language,
            languageName: this.availableLanguages[language] || language
        });
        
        // Set loading state
        this.setLoadingState(true);

        try {
            // 1. Persist language preference using persistence manager
            this.persistenceManager.setCurrentLanguage(language);
            
            // 2. Update server-side language preference
            await this.persistenceManager.syncWithServer(language);
            
            // 3. Load translation context for new language
            await this.loadTranslationContext(language);
            
            // 4. Update URL with language parameter and reload
            const url = new URL(window.location);
            url.searchParams.set('lang', language);
            
            // Emit success event
            this.emitEvent('language:switch_success', { 
                language: language,
                languageName: this.availableLanguages[language] || language
            });
            
            // Show success feedback before reload
            this.showLanguageChangeNotification(language);
            
            // Small delay to show the notification
            setTimeout(() => {
                window.location.href = url.toString();
            }, 500);
            
        } catch (error) {
            console.error('Failed to switch language:', error);
            
            // Emit error event
            this.emitEvent('language:switch_error', { 
                language: language,
                message: 'Failed to switch language',
                error: error
            });
            
            this.setLoadingState(false);
            
            // Fallback: direct page reload with language parameter
            try {
                const url = new URL(window.location);
                url.searchParams.set('lang', language);
                window.location.href = url.toString();
            } catch (urlError) {
                // Last resort fallback
                const separator = window.location.search ? '&' : '?';
                window.location.href = window.location.pathname + window.location.search + separator + 'lang=' + language;
            }
        }
    }

    async updateServerLanguage(language) {
        try {
            const response = await fetch('/api/v1/user/language', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ language: language })
            });

            if (!response.ok) {
                console.warn('Failed to update server language preference:', response.status);
                // Don't throw error - this is not critical for language switching
            } else {
                console.log('Server language preference updated successfully');
            }
        } catch (error) {
            console.warn('Could not update server language preference:', error);
            // Don't throw error - this is not critical for language switching
        }
    }

    async loadTranslationContext(language = null) {
        const targetLanguage = language || this.currentLanguage;
        
        try {
            // Check cache first
            if (this.translationCache.has(targetLanguage)) {
                console.log('Using cached translations for', targetLanguage);
                return this.translationCache.get(targetLanguage);
            }

            const response = await fetch(`/api/v1/i18n/translations/${targetLanguage}`);
            
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.data.translations) {
                    // Cache the translations
                    this.translationCache.set(targetLanguage, data.data.translations);
                    
                    // Update global i18n if available
                    if (window.i18n && typeof window.i18n.setLocale === 'function') {
                        await window.i18n.setLocale(targetLanguage);
                    }
                    
                    console.log('Translation context loaded for', targetLanguage);
                    return data.data.translations;
                }
            } else {
                console.warn('Failed to load translation context:', response.status);
            }
        } catch (error) {
            console.warn('Could not load translation context:', error);
        }
        
        return null;
    }

    setLoadingState(loading) {
        this.isLoading = loading;
        
        // Re-render to show/hide loading state
        const container = document.getElementById(this.containerId);
        if (container) {
            container.innerHTML = this.createSwitcherHTML();
            this.addEventListeners();
        }
    }

    showLanguageChangeNotification(language) {
        const languageName = this.availableLanguages[language] || language;
        
        // Create notification element
        const notification = document.createElement('div');
        notification.className = 'alert alert-success alert-dismissible fade show position-fixed';
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            <i class="fas fa-globe me-2"></i>
            Language changed to ${languageName}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 3000);
    }

    updateCurrentLanguage(language) {
        if (this.availableLanguages[language]) {
            this.currentLanguage = language;
            this.persistenceManager.setCurrentLanguage(language);
            this.init(); // Re-render
        }
    }

    getCurrentLanguage() {
        return this.currentLanguage;
    }

    getAvailableLanguages() {
        return this.availableLanguages;
    }

    // Method to update translatable elements on the page
    updateTranslatableElements() {
        const elements = document.querySelectorAll('[data-i18n]');
        elements.forEach(element => {
            const key = element.dataset.i18n;
            const params = element.dataset.i18nParams ? 
                JSON.parse(element.dataset.i18nParams) : {};
            
            // Use global translation function if available
            const translation = window._ ? window._(key, params) : key;
            
            if (element.tagName === 'INPUT' && (element.type === 'submit' || element.type === 'button')) {
                element.value = translation;
            } else if (element.hasAttribute('placeholder')) {
                element.placeholder = translation;
            } else if (element.hasAttribute('title')) {
                element.title = translation;
            } else {
                element.textContent = translation;
            }
        });
    }

    // Clear translation cache
    clearCache() {
        this.translationCache.clear();
    }
}

    /**
     * Emit custom events for loading states and user feedback
     */
    emitEvent(eventName, data = {}) {
        const event = new CustomEvent(eventName, { detail: data });
        document.dispatchEvent(event);
    }
}

// Export for global use
window.EnhancedLanguageSwitcher = EnhancedLanguageSwitcher;