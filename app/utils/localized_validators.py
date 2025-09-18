"""Localized validation utilities with i18n support."""
from typing import Dict, List, Any, Optional, Union
from flask_babel import gettext as _, ngettext
from marshmallow import ValidationError as MarshmallowValidationError
from app.utils.validators import BaseValidator, ValidationError
from app.utils.response import validation_error_response
import structlog

logger = structlog.get_logger()


class LocalizedValidationError(ValidationError):
    """Validation error with localization support."""
    
    def __init__(self, message: str, field: str = None, code: str = None, **kwargs):
        # Localize the message
        try:
            localized_message = _(message, **kwargs) if kwargs else _(message)
            super().__init__(str(localized_message))
        except Exception as e:
            logger.debug(f"Could not localize validation error: {message}, error: {e}")
            super().__init__(message)
        
        self.field = field
        self.code = code
        self.params = kwargs


class LocalizedValidator(BaseValidator):
    """Base validator with localization support."""
    
    def add_localized_error(self, field: str, message_key: str, **kwargs):
        """Add localized validation error."""
        try:
            message = _(message_key, **kwargs) if kwargs else _(message_key)
            self.add_error(field, str(message))
        except Exception as e:
            logger.debug(f"Could not localize validation message: {message_key}, error: {e}")
            self.add_error(field, message_key)
    
    def validate_required_field(self, field: str, value: Any, message_key: str = None):
        """Validate required field with localized error."""
        if not message_key:
            message_key = 'This field is required'
        
        if not value or (isinstance(value, str) and not value.strip()):
            self.add_localized_error(field, message_key)
            return False
        return True
    
    def validate_email_field(self, field: str, value: str, message_key: str = None):
        """Validate email field with localized error."""
        if not message_key:
            message_key = 'Please enter a valid email address'
        
        if not value:
            return True  # Let required validation handle empty values
        
        from app.utils.validators import validate_email
        try:
            validate_email(value)
            return True
        except ValidationError:
            self.add_localized_error(field, message_key)
            return False
    
    def validate_length(self, field: str, value: str, min_length: int = None, max_length: int = None):
        """Validate string length with localized errors."""
        if not value:
            return True  # Let required validation handle empty values
        
        length = len(value)
        
        if min_length and length < min_length:
            if max_length:
                self.add_localized_error(
                    field, 
                    'Length must be between {min} and {max} characters',
                    min=min_length,
                    max=max_length
                )
            else:
                self.add_localized_error(
                    field,
                    'Must be at least {min} characters long',
                    min=min_length
                )
            return False
        
        if max_length and length > max_length:
            if min_length:
                self.add_localized_error(
                    field,
                    'Length must be between {min} and {max} characters',
                    min=min_length,
                    max=max_length
                )
            else:
                self.add_localized_error(
                    field,
                    'Must be no more than {max} characters long',
                    max=max_length
                )
            return False
        
        return True
    
    def validate_choice(self, field: str, value: Any, choices: List[Any], message_key: str = None):
        """Validate choice field with localized error."""
        if not message_key:
            message_key = 'Invalid choice. Valid options are: {choices}'
        
        if value not in choices:
            choices_str = ', '.join(str(choice) for choice in choices)
            self.add_localized_error(field, message_key, choices=choices_str)
            return False
        return True
    
    def validate_numeric_range(self, field: str, value: Union[int, float], min_value: Union[int, float] = None, max_value: Union[int, float] = None):
        """Validate numeric range with localized errors."""
        if value is None:
            return True  # Let required validation handle None values
        
        if min_value is not None and value < min_value:
            if max_value is not None:
                self.add_localized_error(
                    field,
                    'Value must be between {min} and {max}',
                    min=min_value,
                    max=max_value
                )
            else:
                self.add_localized_error(
                    field,
                    'Value must be at least {min}',
                    min=min_value
                )
            return False
        
        if max_value is not None and value > max_value:
            if min_value is not None:
                self.add_localized_error(
                    field,
                    'Value must be between {min} and {max}',
                    min=min_value,
                    max=max_value
                )
            else:
                self.add_localized_error(
                    field,
                    'Value must be no more than {max}',
                    max=max_value
                )
            return False
        
        return True


class APIValidationMixin:
    """Mixin for API endpoint validation with localization."""
    
    def validate_json_request(self, required_fields: List[str] = None, optional_fields: List[str] = None):
        """Validate JSON request with localized errors."""
        from flask import request
        
        if not request.is_json:
            return validation_error_response({
                'request': [_('Request must be JSON')]
            })
        
        data = request.get_json()
        if not data:
            return validation_error_response({
                'request': [_('Request body cannot be empty')]
            })
        
        if required_fields:
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                errors = {}
                for field in missing_fields:
                    errors[field] = [_('This field is required')]
                return validation_error_response(errors)
        
        return None  # No validation errors
    
    def validate_pagination_request(self):
        """Validate pagination parameters with localized errors."""
        from flask import request
        
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
        except ValueError:
            return validation_error_response({
                'pagination': [_('Page and per_page must be valid numbers')]
            })
        
        if page < 1:
            return validation_error_response({
                'page': [_('Page number must be positive')]
            })
        
        if per_page < 1:
            return validation_error_response({
                'per_page': [_('Per page value must be positive')]
            })
        
        if per_page > 100:
            return validation_error_response({
                'per_page': [_('Per page value cannot exceed 100')]
            })
        
        return None  # No validation errors


