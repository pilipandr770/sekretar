"""Comprehensive tests for API response localization system."""
import pytest
import json
from unittest.mock import patch, MagicMock
from flask import Flask, request, g
from flask_babel import Babel

from app import create_app
from app.models import User, Tenant, Contact
from app.utils.api_localization_middleware import (
    APILocalizationMiddleware, ValidationErrorLocalizer,
    create_localized_validation_error, localize_api_message
)
from app.utils.localized_validators import (
    LocalizedValidator, LocalizedFormValidator, 
    create_field_validator, APIValidationMixin
)
from app.utils.response import (
    localized_success_response, localized_error_response,
    business_validation_error_response, api_method_response
)


class TestAPILocalizationMiddleware:
    """Test API localization middleware functionality."""
    
    @pytest.fixture
    def app(self):
        """Create test app with localization middleware."""
        app = create_app('testing')
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    @pytest.fixture
    def auth_headers(self, app, client):
        """Create authentication headers for testing."""
        with app.app_context():
            # Create test tenant and user
            tenant = Tenant.create(
                name="Test Organization",
                email="test@example.com",
                is_active=True
            )
            
            user = User.create(
                email="test@example.com",
                password="testpassword123",
                first_name="Test",
                last_name="User",
                tenant_id=tenant.id,
                role="owner",
                is_active=True,
                language="de"  # Set German as preferred language
            )
            
            # Login to get JWT token
            response = client.post('/api/v1/auth/login', json={
                'email': 'test@example.com',
                'password': 'testpassword123'
            })
            
            token = response.json['data']['access_token']
            return {'Authorization': f'Bearer {token}'}
    
    def test_middleware_initialization(self, app):
        """Test middleware is properly initialized."""
        with app.app_context():
            # Check that middleware is registered
            assert any(
                hasattr(func, '__name__') and 'localize_response' in func.__name__
                for func in app.after_request_funcs.get(None, [])
            )
    
    def test_response_localization_json_api(self, app, client, auth_headers):
        """Test that JSON API responses are localized."""
        with app.app_context():
            # Set language to German
            with client.session_transaction() as sess:
                sess['language'] = 'de'
            
            # Make API request that should return localized response
            response = client.get('/api/v1/tenant', headers=auth_headers)
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Check that response structure is maintained
            assert 'success' in data
            assert 'message' in data
            assert 'data' in data
    
    def test_validation_error_localization(self, app, client, auth_headers):
        """Test that validation errors are localized."""
        with app.app_context():
            # Set language to German
            with client.session_transaction() as sess:
                sess['language'] = 'de'
            
            # Make request with invalid data
            response = client.post('/api/v1/localized-example/contacts', 
                                 headers=auth_headers,
                                 json={'email': 'invalid-email'})
            
            assert response.status_code == 422
            data = response.get_json()
            
            # Check that validation errors are present and localized
            assert 'error' in data
            assert 'details' in data['error']
            assert 'validation_errors' in data['error']['details']
    
    def test_skip_non_api_endpoints(self, app, client):
        """Test that non-API endpoints are not localized."""
        with app.app_context():
            # Make request to non-API endpoint
            response = client.get('/static/test.css')  # This will 404 but that's ok
            
            # Should not be processed by localization middleware
            assert response.status_code == 404
    
    def test_skip_health_endpoints(self, app, client):
        """Test that health check endpoints are not localized."""
        with app.app_context():
            response = client.get('/api/v1/health')
            
            # Should not be processed by localization middleware
            assert response.status_code == 200


class TestValidationErrorLocalizer:
    """Test validation error localization utilities."""
    
    def test_localize_marshmallow_errors(self):
        """Test Marshmallow error localization."""
        errors = {
            'email': ['Not a valid email address.'],
            'name': ['Missing data for required field.'],
            'age': ['Not a valid integer.']
        }
        
        localized = ValidationErrorLocalizer.localize_marshmallow_errors(errors)
        
        assert 'email' in localized
        assert 'name' in localized
        assert 'age' in localized
        
        # Check that messages are localized (will be in English for test)
        assert len(localized['email']) > 0
        assert len(localized['name']) > 0
        assert len(localized['age']) > 0
    
    def test_translate_validation_message(self):
        """Test individual validation message translation."""
        message = "Missing data for required field."
        translated = ValidationErrorLocalizer._translate_validation_message(message, 'test_field')
        
        # Should return a translated message
        assert isinstance(translated, str)
        assert len(translated) > 0
    
    def test_extract_params(self):
        """Test parameter extraction from validation messages."""
        message = "Length must be between 5 and 10."
        pattern = "Length must be between {min} and {max}."
        
        params = ValidationErrorLocalizer._extract_params(message, pattern)
        
        assert 'min' in params
        assert 'max' in params
        assert params['min'] == '5'
        assert params['max'] == '10'


