"""Utilities for multilingual content management."""
from flask import g
from flask_babel import gettext as _
from app.utils.i18n import LANGUAGES, get_user_language
import json
from typing import Dict, Any, Optional


class MultilingualField:
    """Helper for managing multilingual fields in models."""
    
    def __init__(self, data: Dict[str, str] = None):
        """Initialize with multilingual data."""
        self.data = data or {}
    
    def get(self, language: str = None) -> str:
        """Get text in specified language."""
        if language is None:
            language = get_user_language()
        
        # Try exact language match
        if language in self.data:
            return self.data[language]
        
        # Try language without region (e.g., 'en' from 'en-US')
        base_lang = language.split('-')[0]
        if base_lang in self.data:
            return self.data[base_lang]
        
        # Try English as fallback
        if 'en' in self.data:
            return self.data['en']
        
        # Return first available language
        if self.data:
            return next(iter(self.data.values()))
        
        return ''
    
    def set(self, text: str, language: str = None):
        """Set text for specified language."""
        if language is None:
            language = get_user_language()
        
        self.data[language] = text
    
    def update(self, updates: Dict[str, str]):
        """Update multiple languages at once."""
        self.data.update(updates)
    
    def has_language(self, language: str) -> bool:
        """Check if text exists for language."""
        return language in self.data
    
    def get_available_languages(self) -> list:
        """Get list of available languages."""
        return list(self.data.keys())
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return self.data.copy()
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.data, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'MultilingualField':
        """Create from JSON string."""
        try:
            data = json.loads(json_str) if json_str else {}
            return cls(data)
        except (json.JSONDecodeError, TypeError):
            return cls()
    
    def __str__(self):
        """Return text in current language."""
        return self.get()
    
    def __repr__(self):
        """Return representation."""
        return f"MultilingualField({self.data})"


def create_multilingual_content(content: Dict[str, Any], fields: list) -> Dict[str, Any]:
    """Create multilingual content from input data."""
    result = content.copy()
    current_lang = get_user_language()
    
    for field in fields:
        if field in content:
            # If it's already a dict with language keys, use as is
            if isinstance(content[field], dict):
                result[field] = content[field]
            else:
                # Create multilingual field with current language
                result[field] = {current_lang: content[field]}
    
    return result


def get_localized_content(content: Dict[str, Any], fields: list, language: str = None) -> Dict[str, Any]:
    """Get localized version of content."""
    if language is None:
        language = get_user_language()
    
    result = content.copy()
    
    for field in fields:
        if field in content and isinstance(content[field], dict):
            multilingual = MultilingualField(content[field])
            result[field] = multilingual.get(language)
    
    return result


class LocalizedEnum:
    """Base class for localized enumerations."""
    
    @classmethod
    def get_choices(cls, language: str = None) -> Dict[str, str]:
        """Get localized choices."""
        if language is None:
            language = get_user_language()
        
        choices = {}
        for key, translations in cls._choices.items():
            if isinstance(translations, dict):
                multilingual = MultilingualField(translations)
                choices[key] = multilingual.get(language)
            else:
                choices[key] = str(translations)
        
        return choices
    
    @classmethod
    def get_display_name(cls, key: str, language: str = None) -> str:
        """Get display name for a key."""
        choices = cls.get_choices(language)
        return choices.get(key, key)


class TaskPriority(LocalizedEnum):
    """Localized task priority enum."""
    
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'
    
    _choices = {
        LOW: {
            'en': 'Low',
            'de': 'Niedrig',
            'uk': 'Низький'
        },
        MEDIUM: {
            'en': 'Medium',
            'de': 'Mittel',
            'uk': 'Середній'
        },
        HIGH: {
            'en': 'High',
            'de': 'Hoch',
            'uk': 'Високий'
        },
        URGENT: {
            'en': 'Urgent',
            'de': 'Dringend',
            'uk': 'Терміновий'
        }
    }


