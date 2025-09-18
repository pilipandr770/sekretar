"""Tests for enhanced i18n infrastructure and services."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
from flask import session, g

from app.utils.i18n import (
    LanguageDetectionService, get_user_language, set_user_language,
    get_cached_translation, invalidate_translation_cache,
    get_translation_context, LANGUAGES
)
from app.services.translation_service import TranslationService, ValidationError
from app.services.localization_service import LocalizationService


class TestLanguageDetectionService:
    """Test enhanced language detection service."""
    
    def test_init(self):
        """Test service initialization."""
        service = LanguageDetectionService()
        assert service.cache_timeout == 300
    
    def test_validate_language_code(self):
        """Test language code validation."""
        service = LanguageDetectionService()
        
        assert service.validate_language_code('en') is True
        assert service.validate_language_code('de') is True
        assert service.validate_language_code('uk') is True
        assert service.validate_language_code('fr') is False
        assert service.validate_language_code('invalid') is False
    
    @patch('app.utils.i18n.request')
    def test_detect_language_from_url(self, mock_request):
        """Test language detection from URL parameter."""
        service = LanguageDetectionService()
        mock_request.args.get.return_value = 'de'
        
        with patch('app.utils.i18n.session', {}) as mock_session:
            language = service._detect_language()
            assert language == 'de'
            assert mock_session['language'] == 'de'
    
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
        
        with patch('flask_jwt_extended.get_current_user', return_value=mock_user):
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
    
    @patch('app.utils.i18n.session', {})
    def test_set_user_language_valid(self):
        """Test setting valid user language."""
        service = LanguageDetectionService()
        
        with patch('app.utils.i18n.cache') as mock_cache:
            result = service.set_user_language('de')
            assert result is True
            mock_cache.delete_memoized.assert_called_once()
    
    def test_set_user_language_invalid(self):
        """Test setting invalid user language."""
        service = LanguageDetectionService()
        
        result = service.set_user_language('invalid')
        assert result is False


class TestTranslationService:
    """Test translation management service."""
    
    @patch('app.services.translation_service.current_app')
    def test_init(self, mock_app):
        """Test service initialization."""
        mock_app.root_path = '/app'
        mock_app.config.get.return_value = LANGUAGES
        
        service = TranslationService()
        assert service.supported_languages == LANGUAGES
    
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
        
        # Should have coverage for de and uk (en is 100% by default)
        assert 'en' in coverage
        assert coverage['en'] == 100.0
        assert 'de' in coverage
        assert coverage['de'] == pytest.approx(66.67, rel=1e-2)  # 2/3 translated
    
    def test_validation_error(self):
        """Test ValidationError class."""
        error = ValidationError('de', 'hello', 'Missing translation')
        assert error.language == 'de'
        assert error.key == 'hello'
        assert error.error == 'Missing translation'
        assert 'ValidationError' in repr(error)


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
    
    @patch('babel.dates.format_date')
    def test_format_date(self, mock_format_date):
        """Test date formatting."""
        mock_format_date.return_value = '15.09.2023'
        
        service = LocalizationService()
        date = datetime(2023, 9, 15)
        formatted = service.format_date(date, locale='de')
        
        assert formatted == '15.09.2023'
        mock_format_date.assert_called_once()
    
    @patch('babel.numbers.format_currency')
    def test_format_currency(self, mock_format_currency):
        """Test currency formatting."""
        mock_format_currency.return_value = '€ 1.234,56'
        
        service = LocalizationService()
        formatted = service.format_currency(1234.56, 'EUR', 'de')
        
        assert formatted == '€ 1.234,56'
        mock_format_currency.assert_called_once()
    
    @patch('babel.numbers.format_decimal')
    def test_format_number(self, mock_format_decimal):
        """Test number formatting."""
        mock_format_decimal.return_value = '1.234,56'
        
        service = LocalizationService()
        formatted = service.format_number(1234.56, 'de')
        
        assert formatted == '1.234,56'
        mock_format_decimal.assert_called_once()
    
    @patch('app.services.localization_service.get_locale')
    def test_get_relative_time_past(self, mock_get_locale):
        """Test relative time formatting for past dates."""
        mock_get_locale.return_value = 'en'
        
        service = LocalizationService()
        past_time = datetime.utcnow() - timedelta(hours=2)
        
        with patch('app.services.localization_service.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime.utcnow()
            relative = service.get_relative_time(past_time)
            assert 'ago' in relative or 'тому' in relative or 'vor' in relative
    
    @patch('app.services.localization_service.get_locale')
    def test_get_relative_time_future(self, mock_get_locale):
        """Test relative time formatting for future dates."""
        mock_get_locale.return_value = 'en'
        
        service = LocalizationService()
        future_time = datetime.utcnow() + timedelta(hours=2)
        
        with patch('app.services.localization_service.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime.utcnow()
            relative = service.get_relative_time(future_time)
            assert 'in' in relative or 'через' in relative
    
    @patch('flask_babel.ngettext')
    def test_pluralize(self, mock_ngettext):
        """Test pluralization."""
        mock_ngettext.return_value = 'items'
        
        service = LocalizationService()
        result = service.pluralize(2, 'item', 'items')
        
        assert result == 'items'
        mock_ngettext.assert_called_once_with('item', 'items', 2)
    
    def test_format_file_size(self):
        """Test file size formatting."""
        service = LocalizationService()
        
        # Test bytes
        assert 'B' in service.format_file_size(0)
        assert 'B' in service.format_file_size(512)
        
        # Test KB
        size_kb = service.format_file_size(1024)
        assert 'KB' in size_kb or 'КБ' in size_kb
        
        # Test MB
        size_mb = service.format_file_size(1024 * 1024)
        assert 'MB' in size_mb or 'МБ' in size_mb
    
    def test_is_rtl_locale(self):
        """Test RTL locale detection."""
        service = LocalizationService()
        
        # Current supported locales are LTR
        assert service.is_rtl_locale('en') is False
        assert service.is_rtl_locale('de') is False
        assert service.is_rtl_locale('uk') is False


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
        
        context = get_translation_context()
        
        assert context['current_language'] == 'de'
        assert context['available_languages'] == LANGUAGES
        assert 'locale_info' in context


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
            language = service._detect_language()
            # Should detect from URL parameter
            assert language in LANGUAGES
    
    def test_translation_service_with_context(self, app_context):
        """Test translation service within app context."""
        service = TranslationService()
        # Should initialize without errors
        assert service.supported_languages == LANGUAGES
    
    def test_localization_service_with_context(self, app_context):
        """Test localization service within app context."""
        service = LocalizationService()
        
        # Test basic formatting
        date = datetime(2023, 9, 15)
        formatted = service.format_date(date)
        assert isinstance(formatted, str)
        
        # Test number formatting
        formatted_num = service.format_number(1234.56)
        assert isinstance(formatted_num, str)