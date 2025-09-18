/**
 * Client-side localization utilities for advanced formatting
 */
class LocalizationClient {
    constructor(locale = 'en', options = {}) {
        this.locale = locale;
        this.options = {
            currency: 'EUR',
            timezone: 'UTC',
            ...options
        };
        
        // Initialize Intl formatters
        this.initializeFormatters();
        
        // Cache for relative time strings
        this.relativeTimeCache = new Map();
        this.relativeTimeStrings = this.getRelativeTimeStrings();
    }
    
    initializeFormatters() {
        try {
            // Date formatters
            this.dateFormatters = {
                short: new Intl.DateTimeFormat(this.locale, { 
                    year: 'numeric', 
                    month: 'numeric', 
                    day: 'numeric' 
                }),
                medium: new Intl.DateTimeFormat(this.locale, { 
                    year: 'numeric', 
                    month: 'short', 
                    day: 'numeric' 
                }),
                long: new Intl.DateTimeFormat(this.locale, { 
                    year: 'numeric', 
                    month: 'long', 
                    day: 'numeric' 
                }),
                full: new Intl.DateTimeFormat(this.locale, { 
                    weekday: 'long',
                    year: 'numeric', 
                    month: 'long', 
                    day: 'numeric' 
                })
            };
            
            // Time formatters
            this.timeFormatters = {
                short: new Intl.DateTimeFormat(this.locale, { 
                    hour: 'numeric', 
                    minute: 'numeric' 
                }),
                medium: new Intl.DateTimeFormat(this.locale, { 
                    hour: 'numeric', 
                    minute: 'numeric', 
                    second: 'numeric' 
                }),
                long: new Intl.DateTimeFormat(this.locale, { 
                    hour: 'numeric', 
                    minute: 'numeric', 
                    second: 'numeric',
                    timeZoneName: 'short'
                })
            };
            
            // DateTime formatters
            this.dateTimeFormatters = {
                short: new Intl.DateTimeFormat(this.locale, { 
                    year: 'numeric', 
                    month: 'numeric', 
                    day: 'numeric',
                    hour: 'numeric', 
                    minute: 'numeric' 
                }),
                medium: new Intl.DateTimeFormat(this.locale, { 
                    year: 'numeric', 
                    month: 'short', 
                    day: 'numeric',
                    hour: 'numeric', 
                    minute: 'numeric', 
                    second: 'numeric' 
                }),
                long: new Intl.DateTimeFormat(this.locale, { 
                    year: 'numeric', 
                    month: 'long', 
                    day: 'numeric',
                    hour: 'numeric', 
                    minute: 'numeric', 
                    second: 'numeric',
                    timeZoneName: 'short'
                })
            };
            
            // Number formatters
            this.numberFormatter = new Intl.NumberFormat(this.locale);
            this.percentFormatter = new Intl.NumberFormat(this.locale, { 
                style: 'percent',
                minimumFractionDigits: 1,
                maximumFractionDigits: 2
            });
            
            // Currency formatters
            this.currencyFormatters = {};
            const currencies = ['EUR', 'USD', 'GBP', 'UAH'];
            currencies.forEach(currency => {
                this.currencyFormatters[currency] = new Intl.NumberFormat(this.locale, {
                    style: 'currency',
                    currency: currency
                });
            });
            
            // Relative time formatter (if supported)
            if (Intl.RelativeTimeFormat) {
                this.relativeTimeFormatter = new Intl.RelativeTimeFormat(this.locale, {
                    numeric: 'auto'
                });
            }
            
        } catch (error) {
            console.warn('Failed to initialize Intl formatters:', error);
            this.fallbackMode = true;
        }
    }
    
    formatDate(date, format = 'medium') {
        if (!date) return '';
        
        const dateObj = date instanceof Date ? date : new Date(date);
        
        if (this.fallbackMode || !this.dateFormatters[format]) {
            return this.fallbackDateFormat(dateObj, format);
        }
        
        try {
            return this.dateFormatters[format].format(dateObj);
        } catch (error) {
            console.warn('Date formatting error:', error);
            return this.fallbackDateFormat(dateObj, format);
        }
    }
    
