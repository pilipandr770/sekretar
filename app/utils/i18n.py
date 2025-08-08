"""Internationalization utilities."""
from flask import request, session, current_app
from flask_babel import Babel, get_locale, lazy_gettext as _l
import os


# Supported languages
LANGUAGES = {
    'en': 'English',
    'de': 'Deutsch', 
    'uk': 'Українська'
}

babel = Babel()


def get_user_language():
    """Get user's preferred language from various sources."""
    # 1. Check URL parameter
    if request and request.args.get('lang'):
        lang = request.args.get('lang')
        if lang in LANGUAGES:
            session['language'] = lang
            return lang
    
    # 2. Check session
    if 'language' in session and session['language'] in LANGUAGES:
        return session['language']
    
    # 3. Check user profile (if authenticated)
    try:
        from flask_jwt_extended import get_current_user
        user = get_current_user()
        if user and hasattr(user, 'language') and user.language in LANGUAGES:
            return user.language
    except:
        pass
    
    # 4. Check Accept-Language header
    if request:
        return request.accept_languages.best_match(LANGUAGES.keys()) or 'en'
    
    # 5. Default to English
    return 'en'


@babel.localeselector
def get_locale():
    """Select locale for current request."""
    return get_user_language()


def init_babel(app):
    """Initialize Babel with Flask app."""
    babel.init_app(app)
    
    # Set default locale and timezone
    app.config.setdefault('LANGUAGES', LANGUAGES)
    app.config.setdefault('BABEL_DEFAULT_LOCALE', 'en')
    app.config.setdefault('BABEL_DEFAULT_TIMEZONE', 'UTC')
    
    return babel


def get_available_languages():
    """Get list of available languages."""
    return LANGUAGES


def set_user_language(language_code):
    """Set user's language preference."""
    if language_code in LANGUAGES:
        session['language'] = language_code
        return True
    return False


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
    locale = get_locale()
    
    if str(locale) == 'de':
        return f"{amount:,.2f} {currency}".replace(',', 'X').replace('.', ',').replace('X', '.')
    elif str(locale) == 'uk':
        return f"{amount:,.2f} {currency}"
    else:  # English
        return f"{currency} {amount:,.2f}"