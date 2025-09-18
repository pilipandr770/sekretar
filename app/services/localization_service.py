"""Localization formatter service for dates, numbers, and currency."""
from datetime import datetime, timedelta
from typing import Optional, Union
from decimal import Decimal
import locale as system_locale
from babel.dates import format_date, format_datetime, format_time
from babel.numbers import format_currency, format_decimal, format_percent
from babel.core import Locale
from babel import dates
from flask import current_app
from flask_babel import get_locale, ngettext, _
import logging

logger = logging.getLogger(__name__)


class LocalizationService:
    """Service for locale-aware formatting of dates, numbers, and currency."""
    
    def __init__(self):
        self.default_locale = 'en'
        self.supported_locales = {
            'en': 'en_US',
            'de': 'de_DE', 
            'uk': 'uk_UA'
        }
        
    def get_current_locale(self) -> str:
        """Get current locale string."""
        try:
            current_locale = str(get_locale())
            return self.supported_locales.get(current_locale, 'en_US')
        except:
            return 'en_US'
    
    def get_babel_locale(self, locale_code: Optional[str] = None) -> Locale:
        """Get Babel Locale object."""
        if locale_code is None:
            locale_code = str(get_locale()) if get_locale() else 'en'
        
        babel_locale = self.supported_locales.get(locale_code, 'en_US')
        return Locale.parse(babel_locale)
    
    def format_date(self, date: datetime, format: str = 'medium', locale: Optional[str] = None) -> str:
        """Format date according to locale conventions."""
        try:
            babel_locale = self.get_babel_locale(locale)
            return format_date(date, format=format, locale=babel_locale)
        except Exception as e:
            logger.error(f"Error formatting date: {e}")
            return date.strftime('%Y-%m-%d')
    
    def format_datetime(self, dt: datetime, format: str = 'medium', locale: Optional[str] = None) -> str:
        """Format datetime according to locale conventions."""
        try:
            babel_locale = self.get_babel_locale(locale)
            return format_datetime(dt, format=format, locale=babel_locale)
        except Exception as e:
            logger.error(f"Error formatting datetime: {e}")
            return dt.strftime('%Y-%m-%d %H:%M')
    
    def format_time(self, time: datetime, format: str = 'medium', locale: Optional[str] = None) -> str:
        """Format time according to locale conventions."""
        try:
            babel_locale = self.get_babel_locale(locale)
            return format_time(time, format=format, locale=babel_locale)
        except Exception as e:
            logger.error(f"Error formatting time: {e}")
            return time.strftime('%H:%M')
    
    def format_currency(self, amount: Union[float, Decimal], currency: str = 'EUR', 
                       locale: Optional[str] = None) -> str:
        """Format currency according to locale conventions."""
        if amount is None:
            return f"{currency} 0.00"
            
        try:
            babel_locale = self.get_babel_locale(locale)
            return format_currency(amount, currency, locale=babel_locale)
        except Exception as e:
            logger.error(f"Error formatting currency: {e}")
            # Fallback formatting
            try:
                return f"{currency} {float(amount):,.2f}"
            except (ValueError, TypeError):
                return f"{currency} 0.00"
    
    def format_number(self, number: Union[int, float, Decimal], locale: Optional[str] = None) -> str:
        """Format number according to locale conventions."""
        try:
            babel_locale = self.get_babel_locale(locale)
            return format_decimal(number, locale=babel_locale)
        except Exception as e:
            logger.error(f"Error formatting number: {e}")
            return f"{number:,}"
    
    def format_percent(self, number: Union[float, Decimal], locale: Optional[str] = None) -> str:
        """Format percentage according to locale conventions."""
        try:
            babel_locale = self.get_babel_locale(locale)
            return format_percent(number, locale=babel_locale)
        except Exception as e:
            logger.error(f"Error formatting percent: {e}")
            return f"{number * 100:.1f}%"
    
    def get_relative_time(self, dt: datetime, locale: Optional[str] = None) -> str:
        """Get relative time string (e.g., '2 hours ago')."""
        try:
            babel_locale = self.get_babel_locale(locale)
            now = datetime.utcnow()
            
            # Calculate time difference
            if dt > now:
                delta = dt - now
                future = True
            else:
                delta = now - dt
                future = False
            
            # Format relative time
            if delta.days > 0:
                if delta.days == 1:
                    if future:
                        return self._translate_relative('tomorrow', locale)
                    else:
                        return self._translate_relative('yesterday', locale)
                else:
                    if future:
                        return self._translate_relative('in_days', locale, count=delta.days)
                    else:
                        return self._translate_relative('days_ago', locale, count=delta.days)
            
            hours = delta.seconds // 3600
            if hours > 0:
                if future:
                    return self._translate_relative('in_hours', locale, count=hours)
                else:
                    return self._translate_relative('hours_ago', locale, count=hours)
            
            minutes = (delta.seconds % 3600) // 60
            if minutes > 0:
                if future:
                    return self._translate_relative('in_minutes', locale, count=minutes)
                else:
                    return self._translate_relative('minutes_ago', locale, count=minutes)
            
            if future:
                return self._translate_relative('in_moments', locale)
            else:
                return self._translate_relative('moments_ago', locale)
                
        except Exception as e:
            logger.error(f"Error formatting relative time: {e}")
            return str(dt)
    
    def _translate_relative(self, key: str, locale: Optional[str] = None, count: int = 1) -> str:
        """Translate relative time strings with proper pluralization."""
        translations = {
            'en': {
                'tomorrow': 'tomorrow',
                'yesterday': 'yesterday',
                'in_days': lambda n: f'in {n} day' if n == 1 else f'in {n} days',
                'days_ago': lambda n: f'{n} day ago' if n == 1 else f'{n} days ago',
                'in_hours': lambda n: f'in {n} hour' if n == 1 else f'in {n} hours',
                'hours_ago': lambda n: f'{n} hour ago' if n == 1 else f'{n} hours ago',
                'in_minutes': lambda n: f'in {n} minute' if n == 1 else f'in {n} minutes',
                'minutes_ago': lambda n: f'{n} minute ago' if n == 1 else f'{n} minutes ago',
                'in_moments': 'in a moment',
                'moments_ago': 'just now'
            },
            'de': {
                'tomorrow': 'morgen',
                'yesterday': 'gestern',
                'in_days': lambda n: f'in {n} Tag' if n == 1 else f'in {n} Tagen',
                'days_ago': lambda n: f'vor {n} Tag' if n == 1 else f'vor {n} Tagen',
                'in_hours': lambda n: f'in {n} Stunde' if n == 1 else f'in {n} Stunden',
                'hours_ago': lambda n: f'vor {n} Stunde' if n == 1 else f'vor {n} Stunden',
                'in_minutes': lambda n: f'in {n} Minute' if n == 1 else f'in {n} Minuten',
                'minutes_ago': lambda n: f'vor {n} Minute' if n == 1 else f'vor {n} Minuten',
                'in_moments': 'gleich',
                'moments_ago': 'gerade eben'
            },
            'uk': {
                'tomorrow': 'завтра',
                'yesterday': 'вчора',
                'in_days': lambda n: f'через {n} день' if n == 1 else f'через {n} дні' if 2 <= n <= 4 else f'через {n} днів',
                'days_ago': lambda n: f'{n} день тому' if n == 1 else f'{n} дні тому' if 2 <= n <= 4 else f'{n} днів тому',
                'in_hours': lambda n: f'через {n} годину' if n == 1 else f'через {n} години' if 2 <= n <= 4 else f'через {n} годин',
                'hours_ago': lambda n: f'{n} годину тому' if n == 1 else f'{n} години тому' if 2 <= n <= 4 else f'{n} годин тому',
                'in_minutes': lambda n: f'через {n} хвилину' if n == 1 else f'через {n} хвилини' if 2 <= n <= 4 else f'через {n} хвилин',
                'minutes_ago': lambda n: f'{n} хвилину тому' if n == 1 else f'{n} хвилини тому' if 2 <= n <= 4 else f'{n} хвилин тому',
                'in_moments': 'зараз',
                'moments_ago': 'щойно'
            }
        }
        
        current_locale = locale or str(get_locale()) or 'en'
        locale_translations = translations.get(current_locale, translations['en'])
        
        translation = locale_translations.get(key)
        if callable(translation):
            return translation(count)
        return translation or key
    
    def pluralize(self, count: int, singular: str, plural: str = None, 
                 locale: Optional[str] = None) -> str:
        """Handle pluralization according to locale rules."""
        try:
            current_locale = locale or str(get_locale()) or 'en'
            
            # Use Flask-Babel's ngettext for proper pluralization
            if plural is None:
                # Generate plural form for English
                if singular.endswith('y'):
                    plural = singular[:-1] + 'ies'
                elif singular.endswith(('s', 'sh', 'ch', 'x', 'z')):
                    plural = singular + 'es'
                else:
                    plural = singular + 's'
            
            return ngettext(singular, plural, count)
            
        except Exception as e:
            logger.error(f"Error with pluralization: {e}")
            return singular if count == 1 else (plural or singular + 's')
    
    def get_locale_info(self, locale_code: Optional[str] = None) -> dict:
        """Get locale information including formats and settings."""
        try:
            babel_locale = self.get_babel_locale(locale_code)
            
            return {
                'code': str(babel_locale),
                'display_name': babel_locale.display_name,
                'english_name': babel_locale.english_name,
                'language': babel_locale.language,
                'territory': babel_locale.territory,
                'currency': getattr(babel_locale, 'currency', None),
                'currency_symbol': babel_locale.currency_symbols.get(getattr(babel_locale, 'currency', 'USD'), ''),
                'decimal_symbol': babel_locale.number_symbols.get('decimal', '.'),
                'group_symbol': babel_locale.number_symbols.get('group', ','),
                'first_week_day': babel_locale.first_week_day,
                'weekend_start': babel_locale.weekend_start,
                'weekend_end': babel_locale.weekend_end,
                'date_formats': {
                    'short': babel_locale.date_formats['short'].pattern,
                    'medium': babel_locale.date_formats['medium'].pattern,
                    'long': babel_locale.date_formats['long'].pattern,
                    'full': babel_locale.date_formats['full'].pattern,
                },
                'time_formats': {
                    'short': babel_locale.time_formats['short'].pattern,
                    'medium': babel_locale.time_formats['medium'].pattern,
                    'long': babel_locale.time_formats['long'].pattern,
                    'full': babel_locale.time_formats['full'].pattern,
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting locale info: {e}")
            return {}
    
    def format_file_size(self, size_bytes: int, locale: Optional[str] = None) -> str:
        """Format file size in human readable format."""
        try:
            current_locale = locale or str(get_locale()) or 'en'
            
            if size_bytes == 0:
                return "0 B"
            
            size_names = {
                'en': ["B", "KB", "MB", "GB", "TB"],
                'de': ["B", "KB", "MB", "GB", "TB"],
                'uk': ["Б", "КБ", "МБ", "ГБ", "ТБ"]
            }
            
            names = size_names.get(current_locale, size_names['en'])
            
            import math
            i = int(math.floor(math.log(size_bytes, 1024)))
            p = math.pow(1024, i)
            s = round(size_bytes / p, 2)
            
            formatted_size = self.format_number(s, locale)
            return f"{formatted_size} {names[i]}"
            
        except Exception as e:
            logger.error(f"Error formatting file size: {e}")
            return f"{size_bytes} B"
    
    def get_month_names(self, locale: Optional[str] = None) -> dict:
        """Get localized month names."""
        try:
            babel_locale = self.get_babel_locale(locale)
            
            return {
                'wide': [babel_locale.months['format']['wide'][i] for i in range(1, 13)],
                'abbreviated': [babel_locale.months['format']['abbreviated'][i] for i in range(1, 13)]
            }
            
        except Exception as e:
            logger.error(f"Error getting month names: {e}")
            return {
                'wide': ['January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December'],
                'abbreviated': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            }
    
    def get_day_names(self, locale: Optional[str] = None) -> dict:
        """Get localized day names."""
        try:
            babel_locale = self.get_babel_locale(locale)
            
            return {
                'wide': [babel_locale.days['format']['wide'][i] for i in range(7)],
                'abbreviated': [babel_locale.days['format']['abbreviated'][i] for i in range(7)]
            }
            
        except Exception as e:
            logger.error(f"Error getting day names: {e}")
            return {
                'wide': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
                'abbreviated': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            }
    
    def is_rtl_locale(self, locale: Optional[str] = None) -> bool:
        """Check if locale uses right-to-left text direction."""
        try:
            babel_locale = self.get_babel_locale(locale)
            return babel_locale.text_direction == 'rtl'
        except:
            return False