def handle_marshmallow_validation_error(error: MarshmallowValidationError):
    """Handle Marshmallow validation errors with localization."""
    from app.utils.api_localization_middleware import ValidationErrorLocalizer
    
    localized_errors = ValidationErrorLocalizer.localize_marshmallow_errors(error.messages)
    
    return validation_error_response(
        errors=localized_errors,
        message=_('Validation failed')
    )


def create_field_validator(field_name: str, field_type: str = 'string', **constraints):
    """Create a field validator with localized error messages."""
    
    def validator(value):
        """Field validator function."""
        errors = []
        
        # Required validation
        if constraints.get('required', False):
            if not value or (isinstance(value, str) and not value.strip()):
                errors.append(_('This field is required'))
                return errors
        
        # Skip other validations if value is empty and not required
        if not value:
            return errors
        
        # Type-specific validations
        if field_type == 'email':
            from app.utils.validators import validate_email
            try:
                validate_email(value)
            except ValidationError:
                errors.append(_('Please enter a valid email address'))
        
        elif field_type == 'string':
            if not isinstance(value, str):
                errors.append(_('Must be a text value'))
            else:
                # Length validation
                min_length = constraints.get('min_length')
                max_length = constraints.get('max_length')
                
                if min_length and len(value) < min_length:
                    if max_length:
                        errors.append(_('Length must be between {min} and {max} characters', 
                                      min=min_length, max=max_length))
                    else:
                        errors.append(_('Must be at least {min} characters long', min=min_length))
                
                if max_length and len(value) > max_length:
                    if min_length:
                        errors.append(_('Length must be between {min} and {max} characters',
                                      min=min_length, max=max_length))
                    else:
                        errors.append(_('Must be no more than {max} characters long', max=max_length))
        
        elif field_type == 'integer':
            try:
                int_value = int(value)
                min_value = constraints.get('min_value')
                max_value = constraints.get('max_value')
                
                if min_value is not None and int_value < min_value:
                    errors.append(_('Value must be at least {min}', min=min_value))
                
                if max_value is not None and int_value > max_value:
                    errors.append(_('Value must be no more than {max}', max=max_value))
                    
            except (ValueError, TypeError):
                errors.append(_('Must be a valid number'))
        
        elif field_type == 'choice':
            choices = constraints.get('choices', [])
            if value not in choices:
                choices_str = ', '.join(str(choice) for choice in choices)
                errors.append(_('Invalid choice. Valid options are: {choices}', choices=choices_str))
        
        return errors
    
    return validator


class LocalizedFormValidator:
    """Form validator with comprehensive localization support."""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.errors = {}
        self.cleaned_data = {}
    
    def add_error(self, field: str, message: str, **kwargs):
        """Add localized error message."""
        if field not in self.errors:
            self.errors[field] = []
        
        try:
            localized_message = _(message, **kwargs) if kwargs else _(message)
            self.errors[field].append(str(localized_message))
        except Exception as e:
            logger.debug(f"Could not localize form error: {message}, error: {e}")
            self.errors[field].append(message)
    
    def validate_field(self, field: str, validators: List[callable]):
        """Validate field with multiple validators."""
        value = self.data.get(field)
        
        for validator in validators:
            try:
                result = validator(value)
                if isinstance(result, list) and result:
                    # Validator returned error messages
                    if field not in self.errors:
                        self.errors[field] = []
                    self.errors[field].extend(result)
                elif result is False:
                    # Validator returned False (generic error)
                    self.add_error(field, 'Invalid value')
                elif isinstance(result, tuple) and len(result) == 2:
                    # Validator returned (is_valid, cleaned_value)
                    is_valid, cleaned_value = result
                    if not is_valid:
                        self.add_error(field, 'Invalid value')
                    else:
                        self.cleaned_data[field] = cleaned_value
                else:
                    # Validator passed, use original value
                    self.cleaned_data[field] = value
                    
            except Exception as e:
                logger.error(f"Validator error for field {field}: {e}")
                self.add_error(field, 'Validation error occurred')
    
    def is_valid(self) -> bool:
        """Check if form is valid."""
        return len(self.errors) == 0
    
    def get_errors(self) -> Dict[str, List[str]]:
        """Get validation errors."""
        return self.errors
    
    def get_cleaned_data(self) -> Dict[str, Any]:
        """Get cleaned data."""
        return self.cleaned_data
    
    def to_response(self):
        """Convert to validation error response."""
        if self.is_valid():
            return None
        
        return validation_error_response(
            errors=self.errors,
            message=_('Form validation failed')
        )


def validate_api_request(schema_class, data: Dict[str, Any]):
    """Validate API request using Marshmallow schema with localization."""
    try:
        schema = schema_class()
        result = schema.load(data)
        return result, None
    except MarshmallowValidationError as e:
        return None, handle_marshmallow_validation_error(e)


def create_business_rule_validator(rule_name: str, error_message_key: str):
    """Create a business rule validator with localized error message."""
    
    def validator(value, context: Dict[str, Any] = None):
        """Business rule validator."""
        # This is a template - implement specific business rules
        # Return True if valid, False or error message if invalid
        
        # Example business rule validation
        if rule_name == 'unique_email':
            # Check if email is unique in the system
            from app.models import User
            existing_user = User.query.filter_by(email=value).first()
            if existing_user:
                return [_(error_message_key, email=value)]
        
        elif rule_name == 'valid_tenant_user':
            # Check if user belongs to current tenant
            if context and 'tenant_id' in context:
                from app.models import User
                user = User.query.filter_by(email=value, tenant_id=context['tenant_id']).first()
                if not user:
                    return [_(error_message_key)]
        
        return []  # No errors
    
    return validator