    formatTime(date, format = 'short') {
        if (!date) return '';
        
        const dateObj = date instanceof Date ? date : new Date(date);
        
        if (this.fallbackMode || !this.timeFormatters[format]) {
            return this.fallbackTimeFormat(dateObj, format);
        }
        
        try {
            return this.timeFormatters[format].format(dateObj);
        } catch (error) {
            console.warn('Time formatting error:', error);
            return this.fallbackTimeFormat(dateObj, format);
        }
    }
    
    formatDateTime(date, format = 'medium') {
        if (!date) return '';
        
        const dateObj = date instanceof Date ? date : new Date(date);
        
        if (this.fallbackMode || !this.dateTimeFormatters[format]) {
            return this.fallbackDateTimeFormat(dateObj, format);
        }
        
        try {
            return this.dateTimeFormatters[format].format(dateObj);
        } catch (error) {
            console.warn('DateTime formatting error:', error);
            return this.fallbackDateTimeFormat(dateObj, format);
        }
    }
    
    formatNumber(number, options = {}) {
        if (number === null || number === undefined) return '';
        
        if (this.fallbackMode) {
            return this.fallbackNumberFormat(number);
        }
        
        try {
            if (options.style || options.currency) {
                const formatter = new Intl.NumberFormat(this.locale, options);
                return formatter.format(number);
            }
            return this.numberFormatter.format(number);
        } catch (error) {
            console.warn('Number formatting error:', error);
            return this.fallbackNumberFormat(number);
        }
    }
    
    formatCurrency(amount, currency = null) {
        if (amount === null || amount === undefined) return '';
        
        const currencyCode = currency || this.options.currency;
        
        if (this.fallbackMode || !this.currencyFormatters[currencyCode]) {
            return this.fallbackCurrencyFormat(amount, currencyCode);
        }
        
        try {
            return this.currencyFormatters[currencyCode].format(amount);
        } catch (error) {
            console.warn('Currency formatting error:', error);
            return this.fallbackCurrencyFormat(amount, currencyCode);
        }
    }
    
    formatPercent(number) {
        if (number === null || number === undefined) return '';
        
        if (this.fallbackMode) {
            return `${(number * 100).toFixed(1)}%`;
        }
        
        try {
            return this.percentFormatter.format(number);
        } catch (error) {
            console.warn('Percent formatting error:', error);
            return `${(number * 100).toFixed(1)}%`;
        }
    }
    
    formatRelativeTime(date) {
        if (!date) return '';
        
        const dateObj = date instanceof Date ? date : new Date(date);
        const now = new Date();
        const diffMs = dateObj.getTime() - now.getTime();
        const diffSeconds = Math.floor(diffMs / 1000);
        const diffMinutes = Math.floor(diffSeconds / 60);
        const diffHours = Math.floor(diffMinutes / 60);
        const diffDays = Math.floor(diffHours / 24);
        
        // Use cached result if available
        const cacheKey = `${diffSeconds}_${this.locale}`;
        if (this.relativeTimeCache.has(cacheKey)) {
            return this.relativeTimeCache.get(cacheKey);
        }
        
        let result;
        
        if (this.relativeTimeFormatter && Math.abs(diffDays) < 7) {
            try {
                if (Math.abs(diffDays) >= 1) {
                    result = this.relativeTimeFormatter.format(diffDays, 'day');
                } else if (Math.abs(diffHours) >= 1) {
                    result = this.relativeTimeFormatter.format(diffHours, 'hour');
                } else if (Math.abs(diffMinutes) >= 1) {
                    result = this.relativeTimeFormatter.format(diffMinutes, 'minute');
                } else {
                    result = this.relativeTimeStrings.now;
                }
            } catch (error) {
                console.warn('Relative time formatting error:', error);
                result = this.fallbackRelativeTime(diffSeconds, diffMinutes, diffHours, diffDays);
            }
        } else {
            result = this.fallbackRelativeTime(diffSeconds, diffMinutes, diffHours, diffDays);
        }
        
        // Cache the result
        this.relativeTimeCache.set(cacheKey, result);
        
        // Clear cache periodically to prevent memory leaks
        if (this.relativeTimeCache.size > 100) {
            const firstKey = this.relativeTimeCache.keys().next().value;
            this.relativeTimeCache.delete(firstKey);
        }
        
        return result;
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        
        const sizes = this.getFileSizeUnits();
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        const size = bytes / Math.pow(1024, i);
        
        return `${this.formatNumber(size, { maximumFractionDigits: 2 })} ${sizes[i]}`;
    }
    