class LeadStatus(LocalizedEnum):
    """Localized lead status enum."""
    
    OPEN = 'open'
    WON = 'won'
    LOST = 'lost'
    CANCELLED = 'cancelled'
    
    _choices = {
        OPEN: {
            'en': 'Open',
            'de': 'Offen',
            'uk': 'Відкритий'
        },
        WON: {
            'en': 'Won',
            'de': 'Gewonnen',
            'uk': 'Виграний'
        },
        LOST: {
            'en': 'Lost',
            'de': 'Verloren',
            'uk': 'Програний'
        },
        CANCELLED: {
            'en': 'Cancelled',
            'de': 'Abgebrochen',
            'uk': 'Скасований'
        }
    }


class ContactType(LocalizedEnum):
    """Localized contact type enum."""
    
    PROSPECT = 'prospect'
    CUSTOMER = 'customer'
    PARTNER = 'partner'
    VENDOR = 'vendor'
    
    _choices = {
        PROSPECT: {
            'en': 'Prospect',
            'de': 'Interessent',
            'uk': 'Потенційний клієнт'
        },
        CUSTOMER: {
            'en': 'Customer',
            'de': 'Kunde',
            'uk': 'Клієнт'
        },
        PARTNER: {
            'en': 'Partner',
            'de': 'Partner',
            'uk': 'Партнер'
        },
        VENDOR: {
            'en': 'Vendor',
            'de': 'Lieferant',
            'uk': 'Постачальник'
        }
    }


def localize_model_data(model_data: Dict[str, Any], model_type: str) -> Dict[str, Any]:
    """Localize model data based on model type."""
    result = model_data.copy()
    
    # Add localized enum values
    if model_type == 'task' and 'priority' in result:
        result['priority_display'] = TaskPriority.get_display_name(result['priority'])
    
    elif model_type == 'lead' and 'status' in result:
        result['status_display'] = LeadStatus.get_display_name(result['status'])
    
    elif model_type == 'contact' and 'contact_type' in result:
        result['contact_type_display'] = ContactType.get_display_name(result['contact_type'])
    
    return result


def get_validation_messages() -> Dict[str, str]:
    """Get localized validation messages."""
    return {
        'required': _('This field is required'),
        'invalid_email': _('Invalid email address'),
        'invalid_phone': _('Invalid phone number'),
        'too_short': _('Value is too short'),
        'too_long': _('Value is too long'),
        'invalid_choice': _('Invalid choice'),
        'invalid_date': _('Invalid date format'),
        'invalid_number': _('Invalid number'),
        'file_too_large': _('File is too large'),
        'invalid_file_type': _('Invalid file type')
    }


def translate_validation_error(field_name: str, error_type: str, **kwargs) -> str:
    """Translate validation error message."""
    messages = get_validation_messages()
    base_message = messages.get(error_type, _('Invalid value'))
    
    # Add field name to message
    field_display = _(field_name.replace('_', ' ').title())
    
    if error_type == 'required':
        return _('%(field)s is required', field=field_display)
    else:
        return _('%(field)s: %(message)s', field=field_display, message=base_message)


class MultilingualValidator:
    """Validator for multilingual fields."""
    
    def __init__(self, required_languages: list = None, optional_languages: list = None):
        """Initialize validator."""
        self.required_languages = required_languages or ['en']
        self.optional_languages = optional_languages or []
        self.all_languages = set(self.required_languages + self.optional_languages)
    
    def validate(self, data: Dict[str, str], field_name: str = 'field') -> list:
        """Validate multilingual data."""
        errors = []
        
        if not isinstance(data, dict):
            errors.append(_('%(field)s must be an object with language keys', field=field_name))
            return errors
        
        # Check required languages
        for lang in self.required_languages:
            if lang not in data or not data[lang].strip():
                lang_name = LANGUAGES.get(lang, lang)
                errors.append(_('%(field)s is required in %(language)s', 
                             field=field_name, language=lang_name))
        
        # Check for invalid languages
        for lang in data.keys():
            if lang not in LANGUAGES:
                errors.append(_('Unsupported language: %(language)s', language=lang))
        
        return errors