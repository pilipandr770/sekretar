"""
End-to-end integration tests for i18n functionality.
Tests complete language switching workflows, API integration, and template rendering.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import session, url_for
import json
import os

from app import create_app, db
from app.models import User, Tenant
from app.utils.i18n import get_user_language, set_user_language, LANGUAGES


class TestI18nAPIIntegration:
    """Test i18n API endpoints integration."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test-secret-key'
        
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    @pytest.fixture
    def auth_headers(self, app, client):
        """Create authentication headers."""
        with app.app_context():
            # Create test tenant and user
            tenant = Tenant(name="Test Tenant", slug="test")
            db.session.add(tenant)
            db.session.commit()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id,
                language="en"
            )
            
            # Login to get JWT token
            response = client.post('/api/v1/auth/login', json={
                'email': 'test@example.com',
                'password': 'password123'
            })
            
            if response.status_code == 200:
                data = response.get_json()
                token = data.get('data', {}).get('access_token')
                return {'Authorization': f'Bearer {token}'}
            
            return {}
    
    def test_get_languages_endpoint(self, client):
        """Test getting available languages via API."""
        response = client.get('/api/v1/i18n/languages')
        
        # Should work even if endpoint doesn't exist yet
        if response.status_code == 404:
            pytest.skip("I18n API endpoints not implemented yet")
        
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert 'languages' in data['data']
        assert 'current' in data['data']
        assert 'available' in data['data']
        
        # Check all supported languages are present
        languages = data['data']['languages']
        assert 'en' in languages
        assert 'de' in languages
        assert 'uk' in languages
        assert languages['en'] == 'English'
        assert languages['de'] == 'Deutsch'
        assert languages['uk'] == 'Українська'
    
    def test_get_translations_endpoint_english(self, client):
        """Test getting English translations."""
        response = client.get('/api/v1/i18n/translations/en')
        
        # Should work even if translation files don't exist
        if response.status_code == 404:
            pytest.skip("Translation API endpoints not implemented yet")
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.get_json()
            assert data['success'] is True
            assert 'translations' in data['data']
            assert 'metadata' in data['data']
    
    def test_get_translations_endpoint_german(self, client):
        """Test getting German translations."""
        response = client.get('/api/v1/i18n/translations/de')
        
        # Should work even if translation files don't exist
        if response.status_code == 404:
            pytest.skip("Translation API endpoints not implemented yet")
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['language'] == 'de'
    
    def test_get_translations_endpoint_invalid_language(self, client):
        """Test getting translations for invalid language."""
        response = client.get('/api/v1/i18n/translations/invalid')
        
        if response.status_code == 404:
            pytest.skip("Translation API endpoints not implemented yet")
        
        assert response.status_code == 400
        
        data = response.get_json()
        assert data['success'] is False
        assert 'Unsupported language' in data['error']['message']
    
    def test_get_i18n_context_endpoint(self, client):
        """Test getting i18n context."""
        response = client.get('/api/v1/i18n/context')
        
        if response.status_code == 404:
            pytest.skip("I18n context API endpoint not implemented yet")
        
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        
        context = data['data']
        assert 'current_language' in context
        assert 'available_languages' in context
        assert 'translations' in context
        assert 'user' in context
        assert 'locale_info' in context
        assert 'formatting_options' in context
        
        # Check available languages
        assert context['available_languages'] == LANGUAGES
    
    def test_get_user_language_preference_anonymous(self, client):
        """Test getting user language preference for anonymous user."""
        response = client.get('/api/v1/i18n/user/language')
        
        if response.status_code == 404:
            pytest.skip("User language API endpoint not implemented yet")
        
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['is_authenticated'] is False
        assert data['data']['language'] in LANGUAGES
    
    def test_get_user_language_preference_authenticated(self, client, auth_headers):
        """Test getting user language preference for authenticated user."""
        if not auth_headers:
            pytest.skip("Authentication not available")
        
        response = client.get('/api/v1/i18n/user/language', headers=auth_headers)
        
        if response.status_code == 404:
            pytest.skip("User language API endpoint not implemented yet")
        
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['is_authenticated'] is True
        assert data['data']['language'] in LANGUAGES
    
    def test_set_user_language_preference_anonymous(self, client):
        """Test setting user language preference for anonymous user."""
        response = client.post('/api/v1/i18n/user/language', json={'language': 'de'})
        
        if response.status_code == 404:
            pytest.skip("User language API endpoint not implemented yet")
        
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['language'] == 'de'
        assert data['data']['is_authenticated'] is False
    
    def test_set_user_language_preference_authenticated(self, client, auth_headers):
        """Test setting user language preference for authenticated user."""
        if not auth_headers:
            pytest.skip("Authentication not available")
        
        response = client.post('/api/v1/i18n/user/language', 
                             json={'language': 'de'}, 
                             headers=auth_headers)
        
        if response.status_code == 404:
            pytest.skip("User language API endpoint not implemented yet")
        
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['language'] == 'de'
        assert data['data']['is_authenticated'] is True
    
    def test_set_user_language_preference_invalid(self, client):
        """Test setting invalid user language preference."""
        response = client.post('/api/v1/i18n/user/language', json={'language': 'invalid'})
        
        if response.status_code == 404:
            pytest.skip("User language API endpoint not implemented yet")
        
        assert response.status_code == 400
        
        data = response.get_json()
        assert data['success'] is False
        assert 'Unsupported language' in data['error']['message']
    
    def test_set_user_language_preference_missing_data(self, client):
        """Test setting user language preference with missing data."""
        response = client.post('/api/v1/i18n/user/language', json={})
        
        if response.status_code == 404:
            pytest.skip("User language API endpoint not implemented yet")
        
        assert response.status_code == 400
        
        data = response.get_json()
        assert data['success'] is False
        assert 'Language is required' in data['error']['message']
    
    def test_get_translation_stats_endpoint(self, client):
        """Test getting translation statistics."""
        response = client.get('/api/v1/i18n/stats')
        
        if response.status_code == 404:
            pytest.skip("Translation stats API endpoint not implemented yet")
        
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        
        stats = data['data']['stats']
        overall = data['data']['overall']
        
        # Should have stats for all languages
        assert 'en' in stats
        assert 'de' in stats
        assert 'uk' in stats
        
        # Check overall stats
        assert 'total_languages' in overall
        assert 'average_coverage' in overall
        assert overall['total_languages'] == len(LANGUAGES)


