"""Translation monitoring utilities for detecting and logging missing translations."""
import logging
import functools
from typing import Optional, Dict, Any
from flask import request, g, current_app
from flask_babel import gettext, get_locale
from app.models.translation_stats import MissingTranslation, TranslationValidationError
from app.utils.i18n import LANGUAGES
import structlog

logger = structlog.get_logger()


class TranslationMonitor:
    """Monitor and log missing translations during runtime."""
    
    def __init__(self):
        self.enabled = True
        self.log_to_database = True
        self.log_to_file = True
        self.cache_missing = set()  # Cache to avoid duplicate logs in same request
        
    def enable_monitoring(self):
        """Enable translation monitoring."""
        self.enabled = True
        
    def disable_monitoring(self):
        """Disable translation monitoring."""
        self.enabled = False
        
    def log_missing_translation(self, message_id: str, language: str = None, 
                              context: Dict[str, Any] = None):
        """Log a missing translation."""
        if not self.enabled:
            return
            
        if not language:
            language = str(get_locale())
            
        # Avoid duplicate logs in same request
        cache_key = f"{language}:{message_id}"
        if cache_key in self.cache_missing:
            return
            
        self.cache_missing.add(cache_key)
        
        # Extract context information
        source_file = None
        line_number = None
        
        if context:
            source_file = context.get('source_file')
            line_number = context.get('line_number')
        
        # Try to get source info from request context
        if not source_file and request:
            source_file = request.endpoint
            
        # Log to database
        if self.log_to_database:
            try:
                MissingTranslation.log_missing(
                    language=language,
                    message_id=message_id,
                    source_file=source_file,
                    line_number=line_number,
                    context=str(context) if context else None
                )
            except Exception as e:
                logger.error("Failed to log missing translation to database", 
                           error=str(e), message_id=message_id, language=language)
        
        # Log to application log
        if self.log_to_file:
            logger.warning(
                "Missing translation detected",
                message_id=message_id,
                language=language,
                source_file=source_file,
                line_number=line_number,
                context=context
            )
    
    def log_translation_error(self, message_id: str, error_type: str, 
                            error_message: str, language: str = None,
                            severity: str = 'warning', context: Dict[str, Any] = None):
        """Log a translation validation error."""
        if not self.enabled:
            return
            
        if not language:
            language = str(get_locale())
            
        # Extract context information
        source_file = None
        line_number = None
        
        if context:
            source_file = context.get('source_file')
            line_number = context.get('line_number')
        
        # Log to database
        if self.log_to_database:
            try:
                TranslationValidationError.log_error(
                    language=language,
                    message_id=message_id,
                    error_type=error_type,
                    error_message=error_message,
                    severity=severity,
                    source_file=source_file,
                    line_number=line_number
                )
            except Exception as e:
                logger.error("Failed to log translation error to database", 
                           error=str(e), message_id=message_id, language=language)
        
        # Log to application log
        if self.log_to_file:
            logger.log(
                severity.upper(),
                "Translation validation error",
                message_id=message_id,
                language=language,
                error_type=error_type,
                error_message=error_message,
                source_file=source_file,
                line_number=line_number,
                context=context
            )
    
    def clear_request_cache(self):
        """Clear the request-level cache of missing translations."""
        self.cache_missing.clear()


# Global monitor instance
translation_monitor = TranslationMonitor()


def monitored_gettext(message, **kwargs):
    """Wrapper around gettext that monitors for missing translations."""
    try:
        # Get the translation
        translated = gettext(message, **kwargs)
        
        # Check if translation is missing (returns the original message)
        if translated == message and str(get_locale()) != 'en':
            # Log missing translation
            translation_monitor.log_missing_translation(
                message_id=message,
                context={'kwargs': kwargs}
            )
        
        return translated
        
    except Exception as e:
        # Log translation error
        translation_monitor.log_translation_error(
            message_id=message,
            error_type='gettext_error',
            error_message=str(e),
            severity='error',
            context={'kwargs': kwargs}
        )
        
        # Return original message as fallback
        return message


def monitored_ngettext(singular, plural, num, **kwargs):
    """Wrapper around ngettext that monitors for missing translations."""
    try:
        from flask_babel import ngettext
        
        # Get the translation
        translated = ngettext(singular, plural, num, **kwargs)
        
        # Check if translation is missing
        expected_message = singular if num == 1 else plural
        if translated == expected_message and str(get_locale()) != 'en':
            # Log missing translation
            translation_monitor.log_missing_translation(
                message_id=f"{singular}|{plural}",
                context={'num': num, 'kwargs': kwargs}
            )
        
        return translated
        
    except Exception as e:
        # Log translation error
        translation_monitor.log_translation_error(
            message_id=f"{singular}|{plural}",
            error_type='ngettext_error',
            error_message=str(e),
            severity='error',
            context={'num': num, 'kwargs': kwargs}
        )
        
        # Return appropriate fallback
        return singular if num == 1 else plural


