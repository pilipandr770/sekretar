"""API response localization middleware."""
from flask import request, g, current_app
from flask_babel import gettext as _, ngettext
from flask_jwt_extended import get_current_user
from typing import Dict, Any, Optional, List, Union
import structlog

logger = structlog.get_logger()


class APILocalizationMiddleware:
    """Middleware for automatic API response localization."""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the middleware with Flask app."""
        self.app = app
        
        # Set up after request handler for response localization
        app.after_request(self.localize_response)
        
        logger.info("API localization middleware initialized")
    
    def localize_response(self, response):
        """Localize API response content."""
        # Only process JSON API responses
        if not self._should_localize_response(response):
            return response
        
        try:
            # Get response data
            if response.is_json:
                data = response.get_json()
                if data:
                    # Localize the response data
                    localized_data = self._localize_response_data(data)
                    
                    # Update response with localized data
                    response.data = current_app.json.dumps(localized_data)
                    response.headers['Content-Length'] = len(response.data)
                    
                    logger.debug(
                        "Response localized",
                        path=request.path,
                        language=getattr(g, 'language', 'en'),
                        status_code=response.status_code
                    )
        
        except Exception as e:
            logger.warning(
                "Failed to localize response",
                error=str(e),
                path=request.path,
                status_code=response.status_code
            )
        
        return response
    
    def _should_localize_response(self, response) -> bool:
        """Check if response should be localized."""
        # Only localize API endpoints
        if not request.path.startswith('/api/'):
            return False
        
        # Only localize JSON responses
        if not response.is_json:
            return False
        
        # Skip health checks and static endpoints
        skip_paths = [
            '/api/v1/health',
            '/api/v1/status',
            '/api/v1/version'
        ]
        if request.path in skip_paths:
            return False
        
        # Only localize successful responses and client errors (4xx)
        if not (200 <= response.status_code < 500):
            return False
        
        return True
    
    def _localize_response_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Localize response data recursively."""
        if not isinstance(data, dict):
            return data
        
        localized_data = data.copy()
        
        # Localize common response fields
        if 'message' in localized_data:
            localized_data['message'] = self._localize_message(localized_data['message'])
        
        # Localize error messages
        if 'error' in localized_data and isinstance(localized_data['error'], dict):
            localized_data['error'] = self._localize_error(localized_data['error'])
        
        # Localize validation errors
        if 'details' in localized_data and isinstance(localized_data['details'], dict):
            if 'validation_errors' in localized_data['details']:
                localized_data['details']['validation_errors'] = self._localize_validation_errors(
                    localized_data['details']['validation_errors']
                )
        
        # Localize data fields that contain translatable content
        if 'data' in localized_data:
            localized_data['data'] = self._localize_data_fields(localized_data['data'])
        
        return localized_data
    
    def _localize_message(self, message: str) -> str:
        """Localize a message string."""
        if not message or not isinstance(message, str):
            return message
        
        # Try to translate the message
        try:
            translated = _(message)
            return str(translated)
        except Exception as e:
            logger.debug(f"Could not translate message: {message}, error: {e}")
            return message
    
    def _localize_error(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Localize error object."""
        localized_error = error.copy()
        
        if 'message' in localized_error:
            localized_error['message'] = self._localize_message(localized_error['message'])
        
        if 'details' in localized_error:
            localized_error['details'] = self._localize_response_data(localized_error['details'])
        
        return localized_error
    
    def _localize_validation_errors(self, validation_errors: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Localize validation error messages."""
        localized_errors = {}
        
        for field, messages in validation_errors.items():
            localized_messages = []
            for message in messages:
                if isinstance(message, str):
                    localized_messages.append(self._localize_message(message))
                else:
                    localized_messages.append(message)
            localized_errors[field] = localized_messages
        
        return localized_errors
    
    def _localize_data_fields(self, data: Any) -> Any:
        """Localize data fields that contain translatable content."""
        if isinstance(data, dict):
            localized_data = {}
            for key, value in data.items():
                # Localize specific fields that commonly contain translatable content
                if key in ['status_display', 'type_display', 'category_display', 'description']:
                    localized_data[key] = self._localize_message(value) if isinstance(value, str) else value
                else:
                    localized_data[key] = self._localize_data_fields(value)
            return localized_data
        
        elif isinstance(data, list):
            return [self._localize_data_fields(item) for item in data]
        
        else:
            return data


class ValidationErrorLocalizer:
    """Utility class for localizing validation errors."""
    
    @staticmethod
    def localize_marshmallow_errors(errors: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Localize Marshmallow validation errors."""
        localized_errors = {}
        
        for field, messages in errors.items():
            localized_messages = []
            for message in messages:
                localized_message = ValidationErrorLocalizer._translate_validation_message(message, field)
                localized_messages.append(localized_message)
            localized_errors[field] = localized_messages
        
        return localized_errors
    
    @staticmethod
    def _translate_validation_message(message: str, field: str) -> str:
        """Translate common validation messages."""
        # Common validation message patterns
        translations = {
            'Missing data for required field.': _('This field is required.'),
            'Field may not be null.': _('This field cannot be empty.'),
            'Not a valid email address.': _('Please enter a valid email address.'),
            'Not a valid URL.': _('Please enter a valid URL.'),
            'Not a valid integer.': _('Please enter a valid number.'),
            'Not a valid number.': _('Please enter a valid number.'),
            'Not a valid boolean.': _('Please enter true or false.'),
            'Not a valid date.': _('Please enter a valid date.'),
            'Not a valid datetime.': _('Please enter a valid date and time.'),
            'Length must be between {min} and {max}.': _('Length must be between {min} and {max} characters.'),
            'Shorter than minimum length {min}.': _('Must be at least {min} characters long.'),
            'Longer than maximum length {max}.': _('Must be no more than {max} characters long.'),
            'Must be greater than or equal to {min}.': _('Must be at least {min}.'),
            'Must be less than or equal to {max}.': _('Must be no more than {max}.'),
        }
        
        # Try exact match first
        if message in translations:
            return str(translations[message])
        
        # Try pattern matching for parameterized messages
        for pattern, translation in translations.items():
            if '{' in pattern and '}' in pattern:
                # Simple pattern matching - could be enhanced with regex
                base_pattern = pattern.split('{')[0].strip()
                if message.startswith(base_pattern):
                    try:
                        return str(translation).format(**ValidationErrorLocalizer._extract_params(message, pattern))
                    except:
                        pass
        
        # Fallback to original message with translation attempt
        try:
            return str(_(message))
        except:
            return message
    
    @staticmethod
    def _extract_params(message: str, pattern: str) -> Dict[str, str]:
        """Extract parameters from validation message."""
        # Simple parameter extraction - could be enhanced
        params = {}
        
        # Extract numbers from common patterns
        import re
        numbers = re.findall(r'\d+', message)
        
        if 'min' in pattern and 'max' in pattern and len(numbers) >= 2:
            params['min'] = numbers[0]
            params['max'] = numbers[1]
        elif 'min' in pattern and len(numbers) >= 1:
            params['min'] = numbers[0]
        elif 'max' in pattern and len(numbers) >= 1:
            params['max'] = numbers[0]
        
        return params


def create_localized_validation_error(errors: Dict[str, List[str]], message: Optional[str] = None) -> Dict[str, Any]:
    """Create a localized validation error response."""
    from app.utils.response import error_response
    
    if not message:
        message = _('Validation failed')
    
    # Localize the validation errors
    localized_errors = ValidationErrorLocalizer.localize_marshmallow_errors(errors)
    
    return error_response(
        error_code='VALIDATION_ERROR',
        message=message,
        status_code=422,
        details={'validation_errors': localized_errors}
    )


def localize_api_message(message_key: str, **kwargs) -> str:
    """Localize API message with parameters."""
    try:
        if kwargs:
            return str(_(message_key, **kwargs))
        else:
            return str(_(message_key))
    except Exception as e:
        logger.debug(f"Could not localize message: {message_key}, error: {e}")
        return message_key


def localize_model_display_fields(model_data: Dict[str, Any], display_fields: List[str]) -> Dict[str, Any]:
    """Localize model display fields."""
    localized_data = model_data.copy()
    
    for field in display_fields:
        if field in localized_data and isinstance(localized_data[field], str):
            localized_data[field] = localize_api_message(localized_data[field])
    
    return localized_data


def init_api_localization_middleware(app):
    """Initialize API localization middleware."""
    middleware = APILocalizationMiddleware(app)
    return middleware