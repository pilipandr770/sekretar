"""
Internationalization API endpoints
Provides translation data and language management for frontend
"""

from flask import Blueprint, jsonify, request, current_app, session
from flask_jwt_extended import jwt_required, get_current_user
from app.utils.i18n import (
    get_user_language, set_user_language, get_available_languages,
    LANGUAGES, language_detection, get_translation_context
)
from app.utils.response import success_response, error_response
from app.models import User
from app import db
import json
import os
import logging

logger = logging.getLogger(__name__)

# Create blueprint
i18n_bp = Blueprint('i18n', __name__, url_prefix='/api/v1/i18n')

# Create user blueprint for language preferences
user_bp = Blueprint('i18n_user', __name__, url_prefix='/api/v1/user')


@i18n_bp.route('/languages', methods=['GET'])
def get_languages():
    """Get available languages."""
    try:
        return success_response(
            data={
                'languages': LANGUAGES,
                'current': get_user_language(),
                'available': list(LANGUAGES.keys())
            },
            message='Languages retrieved successfully'
        )
    except Exception as e:
        logger.error(f"Error getting languages: {e}")
        return error_response('Failed to get languages', 500)


@i18n_bp.route('/translations/<language>', methods=['GET'])
def get_translations(language):
    """Get translations for a specific language."""
    try:
        # Validate language
        if not language_detection.validate_language_code(language):
            return error_response(f'Unsupported language: {language}', 400)

        # Load translation file
        translations = load_translation_file(language)
        
        if translations is None:
            return error_response(f'Translation file not found for language: {language}', 404)

        return success_response(
            data={
                'language': language,
                'translations': translations,
                'metadata': {
                    'total_keys': len(translations),
                    'translated_keys': len([v for v in translations.values() if v and v.strip()]),
                    'language_name': LANGUAGES.get(language, language)
                }
            },
            message=f'Translations for {language} retrieved successfully'
        )
    except Exception as e:
        logger.error(f"Error getting translations for {language}: {e}")
        return error_response('Failed to get translations', 500)


@i18n_bp.route('/user/language', methods=['GET'])
@jwt_required(optional=True)
def get_user_language_preference():
    """Get current user's language preference."""
    try:
        current_language = get_user_language()
        user = get_current_user()
        
        return success_response(
            data={
                'language': current_language,
                'is_authenticated': user is not None,
                'user_preference': user.language if user and hasattr(user, 'language') else None,
                'session_language': session.get('language'),
                'available_languages': LANGUAGES
            },
            message='User language preference retrieved successfully'
        )
    except Exception as e:
        logger.error(f"Error getting user language preference: {e}")
        return error_response('Failed to get user language preference', 500)


@i18n_bp.route('/user/language', methods=['POST'])
@jwt_required(optional=True)
def set_user_language_preference():
    """Set user's language preference."""
    try:
        data = request.get_json()
        
        if not data or 'language' not in data:
            return error_response('Language is required', 400)
        
        language = data['language']
        
        # Validate language
        if not language_detection.validate_language_code(language):
            return error_response(f'Unsupported language: {language}', 400)
        
        # Set language preference
        user = get_current_user()
        user_id = user.id if user else None
        
        success = set_user_language(language, user_id)
        
        if not success:
            return error_response('Failed to set language preference', 500)
        
        return success_response(
            data={
                'language': language,
                'previous_language': session.get('previous_language'),
                'is_authenticated': user is not None
            },
            message=f'Language preference set to {LANGUAGES.get(language, language)}'
        )
    except Exception as e:
        logger.error(f"Error setting user language preference: {e}")
        return error_response('Failed to set language preference', 500)


@i18n_bp.route('/context', methods=['GET'])
@jwt_required(optional=True)
def get_i18n_context():
    """Get complete i18n context for frontend initialization."""
    try:
        current_language = get_user_language()
        user = get_current_user()
        
        # Load translations for current language
        translations = load_translation_file(current_language)
        
        # Load fallback translations (English) if current language is not English
        fallback_translations = None
        if current_language != 'en':
            fallback_translations = load_translation_file('en')
        
        context = {
            'current_language': current_language,
            'available_languages': LANGUAGES,
            'translations': translations or {},
            'fallback_translations': fallback_translations or {},
            'user': {
                'is_authenticated': user is not None,
                'language_preference': user.language if user and hasattr(user, 'language') else None
            },
            'locale_info': get_locale_info(current_language),
            'formatting_options': get_formatting_options(current_language)
        }
        
        return success_response(
            data=context,
            message='I18n context retrieved successfully'
        )
    except Exception as e:
        logger.error(f"Error getting i18n context: {e}")
        return error_response('Failed to get i18n context', 500)


@i18n_bp.route('/stats', methods=['GET'])
@jwt_required(optional=True)
def get_translation_stats():
    """Get translation statistics for all languages."""
    try:
        stats = {}
        
        for language_code, language_name in LANGUAGES.items():
            translations = load_translation_file(language_code)
            
            if translations:
                total_keys = len(translations)
                translated_keys = len([v for v in translations.values() if v and v.strip()])
                coverage = (translated_keys / total_keys * 100) if total_keys > 0 else 0
                
                stats[language_code] = {
                    'name': language_name,
                    'total_keys': total_keys,
                    'translated_keys': translated_keys,
                    'coverage_percentage': round(coverage, 2),
                    'missing_keys': total_keys - translated_keys
                }
            else:
                stats[language_code] = {
                    'name': language_name,
                    'total_keys': 0,
                    'translated_keys': 0,
                    'coverage_percentage': 0,
                    'missing_keys': 0,
                    'error': 'Translation file not found'
                }
        
        return success_response(
            data={
                'stats': stats,
                'overall': {
                    'total_languages': len(LANGUAGES),
                    'average_coverage': sum(s.get('coverage_percentage', 0) for s in stats.values()) / len(stats)
                }
            },
            message='Translation statistics retrieved successfully'
        )
    except Exception as e:
        logger.error(f"Error getting translation stats: {e}")
        return error_response('Failed to get translation statistics', 500)


