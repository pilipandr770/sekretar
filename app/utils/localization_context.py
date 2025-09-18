"""Localization context processor for templates."""
from datetime import datetime
from flask import g
from flask_babel import get_locale
from app.services.localization_service import LocalizationService
from app.utils.i18n import get_user_language, LANGUAGES
import logging

logger = logging.getLogger(__name__)


class LocalizationContextProcessor:
    """Context processor for injecting localization data into templates."""
    
    def __init__(self):
        self.localization_service = LocalizationService()
    
    def get_localization_context(self):
        """Get localization context for templates."""
        try:
            current_locale = get_user_language()
            locale_info = self.localization_service.get_locale_info()
            
            context = {
                'locale': {
                    'code': current_locale,
                    'name': LANGUAGES.get(current_locale, 'English'),
                    'info': locale_info,
                    'is_rtl': self.localization_service.is_rtl_locale(),
                },
                'localization': {
                    'date_formats': self._get_date_format_examples(),
                    'number_formats': self._get_number_format_examples(),
                    'currency_formats': self._get_currency_format_examples(),
                    'month_names': self.localization_service.get_month_names(),
                    'day_names': self.localization_service.get_day_names(),
                },
                'available_languages': LANGUAGES,
                'current_time': datetime.utcnow(),
            }
            
            return context
            
        except Exception as e:
            logger.error(f"Error creating localization context: {e}")
            return {
                'locale': {
                    'code': 'en',
                    'name': 'English',
                    'info': {},
                    'is_rtl': False,
                },
                'localization': {
                    'date_formats': {},
                    'number_formats': {},
                    'currency_formats': {},
                    'month_names': {'wide': [], 'abbreviated': []},
                    'day_names': {'wide': [], 'abbreviated': []},
                },
                'available_languages': LANGUAGES,
                'current_time': datetime.utcnow(),
            }
    
    def _get_date_format_examples(self):
        """Get date format examples for current locale."""
        try:
            sample_date = datetime(2023, 12, 25, 14, 30, 0)  # Christmas 2023, 2:30 PM
            
            return {
                'short_date': self.localization_service.format_date(sample_date, 'short'),
                'medium_date': self.localization_service.format_date(sample_date, 'medium'),
                'long_date': self.localization_service.format_date(sample_date, 'long'),
                'full_date': self.localization_service.format_date(sample_date, 'full'),
                'short_time': self.localization_service.format_time(sample_date, 'short'),
                'medium_time': self.localization_service.format_time(sample_date, 'medium'),
                'short_datetime': self.localization_service.format_datetime(sample_date, 'short'),
                'medium_datetime': self.localization_service.format_datetime(sample_date, 'medium'),
            }
        except Exception as e:
            logger.error(f"Error getting date format examples: {e}")
            return {}
    
    def _get_number_format_examples(self):
        """Get number format examples for current locale."""
        try:
            return {
                'integer': self.localization_service.format_number(1234567),
                'decimal': self.localization_service.format_number(1234.56),
                'percent': self.localization_service.format_percent(0.1234),
                'large_number': self.localization_service.format_number(1234567890.123),
            }
        except Exception as e:
            logger.error(f"Error getting number format examples: {e}")
            return {}
    
    def _get_currency_format_examples(self):
        """Get currency format examples for current locale."""
        try:
            return {
                'eur': self.localization_service.format_currency(1234.56, 'EUR'),
                'usd': self.localization_service.format_currency(1234.56, 'USD'),
                'gbp': self.localization_service.format_currency(1234.56, 'GBP'),
                'uah': self.localization_service.format_currency(1234.56, 'UAH'),
            }
        except Exception as e:
            logger.error(f"Error getting currency format examples: {e}")
            return {}


def init_localization_context_processor(app):
    """Initialize localization context processor."""
    processor = LocalizationContextProcessor()
    
    @app.context_processor
    def inject_localization_context():
        """Inject localization context into all templates."""
        # Cache context in request-level g object to avoid repeated calculations
        if not hasattr(g, 'localization_context'):
            g.localization_context = processor.get_localization_context()
        
        return g.localization_context
    
    logger.info("✅ Localization context processor initialized")
    return processor