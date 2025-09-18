"""
Comprehensive test suite for i18n functionality.
Tests all translation services, utilities, and integration points.
This is the main test file that covers all i18n requirements.
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
from app.services.translation_service import TranslationService, TranslationValidationError
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
        
        service = TranslationService()
        assert str(service.translations_dir).endswith('translations')
        assert str(service.template_dir).endswith('templates')
    
    @patch('app.services.translation_service.extract_from_dir')
    @patch('app.services.translation_service.write_po')
    @patch('app.services.translation_service.current_app')
    def test_extract_messages_success(self, mock_app, mock_write_po, mock_extract):
        """Test successful message extraction."""
        mock_app.root_path = '/app'
        
        # Mock extraction results
        mock_extract.return_value = [
            ('test.py', 1, 'Hello', [], None),
            ('test.py', 2, 'World', [], None)
        ]
        
        service = TranslationService()
        
        with patch.object(service.translations_dir, 'mkdir'):
            with patch.object(service, '_update_po_file', return_value=True):
                result = service.extract_messages()
                
                assert 'extracted_messages' in result
                assert 'total_unique_messages' in result
                assert 'updated_languages' in result
    
    @patch('builtins.open', create=True)
    @patch('app.services.translation_service.read_po')
    @patch('app.services.translation_service.write_po')
    @patch('app.services.translation_service.current_app')
    def test_get_translation_coverage(self, mock_app, mock_write_po, mock_read_po, mock_open):
        """Test translation coverage calculation."""
        mock_app.root_path = '/app'
        
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
        
        with patch.object(service.translations_dir, 'exists', return_value=True):
            coverage = service.get_translation_coverage()
            
            # Should have coverage for all languages
            assert 'en' in coverage
            assert 'de' in coverage
            assert 'uk' in coverage
    
    @patch('builtins.open', create=True)
    @patch('app.services.translation_service.read_po')
    @patch('app.services.translation_service.current_app')
    def test_validate_translations(self, mock_app, mock_read_po, mock_open):
        """Test translation validation."""
        mock_app.root_path = '/app'
        
        # Mock catalog with validation issues
        mock_catalog = Mock()
        mock_messages = [
            Mock(id='hello', string='hallo', locations=[('test.py', 1)], fuzzy=False),
            Mock(id='missing', string='', locations=[('test.py', 2)], fuzzy=False),  # missing translation
            Mock(id='placeholder_test %(name)s', string='test', locations=[('test.py', 3)], fuzzy=False),  # missing placeholder
        ]
        mock_catalog.__iter__ = Mock(return_value=iter(mock_messages))
        mock_read_po.return_value = mock_catalog
        
        service = TranslationService()
        
        with patch.object(service.translations_dir, 'exists', return_value=True):
            errors = service.validate_translations()
            
            # Should find validation errors
            assert len(errors) > 0
            assert any(error['type'] == 'missing_translation' for error in errors)
    
    @patch('builtins.open', create=True)
    @patch('app.services.translation_service.read_po')
    @patch('app.services.translation_service.current_app')
    def test_get_missing_translations(self, mock_app, mock_read_po, mock_open):
        """Test getting missing translations."""
        mock_app.root_path = '/app'
        
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
        
        with patch.object(service.translations_dir, 'exists', return_value=True):
            missing = service.get_missing_translations()
            
            # Should find missing translations for non-English languages
            assert 'de' in missing
            assert 'missing1' in missing['de']
            assert 'missing2' in missing['de']
    
    def test_validation_error(self):
        """Test TranslationValidationError class."""
        error = TranslationValidationError('Test error message')
        assert str(error) == 'Test error message'
        assert isinstance(error, Exception)


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
    
    def test_get_locale_info(self):
        """Test getting locale information."""
        service = LocalizationService()
        
        # Test English
        info_en = service.get_locale_info('en')
        assert isinstance(info_en, dict)
        
        # Test German
        info_de = service.get_locale_info('de')
        assert isinstance(info_de, dict)
        
        # Test Ukrainian
        info_uk = service.get_locale_info('uk')
        assert isinstance(info_uk, dict)


class TestEmailLocalizationService:
    """Test email localization service."""
    
    def test_init(self):
        """Test service initialization."""
        service = EmailLocalizationService()
        assert service.fallback_language == 'en'
        assert service.template_cache == {}
    
    def test_get_user_language_preference_with_user_language(self):
        """Test getting user language preference when user has language set."""
        service = EmailLocalizationService()
        
        mock_user = Mock()
        mock_user.language = 'de'
        
        language = service.get_user_language_preference(mock_user)
        assert language == 'de'
    
    def test_get_user_language_preference_fallback(self):
        """Test getting user language preference with fallback."""
        service = EmailLocalizationService()
        
        mock_user = Mock()
        mock_user.language = None
        mock_user.tenant_id = None
        
        language = service.get_user_language_preference(mock_user)
        assert language == 'en'
    
    @patch('jinja2.Environment.get_template')
    def test_get_localized_template_exists(self, mock_get_template):
        """Test getting localized template when it exists."""
        mock_template = Mock()
        mock_get_template.return_value = mock_template
        
        service = EmailLocalizationService()
        template = service.get_localized_template('welcome', 'de')
        
        assert template == mock_template
    
    @patch('jinja2.Environment.get_template')
    def test_get_localized_template_not_found(self, mock_get_template):
        """Test getting localized template when it doesn't exist."""
        from jinja2 import TemplateNotFound
        mock_get_template.side_effect = TemplateNotFound('template not found')
        
        service = EmailLocalizationService()
        template = service.get_localized_template('welcome', 'de')
        
        assert template is None
    
    def test_render_localized_email_success(self):
        """Test rendering localized email successfully."""
        service = EmailLocalizationService()
        
        mock_template = Mock()
        mock_template.render.return_value = 'Subject: Welcome\n\nHello World'
        
        with patch.object(service, 'get_localized_template', return_value=mock_template):
            subject, content = service.render_localized_email('welcome', {}, 'en')
            
            assert subject == 'Welcome'
            assert 'Hello World' in content
    
    def test_render_localized_email_failure(self):
        """Test rendering localized email failure."""
        service = EmailLocalizationService()
        
        with patch.object(service, 'get_localized_template', return_value=None):
            subject, content = service.render_localized_email('welcome', {}, 'en')
            
            assert subject is None
            assert content is None
    
    @patch('flask_babel.gettext')
    @patch('app.services.email_localization_service.current_app')
    def test_get_localized_subject(self, mock_app, mock_gettext):
        """Test getting localized email subject."""
        mock_gettext.return_value = 'Willkommen bei AI Secretary'
        mock_app.test_request_context.return_value.__enter__ = Mock()
        mock_app.test_request_context.return_value.__exit__ = Mock()
        
        service = EmailLocalizationService()
        
        with patch('flask.session', {}):
            subject = service.get_localized_subject('welcome_subject', 'de')
            assert subject == 'Willkommen bei AI Secretary'
    
    def test_send_localized_email_success(self):
        """Test sending localized email successfully."""
        service = EmailLocalizationService()
        
        mock_user = Mock()
        mock_user.email = 'test@example.com'
        mock_user.language = 'de'
        mock_user.tenant_id = 1
        mock_user.id = 1
        
        with patch.object(service, 'render_localized_email', return_value=('Subject', 'Content')):
            with patch('app.services.notification_service.NotificationService') as mock_notification_service:
                mock_service = mock_notification_service.return_value
                mock_notification = Mock()
                mock_notification.id = 1
                mock_service.create_notification.return_value = mock_notification
                
                result = service.send_localized_email(mock_user, 'welcome', {})
                assert result is True
    
    def test_send_localized_email_failure(self):
        """Test sending localized email failure."""
        service = EmailLocalizationService()
        
        mock_user = Mock()
        mock_user.email = 'test@example.com'
        mock_user.language = 'de'
        
        with patch.object(service, 'render_localized_email', return_value=(None, None)):
            result = service.send_localized_email(mock_user, 'welcome', {})
            assert result is False
    
    def test_extract_subject_and_content_with_subject(self):
        """Test extracting subject and content when subject is present."""
        service = EmailLocalizationService()
        
        rendered_content = 'Subject: Welcome\n\nHello World'
        subject, content = service._extract_subject_and_content(rendered_content)
        
        assert subject == 'Welcome'
        assert 'Hello World' in content
    
    def test_extract_subject_and_content_without_subject(self):
        """Test extracting subject and content when no subject is present."""
        service = EmailLocalizationService()
        
        rendered_content = 'Hello World'
        subject, content = service._extract_subject_and_content(rendered_content)
        
        assert subject is None
        assert content == 'Hello World'
    
    def test_html_to_text_with_beautifulsoup(self):
        """Test HTML to text conversion with BeautifulSoup."""
        service = EmailLocalizationService()
        
        html_content = '<h1>Hello</h1><p>World</p>'
        
        with patch('bs4.BeautifulSoup') as mock_soup:
            mock_soup_instance = Mock()
            mock_soup_instance.get_text.return_value = 'Hello\nWorld'
            mock_soup.return_value = mock_soup_instance
            
            text = service._html_to_text(html_content)
            assert text == 'Hello\nWorld'
    
    def test_html_to_text_fallback(self):
        """Test HTML to text conversion fallback."""
        service = EmailLocalizationService()
        
        html_content = '<h1>Hello</h1><p>World</p>'
        
        with patch('bs4.BeautifulSoup', side_effect=ImportError):
            text = service._html_to_text(html_content)
            assert 'Hello' in text
            assert 'World' in text
            assert '<h1>' not in text
    
    def test_clear_template_cache(self):
        """Test clearing template cache."""
        service = EmailLocalizationService()
        service.template_cache = {'welcome_en': 'template1', 'welcome_de': 'template2'}
        
        # Clear specific template and language
        service.clear_template_cache('welcome', 'en')
        assert 'welcome_en' not in service.template_cache
        assert 'welcome_de' in service.template_cache
        
        # Clear all variants of template
        service.clear_template_cache('welcome')
        assert len(service.template_cache) == 0
    
    def test_validate_template_success(self):
        """Test template validation success."""
        service = EmailLocalizationService()
        
        mock_template = Mock()
        
        with patch.object(service, 'get_localized_template', return_value=mock_template):
            with patch.object(service, 'render_localized_email', return_value=('Subject', 'Content')):
                result = service.validate_template('welcome', 'en')
                
                assert result['valid'] is True
                assert result['exists'] is True
                assert len(result['errors']) == 0
    
    def test_validate_template_not_found(self):
        """Test template validation when template not found."""
        service = EmailLocalizationService()
        
        with patch.object(service, 'get_localized_template', return_value=None):
            result = service.validate_template('welcome', 'en')
            
            assert result['valid'] is False
            assert result['exists'] is False
            assert len(result['errors']) > 0


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
        assert hasattr(SystemMessages, 'CREATED_SUCCESSFULLY')
        assert hasattr(SystemMessages, 'NOT_FOUND')
        assert hasattr(SystemMessages, 'TRIAL_EXPIRED')
        assert hasattr(SystemMessages, 'AI_PROCESSING_FAILED')
        assert hasattr(SystemMessages, 'FILE_TOO_LARGE')
    
    def test_business_messages_exist(self):
        """Test that business messages are defined."""
        assert hasattr(BusinessMessages, 'LEAD_CREATED')
        assert hasattr(BusinessMessages, 'TASK_ASSIGNED')
        assert hasattr(BusinessMessages, 'CONTACT_ADDED')
        assert hasattr(BusinessMessages, 'CHANNEL_CONNECTED')
        assert hasattr(BusinessMessages, 'MESSAGE_SENT')
        assert hasattr(BusinessMessages, 'EVENT_CREATED')
        assert hasattr(BusinessMessages, 'DOCUMENT_UPLOADED')


