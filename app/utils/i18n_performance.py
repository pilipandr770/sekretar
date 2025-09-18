"""
Performance optimizations for i18n system.
"""

import os
import time
import functools
from typing import Dict, Any, Optional, List
from flask import current_app, g, request
from babel import Locale
from babel.core import get_global
from babel.dates import format_datetime, format_date, format_time
from babel.numbers import format_currency, format_decimal
from babel.support import LazyProxy

class I18nPerformanceOptimizer:
    """Optimizations for i18n performance in production."""
    
    def __init__(self):
        self._locale_cache = {}
        self._format_cache = {}
        self._stats = {
            'locale_cache_hits': 0,
            'locale_cache_misses': 0,
            'format_cache_hits': 0,
            'format_cache_misses': 0
        }
    
    def get_cached_locale(self, locale_code: str) -> Optional[Locale]:
        """Get cached Locale object."""
        if locale_code in self._locale_cache:
            self._stats['locale_cache_hits'] += 1
            return self._locale_cache[locale_code]
        
        try:
            locale = Locale.parse(locale_code)
            self._locale_cache[locale_code] = locale
            self._stats['locale_cache_misses'] += 1
            return locale
        except Exception as e:
            current_app.logger.warning(f"Invalid locale code: {locale_code}, error: {e}")
            return None
    
    def cached_format_datetime(self, datetime_obj, format='medium', locale='en'):
        """Cached datetime formatting."""
        cache_key = f"dt:{datetime_obj.isoformat()}:{format}:{locale}"
        
        if cache_key in self._format_cache:
            self._stats['format_cache_hits'] += 1
            return self._format_cache[cache_key]
        
        try:
            locale_obj = self.get_cached_locale(locale)
            if locale_obj:
                formatted = format_datetime(datetime_obj, format=format, locale=locale_obj)
                self._format_cache[cache_key] = formatted
                self._stats['format_cache_misses'] += 1
                return formatted
        except Exception as e:
            current_app.logger.warning(f"Datetime formatting error: {e}")
        
        # Fallback
        return datetime_obj.strftime('%Y-%m-%d %H:%M:%S')
    
    def cached_format_currency(self, amount, currency='EUR', locale='en'):
        """Cached currency formatting."""
        cache_key = f"cur:{amount}:{currency}:{locale}"
        
        if cache_key in self._format_cache:
            self._stats['format_cache_hits'] += 1
            return self._format_cache[cache_key]
        
        try:
            locale_obj = self.get_cached_locale(locale)
            if locale_obj:
                formatted = format_currency(amount, currency, locale=locale_obj)
                self._format_cache[cache_key] = formatted
                self._stats['format_cache_misses'] += 1
                return formatted
        except Exception as e:
            current_app.logger.warning(f"Currency formatting error: {e}")
        
        # Fallback
        return f"{amount} {currency}"
    
    def cached_format_decimal(self, number, locale='en'):
        """Cached decimal formatting."""
        cache_key = f"dec:{number}:{locale}"
        
        if cache_key in self._format_cache:
            self._stats['format_cache_hits'] += 1
            return self._format_cache[cache_key]
        
        try:
            locale_obj = self.get_cached_locale(locale)
            if locale_obj:
                formatted = format_decimal(number, locale=locale_obj)
                self._format_cache[cache_key] = formatted
                self._stats['format_cache_misses'] += 1
                return formatted
        except Exception as e:
            current_app.logger.warning(f"Decimal formatting error: {e}")
        
        # Fallback
        return str(number)
    
    def clear_caches(self):
        """Clear all caches."""
        self._locale_cache.clear()
        self._format_cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        total_locale = self._stats['locale_cache_hits'] + self._stats['locale_cache_misses']
        total_format = self._stats['format_cache_hits'] + self._stats['format_cache_misses']
        
        locale_hit_rate = (self._stats['locale_cache_hits'] / total_locale * 100) if total_locale > 0 else 0
        format_hit_rate = (self._stats['format_cache_hits'] / total_format * 100) if total_format > 0 else 0
        
        return {
            'locale_cache': {
                'hits': self._stats['locale_cache_hits'],
                'misses': self._stats['locale_cache_misses'],
                'hit_rate': round(locale_hit_rate, 2),
                'size': len(self._locale_cache)
            },
            'format_cache': {
                'hits': self._stats['format_cache_hits'],
                'misses': self._stats['format_cache_misses'],
                'hit_rate': round(format_hit_rate, 2),
                'size': len(self._format_cache)
            }
        }

# Global optimizer instance
_optimizer = None

def get_i18n_optimizer() -> I18nPerformanceOptimizer:
    """Get or create the global i18n optimizer."""
    global _optimizer
    
    if _optimizer is None:
        _optimizer = I18nPerformanceOptimizer()
    
    return _optimizer

