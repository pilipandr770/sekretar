"""Response utilities with i18n support."""
from datetime import datetime
from flask import jsonify, request
from flask_babel import gettext as _
from app.utils.i18n import translate_error_message, get_user_language
from app.utils.errors import generate_request_id
import structlog

logger = structlog.get_logger()


def generate_timestamp():
    """Generate ISO-8601 timestamp for responses."""
    return datetime.utcnow().isoformat() + 'Z'


def api_response(data=None, message=None, status_code=200, **kwargs):
    """Create API response with consistent structure for basic endpoints."""
    timestamp = generate_timestamp()
    
    response_data = {
        'timestamp': timestamp
    }
    
    if message:
        response_data['message'] = message
    
    if data is not None:
        response_data.update(data)
    
    # Add any additional fields
    response_data.update(kwargs)
    
    return jsonify(response_data), status_code


def health_response(status, checks, version=None, status_code=None):
    """Create health check response with consistent structure."""
    timestamp = generate_timestamp()
    
    response_data = {
        'status': status,
        'timestamp': timestamp,
        'checks': checks
    }
    
    if version:
        response_data['version'] = version
    
    # Use provided status_code or default based on health status
    if status_code is None:
        status_code = 200 if status == "healthy" else 503
    
    return jsonify(response_data), status_code


def version_response(version, build_date=None, environment=None, **kwargs):
    """Create version response with consistent structure."""
    response_data = {
        'version': version
    }
    
    if build_date:
        response_data['build_date'] = build_date
    
    if environment:
        response_data['environment'] = environment
    
    # Add any additional version info
    response_data.update(kwargs)
    
    return jsonify(response_data), 200


def welcome_response(message, version=None, endpoints=None, environment=None):
    """Create welcome response with consistent structure."""
    timestamp = generate_timestamp()
    
    response_data = {
        'message': message,
        'timestamp': timestamp
    }
    
    if version:
        response_data['version'] = version
    
    if environment:
        response_data['environment'] = environment
    
    if endpoints:
        response_data['endpoints'] = endpoints
    
    return jsonify(response_data), 200


def success_response(message=None, data=None, status_code=200, message_key=None, **kwargs):
    """Create success response with i18n support and consistent structure."""
    request_id = generate_request_id()
    timestamp = generate_timestamp()
    
    # Translate message if message_key provided
    if message_key:
        message = _(message_key)
    elif message:
        message = _(message) if isinstance(message, str) else message
    
    response_data = {
        'success': True,
        'timestamp': timestamp,
        'request_id': request_id
    }
    
    if message:
        response_data['message'] = str(message)
    
    if data is not None:
        response_data['data'] = data
    
    # Add any additional fields
    response_data.update(kwargs)
    
    logger.info(
        "Success response",
        status_code=status_code,
        message=message,
        request_id=request_id,
        language=get_user_language(),
        timestamp=timestamp
    )
    
    return jsonify(response_data), status_code


def error_response(error_code, message=None, status_code=400, details=None, **kwargs):
    """Create error response with i18n support and consistent structure."""
    request_id = generate_request_id()
    timestamp = generate_timestamp()
    
    # Translate error message
    if message:
        translated_message = _(message) if isinstance(message, str) else message
    else:
        translated_message = translate_error_message(error_code, **kwargs)
    
    response_data = {
        'success': False,
        'timestamp': timestamp,
        'error': {
            'code': error_code,
            'message': str(translated_message),
            'request_id': request_id
        }
    }
    
    if details:
        response_data['error']['details'] = details
    
    logger.error(
        "Error response",
        error_code=error_code,
        message=translated_message,
        status_code=status_code,
        request_id=request_id,
        language=get_user_language(),
        timestamp=timestamp,
        path=request.path if request else None,
        method=request.method if request else None
    )
    
    return jsonify(response_data), status_code


def validation_error_response(errors, message=None):
    """Create validation error response with localization support."""
    if not message:
        message = _('Validation failed')
    
    # Localize validation errors if they're not already localized
    from app.utils.api_localization_middleware import ValidationErrorLocalizer
    localized_errors = ValidationErrorLocalizer.localize_marshmallow_errors(errors)
    
    return error_response(
        error_code='VALIDATION_ERROR',
        message=message,
        status_code=422,
        details={'validation_errors': localized_errors}
    )


def not_found_response(resource_type=None):
    """Create not found error response."""
    if resource_type:
        message = _('%(resource)s not found', resource=_(resource_type))
    else:
        message = _('Resource not found')
    
    return error_response(
        error_code='NOT_FOUND_ERROR',
        message=message,
        status_code=404
    )


def unauthorized_response(message=None):
    """Create unauthorized error response."""
    if not message:
        message = _('Authentication required')
    
    return error_response(
        error_code='AUTHENTICATION_ERROR',
        message=message,
        status_code=401
    )


def forbidden_response(message=None):
    """Create forbidden error response."""
    if not message:
        message = _('Access denied')
    
    return error_response(
        error_code='AUTHORIZATION_ERROR',
        message=message,
        status_code=403
    )


