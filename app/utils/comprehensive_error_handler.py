"""
Comprehensive Error Handler

This module provides a comprehensive error handling system that integrates
enhanced logging, graceful degradation, user notifications, and error formatting.
"""
import logging
from typing import Dict, Any, Optional, Tuple
from flask import Flask, request, current_app, g
from werkzeug.exceptions import HTTPException
import structlog

logger = structlog.get_logger(__name__)


class ComprehensiveErrorHandler:
    """
    Comprehensive error handler that coordinates all error handling systems.
    """
    
    def __init__(self, app: Optional[Flask] = None):
        """Initialize comprehensive error handler."""
        self.app = app
        self._enhanced_logging_manager = None
        self._graceful_degradation_manager = None
        self._user_notification_manager = None
        self._error_formatter = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize with Flask app."""
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['comprehensive_error_handler'] = self
        
        # Initialize component managers
        self._initialize_managers()
        
        # Register comprehensive error handlers
        self._register_error_handlers()
        
        # Register request hooks
        self._register_request_hooks()
        
        logger.info("🛡️ Comprehensive error handler initialized")
    
    def _initialize_managers(self):
        """Initialize all error handling component managers."""
        try:
            from app.utils.enhanced_logging import get_enhanced_logging_manager
            from app.utils.graceful_degradation import get_graceful_degradation_manager
            from app.utils.user_notifications import get_user_notification_manager
            from app.utils.error_formatter import get_error_formatter
            
            self._enhanced_logging_manager = get_enhanced_logging_manager(self.app)
            self._graceful_degradation_manager = get_graceful_degradation_manager(self.app)
            self._user_notification_manager = get_user_notification_manager(self.app)
            self._error_formatter = get_error_formatter()
            
            logger.info("✅ All error handling managers initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize error handling managers: {e}")
    
    def _register_error_handlers(self):
        """Register comprehensive error handlers."""
        
        @self.app.errorhandler(Exception)
        def handle_all_exceptions(error):
            """Comprehensive exception handler."""
            return self._handle_exception(error)
        
        @self.app.errorhandler(HTTPException)
        def handle_http_exceptions(error):
            """Handle HTTP exceptions."""
            return self._handle_http_exception(error)
    
    def _register_request_hooks(self):
        """Register request hooks for error context."""
        
        @self.app.before_request
        def before_request():
            """Set up error handling context before request."""
            g.error_context = {
                'request_id': self._generate_request_id(),
                'path': request.path,
                'method': request.method,
                'remote_addr': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', 'Unknown')
            }
        
        @self.app.after_request
        def after_request(response):
            """Clean up error handling context after request."""
            # Log successful requests for monitoring
            if hasattr(g, 'error_context') and response.status_code < 400:
                if self._enhanced_logging_manager:
                    self._enhanced_logging_manager.context_logger.log_with_context(
                        'debug',
                        'Request completed successfully',
                        status_code=response.status_code,
                        content_length=response.content_length
                    )
            
            return response
    
    def _handle_exception(self, error: Exception) -> Tuple[Dict[str, Any], int]:
        """Handle any exception comprehensively."""
        error_context = getattr(g, 'error_context', {})
        
        # 1. Enhanced logging
        if self._enhanced_logging_manager:
            self._enhanced_logging_manager.error_tracker.track_error(error, error_context)
        
        # 2. Check if this is a service degradation issue
        self._check_and_handle_service_degradation(error, error_context)
        
        # 3. Create user notification if needed
        self._create_error_notification(error, error_context)
        
        # 4. Format user-friendly response
        response_data, status_code = self._format_error_response(error, error_context)
        
        # 5. Log the final response
        logger.error(
            "Exception handled comprehensively",
            error_type=type(error).__name__,
            status_code=status_code,
            request_id=error_context.get('request_id'),
            path=error_context.get('path'),
            method=error_context.get('method')
        )
        
        return response_data, status_code
    
    def _handle_http_exception(self, error: HTTPException) -> Tuple[Dict[str, Any], int]:
        """Handle HTTP exceptions."""
        error_context = getattr(g, 'error_context', {})
        
        # Log HTTP errors
        if self._enhanced_logging_manager:
            self._enhanced_logging_manager.context_logger.log_with_context(
                'warning',
                f"HTTP {error.code} error",
                error_description=error.description,
                status_code=error.code
            )
        
        # Format response
        response_data = {
            'error': {
                'code': f'HTTP_{error.code}',
                'message': error.description,
                'request_id': error_context.get('request_id')
            }
        }
        
        return response_data, error.code
    
    def _check_and_handle_service_degradation(self, error: Exception, context: Dict[str, Any]):
        """Check if error indicates service degradation and handle accordingly."""
        if not self._graceful_degradation_manager:
            return
        
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()
        
        # Database connection errors
        if any(keyword in error_type for keyword in ['database', 'sql', 'connection']):
            if 'connection' in error_message or 'connect' in error_message:
                self._graceful_degradation_manager.add_service_degradation(
                    self._graceful_degradation_manager.ServiceDegradation(
                        service_name='database',
                        level=self._graceful_degradation_manager.ServiceLevel.UNAVAILABLE,
                        reason=f'Database connection error: {str(error)[:100]}',
                        fallback_enabled=True,
                        user_message='Database is temporarily unavailable. Some features may be limited.',
                        admin_message=f'Database connection failed: {str(error)}',
                        recovery_instructions='Check database service status and connection settings'
                    )
                )
        
        # External service errors
        elif any(keyword in error_type for keyword in ['timeout', 'connection', 'http']):
            service_name = context.get('service_name', 'external_service')
            self._graceful_degradation_manager.add_service_degradation(
                self._graceful_degradation_manager.ServiceDegradation(
                    service_name=service_name,
                    level=self._graceful_degradation_manager.ServiceLevel.DEGRADED,
                    reason=f'External service error: {str(error)[:100]}',
                    fallback_enabled=False,
                    user_message=f'{service_name.title()} service is temporarily unavailable.',
                    admin_message=f'External service error for {service_name}: {str(error)}',
                    recovery_instructions=f'Check {service_name} service status and configuration'
                )
            )
    
    def _create_error_notification(self, error: Exception, context: Dict[str, Any]):
        """Create user notification for significant errors."""
        if not self._user_notification_manager:
            return
        
        error_type = type(error).__name__.lower()
        error_severity = self._determine_notification_severity(error)
        
        # Only create notifications for significant errors
        if error_severity in ['high', 'critical']:
            notification_id = f"error_{context.get('request_id', 'unknown')}"
            
            # Determine notification type and message
            if 'database' in error_type or 'sql' in error_type:
                template_name = 'database_connection_failed'
                title = 'Database Issue'
            elif 'auth' in error_type or 'permission' in error_type:
                template_name = 'configuration_error'
                title = 'Authentication Issue'
            elif 'config' in error_type or 'environment' in error_type:
                template_name = 'configuration_error'
                title = 'Configuration Issue'
            else:
                template_name = 'configuration_error'
                title = 'System Issue'
            
            try:
                self._user_notification_manager.create_from_template(
                    notification_id=notification_id,
                    template_name=template_name,
                    title=title,
                    message=f'A {error_severity} severity error occurred: {type(error).__name__}',
                    service_affected=context.get('service_name', 'system')
                )
            except Exception as e:
                logger.warning(f"Failed to create error notification: {e}")
    
    def _determine_notification_severity(self, error: Exception) -> str:
        """Determine notification severity based on error type."""
        error_type = type(error).__name__.lower()
        
        # Critical errors
        if any(keyword in error_type for keyword in ['database', 'auth', 'security']):
            return 'critical'
        
        # High severity errors
        if any(keyword in error_type for keyword in ['permission', 'config', 'connection']):
            return 'high'
        
        # Medium severity errors
        if any(keyword in error_type for keyword in ['validation', 'timeout', 'file']):
            return 'medium'
        
        return 'low'
    
    def _format_error_response(self, error: Exception, context: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """Format comprehensive error response."""
        # Use error formatter if available
        if self._error_formatter:
            try:
                formatted_error = self._error_formatter.create_user_friendly_response(
                    error=error,
                    context=context,
                    include_technical_details=current_app.config.get('DEBUG', False)
                )
                
                response_data = {
                    'error': {
                        'code': formatted_error.get('error_category', 'UNKNOWN_ERROR').upper(),
                        'message': formatted_error['user_message'],
                        'request_id': context.get('request_id')
                    }
                }
                
                # Add resolution steps if available
                if formatted_error.get('resolution_steps'):
                    response_data['error']['resolution_steps'] = formatted_error['resolution_steps']
                
                # Add technical details if in debug mode
                if formatted_error.get('technical_details'):
                    response_data['error']['technical_details'] = formatted_error['technical_details']
                
                # Determine status code
                status_code = self._determine_status_code(error)
                
                return response_data, status_code
                
            except Exception as e:
                logger.warning(f"Failed to format error response: {e}")
        
        # Fallback to basic error response
        response_data = {
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An internal error occurred. Please try again later.',
                'request_id': context.get('request_id')
            }
        }
        
        if current_app.config.get('DEBUG'):
            response_data['error']['technical_details'] = {
                'error_type': type(error).__name__,
                'error_message': str(error)
            }
        
        return response_data, 500
    
    def _determine_status_code(self, error: Exception) -> int:
        """Determine appropriate HTTP status code for error."""
        error_type = type(error).__name__.lower()
        
        # Authentication/Authorization errors
        if 'auth' in error_type or 'permission' in error_type:
            if 'permission' in error_type or 'forbidden' in error_type:
                return 403
            return 401
        
        # Validation errors
        if 'validation' in error_type or 'invalid' in error_type:
            return 400
        
        # Not found errors
        if 'notfound' in error_type or 'missing' in error_type:
            return 404
        
        # Conflict errors
        if 'conflict' in error_type or 'duplicate' in error_type:
            return 409
        
        # Rate limiting errors
        if 'rate' in error_type or 'limit' in error_type:
            return 429
        
        # Service unavailable errors
        if 'service' in error_type or 'unavailable' in error_type:
            return 503
        
        # Default to internal server error
        return 500
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        import uuid
        return f"req_{uuid.uuid4().hex[:12]}"
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        stats = {
            'error_tracking': {},
            'service_degradations': {},
            'notifications': {},
            'system_health': {}
        }
        
        # Error tracking stats
        if self._enhanced_logging_manager:
            stats['error_tracking'] = self._enhanced_logging_manager.get_logging_stats()
        
        # Service degradation stats
        if self._graceful_degradation_manager:
            stats['service_degradations'] = self._graceful_degradation_manager.get_service_status_summary()
        
        # Notification stats
        if self._user_notification_manager:
            stats['notifications'] = self._user_notification_manager.get_notification_stats()
        
        # Overall system health
        if self._graceful_degradation_manager:
            overall_level = self._graceful_degradation_manager.get_overall_service_level()
            stats['system_health'] = {
                'overall_level': overall_level.value,
                'health_score': self._calculate_health_score(stats['service_degradations'])
            }
        
        return stats
    
    def _calculate_health_score(self, service_stats: Dict[str, Any]) -> float:
        """Calculate overall system health score."""
        if not service_stats:
            return 100.0
        
        degraded = service_stats.get('degraded_services', 0)
        unavailable = service_stats.get('unavailable_services', 0)
        critical_issues = service_stats.get('critical_issues', 0)
        
        # Simple health score calculation
        total_issues = degraded + unavailable + critical_issues
        if total_issues == 0:
            return 100.0
        
        # Weight different types of issues
        score = 100.0 - (degraded * 10 + unavailable * 20 + critical_issues * 30)
        return max(0.0, min(100.0, score))


# Global instance
_comprehensive_error_handler = None


def get_comprehensive_error_handler(app: Optional[Flask] = None) -> ComprehensiveErrorHandler:
    """Get or create comprehensive error handler instance."""
    global _comprehensive_error_handler
    
    if _comprehensive_error_handler is None:
        _comprehensive_error_handler = ComprehensiveErrorHandler(app)
    elif app is not None and _comprehensive_error_handler.app is None:
        _comprehensive_error_handler.init_app(app)
    
    return _comprehensive_error_handler


def init_comprehensive_error_handler(app: Flask) -> ComprehensiveErrorHandler:
    """Initialize comprehensive error handler for Flask app."""
    handler = get_comprehensive_error_handler(app)
    return handler