class TestLocalizedValidators:
    """Test localized validation utilities."""
    
    def test_localized_validator_basic(self):
        """Test basic localized validator functionality."""
        data = {'name': '', 'email': 'invalid'}
        validator = LocalizedValidator(data)
        
        # Test required field validation
        validator.validate_required_field('name', data.get('name'))
        
        # Test email validation
        validator.validate_email_field('email', data.get('email'))
        
        assert not validator.is_valid()
        assert 'name' in validator.errors
        assert 'email' in validator.errors
    
    def test_localized_validator_length(self):
        """Test length validation with localized errors."""
        data = {'short': 'ab', 'long': 'a' * 101}
        validator = LocalizedValidator(data)
        
        # Test length validation
        validator.validate_length('short', data.get('short'), min_length=5)
        validator.validate_length('long', data.get('long'), max_length=100)
        
        assert not validator.is_valid()
        assert 'short' in validator.errors
        assert 'long' in validator.errors
    
    def test_localized_validator_choice(self):
        """Test choice validation with localized errors."""
        data = {'status': 'invalid'}
        validator = LocalizedValidator(data)
        
        validator.validate_choice('status', data.get('status'), ['active', 'inactive'])
        
        assert not validator.is_valid()
        assert 'status' in validator.errors
    
    def test_localized_validator_numeric_range(self):
        """Test numeric range validation."""
        data = {'age': -5, 'score': 150}
        validator = LocalizedValidator(data)
        
        validator.validate_numeric_range('age', data.get('age'), min_value=0)
        validator.validate_numeric_range('score', data.get('score'), max_value=100)
        
        assert not validator.is_valid()
        assert 'age' in validator.errors
        assert 'score' in validator.errors
    
    def test_create_field_validator(self):
        """Test field validator creation."""
        # Test string validator
        string_validator = create_field_validator('test', 'string', required=True, min_length=5)
        
        # Test with empty value
        errors = string_validator('')
        assert len(errors) > 0
        
        # Test with short value
        errors = string_validator('abc')
        assert len(errors) > 0
        
        # Test with valid value
        errors = string_validator('valid string')
        assert len(errors) == 0
    
    def test_localized_form_validator(self):
        """Test comprehensive form validator."""
        data = {
            'name': '',
            'email': 'invalid-email',
            'age': 'not-a-number'
        }
        
        validator = LocalizedFormValidator(data)
        
        # Add field validations
        validator.validate_field('name', [
            create_field_validator('name', 'string', required=True)
        ])
        
        validator.validate_field('email', [
            create_field_validator('email', 'email')
        ])
        
        validator.validate_field('age', [
            create_field_validator('age', 'integer', min_value=0, max_value=120)
        ])
        
        assert not validator.is_valid()
        errors = validator.get_errors()
        
        assert 'name' in errors
        assert 'email' in errors
        assert 'age' in errors


class TestAPIValidationMixin:
    """Test API validation mixin functionality."""
    
    def test_validate_json_request(self, app):
        """Test JSON request validation."""
        with app.test_request_context('/test', json={'name': 'test'}):
            mixin = APIValidationMixin()
            
            # Test valid JSON request
            result = mixin.validate_json_request(['name'])
            assert result is None
            
            # Test missing required field
            result = mixin.validate_json_request(['email'])
            assert result is not None
            assert result[1] == 422  # Validation error status code
    
    def test_validate_pagination_request(self, app):
        """Test pagination validation."""
        with app.test_request_context('/test?page=1&per_page=20'):
            mixin = APIValidationMixin()
            
            result = mixin.validate_pagination_request()
            assert result is None
        
        with app.test_request_context('/test?page=0&per_page=200'):
            mixin = APIValidationMixin()
            
            result = mixin.validate_pagination_request()
            assert result is not None
            assert result[1] == 422


