"""
Enhanced Logging System

This module provides enhanced logging for troubleshooting database and service issues,
with structured logging, contextual information, and error tracking.
"""
import logging
import os
import sys
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json
from flask import request, g, current_app, has_request_context
import structlog
from structlog.processors import JSONRenderer, TimeStamper
from structlog.stdlib import LoggerFactory, BoundLogger


class DatabaseIssueLogger:
    """Specialized logger for database-related issues."""
    
    def __init__(self, logger_name: str = 'database_issues'):
        self.logger = structlog.get_logger(logger_name)
    
    def log_connection_attempt(self, db_type: str, connection_string: str, success: bool, 
                             response_time_ms: float = None, error: str = None):
        """Log database connection attempt."""
        masked_connection = self._mask_connection_string(connection_string)
        
        if success:
            self.logger.info(
                "Database connection successful",
                db_type=db_type,
                connection_string=masked_connection,
                response_time_ms=response_time_ms,
                timestamp=datetime.now().isoformat()
            )
        else:
            self.logger.error(
                "Database connection failed",
                db_type=db_type,
                connection_string=masked_connection,
                error=error,
                response_time_ms=response_time_ms,
                timestamp=datetime.now().isoformat()
            )
    
    def log_fallback_activation(self, from_db: str, to_db: str, reason: str):
        """Log database fallback activation."""
        self.logger.warning(
            "Database fallback activated",
            from_database=from_db,
            to_database=to_db,
            reason=reason,
            timestamp=datetime.now().isoformat()
        )
    
    def log_query_error(self, query: str, error: str, db_type: str = None):
        """Log database query error."""
        self.logger.error(
            "Database query error",
            query=query[:200] + "..." if len(query) > 200 else query,
            error=error,
            db_type=db_type,
            timestamp=datetime.now().isoformat()
        )
    
    def log_migration_issue(self, migration_name: str, error: str, db_type: str = None):
        """Log database migration issue."""
        self.logger.error(
            "Database migration issue",
            migration_name=migration_name,
            error=error,
            db_type=db_type,
            timestamp=datetime.now().isoformat()
        )
    
    def log_schema_issue(self, schema_name: str, error: str, db_type: str = None):
        """Log database schema issue."""
        self.logger.error(
            "Database schema issue",
            schema_name=schema_name,
            error=error,
            db_type=db_type,
            timestamp=datetime.now().isoformat()
        )
    
    def _mask_connection_string(self, connection_string: str) -> str:
        """Mask sensitive information in connection strings."""
        if not connection_string:
            return "N/A"
        
        # Mask password in PostgreSQL connection strings
        if connection_string.startswith('postgresql://'):
            parts = connection_string.split('@')
            if len(parts) > 1:
                user_pass = parts[0].split('//')[-1]
                if ':' in user_pass:
                    user = user_pass.split(':')[0]
                    return f"postgresql://{user}:***@{parts[1]}"
        
        # For SQLite, just show the file path
        if connection_string.startswith('sqlite:///'):
            return connection_string
        
        return "***"


class ServiceIssueLogger:
    """Specialized logger for service-related issues."""
    
    def __init__(self, logger_name: str = 'service_issues'):
        self.logger = structlog.get_logger(logger_name)
    
    def log_service_unavailable(self, service_name: str, error: str, 
                               fallback_available: bool = False, fallback_service: str = None):
        """Log service unavailability."""
        self.logger.warning(
            "Service unavailable",
            service_name=service_name,
            error=error,
            fallback_available=fallback_available,
            fallback_service=fallback_service,
            timestamp=datetime.now().isoformat()
        )
    
    def log_service_degradation(self, service_name: str, degradation_level: str, 
                               reason: str, impact: str = None):
        """Log service degradation."""
        self.logger.warning(
            "Service degradation detected",
            service_name=service_name,
            degradation_level=degradation_level,
            reason=reason,
            impact=impact,
            timestamp=datetime.now().isoformat()
        )
    
    def log_service_recovery(self, service_name: str, downtime_duration: str = None):
        """Log service recovery."""
        self.logger.info(
            "Service recovered",
            service_name=service_name,
            downtime_duration=downtime_duration,
            timestamp=datetime.now().isoformat()
        )
    
    def log_external_api_error(self, api_name: str, endpoint: str, status_code: int, 
                              error: str, retry_count: int = 0):
        """Log external API error."""
        self.logger.error(
            "External API error",
            api_name=api_name,
            endpoint=endpoint,
            status_code=status_code,
            error=error,
            retry_count=retry_count,
            timestamp=datetime.now().isoformat()
        )
    
    def log_configuration_error(self, service_name: str, config_key: str, 
                               error: str, resolution_hint: str = None):
        """Log configuration error."""
        self.logger.error(
            "Service configuration error",
            service_name=service_name,
            config_key=config_key,
            error=error,
            resolution_hint=resolution_hint,
            timestamp=datetime.now().isoformat()
        )


