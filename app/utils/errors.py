"""Error handling utilities."""
import uuid
from flask import jsonify, request, current_app
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError
import structlog

logger = structlog.get_logger()


class ServiceUnavailableError(Exception):
    """Service unavailable error with graceful degradation support."""
    
    def __init__(self, service_name, message=None, fallback_available=False, fallback_service=None):
        self.service_name = service_name
        self.fallback_available = fallback_available
        self.fallback_service = fallback_service
        
        if not message:
            if fallback_available:
                message = f"{service_name} is temporarily unavailable, using fallback"
            else:
                message = f"{service_name} is temporarily unavailable"
        
        super().__init__(message)


class ConfigurationError(Exception):
    """Configuration error with resolution hints."""
    
    def __init__(self, config_key, message=None, resolution_steps=None):
        self.config_key = config_key
        self.resolution_steps = resolution_steps or []
        
        if not message:
            message = f"Configuration error for {config_key}"
        
        super().__init__(message)


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
        
        # Enhanced logging with context
        try:
            from app.utils.enhanced_logging import get_enhanced_logging_manager
            logging_manager = get_enhanced_logging_manager()
            logging_manager.error_tracker.track_error(error, {
                'error_code': error.error_code,
                'status_code': error.status_code,
                'details': error.details,
                'request_id': request_id,
                'path': request.path,
                'method': request.method
            })
        except ImportError:
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
        
        # Create user-friendly error message
        user_message = error.message
        if not app.config.get('DEBUG') and error.status_code >= 500:
            user_message = "An internal error occurred. Please try again later."
        
        return create_error_response(
            error.error_code,
            user_message,
            error.status_code,
            error.details if app.config.get('DEBUG') else None,
            request_id
        )
    
    @app.errorhandler(ServiceUnavailableError)
    def handle_service_unavailable_error(error):
        """Handle service unavailable errors with graceful degradation."""
        request_id = generate_request_id()
        
        # Log service unavailability
        try:
            from app.utils.enhanced_logging import log_service_unavailable
            log_service_unavailable(
                service_name=error.service_name,
                error=str(error),
                fallback_available=error.fallback_available,
                fallback_service=error.fallback_service
            )
        except ImportError:
            logger.warning(f"Service unavailable: {error.service_name} - {str(error)}")
        
        # Create user-friendly error response
        if error.fallback_available:
            message = f"Service is running in reduced functionality mode"
            status_code = 200  # Still functional with fallback
        else:
            message = f"Service is temporarily unavailable"
            status_code = 503
        
        return create_error_response(
            'SERVICE_UNAVAILABLE',
            message,
            status_code,
            {
                'service': error.service_name,
                'fallback_available': error.fallback_available,
                'fallback_service': error.fallback_service
            },
            request_id
        )
    
    @app.errorhandler(ConfigurationError)
    def handle_configuration_error(error):
        """Handle configuration errors with resolution hints."""
        request_id = generate_request_id()
        
        # Log configuration error
        try:
            from app.utils.enhanced_logging import log_configuration_error
            log_configuration_error(
                service_name='configuration',
                config_key=error.config_key,
                error=str(error),
                resolution_hint='; '.join(error.resolution_steps) if error.resolution_steps else None
            )
        except ImportError:
            logger.error(f"Configuration error: {error.config_key} - {str(error)}")
        
        # Create admin-friendly error response
        message = "Configuration issue detected"
        if not current_app.config.get('DEBUG'):
            message = "System configuration needs attention"
        
        return create_error_response(
            'CONFIGURATION_ERROR',
            message,
            500,
            {
                'config_key': error.config_key,
                'resolution_steps': error.resolution_steps
            } if current_app.config.get('DEBUG') else None,
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
        
        # Enhanced error tracking and logging
        try:
            from app.utils.enhanced_logging import get_enhanced_logging_manager
            from app.utils.user_notifications import get_user_notification_manager
            
            logging_manager = get_enhanced_logging_manager()
            notification_manager = get_user_notification_manager()
            
            # Track the error
            logging_manager.error_tracker.track_error(error, {
                'request_id': request_id,
                'path': request.path,
                'method': request.method,
                'error_category': 'unexpected_error'
            })
            
            # Create admin notification for critical errors
            if not app.config.get('DEBUG'):
                notification_manager.create_notification(
                    notification_id=f"critical_error_{request_id}",
                    type=notification_manager.NotificationType.ERROR,
                    priority=notification_manager.NotificationPriority.URGENT,
                    title="Critical System Error",
                    message=f"An unexpected error occurred: {type(error).__name__}",
                    dismissible=False,
                    service_affected="system",
                    resolution_steps=[
                        "Check application logs for detailed error information",
                        "Review recent configuration changes",
                        "Contact system administrator if error persists"
                    ]
                )
            
        except ImportError:
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
            message = 'An unexpected error occurred. Our team has been notified and is working to resolve the issue.'
        
        return create_error_response(
            'INTERNAL_ERROR',
            message,
            500,
            {'request_id': request_id} if not current_app.config.get('DEBUG') else None,
            request_id
        )