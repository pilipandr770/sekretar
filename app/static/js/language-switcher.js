/**
 * Simple Language Switcher for AI Secretary
 */

class LanguageSwitcher {
    constructor(options = {}) {
        this.containerId = options.containerId || 'language-switcher';
        this.availableLanguages = options.availableLanguages || {
            'en': 'English',
            'de': 'Deutsch', 
            'uk': 'Українська'
        };
        
        // Detect current language from multiple sources
        this.currentLanguage = this.detectCurrentLanguage(options.currentLanguage);
        
        this.init();
    }

    detectCurrentLanguage(fallbackLanguage = 'en') {
        // 1. Check URL parameter (highest priority)
        const urlParams = new URLSearchParams(window.location.search);
        const urlLang = urlParams.get('lang');
        if (urlLang && this.availableLanguages[urlLang]) {
            console.log('Language detected from URL:', urlLang);
            return urlLang;
        }

        // 2. Check localStorage
        const storedLang = localStorage.getItem('preferred_language');
        if (storedLang && this.availableLanguages[storedLang]) {
            console.log('Language detected from localStorage:', storedLang);
            return storedLang;
        }

        // 3. Check HTML lang attribute
        const htmlLang = document.documentElement.lang;
        if (htmlLang && this.availableLanguages[htmlLang]) {
            console.log('Language detected from HTML lang attribute:', htmlLang);
            return htmlLang;
        }

        // 4. Use provided fallback or default
        const finalLang = fallbackLanguage || 'en';
        console.log('Using fallback language:', finalLang);
        return finalLang;
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
    }

    createSwitcherHTML() {
        const currentLangName = this.availableLanguages[this.currentLanguage] || 'English';
        
        let html = `
            <div class="dropdown">
                <button class="btn btn-outline-light btn-sm dropdown-toggle" type="button" 
                        id="languageDropdown" data-bs-toggle="dropdown" aria-expanded="false">
                    🌐 ${currentLangName}
                </button>
                <ul class="dropdown-menu" aria-labelledby="languageDropdown">
        `;
        
        for (const [code, name] of Object.entries(this.availableLanguages)) {
            const isActive = code === this.currentLanguage;
            html += `
                <li>
                    <a class="dropdown-item ${isActive ? 'active' : ''}" 
                       href="#" data-language="${code}">
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
        if (language === this.currentLanguage) {
            return;
        }

        try {
            console.log(`Switching language from ${this.currentLanguage} to ${language}`);
            
            // First, update server-side language preference
            await this.updateServerLanguage(language);
            
            // Update URL with language parameter
            const url = new URL(window.location);
            url.searchParams.set('lang', language);
            
            // Store the language preference in localStorage for immediate access
            localStorage.setItem('preferred_language', language);
            
            // Reload page with new language
            window.location.href = url.toString();
            
        } catch (error) {
            console.error('Failed to switch language:', error);
            
            // Fallback: simple page reload with language parameter
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
            } else {
                console.log('Server language preference updated successfully');
            }
        } catch (error) {
            console.warn('Could not update server language preference:', error);
            // Don't throw error - this is not critical for language switching
        }
    }

    updateCurrentLanguage(language) {
        this.currentLanguage = language;
        this.init(); // Re-render
    }
}

// Export for global use
window.LanguageSwitcher = LanguageSwitcher;