class RequestContextLogger:
    """Logger that includes request context information."""
    
    def __init__(self, logger_name: str = 'request_context'):
        self.logger = structlog.get_logger(logger_name)
    
    def log_with_context(self, level: str, message: str, **kwargs):
        """Log message with request context."""
        context = self._get_request_context()
        context.update(kwargs)
        
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message, **context)
    
    def _get_request_context(self) -> Dict[str, Any]:
        """Get current request context."""
        context = {
            'timestamp': datetime.now().isoformat()
        }
        
        if has_request_context():
            context.update({
                'method': request.method,
                'path': request.path,
                'remote_addr': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', 'Unknown'),
                'request_id': getattr(g, 'request_id', None)
            })
            
            # Add user information if available
            if hasattr(g, 'current_user') and g.current_user:
                context['user_id'] = getattr(g.current_user, 'id', None)
                context['user_email'] = getattr(g.current_user, 'email', None)
        
        return context


class ErrorTracker:
    """Track and analyze application errors."""
    
    def __init__(self, logger_name: str = 'error_tracker'):
        self.logger = structlog.get_logger(logger_name)
        self._error_counts: Dict[str, int] = {}
        self._error_patterns: List[Dict[str, Any]] = []
    
    def track_error(self, error: Exception, context: Dict[str, Any] = None):
        """Track an error occurrence."""
        error_type = type(error).__name__
        error_message = str(error)
        error_traceback = traceback.format_exc()
        
        # Categorize error
        error_category = self._categorize_error(error, context)
        error_severity = self._determine_error_severity(error, context)
        
        # Update error counts
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1
        
        # Create error record
        error_record = {
            'error_type': error_type,
            'error_message': error_message,
            'error_count': self._error_counts[error_type],
            'error_category': error_category,
            'error_severity': error_severity,
            'traceback': error_traceback,
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }
        
        # Add request context if available
        if has_request_context():
            error_record['request_context'] = {
                'method': request.method,
                'path': request.path,
                'remote_addr': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', 'Unknown')
            }
        
        # Log the error
        self.logger.error(
            "Error tracked",
            **error_record
        )
        
        # Store error pattern
        self._error_patterns.append(error_record)
        
        # Keep only recent error patterns (last 100)
        if len(self._error_patterns) > 100:
            self._error_patterns = self._error_patterns[-100:]
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary statistics."""
        return {
            'total_errors': sum(self._error_counts.values()),
            'unique_error_types': len(self._error_counts),
            'error_counts': self._error_counts.copy(),
            'recent_errors': len(self._error_patterns),
            'most_common_error': max(self._error_counts.items(), 
                                   key=lambda x: x[1]) if self._error_counts else None
        }
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent error patterns."""
        return self._error_patterns[-limit:] if self._error_patterns else []
    
    def _categorize_error(self, error: Exception, context: Dict[str, Any] = None) -> str:
        """Categorize error based on type and context."""
        error_type = type(error).__name__
        context = context or {}
        
        # Database errors
        if 'database' in error_type.lower() or 'sql' in error_type.lower():
            return 'database'
        
        # Authentication/Authorization errors
        if any(keyword in error_type.lower() for keyword in ['auth', 'permission', 'token', 'jwt']):
            return 'authentication'
        
        # External service errors
        if any(keyword in error_type.lower() for keyword in ['connection', 'timeout', 'http', 'api']):
            return 'external_service'
        
        # Configuration errors
        if any(keyword in error_type.lower() for keyword in ['config', 'environment', 'setting']):
            return 'configuration'
        
        # File system errors
        if any(keyword in error_type.lower() for keyword in ['file', 'directory', 'permission', 'io']):
            return 'filesystem'
        
        # Validation errors
        if 'validation' in error_type.lower() or 'invalid' in error_type.lower():
            return 'validation'
        
        # Check context for additional categorization
        if context.get('error_category'):
            return context['error_category']
        
        return 'general'
    
    def _determine_error_severity(self, error: Exception, context: Dict[str, Any] = None) -> str:
        """Determine error severity based on type and context."""
        error_type = type(error).__name__
        context = context or {}
        
        # Critical errors that affect core functionality
        critical_patterns = ['database', 'authentication', 'security', 'critical']
        if any(pattern in error_type.lower() for pattern in critical_patterns):
            return 'critical'
        
        # High severity errors that affect important features
        high_patterns = ['permission', 'authorization', 'configuration', 'external_service']
        if any(pattern in error_type.lower() for pattern in high_patterns):
            return 'high'
        
        # Medium severity errors that affect user experience
        medium_patterns = ['validation', 'file', 'timeout', 'connection']
        if any(pattern in error_type.lower() for pattern in medium_patterns):
            return 'medium'
        
        # Check context for severity override
        if context.get('error_severity'):
            return context['error_severity']
        
        return 'low'


