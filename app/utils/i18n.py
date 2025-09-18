"""Internationalization utilities."""
from flask import request, session, current_app, g
from flask_babel import Babel, get_locale, lazy_gettext as _l
from flask_caching import Cache
from typing import Optional, Dict, Any
import os
import logging

logger = logging.getLogger(__name__)

# Supported languages
LANGUAGES = {
    'en': 'English',
    'de': 'Deutsch', 
    'uk': 'Українська'
}

babel = Babel()
cache = Cache()


class LanguageDetectionService:
    """Enhanced language detection service with caching and priority-based selection."""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        
    @cache.memoize(timeout=300)
    def get_user_language(self, user_id: Optional[int] = None) -> str:
        """Get user's preferred language from various sources with caching."""
        # Store in g for request-level caching
        if hasattr(g, 'user_language'):
            return g.user_language
            
        language = self._detect_language(user_id)
        g.user_language = language
        return language
    
    def _detect_language(self, user_id: Optional[int] = None) -> str:
        """Detect language using priority-based approach."""
        # 1. Check URL parameter (highest priority)
        if request and request.args.get('lang'):
            lang = request.args.get('lang')
            if self.validate_language_code(lang):
                session['language'] = lang
                logger.debug(f"Language set from URL parameter: {lang}")
                return lang
        
        # 2. Check session storage
        if 'language' in session and self.validate_language_code(session['language']):
            logger.debug(f"Language from session: {session['language']}")
            return session['language']
        
        # 3. Check user profile (if authenticated)
        user_lang = self._get_user_profile_language(user_id)
        if user_lang:
            session['language'] = user_lang  # Cache in session
            logger.debug(f"Language from user profile: {user_lang}")
            return user_lang
        
        # 4. Check tenant default language
        tenant_lang = self.get_tenant_default_language()
        if tenant_lang and self.validate_language_code(tenant_lang):
            logger.debug(f"Language from tenant default: {tenant_lang}")
            return tenant_lang
        
        # 5. Check browser Accept-Language header
        browser_lang = self.get_browser_language()
        if browser_lang:
            logger.debug(f"Language from browser: {browser_lang}")
            return browser_lang
        
        # 6. Default to English
        logger.debug("Using default language: en")
        return 'en'
    
    def _get_user_profile_language(self, user_id: Optional[int] = None) -> Optional[str]:
        """Get language from user profile."""
        try:
            if user_id:
                # Direct user ID lookup
                from app.models import User
                user = User.query.get(user_id)
                if user and hasattr(user, 'language') and self.validate_language_code(user.language):
                    return user.language
            else:
                # Try to get current user from JWT
                from flask_jwt_extended import get_current_user
                user = get_current_user()
                if user and hasattr(user, 'language') and self.validate_language_code(user.language):
                    return user.language
        except Exception as e:
            logger.debug(f"Could not get user language: {e}")
        
        return None
    
    def get_browser_language(self) -> Optional[str]:
        """Get language from browser Accept-Language header."""
        if request and request.accept_languages:
            return request.accept_languages.best_match(LANGUAGES.keys())
        return None
    
    def get_tenant_default_language(self) -> Optional[str]:
        """Get tenant's default language."""
        try:
            # Try to get tenant from current context
            if hasattr(g, 'current_tenant') and g.current_tenant:
                if hasattr(g.current_tenant, 'default_language'):
                    return g.current_tenant.default_language
            
            # Fallback to app config
            return current_app.config.get('DEFAULT_LANGUAGE', 'en')
        except:
            return 'en'
    
    def validate_language_code(self, language_code: str) -> bool:
        """Validate if language code is supported."""
        return language_code in LANGUAGES
    
    def set_user_language(self, language_code: str, user_id: Optional[int] = None) -> bool:
        """Set user's language preference with validation."""
        if not self.validate_language_code(language_code):
            logger.warning(f"Invalid language code: {language_code}")
            return False
        
        # Update session
        session['language'] = language_code
        
        # Update user profile if authenticated
        try:
            if user_id:
                from app.models import User
                from app import db
                user = User.query.get(user_id)
                if user:
                    user.language = language_code
                    db.session.commit()
                    logger.info(f"Updated user {user_id} language to {language_code}")
            else:
                from flask_jwt_extended import get_current_user
                from app import db
                user = get_current_user()
                if user:
                    user.language = language_code
                    db.session.commit()
                    logger.info(f"Updated user {user.id} language to {language_code}")
        except Exception as e:
            logger.error(f"Could not update user language: {e}")
        
        # Clear cache
        if hasattr(g, 'user_language'):
            delattr(g, 'user_language')
        
        cache.delete_memoized(self.get_user_language)
        
        return True

# Global instance
language_detection = LanguageDetectionService()

def get_user_language():
    """Get user's preferred language from various sources."""
    return language_detection.get_user_language()