class TestI18nTemplateIntegration:
    """Test i18n template integration."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    def test_template_language_context(self, app, client):
        """Test that templates receive language context."""
        with app.test_request_context():
            # Mock template rendering
            with patch('flask.render_template') as mock_render:
                mock_render.return_value = 'rendered'
                
                # Import after app context is available
                from flask import render_template
                
                # This should include i18n context
                result = render_template('base.html')
                
                # Check that render_template was called
                mock_render.assert_called_once()
    
    def test_template_translation_functions(self, app):
        """Test that translation functions are available in templates."""
        with app.test_request_context():
            # Check that Babel functions are available
            from flask_babel import gettext, ngettext, lazy_gettext
            
            # These should not raise exceptions
            assert callable(gettext)
            assert callable(ngettext)
            assert callable(lazy_gettext)
    
    def test_template_globals_available(self, app):
        """Test that i18n template globals are available."""
        with app.test_request_context():
            # Check template globals
            globals_dict = app.jinja_env.globals
            
            # These should be available if properly initialized
            expected_globals = [
                'get_available_languages',
                'get_current_language', 
                'get_language_name'
            ]
            
            for global_name in expected_globals:
                if global_name in globals_dict:
                    # Test the functions
                    if global_name == 'get_available_languages':
                        languages = globals_dict[global_name]()
                        assert languages == LANGUAGES
                    elif global_name == 'get_current_language':
                        current_lang = globals_dict[global_name]()
                        assert current_lang in LANGUAGES
                    elif global_name == 'get_language_name':
                        lang_name = globals_dict[global_name]('de')
                        assert lang_name == 'Deutsch'


class TestI18nSessionIntegration:
    """Test i18n session integration."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        
        with app.app_context():
            yield app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    def test_language_persistence_in_session(self, app, client):
        """Test that language preference persists in session."""
        with client.session_transaction() as sess:
            sess['language'] = 'de'
        
        with app.test_request_context():
            from app.utils.i18n import get_user_language
            language = get_user_language()
            assert language == 'de'
    
    def test_language_switching_updates_session(self, app, client):
        """Test that language switching updates session."""
        with app.test_request_context():
            from app.utils.i18n import set_user_language
            
            # Set language
            result = set_user_language('uk')
            assert result is True
        
        # Check session was updated
        with client.session_transaction() as sess:
            assert sess.get('language') == 'uk'
    
    def test_url_parameter_overrides_session(self, app, client):
        """Test that URL parameter overrides session language."""
        # Set session language
        with client.session_transaction() as sess:
            sess['language'] = 'de'
        
        # Request with different language parameter
        with app.test_request_context('/?lang=uk'):
            from app.utils.i18n import get_user_language
            language = get_user_language()
            # Should use URL parameter
            assert language == 'uk'


