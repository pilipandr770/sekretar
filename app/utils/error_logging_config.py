"""
Error Logging Configuration

This module provides configuration for error logging, rate limiting,
and structured logging with environment-based settings.
"""
import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class LogLevel(Enum):
    """Log levels for configuration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorHandlingMode(Enum):
    """Error handling modes."""
    DEVELOPMENT = "development"  # Verbose logging, detailed errors
    PRODUCTION = "production"    # Rate limited, user-friendly errors
    TESTING = "testing"         # Minimal logging, fast execution


@dataclass
class ErrorLoggingConfig:
    """Configuration for error logging and rate limiting."""
    
    # Log levels
    default_log_level: LogLevel = LogLevel.INFO
    database_log_level: LogLevel = LogLevel.WARNING
    context_log_level: LogLevel = LogLevel.WARNING
    external_service_log_level: LogLevel = LogLevel.ERROR
    
    # Rate limiting settings
    enable_rate_limiting: bool = True
    max_errors_per_minute: int = 5
    max_errors_per_hour: int = 50
    summary_interval_minutes: int = 15
    cleanup_interval_minutes: int = 60
    max_stored_errors: int = 1000
    
    # Error handling mode
    error_handling_mode: ErrorHandlingMode = ErrorHandlingMode.PRODUCTION
    
    # Structured logging
    enable_structured_logging: bool = True
    include_technical_details: bool = False
    include_traceback: bool = False
    log_format: str = "json"  # "json" or "text"
    
    # File logging
    enable_file_logging: bool = False
    log_file_path: str = "logs/application.log"
    max_log_file_size_mb: int = 100
    log_file_backup_count: int = 5
    
    # Error notification
    enable_error_notifications: bool = False
    notification_webhook_url: Optional[str] = None
    notification_severity_threshold: str = "high"
    
    # Context information
    include_request_context: bool = True
    include_environment_info: bool = True
    mask_sensitive_data: bool = True
    
    # Performance settings
    async_logging: bool = False
    log_buffer_size: int = 1000
    log_flush_interval_seconds: int = 5
    
    # Development settings
    debug_mode: bool = False
    verbose_errors: bool = False
    log_sql_queries: bool = False


class ErrorLoggingConfigManager:
    """Manages error logging configuration from environment variables and Flask config."""
    
    def __init__(self, app=None):
        """Initialize configuration manager."""
        self.app = app
        self._config: Optional[ErrorLoggingConfig] = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['error_logging_config'] = self
        
        # Load configuration
        self._config = self._load_configuration()
        
        # Apply configuration to logging system
        self._apply_logging_configuration()
    
    def get_config(self) -> ErrorLoggingConfig:
        """Get current configuration."""
        if self._config is None:
            self._config = self._load_configuration()
        return self._config
    
    def _load_configuration(self) -> ErrorLoggingConfig:
        """Load configuration from environment and Flask config."""
        config = ErrorLoggingConfig()
        
        # Determine error handling mode
        flask_env = os.environ.get('FLASK_ENV', 'production').lower()
        testing = os.environ.get('TESTING', 'false').lower() == 'true'
        
        if testing:
            config.error_handling_mode = ErrorHandlingMode.TESTING
        elif flask_env in ['development', 'dev']:
            config.error_handling_mode = ErrorHandlingMode.DEVELOPMENT
        else:
            config.error_handling_mode = ErrorHandlingMode.PRODUCTION
        
        # Load log levels
        config.default_log_level = self._get_log_level('LOG_LEVEL', config.default_log_level)
        config.database_log_level = self._get_log_level('DATABASE_LOG_LEVEL', config.database_log_level)
        config.context_log_level = self._get_log_level('CONTEXT_LOG_LEVEL', config.context_log_level)
        config.external_service_log_level = self._get_log_level('EXTERNAL_SERVICE_LOG_LEVEL', config.external_service_log_level)
        
        # Load rate limiting settings
        config.enable_rate_limiting = self._get_bool('ENABLE_ERROR_RATE_LIMITING', config.enable_rate_limiting)
        config.max_errors_per_minute = self._get_int('MAX_ERRORS_PER_MINUTE', config.max_errors_per_minute)
        config.max_errors_per_hour = self._get_int('MAX_ERRORS_PER_HOUR', config.max_errors_per_hour)
        config.summary_interval_minutes = self._get_int('ERROR_SUMMARY_INTERVAL_MINUTES', config.summary_interval_minutes)
        config.cleanup_interval_minutes = self._get_int('ERROR_CLEANUP_INTERVAL_MINUTES', config.cleanup_interval_minutes)
        config.max_stored_errors = self._get_int('MAX_STORED_ERRORS', config.max_stored_errors)
        
        # Load structured logging settings
        config.enable_structured_logging = self._get_bool('ENABLE_STRUCTURED_LOGGING', config.enable_structured_logging)
        config.log_format = os.environ.get('LOG_FORMAT', config.log_format).lower()
        
        # Load file logging settings
        config.enable_file_logging = self._get_bool('ENABLE_FILE_LOGGING', config.enable_file_logging)
        config.log_file_path = os.environ.get('LOG_FILE_PATH', config.log_file_path)
        config.max_log_file_size_mb = self._get_int('MAX_LOG_FILE_SIZE_MB', config.max_log_file_size_mb)
        config.log_file_backup_count = self._get_int('LOG_FILE_BACKUP_COUNT', config.log_file_backup_count)
        
        # Load error notification settings
        config.enable_error_notifications = self._get_bool('ENABLE_ERROR_NOTIFICATIONS', config.enable_error_notifications)
        config.notification_webhook_url = os.environ.get('ERROR_NOTIFICATION_WEBHOOK_URL')
        config.notification_severity_threshold = os.environ.get('ERROR_NOTIFICATION_SEVERITY_THRESHOLD', config.notification_severity_threshold).lower()
        
        # Load context settings
        config.include_request_context = self._get_bool('INCLUDE_REQUEST_CONTEXT', config.include_request_context)
        config.include_environment_info = self._get_bool('INCLUDE_ENVIRONMENT_INFO', config.include_environment_info)
        config.mask_sensitive_data = self._get_bool('MASK_SENSITIVE_DATA', config.mask_sensitive_data)
        
        # Load performance settings
        config.async_logging = self._get_bool('ASYNC_LOGGING', config.async_logging)
        config.log_buffer_size = self._get_int('LOG_BUFFER_SIZE', config.log_buffer_size)
        config.log_flush_interval_seconds = self._get_int('LOG_FLUSH_INTERVAL_SECONDS', config.log_flush_interval_seconds)
        
        # Apply mode-specific overrides
        self._apply_mode_overrides(config)
        
        # Load Flask app config overrides
        if self.app:
            self._apply_flask_config_overrides(config)
        
        return config
    
    def _apply_mode_overrides(self, config: ErrorLoggingConfig):
        """Apply mode-specific configuration overrides."""
        if config.error_handling_mode == ErrorHandlingMode.DEVELOPMENT:
            config.debug_mode = True
            config.verbose_errors = True
            config.include_technical_details = True
            config.include_traceback = True
            config.enable_rate_limiting = False
            config.default_log_level = LogLevel.DEBUG
            config.log_sql_queries = True
            
        elif config.error_handling_mode == ErrorHandlingMode.TESTING:
            config.enable_rate_limiting = False
            config.enable_file_logging = False
            config.enable_error_notifications = False
            config.default_log_level = LogLevel.WARNING
            config.include_technical_details = False
            config.include_traceback = False
            
        elif config.error_handling_mode == ErrorHandlingMode.PRODUCTION:
            config.debug_mode = False
            config.verbose_errors = False
            config.include_technical_details = False
            config.include_traceback = False
            config.enable_rate_limiting = True
            config.mask_sensitive_data = True
    
    def _apply_flask_config_overrides(self, config: ErrorLoggingConfig):
        """Apply Flask app configuration overrides."""
        flask_config = self.app.config
        
        # Override with Flask config values
        if 'ERROR_LOGGING_CONFIG' in flask_config:
            error_config = flask_config['ERROR_LOGGING_CONFIG']
            
            for key, value in error_config.items():
                if hasattr(config, key.lower()):
                    setattr(config, key.lower(), value)
        
        # Apply debug mode from Flask
        if flask_config.get('DEBUG'):
            config.debug_mode = True
            config.verbose_errors = True
            config.include_technical_details = True
            config.include_traceback = True
    
    def _apply_logging_configuration(self):
        """Apply configuration to the logging system."""
        config = self.get_config()
        
        # Set root logger level
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config.default_log_level.value))
        
        # Configure specific loggers
        database_logger = logging.getLogger('app.utils.smart_connection_manager')
        database_logger.setLevel(getattr(logging, config.database_log_level.value))
        
        context_logger = logging.getLogger('app.utils.application_context_manager')
        context_logger.setLevel(getattr(logging, config.context_log_level.value))
        
        # Configure file logging if enabled
        if config.enable_file_logging:
            self._setup_file_logging(config)
    
    def _setup_file_logging(self, config: ErrorLoggingConfig):
        """Setup file logging with rotation."""
        import logging.handlers
        from pathlib import Path
        
        # Create log directory
        log_path = Path(config.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            config.log_file_path,
            maxBytes=config.max_log_file_size_mb * 1024 * 1024,
            backupCount=config.log_file_backup_count
        )
        
        # Set formatter
        if config.log_format == 'json':
            formatter = logging.Formatter('%(message)s')
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, config.default_log_level.value))
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
    
    def _get_log_level(self, env_var: str, default: LogLevel) -> LogLevel:
        """Get log level from environment variable."""
        value = os.environ.get(env_var, default.value).upper()
        try:
            return LogLevel(value)
        except ValueError:
            return default
    
    def _get_bool(self, env_var: str, default: bool) -> bool:
        """Get boolean value from environment variable."""
        value = os.environ.get(env_var, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def _get_int(self, env_var: str, default: int) -> int:
        """Get integer value from environment variable."""
        try:
            return int(os.environ.get(env_var, str(default)))
        except ValueError:
            return default
    
    def get_rate_limiter_config(self) -> Dict[str, Any]:
        """Get configuration for error rate limiter."""
        config = self.get_config()
        
        if not config.enable_rate_limiting:
            # Return config that effectively disables rate limiting
            return {
                'max_errors_per_minute': 1000000,
                'max_errors_per_hour': 1000000,
                'summary_interval_minutes': 1440,  # 24 hours
                'cleanup_interval_minutes': 1440,
                'max_stored_errors': 10
            }
        
        return {
            'max_errors_per_minute': config.max_errors_per_minute,
            'max_errors_per_hour': config.max_errors_per_hour,
            'summary_interval_minutes': config.summary_interval_minutes,
            'cleanup_interval_minutes': config.cleanup_interval_minutes,
            'max_stored_errors': config.max_stored_errors
        }
    
    def get_structured_logger_config(self) -> Dict[str, Any]:
        """Get configuration for structured logger."""
        config = self.get_config()
        
        return {
            'enable_structured_logging': config.enable_structured_logging,
            'include_technical_details': config.include_technical_details,
            'include_traceback': config.include_traceback,
            'log_format': config.log_format,
            'include_request_context': config.include_request_context,
            'include_environment_info': config.include_environment_info,
            'mask_sensitive_data': config.mask_sensitive_data
        }
    
    def should_log_technical_details(self) -> bool:
        """Check if technical details should be logged."""
        config = self.get_config()
        return config.include_technical_details or config.debug_mode
    
    def should_include_traceback(self) -> bool:
        """Check if traceback should be included."""
        config = self.get_config()
        return config.include_traceback or config.debug_mode
    
    def get_notification_config(self) -> Dict[str, Any]:
        """Get error notification configuration."""
        config = self.get_config()
        
        return {
            'enable_error_notifications': config.enable_error_notifications,
            'webhook_url': config.notification_webhook_url,
            'severity_threshold': config.notification_severity_threshold
        }


# Global instance
_config_manager: Optional[ErrorLoggingConfigManager] = None


def get_error_logging_config_manager(app=None) -> ErrorLoggingConfigManager:
    """Get or create global error logging configuration manager."""
    global _config_manager
    
    if _config_manager is None:
        _config_manager = ErrorLoggingConfigManager(app)
    elif app is not None and _config_manager.app is None:
        _config_manager.init_app(app)
    
    return _config_manager


def get_error_logging_config(app=None) -> ErrorLoggingConfig:
    """Get current error logging configuration."""
    manager = get_error_logging_config_manager(app)
    return manager.get_config()


def init_error_logging_config(app) -> ErrorLoggingConfigManager:
    """Initialize error logging configuration for Flask app."""
    manager = get_error_logging_config_manager(app)
    return manager