def performance_timer(func):
    """Decorator to measure i18n function performance."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        
        # Log slow operations
        if duration > 0.1:  # 100ms threshold
            current_app.logger.warning(
                f"Slow i18n operation: {func.__name__} took {duration:.3f}s"
            )
        
        return result
    return wrapper

class LazyTranslation:
    """Lazy translation proxy for better performance."""
    
    def __init__(self, key: str, **kwargs):
        self.key = key
        self.kwargs = kwargs
        self._cached_result = None
        self._cached_locale = None
    
    def __str__(self):
        current_locale = getattr(g, 'current_locale', 'en')
        
        # Return cached result if locale hasn't changed
        if self._cached_result and self._cached_locale == current_locale:
            return self._cached_result
        
        # Get fresh translation
        from flask_babel import gettext
        if self.kwargs:
            result = gettext(self.key, **self.kwargs)
        else:
            result = gettext(self.key)
        
        # Cache result
        self._cached_result = result
        self._cached_locale = current_locale
        
        return result
    
    def __repr__(self):
        return f"LazyTranslation('{self.key}')"

def lazy_gettext(key: str, **kwargs) -> LazyTranslation:
    """Create a lazy translation that's evaluated when needed."""
    return LazyTranslation(key, **kwargs)

def batch_translate(keys: List[str], locale: str = None) -> Dict[str, str]:
    """Translate multiple keys at once for better performance."""
    if not locale:
        locale = getattr(g, 'current_locale', 'en')
    
    from app.services.translation_cache_service import get_translation_cache_service
    cache_service = get_translation_cache_service()
    
    results = {}
    for key in keys:
        translation = cache_service.get_translation(key, locale)
        results[key] = translation or key
    
    return results

def preload_page_translations(template_name: str, locale: str = None):
    """Preload translations for a specific page/template."""
    if not locale:
        locale = getattr(g, 'current_locale', 'en')
    
    # Define common translations per template
    template_translations = {
        'dashboard.html': [
            'Dashboard', 'Welcome', 'Overview', 'Statistics', 'Recent Activity',
            'Quick Actions', 'Settings', 'Profile', 'Logout'
        ],
        'users.html': [
            'Users', 'Add User', 'Edit User', 'Delete User', 'User List',
            'Name', 'Email', 'Role', 'Status', 'Actions', 'Active', 'Inactive'
        ],
        'login.html': [
            'Login', 'Email', 'Password', 'Remember Me', 'Forgot Password',
            'Sign In', 'Register', 'Welcome Back'
        ],
        'register.html': [
            'Register', 'Sign Up', 'Create Account', 'First Name', 'Last Name',
            'Organization', 'Confirm Password', 'Terms of Service'
        ]
    }
    
    keys = template_translations.get(template_name, [])
    if keys:
        batch_translate(keys, locale)

class I18nMiddleware:
    """Middleware for i18n performance optimizations."""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize middleware with Flask app."""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        """Set up i18n context before request."""
        # Store request start time for performance monitoring
        g.i18n_start_time = time.time()
        
        # Detect and cache locale early
        from flask_babel import get_locale
        g.current_locale = str(get_locale())
        
        # Preload common translations based on endpoint
        endpoint = request.endpoint
        if endpoint:
            template_name = self._guess_template_name(endpoint)
            if template_name:
                try:
                    preload_page_translations(template_name, g.current_locale)
                except Exception as e:
                    current_app.logger.warning(f"Failed to preload translations: {e}")
    
    def after_request(self, response):
        """Clean up after request."""
        # Log slow i18n operations
        if hasattr(g, 'i18n_start_time'):
            duration = time.time() - g.i18n_start_time
            if duration > 0.5:  # 500ms threshold
                current_app.logger.warning(
                    f"Slow i18n request: {request.endpoint} took {duration:.3f}s"
                )
        
        return response
    
    def _guess_template_name(self, endpoint: str) -> Optional[str]:
        """Guess template name from endpoint."""
        if not endpoint:
            return None
        
        # Remove blueprint prefix
        if '.' in endpoint:
            endpoint = endpoint.split('.')[-1]
        
        # Map endpoints to templates
        template_map = {
            'dashboard': 'dashboard.html',
            'users': 'users.html',
            'login': 'login.html',
            'register': 'register.html',
            'profile': 'profile.html',
            'settings': 'settings.html'
        }
        
        return template_map.get(endpoint)

def init_i18n_performance(app):
    """Initialize i18n performance optimizations."""
    # Initialize middleware
    I18nMiddleware(app)
    
    # Initialize optimizer
    optimizer = get_i18n_optimizer()
    
    # Add template globals for performance
    app.jinja_env.globals['lazy_gettext'] = lazy_gettext
    app.jinja_env.globals['batch_translate'] = batch_translate
    
    # Add performance monitoring
    if app.config.get('I18N_PERFORMANCE_MONITORING', False):
        @app.route('/admin/i18n/performance')
        def i18n_performance_stats():
            from flask import jsonify
            from app.services.translation_cache_service import get_translation_cache_service
            
            cache_service = get_translation_cache_service()
            optimizer = get_i18n_optimizer()
            
            return jsonify({
                'cache_stats': cache_service.get_cache_stats(),
                'optimizer_stats': optimizer.get_stats(),
                'file_info': cache_service.get_translation_file_info()
            })
    
    app.logger.info("I18n performance optimizations initialized")
    return optimizer