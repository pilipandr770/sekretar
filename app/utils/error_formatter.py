"""
Error Message Formatter

This module provides utilities for creating user-friendly error messages
and formatting error responses with appropriate context and resolution steps.
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from flask import current_app, request, has_request_context
def _(text):
    """Safe gettext function that works with or without Babel."""
    try:
        from flask import current_app
        if current_app and 'babel' in current_app.extensions:
            from flask_babel import gettext
            return gettext(text)
    except (ImportError, RuntimeError, KeyError):
        pass
    return text

def ngettext(singular, plural, n):
    """Safe ngettext function that works with or without Babel."""
    try:
        from flask import current_app
        if current_app and 'babel' in current_app.extensions:
            from flask_babel import ngettext as babel_ngettext
            return babel_ngettext(singular, plural, n)
    except (ImportError, RuntimeError, KeyError):
        pass
    return singular if n == 1 else plural
import structlog

logger = structlog.get_logger(__name__)


class ErrorMessageFormatter:
    """Formats error messages for different audiences and contexts."""
    
    def __init__(self):
        self.user_friendly_messages = {
            # Database errors
            'database_connection_failed': {
                'user': _('We are experiencing technical difficulties. Please try again in a few moments.'),
                'admin': _('Database connection failed. Check database service status and connection settings.'),
                'resolution_steps': [
                    _('Check database service status'),
                    _('Verify connection settings'),
                    _('Review database logs'),
                    _('Contact system administrator if issue persists')
                ]
            },
            'database_query_failed': {
                'user': _('Unable to process your request. Please try again.'),
                'admin': _('Database query failed. Check query syntax and database schema.'),
                'resolution_steps': [
                    _('Review query syntax'),
                    _('Check database schema'),
                    _('Verify data integrity'),
                    _('Check database logs for details')
                ]
            },
            
            # Authentication errors
            'authentication_failed': {
                'user': _('Invalid credentials. Please check your email and password.'),
                'admin': _('User authentication failed. Check user credentials and account status.'),
                'resolution_steps': [
                    _('Verify email and password'),
                    _('Check account status'),
                    _('Reset password if necessary'),
                    _('Contact support if issue persists')
                ]
            },
            'token_expired': {
                'user': _('Your session has expired. Please log in again.'),
                'admin': _('JWT token has expired. User needs to re-authenticate.'),
                'resolution_steps': [
                    _('Log in again'),
                    _('Check token expiration settings'),
                    _('Clear browser cache if necessary')
                ]
            },
            'insufficient_permissions': {
                'user': _('You do not have permission to perform this action.'),
                'admin': _('User lacks required permissions for this operation.'),
                'resolution_steps': [
                    _('Contact administrator for access'),
                    _('Review user permissions'),
                    _('Check role assignments')
                ]
            },
            
            # External service errors
            'external_service_unavailable': {
                'user': _('This feature is temporarily unavailable. Please try again later.'),
                'admin': _('External service is unavailable. Check service status and configuration.'),
                'resolution_steps': [
                    _('Check external service status'),
                    _('Verify API credentials'),
                    _('Review network connectivity'),
                    _('Check service documentation for updates')
                ]
            },
            'api_rate_limit_exceeded': {
                'user': _('Too many requests. Please wait a moment before trying again.'),
                'admin': _('API rate limit exceeded. Consider implementing request throttling.'),
                'resolution_steps': [
                    _('Wait before making more requests'),
                    _('Implement request throttling'),
                    _('Review API usage patterns'),
                    _('Consider upgrading service plan')
                ]
            },
            
            # Configuration errors
            'configuration_missing': {
                'user': _('This feature is not available due to system configuration.'),
                'admin': _('Required configuration is missing. Check environment variables.'),
                'resolution_steps': [
                    _('Set required environment variables'),
                    _('Review configuration documentation'),
                    _('Restart application after configuration changes'),
                    _('Validate configuration settings')
                ]
            },
            'configuration_invalid': {
                'user': _('System configuration error. Please contact support.'),
                'admin': _('Invalid configuration detected. Review and correct settings.'),
                'resolution_steps': [
                    _('Review configuration values'),
                    _('Check configuration format'),
                    _('Validate against documentation'),
                    _('Test configuration changes')
                ]
            },
            
            # File system errors
            'file_not_found': {
                'user': _('The requested file could not be found.'),
                'admin': _('File not found. Check file path and permissions.'),
                'resolution_steps': [
                    _('Verify file path'),
                    _('Check file permissions'),
                    _('Ensure file exists'),
                    _('Review file system logs')
                ]
            },
            'file_permission_denied': {
                'user': _('Unable to access the requested file.'),
                'admin': _('File permission denied. Check file and directory permissions.'),
                'resolution_steps': [
                    _('Check file permissions'),
                    _('Verify directory permissions'),
                    _('Ensure application has required access'),
                    _('Review file ownership')
                ]
            },
            'disk_space_full': {
                'user': _('Unable to save your changes. Please try again later.'),
                'admin': _('Insufficient disk space. Free up space or expand storage.'),
                'resolution_steps': [
                    _('Free up disk space'),
                    _('Remove unnecessary files'),
                    _('Expand storage capacity'),
                    _('Monitor disk usage')
                ]
            },
            
            # Validation errors
            'validation_failed': {
                'user': _('Please check your input and try again.'),
                'admin': _('Input validation failed. Check validation rules and data format.'),
                'resolution_steps': [
                    _('Review input data'),
                    _('Check validation rules'),
                    _('Verify data format'),
                    _('Provide clear validation messages')
                ]
            },
            'required_field_missing': {
                'user': _('Please fill in all required fields.'),
                'admin': _('Required field validation failed. Check form requirements.'),
                'resolution_steps': [
                    _('Fill in all required fields'),
                    _('Review form validation'),
                    _('Check field requirements'),
                    _('Update form documentation')
                ]
            },
            
            # Network errors
            'network_timeout': {
                'user': _('Request timed out. Please check your connection and try again.'),
                'admin': _('Network timeout occurred. Check network connectivity and timeouts.'),
                'resolution_steps': [
                    _('Check network connectivity'),
                    _('Review timeout settings'),
                    _('Test network performance'),
                    _('Consider increasing timeout values')
                ]
            },
            'connection_refused': {
                'user': _('Unable to connect to the service. Please try again later.'),
                'admin': _('Connection refused. Check service availability and network configuration.'),
                'resolution_steps': [
                    _('Check service status'),
                    _('Verify network configuration'),
                    _('Review firewall settings'),
                    _('Test connectivity')
                ]
            }
        }
    
    def format_error_message(
        self,
        error_key: str,
        audience: str = 'user',
        context: Dict[str, Any] = None,
        include_resolution: bool = False
    ) -> Dict[str, Any]:
        """
        Format error message for specific audience.
        
        Args:
            error_key: Key identifying the error type
            audience: Target audience ('user' or 'admin')
            context: Additional context for message formatting
            include_resolution: Whether to include resolution steps
            
        Returns:
            Formatted error message with optional resolution steps
        """
        context = context or {}
        
        # Get message template
        message_template = self.user_friendly_messages.get(error_key)
        if not message_template:
            return self._get_generic_error_message(audience, include_resolution)
        
        # Format message for audience
        message = message_template.get(audience, message_template.get('user', ''))
        
        # Apply context formatting if needed
        if context and '{' in message:
            try:
                message = message.format(**context)
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to format error message: {e}")
        
        result = {
            'message': message,
            'error_key': error_key,
            'audience': audience
        }
        
        # Add resolution steps if requested
        if include_resolution and 'resolution_steps' in message_template:
            result['resolution_steps'] = message_template['resolution_steps']
        
        return result
    
    def _get_generic_error_message(self, audience: str, include_resolution: bool) -> Dict[str, Any]:
        """Get generic error message when specific message is not available."""
        if audience == 'admin':
            message = _('An error occurred. Check logs for details.')
            resolution_steps = [
                _('Check application logs'),
                _('Review error details'),
                _('Identify root cause'),
                _('Apply appropriate fix')
            ]
        else:
            message = _('An error occurred. Please try again or contact support.')
            resolution_steps = [
                _('Try again'),
                _('Refresh the page'),
                _('Contact support if issue persists')
            ]
        
        result = {
            'message': message,
            'error_key': 'generic_error',
            'audience': audience
        }
        
        if include_resolution:
            result['resolution_steps'] = resolution_steps
        
        return result
    
    def categorize_error_by_exception(self, error: Exception) -> str:
        """Categorize error based on exception type."""
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()
        
        # Database errors
        if any(keyword in error_type for keyword in ['database', 'sql', 'connection']):
            if 'connection' in error_message or 'connect' in error_message:
                return 'database_connection_failed'
            return 'database_query_failed'
        
        # Authentication errors
        if any(keyword in error_type for keyword in ['auth', 'token', 'jwt']):
            if 'expired' in error_message:
                return 'token_expired'
            if 'permission' in error_message or 'forbidden' in error_message:
                return 'insufficient_permissions'
            return 'authentication_failed'
        
        # File system errors
        if any(keyword in error_type for keyword in ['file', 'io', 'os']):
            if 'not found' in error_message or 'no such file' in error_message:
                return 'file_not_found'
            if 'permission' in error_message or 'access' in error_message:
                return 'file_permission_denied'
            if 'space' in error_message or 'disk full' in error_message:
                return 'disk_space_full'
        
        # Network errors
        if any(keyword in error_type for keyword in ['timeout', 'connection', 'network']):
            if 'timeout' in error_message:
                return 'network_timeout'
            if 'refused' in error_message or 'unreachable' in error_message:
                return 'connection_refused'
            return 'external_service_unavailable'
        
        # Validation errors
        if any(keyword in error_type for keyword in ['validation', 'invalid', 'value']):
            if 'required' in error_message or 'missing' in error_message:
                return 'required_field_missing'
            return 'validation_failed'
        
        # Configuration errors
        if any(keyword in error_type for keyword in ['config', 'environment', 'setting']):
            if 'missing' in error_message or 'not found' in error_message:
                return 'configuration_missing'
            return 'configuration_invalid'
        
        return 'generic_error'
    
    def create_user_friendly_response(
        self,
        error: Exception,
        context: Dict[str, Any] = None,
        include_technical_details: bool = None
    ) -> Dict[str, Any]:
        """
        Create user-friendly error response.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            include_technical_details: Whether to include technical details (defaults to DEBUG setting)
            
        Returns:
            User-friendly error response
        """
        if include_technical_details is None:
            include_technical_details = current_app.config.get('DEBUG', False)
        
        # Categorize the error
        error_key = self.categorize_error_by_exception(error)
        
        # Determine audience
        audience = 'admin' if include_technical_details else 'user'
        
        # Format error message
        formatted_error = self.format_error_message(
            error_key=error_key,
            audience=audience,
            context=context,
            include_resolution=True
        )
        
        response = {
            'user_message': formatted_error['message'],
            'error_category': error_key,
            'resolution_steps': formatted_error.get('resolution_steps', [])
        }
        
        # Add technical details if requested
        if include_technical_details:
            response['technical_details'] = {
                'error_type': type(error).__name__,
                'error_message': str(error),
                'context': context or {}
            }
            
            # Add request context if available
            if has_request_context():
                response['technical_details']['request_context'] = {
                    'method': request.method,
                    'path': request.path,
                    'remote_addr': request.remote_addr
                }
        
        return response


# Global instance
_error_formatter = None


def get_error_formatter() -> ErrorMessageFormatter:
    """Get or create error formatter instance."""
    global _error_formatter
    
    if _error_formatter is None:
        _error_formatter = ErrorMessageFormatter()
    
    return _error_formatter


def format_user_friendly_error(
    error: Exception,
    context: Dict[str, Any] = None,
    include_technical_details: bool = None
) -> Dict[str, Any]:
    """
    Convenience function to format user-friendly error.
    
    Args:
        error: The exception that occurred
        context: Additional context information
        include_technical_details: Whether to include technical details
        
    Returns:
        User-friendly error response
    """
    formatter = get_error_formatter()
    return formatter.create_user_friendly_response(
        error=error,
        context=context,
        include_technical_details=include_technical_details
    )