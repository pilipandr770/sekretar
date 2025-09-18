"""Simple tests for API response localization system."""
import pytest
import json
from unittest.mock import patch, MagicMock
from flask import Flask, request, g

from app.utils.api_localization_middleware import (
    APILocalizationMiddleware, ValidationErrorLocalizer,
    create_localized_validation_error, localize_api_message
)
from app.utils.localized_validators import (
    LocalizedValidator, LocalizedFormValidator, 
    create_field_validator
)
from app.utils.response import (
    localized_success_response, localized_error_response,
    business_validation_error_response
)


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


class TestLocalizedResponseFunctions:
    """Test localized response utility functions."""
    
    def test_localized_success_response(self):
        """Test localized success response creation."""
        app = Flask(__name__)
        
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
    
    def test_localized_error_response(self):
        """Test localized error response creation."""
        app = Flask(__name__)
        
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
    
    def test_business_validation_error_response(self):
        """Test business validation error response."""
        app = Flask(__name__)
        
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


class TestAPILocalizationMiddleware:
    """Test API localization middleware functionality."""
    
    def test_middleware_initialization(self):
        """Test middleware is properly initialized."""
        app = Flask(__name__)
        middleware = APILocalizationMiddleware(app)
        
        # Check that middleware is registered
        assert middleware.app == app
    
    def test_should_localize_response(self):
        """Test response localization decision logic."""
        app = Flask(__name__)
        middleware = APILocalizationMiddleware(app)
        
        with app.test_request_context('/api/v1/test'):
            # Mock response
            response = MagicMock()
            response.is_json = True
            response.status_code = 200
            
            assert middleware._should_localize_response(response) is True
            
            # Test non-API path
            with app.test_request_context('/static/test.css'):
                assert middleware._should_localize_response(response) is False
            
            # Test health endpoint
            with app.test_request_context('/api/v1/health'):
                assert middleware._should_localize_response(response) is False
            
            # Test non-JSON response
            response.is_json = False
            with app.test_request_context('/api/v1/test'):
                assert middleware._should_localize_response(response) is False
    
    def test_localize_message(self):
        """Test message localization."""
        app = Flask(__name__)
        middleware = APILocalizationMiddleware(app)
        
        with app.app_context():
            # Test basic message localization
            message = "Test message"
            localized = middleware._localize_message(message)
            assert isinstance(localized, str)
            assert len(localized) > 0
    
    def test_localize_validation_errors(self):
        """Test validation error localization."""
        app = Flask(__name__)
        middleware = APILocalizationMiddleware(app)
        
        with app.app_context():
            validation_errors = {
                'email': ['Invalid email address'],
                'name': ['This field is required']
            }
            
            localized = middleware._localize_validation_errors(validation_errors)
            
            assert 'email' in localized
            assert 'name' in localized
            assert len(localized['email']) > 0
            assert len(localized['name']) > 0


class TestLocalizationUtilities:
    """Test localization utility functions."""
    
    def test_localize_api_message(self):
        """Test API message localization."""
        app = Flask(__name__)
        
        with app.app_context():
            # Test simple message
            message = localize_api_message('Test message')
            assert isinstance(message, str)
            assert len(message) > 0
            
            # Test message with parameters
            message = localize_api_message('Hello {name}', name='World')
            assert isinstance(message, str)
            assert len(message) > 0
    
    def test_create_localized_validation_error(self):
        """Test localized validation error creation."""
        app = Flask(__name__)
        
        with app.app_context():
            errors = {
                'email': ['Invalid email'],
                'name': ['Required field']
            }
            
            response = create_localized_validation_error(errors)
            
            # Should return a tuple (response, status_code)
            assert isinstance(response, tuple)
            assert len(response) == 2
            
            response_obj, status_code = response
            assert status_code == 422
            
            data = json.loads(response_obj.data)
            assert data['success'] is False
            assert 'validation_errors' in data['error']['details']


class TestFieldValidators:
    """Test individual field validators."""
    
    def test_email_validator(self):
        """Test email field validator."""
        validator = create_field_validator('email', 'email')
        
        # Test valid email
        errors = validator('test@example.com')
        assert len(errors) == 0
        
        # Test invalid email
        errors = validator('invalid-email')
        assert len(errors) > 0
    
    def test_string_validator(self):
        """Test string field validator."""
        validator = create_field_validator('name', 'string', min_length=3, max_length=10)
        
        # Test valid string
        errors = validator('valid')
        assert len(errors) == 0
        
        # Test too short
        errors = validator('ab')
        assert len(errors) > 0
        
        # Test too long
        errors = validator('this is too long')
        assert len(errors) > 0
    
    def test_integer_validator(self):
        """Test integer field validator."""
        validator = create_field_validator('age', 'integer', min_value=0, max_value=120)
        
        # Test valid integer
        errors = validator(25)
        assert len(errors) == 0
        
        # Test negative value
        errors = validator(-5)
        assert len(errors) > 0
        
        # Test too large value
        errors = validator(150)
        assert len(errors) > 0
        
        # Test invalid type
        errors = validator('not a number')
        assert len(errors) > 0
    
    def test_choice_validator(self):
        """Test choice field validator."""
        validator = create_field_validator('status', 'choice', choices=['active', 'inactive'])
        
        # Test valid choice
        errors = validator('active')
        assert len(errors) == 0
        
        # Test invalid choice
        errors = validator('invalid')
        assert len(errors) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])