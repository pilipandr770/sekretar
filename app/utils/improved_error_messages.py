"""
Improved Error Messages and Logging

This module provides enhanced error messages with actionable information,
structured logging, and context-aware error handling.
"""
import logging
import os
import traceback
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import json


class ErrorCategory(Enum):
    """Categories of errors for better organization."""
    DATABASE_CONNECTION = "database_connection"
    APPLICATION_CONTEXT = "application_context"
    CONFIGURATION = "configuration"
    EXTERNAL_SERVICE = "external_service"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    RESOURCE = "resource"
    NETWORK = "network"
    GENERAL = "general"


class ErrorSeverity(Enum):
    """Error severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ActionableError:
    """Represents an error with actionable information."""
    error_type: str
    error_message: str
    category: ErrorCategory
    severity: ErrorSeverity
    user_message: str
    technical_details: str
    resolution_steps: List[str]
    context: Dict[str, Any]
    timestamp: datetime
    request_id: Optional[str] = None
    traceback: Optional[str] = None


class ImprovedErrorMessageGenerator:
    """
    Generates improved error messages with actionable information.
    """
    
    def __init__(self):
        """Initialize the error message generator."""
        self._error_patterns = self._initialize_error_patterns()
        self._resolution_templates = self._initialize_resolution_templates()
    
    def create_actionable_error(self,
                              error: Exception,
                              context: Optional[Dict[str, Any]] = None,
                              request_id: Optional[str] = None) -> ActionableError:
        """
        Create an actionable error from an exception.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            request_id: Optional request ID for tracking
            
        Returns:
            ActionableError with enhanced information
        """
        error_type = type(error).__name__
        error_message = str(error)
        context = context or {}
        
        # Categorize the error
        category = self._categorize_error(error, context)
        severity = self._determine_severity(error, context)
        
        # Generate user-friendly message and resolution steps
        user_message, resolution_steps = self._generate_user_message_and_steps(
            error, category, context
        )
        
        # Generate technical details
        technical_details = self._generate_technical_details(error, context)
        
        return ActionableError(
            error_type=error_type,
            error_message=error_message,
            category=category,
            severity=severity,
            user_message=user_message,
            technical_details=technical_details,
            resolution_steps=resolution_steps,
            context=context,
            timestamp=datetime.now(),
            request_id=request_id,
            traceback=traceback.format_exc()
        )
    
    def _categorize_error(self, error: Exception, context: Dict[str, Any]) -> ErrorCategory:
        """Categorize the error based on type and context."""
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()
        
        # Database connection errors
        if any(keyword in error_type for keyword in ['database', 'sql', 'connection']):
            if any(keyword in error_message for keyword in ['connect', 'connection', 'timeout']):
                return ErrorCategory.DATABASE_CONNECTION
        
        # Application context errors
        if 'context' in error_type or 'working outside of application context' in error_message:
            return ErrorCategory.APPLICATION_CONTEXT
        
        # Configuration errors
        if any(keyword in error_type for keyword in ['config', 'environment', 'setting']):
            return ErrorCategory.CONFIGURATION
        
        # Check error message for configuration-related content
        if any(keyword in error_message for keyword in ['invalid', 'url', 'missing', 'configuration']):
            if context.get('service_name') and 'config' in context['service_name'].lower():
                return ErrorCategory.CONFIGURATION
        
        # Authentication/Authorization errors
        if any(keyword in error_type for keyword in ['auth', 'permission', 'token', 'jwt']):
            if 'permission' in error_type or 'forbidden' in error_message:
                return ErrorCategory.PERMISSION
            return ErrorCategory.AUTHENTICATION
        
        # External service errors
        if any(keyword in error_type for keyword in ['http', 'request', 'timeout', 'connection']):
            return ErrorCategory.EXTERNAL_SERVICE
        
        # Network errors
        if any(keyword in error_type for keyword in ['network', 'socket', 'dns']):
            return ErrorCategory.NETWORK
        
        # Validation errors
        if 'validation' in error_type or 'invalid' in error_type:
            return ErrorCategory.VALIDATION
        
        # Resource errors
        if any(keyword in error_type for keyword in ['file', 'directory', 'memory', 'disk']):
            return ErrorCategory.RESOURCE
        
        return ErrorCategory.GENERAL
    
    def _determine_severity(self, error: Exception, context: Dict[str, Any]) -> ErrorSeverity:
        """Determine error severity based on type and context."""
        error_type = type(error).__name__.lower()
        
        # Critical errors that prevent core functionality
        if any(keyword in error_type for keyword in ['database', 'auth', 'security']):
            return ErrorSeverity.CRITICAL
        
        # High severity errors that affect important features
        if any(keyword in error_type for keyword in ['permission', 'config', 'connection']):
            return ErrorSeverity.HIGH
        
        # Medium severity errors that affect user experience
        if any(keyword in error_type for keyword in ['validation', 'timeout', 'file']):
            return ErrorSeverity.MEDIUM
        
        # Check context for severity hints
        if context.get('severity'):
            try:
                return ErrorSeverity(context['severity'])
            except ValueError:
                pass
        
        return ErrorSeverity.LOW
    
    def _generate_user_message_and_steps(self,
                                       error: Exception,
                                       category: ErrorCategory,
                                       context: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Generate user-friendly message and resolution steps."""
        error_type = type(error).__name__
        error_message = str(error)
        
        if category == ErrorCategory.DATABASE_CONNECTION:
            return self._handle_database_connection_error(error, context)
        elif category == ErrorCategory.APPLICATION_CONTEXT:
            return self._handle_application_context_error(error, context)
        elif category == ErrorCategory.CONFIGURATION:
            return self._handle_configuration_error(error, context)
        elif category == ErrorCategory.EXTERNAL_SERVICE:
            return self._handle_external_service_error(error, context)
        elif category == ErrorCategory.AUTHENTICATION:
            return self._handle_authentication_error(error, context)
        elif category == ErrorCategory.PERMISSION:
            return self._handle_permission_error(error, context)
        elif category == ErrorCategory.VALIDATION:
            return self._handle_validation_error(error, context)
        elif category == ErrorCategory.RESOURCE:
            return self._handle_resource_error(error, context)
        elif category == ErrorCategory.NETWORK:
            return self._handle_network_error(error, context)
        else:
            return self._handle_general_error(error, context)
    
    def _handle_database_connection_error(self, error: Exception, context: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Handle database connection errors."""
        error_message = str(error).lower()
        
        if 'timeout' in error_message:
            user_message = "Database connection timed out. The database server may be overloaded or unreachable."
            resolution_steps = [
                "Check if the database server is running and accessible",
                "Verify network connectivity to the database server",
                "Check if DATABASE_URL environment variable is correctly set",
                "Consider increasing the connection timeout in configuration",
                "Check database server logs for any issues"
            ]
        elif 'authentication' in error_message or 'password' in error_message:
            user_message = "Database authentication failed. Please check your database credentials."
            resolution_steps = [
                "Verify the database username and password in DATABASE_URL",
                "Check if the database user has the necessary permissions",
                "Ensure the database exists and is accessible",
                "Test the connection string manually using a database client"
            ]
        elif 'does not exist' in error_message or 'not found' in error_message:
            user_message = "Database or table not found. The database may need to be created or migrated."
            resolution_steps = [
                "Check if the database specified in DATABASE_URL exists",
                "Run database migrations to create missing tables",
                "Verify the database name in the connection string",
                "Check if you have permissions to access the database"
            ]
        elif 'connection refused' in error_message:
            user_message = "Cannot connect to database server. The server may be down or unreachable."
            resolution_steps = [
                "Check if the database server is running",
                "Verify the host and port in DATABASE_URL are correct",
                "Check firewall settings that might block the connection",
                "Test network connectivity to the database server",
                "Check if the database service is properly configured"
            ]
        else:
            user_message = "Database connection failed. Please check your database configuration."
            resolution_steps = [
                "Verify DATABASE_URL environment variable is set correctly",
                "Check database server status and connectivity",
                "Review database server logs for error details",
                "Test the connection using a database client tool",
                "Consider using SQLite as a fallback for development"
            ]
        
        return user_message, resolution_steps
    
    def _handle_application_context_error(self, error: Exception, context: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Handle application context errors."""
        user_message = "Application context error occurred. This usually happens in background tasks."
        resolution_steps = [
            "Ensure background tasks use proper Flask application context",
            "Use the ApplicationContextManager for background services",
            "Wrap database operations with app.app_context()",
            "Check if the function is being called outside of a Flask request",
            "Review the application initialization code"
        ]
        
        return user_message, resolution_steps
    
    def _handle_configuration_error(self, error: Exception, context: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Handle configuration errors."""
        error_message = str(error).lower()
        
        if 'environment' in error_message or 'env' in error_message:
            user_message = "Environment configuration error. Required environment variables may be missing."
            resolution_steps = [
                "Check if all required environment variables are set",
                "Verify the .env file exists and is properly formatted",
                "Compare your configuration with .env.example",
                "Check for typos in environment variable names",
                "Ensure environment variables are loaded before application startup"
            ]
        else:
            user_message = "Configuration error occurred. Please check your application settings."
            resolution_steps = [
                "Review your configuration files for syntax errors",
                "Check if all required configuration values are provided",
                "Verify configuration file paths and permissions",
                "Compare with working configuration examples",
                "Check application logs for more specific error details"
            ]
        
        return user_message, resolution_steps
    
    def _handle_external_service_error(self, error: Exception, context: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Handle external service errors."""
        service_name = context.get('service_name', 'external service')
        
        user_message = f"Failed to connect to {service_name}. The service may be temporarily unavailable."
        resolution_steps = [
            f"Check if {service_name} is accessible from your network",
            "Verify service URL and credentials are correct",
            "Check if the service is experiencing downtime",
            "Review rate limiting or quota restrictions",
            "Consider implementing retry logic with exponential backoff",
            "Check if fallback options are available"
        ]
        
        return user_message, resolution_steps
    
    def _handle_authentication_error(self, error: Exception, context: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Handle authentication errors."""
        user_message = "Authentication failed. Please check your credentials."
        resolution_steps = [
            "Verify username and password are correct",
            "Check if the account is active and not locked",
            "Ensure authentication tokens are valid and not expired",
            "Review authentication configuration settings",
            "Check if two-factor authentication is required",
            "Clear browser cache and cookies if using web interface"
        ]
        
        return user_message, resolution_steps
    
    def _handle_permission_error(self, error: Exception, context: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Handle permission errors."""
        user_message = "Permission denied. You don't have sufficient privileges for this operation."
        resolution_steps = [
            "Check if your user account has the necessary permissions",
            "Contact an administrator to grant required permissions",
            "Verify you're accessing the correct resource",
            "Check if the resource exists and is accessible",
            "Review role-based access control settings"
        ]
        
        return user_message, resolution_steps
    
    def _handle_validation_error(self, error: Exception, context: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Handle validation errors."""
        user_message = "Input validation failed. Please check the provided data."
        resolution_steps = [
            "Review the input data for correct format and values",
            "Check required fields are provided",
            "Verify data types match expected formats",
            "Check for special characters that might not be allowed",
            "Review validation rules and constraints",
            "Ensure data length is within acceptable limits"
        ]
        
        return user_message, resolution_steps
    
    def _handle_resource_error(self, error: Exception, context: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Handle resource errors."""
        error_message = str(error).lower()
        
        if 'file' in error_message or 'directory' in error_message:
            user_message = "File or directory access error. Check file permissions and paths."
            resolution_steps = [
                "Verify the file or directory path is correct",
                "Check file and directory permissions",
                "Ensure the file exists and is accessible",
                "Check available disk space",
                "Verify the application has read/write permissions"
            ]
        elif 'memory' in error_message:
            user_message = "Memory error occurred. The system may be running low on memory."
            resolution_steps = [
                "Check system memory usage",
                "Restart the application to free up memory",
                "Consider increasing available memory",
                "Review memory-intensive operations",
                "Check for memory leaks in the application"
            ]
        else:
            user_message = "Resource access error occurred."
            resolution_steps = [
                "Check system resources (memory, disk space, file handles)",
                "Verify resource permissions and accessibility",
                "Review resource usage patterns",
                "Consider resource cleanup or optimization"
            ]
        
        return user_message, resolution_steps
    
    def _handle_network_error(self, error: Exception, context: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Handle network errors."""
        user_message = "Network error occurred. Check your internet connection and network settings."
        resolution_steps = [
            "Check internet connectivity",
            "Verify network configuration and DNS settings",
            "Check if firewall is blocking the connection",
            "Test connectivity to the target server",
            "Review proxy settings if applicable",
            "Check for network timeouts or rate limiting"
        ]
        
        return user_message, resolution_steps
    
    def _handle_general_error(self, error: Exception, context: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Handle general errors."""
        user_message = "An unexpected error occurred. Please check the logs for more details."
        resolution_steps = [
            "Check application logs for detailed error information",
            "Verify system requirements are met",
            "Try restarting the application",
            "Check for recent configuration changes",
            "Contact support if the issue persists"
        ]
        
        return user_message, resolution_steps
    
    def _generate_technical_details(self, error: Exception, context: Dict[str, Any]) -> str:
        """Generate technical details for debugging."""
        details = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat(),
            'context': context
        }
        
        # Add environment information
        details['environment'] = {
            'python_version': os.sys.version,
            'platform': os.name,
            'working_directory': os.getcwd()
        }
        
        # Add relevant environment variables (masked)
        env_vars = {}
        for key in ['DATABASE_URL', 'REDIS_URL', 'SECRET_KEY', 'FLASK_ENV']:
            value = os.environ.get(key)
            if value:
                if key in ['DATABASE_URL', 'REDIS_URL'] and '://' in value:
                    # Mask credentials in URLs
                    parts = value.split('://')
                    if len(parts) == 2 and '@' in parts[1]:
                        auth_part, host_part = parts[1].split('@', 1)
                        if ':' in auth_part:
                            user, password = auth_part.split(':', 1)
                            masked_value = f"{parts[0]}://{user}:***@{host_part}"
                        else:
                            masked_value = f"{parts[0]}://***@{host_part}"
                        env_vars[key] = masked_value
                    else:
                        env_vars[key] = value
                elif key == 'SECRET_KEY':
                    env_vars[key] = '***' if value else 'Not set'
                else:
                    env_vars[key] = value
            else:
                env_vars[key] = 'Not set'
        
        details['environment_variables'] = env_vars
        
        return json.dumps(details, indent=2, default=str)
    
    def _initialize_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize error patterns for matching."""
        return {
            'database_connection_timeout': {
                'patterns': ['timeout', 'connection timeout', 'timed out'],
                'category': ErrorCategory.DATABASE_CONNECTION,
                'severity': ErrorSeverity.HIGH
            },
            'database_authentication_failed': {
                'patterns': ['authentication failed', 'password authentication failed', 'access denied'],
                'category': ErrorCategory.DATABASE_CONNECTION,
                'severity': ErrorSeverity.CRITICAL
            },
            'working_outside_context': {
                'patterns': ['working outside of application context'],
                'category': ErrorCategory.APPLICATION_CONTEXT,
                'severity': ErrorSeverity.MEDIUM
            }
        }
    
    def _initialize_resolution_templates(self) -> Dict[ErrorCategory, List[str]]:
        """Initialize resolution step templates."""
        return {
            ErrorCategory.DATABASE_CONNECTION: [
                "Check database server status",
                "Verify connection string",
                "Test network connectivity",
                "Review database logs"
            ],
            ErrorCategory.APPLICATION_CONTEXT: [
                "Use proper Flask application context",
                "Wrap operations with app.app_context()",
                "Check background task implementation"
            ],
            ErrorCategory.CONFIGURATION: [
                "Review configuration files",
                "Check environment variables",
                "Verify file permissions"
            ]
        }


class StructuredLogger:
    """
    Provides structured logging with enhanced context and formatting.
    """
    
    def __init__(self, logger_name: str = __name__):
        """Initialize structured logger."""
        self.logger = logging.getLogger(logger_name)
        self.error_generator = ImprovedErrorMessageGenerator()
    
    def log_actionable_error(self,
                           error: Exception,
                           context: Optional[Dict[str, Any]] = None,
                           request_id: Optional[str] = None,
                           log_level: str = 'error'):
        """
        Log an error with actionable information.
        
        Args:
            error: The exception to log
            context: Additional context information
            request_id: Optional request ID for tracking
            log_level: Log level to use
        """
        actionable_error = self.error_generator.create_actionable_error(
            error, context, request_id
        )
        
        # Create structured log entry
        log_data = {
            'error_type': actionable_error.error_type,
            'error_category': actionable_error.category.value,
            'error_severity': actionable_error.severity.value,
            'user_message': actionable_error.user_message,
            'resolution_steps': actionable_error.resolution_steps,
            'context': actionable_error.context,
            'timestamp': actionable_error.timestamp.isoformat(),
            'request_id': actionable_error.request_id
        }
        
        # Add technical details in debug mode
        if self.logger.isEnabledFor(logging.DEBUG):
            log_data['technical_details'] = actionable_error.technical_details
            log_data['traceback'] = actionable_error.traceback
        
        # Log with appropriate level
        log_method = getattr(self.logger, log_level.lower(), self.logger.error)
        log_method(
            f"[{actionable_error.category.value.upper()}] {actionable_error.user_message}",
            extra={'structured_data': log_data}
        )
    
    def log_with_context(self,
                        level: str,
                        message: str,
                        context: Optional[Dict[str, Any]] = None,
                        **kwargs):
        """
        Log a message with structured context.
        
        Args:
            level: Log level
            message: Log message
            context: Additional context information
            **kwargs: Additional keyword arguments
        """
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'context': context or {},
            **kwargs
        }
        
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message, extra={'structured_data': log_data})


# Global instances for easy access
_error_message_generator: Optional[ImprovedErrorMessageGenerator] = None
_structured_logger: Optional[StructuredLogger] = None


def get_error_message_generator() -> ImprovedErrorMessageGenerator:
    """Get or create global error message generator."""
    global _error_message_generator
    if _error_message_generator is None:
        _error_message_generator = ImprovedErrorMessageGenerator()
    return _error_message_generator


def get_structured_logger(logger_name: str = __name__) -> StructuredLogger:
    """Get or create structured logger."""
    global _structured_logger
    if _structured_logger is None:
        _structured_logger = StructuredLogger(logger_name)
    return _structured_logger


def log_actionable_error(error: Exception,
                        context: Optional[Dict[str, Any]] = None,
                        request_id: Optional[str] = None,
                        log_level: str = 'error',
                        logger_name: str = __name__):
    """
    Convenience function to log an actionable error.
    
    Args:
        error: The exception to log
        context: Additional context information
        request_id: Optional request ID for tracking
        log_level: Log level to use
        logger_name: Logger name to use
    """
    structured_logger = get_structured_logger(logger_name)
    structured_logger.log_actionable_error(error, context, request_id, log_level)


def create_actionable_error_message(error: Exception,
                                  context: Optional[Dict[str, Any]] = None,
                                  request_id: Optional[str] = None) -> ActionableError:
    """
    Convenience function to create an actionable error message.
    
    Args:
        error: The exception to process
        context: Additional context information
        request_id: Optional request ID for tracking
        
    Returns:
        ActionableError with enhanced information
    """
    generator = get_error_message_generator()
    return generator.create_actionable_error(error, context, request_id)