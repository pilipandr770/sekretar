"""Error handling utilities."""
import uuid
from flask import jsonify, request, current_app
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError
import structlog

logger = structlog.get_logger()


class APIError(Exception):
    """Base API error class."""
    
    def __init__(self, message, status_code=400, error_code=None, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or 'API_ERROR'
        self.details = details or {}


class ValidationError(APIError):
    """Validation error."""
    
    def __init__(self, message, details=None):
        super().__init__(message, 400, 'VALIDATION_ERROR', details)


class AuthenticationError(APIError):
    """Authentication error."""
    
    def __init__(self, message='Authentication required'):
        super().__init__(message, 401, 'AUTHENTICATION_ERROR')


class AuthorizationError(APIError):
    """Authorization error."""
    
    def __init__(self, message='Insufficient permissions'):
        super().__init__(message, 403, 'AUTHORIZATION_ERROR')


class NotFoundError(APIError):
    """Resource not found error."""
    
    def __init__(self, message='Resource not found'):
        super().__init__(message, 404, 'NOT_FOUND_ERROR')


class ConflictError(APIError):
    """Resource conflict error."""
    
    def __init__(self, message='Resource conflict'):
        super().__init__(message, 409, 'CONFLICT_ERROR')


class RateLimitError(APIError):
    """Rate limit exceeded error."""
    
    def __init__(self, message='Rate limit exceeded'):
        super().__init__(message, 429, 'RATE_LIMIT_ERROR')


class ExternalServiceError(APIError):
    """External service error."""
    
    def __init__(self, message='External service unavailable', service_name=None):
        details = {'service': service_name} if service_name else {}
        super().__init__(message, 503, 'EXTERNAL_SERVICE_ERROR', details)


def generate_request_id():
    """Generate unique request ID."""
    return f"req_{uuid.uuid4().hex[:12]}"


def create_error_response(error_code, message, status_code=400, details=None, request_id=None):
    """Create standardized error response."""
    if request_id is None:
        request_id = generate_request_id()
    
    response_data = {
        'error': {
            'code': error_code,
            'message': message,
            'request_id': request_id
        }
    }
    
    if details:
        response_data['error']['details'] = details
    
    return jsonify(response_data), status_code


def register_error_handlers(app):
    """Register error handlers with Flask app."""
    
    @app.errorhandler(APIError)
    def handle_api_error(error):
        """Handle custom API errors."""
        request_id = generate_request_id()
        
        logger.error(
            "API error occurred",
            error_code=error.error_code,
            message=error.message,
            status_code=error.status_code,
            details=error.details,
            request_id=request_id,
            path=request.path,
            method=request.method
        )
        
        return create_error_response(
            error.error_code,
            error.message,
            error.status_code,
            error.details,
            request_id
        )
    
    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        """Handle HTTP errors."""
        request_id = generate_request_id()
        
        logger.warning(
            "HTTP error occurred",
            status_code=error.code,
            message=error.description,
            request_id=request_id,
            path=request.path,
            method=request.method
        )
        
        return create_error_response(
            'HTTP_ERROR',
            error.description,
            error.code,
            request_id=request_id
        )
    
    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        """Handle database errors."""
        request_id = generate_request_id()
        
        logger.error(
            "Database error occurred",
            error_type=type(error).__name__,
            error_message=str(error),
            request_id=request_id,
            path=request.path,
            method=request.method
        )
        
        # Don't expose internal database errors in production
        if current_app.config.get('DEBUG'):
            message = str(error)
        else:
            message = 'Internal database error'
        
        return create_error_response(
            'DATABASE_ERROR',
            message,
            500,
            request_id=request_id
        )
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle unexpected errors."""
        request_id = generate_request_id()
        
        logger.error(
            "Unexpected error occurred",
            error_type=type(error).__name__,
            error_message=str(error),
            request_id=request_id,
            path=request.path,
            method=request.method,
            exc_info=True
        )
        
        # Don't expose internal errors in production
        if current_app.config.get('DEBUG'):
            message = str(error)
        else:
            message = 'Internal server error'
        
        return create_error_response(
            'INTERNAL_ERROR',
            message,
            500,
            request_id=request_id
        )