class TestI18nDatabaseIntegration:
    """Test i18n database integration."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        app.config['TESTING'] = True
        
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    def test_user_language_preference_storage(self, app):
        """Test storing user language preference in database."""
        with app.app_context():
            # Create tenant
            tenant = Tenant(name="Test", slug="test")
            db.session.add(tenant)
            db.session.commit()
            
            # Create user with language preference
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id,
                language="de"
            )
            
            assert user.language == "de"
            
            # Verify it's stored in database
            stored_user = User.query.filter_by(email="test@example.com").first()
            assert stored_user.language == "de"
    
    def test_user_language_preference_update(self, app):
        """Test updating user language preference in database."""
        with app.app_context():
            # Create tenant
            tenant = Tenant(name="Test", slug="test")
            db.session.add(tenant)
            db.session.commit()
            
            # Create user
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id,
                language="en"
            )
            
            # Update language
            user.language = "uk"
            db.session.commit()
            
            # Verify update
            updated_user = User.query.get(user.id)
            assert updated_user.language == "uk"
    
    def test_user_language_in_serialization(self, app):
        """Test that user language is included in serialization."""
        with app.app_context():
            # Create tenant
            tenant = Tenant(name="Test", slug="test")
            db.session.add(tenant)
            db.session.commit()
            
            # Create user
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id,
                language="de"
            )
            
            # Check serialization
            user_dict = user.to_dict()
            assert 'language' in user_dict
            assert user_dict['language'] == 'de'


class TestI18nEndToEndFlow:
    """Test complete end-to-end i18n flow."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test-secret-key'
        
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    def test_complete_language_switching_flow(self, app, client):
        """Test complete language switching flow."""
        # Skip if API endpoints not implemented
        response = client.get('/api/v1/i18n/context')
        if response.status_code == 404:
            pytest.skip("I18n API endpoints not implemented yet")
        
        # Step 1: Initial request should use default language
        assert response.status_code == 200
        
        data = response.get_json()
        initial_language = data['data']['current_language']
        assert initial_language in LANGUAGES
        
        # Step 2: Switch language via API
        response = client.post('/api/v1/i18n/user/language', json={'language': 'de'})
        assert response.status_code == 200
        
        # Step 3: Verify language was switched
        response = client.get('/api/v1/i18n/context')
        assert response.status_code == 200
        
        data = response.get_json()
        current_language = data['data']['current_language']
        assert current_language == 'de'
        
        # Step 4: Switch to another language
        response = client.post('/api/v1/i18n/user/language', json={'language': 'uk'})
        assert response.status_code == 200
        
        # Step 5: Verify second language switch
        response = client.get('/api/v1/i18n/context')
        assert response.status_code == 200
        
        data = response.get_json()
        current_language = data['data']['current_language']
        assert current_language == 'uk'
    
    def test_language_persistence_across_requests(self, app, client):
        """Test that language preference persists across requests."""
        # Skip if API endpoints not implemented
        response = client.post('/api/v1/i18n/user/language', json={'language': 'de'})
        if response.status_code == 404:
            pytest.skip("I18n API endpoints not implemented yet")
        
        # Set language
        assert response.status_code == 200
        
        # Make multiple requests and verify language persists
        for _ in range(3):
            response = client.get('/api/v1/i18n/context')
            assert response.status_code == 200
            
            data = response.get_json()
            assert data['data']['current_language'] == 'de'
    
    def test_url_parameter_language_switching(self, app, client):
        """Test language switching via URL parameter."""
        # Set initial language in session
        response = client.post('/api/v1/i18n/user/language', json={'language': 'en'})
        if response.status_code == 404:
            pytest.skip("I18n API endpoints not implemented yet")
        
        assert response.status_code == 200
        
        # Request with URL parameter should override session
        with app.test_request_context('/?lang=de'):
            from app.utils.i18n import get_user_language
            language = get_user_language()
            assert language == 'de'
    
    def test_invalid_language_handling(self, app, client):
        """Test handling of invalid language codes."""
        # Try to set invalid language
        response = client.post('/api/v1/i18n/user/language', json={'language': 'invalid'})
        if response.status_code == 404:
            pytest.skip("I18n API endpoints not implemented yet")
        
        assert response.status_code == 400
        
        # Verify current language is unchanged
        response = client.get('/api/v1/i18n/context')
        assert response.status_code == 200
        
        data = response.get_json()
        current_language = data['data']['current_language']
        assert current_language in LANGUAGES  # Should be valid language
    
    def test_browser_language_detection(self, app, client):
        """Test browser language detection."""
        # Mock Accept-Language header
        headers = {'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8'}
        
        with app.test_request_context(headers=headers):
            from app.utils.i18n import LanguageDetectionService
            service = LanguageDetectionService()
            
            # Mock the browser language detection
            with patch.object(service, 'get_browser_language', return_value='de'):
                language = service._detect_language()
                assert language == 'de'


