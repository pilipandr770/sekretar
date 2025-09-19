"""
Configuration validation utility for AI Secretary application.
Enhanced system for comprehensive configuration validation, environment checking, and service health monitoring.
Addresses Requirements 6.1, 6.2, 6.3, and 6.4 for complete deployment preparation.
"""

import os
import sys
import logging
import re
import socket
import subprocess
import platform
from typing import Dict, List, Tuple, Any, Optional, Union
from urllib.parse import urlparse
import importlib.util
import sqlite3
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Validation severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ServiceStatus(Enum):
    """Service status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    NOT_CONFIGURED = "not_configured"
    UNKNOWN = "unknown"


@dataclass
class ValidationIssue:
    """Represents a validation issue."""
    message: str
    severity: ValidationSeverity
    category: str
    suggestion: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ServiceHealth:
    """Represents service health status."""
    name: str
    status: ServiceStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    fallback_available: bool = False
    fallback_message: Optional[str] = None
    last_check: datetime = field(default_factory=datetime.now)


@dataclass
class ValidationReport:
    """Comprehensive validation report."""
    valid: bool
    critical_issues: List[ValidationIssue] = field(default_factory=list)
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    info: List[ValidationIssue] = field(default_factory=list)
    services: Dict[str, ServiceHealth] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_issue(self, message: str, severity: ValidationSeverity, category: str, 
                  suggestion: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Add a validation issue."""
        issue = ValidationIssue(
            message=message,
            severity=severity,
            category=category,
            suggestion=suggestion,
            details=details or {}
        )
        
        if severity == ValidationSeverity.CRITICAL:
            self.critical_issues.append(issue)
            self.valid = False
        elif severity == ValidationSeverity.ERROR:
            self.errors.append(issue)
            self.valid = False
        elif severity == ValidationSeverity.WARNING:
            self.warnings.append(issue)
        else:
            self.info.append(issue)
        
        if suggestion:
            self.recommendations.append(suggestion)
    
    def add_service(self, service: ServiceHealth):
        """Add service health information."""
        self.services[service.name] = service
    
    def get_summary(self) -> Dict[str, Any]:
        """Get validation summary."""
        return {
            'valid': self.valid,
            'total_issues': len(self.critical_issues) + len(self.errors) + len(self.warnings) + len(self.info),
            'critical_count': len(self.critical_issues),
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'info_count': len(self.info),
            'services_healthy': sum(1 for s in self.services.values() if s.status == ServiceStatus.HEALTHY),
            'services_total': len(self.services),
            'timestamp': self.timestamp.isoformat()
        }


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ServiceDependencyError(Exception):
    """Raised when service dependency check fails."""
    pass