def conflict_response(message=None):
    """Create conflict error response."""
    if not message:
        message = _('Resource already exists')
    
    return error_response(
        error_code='CONFLICT_ERROR',
        message=message,
        status_code=409
    )


def rate_limit_response(message=None):
    """Create rate limit error response."""
    if not message:
        message = _('Rate limit exceeded')
    
    return error_response(
        error_code='RATE_LIMIT_ERROR',
        message=message,
        status_code=429
    )


def service_unavailable_response(service_name=None, message=None):
    """Create service unavailable error response."""
    if not message:
        if service_name:
            message = _('%(service)s is unavailable', service=service_name)
        else:
            message = _('External service unavailable')
    
    return error_response(
        error_code='EXTERNAL_SERVICE_ERROR',
        message=message,
        status_code=503,
        service=service_name
    )


def paginated_response(items, page, per_page, total, message=None, **kwargs):
    """Create paginated response."""
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': (total + per_page - 1) // per_page,
        'has_prev': page > 1,
        'has_next': page * per_page < total
    }
    
    return success_response(
        message=message,
        data={
            'items': items,
            'pagination': pagination
        },
        **kwargs
    )


class ResponseBuilder:
    """Fluent response builder with i18n support."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset builder state."""
        self._success = True
        self._message = None
        self._message_key = None
        self._data = None
        self._error_code = None
        self._status_code = 200
        self._details = None
        self._extra = {}
        return self
    
    def success(self, message=None, message_key=None):
        """Set success message."""
        self._success = True
        self._message = message
        self._message_key = message_key
        self._status_code = 200
        return self
    
    def error(self, error_code, message=None, status_code=400):
        """Set error details."""
        self._success = False
        self._error_code = error_code
        self._message = message
        self._status_code = status_code
        return self
    
    def data(self, data):
        """Set response data."""
        self._data = data
        return self
    
    def details(self, details):
        """Set error details."""
        self._details = details
        return self
    
    def status(self, status_code):
        """Set status code."""
        self._status_code = status_code
        return self
    
    def extra(self, **kwargs):
        """Add extra fields to response."""
        self._extra.update(kwargs)
        return self
    
    def build(self):
        """Build the response with consistent timestamp formatting."""
        if self._success:
            return success_response(
                message=self._message,
                message_key=self._message_key,
                data=self._data,
                status_code=self._status_code,
                **self._extra
            )
        else:
            return error_response(
                error_code=self._error_code,
                message=self._message,
                status_code=self._status_code,
                details=self._details,
                **self._extra
            )


def localized_success_response(message_key: str, data=None, status_code=200, **kwargs):
    """Create success response with localized message key."""
    message = _(message_key, **kwargs) if kwargs else _(message_key)
    return success_response(
        message=str(message),
        data=data,
        status_code=status_code
    )


def localized_error_response(error_code: str, message_key: str, status_code=400, details=None, **kwargs):
    """Create error response with localized message key."""
    message = _(message_key, **kwargs) if kwargs else _(message_key)
    return error_response(
        error_code=error_code,
        message=str(message),
        status_code=status_code,
        details=details
    )


def business_validation_error_response(field_errors: dict, message_key: str = None):
    """Create business validation error response with localized messages."""
    if not message_key:
        message_key = 'Business validation failed'
    
    message = _(message_key)
    
    # Localize field error messages
    localized_errors = {}
    for field, error_messages in field_errors.items():
        if isinstance(error_messages, list):
            localized_errors[field] = [_(msg) if isinstance(msg, str) else msg for msg in error_messages]
        else:
            localized_errors[field] = [_(error_messages) if isinstance(error_messages, str) else error_messages]
    
    return error_response(
        error_code='BUSINESS_VALIDATION_ERROR',
        message=str(message),
        status_code=422,
        details={'validation_errors': localized_errors}
    )


def localized_paginated_response(items, page, per_page, total, message_key=None, **kwargs):
    """Create paginated response with localized message."""
    message = None
    if message_key:
        message = _(message_key, **kwargs) if kwargs else _(message_key)
        message = str(message)
    
    return paginated_response(
        items=items,
        page=page,
        per_page=per_page,
        total=total,
        message=message
    )


def api_method_response(method: str, resource: str, success: bool = True, data=None, **kwargs):
    """Create standardized API method response with localization."""
    if success:
        message_patterns = {
            'GET': 'Retrieved {resource} successfully',
            'POST': 'Created {resource} successfully', 
            'PUT': 'Updated {resource} successfully',
            'PATCH': 'Updated {resource} successfully',
            'DELETE': 'Deleted {resource} successfully'
        }
        
        message_key = message_patterns.get(method.upper(), 'Operation completed successfully')
        message = _(message_key, resource=_(resource))
        
        return success_response(
            message=str(message),
            data=data,
            **kwargs
        )
    else:
        message = _('Operation failed for {resource}', resource=_(resource))
        return error_response(
            error_code='OPERATION_FAILED',
            message=str(message),
            status_code=400,
            **kwargs
        )


# Global response builder instance
response = ResponseBuilder()