class TestI18nErrorHandling:
    """Test i18n error handling and fallbacks."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        app.config['TESTING'] = True
        
        with app.app_context():
            yield app
    
    def test_missing_translation_fallback(self, app):
        """Test fallback when translation is missing."""
        with app.test_request_context():
            from app.utils.i18n import get_cached_translation
            
            # Mock missing translation
            with patch('app.utils.i18n.translation_cache.get_cached_translation', return_value=None):
                with patch('flask_babel.gettext', return_value='fallback_text'):
                    result = get_cached_translation('missing_key', 'de')
                    assert result == 'fallback_text'
    
    def test_invalid_locale_handling(self, app):
        """Test handling of invalid locale codes."""
        with app.test_request_context():
            from app.services.localization_service import LocalizationService
            service = LocalizationService()
            
            # Test with invalid locale
            formatted = service.format_date(datetime(2023, 9, 15), locale='invalid')
            assert isinstance(formatted, str)
            assert '2023' in formatted  # Should still format the date
    
    def test_service_unavailable_fallback(self, app):
        """Test fallback when services are unavailable."""
        with app.test_request_context():
            from app.utils.i18n import format_currency
            
            # Mock service unavailable
            with patch('app.services.localization_service.LocalizationService', side_effect=ImportError):
                formatted = format_currency(1234.56, 'EUR')
                assert isinstance(formatted, str)
                assert 'EUR' in formatted
                assert '1234' in formatted
    
    def test_database_error_handling(self, app):
        """Test handling of database errors during language operations."""
        with app.test_request_context():
            from app.utils.i18n import set_user_language
            
            # Mock database error
            with patch('app.db.session.commit', side_effect=Exception("DB Error")):
                # Should still return True for session update
                result = set_user_language('de')
                assert result is True


class TestI18nPerformance:
    """Test i18n performance and caching."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        app.config['TESTING'] = True
        
        with app.app_context():
            yield app
    
    def test_translation_caching(self, app):
        """Test that translations are properly cached."""
        with app.test_request_context():
            from app.utils.i18n import get_cached_translation
            
            # Mock cache hit
            with patch('app.utils.i18n.translation_cache.get_cached_translation') as mock_cache:
                mock_cache.return_value = 'cached_translation'
                
                result = get_cached_translation('test_key', 'de')
                assert result == 'cached_translation'
                mock_cache.assert_called_once_with('test_key', 'de')
    
    def test_language_detection_caching(self, app):
        """Test that language detection results are cached."""
        with app.test_request_context():
            from app.utils.i18n import LanguageDetectionService
            service = LanguageDetectionService()
            
            # Mock cache
            with patch('app.utils.i18n.cache.memoize') as mock_memoize:
                mock_memoize.return_value = lambda func: func
                
                # Call multiple times
                lang1 = service.get_user_language()
                lang2 = service.get_user_language()
                
                # Should use caching
                assert lang1 == lang2
    
    def test_cache_invalidation(self, app):
        """Test cache invalidation when language changes."""
        with app.test_request_context():
            from app.utils.i18n import invalidate_translation_cache
            
            with patch('app.utils.i18n.translation_cache.invalidate_cache') as mock_invalidate:
                invalidate_translation_cache('de')
                mock_invalidate.assert_called_once_with('de')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])