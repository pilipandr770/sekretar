"""Template filters for advanced localization features."""
from datetime import datetime, timedelta
from typing import Union, Optional
from decimal import Decimal
from flask import current_app
from flask_babel import get_locale
from app.services.localization_service import LocalizationService
import logging

logger = logging.getLogger(__name__)


def init_template_filters(app):
    """Initialize template filters for localization."""
    localization_service = LocalizationService()
    
    @app.template_filter('format_date')
    def format_date_filter(date: datetime, format: str = 'medium') -> str:
        """Template filter for formatting dates according to locale."""
        if not date:
            return ''
        
        try:
            return localization_service.format_date(date, format)
        except Exception as e:
            logger.error(f"Error formatting date in template: {e}")
            return date.strftime('%Y-%m-%d')
    
    @app.template_filter('format_datetime')
    def format_datetime_filter(dt: datetime, format: str = 'medium') -> str:
        """Template filter for formatting datetime according to locale."""
        if not dt:
            return ''
        
        try:
            return localization_service.format_datetime(dt, format)
        except Exception as e:
            logger.error(f"Error formatting datetime in template: {e}")
            return dt.strftime('%Y-%m-%d %H:%M')
    
    @app.template_filter('format_time')
    def format_time_filter(time: datetime, format: str = 'medium') -> str:
        """Template filter for formatting time according to locale."""
        if not time:
            return ''
        
        try:
            return localization_service.format_time(time, format)
        except Exception as e:
            logger.error(f"Error formatting time in template: {e}")
            return time.strftime('%H:%M')
    
    @app.template_filter('format_currency')
    def format_currency_filter(amount: Union[float, Decimal], currency: str = 'EUR') -> str:
        """Template filter for formatting currency according to locale."""
        if amount is None:
            return ''
        
        try:
            return localization_service.format_currency(amount, currency)
        except Exception as e:
            logger.error(f"Error formatting currency in template: {e}")
            return f"{currency} {amount:,.2f}"
    
    @app.template_filter('format_number')
    def format_number_filter(number: Union[int, float, Decimal]) -> str:
        """Template filter for formatting numbers according to locale."""
        if number is None:
            return ''
        
        try:
            return localization_service.format_number(number)
        except Exception as e:
            logger.error(f"Error formatting number in template: {e}")
            return f"{number:,}"
    
    @app.template_filter('format_percent')
    def format_percent_filter(number: Union[float, Decimal]) -> str:
        """Template filter for formatting percentages according to locale."""
        if number is None:
            return ''
        
        try:
            return localization_service.format_percent(number)
        except Exception as e:
            logger.error(f"Error formatting percent in template: {e}")
            return f"{number * 100:.1f}%"
    
    @app.template_filter('relative_time')
    def relative_time_filter(dt: datetime) -> str:
        """Template filter for relative time formatting."""
        if not dt:
            return ''
        
        try:
            return localization_service.get_relative_time(dt)
        except Exception as e:
            logger.error(f"Error formatting relative time in template: {e}")
            return str(dt)
    
    @app.template_filter('format_file_size')
    def format_file_size_filter(size_bytes: int) -> str:
        """Template filter for formatting file sizes."""
        if size_bytes is None:
            return ''
        
        try:
            return localization_service.format_file_size(size_bytes)
        except Exception as e:
            logger.error(f"Error formatting file size in template: {e}")
            return f"{size_bytes} B"
    
    @app.template_filter('pluralize_count')
    def pluralize_count_filter(count: int, singular: str, plural: str = None) -> str:
        """Template filter for pluralization with count."""
        try:
            pluralized = localization_service.pluralize(count, singular, plural)
            return f"{localization_service.format_number(count)} {pluralized}"
        except Exception as e:
            logger.error(f"Error with pluralization in template: {e}")
            return f"{count} {singular if count == 1 else (plural or singular + 's')}"
    
    @app.template_filter('locale_aware_sort')
    def locale_aware_sort_filter(items: list, key: str = None) -> list:
        """Template filter for locale-aware sorting."""
        try:
            import locale as system_locale
            current_locale = str(get_locale()) if get_locale() else 'en'
            
            # Map our locale codes to system locale codes
            locale_mapping = {
                'en': 'en_US.UTF-8',
                'de': 'de_DE.UTF-8',
                'uk': 'uk_UA.UTF-8'
            }
            
            system_locale_code = locale_mapping.get(current_locale, 'en_US.UTF-8')
            
            try:
                system_locale.setlocale(system_locale.LC_COLLATE, system_locale_code)
                if key:
                    return sorted(items, key=lambda x: getattr(x, key, ''), cmp=system_locale.strcoll)
                else:
                    return sorted(items, cmp=system_locale.strcoll)
            except (system_locale.Error, AttributeError):
                # Fallback to regular sorting if locale is not available
                if key:
                    return sorted(items, key=lambda x: getattr(x, key, ''))
                else:
                    return sorted(items)
                
        except Exception as e:
            logger.error(f"Error with locale-aware sorting in template: {e}")
            return items
    
    @app.template_global()
    def get_locale_info():
        """Template global for getting locale information."""
        try:
            return localization_service.get_locale_info()
        except Exception as e:
            logger.error(f"Error getting locale info in template: {e}")
            return {}
    
    @app.template_global()
    def get_month_names():
        """Template global for getting localized month names."""
        try:
            return localization_service.get_month_names()
        except Exception as e:
            logger.error(f"Error getting month names in template: {e}")
            return {
                'wide': ['January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December'],
                'abbreviated': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            }
    
    @app.template_global()
    def get_day_names():
        """Template global for getting localized day names."""
        try:
            return localization_service.get_day_names()
        except Exception as e:
            logger.error(f"Error getting day names in template: {e}")
            return {
                'wide': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
                'abbreviated': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            }
    
    @app.template_global()
    def is_rtl_locale():
        """Template global for checking if current locale is RTL."""
        try:
            return localization_service.is_rtl_locale()
        except Exception as e:
            logger.error(f"Error checking RTL locale in template: {e}")
            return False
    
    @app.template_test('past')
    def is_past_test(dt: datetime) -> bool:
        """Template test for checking if datetime is in the past."""
        if not dt:
            return False
        return dt < datetime.utcnow()
    
    @app.template_test('future')
    def is_future_test(dt: datetime) -> bool:
        """Template test for checking if datetime is in the future."""
        if not dt:
            return False
        return dt > datetime.utcnow()
    
    @app.template_test('today')
    def is_today_test(dt: datetime) -> bool:
        """Template test for checking if datetime is today."""
        if not dt:
            return False
        today = datetime.utcnow().date()
        return dt.date() == today
    
    @app.template_test('this_week')
    def is_this_week_test(dt: datetime) -> bool:
        """Template test for checking if datetime is in current week."""
        if not dt:
            return False
        
        now = datetime.utcnow()
        start_of_week = now - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        return start_of_week.date() <= dt.date() <= end_of_week.date()
    
    @app.template_test('this_month')
    def is_this_month_test(dt: datetime) -> bool:
        """Template test for checking if datetime is in current month."""
        if not dt:
            return False
        
        now = datetime.utcnow()
        return dt.year == now.year and dt.month == now.month
    
    logger.info("✅ Template filters for localization initialized")
    return True