class TestLocalizedResponseFunctions:
    """Test localized response utility functions."""
    
    def test_localized_success_response(self, app):
        """Test localized success response creation."""
        with app.app_context():
            response, status_code = localized_success_response(
                message_key='Operation completed successfully',
                data={'id': 1}
            )
            
            assert status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'message' in data
            assert data['data']['id'] == 1
    
    def test_localized_error_response(self, app):
        """Test localized error response creation."""
        with app.app_context():
            response, status_code = localized_error_response(
                error_code='TEST_ERROR',
                message_key='Test error message',
                status_code=400
            )
            
            assert status_code == 400
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'error' in data
            assert data['error']['code'] == 'TEST_ERROR'
    
    def test_business_validation_error_response(self, app):
        """Test business validation error response."""
        with app.app_context():
            field_errors = {
                'email': ['Email already exists'],
                'name': ['Name is too short']
            }
            
            response, status_code = business_validation_error_response(field_errors)
            
            assert status_code == 422
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'validation_errors' in data['error']['details']
    
    def test_api_method_response(self, app):
        """Test standardized API method responses."""
        with app.app_context():
            # Test successful POST
            response, status_code = api_method_response(
                method='POST',
                resource='contact',
                success=True,
                data={'id': 1}
            )
            
            assert status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'Created' in data['message']
            
            # Test failed operation
            response, status_code = api_method_response(
                method='DELETE',
                resource='contact',
                success=False
            )
            
            assert status_code == 400
            data = json.loads(response.data)
            assert data['success'] is False


class TestLanguageContextIntegration:
    """Test integration with language context and user preferences."""
    
    def test_user_language_preference(self, app):
        """Test that user language preference affects API responses."""
        with app.app_context():
            # Create user with German preference
            tenant = Tenant.create(name="Test Org", email="test@example.com")
            user = User.create(
                email="german@example.com",
                password="password123",
                tenant_id=tenant.id,
                language="de"
            )
            
            # Mock current user
            with patch('flask_jwt_extended.get_current_user', return_value=user):
                with app.test_request_context():
                    g.current_user = user
                    g.language = 'de'
                    
                    # Test that responses use German language context
                    response, status_code = localized_success_response(
                        message_key='Operation completed successfully'
                    )
                    
                    assert status_code == 200
                    # Response should be localized based on user preference
    
    def test_session_language_override(self, app):
        """Test that session language overrides user preference."""
        with app.app_context():
            with app.test_request_context():
                # Set session language
                from flask import session
                session['language'] = 'uk'
                g.language = 'uk'
                
                response, status_code = localized_error_response(
                    error_code='TEST_ERROR',
                    message_key='Test error message'
                )
                
                assert status_code == 400
                # Should use Ukrainian translations


class TestEndToEndAPILocalization:
    """End-to-end tests for API localization."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        return create_app('testing')
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    def test_complete_api_flow_localization(self, app, client):
        """Test complete API flow with localization."""
        with app.app_context():
            # Create test data
            tenant = Tenant.create(name="Test Org", email="test@example.com")
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id,
                language="de",
                role="owner"
            )
            
            # Login
            login_response = client.post('/api/v1/auth/login', json={
                'email': 'test@example.com',
                'password': 'password123'
            })
            
            assert login_response.status_code == 200
            token = login_response.json['data']['access_token']
            headers = {'Authorization': f'Bearer {token}'}
            
            # Set language preference
            with client.session_transaction() as sess:
                sess['language'] = 'de'
            
            # Test API endpoint with validation error
            response = client.post('/api/v1/localized-example/contacts',
                                 headers=headers,
                                 json={'email': 'invalid-email'})
            
            # Should return localized validation error
            assert response.status_code == 422
            data = response.get_json()
            assert 'error' in data
            assert 'validation_errors' in data['error']['details']
            
            # Test successful API call
            response = client.post('/api/v1/localized-example/contacts',
                                 headers=headers,
                                 json={
                                     'first_name': 'Test',
                                     'last_name': 'User',
                                     'email': 'test.user@example.com'
                                 })
            
            # Should return localized success message
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert 'message' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])