def load_translation_file(language):
    """Load translation file for a specific language."""
    try:
        # Path to translation file
        translation_file = os.path.join(
            current_app.root_path,
            'translations',
            language,
            'LC_MESSAGES',
            'messages.po'
        )
        
        if not os.path.exists(translation_file):
            logger.warning(f"Translation file not found: {translation_file}")
            return None
        
        # Parse .po file
        translations = parse_po_file(translation_file)
        return translations
        
    except Exception as e:
        logger.error(f"Error loading translation file for {language}: {e}")
        return None


def parse_po_file(file_path):
    """Parse a .po file and return translations dictionary."""
    translations = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Simple .po file parser
        lines = content.split('\n')
        current_msgid = None
        current_msgstr = None
        in_msgid = False
        in_msgstr = False
        
        for line in lines:
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Start of msgid
            if line.startswith('msgid '):
                if current_msgid and current_msgstr is not None:
                    translations[current_msgid] = current_msgstr
                
                current_msgid = parse_po_string(line[6:])
                current_msgstr = None
                in_msgid = True
                in_msgstr = False
                continue
            
            # Start of msgstr
            if line.startswith('msgstr '):
                current_msgstr = parse_po_string(line[7:])
                in_msgid = False
                in_msgstr = True
                continue
            
            # Continuation of msgid or msgstr
            if line.startswith('"') and line.endswith('"'):
                string_content = parse_po_string(line)
                
                if in_msgid and current_msgid is not None:
                    current_msgid += string_content
                elif in_msgstr and current_msgstr is not None:
                    current_msgstr += string_content
        
        # Add last translation
        if current_msgid and current_msgstr is not None:
            translations[current_msgid] = current_msgstr
        
        # Remove empty msgid (header)
        translations.pop('', None)
        
        return translations
        
    except Exception as e:
        logger.error(f"Error parsing .po file {file_path}: {e}")
        return {}


def parse_po_string(po_string):
    """Parse a quoted string from .po file."""
    if po_string.startswith('"') and po_string.endswith('"'):
        # Remove quotes and handle escape sequences
        content = po_string[1:-1]
        content = content.replace('\\"', '"')
        content = content.replace('\\n', '\n')
        content = content.replace('\\t', '\t')
        content = content.replace('\\\\', '\\')
        return content
    return po_string


def get_locale_info(language):
    """Get locale information for a language."""
    locale_info = {
        'en': {
            'code': 'en-US',
            'name': 'English',
            'native_name': 'English',
            'direction': 'ltr',
            'date_format': 'MM/dd/yyyy',
            'time_format': 'h:mm a',
            'decimal_separator': '.',
            'thousands_separator': ',',
            'currency_symbol': '$',
            'currency_position': 'before'
        },
        'de': {
            'code': 'de-DE',
            'name': 'German',
            'native_name': 'Deutsch',
            'direction': 'ltr',
            'date_format': 'dd.MM.yyyy',
            'time_format': 'HH:mm',
            'decimal_separator': ',',
            'thousands_separator': '.',
            'currency_symbol': '€',
            'currency_position': 'after'
        },
        'uk': {
            'code': 'uk-UA',
            'name': 'Ukrainian',
            'native_name': 'Українська',
            'direction': 'ltr',
            'date_format': 'dd.MM.yyyy',
            'time_format': 'HH:mm',
            'decimal_separator': ',',
            'thousands_separator': ' ',
            'currency_symbol': '₴',
            'currency_position': 'after'
        }
    }
    
    return locale_info.get(language, locale_info['en'])


def get_formatting_options(language):
    """Get formatting options for a language."""
    return {
        'date_formats': {
            'short': get_locale_info(language)['date_format'],
            'medium': get_locale_info(language)['date_format'],
            'long': get_locale_info(language)['date_format'],
            'full': get_locale_info(language)['date_format']
        },
        'time_formats': {
            'short': get_locale_info(language)['time_format'],
            'medium': get_locale_info(language)['time_format'],
            'long': get_locale_info(language)['time_format']
        },
        'number_formats': {
            'decimal_separator': get_locale_info(language)['decimal_separator'],
            'thousands_separator': get_locale_info(language)['thousands_separator']
        },
        'currency_formats': {
            'symbol': get_locale_info(language)['currency_symbol'],
            'position': get_locale_info(language)['currency_position']
        }
    }


# Error handlers
@i18n_bp.errorhandler(400)
def bad_request(error):
    return error_response('Bad request', 400)


@i18n_bp.errorhandler(404)
def not_found(error):
    return error_response('Resource not found', 404)


@i18n_bp.errorhandler(500)
def internal_error(error):
    return error_response('Internal server error', 500)


# User language preference endpoints
@user_bp.route('/language', methods=['GET'])
@jwt_required(optional=True)
def get_user_language_api():
    """Get current user's language preference (alias for frontend compatibility)."""
    return get_user_language_preference()


@user_bp.route('/language', methods=['POST'])
@jwt_required(optional=True)
def set_user_language_api():
    """Set user's language preference (alias for frontend compatibility)."""
    return set_user_language_preference()