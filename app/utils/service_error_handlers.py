"""
Service Error Handlers

This module provides specialized error handlers for different services
with graceful degradation capabilities.
"""
import logging
from typing import Dict, Any, Optional, Callable
from flask import current_app, request, g
from functools import wraps
import structlog

logger = structlog.get_logger(__name__)


class ServiceErrorHandler:
    """Base class for service-specific error handlers."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.fallback_enabled = True
        self.fallback_handlers = {}
        self.error_callbacks = []
    
    def add_fallback_handler(self, error_type: type, handler: Callable):
        """Add a fallback handler for specific error type."""
        self.fallback_handlers[error_type] = handler
    
    def add_error_callback(self, callback: Callable):
        """Add callback to be called when error occurs."""
        self.error_callbacks.append(callback)
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> Any:
        """Handle service error with fallback."""
        context = context or {}
        context['service_name'] = self.service_name
        
        # Call error callbacks
        for callback in self.error_callbacks:
            try:
                callback(error, context)
            except Exception as callback_error:
                logger.error(f"Error callback failed: {callback_error}")
        
        # Try fallback handler
        error_type = type(error)
        if error_type in self.fallback_handlers and self.fallback_enabled:
            try:
                return self.fallback_handlers[error_type](error, context)
            except Exception as fallback_error:
                logger.error(f"Fallback handler failed: {fallback_error}")
        
        # No fallback available - re-raise
        raise error


class DatabaseErrorHandler(ServiceErrorHandler):
    """Error handler for database operations."""
    
    def __init__(self):
        super().__init__('database')
        self._setup_fallback_handlers()
    
    def _setup_fallback_handlers(self):
        """Setup database-specific fallback handlers."""
        from sqlalchemy.exc import OperationalError, DatabaseError, DisconnectionError
        
        # Connection errors - try alternative database
        self.add_fallback_handler(OperationalError, self._handle_connection_error)
        self.add_fallback_handler(DisconnectionError, self._handle_connection_error)
        self.add_fallback_handler(DatabaseError, self._handle_database_error)
    
    def _handle_connection_error(self, error: Exception, context: Dict[str, Any]) -> Any:
        """Handle database connection errors."""
        logger.warning(f"Database connection error: {error}")
        
        # Try to switch to fallback database
        try:
            from app.utils.database_manager import get_database_manager
            
            if current_app:
                db_manager = get_database_manager(current_app)
                
                # Try to switch to SQLite fallback
                if db_manager.switch_to_fallback():
                    logger.info("✅ Switched to SQLite fallback database")
                    
                    # Notify user about degraded service
                    self._notify_database_degradation('connection_error', str(error))
                    
                    # Return indication that operation should be retried
                    return {'retry': True, 'fallback_active': True}
                else:
                    logger.error("❌ Failed to switch to fallback database")
                    
        except Exception as fallback_error:
            logger.error(f"Database fallback failed: {fallback_error}")
        
        # Create user-friendly error response
        return {
            'error': True,
            'message': 'Database is temporarily unavailable. Please try again later.',
            'user_message': 'We are experiencing technical difficulties. Please try again in a few moments.',
            'retry_after': 30
        }
    
    def _handle_database_error(self, error: Exception, context: Dict[str, Any]) -> Any:
        """Handle general database errors."""
        logger.error(f"Database error: {error}")
        
        # Notify about database issues
        self._notify_database_degradation('database_error', str(error))
        
        return {
            'error': True,
            'message': 'Database operation failed. Please try again.',
            'user_message': 'Unable to process your request. Please try again.',
            'retry_after': 10
        }
    
    def _notify_database_degradation(self, error_type: str, error_message: str):
        """Notify about database degradation."""
        try:
            # Get notification manager
            if current_app and 'ERROR_HANDLERS' in current_app.config:
                error_handlers = current_app.config['ERROR_HANDLERS']
                notification_manager = error_handlers.get('user_notifications')
                
                if notification_manager:
                    notification_manager.notify_service_degradation(
                        service_name='database',
                        level='degraded' if 'connection' in error_type else 'unavailable',
                        reason=f'Database {error_type}: {error_message[:100]}'
                    )
                    
        except Exception as e:
            logger.error(f"Failed to notify database degradation: {e}")


class ExternalServiceErrorHandler(ServiceErrorHandler):
    """Error handler for external service calls."""
    
    def __init__(self, service_name: str):
        super().__init__(service_name)
        self._setup_fallback_handlers()
    
    def _setup_fallback_handlers(self):
        """Setup external service fallback handlers."""
        import requests
        
        # HTTP errors
        self.add_fallback_handler(requests.exceptions.ConnectionError, self._handle_connection_error)
        self.add_fallback_handler(requests.exceptions.Timeout, self._handle_timeout_error)
        self.add_fallback_handler(requests.exceptions.HTTPError, self._handle_http_error)
        self.add_fallback_handler(requests.exceptions.RequestException, self._handle_request_error)
    
    def _handle_connection_error(self, error: Exception, context: Dict[str, Any]) -> Any:
        """Handle external service connection errors."""
        logger.warning(f"External service connection error ({self.service_name}): {error}")
        
        # Notify about service unavailability
        self._notify_service_unavailable('connection_error', str(error))
        
        return {
            'error': True,
            'service_unavailable': True,
            'message': f'{self.service_name.title()} service is temporarily unavailable.',
            'user_message': f'This feature is temporarily unavailable. Please try again later.',
            'retry_after': 300  # 5 minutes
        }
    
    def _handle_timeout_error(self, error: Exception, context: Dict[str, Any]) -> Any:
        """Handle external service timeout errors."""
        logger.warning(f"External service timeout ({self.service_name}): {error}")
        
        return {
            'error': True,
            'timeout': True,
            'message': f'{self.service_name.title()} service request timed out.',
            'user_message': 'The request is taking longer than expected. Please try again.',
            'retry_after': 60
        }
    
    def _handle_http_error(self, error: Exception, context: Dict[str, Any]) -> Any:
        """Handle HTTP errors from external services."""
        logger.warning(f"External service HTTP error ({self.service_name}): {error}")
        
        # Extract status code if available
        status_code = getattr(error.response, 'status_code', None) if hasattr(error, 'response') else None
        
        if status_code == 429:  # Rate limit
            return {
                'error': True,
                'rate_limited': True,
                'message': f'{self.service_name.title()} service rate limit exceeded.',
                'user_message': 'Too many requests. Please wait a moment and try again.',
                'retry_after': 300
            }
        elif status_code and status_code >= 500:  # Server error
            self._notify_service_unavailable('server_error', f'HTTP {status_code}')
            return {
                'error': True,
                'server_error': True,
                'message': f'{self.service_name.title()} service is experiencing issues.',
                'user_message': 'This feature is temporarily unavailable due to server issues.',
                'retry_after': 600
            }
        else:
            return {
                'error': True,
                'http_error': True,
                'status_code': status_code,
                'message': f'{self.service_name.title()} service returned an error.',
                'user_message': 'Unable to complete the request. Please try again.',
                'retry_after': 60
            }
    
    def _handle_request_error(self, error: Exception, context: Dict[str, Any]) -> Any:
        """Handle general request errors."""
        logger.error(f"External service request error ({self.service_name}): {error}")
        
        return {
            'error': True,
            'request_error': True,
            'message': f'{self.service_name.title()} service request failed.',
            'user_message': 'Unable to connect to external service. Please try again later.',
            'retry_after': 120
        }
    
    def _notify_service_unavailable(self, error_type: str, error_message: str):
        """Notify about service unavailability."""
        try:
            # Get notification manager
            if current_app and 'ERROR_HANDLERS' in current_app.config:
                error_handlers = current_app.config['ERROR_HANDLERS']
                notification_manager = error_handlers.get('user_notifications')
                
                if notification_manager:
                    notification_manager.notify_service_degradation(
                        service_name=self.service_name,
                        level='unavailable',
                        reason=f'{self.service_name} {error_type}: {error_message[:100]}'
                    )
                    
        except Exception as e:
            logger.error(f"Failed to notify service unavailability: {e}")


class CacheErrorHandler(ServiceErrorHandler):
    """Error handler for cache operations."""
    
    def __init__(self):
        super().__init__('cache')
        self._setup_fallback_handlers()
    
    def _setup_fallback_handlers(self):
        """Setup cache-specific fallback handlers."""
        # Redis connection errors
        try:
            import redis
            self.add_fallback_handler(redis.ConnectionError, self._handle_redis_error)
            self.add_fallback_handler(redis.TimeoutError, self._handle_redis_error)
            self.add_fallback_handler(redis.RedisError, self._handle_redis_error)
        except ImportError:
            pass
        
        # General cache errors
        self.add_fallback_handler(Exception, self._handle_cache_error)
    
    def _handle_redis_error(self, error: Exception, context: Dict[str, Any]) -> Any:
        """Handle Redis connection errors."""
        logger.warning(f"Redis cache error: {error}")
        
        # Switch to simple cache
        try:
            if current_app:
                current_app.config['CACHE_TYPE'] = 'simple'
                logger.info("✅ Switched to simple cache fallback")
                
                # Notify about cache degradation
                self._notify_cache_degradation('redis_error', str(error))
                
        except Exception as fallback_error:
            logger.error(f"Cache fallback failed: {fallback_error}")
        
        return {
            'error': False,  # Not a critical error
            'fallback_active': True,
            'message': 'Cache is running in reduced performance mode.',
            'user_message': 'The application may respond more slowly than usual.'
        }
    
    def _handle_cache_error(self, error: Exception, context: Dict[str, Any]) -> Any:
        """Handle general cache errors."""
        logger.warning(f"Cache error: {error}")
        
        # Cache errors are not critical - continue without cache
        return {
            'error': False,
            'cache_disabled': True,
            'message': 'Cache temporarily disabled.',
            'user_message': None  # Don't show to user
        }
    
    def _notify_cache_degradation(self, error_type: str, error_message: str):
        """Notify about cache degradation."""
        try:
            # Get notification manager
            if current_app and 'ERROR_HANDLERS' in current_app.config:
                error_handlers = current_app.config['ERROR_HANDLERS']
                notification_manager = error_handlers.get('user_notifications')
                
                if notification_manager:
                    notification_manager.notify_service_degradation(
                        service_name='cache',
                        level='degraded',
                        reason=f'Cache {error_type}: {error_message[:100]}'
                    )
                    
        except Exception as e:
            logger.error(f"Failed to notify cache degradation: {e}")


class AuthenticationErrorHandler(ServiceErrorHandler):
    """Error handler for authentication operations."""
    
    def __init__(self):
        super().__init__('authentication')
        self._setup_fallback_handlers()
    
    def _setup_fallback_handlers(self):
        """Setup authentication-specific fallback handlers."""
        from flask_jwt_extended.exceptions import JWTExtendedException
        
        # JWT errors
        self.add_fallback_handler(JWTExtendedException, self._handle_jwt_error)
        
        # General authentication errors
        self.add_fallback_handler(Exception, self._handle_auth_error)
    
    def _handle_jwt_error(self, error: Exception, context: Dict[str, Any]) -> Any:
        """Handle JWT-related errors."""
        logger.warning(f"JWT error: {error}")
        
        return {
            'error': True,
            'auth_error': True,
            'jwt_error': True,
            'message': 'Authentication token is invalid or expired.',
            'user_message': 'Your session has expired. Please log in again.',
            'redirect': '/auth/login',
            'clear_token': True
        }
    
    def _handle_auth_error(self, error: Exception, context: Dict[str, Any]) -> Any:
        """Handle general authentication errors."""
        logger.error(f"Authentication error: {error}")
        
        return {
            'error': True,
            'auth_error': True,
            'message': 'Authentication failed.',
            'user_message': 'Unable to verify your identity. Please try logging in again.',
            'redirect': '/auth/login'
        }


# Service error handler registry
_service_error_handlers = {}


def get_service_error_handler(service_name: str) -> ServiceErrorHandler:
    """Get or create service error handler."""
    if service_name not in _service_error_handlers:
        if service_name == 'database':
            _service_error_handlers[service_name] = DatabaseErrorHandler()
        elif service_name == 'cache':
            _service_error_handlers[service_name] = CacheErrorHandler()
        elif service_name == 'authentication':
            _service_error_handlers[service_name] = AuthenticationErrorHandler()
        else:
            # Generic external service handler
            _service_error_handlers[service_name] = ExternalServiceErrorHandler(service_name)
    
    return _service_error_handlers[service_name]


def with_service_error_handling(service_name: str):
    """Decorator to add service error handling to functions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as error:
                # Get service error handler
                error_handler = get_service_error_handler(service_name)
                
                # Handle the error
                result = error_handler.handle_error(error, {
                    'function': func.__name__,
                    'args': args,
                    'kwargs': kwargs
                })
                
                # If result indicates retry, try once more
                if isinstance(result, dict) and result.get('retry'):
                    try:
                        return func(*args, **kwargs)
                    except Exception as retry_error:
                        # Second attempt failed - return error result
                        logger.error(f"Retry failed for {func.__name__}: {retry_error}")
                        result['retry_failed'] = True
                        return result
                
                return result
        
        return wrapper
    return decorator


def init_service_error_handlers(app):
    """Initialize service error handlers."""
    try:
        # Pre-create common error handlers
        get_service_error_handler('database')
        get_service_error_handler('cache')
        get_service_error_handler('authentication')
        
        # Create handlers for configured external services
        external_services = [
            'openai', 'stripe', 'google_oauth', 'telegram', 'signal'
        ]
        
        for service in external_services:
            get_service_error_handler(service)
        
        logger.info(f"✅ Service error handlers initialized for {len(_service_error_handlers)} services")
        
        # Store in app config
        app.config['SERVICE_ERROR_HANDLERS'] = _service_error_handlers
        
        return _service_error_handlers
        
    except Exception as e:
        logger.error(f"Failed to initialize service error handlers: {e}")
        return {}