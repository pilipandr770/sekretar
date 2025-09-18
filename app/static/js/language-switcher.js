/**
 * Language Switcher Component
 * Provides UI for dynamic language switching
 */

class LanguageSwitcher {
    constructor(options = {}) {
        this.options = {
            containerId: 'language-switcher',
            showFlags: true,
            showNames: true,
            position: 'top-right',
            style: 'dropdown', // 'dropdown', 'buttons', 'select'
            ...options
        };

        this.languages = {
            en: { name: 'English', flag: '🇺🇸', nativeName: 'English' },
            de: { name: 'German', flag: '🇩🇪', nativeName: 'Deutsch' },
            uk: { name: 'Ukrainian', flag: '🇺🇦', nativeName: 'Українська' }
        };

        this.currentLanguage = window.i18n ? window.i18n.getLocale() : 'en';
        this.init();
    }

    /**
     * Initialize the language switcher
     */
    init() {
        this.createContainer();
        this.render();
        this.attachEventListeners();
        
        // Listen for locale changes
        window.addEventListener('localechange', (event) => {
            this.currentLanguage = event.detail.locale;
            this.updateUI();
        });
    }

    /**
     * Create the container element
     */
    createContainer() {
        let container = document.getElementById(this.options.containerId);
        
        if (!container) {
            container = document.createElement('div');
            container.id = this.options.containerId;
            container.className = `language-switcher language-switcher--${this.options.style}`;
            
            // Add to page based on position
            this.addToPage(container);
        }

        this.container = container;
    }

    /**
     * Add container to page based on position
     * @param {HTMLElement} container - Container element
     */
    addToPage(container) {
        const positions = {
            'top-right': () => {
                container.style.position = 'fixed';
                container.style.top = '20px';
                container.style.right = '20px';
                container.style.zIndex = '1000';
                document.body.appendChild(container);
            },
            'top-left': () => {
                container.style.position = 'fixed';
                container.style.top = '20px';
                container.style.left = '20px';
                container.style.zIndex = '1000';
                document.body.appendChild(container);
            },
            'navbar': () => {
                const navbar = document.querySelector('.navbar, .header, nav');
                if (navbar) {
                    navbar.appendChild(container);
                } else {
                    document.body.appendChild(container);
                }
            },
            'footer': () => {
                const footer = document.querySelector('.footer, footer');
                if (footer) {
                    footer.appendChild(container);
                } else {
                    document.body.appendChild(container);
                }
            }
        };

        const positionHandler = positions[this.options.position] || positions['top-right'];
        positionHandler();
    }

    /**
     * Render the language switcher UI
     */
    render() {
        const styles = {
            dropdown: () => this.renderDropdown(),
            buttons: () => this.renderButtons(),
            select: () => this.renderSelect()
        };

        const renderer = styles[this.options.style] || styles.dropdown;
        this.container.innerHTML = renderer();
    }

