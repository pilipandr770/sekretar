/**
 * Frontend Internationalization (i18n) Client
 * Provides client-side translation, formatting, and dynamic language switching
 */

class I18nClient {
    constructor(locale = 'en', translations = {}) {
        this.locale = locale;
        this.translations = translations;
        this.fallbackLocale = 'en';
        this.cache = new Map();
        this.formatters = {};
        
        // Initialize formatters for the current locale
        this.initializeFormatters();
        
        // Bind methods to preserve context
        this.translate = this.translate.bind(this);
        this.formatDate = this.formatDate.bind(this);
        this.formatNumber = this.formatNumber.bind(this);
        this.formatCurrency = this.formatCurrency.bind(this);
        this.setLocale = this.setLocale.bind(this);
    }

    /**
     * Initialize locale-specific formatters
     */
    initializeFormatters() {
        try {
            // Date/time formatters
            this.formatters.date = new Intl.DateTimeFormat(this.locale);
            this.formatters.dateShort = new Intl.DateTimeFormat(this.locale, {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            });
            this.formatters.dateLong = new Intl.DateTimeFormat(this.locale, {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            this.formatters.time = new Intl.DateTimeFormat(this.locale, {
                hour: '2-digit',
                minute: '2-digit'
            });
            this.formatters.datetime = new Intl.DateTimeFormat(this.locale, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });

            // Number formatters
            this.formatters.number = new Intl.NumberFormat(this.locale);
            this.formatters.decimal = new Intl.NumberFormat(this.locale, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
            this.formatters.percent = new Intl.NumberFormat(this.locale, {
                style: 'percent'
            });

            // Currency formatters (default to EUR, can be overridden)
            this.formatters.currency = new Intl.NumberFormat(this.locale, {
                style: 'currency',
                currency: 'EUR'
            });

            // Relative time formatter
            if (Intl.RelativeTimeFormat) {
                this.formatters.relativeTime = new Intl.RelativeTimeFormat(this.locale, {
                    numeric: 'auto'
                });
            }
        } catch (error) {
            console.warn('Failed to initialize formatters for locale:', this.locale, error);
            // Fallback to basic formatters
            this.initializeFallbackFormatters();
        }
    }

    /**
     * Initialize fallback formatters when Intl API is not available
     */
    initializeFallbackFormatters() {
        this.formatters = {
            date: { format: (date) => date.toLocaleDateString() },
            dateShort: { format: (date) => date.toLocaleDateString() },
            dateLong: { format: (date) => date.toLocaleDateString() },
            time: { format: (date) => date.toLocaleTimeString() },
            datetime: { format: (date) => date.toLocaleString() },
            number: { format: (num) => num.toString() },
            decimal: { format: (num) => num.toFixed(2) },
            percent: { format: (num) => (num * 100).toFixed(1) + '%' },
            currency: { format: (num) => '€' + num.toFixed(2) }
        };
    }

    /**
     * Translate a key with optional parameters
     * @param {string} key - Translation key
     * @param {Object} params - Parameters for string interpolation
     * @returns {string} Translated string
     */
    translate(key, params = {}) {
        // Check cache first
        const cacheKey = `${key}:${JSON.stringify(params)}`;
        if (this.cache.has(cacheKey)) {
            return this.cache.get(cacheKey);
        }

        let translation = this.getTranslation(key);
        
        // Apply parameter substitution
        if (params && Object.keys(params).length > 0) {
            translation = this.interpolateParams(translation, params);
        }

        // Cache the result
        this.cache.set(cacheKey, translation);
        
        return translation;
    }

    /**
     * Get translation for a key with fallback logic
     * @param {string} key - Translation key
     * @returns {string} Translation or fallback
     */
    getTranslation(key) {
        // Try current locale
        if (this.translations[key]) {
            return this.translations[key];
        }

        // Try fallback locale if different
        if (this.locale !== this.fallbackLocale && window.i18nFallbackTranslations) {
            const fallback = window.i18nFallbackTranslations[key];
            if (fallback) {
                console.warn(`Translation missing for '${key}' in ${this.locale}, using fallback`);
                return fallback;
            }
        }

        // Return key as last resort
        console.warn(`Translation missing for key: ${key}`);
        return key;
    }

    /**
     * Interpolate parameters into translation string
     * @param {string} translation - Translation string with placeholders
     * @param {Object} params - Parameters to interpolate
     * @returns {string} Interpolated string
     */
    interpolateParams(translation, params) {
        return translation.replace(/\{\{(\w+)\}\}/g, (match, key) => {
            return params[key] !== undefined ? params[key] : match;
        }).replace(/%\((\w+)\)s/g, (match, key) => {
            return params[key] !== undefined ? params[key] : match;
        });
    }

    /**
     * Format date according to locale
     * @param {Date|string|number} date - Date to format
     * @param {string} format - Format type (short, long, time, datetime)
     * @returns {string} Formatted date
     */
    formatDate(date, format = 'short') {
        try {
            const dateObj = date instanceof Date ? date : new Date(date);
            
            if (isNaN(dateObj.getTime())) {
                return date.toString();
            }

            const formatter = this.formatters[`date${format.charAt(0).toUpperCase() + format.slice(1)}`] 
                            || this.formatters.date;
            
            return formatter.format(dateObj);
        } catch (error) {
            console.error('Date formatting error:', error);
            return date.toString();
        }
    }

    /**
     * Format number according to locale
     * @param {number} number - Number to format
     * @param {Object} options - Formatting options
     * @returns {string} Formatted number
     */
    formatNumber(number, options = {}) {
        try {
            const { style = 'decimal', minimumFractionDigits, maximumFractionDigits } = options;
            
            let formatter = this.formatters.number;
            
            if (style === 'decimal') {
                formatter = this.formatters.decimal;
            } else if (style === 'percent') {
                formatter = this.formatters.percent;
            }

            // Create custom formatter if specific options provided
            if (minimumFractionDigits !== undefined || maximumFractionDigits !== undefined) {
                const formatOptions = { ...options };
                delete formatOptions.style;
                formatter = new Intl.NumberFormat(this.locale, formatOptions);
            }

            return formatter.format(number);
        } catch (error) {
            console.error('Number formatting error:', error);
            return number.toString();
        }
    }

    /**
     * Format currency according to locale
     * @param {number} amount - Amount to format
     * @param {string} currency - Currency code (default: EUR)
     * @param {Object} options - Additional formatting options
     * @returns {string} Formatted currency
     */
    formatCurrency(amount, currency = 'EUR', options = {}) {
        try {
            const formatter = new Intl.NumberFormat(this.locale, {
                style: 'currency',
                currency: currency,
                ...options
            });
            
            return formatter.format(amount);
        } catch (error) {
            console.error('Currency formatting error:', error);
            // Fallback formatting
            return `${currency} ${amount.toFixed(2)}`;
        }
    }

    /**
     * Format relative time (e.g., "2 hours ago")
     * @param {Date|string|number} date - Date to compare
     * @param {Date} baseDate - Base date for comparison (default: now)
     * @returns {string} Relative time string
     */
    formatRelativeTime(date, baseDate = new Date()) {
        try {
            const dateObj = date instanceof Date ? date : new Date(date);
            const baseDateObj = baseDate instanceof Date ? baseDate : new Date(baseDate);
            
            if (isNaN(dateObj.getTime()) || isNaN(baseDateObj.getTime())) {
                return this.formatDate(date);
            }

            const diffMs = dateObj.getTime() - baseDateObj.getTime();
            const diffSeconds = Math.floor(diffMs / 1000);
            const diffMinutes = Math.floor(diffSeconds / 60);
            const diffHours = Math.floor(diffMinutes / 60);
            const diffDays = Math.floor(diffHours / 24);

            if (this.formatters.relativeTime) {
                if (Math.abs(diffDays) >= 1) {
                    return this.formatters.relativeTime.format(diffDays, 'day');
                } else if (Math.abs(diffHours) >= 1) {
                    return this.formatters.relativeTime.format(diffHours, 'hour');
                } else if (Math.abs(diffMinutes) >= 1) {
                    return this.formatters.relativeTime.format(diffMinutes, 'minute');
                } else {
                    return this.formatters.relativeTime.format(diffSeconds, 'second');
                }
            } else {
                // Fallback relative time formatting
                return this.formatRelativeTimeFallback(diffSeconds);
            }
        } catch (error) {
            console.error('Relative time formatting error:', error);
            return this.formatDate(date);
        }
    }

    /**
     * Fallback relative time formatting
     * @param {number} diffSeconds - Difference in seconds
     * @returns {string} Relative time string
     */
    formatRelativeTimeFallback(diffSeconds) {
        const absSeconds = Math.abs(diffSeconds);
        const isPast = diffSeconds < 0;
        
        const units = [
            { name: 'year', seconds: 31536000 },
            { name: 'month', seconds: 2592000 },
            { name: 'day', seconds: 86400 },
            { name: 'hour', seconds: 3600 },
            { name: 'minute', seconds: 60 },
            { name: 'second', seconds: 1 }
        ];

        for (const unit of units) {
            const count = Math.floor(absSeconds / unit.seconds);
            if (count >= 1) {
                const unitKey = count === 1 ? unit.name : `${unit.name}s`;
                const timeStr = `${count} ${this.translate(unitKey)}`;
                return isPast ? 
                    this.translate('time_ago', { time: timeStr }) : 
                    this.translate('in_time', { time: timeStr });
            }
        }

        return this.translate('just_now');
    }

    /**
     * Set new locale and reload translations
     * @param {string} locale - New locale code
     * @returns {Promise<boolean>} Success status
     */
    async setLocale(locale) {
        if (locale === this.locale) {
            return true;
        }

        const previousLocale = this.locale;

        try {
            // Load translations for new locale
            const success = await this.loadTranslations(locale);
            
            if (success) {
                this.locale = locale;
                this.initializeFormatters();
                this.clearCache();
                
                // Update HTML lang attribute
                document.documentElement.lang = locale;
                
                // Store in localStorage for persistence
                localStorage.setItem('preferred_language', locale);
                
                // Trigger locale change event
                this.dispatchLocaleChangeEvent(locale, previousLocale);
                
                // Update server-side locale preference
                await this.updateServerLocale(locale);
                
                console.log(`Locale changed from ${previousLocale} to ${locale}`);
                return true;
            }
            
            return false;
        } catch (error) {
            console.error('Failed to set locale:', error);
            return false;
        }
    }

    /**
     * Load translations for a specific locale
     * @param {string} locale - Locale code
     * @returns {Promise<boolean>} Success status
     */
    async loadTranslations(locale) {
        try {
            // Check if translations are already cached
            const cacheKey = `i18n_translations_${locale}`;
            const cached = localStorage.getItem(cacheKey);
            
            if (cached) {
                const { translations, timestamp } = JSON.parse(cached);
                // Use cached translations if less than 1 hour old
                if (Date.now() - timestamp < 3600000) {
                    this.translations = translations;
                    return true;
                }
            }

            // Fetch translations from server
            const response = await fetch(`/api/v1/i18n/translations/${locale}`);
            
            if (!response.ok) {
                throw new Error(`Failed to load translations: ${response.status}`);
            }

            const data = await response.json();
            this.translations = data.translations || {};

            // Cache translations
            localStorage.setItem(cacheKey, JSON.stringify({
                translations: this.translations,
                timestamp: Date.now()
            }));

            return true;
        } catch (error) {
            console.error('Failed to load translations:', error);
            return false;
        }
    }

    /**
     * Update server-side locale preference
     * @param {string} locale - Locale code
     * @returns {Promise<boolean>} Success status
     */
    async updateServerLocale(locale) {
        try {
            const response = await fetch('/api/v1/user/language', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ language: locale })
            });

            return response.ok;
        } catch (error) {
            console.error('Failed to update server locale:', error);
            return false;
        }
    }

    /**
     * Dispatch locale change event
     * @param {string} locale - New locale
     * @param {string} previousLocale - Previous locale
     */
    dispatchLocaleChangeEvent(locale, previousLocale) {
        const event = new CustomEvent('localechange', {
            detail: { locale, previousLocale }
        });
        window.dispatchEvent(event);
    }

    /**
     * Clear translation cache
     */
    clearCache() {
        this.cache.clear();
    }

    /**
     * Get current locale
     * @returns {string} Current locale code
     */
    getLocale() {
        return this.locale;
    }

    /**
     * Get available locales
     * @returns {Array<string>} Available locale codes
     */
    getAvailableLocales() {
        return window.i18nAvailableLocales || ['en', 'de', 'uk'];
    }

    /**
     * Check if locale is supported
     * @param {string} locale - Locale code to check
     * @returns {boolean} Whether locale is supported
     */
    isLocaleSupported(locale) {
        return this.getAvailableLocales().includes(locale);
    }

    /**
     * Pluralize based on count and locale rules
     * @param {number} count - Count for pluralization
     * @param {string} singular - Singular form key
     * @param {string} plural - Plural form key
     * @param {string} zero - Zero form key (optional)
     * @returns {string} Pluralized string
     */
    pluralize(count, singular, plural, zero = null) {
        if (count === 0 && zero) {
            return this.translate(zero, { count });
        }

        // Simple pluralization rules
        const key = count === 1 ? singular : plural;
        return this.translate(key, { count });
    }

    /**
     * Get translation statistics
     * @returns {Object} Translation statistics
     */
    getTranslationStats() {
        const totalKeys = Object.keys(this.translations).length;
        const translatedKeys = Object.values(this.translations).filter(v => v && v.trim()).length;
        
        return {
            locale: this.locale,
            totalKeys,
            translatedKeys,
            coverage: totalKeys > 0 ? (translatedKeys / totalKeys) * 100 : 0
        };
    }
}

// Global translation function
function _(key, params = {}) {
    return window.i18n ? window.i18n.translate(key, params) : key;
}

// Global formatting functions
function formatDate(date, format = 'short') {
    return window.i18n ? window.i18n.formatDate(date, format) : new Date(date).toLocaleDateString();
}

function formatNumber(number, options = {}) {
    return window.i18n ? window.i18n.formatNumber(number, options) : number.toString();
}

function formatCurrency(amount, currency = 'EUR', options = {}) {
    return window.i18n ? window.i18n.formatCurrency(amount, currency, options) : `${currency} ${amount.toFixed(2)}`;
}

function formatRelativeTime(date, baseDate = new Date()) {
    return window.i18n ? window.i18n.formatRelativeTime(date, baseDate) : new Date(date).toLocaleDateString();
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { I18nClient, _, formatDate, formatNumber, formatCurrency, formatRelativeTime };
}