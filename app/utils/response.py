"""Response utilities with i18n support."""
from flask import jsonify, request
from flask_babel import gettext as _
from app.utils.i18n import translate_error_message, get_user_language
from app.utils.errors import generate_request_id
import structlog

logger = structlog.get_logger()


def success_response(message=None, data=None, status_code=200, message_key=None, **kwargs):
    """Create success response with i18n support."""
    request_id = generate_request_id()
    
    # Translate message if message_key provided
    if message_key:
        message = _(message_key)
    elif message:
        message = _(message) if isinstance(message, str) else message
    
    response_data = {
        'success': True,
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
        language=get_user_language()
    )
    
    return jsonify(response_data), status_code


def error_response(error_code, message=None, status_code=400, details=None, **kwargs):
    """Create error response with i18n support."""
    request_id = generate_request_id()
    
    # Translate error message
    if message:
        translated_message = _(message) if isinstance(message, str) else message
    else:
        translated_message = translate_error_message(error_code, **kwargs)
    
    response_data = {
        'success': False,
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
        path=request.path if request else None,
        method=request.method if request else None
    )
    
    return jsonify(response_data), status_code


def validation_error_response(errors, message=None):
    """Create validation error response."""
    if not message:
        message = _('Validation failed')
    
    return error_response(
        error_code='VALIDATION_ERROR',
        message=message,
        status_code=422,
        details={'validation_errors': errors}
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
        """Build the response."""
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


# Global response builder instance
response = ResponseBuilder()