class EnhancedLoggingManager:
    """Main enhanced logging manager."""
    
    def __init__(self, app=None):
        """Initialize enhanced logging manager."""
        self.app = app
        self.db_logger = DatabaseIssueLogger()
        self.service_logger = ServiceIssueLogger()
        self.context_logger = RequestContextLogger()
        self.error_tracker = ErrorTracker()
        
        # Configuration
        self._log_level = logging.INFO
        self._log_format = 'json'
        self._log_file_enabled = False
        self._log_file_path = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['enhanced_logging'] = self
        
        # Load configuration
        self._log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper())
        self._log_format = app.config.get('LOG_FORMAT', 'json')
        self._log_file_enabled = app.config.get('LOG_FILE_ENABLED', False)
        self._log_file_path = app.config.get('LOG_FILE_PATH', 'logs/application.log')
        
        # Configure structured logging
        self._configure_structured_logging()
        
        # Setup log file if enabled
        if self._log_file_enabled:
            self._setup_file_logging()
        
        # Register error handler
        app.errorhandler(Exception)(self._handle_application_error)
        
        # Register request hooks
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        
        logger = structlog.get_logger(__name__)
        logger.info("🔍 Enhanced logging manager initialized")
    
    def _configure_structured_logging(self):
        """Configure structured logging with appropriate processors."""
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
        ]
        
        if self._log_format == 'json':
            processors.append(JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())
        
        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=LoggerFactory(),
            wrapper_class=BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    def _setup_file_logging(self):
        """Setup file logging if enabled."""
        if not self._log_file_path:
            return
        
        # Create log directory if it doesn't exist
        log_dir = Path(self._log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup file handler
        file_handler = logging.FileHandler(self._log_file_path)
        file_handler.setLevel(self._log_level)
        
        if self._log_format == 'json':
            formatter = logging.Formatter('%(message)s')
        else:
            formatter = logging.Formatter(
                '%(asctime)s %(levelname)s %(name)s: %(message)s'
            )
        
        file_handler.setFormatter(formatter)
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        
        logger = structlog.get_logger(__name__)
        logger.info(f"File logging enabled: {self._log_file_path}")
    
    def _before_request(self):
        """Before request hook to setup request context."""
        # Only set if not already set by performance logger
        if not hasattr(g, 'request_start_time'):
            g.request_start_time = datetime.now()
        if not hasattr(g, 'request_id'):
            g.request_id = self._generate_request_id()
    
    def _after_request(self, response):
        """After request hook to log request completion."""
        if hasattr(g, 'request_start_time'):
            # Handle both datetime and float (time.time()) formats
            if isinstance(g.request_start_time, datetime):
                duration = (datetime.now() - g.request_start_time).total_seconds() * 1000
            else:
                # Assume it's a float from time.time()
                import time
                duration = (time.time() - g.request_start_time) * 1000
            
            self.context_logger.log_with_context(
                'info',
                'Request completed',
                status_code=response.status_code,
                duration_ms=duration,
                content_length=response.content_length
            )
        
        return response
    
    def _handle_application_error(self, error):
        """Handle application errors."""
        self.error_tracker.track_error(error)
        
        # Re-raise the error to let Flask handle it normally
        raise error
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        import uuid
        return f"req_{uuid.uuid4().hex[:12]}"
    
    def log_database_issue(self, issue_type: str, **kwargs):
        """Log database-related issue."""
        if issue_type == 'connection_attempt':
            self.db_logger.log_connection_attempt(**kwargs)
        elif issue_type == 'fallback_activation':
            self.db_logger.log_fallback_activation(**kwargs)
        elif issue_type == 'query_error':
            self.db_logger.log_query_error(**kwargs)
        elif issue_type == 'migration_issue':
            self.db_logger.log_migration_issue(**kwargs)
        elif issue_type == 'schema_issue':
            self.db_logger.log_schema_issue(**kwargs)
    
    def log_service_issue(self, issue_type: str, **kwargs):
        """Log service-related issue."""
        if issue_type == 'service_unavailable':
            self.service_logger.log_service_unavailable(**kwargs)
        elif issue_type == 'service_degradation':
            self.service_logger.log_service_degradation(**kwargs)
        elif issue_type == 'service_recovery':
            self.service_logger.log_service_recovery(**kwargs)
        elif issue_type == 'external_api_error':
            self.service_logger.log_external_api_error(**kwargs)
        elif issue_type == 'configuration_error':
            self.service_logger.log_configuration_error(**kwargs)
    
    def get_logging_stats(self) -> Dict[str, Any]:
        """Get logging statistics."""
        return {
            'error_summary': self.error_tracker.get_error_summary(),
            'recent_errors': self.error_tracker.get_recent_errors(5),
            'log_level': logging.getLevelName(self._log_level),
            'log_format': self._log_format,
            'file_logging_enabled': self._log_file_enabled,
            'log_file_path': self._log_file_path
        }


# Global instance
_enhanced_logging_manager = None


def get_enhanced_logging_manager(app=None) -> EnhancedLoggingManager:
    """Get or create enhanced logging manager instance."""
    global _enhanced_logging_manager
    
    if _enhanced_logging_manager is None:
        _enhanced_logging_manager = EnhancedLoggingManager(app)
    elif app is not None and _enhanced_logging_manager.app is None:
        _enhanced_logging_manager.init_app(app)
    
    return _enhanced_logging_manager


def init_enhanced_logging(app):
    """Initialize enhanced logging for Flask app."""
    manager = get_enhanced_logging_manager(app)
    return manager


# Convenience functions for direct logging
def log_database_connection_attempt(db_type: str, connection_string: str, success: bool, 
                                   response_time_ms: float = None, error: str = None):
    """Log database connection attempt."""
    manager = get_enhanced_logging_manager()
    manager.log_database_issue('connection_attempt', 
                              db_type=db_type, 
                              connection_string=connection_string,
                              success=success,
                              response_time_ms=response_time_ms,
                              error=error)


def log_service_unavailable(service_name: str, error: str, 
                           fallback_available: bool = False, fallback_service: str = None):
    """Log service unavailability."""
    manager = get_enhanced_logging_manager()
    manager.log_service_issue('service_unavailable',
                             service_name=service_name,
                             error=error,
                             fallback_available=fallback_available,
                             fallback_service=fallback_service)


def log_configuration_error(service_name: str, config_key: str, 
                           error: str, resolution_hint: str = None):
    """Log configuration error."""
    manager = get_enhanced_logging_manager()
    manager.log_service_issue('configuration_error',
                             service_name=service_name,
                             config_key=config_key,
                             error=error,
                             resolution_hint=resolution_hint)