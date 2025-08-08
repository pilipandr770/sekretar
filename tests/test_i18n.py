"""Test internationalization functionality."""
import pytest
from flask import session
from app.utils.i18n import (
    get_user_language, set_user_language, get_available_languages,
    format_currency, get_localized_date_format
)
from app.models.tenant import Tenant
from app.models.user import User


class TestI18n:
    """Test i18n functionality."""
    
    def test_available_languages(self, app):
        """Test getting available languages."""
        with app.app_context():
            languages = get_available_languages()
            
            assert 'en' in languages
            assert 'de' in languages
            assert 'uk' in languages
            assert languages['en'] == 'English'
            assert languages['de'] == 'Deutsch'
            assert languages['uk'] == 'Українська'
    
    def test_set_user_language(self, app):
        """Test setting user language."""
        with app.test_request_context():
            # Test valid language
            assert set_user_language('de') is True
            assert session['language'] == 'de'
            
            # Test invalid language
            assert set_user_language('fr') is False
            assert session['language'] == 'de'  # Should remain unchanged
    
    def test_get_user_language_from_session(self, app):
        """Test getting language from session."""
        with app.test_request_context():
            session['language'] = 'de'
            assert get_user_language() == 'de'
    
    def test_get_user_language_default(self, app):
        """Test default language when none set."""
        with app.test_request_context():
            # Should default to English
            assert get_user_language() == 'en'
    
    def test_currency_formatting(self, app):
        """Test currency formatting for different locales."""
        with app.test_request_context():
            # Test German formatting
            session['language'] = 'de'
            formatted = format_currency(1234.56, 'EUR')
            assert '1.234,56' in formatted
            assert 'EUR' in formatted
            
            # Test English formatting
            session['language'] = 'en'
            formatted = format_currency(1234.56, 'EUR')
            assert '1,234.56' in formatted
            assert 'EUR' in formatted
    
    def test_date_format_localization(self, app):
        """Test date format localization."""
        with app.test_request_context():
            # Test German format
            session['language'] = 'de'
            format_str = get_localized_date_format()
            assert format_str == '%d.%m.%Y'
            
            # Test English format
            session['language'] = 'en'
            format_str = get_localized_date_format()
            assert format_str == '%m/%d/%Y'
            
            # Test Ukrainian format
            session['language'] = 'uk'
            format_str = get_localized_date_format()
            assert format_str == '%d.%m.%Y'


class TestI18nAPI:
    """Test i18n API endpoints."""
    
    def test_get_languages_endpoint(self, client):
        """Test getting available languages via API."""
        response = client.get('/api/v1/languages')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert 'languages' in data['data']
        assert 'current' in data['data']
        assert 'en' in data['data']['languages']
        assert 'de' in data['data']['languages']
        assert 'uk' in data['data']['languages']
    
    def test_set_language_endpoint(self, client):
        """Test setting language via API."""
        # Test valid language
        response = client.post('/api/v1/language', json={'language': 'de'})
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['language'] == 'de'
        
        # Test invalid language
        response = client.post('/api/v1/language', json={'language': 'fr'})
        assert response.status_code == 400
        
        data = response.get_json()
        assert data['success'] is False
        assert 'Invalid language code' in data['error']['message']
    
    def test_set_language_missing_data(self, client):
        """Test setting language with missing data."""
        response = client.post('/api/v1/language', json={})
        assert response.status_code == 400
        
        data = response.get_json()
        assert data['success'] is False
        assert 'Language code is required' in data['error']['message']


class TestUserLanguagePreference:
    """Test user language preferences."""
    
    def test_user_language_in_profile(self, app):
        """Test user language preference in profile."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id,
                language="de"
            )
            
            assert user.language == "de"
            
            # Test language in to_dict
            user_dict = user.to_dict()
            assert 'language' in user_dict
            assert user_dict['language'] == 'de'
    
    def test_user_language_update(self, app):
        """Test updating user language preference."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id,
                language="en"
            )
            
            # Update language
            user.language = "de"
            user.save()
            
            # Verify update
            updated_user = User.query.get(user.id)
            assert updated_user.language == "de"


class TestTranslationMessages:
    """Test translation message functionality."""
    
    def test_system_messages_import(self, app):
        """Test importing system messages."""
        with app.app_context():
            from app.utils.i18n import SystemMessages
            
            # Test that messages are accessible
            assert hasattr(SystemMessages, 'LOGIN_REQUIRED')
            assert hasattr(SystemMessages, 'INVALID_CREDENTIALS')
            assert hasattr(SystemMessages, 'FIELD_REQUIRED')
    
    def test_business_messages_import(self, app):
        """Test importing business messages."""
        with app.app_context():
            from app.utils.i18n import BusinessMessages
            
            # Test that messages are accessible
            assert hasattr(BusinessMessages, 'LEAD_CREATED')
            assert hasattr(BusinessMessages, 'CONTACT_ADDED')
            assert hasattr(BusinessMessages, 'MESSAGE_SENT')
    
    def test_error_message_translation(self, app):
        """Test error message translation."""
        with app.app_context():
            from app.utils.i18n import translate_error_message
            
            # Test basic error translation
            message = translate_error_message('VALIDATION_ERROR')
            assert isinstance(message, str)
            assert len(message) > 0
            
            # Test with parameters
            message = translate_error_message('NOT_FOUND_ERROR')
            assert isinstance(message, str)
            assert len(message) > 0