class ConfigValidator:
    """
    Enhanced configuration validator for comprehensive settings validation.
    Validates critical variables, URL formats, keys, ports, and setting compatibility.
    """
    
    def __init__(self, config_file: str = ".env"):
        self.config_file = config_file
        self.report = ValidationReport(valid=True)
        
        # Critical environment variables that must be present
        self.critical_variables = {
            'SECRET_KEY': {
                'description': 'Application secret key for session security',
                'validator': self._validate_secret_key,
                'required': True
            },
            'JWT_SECRET_KEY': {
                'description': 'JWT token signing key',
                'validator': self._validate_jwt_secret,
                'required': True
            },
            'DATABASE_URL': {
                'description': 'Database connection string',
                'validator': self._validate_database_url,
                'required': True
            },
            'FLASK_APP': {
                'description': 'Flask application entry point',
                'validator': self._validate_flask_app,
                'required': True
            }
        }
        
        # Optional but important variables
        self.optional_variables = {
            'OPENAI_API_KEY': {
                'description': 'OpenAI API key for AI features',
                'validator': self._validate_openai_key,
                'fallback': 'AI features will be disabled'
            },
            'REDIS_URL': {
                'description': 'Redis connection for caching and queues',
                'validator': self._validate_redis_url,
                'fallback': 'Simple cache will be used'
            },
            'GOOGLE_CLIENT_ID': {
                'description': 'Google OAuth client ID',
                'validator': self._validate_google_oauth,
                'fallback': 'Google OAuth will be disabled'
            },
            'STRIPE_SECRET_KEY': {
                'description': 'Stripe secret key for payments',
                'validator': self._validate_stripe_key,
                'fallback': 'Payment features will be disabled'
            }
        }
        
        # Port validation ranges
        self.valid_port_ranges = {
            'development': (3000, 9999),
            'production': (80, 65535)
        }
        
    def validate_all(self) -> ValidationReport:
        """
        Run comprehensive configuration validation.
        
        Returns:
            ValidationReport with complete validation results
        """
        logger.info("Starting comprehensive configuration validation")
        
        # Reset validation state
        self.report = ValidationReport(valid=True)
        
        try:
            # Load environment variables
            env_vars = self._load_env_file()
            self.report.environment['loaded_variables'] = len(env_vars)
            
            # Run validation checks
            self._validate_critical_variables(env_vars)
            self._validate_optional_variables(env_vars)
            self._validate_security_settings(env_vars)
            self._validate_url_formats(env_vars)
            self._validate_port_configurations(env_vars)
            self._validate_key_formats(env_vars)
            self._validate_setting_compatibility(env_vars)
            
            # Store environment info
            self.report.environment.update({
                'config_file': self.config_file,
                'variables_count': len(env_vars),
                'flask_env': env_vars.get('FLASK_ENV', 'development'),
                'debug_mode': env_vars.get('FLASK_DEBUG', 'false').lower() in ['true', '1', 'yes']
            })
            
            logger.info(f"Configuration validation completed: {self.report.get_summary()}")
            
        except Exception as e:
            self.report.add_issue(
                f"Configuration validation failed with exception: {str(e)}",
                ValidationSeverity.CRITICAL,
                "system",
                "Check configuration file accessibility and format"
            )
            logger.error(f"Configuration validation failed: {e}", exc_info=True)
        
        return self.report
    
    def _load_env_file(self) -> Dict[str, str]:
        """Load environment variables from .env file."""
        env_vars = {}
        
        if not os.path.exists(self.config_file):
            self.report.add_issue(
                f"Configuration file '{self.config_file}' not found",
                ValidationSeverity.CRITICAL,
                "file_system",
                f"Create {self.config_file} file with required environment variables"
            )
            return env_vars
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        try:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
                        except ValueError:
                            self.report.add_issue(
                                f"Invalid line format at line {line_num}: {line}",
                                ValidationSeverity.WARNING,
                                "format",
                                "Fix environment variable format (KEY=value)"
                            )
        except Exception as e:
            self.report.add_issue(
                f"Failed to read configuration file: {e}",
                ValidationSeverity.CRITICAL,
                "file_system",
                "Check file permissions and encoding"
            )
        
        return env_vars
    
    def _validate_critical_variables(self, env_vars: Dict[str, str]) -> None:
        """Validate critical environment variables."""
        for var_name, config in self.critical_variables.items():
            value = env_vars.get(var_name, '').strip()
            
            if not value:
                self.report.add_issue(
                    f"Critical variable '{var_name}' is missing",
                    ValidationSeverity.CRITICAL,
                    "configuration",
                    f"Set {var_name}={config['description']}"
                )
            else:
                # Run specific validator
                if 'validator' in config:
                    config['validator'](var_name, value, env_vars)
    
    def _validate_optional_variables(self, env_vars: Dict[str, str]) -> None:
        """Validate optional environment variables."""
        for var_name, config in self.optional_variables.items():
            value = env_vars.get(var_name, '').strip()
            
            if not value or value.startswith('your-'):
                self.report.add_issue(
                    f"Optional variable '{var_name}' not configured",
                    ValidationSeverity.INFO,
                    "configuration",
                    f"Configure {var_name} to enable {config['description']}",
                    {'fallback': config.get('fallback', 'Feature will be disabled')}
                )
            else:
                # Run specific validator
                if 'validator' in config:
                    config['validator'](var_name, value, env_vars)
    
    def _validate_secret_key(self, name: str, value: str, env_vars: Dict[str, str]) -> None:
        """Validate SECRET_KEY format and strength."""
        if value in ['your-secret-key-here', 'dev-secret-key', 'change-me']:
            self.report.add_issue(
                f"{name} is using default/example value - SECURITY RISK",
                ValidationSeverity.CRITICAL,
                "security",
                f"Generate a strong random {name} (at least 32 characters)"
            )
        elif len(value) < 32:
            self.report.add_issue(
                f"{name} should be at least 32 characters long",
                ValidationSeverity.WARNING,
                "security",
                f"Use a longer {name} for better security"
            )
        elif not re.search(r'[A-Za-z]', value) or not re.search(r'[0-9]', value):
            self.report.add_issue(
                f"{name} should contain both letters and numbers",
                ValidationSeverity.WARNING,
                "security",
                f"Use a more complex {name} with mixed characters"
            )
    
    def _validate_jwt_secret(self, name: str, value: str, env_vars: Dict[str, str]) -> None:
        """Validate JWT_SECRET_KEY format and strength."""
        self._validate_secret_key(name, value, env_vars)  # Same validation as SECRET_KEY
    
    def _validate_flask_app(self, name: str, value: str, env_vars: Dict[str, str]) -> None:
        """Validate FLASK_APP setting."""
        if not value.endswith('.py') and ':' not in value:
            self.report.add_issue(
                f"{name} should point to a Python file or module:function",
                ValidationSeverity.WARNING,
                "configuration",
                "Use format like 'run.py' or 'app:create_app'"
            )
    
    def _validate_database_url(self, name: str, value: str, env_vars: Dict[str, str]) -> None:
        """Validate DATABASE_URL format and accessibility."""
        try:
            parsed = urlparse(value)
            
            if not parsed.scheme:
                self.report.add_issue(
                    f"{name} missing database scheme",
                    ValidationSeverity.ERROR,
                    "database",
                    "Use format like 'sqlite:///db.sqlite' or 'postgresql://user:pass@host/db'"
                )
                return
            
            # Check for common PostgreSQL URL issue
            if value.startswith('postgres://'):
                self.report.add_issue(
                    f"{name} uses deprecated 'postgres://' scheme",
                    ValidationSeverity.WARNING,
                    "database",
                    "Change 'postgres://' to 'postgresql://' for SQLAlchemy compatibility"
                )
            
            # Validate SQLite specific settings
            if parsed.scheme == 'sqlite':
                self._validate_sqlite_config(value, env_vars)
            
            # Validate PostgreSQL specific settings
            elif parsed.scheme in ['postgresql', 'postgres']:
                self._validate_postgresql_config(parsed, env_vars)
            
        except Exception as e:
            self.report.add_issue(
                f"Invalid {name} format: {e}",
                ValidationSeverity.ERROR,
                "database",
                "Check database URL format and accessibility"
            )
    
    def _validate_openai_key(self, name: str, value: str, env_vars: Dict[str, str]) -> None:
        """Validate OpenAI API key format."""
        if not value.startswith('sk-'):
            self.report.add_issue(
                f"{name} format appears invalid (should start with 'sk-')",
                ValidationSeverity.WARNING,
                "external_service",
                "Verify OpenAI API key format"
            )
    
    def _validate_redis_url(self, name: str, value: str, env_vars: Dict[str, str]) -> None:
        """Validate Redis URL format."""
        try:
            parsed = urlparse(value)
            if parsed.scheme not in ['redis', 'rediss']:
                self.report.add_issue(
                    f"{name} scheme '{parsed.scheme}' may not be supported",
                    ValidationSeverity.WARNING,
                    "cache",
                    "Use 'redis://' or 'rediss://' scheme"
                )
        except Exception as e:
            self.report.add_issue(
                f"Invalid {name} format: {e}",
                ValidationSeverity.WARNING,
                "cache",
                "Check Redis URL format"
            )
    
    def _validate_google_oauth(self, name: str, value: str, env_vars: Dict[str, str]) -> None:
        """Validate Google OAuth configuration."""
        if name == 'GOOGLE_CLIENT_ID':
            google_secret = env_vars.get('GOOGLE_CLIENT_SECRET', '').strip()
            if not google_secret:
                self.report.add_issue(
                    "GOOGLE_CLIENT_ID set but GOOGLE_CLIENT_SECRET missing",
                    ValidationSeverity.WARNING,
                    "oauth",
                    "Set GOOGLE_CLIENT_SECRET for complete OAuth configuration"
                )
    
    def _validate_stripe_key(self, name: str, value: str, env_vars: Dict[str, str]) -> None:
        """Validate Stripe key format."""
        if not value.startswith(('sk_test_', 'sk_live_')):
            self.report.add_issue(
                f"{name} format appears invalid (should start with 'sk_test_' or 'sk_live_')",
                ValidationSeverity.WARNING,
                "payment",
                "Verify Stripe secret key format"
            )
    
    def _validate_url_formats(self, env_vars: Dict[str, str]) -> None:
        """Validate URL formats for all URL-based configuration variables."""
        url_variables = {
            'DATABASE_URL': 'Database connection URL',
            'REDIS_URL': 'Redis connection URL',
            'WEBHOOK_URL': 'Webhook callback URL',
            'FRONTEND_URL': 'Frontend application URL'
        }
        
        for var_name, description in url_variables.items():
            value = env_vars.get(var_name, '').strip()
            if value and not value.startswith('your-'):
                self._validate_url_format(var_name, value, description)
    
    def _validate_url_format(self, name: str, url: str, description: str) -> None:
        """Validate individual URL format."""
        try:
            parsed = urlparse(url)
            
            # Check for required components
            if not parsed.scheme:
                self.report.add_issue(
                    f"{name} missing URL scheme",
                    ValidationSeverity.ERROR,
                    "url_format",
                    f"Add scheme to {name} (e.g., http://, https://, postgresql://)"
                )
            
            # Validate common schemes
            valid_schemes = {
                'DATABASE_URL': ['sqlite', 'postgresql', 'postgres', 'mysql'],
                'REDIS_URL': ['redis', 'rediss'],
                'WEBHOOK_URL': ['http', 'https'],
                'FRONTEND_URL': ['http', 'https']
            }
            
            if name in valid_schemes and parsed.scheme not in valid_schemes[name]:
                self.report.add_issue(
                    f"{name} has invalid scheme '{parsed.scheme}'",
                    ValidationSeverity.WARNING,
                    "url_format",
                    f"Use one of: {', '.join(valid_schemes[name])}"
                )
            
            # Check for localhost in production
            flask_env = env_vars.get('FLASK_ENV', 'development').lower()
            if flask_env == 'production' and parsed.hostname in ['localhost', '127.0.0.1']:
                self.report.add_issue(
                    f"{name} uses localhost in production environment",
                    ValidationSeverity.WARNING,
                    "production",
                    f"Use production hostname for {name}"
                )
                
        except Exception as e:
            self.report.add_issue(
                f"Invalid URL format in {name}: {e}",
                ValidationSeverity.ERROR,
                "url_format",
                f"Fix URL format for {name}"
            )
    
    def _validate_port_configurations(self, env_vars: Dict[str, str]) -> None:
        """Validate port configurations."""
        port_variables = {
            'PORT': 'Application port',
            'REDIS_PORT': 'Redis port',
            'DB_PORT': 'Database port'
        }
        
        flask_env = env_vars.get('FLASK_ENV', 'development').lower()
        port_range = self.valid_port_ranges.get(flask_env, self.valid_port_ranges['development'])
        
        for var_name, description in port_variables.items():
            value = env_vars.get(var_name, '').strip()
            if value:
                self._validate_port(var_name, value, description, port_range)
        
        # Extract ports from URLs
        self._validate_url_ports(env_vars, port_range)
    
    def _validate_port(self, name: str, port_str: str, description: str, port_range: Tuple[int, int]) -> None:
        """Validate individual port configuration."""
        try:
            port = int(port_str)
            
            if not (1 <= port <= 65535):
                self.report.add_issue(
                    f"{name} port {port} is out of valid range (1-65535)",
                    ValidationSeverity.ERROR,
                    "port",
                    f"Use a valid port number for {name}"
                )
            elif port < port_range[0] or port > port_range[1]:
                self.report.add_issue(
                    f"{name} port {port} is outside recommended range ({port_range[0]}-{port_range[1]})",
                    ValidationSeverity.WARNING,
                    "port",
                    f"Consider using a port in range {port_range[0]}-{port_range[1]}"
                )
            elif port < 1024:
                self.report.add_issue(
                    f"{name} port {port} requires root privileges",
                    ValidationSeverity.WARNING,
                    "port",
                    f"Use port > 1024 for {name} to avoid privilege requirements"
                )
                
        except ValueError:
            self.report.add_issue(
                f"{name} has invalid port format: {port_str}",
                ValidationSeverity.ERROR,
                "port",
                f"Use numeric port for {name}"
            )
    
    def _validate_url_ports(self, env_vars: Dict[str, str], port_range: Tuple[int, int]) -> None:
        """Validate ports extracted from URLs."""
        url_vars = ['DATABASE_URL', 'REDIS_URL']
        
        for var_name in url_vars:
            value = env_vars.get(var_name, '').strip()
            if value:
                try:
                    parsed = urlparse(value)
                    if parsed.port:
                        self._validate_port(f"{var_name}_PORT", str(parsed.port), f"Port from {var_name}", port_range)
                except Exception:
                    pass  # URL validation will catch format issues
    
    def _validate_key_formats(self, env_vars: Dict[str, str]) -> None:
        """Validate format of various keys and tokens."""
        key_patterns = {
            'OPENAI_API_KEY': {
                'pattern': r'^sk-[A-Za-z0-9]{48}$',
                'description': 'OpenAI API key format'
            },
            'STRIPE_SECRET_KEY': {
                'pattern': r'^sk_(test_|live_)[A-Za-z0-9]{24,}$',
                'description': 'Stripe secret key format'
            },
            'GOOGLE_CLIENT_ID': {
                'pattern': r'^[0-9]+-[A-Za-z0-9_]+\.apps\.googleusercontent\.com$',
                'description': 'Google OAuth client ID format'
            }
        }
        
        for var_name, config in key_patterns.items():
            value = env_vars.get(var_name, '').strip()
            if value and not value.startswith('your-'):
                if not re.match(config['pattern'], value):
                    self.report.add_issue(
                        f"{var_name} format doesn't match expected pattern",
                        ValidationSeverity.WARNING,
                        "key_format",
                        f"Verify {config['description']}"
                    )
    
    def _validate_setting_compatibility(self, env_vars: Dict[str, str]) -> None:
        """Validate compatibility between different settings."""
        flask_env = env_vars.get('FLASK_ENV', 'development').lower()
        flask_debug = env_vars.get('FLASK_DEBUG', 'false').lower()
        
        # Production environment checks
        if flask_env == 'production':
            self._validate_production_settings(env_vars, flask_debug)
        
        # Cache configuration compatibility
        self._validate_cache_compatibility(env_vars)
        
        # OAuth configuration compatibility
        self._validate_oauth_compatibility(env_vars)
        
        # Database and cache compatibility
        self._validate_service_compatibility(env_vars)
    
    def _validate_production_settings(self, env_vars: Dict[str, str], flask_debug: str) -> None:
        """Validate production-specific settings."""
        if flask_debug in ['true', '1', 'yes']:
            self.report.add_issue(
                "FLASK_DEBUG is enabled in production - SECURITY RISK",
                ValidationSeverity.CRITICAL,
                "security",
                "Set FLASK_DEBUG=false in production"
            )
        
        # Check for secure cookie settings
        jwt_cookie_secure = env_vars.get('JWT_COOKIE_SECURE', 'false').lower()
        if jwt_cookie_secure != 'true':
            self.report.add_issue(
                "JWT_COOKIE_SECURE should be 'true' in production for HTTPS",
                ValidationSeverity.WARNING,
                "security",
                "Set JWT_COOKIE_SECURE=true for production HTTPS"
            )
        
        # Check for HTTPS enforcement
        force_https = env_vars.get('FORCE_HTTPS', 'false').lower()
        if force_https != 'true':
            self.report.add_issue(
                "FORCE_HTTPS not enabled in production",
                ValidationSeverity.WARNING,
                "security",
                "Set FORCE_HTTPS=true for production security"
            )
    
    def _validate_cache_compatibility(self, env_vars: Dict[str, str]) -> None:
        """Validate cache configuration compatibility."""
        cache_type = env_vars.get('CACHE_TYPE', 'simple').lower()
        redis_url = env_vars.get('REDIS_URL', '').strip()
        
        if cache_type == 'redis' and not redis_url:
            self.report.add_issue(
                "CACHE_TYPE is 'redis' but REDIS_URL is not configured",
                ValidationSeverity.WARNING,
                "cache",
                "Set REDIS_URL or change CACHE_TYPE to 'simple'",
                {'fallback': 'Will use simple cache instead'}
            )
    
    def _validate_oauth_compatibility(self, env_vars: Dict[str, str]) -> None:
        """Validate OAuth configuration compatibility."""
        google_client_id = env_vars.get('GOOGLE_CLIENT_ID', '').strip()
        google_client_secret = env_vars.get('GOOGLE_CLIENT_SECRET', '').strip()
        
        if google_client_id and not google_client_secret:
            self.report.add_issue(
                "GOOGLE_CLIENT_ID configured but GOOGLE_CLIENT_SECRET missing",
                ValidationSeverity.WARNING,
                "oauth",
                "Set GOOGLE_CLIENT_SECRET for complete OAuth setup"
            )
        elif google_client_secret and not google_client_id:
            self.report.add_issue(
                "GOOGLE_CLIENT_SECRET configured but GOOGLE_CLIENT_ID missing",
                ValidationSeverity.WARNING,
                "oauth",
                "Set GOOGLE_CLIENT_ID for complete OAuth setup"
            )
    
    def _validate_service_compatibility(self, env_vars: Dict[str, str]) -> None:
        """Validate compatibility between different services."""
        # Celery and Redis compatibility
        celery_broker = env_vars.get('CELERY_BROKER_URL', '').strip()
        redis_url = env_vars.get('REDIS_URL', '').strip()
        
        if celery_broker and not redis_url:
            self.report.add_issue(
                "Celery configured but Redis URL not available",
                ValidationSeverity.WARNING,
                "task_queue",
                "Configure REDIS_URL for Celery task queue",
                {'fallback': 'Celery will be disabled'}
            )
    
    def _validate_sqlite_config(self, database_url: str, env_vars: Dict[str, str]) -> None:
        """Validate SQLite-specific configuration."""
        db_schema = env_vars.get('DB_SCHEMA', '').strip()
        if db_schema:
            self.report.add_issue(
                "DB_SCHEMA is set but SQLite doesn't support schemas",
                ValidationSeverity.WARNING,
                "database",
                "Remove DB_SCHEMA when using SQLite"
            )
        
        # Check SQLite file accessibility
        db_path = database_url.replace('sqlite:///', '')
        if db_path and not db_path.startswith(':memory:'):
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    self.report.add_issue(
                        f"Created database directory: {db_dir}",
                        ValidationSeverity.INFO,
                        "database",
                        None
                    )
                except Exception as e:
                    self.report.add_issue(
                        f"Cannot create database directory '{db_dir}': {e}",
                        ValidationSeverity.ERROR,
                        "database",
                        f"Ensure write permissions for database directory"
                    )
    
    def _validate_postgresql_config(self, parsed_url, env_vars: Dict[str, str]) -> None:
        """Validate PostgreSQL-specific configuration."""
        if not all([parsed_url.hostname, parsed_url.username, parsed_url.password]):
            self.report.add_issue(
                "PostgreSQL URL missing hostname, username, or password",
                ValidationSeverity.WARNING,
                "database",
                "Ensure complete PostgreSQL connection string"
            )
        
        if parsed_url.port and not (1 <= parsed_url.port <= 65535):
            self.report.add_issue(
                f"Invalid PostgreSQL port: {parsed_url.port}",
                ValidationSeverity.ERROR,
                "database",
                "Use valid PostgreSQL port (typically 5432)"
            )

    def _validate_required_variables(self, env_vars: Dict[str, str]) -> None:
        """Validate required environment variables."""
        required_vars = {
            'SECRET_KEY': 'Application secret key for session security',
            'JWT_SECRET_KEY': 'JWT token signing key',
            'DATABASE_URL': 'Database connection string',
            'FLASK_APP': 'Flask application entry point'
        }
        
        for var, description in required_vars.items():
            value = env_vars.get(var, '').strip()
            if not value:
                self.critical_errors.append(f"Required variable '{var}' is missing ({description})")
            elif value in ['your-secret-key-here', 'dev-secret-key', 'jwt-secret-key']:
                self.critical_errors.append(f"Variable '{var}' is using default/example value - SECURITY RISK")
    
    def _validate_security_settings(self, env_vars: Dict[str, str]) -> None:
        """Validate security-related configuration."""
        flask_env = env_vars.get('FLASK_ENV', '').lower()
        flask_debug = env_vars.get('FLASK_DEBUG', '').lower()
        
        # Check for production security issues
        if flask_env == 'production':
            if flask_debug in ['true', '1', 'yes']:
                self.errors.append("FLASK_DEBUG is enabled in production - SECURITY RISK")
            
            jwt_cookie_secure = env_vars.get('JWT_COOKIE_SECURE', '').lower()
            if jwt_cookie_secure != 'true':
                self.warnings.append("JWT_COOKIE_SECURE should be 'true' in production for HTTPS")
        
        # Check secret key strength
        secret_key = env_vars.get('SECRET_KEY', '')
        if secret_key and len(secret_key) < 32:
            self.warnings.append("SECRET_KEY should be at least 32 characters long")
        
        jwt_secret = env_vars.get('JWT_SECRET_KEY', '')
        if jwt_secret and len(jwt_secret) < 32:
            self.warnings.append("JWT_SECRET_KEY should be at least 32 characters long")
    
    def _validate_database_configuration(self, env_vars: Dict[str, str]) -> None:
        """Validate database configuration."""
        database_url = env_vars.get('DATABASE_URL', '')
        
        if not database_url:
            self.critical_errors.append("DATABASE_URL is not configured")
            return
        
        try:
            parsed = urlparse(database_url)
            
            # Fix common PostgreSQL URL format issue
            if database_url.startswith('postgres://'):
                self.warnings.append("DATABASE_URL uses 'postgres://' - should be 'postgresql://' for SQLAlchemy")
                # Auto-suggest fix
                fixed_url = database_url.replace('postgres://', 'postgresql://', 1)
                logger.info(f"Suggested fix: DATABASE_URL={fixed_url}")
            
            # Check SQLite specific configuration
            if parsed.scheme == 'sqlite':
                db_schema = env_vars.get('DB_SCHEMA', '').strip()
                if db_schema:
                    self.warnings.append("DB_SCHEMA is set but SQLite doesn't support schemas")
                
                # Check if SQLite file path is accessible
                db_path = database_url.replace('sqlite:///', '')
                if db_path and not db_path.startswith(':memory:'):
                    db_dir = os.path.dirname(db_path)
                    if db_dir and not os.path.exists(db_dir):
                        try:
                            os.makedirs(db_dir, exist_ok=True)
                            logger.info(f"Created database directory: {db_dir}")
                        except Exception as e:
                            self.errors.append(f"Cannot create database directory '{db_dir}': {e}")
            
            # Check PostgreSQL specific configuration
            elif parsed.scheme in ['postgresql', 'postgres']:
                if not all([parsed.hostname, parsed.username, parsed.password]):
                    self.warnings.append("PostgreSQL URL missing hostname, username, or password")
                
                # Test basic connection format
                if parsed.port and not (1 <= parsed.port <= 65535):
                    self.errors.append(f"Invalid PostgreSQL port: {parsed.port}")
        
        except Exception as e:
            self.errors.append(f"Invalid DATABASE_URL format: {e}")
    
    def _validate_cache_configuration(self, env_vars: Dict[str, str]) -> None:
        """Validate cache configuration."""
        redis_url = env_vars.get('REDIS_URL', '').strip()
        cache_type = env_vars.get('CACHE_TYPE', 'simple').lower()
        
        if cache_type == 'redis' and not redis_url:
            self.warnings.append("CACHE_TYPE is 'redis' but REDIS_URL is not set - will fallback to simple cache")
        
        # Check Celery configuration
        celery_broker = env_vars.get('CELERY_BROKER_URL', '').strip()
        if celery_broker and not redis_url:
            self.warnings.append("Celery configured but Redis URL not available - Celery will be disabled")
        
        # Validate Redis URL format if provided
        if redis_url:
            try:
                parsed = urlparse(redis_url)
                if parsed.scheme not in ['redis', 'rediss']:
                    self.warnings.append(f"Redis URL scheme '{parsed.scheme}' may not be supported")
            except Exception as e:
                self.warnings.append(f"Invalid Redis URL format: {e}")
    
    def _validate_external_services(self, env_vars: Dict[str, str]) -> None:
        """Validate external service configuration."""
        # OpenAI API
        openai_key = env_vars.get('OPENAI_API_KEY', '').strip()
        if not openai_key or openai_key.startswith('your-'):
            self.warnings.append("OPENAI_API_KEY not configured - AI features will be disabled")
        elif not openai_key.startswith('sk-'):
            self.warnings.append("OPENAI_API_KEY format appears invalid (should start with 'sk-')")
        
        # Google OAuth
        google_client_id = env_vars.get('GOOGLE_CLIENT_ID', '').strip()
        google_client_secret = env_vars.get('GOOGLE_CLIENT_SECRET', '').strip()
        
        if google_client_id and google_client_id.startswith('your-'):
            self.warnings.append("Google OAuth not properly configured - OAuth features will be disabled")
        
        if google_client_id and not google_client_secret:
            self.warnings.append("GOOGLE_CLIENT_ID set but GOOGLE_CLIENT_SECRET missing")
        
        # Stripe
        stripe_secret = env_vars.get('STRIPE_SECRET_KEY', '').strip()
        if stripe_secret and not stripe_secret.startswith(('sk_test_', 'sk_live_')):
            self.warnings.append("STRIPE_SECRET_KEY format appears invalid")
    
    def _check_service_dependencies(self, env_vars: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """Check service dependencies."""
        services = {}
        
        # Check Python and required packages
        services['python'] = self._check_python()
        services['packages'] = self._check_python_packages()
        services['database'] = self._check_database_connectivity(env_vars)
        services['redis'] = self._check_redis_connectivity(env_vars)
        
        return services
    
    def _check_python(self) -> Dict[str, Any]:
        """Check Python installation."""
        try:
            version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            
            if sys.version_info < (3, 8):
                return {
                    'status': 'unhealthy',
                    'version': version,
                    'error': 'Python 3.8+ required'
                }
            
            return {
                'status': 'healthy',
                'version': version,
                'executable': sys.executable
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_python_packages(self) -> Dict[str, Any]:
        """Check required Python packages."""
        required_packages = [
            'flask', 'sqlalchemy', 'flask_sqlalchemy', 'flask_migrate',
            'flask_jwt_extended', 'flask_babel', 'redis', 'celery'
        ]
        
        missing_packages = []
        installed_packages = {}
        
        for package in required_packages:
            try:
                spec = importlib.util.find_spec(package)
                if spec is None:
                    missing_packages.append(package)
                else:
                    # Try to get version if available
                    try:
                        module = importlib.import_module(package)
                        version = getattr(module, '__version__', 'unknown')
                        installed_packages[package] = version
                    except:
                        installed_packages[package] = 'installed'
            except Exception:
                missing_packages.append(package)
        
        if missing_packages:
            return {
                'status': 'unhealthy',
                'missing': missing_packages,
                'installed': installed_packages,
                'error': f"Missing packages: {', '.join(missing_packages)}"
            }
        
        return {
            'status': 'healthy',
            'installed': installed_packages
        }
    
    def _check_database_connectivity(self, env_vars: Dict[str, str]) -> Dict[str, Any]:
        """Check database connectivity."""
        database_url = env_vars.get('DATABASE_URL', '')
        
        if not database_url:
            return {
                'status': 'unhealthy',
                'error': 'DATABASE_URL not configured'
            }
        
        try:
            parsed = urlparse(database_url)
            
            if parsed.scheme == 'sqlite':
                return self._test_sqlite_connection(database_url)
            elif parsed.scheme in ['postgresql', 'postgres']:
                return self._test_postgresql_connection(database_url)
            else:
                return {
                    'status': 'unknown',
                    'type': parsed.scheme,
                    'note': 'Database type not specifically tested'
                }
        
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': f"Database connection test failed: {e}"
            }
    
    def _test_sqlite_connection(self, database_url: str) -> Dict[str, Any]:
        """Test SQLite database connection."""
        try:
            db_path = database_url.replace('sqlite:///', '')
            
            if db_path == ':memory:':
                return {
                    'status': 'healthy',
                    'type': 'SQLite',
                    'location': 'in-memory'
                }
            
            # Test if we can create/access the database file
            db_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else '.'
            
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            
            # Test connection
            with sqlite3.connect(db_path, timeout=5) as conn:
                conn.execute('SELECT 1').fetchone()
            
            return {
                'status': 'healthy',
                'type': 'SQLite',
                'location': db_path,
                'size': os.path.getsize(db_path) if os.path.exists(db_path) else 0
            }
        
        except Exception as e:
            return {
                'status': 'unhealthy',
                'type': 'SQLite',
                'error': str(e)
            }
    
    def _test_postgresql_connection(self, database_url: str) -> Dict[str, Any]:
        """Test PostgreSQL database connection."""
        try:
            # Try to import psycopg2 or asyncpg
            try:
                import psycopg2
                from psycopg2 import sql
                
                # Test connection
                conn = psycopg2.connect(database_url, connect_timeout=10)
                with conn.cursor() as cur:
                    cur.execute('SELECT 1')
                    cur.fetchone()
                conn.close()
                
                return {
                    'status': 'healthy',
                    'type': 'PostgreSQL',
                    'driver': 'psycopg2'
                }
            
            except ImportError:
                # psycopg2 not available, try with SQLAlchemy
                try:
                    from sqlalchemy import create_engine, text
                    
                    engine = create_engine(database_url, connect_args={'connect_timeout': 10})
                    with engine.connect() as conn:
                        conn.execute(text('SELECT 1'))
                    
                    return {
                        'status': 'healthy',
                        'type': 'PostgreSQL',
                        'driver': 'SQLAlchemy'
                    }
                
                except ImportError:
                    return {
                        'status': 'degraded',
                        'type': 'PostgreSQL',
                        'error': 'No PostgreSQL driver available (psycopg2 or SQLAlchemy)',
                        'note': 'Will test during application startup'
                    }
        
        except Exception as e:
            return {
                'status': 'unhealthy',
                'type': 'PostgreSQL',
                'error': str(e)
            }
    
    def _check_redis_connectivity(self, env_vars: Dict[str, str]) -> Dict[str, Any]:
        """Check Redis connectivity."""
        redis_url = env_vars.get('REDIS_URL', '').strip()
        
        if not redis_url:
            return {
                'status': 'not_configured',
                'note': 'Redis not configured - using simple cache fallback'
            }
        
        try:
            import redis
            
            # Test Redis connection
            r = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
            r.ping()
            
            # Get Redis info
            info = r.info()
            
            return {
                'status': 'healthy',
                'version': info.get('redis_version', 'unknown'),
                'memory_used': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0)
            }
        
        except ImportError:
            return {
                'status': 'degraded',
                'error': 'Redis package not installed',
                'fallback': 'simple cache'
            }
        
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'fallback': 'simple cache'
            }


def validate_configuration(config_file: str = ".env") -> Dict[str, Any]:
    """Convenience function to validate configuration."""
    validator = ConfigValidator(config_file)
    return validator.validate_all()


if __name__ == "__main__":
    # CLI usage
    import json
    
    config_file = sys.argv[1] if len(sys.argv) > 1 else ".env"
    result = validate_configuration(config_file)
    
    print(json.dumps(result, indent=2))
    
    if result['critical'] or not result['valid']:
        sys.exit(1)