    /**
     * Render dropdown style switcher
     * @returns {string} HTML string
     */
    renderDropdown() {
        const currentLang = this.languages[this.currentLanguage];
        const otherLanguages = Object.entries(this.languages)
            .filter(([code]) => code !== this.currentLanguage);

        return `
            <div class="language-dropdown">
                <button class="language-dropdown__trigger" type="button" aria-haspopup="true" aria-expanded="false">
                    ${this.options.showFlags ? `<span class="language-flag">${currentLang.flag}</span>` : ''}
                    ${this.options.showNames ? `<span class="language-name">${currentLang.nativeName}</span>` : ''}
                    <span class="language-dropdown__arrow">▼</span>
                </button>
                <div class="language-dropdown__menu" role="menu">
                    ${otherLanguages.map(([code, lang]) => `
                        <button class="language-dropdown__item" 
                                type="button" 
                                role="menuitem" 
                                data-language="${code}"
                                title="${_('Switch to')} ${lang.name}">
                            ${this.options.showFlags ? `<span class="language-flag">${lang.flag}</span>` : ''}
                            ${this.options.showNames ? `<span class="language-name">${lang.nativeName}</span>` : ''}
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Render button style switcher
     * @returns {string} HTML string
     */
    renderButtons() {
        return `
            <div class="language-buttons">
                ${Object.entries(this.languages).map(([code, lang]) => `
                    <button class="language-button ${code === this.currentLanguage ? 'language-button--active' : ''}" 
                            type="button" 
                            data-language="${code}"
                            title="${_('Switch to')} ${lang.name}">
                        ${this.options.showFlags ? `<span class="language-flag">${lang.flag}</span>` : ''}
                        ${this.options.showNames ? `<span class="language-name">${lang.nativeName}</span>` : ''}
                    </button>
                `).join('')}
            </div>
        `;
    }

    /**
     * Render select style switcher
     * @returns {string} HTML string
     */
    renderSelect() {
        return `
            <div class="language-select">
                <label for="language-select-input" class="sr-only">${_('Select Language')}</label>
                <select id="language-select-input" class="language-select__input">
                    ${Object.entries(this.languages).map(([code, lang]) => `
                        <option value="${code}" ${code === this.currentLanguage ? 'selected' : ''}>
                            ${lang.nativeName}
                        </option>
                    `).join('')}
                </select>
            </div>
        `;
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Dropdown events
        const trigger = this.container.querySelector('.language-dropdown__trigger');
        if (trigger) {
            trigger.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleDropdown();
            });

            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!this.container.contains(e.target)) {
                    this.closeDropdown();
                }
            });
        }

        // Language selection events
        this.container.addEventListener('click', (e) => {
            const languageCode = e.target.closest('[data-language]')?.dataset.language;
            if (languageCode) {
                e.preventDefault();
                this.switchLanguage(languageCode);
            }
        });

        // Select change event
        const select = this.container.querySelector('.language-select__input');
        if (select) {
            select.addEventListener('change', (e) => {
                this.switchLanguage(e.target.value);
            });
        }

        // Keyboard navigation for dropdown
        this.container.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeDropdown();
            } else if (e.key === 'Enter' || e.key === ' ') {
                const focused = document.activeElement;
                if (focused.dataset.language) {
                    e.preventDefault();
                    this.switchLanguage(focused.dataset.language);
                }
            }
        });
    }

    /**
     * Toggle dropdown menu
     */
    toggleDropdown() {
        const menu = this.container.querySelector('.language-dropdown__menu');
        const trigger = this.container.querySelector('.language-dropdown__trigger');
        
        if (menu && trigger) {
            const isOpen = trigger.getAttribute('aria-expanded') === 'true';
            
            trigger.setAttribute('aria-expanded', !isOpen);
            menu.style.display = isOpen ? 'none' : 'block';
            
            if (!isOpen) {
                // Focus first menu item
                const firstItem = menu.querySelector('.language-dropdown__item');
                if (firstItem) {
                    firstItem.focus();
                }
            }
        }
    }

    /**
     * Close dropdown menu
     */
    closeDropdown() {
        const menu = this.container.querySelector('.language-dropdown__menu');
        const trigger = this.container.querySelector('.language-dropdown__trigger');
        
        if (menu && trigger) {
            trigger.setAttribute('aria-expanded', 'false');
            menu.style.display = 'none';
        }
    }

    /**
     * Switch to a different language
     * @param {string} languageCode - Language code to switch to
     */
    async switchLanguage(languageCode) {
        if (languageCode === this.currentLanguage) {
            return;
        }

        if (!this.languages[languageCode]) {
            console.error('Unsupported language:', languageCode);
            return;
        }

        // Show loading state
        this.showLoadingState();

        try {
            // Switch language using i18n client
            if (window.i18n) {
                const success = await window.i18n.setLocale(languageCode);
                
                if (success) {
                    this.currentLanguage = languageCode;
                    this.updateUI();
                    this.hideLoadingState();
                    
                    // Refresh page content
                    this.refreshPageContent();
                    
                    // Show success message
                    this.showMessage(_('Language switched successfully'), 'success');
                } else {
                    throw new Error('Failed to switch language');
                }
            } else {
                // Fallback: reload page with language parameter
                const url = new URL(window.location);
                url.searchParams.set('lang', languageCode);
                window.location.href = url.toString();
            }
        } catch (error) {
            console.error('Language switch failed:', error);
            this.hideLoadingState();
            this.showMessage(_('Failed to switch language'), 'error');
        }
    }

    /**
     * Update UI after language change
     */
    updateUI() {
        this.render();
        this.closeDropdown();
        
        // Update page title if it has a translation
        const titleElement = document.querySelector('title');
        if (titleElement && titleElement.dataset.i18nKey) {
            titleElement.textContent = _(titleElement.dataset.i18nKey);
        }
        
        // Update all elements with data-i18n attributes
        this.updateTranslatableElements();
    }

    /**
     * Update all translatable elements on the page
     */
    updateTranslatableElements() {
        const elements = document.querySelectorAll('[data-i18n]');
        
        elements.forEach(element => {
            const key = element.dataset.i18n;
            const params = element.dataset.i18nParams ? 
                JSON.parse(element.dataset.i18nParams) : {};
            
            if (element.tagName === 'INPUT' && (element.type === 'submit' || element.type === 'button')) {
                element.value = _(key, params);
            } else if (element.hasAttribute('placeholder')) {
                element.placeholder = _(key, params);
            } else if (element.hasAttribute('title')) {
                element.title = _(key, params);
            } else {
                element.textContent = _(key, params);
            }
        });
    }

    /**
     * Refresh page content that might need translation updates
     */
    refreshPageContent() {
        // Trigger custom event for components to refresh
        const event = new CustomEvent('languageChanged', {
            detail: { language: this.currentLanguage }
        });
        window.dispatchEvent(event);
        
        // Update form validation messages
        this.updateFormValidationMessages();
        
        // Update date/time displays
        this.updateDateTimeDisplays();
    }

    /**
     * Update form validation messages
     */
    updateFormValidationMessages() {
        const forms = document.querySelectorAll('form[data-i18n-validation]');
        
        forms.forEach(form => {
            const inputs = form.querySelectorAll('input, textarea, select');
            inputs.forEach(input => {
                if (input.validationMessage) {
                    // Trigger validation to update messages
                    input.checkValidity();
                }
            });
        });
    }

    /**
     * Update date/time displays
     */
    updateDateTimeDisplays() {
        const dateElements = document.querySelectorAll('[data-date], [data-datetime], [data-relative-time]');
        
        dateElements.forEach(element => {
            if (element.dataset.date) {
                const date = new Date(element.dataset.date);
                element.textContent = formatDate(date);
            } else if (element.dataset.datetime) {
                const date = new Date(element.dataset.datetime);
                element.textContent = formatDate(date, 'datetime');
            } else if (element.dataset.relativeTime) {
                const date = new Date(element.dataset.relativeTime);
                element.textContent = formatRelativeTime(date);
            }
        });
    }

    /**
     * Show loading state
     */
    showLoadingState() {
        this.container.classList.add('language-switcher--loading');
        
        const trigger = this.container.querySelector('.language-dropdown__trigger, .language-button--active');
        if (trigger) {
            trigger.disabled = true;
            trigger.style.opacity = '0.6';
        }
    }

    /**
     * Hide loading state
     */
    hideLoadingState() {
        this.container.classList.remove('language-switcher--loading');
        
        const trigger = this.container.querySelector('.language-dropdown__trigger, .language-button--active');
        if (trigger) {
            trigger.disabled = false;
            trigger.style.opacity = '1';
        }
    }

    /**
     * Show message to user
     * @param {string} message - Message to show
     * @param {string} type - Message type (success, error, info)
     */
    showMessage(message, type = 'info') {
        // Create or update message element
        let messageEl = document.getElementById('language-switcher-message');
        
        if (!messageEl) {
            messageEl = document.createElement('div');
            messageEl.id = 'language-switcher-message';
            messageEl.className = 'language-switcher-message';
            document.body.appendChild(messageEl);
        }

        messageEl.className = `language-switcher-message language-switcher-message--${type}`;
        messageEl.textContent = message;
        messageEl.style.display = 'block';

        // Auto-hide after 3 seconds
        setTimeout(() => {
            messageEl.style.display = 'none';
        }, 3000);
    }

    /**
     * Destroy the language switcher
     */
    destroy() {
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        
        // Remove message element
        const messageEl = document.getElementById('language-switcher-message');
        if (messageEl && messageEl.parentNode) {
            messageEl.parentNode.removeChild(messageEl);
        }
    }

    /**
     * Get current language
     * @returns {string} Current language code
     */
    getCurrentLanguage() {
        return this.currentLanguage;
    }

    /**
     * Get available languages
     * @returns {Object} Available languages
     */
    getAvailableLanguages() {
        return this.languages;
    }
}

// Auto-initialize if container exists
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('language-switcher') || document.querySelector('[data-language-switcher]')) {
        window.languageSwitcher = new LanguageSwitcher();
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LanguageSwitcher;
}