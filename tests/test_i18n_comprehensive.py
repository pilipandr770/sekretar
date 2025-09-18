"""
Comprehensive test suite for i18n functionality.
Tests all translation services, utilities, and integration points.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime, timedelta
from decimal import Decimal
from flask import session, g, request
import json
import os
import tempfile

from app.utils.i18n import (
    LanguageDetectionService, get_user_language, set_user_language,
    get_cached_translation, invalidate_translation_cache,
    get_translation_context, LANGUAGES, SystemMessages, BusinessMessages,
    translate_error_message, get_localized_date_format, format_currency,
    TranslationCache, language_detection, translation_cache
)
from app.services.translation_service import TranslationService, ValidationError
from app.services.localization_service import LocalizationService
from app.services.email_localization_service import EmailLocalizationService


class TestLanguageDetectionService:
    """Test enhanced language detection service."""
    
    def test_init(self):
        """Test service initialization."""
        service = LanguageDetectionService()
        assert service.cache_timeout == 300
    
    def test_validate_language_code(self):
        """Test language code validation."""
        service = LanguageDetectionService()
        
        # Valid languages
        assert service.validate_language_code('en') is True
        assert service.validate_language_code('de') is True
        assert service.validate_language_code('uk') is True
        
        # Invalid languages
        assert service.validate_language_code('fr') is False
        assert service.validate_language_code('invalid') is False
        assert service.validate_language_code('') is False
        assert service.validate_language_code(None) is False
    
    @patch('app.utils.i18n.request')
    @patch('app.utils.i18n.session', {})
    def test_detect_language_from_url(self, mock_request):
        """Test language detection from URL parameter."""
        service = LanguageDetectionService()
        mock_request.args.get.return_value = 'de'
        
        language = service._detect_language()
        assert language == 'de'
    
    @patch('app.utils.i18n.request')
    @patch('app.utils.i18n.session', {'language': 'uk'})
    def test_detect_language_from_session(self, mock_request):
        """Test language detection from session."""
        service = LanguageDetectionService()
        mock_request.args.get.return_value = None
        
        language = service._detect_language()
        assert language == 'uk'
    
    @patch('app.utils.i18n.request')
    @patch('app.utils.i18n.session', {})
    def test_detect_language_from_user_profile(self, mock_request):
        """Test language detection from user profile."""
        service = LanguageDetectionService()
        mock_request.args.get.return_value = None
        
        mock_user = Mock()
        mock_user.language = 'de'
        
        with patch.object(service, '_get_user_profile_language', return_value='de'):
            language = service._detect_language()
            assert language == 'de'
    
    @patch('app.utils.i18n.request')
    @patch('app.utils.i18n.session', {})
    def test_detect_language_from_browser(self, mock_request):
        """Test language detection from browser."""
        service = LanguageDetectionService()
        mock_request.args.get.return_value = None
        mock_request.accept_languages.best_match.return_value = 'de'
        
        with patch.object(service, '_get_user_profile_language', return_value=None):
            with patch.object(service, 'get_tenant_default_language', return_value=None):
                language = service._detect_language()
                assert language == 'de'
    
    @patch('app.utils.i18n.request')
    @patch('app.utils.i18n.session', {})
    def test_detect_language_default(self, mock_request):
        """Test default language detection."""
        service = LanguageDetectionService()
        mock_request.args.get.return_value = None
        mock_request.accept_languages.best_match.return_value = None
        
        with patch.object(service, '_get_user_profile_language', return_value=None):
            with patch.object(service, 'get_tenant_default_language', return_value=None):
                language = service._detect_language()
                assert language == 'en'
    
    def test_get_user_profile_language_with_user_id(self):
        """Test getting language from user profile with user ID."""
        service = LanguageDetectionService()
        
        mock_user = Mock()
        mock_user.language = 'de'
        
        with patch('app.models.User') as mock_user_model:
            mock_user_model.query.get.return_value = mock_user
            
            language = service._get_user_profile_language(user_id=1)
            assert language == 'de'
    
    def test_get_user_profile_language_from_jwt(self):
        """Test getting language from JWT current user."""
        service = LanguageDetectionService()
        
        mock_user = Mock()
        mock_user.language = 'uk'
        
        with patch('flask_jwt_extended.get_current_user', return_value=mock_user):
            language = service._get_user_profile_language()
            assert language == 'uk'
    
    def test_get_user_profile_language_no_user(self):
        """Test getting language when no user is available."""
        service = LanguageDetectionService()
        
        with patch('flask_jwt_extended.get_current_user', return_value=None):
            language = service._get_user_profile_language()
            assert language is None
    
    @patch('app.utils.i18n.request')
    def test_get_browser_language(self, mock_request):
        """Test getting language from browser."""
        service = LanguageDetectionService()
        mock_request.accept_languages.best_match.return_value = 'de'
        
        language = service.get_browser_language()
        assert language == 'de'
    
    @patch('app.utils.i18n.request')
    def test_get_browser_language_no_request(self, mock_request):
        """Test getting browser language when no request available."""
        service = LanguageDetectionService()
        mock_request = None
        
        with patch('app.utils.i18n.request', None):
            language = service.get_browser_language()
            assert language is None
    
    @patch('app.utils.i18n.g')
    def test_get_tenant_default_language_from_g(self, mock_g):
        """Test getting tenant default language from g."""
        service = LanguageDetectionService()
        
        mock_tenant = Mock()
        mock_tenant.default_language = 'de'
        mock_g.current_tenant = mock_tenant
        
        language = service.get_tenant_default_language()
        assert language == 'de'
    
    @patch('app.utils.i18n.g')
    @patch('app.utils.i18n.current_app')
    def test_get_tenant_default_language_from_config(self, mock_app, mock_g):
        """Test getting tenant default language from config."""
        service = LanguageDetectionService()
        mock_g.current_tenant = None
        mock_app.config.get.return_value = 'uk'
        
        language = service.get_tenant_default_language()
        assert language == 'uk'
    
    @patch('app.utils.i18n.session', {})
    @patch('app.utils.i18n.cache')
    def test_set_user_language_valid(self, mock_cache):
        """Test setting valid user language."""
        service = LanguageDetectionService()
        
        result = service.set_user_language('de')
        assert result is True
        assert session['language'] == 'de'
        mock_cache.delete_memoized.assert_called_once()
    
    def test_set_user_language_invalid(self):
        """Test setting invalid user language."""
        service = LanguageDetectionService()
        
        result = service.set_user_language('invalid')
        assert result is False
    
    @patch('app.utils.i18n.session', {})
    @patch('app.utils.i18n.cache')
    def test_set_user_language_with_user_update(self, mock_cache):
        """Test setting user language with user profile update."""
        service = LanguageDetectionService()
        
        mock_user = Mock()
        mock_db = Mock()
        
        with patch('app.models.User') as mock_user_model:
            with patch('app.db', mock_db):
                mock_user_model.query.get.return_value = mock_user
                
                result = service.set_user_language('de', user_id=1)
                assert result is True
                assert mock_user.language == 'de'
                mock_db.session.commit.assert_called_once()


class TestTranslationService:
    """Test translation management service."""
    
    @patch('app.services.translation_service.current_app')
    def test_init(self, mock_app):
        """Test service initialization."""
        mock_app.root_path = '/app'
        mock_app.config.get.return_value = LANGUAGES
        
        service = TranslationService()
        assert service.supported_languages == LANGUAGES
        assert service.babel_config_path.endswith('babel.cfg')
    
    @patch('subprocess.run')
    @patch('app.services.translation_service.current_app')
    def test_extract_messages_success(self, mock_app, mock_subprocess):
        """Test successful message extraction."""
        mock_app.root_path = '/app'
        mock_app.config.get.return_value = LANGUAGES
        mock_subprocess.return_value.returncode = 0
        
        service = TranslationService()
        result = service.extract_messages()
        assert result is True
        mock_subprocess.assert_called_once()
    
    @patch('subprocess.run')
    @patch('app.services.translation_service.current_app')
    def test_extract_messages_failure(self, mock_app, mock_subprocess):
        """Test failed message extraction."""
        mock_app.root_path = '/app'
        mock_app.config.get.return_value = LANGUAGES
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = 'Error'
        
        service = TranslationService()
        result = service.extract_messages()
        assert result is False
    
    @patch('subprocess.run')
    @patch('app.services.translation_service.current_app')
    def test_compile_translations_success(self, mock_app, mock_subprocess):
        """Test successful translation compilation."""
        mock_app.root_path = '/app'
        mock_app.config.get.return_value = LANGUAGES
        mock_subprocess.return_value.returncode = 0
        
        service = TranslationService()
        result = service.compile_translations()
        assert result is True
        # Should be called for each language
        assert mock_subprocess.call_count == len(LANGUAGES)
    
    @patch('builtins.open', create=True)
    @patch('babel.messages.pofile.read_po')
    @patch('app.services.translation_service.current_app')
    def test_get_translation_coverage(self, mock_app, mock_read_po, mock_open):
        """Test translation coverage calculation."""
        mock_app.root_path = '/app'
        mock_app.config.get.return_value = LANGUAGES
        
        # Mock catalog with messages
        mock_catalog = Mock()
        mock_messages = [
            Mock(id='hello', string='hallo'),
            Mock(id='world', string='welt'),
            Mock(id='test', string='')  # untranslated
        ]
        mock_catalog.__iter__ = Mock(return_value=iter(mock_messages))
        mock_read_po.return_value = mock_catalog
        
        service = TranslationService()
        coverage = service.get_translation_coverage()
        
        # Should have coverage for all languages
        assert 'en' in coverage
        assert coverage['en'] == 100.0  # English is always 100%
        assert 'de' in coverage
        assert coverage['de'] == pytest.approx(66.67, rel=1e-2)  # 2/3 translated
    
    @patch('builtins.open', create=True)
    @patch('babel.messages.pofile.read_po')
    @patch('app.services.translation_service.current_app')
    def test_validate_translations(self, mock_app, mock_read_po, mock_open):
        """Test translation validation."""
        mock_app.root_path = '/app'
        mock_app.config.get.return_value = LANGUAGES
        
        # Mock catalog with validation issues
        mock_catalog = Mock()
        mock_messages = [
            Mock(id='hello', string='hallo'),
            Mock(id='missing', string=''),  # missing translation
            Mock(id='placeholder_test %(name)s', string='test'),  # missing placeholder
        ]
        mock_catalog.__iter__ = Mock(return_value=iter(mock_messages))
        mock_read_po.return_value = mock_catalog
        
        service = TranslationService()
        errors = service.validate_translations()
        
        # Should find validation errors
        assert len(errors) > 0
        assert any(error.error == 'Missing translation' for error in errors)
    
    @patch('builtins.open', create=True)
    @patch('babel.messages.pofile.read_po')
    @patch('app.services.translation_service.current_app')
    def test_get_missing_translations(self, mock_app, mock_read_po, mock_open):
        """Test getting missing translations."""
        mock_app.root_path = '/app'
        mock_app.config.get.return_value = LANGUAGES
        
        # Mock catalog with missing translations
        mock_catalog = Mock()
        mock_messages = [
            Mock(id='hello', string='hallo'),
            Mock(id='missing1', string=''),
            Mock(id='missing2', string=''),
        ]
        mock_catalog.__iter__ = Mock(return_value=iter(mock_messages))
        mock_read_po.return_value = mock_catalog
        
        service = TranslationService()
        missing = service.get_missing_translations()
        
        # Should find missing translations for non-English languages
        assert 'de' in missing
        assert 'missing1' in missing['de']
        assert 'missing2' in missing['de']
    
    def test_validation_error(self):
        """Test ValidationError class."""
        error = ValidationError('de', 'hello', 'Missing translation')
        assert error.language == 'de'
        assert error.key == 'hello'
        assert error.error == 'Missing translation'
        assert 'ValidationError' in repr(error)
        assert 'de' in str(error)
        assert 'hello' in str(error)


class TestLocalizationService:
    """Test localization formatter service."""
    
    def test_init(self):
        """Test service initialization."""
        service = LocalizationService()
        assert service.default_locale == 'en'
        assert 'en' in service.supported_locales
        assert 'de' in service.supported_locales
        assert 'uk' in service.supported_locales
    
    @patch('app.services.localization_service.get_locale')
    def test_get_current_locale(self, mock_get_locale):
        """Test getting current locale."""
        mock_get_locale.return_value = 'de'
        
        service = LocalizationService()
        locale = service.get_current_locale()
        assert locale == 'de_DE'
    
    def test_get_current_locale_fallback(self):
        """Test getting current locale with fallback."""
        service = LocalizationService()
        
        with patch('app.services.localization_service.get_locale', side_effect=Exception):
            locale = service.get_current_locale()
            assert locale == 'en_US'  # fallback
    
    @patch('babel.dates.format_date')
    def test_format_date(self, mock_format_date):
        """Test date formatting."""
        mock_format_date.return_value = '15.09.2023'
        
        service = LocalizationService()
        date = datetime(2023, 9, 15)
        formatted = service.format_date(date, locale='de')
        
        assert formatted == '15.09.2023'
        mock_format_date.assert_called_once()
    
    def test_format_date_fallback(self):
        """Test date formatting with fallback."""
        service = LocalizationService()
        date = datetime(2023, 9, 15)
        
        with patch('babel.dates.format_date', side_effect=Exception):
            formatted = service.format_date(date)
            assert isinstance(formatted, str)
            assert '2023' in formatted
    
    @patch('babel.dates.format_datetime')
    def test_format_datetime(self, mock_format_datetime):
        """Test datetime formatting."""
        mock_format_datetime.return_value = '15.09.2023 14:30'
        
        service = LocalizationService()
        dt = datetime(2023, 9, 15, 14, 30)
        formatted = service.format_datetime(dt, locale='de')
        
        assert formatted == '15.09.2023 14:30'
        mock_format_datetime.assert_called_once()
    
    @patch('babel.numbers.format_currency')
    def test_format_currency(self, mock_format_currency):
        """Test currency formatting."""
        mock_format_currency.return_value = '€ 1.234,56'
        
        service = LocalizationService()
        formatted = service.format_currency(1234.56, 'EUR', 'de')
        
        assert formatted == '€ 1.234,56'
        mock_format_currency.assert_called_once()
    
    def test_format_currency_fallback(self):
        """Test currency formatting with fallback."""
        service = LocalizationService()
        
        with patch('babel.numbers.format_currency', side_effect=Exception):
            formatted = service.format_currency(1234.56, 'EUR')
            assert isinstance(formatted, str)
            assert '1234.56' in formatted
            assert 'EUR' in formatted
    
    @patch('babel.numbers.format_decimal')
    def test_format_number(self, mock_format_decimal):
        """Test number formatting."""
        mock_format_decimal.return_value = '1.234,56'
        
        service = LocalizationService()
        formatted = service.format_number(1234.56, 'de')
        
        assert formatted == '1.234,56'
        mock_format_decimal.assert_called_once()
    
    @patch('app.services.localization_service.get_locale')
    @patch('app.services.localization_service.datetime')
    def test_get_relative_time_past(self, mock_datetime, mock_get_locale):
        """Test relative time formatting for past dates."""
        mock_get_locale.return_value = 'en'
        now = datetime(2023, 9, 15, 12, 0)
        mock_datetime.utcnow.return_value = now
        
        service = LocalizationService()
        past_time = datetime(2023, 9, 15, 10, 0)  # 2 hours ago
        
        relative = service.get_relative_time(past_time)
        assert isinstance(relative, str)
        assert len(relative) > 0
    
    @patch('app.services.localization_service.get_locale')
    @patch('app.services.localization_service.datetime')
    def test_get_relative_time_future(self, mock_datetime, mock_get_locale):
        """Test relative time formatting for future dates."""
        mock_get_locale.return_value = 'en'
        now = datetime(2023, 9, 15, 12, 0)
        mock_datetime.utcnow.return_value = now
        
        service = LocalizationService()
        future_time = datetime(2023, 9, 15, 14, 0)  # 2 hours from now
        
        relative = service.get_relative_time(future_time)
        assert isinstance(relative, str)
        assert len(relative) > 0
    
    @patch('flask_babel.ngettext')
    def test_pluralize(self, mock_ngettext):
        """Test pluralization."""
        mock_ngettext.return_value = 'items'
        
        service = LocalizationService()
        result = service.pluralize(2, 'item', 'items')
        
        assert result == 'items'
        mock_ngettext.assert_called_once_with('item', 'items', 2)
    
    def test_pluralize_fallback(self):
        """Test pluralization with fallback."""
        service = LocalizationService()
        
        with patch('flask_babel.ngettext', side_effect=Exception):
            result = service.pluralize(2, 'item', 'items')
            assert result == 'items'  # fallback logic
    
    def test_format_file_size(self):
        """Test file size formatting."""
        service = LocalizationService()
        
        # Test bytes
        size_b = service.format_file_size(0)
        assert 'B' in size_b
        
        size_b = service.format_file_size(512)
        assert 'B' in size_b
        
        # Test KB
        size_kb = service.format_file_size(1024)
        assert 'KB' in size_kb or 'КБ' in size_kb
        
        # Test MB
        size_mb = service.format_file_size(1024 * 1024)
        assert 'MB' in size_mb or 'МБ' in size_mb
        
        # Test GB
        size_gb = service.format_file_size(1024 * 1024 * 1024)
        assert 'GB' in size_gb or 'ГБ' in size_gb
    
    def test_is_rtl_locale(self):
        """Test RTL locale detection."""
        service = LocalizationService()
        
        # Current supported locales are LTR
        assert service.is_rtl_locale('en') is False
        assert service.is_rtl_locale('de') is False
        assert service.is_rtl_locale('uk') is False
        
        # Test RTL locales (for future support)
        assert service.is_rtl_locale('ar') is True
        assert service.is_rtl_locale('he') is True
    
    def test_get_locale_info(self):
        """Test getting locale information."""
        service = LocalizationService()
        
        # Test English
        info_en = service.get_locale_info('en')
        assert info_en['code'] == 'en-US'
        assert info_en['direction'] == 'ltr'
        assert info_en['currency_symbol'] == '$'
        
        # Test German
        info_de = service.get_locale_info('de')
        assert info_de['code'] == 'de-DE'
        assert info_de['direction'] == 'ltr'
        assert info_de['currency_symbol'] == '€'
        
        # Test Ukrainian
        info_uk = service.get_locale_info('uk')
        assert info_uk['code'] == 'uk-UA'
        assert info_uk['direction'] == 'ltr'
        assert info_uk['currency_symbol'] == '₴'


class TestEmailLocalizationService:
    """Test email localization service."""
    
    @patch('app.services.email_localization_service.current_app')
    def test_init(self, mock_app):
        """Test service initialization."""
        mock_app.root_path = '/app'
        
        service = EmailLocalizationService()
        assert service.template_dir.endswith('templates/email')
    
    @patch('builtins.open', create=True)
    @patch('os.path.exists')
    @patch('app.services.email_localization_service.current_app')
    def test_get_localized_template_exists(self, mock_app, mock_exists, mock_open):
        """Test getting localized template when it exists."""
        mock_app.root_path = '/app'
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = 'Hallo {{name}}'
        
        service = EmailLocalizationService()
        template = service.get_localized_template('welcome', 'de')
        
        assert template == 'Hallo {{name}}'
    
    @patch('builtins.open', create=True)
    @patch('os.path.exists')
    @patch('app.services.email_localization_service.current_app')
    def test_get_localized_template_fallback(self, mock_app, mock_exists, mock_open):
        """Test getting localized template with fallback to English."""
        mock_app.root_path = '/app'
        
        def exists_side_effect(path):
            return 'welcome_en.html' in path
        
        mock_exists.side_effect = exists_side_effect
        mock_open.return_value.__enter__.return_value.read.return_value = 'Hello {{name}}'
        
        service = EmailLocalizationService()
        template = service.get_localized_template('welcome', 'de')
        
        assert template == 'Hello {{name}}'
    
    @patch('jinja2.Template')
    @patch('app.services.email_localization_service.current_app')
    def test_render_localized_email(self, mock_app, mock_template_class):
        """Test rendering localized email."""
        mock_app.root_path = '/app'
        mock_template = Mock()
        mock_template.render.return_value = 'Hello John'
        mock_template_class.return_value = mock_template
        
        service = EmailLocalizationService()
        
        with patch.object(service, 'get_localized_template', return_value='Hello {{name}}'):
            result = service.render_localized_email('welcome', {'name': 'John'}, 'en')
            assert result == 'Hello John'
    
    @patch('flask_babel.gettext')
    def test_get_localized_subject(self, mock_gettext):
        """Test getting localized email subject."""
        mock_gettext.return_value = 'Willkommen bei AI Secretary'
        
        service = EmailLocalizationService()
        
        with patch('app.utils.i18n.get_user_language', return_value='de'):
            subject = service.get_localized_subject('welcome_subject', 'de')
            assert subject == 'Willkommen bei AI Secretary'
    
    @patch('app.services.email_localization_service.send_email')
    def test_send_localized_email(self, mock_send_email):
        """Test sending localized email."""
        mock_send_email.return_value = True
        
        service = EmailLocalizationService()
        mock_user = Mock()
        mock_user.email = 'test@example.com'
        mock_user.language = 'de'
        
        with patch.object(service, 'render_localized_email', return_value='Hallo John'):
            with patch.object(service, 'get_localized_subject', return_value='Willkommen'):
                result = service.send_localized_email(
                    mock_user, 'welcome', {'name': 'John'}
                )
                assert result is True
                mock_send_email.assert_called_once()


class TestI18nIntegration:
    """Test i18n integration functions."""
    
    @patch('app.utils.i18n.language_detection')
    def test_get_user_language(self, mock_detection):
        """Test get_user_language function."""
        mock_detection.get_user_language.return_value = 'de'
        
        result = get_user_language()
        assert result == 'de'
        mock_detection.get_user_language.assert_called_once()
    
    @patch('app.utils.i18n.language_detection')
    def test_set_user_language(self, mock_detection):
        """Test set_user_language function."""
        mock_detection.set_user_language.return_value = True
        
        result = set_user_language('de', user_id=1)
        assert result is True
        mock_detection.set_user_language.assert_called_once_with('de', 1)
    
    @patch('app.utils.i18n.translation_cache')
    def test_get_cached_translation(self, mock_cache):
        """Test cached translation retrieval."""
        mock_cache.get_cached_translation.return_value = 'Hallo'
        
        result = get_cached_translation('Hello', 'de')
        assert result == 'Hallo'
        mock_cache.get_cached_translation.assert_called_once_with('Hello', 'de')
    
    @patch('app.utils.i18n.translation_cache')
    def test_invalidate_translation_cache(self, mock_cache):
        """Test translation cache invalidation."""
        invalidate_translation_cache('de')
        mock_cache.invalidate_cache.assert_called_once_with('de')
    
    @patch('app.utils.i18n.get_user_language')
    def test_get_translation_context(self, mock_get_language):
        """Test translation context retrieval."""
        mock_get_language.return_value = 'de'
        
        with patch('app.utils.i18n.get_locale_info', return_value={'code': 'de-DE'}):
            context = get_translation_context()
            
            assert context['current_language'] == 'de'
            assert context['available_languages'] == LANGUAGES
            assert 'locale_info' in context


class TestTranslationCache:
    """Test translation caching utility."""
    
    def test_init(self):
        """Test cache initialization."""
        cache = TranslationCache()
        assert cache.cache_timeout == 3600
    
    @patch('app.utils.i18n.cache')
    @patch('app.utils.i18n.current_app')
    @patch('app.utils.i18n.session', {})
    @patch('flask_babel.gettext')
    def test_get_cached_translation(self, mock_gettext, mock_app, mock_cache):
        """Test getting cached translation."""
        mock_gettext.return_value = 'Hallo'
        mock_app.test_request_context.return_value.__enter__ = Mock()
        mock_app.test_request_context.return_value.__exit__ = Mock()
        
        cache = TranslationCache()
        
        # Mock the memoize decorator
        mock_cache.memoize.return_value = lambda func: func
        
        result = cache.get_cached_translation('Hello', 'de')
        assert result == 'Hallo'
    
    @patch('app.utils.i18n.cache')
    def test_invalidate_cache_specific_locale(self, mock_cache):
        """Test invalidating cache for specific locale."""
        cache = TranslationCache()
        cache.invalidate_cache('de')
        mock_cache.delete_memoized.assert_called_once()
    
    @patch('app.utils.i18n.cache')
    def test_invalidate_cache_all_locales(self, mock_cache):
        """Test invalidating cache for all locales."""
        cache = TranslationCache()
        cache.invalidate_cache()
        mock_cache.delete_memoized.assert_called_once()


class TestSystemMessages:
    """Test system message translations."""
    
    def test_system_messages_exist(self):
        """Test that system messages are defined."""
        assert hasattr(SystemMessages, 'LOGIN_REQUIRED')
        assert hasattr(SystemMessages, 'INVALID_CREDENTIALS')
        assert hasattr(SystemMessages, 'FIELD_REQUIRED')
        assert hasattr(SystemMessages, 'ACCESS_DENIED')
        assert hasattr(SystemMessages, 'NOT_FOUND')
        assert hasattr(SystemMessages, 'CREATED_SUCCESSFULLY')
    
    def test_business_messages_exist(self):
        """Test that business messages are defined."""
        assert hasattr(BusinessMessages, 'LEAD_CREATED')
        assert hasattr(BusinessMessages, 'CONTACT_ADDED')
        assert hasattr(BusinessMessages, 'MESSAGE_SENT')
        assert hasattr(BusinessMessages, 'TASK_ASSIGNED')
        assert hasattr(BusinessMessages, 'EVENT_CREATED')


class TestErrorMessageTranslation:
    """Test error message translation functionality."""
    
    def test_translate_error_message_basic(self):
        """Test basic error message translation."""
        message = translate_error_message('VALIDATION_ERROR')
        assert isinstance(message, str)
        assert len(message) > 0
    
    def test_translate_error_message_with_params(self):
        """Test error message translation with parameters."""
        message = translate_error_message('NOT_FOUND_ERROR', resource='User')
        assert isinstance(message, str)
        assert len(message) > 0
    
    def test_translate_error_message_unknown(self):
        """Test translation of unknown error code."""
        message = translate_error_message('UNKNOWN_ERROR_CODE')
        assert 'Unknown error' in message or 'UNKNOWN_ERROR_CODE' in message


class TestLocalizationFormatting:
    """Test localization formatting functions."""
    
    def test_get_localized_date_format(self):
        """Test getting localized date format."""
        with patch('app.utils.i18n.get_locale', return_value='de'):
            format_str = get_localized_date_format()
            assert format_str == '%d.%m.%Y'
        
        with patch('app.utils.i18n.get_locale', return_value='en'):
            format_str = get_localized_date_format()
            assert format_str == '%m/%d/%Y'
        
        with patch('app.utils.i18n.get_locale', return_value='uk'):
            format_str = get_localized_date_format()
            assert format_str == '%d.%m.%Y'
    
    def test_format_currency_basic(self):
        """Test basic currency formatting."""
        with patch('app.utils.i18n.get_locale', return_value='de'):
            formatted = format_currency(1234.56, 'EUR')
            assert isinstance(formatted, str)
            assert 'EUR' in formatted
            assert '1234' in formatted or '1.234' in formatted
    
    def test_format_currency_with_service(self):
        """Test currency formatting with localization service."""
        mock_service = Mock()
        mock_service.format_currency.return_value = '€ 1.234,56'
        
        with patch('app.services.localization_service.LocalizationService', return_value=mock_service):
            formatted = format_currency(1234.56, 'EUR')
            assert formatted == '€ 1.234,56'


@pytest.fixture
def app_context():
    """Provide Flask app context for tests."""
    from app import create_app
    app = create_app('testing')
    
    with app.app_context():
        yield app


class TestI18nWithAppContext:
    """Test i18n functionality with Flask app context."""
    
    def test_language_detection_with_context(self, app_context):
        """Test language detection within app context."""
        with app_context.test_request_context('/?lang=de'):
            service = LanguageDetectionService()
            # Should initialize without errors
            assert service.cache_timeout == 300
    
    def test_translation_service_with_context(self, app_context):
        """Test translation service within app context."""
        service = TranslationService()
        # Should initialize without errors
        assert service.supported_languages == LANGUAGES
    
    def test_localization_service_with_context(self, app_context):
        """Test localization service within app context."""
        service = LocalizationService()
        
        # Test basic functionality
        assert service.default_locale == 'en'
        assert len(service.supported_locales) >= 3
    
    def test_email_localization_service_with_context(self, app_context):
        """Test email localization service within app context."""
        service = EmailLocalizationService()
        # Should initialize without errors
        assert service.template_dir.endswith('templates/email')


class TestI18nConstants:
    """Test i18n constants and configuration."""
    
    def test_languages_constant(self):
        """Test LANGUAGES constant."""
        assert isinstance(LANGUAGES, dict)
        assert 'en' in LANGUAGES
        assert 'de' in LANGUAGES
        assert 'uk' in LANGUAGES
        assert LANGUAGES['en'] == 'English'
        assert LANGUAGES['de'] == 'Deutsch'
        assert LANGUAGES['uk'] == 'Українська'
    
    def test_supported_languages_count(self):
        """Test that we have the expected number of supported languages."""
        assert len(LANGUAGES) == 3
    
    def test_language_codes_format(self):
        """Test that language codes are in correct format."""
        for code in LANGUAGES.keys():
            assert isinstance(code, str)
            assert len(code) == 2
            assert code.islower()
    
    def test_language_names_format(self):
        """Test that language names are properly formatted."""
        for name in LANGUAGES.values():
            assert isinstance(name, str)
            assert len(name) > 0