    pluralize(count, singular, plural = null) {
        // Simple pluralization - can be enhanced with proper locale rules
        if (count === 1) {
            return singular;
        }
        
        if (plural) {
            return plural;
        }
        
        // Basic English pluralization rules
        if (singular.endsWith('y')) {
            return singular.slice(0, -1) + 'ies';
        } else if (singular.endsWith('s') || singular.endsWith('sh') || 
                   singular.endsWith('ch') || singular.endsWith('x') || 
                   singular.endsWith('z')) {
            return singular + 'es';
        } else {
            return singular + 's';
        }
    }
    
    // Fallback formatting methods
    fallbackDateFormat(date, format) {
        const options = {
            short: { year: 'numeric', month: 'numeric', day: 'numeric' },
            medium: { year: 'numeric', month: 'short', day: 'numeric' },
            long: { year: 'numeric', month: 'long', day: 'numeric' },
            full: { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }
        };
        
        return date.toLocaleDateString(this.locale, options[format] || options.medium);
    }
    
    fallbackTimeFormat(date, format) {
        const options = {
            short: { hour: 'numeric', minute: 'numeric' },
            medium: { hour: 'numeric', minute: 'numeric', second: 'numeric' },
            long: { hour: 'numeric', minute: 'numeric', second: 'numeric', timeZoneName: 'short' }
        };
        
        return date.toLocaleTimeString(this.locale, options[format] || options.short);
    }
    
    fallbackDateTimeFormat(date, format) {
        return `${this.fallbackDateFormat(date, format)} ${this.fallbackTimeFormat(date, 'short')}`;
    }
    
    fallbackNumberFormat(number) {
        return number.toLocaleString(this.locale);
    }
    
    fallbackCurrencyFormat(amount, currency) {
        const formatted = this.fallbackNumberFormat(amount);
        return `${currency} ${formatted}`;
    }
    
    fallbackRelativeTime(diffSeconds, diffMinutes, diffHours, diffDays) {
        const strings = this.relativeTimeStrings;
        
        if (Math.abs(diffDays) >= 1) {
            return diffDays > 0 ? 
                strings.in_days.replace('{n}', Math.abs(diffDays)) :
                strings.days_ago.replace('{n}', Math.abs(diffDays));
        } else if (Math.abs(diffHours) >= 1) {
            return diffHours > 0 ? 
                strings.in_hours.replace('{n}', Math.abs(diffHours)) :
                strings.hours_ago.replace('{n}', Math.abs(diffHours));
        } else if (Math.abs(diffMinutes) >= 1) {
            return diffMinutes > 0 ? 
                strings.in_minutes.replace('{n}', Math.abs(diffMinutes)) :
                strings.minutes_ago.replace('{n}', Math.abs(diffMinutes));
        } else {
            return strings.now;
        }
    }
    