def get_locale():
    """Select locale for current request."""
    return get_user_language()


def init_babel(app):
    """Initialize Babel with Flask app and caching."""
    babel.init_app(app, locale_selector=get_user_language)
    
    # Initialize cache
    cache.init_app(app)
    
    # Set default locale and timezone
    app.config.setdefault('LANGUAGES', LANGUAGES)
    app.config.setdefault('BABEL_DEFAULT_LOCALE', 'en')
    app.config.setdefault('BABEL_DEFAULT_TIMEZONE', 'UTC')
    app.config.setdefault('DEFAULT_LANGUAGE', 'en')
    
    # Initialize template filters for advanced localization
    try:
        from app.utils.template_filters import init_template_filters
        init_template_filters(app)
        logger.info("✅ Advanced localization template filters initialized")
    except ImportError as e:
        logger.warning(f"⚠️  Template filters not available: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize template filters: {e}")
    
    # Initialize localization context processor
    try:
        from app.utils.localization_context import init_localization_context_processor
        init_localization_context_processor(app)
        logger.info("✅ Localization context processor initialized")
    except ImportError as e:
        logger.warning(f"⚠️  Localization context processor not available: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize localization context processor: {e}")
    
    # Register template globals
    @app.template_global()
    def get_available_languages():
        """Template global for available languages."""
        return LANGUAGES
    
    @app.template_global()
    def get_current_language():
        """Template global for current language."""
        return get_user_language()
    
    @app.template_global()
    def get_language_name(code):
        """Template global for language name."""
        return LANGUAGES.get(code, code)
    
    return babel


def get_available_languages():
    """Get list of available languages."""
    return LANGUAGES


def set_user_language(language_code, user_id: Optional[int] = None):
    """Set user's language preference."""
    return language_detection.set_user_language(language_code, user_id)


# Common translations for system messages
class SystemMessages:
    """System message translations."""
    
    # Authentication
    LOGIN_REQUIRED = _l('Authentication required')
    INVALID_CREDENTIALS = _l('Invalid email or password')
    ACCOUNT_DISABLED = _l('Account is disabled')
    TOKEN_EXPIRED = _l('Token has expired')
    
    # Validation
    FIELD_REQUIRED = _l('This field is required')
    INVALID_EMAIL = _l('Invalid email address')
    INVALID_PHONE = _l('Invalid phone number')
    PASSWORD_TOO_SHORT = _l('Password must be at least 8 characters')
    
    # Permissions
    ACCESS_DENIED = _l('Access denied')
    INSUFFICIENT_PERMISSIONS = _l('Insufficient permissions')
    
    # Operations
    CREATED_SUCCESSFULLY = _l('Created successfully')
    UPDATED_SUCCESSFULLY = _l('Updated successfully')
    DELETED_SUCCESSFULLY = _l('Deleted successfully')
    OPERATION_FAILED = _l('Operation failed')
    
    # Errors
    NOT_FOUND = _l('Resource not found')
    ALREADY_EXISTS = _l('Resource already exists')
    INTERNAL_ERROR = _l('Internal server error')
    
    # Trial and billing
    TRIAL_EXPIRED = _l('Trial period has expired')
    SUBSCRIPTION_REQUIRED = _l('Active subscription required')
    PAYMENT_FAILED = _l('Payment failed')
    
    # KYB
    COUNTERPARTY_ADDED = _l('Counterparty added successfully')
    SANCTIONS_MATCH_FOUND = _l('Sanctions match found')
    VAT_VALIDATION_FAILED = _l('VAT number validation failed')
    
    # AI
    AI_PROCESSING_FAILED = _l('AI processing failed')
    MESSAGE_TOO_LONG = _l('Message is too long')
    
    # File upload
    FILE_TOO_LARGE = _l('File is too large')
    INVALID_FILE_TYPE = _l('Invalid file type')
    UPLOAD_FAILED = _l('File upload failed')


# Business domain translations
class BusinessMessages:
    """Business domain message translations."""
    
    # CRM
    LEAD_CREATED = _l('Lead created successfully')
    LEAD_UPDATED = _l('Lead updated successfully')
    LEAD_WON = _l('Lead marked as won')
    LEAD_LOST = _l('Lead marked as lost')
    
    TASK_ASSIGNED = _l('Task assigned successfully')
    TASK_COMPLETED = _l('Task completed')
    TASK_OVERDUE = _l('Task is overdue')
    
    CONTACT_ADDED = _l('Contact added successfully')
    CONTACT_UPDATED = _l('Contact updated successfully')
    
    # Channels
    CHANNEL_CONNECTED = _l('Channel connected successfully')
    CHANNEL_DISCONNECTED = _l('Channel disconnected')
    CHANNEL_ERROR = _l('Channel connection error')
    
    # Messages
    MESSAGE_SENT = _l('Message sent successfully')
    MESSAGE_FAILED = _l('Failed to send message')
    AUTO_REPLY_SENT = _l('Auto-reply sent')
    
    # Calendar
    EVENT_CREATED = _l('Event created successfully')
    EVENT_UPDATED = _l('Event updated successfully')
    BOOKING_CONFIRMED = _l('Booking confirmed')
    BOOKING_CANCELLED = _l('Booking cancelled')
    
    # Knowledge
    DOCUMENT_UPLOADED = _l('Document uploaded successfully')
    DOCUMENT_PROCESSED = _l('Document processed successfully')
    KNOWLEDGE_UPDATED = _l('Knowledge base updated')