def init_translation_monitoring(app):
    """Initialize translation monitoring for the Flask app."""
    
    # Configure monitoring based on app config
    if app.config.get('TRANSLATION_MONITORING_ENABLED', True):
        translation_monitor.enable_monitoring()
    else:
        translation_monitor.disable_monitoring()
    
    translation_monitor.log_to_database = app.config.get('TRANSLATION_LOG_TO_DATABASE', True)
    translation_monitor.log_to_file = app.config.get('TRANSLATION_LOG_TO_FILE', True)
    
    # Register request hooks
    @app.before_request
    def before_request():
        """Clear translation cache before each request."""
        translation_monitor.clear_request_cache()
    
    @app.after_request
    def after_request(response):
        """Log any accumulated translation issues after request."""
        # Could add request-level summary logging here
        return response
    
    # Register template globals for monitored translation functions
    @app.template_global('_m')
    def template_monitored_gettext(message, **kwargs):
        """Template global for monitored gettext."""
        return monitored_gettext(message, **kwargs)
    
    @app.template_global('ngettext_m')
    def template_monitored_ngettext(singular, plural, num, **kwargs):
        """Template global for monitored ngettext."""
        return monitored_ngettext(singular, plural, num, **kwargs)
    
    logger.info("Translation monitoring initialized", 
               enabled=translation_monitor.enabled,
               log_to_database=translation_monitor.log_to_database,
               log_to_file=translation_monitor.log_to_file)


def monitor_translation_usage(func):
    """Decorator to monitor translation usage in functions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log any translation-related errors
            if 'translation' in str(e).lower() or 'gettext' in str(e).lower():
                translation_monitor.log_translation_error(
                    message_id=f"function:{func.__name__}",
                    error_type='function_translation_error',
                    error_message=str(e),
                    severity='error',
                    context={'function': func.__name__, 'args': str(args)[:100]}
                )
            raise
    return wrapper


class TranslationContext:
    """Context manager for tracking translation usage in code blocks."""
    
    def __init__(self, context_name: str, extra_context: Dict[str, Any] = None):
        self.context_name = context_name
        self.extra_context = extra_context or {}
        self.original_monitor = None
        
    def __enter__(self):
        # Store original monitor state
        self.original_monitor = translation_monitor
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Log any translation errors that occurred in this context
        if exc_type and 'translation' in str(exc_val).lower():
            translation_monitor.log_translation_error(
                message_id=f"context:{self.context_name}",
                error_type='context_translation_error',
                error_message=str(exc_val),
                severity='error',
                context={
                    'context_name': self.context_name,
                    **self.extra_context
                }
            )


def get_translation_health_status():
    """Get current translation system health status."""
    try:
        # Get counts of issues
        total_missing = 0
        total_errors = 0
        
        for lang_code in LANGUAGES.keys():
            total_missing += MissingTranslation.get_unresolved_count(lang_code)
            error_summary = TranslationValidationError.get_error_summary(lang_code)
            total_errors += error_summary.get('total_errors', 0)
        
        # Determine health status
        if total_missing == 0 and total_errors == 0:
            status = 'healthy'
        elif total_missing < 10 and total_errors < 5:
            status = 'warning'
        else:
            status = 'critical'
        
        return {
            'status': status,
            'total_missing_translations': total_missing,
            'total_validation_errors': total_errors,
            'monitoring_enabled': translation_monitor.enabled
        }
        
    except Exception as e:
        logger.error("Failed to get translation health status", error=str(e))
        return {
            'status': 'unknown',
            'error': str(e),
            'monitoring_enabled': translation_monitor.enabled
        }


# Convenience functions for common monitoring tasks
def log_missing_translation(message_id: str, language: str = None, **context):
    """Convenience function to log missing translation."""
    translation_monitor.log_missing_translation(message_id, language, context)


def log_translation_error(message_id: str, error_type: str, error_message: str, 
                         language: str = None, severity: str = 'warning', **context):
    """Convenience function to log translation error."""
    translation_monitor.log_translation_error(
        message_id, error_type, error_message, language, severity, context
    )


def enable_translation_monitoring():
    """Enable translation monitoring."""
    translation_monitor.enable_monitoring()


def disable_translation_monitoring():
    """Disable translation monitoring."""
    translation_monitor.disable_monitoring()


def is_monitoring_enabled():
    """Check if translation monitoring is enabled."""
    return translation_monitor.enabled