    getRelativeTimeStrings() {
        const strings = {
            'en': {
                now: 'just now',
                in_minutes: 'in {n} minute(s)',
                minutes_ago: '{n} minute(s) ago',
                in_hours: 'in {n} hour(s)',
                hours_ago: '{n} hour(s) ago',
                in_days: 'in {n} day(s)',
                days_ago: '{n} day(s) ago'
            },
            'de': {
                now: 'gerade eben',
                in_minutes: 'in {n} Minute(n)',
                minutes_ago: 'vor {n} Minute(n)',
                in_hours: 'in {n} Stunde(n)',
                hours_ago: 'vor {n} Stunde(n)',
                in_days: 'in {n} Tag(en)',
                days_ago: 'vor {n} Tag(en)'
            },
            'uk': {
                now: 'щойно',
                in_minutes: 'через {n} хвилин(у/и)',
                minutes_ago: '{n} хвилин(у/и) тому',
                in_hours: 'через {n} годин(у/и)',
                hours_ago: '{n} годин(у/и) тому',
                in_days: 'через {n} дні(в)',
                days_ago: '{n} дні(в) тому'
            }
        };
        
        return strings[this.locale] || strings['en'];
    }
    
    getFileSizeUnits() {
        const units = {
            'en': ['B', 'KB', 'MB', 'GB', 'TB'],
            'de': ['B', 'KB', 'MB', 'GB', 'TB'],
            'uk': ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
        };
        
        return units[this.locale] || units['en'];
    }
    
    setLocale(locale) {
        if (this.locale !== locale) {
            this.locale = locale;
            this.relativeTimeCache.clear();
            this.relativeTimeStrings = this.getRelativeTimeStrings();
            this.initializeFormatters();
        }
    }
    
    // Utility methods for DOM manipulation
    updateElementsWithLocalization() {
        // Update elements with data-localize attributes
        document.querySelectorAll('[data-localize]').forEach(element => {
            const type = element.dataset.localize;
            const value = element.dataset.value;
            
            if (!value) return;
            
            try {
                switch (type) {
                    case 'date':
                        const format = element.dataset.format || 'medium';
                        element.textContent = this.formatDate(value, format);
                        break;
                    case 'time':
                        const timeFormat = element.dataset.format || 'short';
                        element.textContent = this.formatTime(value, timeFormat);
                        break;
                    case 'datetime':
                        const dtFormat = element.dataset.format || 'medium';
                        element.textContent = this.formatDateTime(value, dtFormat);
                        break;
                    case 'number':
                        element.textContent = this.formatNumber(parseFloat(value));
                        break;
                    case 'currency':
                        const currency = element.dataset.currency || 'EUR';
                        element.textContent = this.formatCurrency(parseFloat(value), currency);
                        break;
                    case 'percent':
                        element.textContent = this.formatPercent(parseFloat(value));
                        break;
                    case 'relative-time':
                        element.textContent = this.formatRelativeTime(value);
                        break;
                    case 'file-size':
                        element.textContent = this.formatFileSize(parseInt(value));
                        break;
                }
            } catch (error) {
                console.warn(`Failed to localize element with type ${type}:`, error);
            }
        });
    }
    
    startAutoUpdate(interval = 60000) {
        // Auto-update relative times every minute
        if (this.autoUpdateInterval) {
            clearInterval(this.autoUpdateInterval);
        }
        
        this.autoUpdateInterval = setInterval(() => {
            document.querySelectorAll('[data-localize="relative-time"]').forEach(element => {
                const value = element.dataset.value;
                if (value) {
                    element.textContent = this.formatRelativeTime(value);
                }
            });
        }, interval);
    }
    
    stopAutoUpdate() {
        if (this.autoUpdateInterval) {
            clearInterval(this.autoUpdateInterval);
            this.autoUpdateInterval = null;
        }
    }
}

// Global instance
window.LocalizationClient = LocalizationClient;

// Initialize with current locale if available
if (typeof window.currentLocale !== 'undefined') {
    window.localization = new LocalizationClient(window.currentLocale);
    
    // Auto-update relative times
    document.addEventListener('DOMContentLoaded', () => {
        window.localization.updateElementsWithLocalization();
        window.localization.startAutoUpdate();
    });
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LocalizationClient;
}