def translate_error_message(error_code, **kwargs):
    """Translate error message by code."""
    messages = {
        'VALIDATION_ERROR': SystemMessages.FIELD_REQUIRED,
        'AUTHENTICATION_ERROR': SystemMessages.LOGIN_REQUIRED,
        'AUTHORIZATION_ERROR': SystemMessages.ACCESS_DENIED,
        'NOT_FOUND_ERROR': SystemMessages.NOT_FOUND,
        'CONFLICT_ERROR': SystemMessages.ALREADY_EXISTS,
        'RATE_LIMIT_ERROR': _l('Rate limit exceeded'),
        'EXTERNAL_SERVICE_ERROR': _l('External service unavailable'),
        'DATABASE_ERROR': _l('Database error occurred'),
        'INTERNAL_ERROR': SystemMessages.INTERNAL_ERROR,
    }
    
    message = messages.get(error_code, _l('Unknown error'))
    
    # Format message with parameters if provided
    if kwargs:
        try:
            return str(message) % kwargs
        except (TypeError, KeyError):
            pass
    
    return str(message)


def get_localized_date_format():
    """Get localized date format."""
    locale = get_locale()
    
    formats = {
        'en': '%m/%d/%Y',
        'de': '%d.%m.%Y', 
        'uk': '%d.%m.%Y'
    }
    
    return formats.get(str(locale), '%Y-%m-%d')


def get_localized_datetime_format():
    """Get localized datetime format."""
    locale = get_locale()
    
    formats = {
        'en': '%m/%d/%Y %I:%M %p',
        'de': '%d.%m.%Y %H:%M',
        'uk': '%d.%m.%Y %H:%M'
    }
    
    return formats.get(str(locale), '%Y-%m-%d %H:%M')


def format_currency(amount, currency='EUR'):
    """Format currency according to locale."""
    try:
        from app.services.localization_service import LocalizationService
        localization_service = LocalizationService()
        return localization_service.format_currency(amount, currency)
    except ImportError:
        # Fallback to simple formatting
        locale = get_locale()
        
        if str(locale) == 'de':
            return f"{amount:,.2f} {currency}".replace(',', 'X').replace('.', ',').replace('X', '.')
        elif str(locale) == 'uk':
            return f"{amount:,.2f} {currency}"
        else:  # English
            return f"{currency} {amount:,.2f}"


class TranslationCache:
    """Translation caching utility."""
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
    
    @cache.memoize(timeout=3600)
    def get_cached_translation(self, key: str, locale: str) -> Optional[str]:
        """Get cached translation."""
        try:
            from flask_babel import gettext
            with current_app.test_request_context():
                # Temporarily set locale
                session['language'] = locale
                return str(gettext(key))
        except:
            return None
    
    def invalidate_cache(self, locale: Optional[str] = None):
        """Invalidate translation cache."""
        if locale:
            # Invalidate specific locale cache
            cache.delete_memoized(self.get_cached_translation, locale=locale)
        else:
            # Invalidate all translation cache
            cache.delete_memoized(self.get_cached_translation)

# Global translation cache instance
translation_cache = TranslationCache()


def get_cached_translation(key: str, locale: Optional[str] = None) -> str:
    """Get translation with caching."""
    if locale is None:
        locale = get_user_language()
    
    cached = translation_cache.get_cached_translation(key, locale)
    if cached:
        return cached
    
    # Fallback to direct translation
    try:
        from flask_babel import gettext
        return str(gettext(key))
    except:
        return key


def invalidate_translation_cache(locale: Optional[str] = None):
    """Invalidate translation cache."""
    translation_cache.invalidate_cache(locale)


def get_translation_context() -> Dict[str, Any]:
    """Get current translation context for templates."""
    return {
        'current_language': get_user_language(),
        'available_languages': LANGUAGES,
        'locale_info': get_locale_info()
    }


def get_locale_info() -> Dict[str, Any]:
    """Get current locale information."""
    try:
        from app.services.localization_service import LocalizationService
        localization_service = LocalizationService()
        return localization_service.get_locale_info()
    except ImportError:
        return {
            'code': get_user_language(),
            'display_name': LANGUAGES.get(get_user_language(), 'English')
        }