class TestErrorMessageTranslation:
    """Test error message translation functionality."""
    
    def test_translate_error_message_known_code(self):
        """Test translating known error codes."""
        result = translate_error_message('VALIDATION_ERROR')
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_translate_error_message_unknown_code(self):
        """Test translating unknown error codes."""
        result = translate_error_message('UNKNOWN_ERROR_CODE')
        assert isinstance(result, str)
        assert 'Unknown error' in result or 'UNKNOWN_ERROR_CODE' in result
    
    def test_translate_error_message_with_params(self):
        """Test translating error messages with parameters."""
        result = translate_error_message('VALIDATION_ERROR', field='email')
        assert isinstance(result, str)
        assert len(result) > 0


class TestLocalizationHelpers:
    """Test localization helper functions."""
    
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
    
    def test_format_currency_helper(self):
        """Test currency formatting helper."""
        with patch('app.utils.i18n.get_locale', return_value='de'):
            formatted = format_currency(1234.56, 'EUR')
            assert isinstance(formatted, str)
            assert 'EUR' in formatted
        
        with patch('app.utils.i18n.get_locale', return_value='en'):
            formatted = format_currency(1234.56, 'USD')
            assert isinstance(formatted, str)
            assert 'USD' in formatted


if __name__ == '__main__':
    pytest.main([__file__, '-v'])