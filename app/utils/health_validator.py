"""
Enhanced Health Validation System

This module provides comprehensive health validation functionality for external services,
database connectivity, schema validation, and diagnostic reporting with fallback modes.
Addresses Requirements 6.3 and 6.4 for service health monitoring and fallback handling.
"""
import logging
import time
import requests
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Union
from enum import Enum
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.exc import SQLAlchemyError
from urllib.parse import urlparse

from .database_init_logger import get_database_init_logger, LogLevel, LogCategory
from .config_validator import ServiceStatus, ServiceHealth

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ValidationSeverity(Enum):
    """Validation issue severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ServiceType(Enum):
    """Types of services that can be validated."""
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL_API = "external_api"
    OAUTH = "oauth"
    PAYMENT = "payment"
    MESSAGING = "messaging"
    STORAGE = "storage"
    MONITORING = "monitoring"


@dataclass
class FallbackConfig:
    """Configuration for service fallback behavior."""
    enabled: bool = True
    fallback_service: Optional[str] = None
    fallback_message: Optional[str] = None
    degraded_functionality: List[str] = field(default_factory=list)
    recovery_instructions: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of database validation process."""
    valid: bool
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    severity: ValidationSeverity = ValidationSeverity.INFO
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_issue(self, issue: str, severity: ValidationSeverity = ValidationSeverity.ERROR):
        """Add a validation issue."""
        self.issues.append(issue)
        if severity.value > self.severity.value:
            self.severity = severity
        logger.log(
            logging.ERROR if severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] else logging.WARNING,
            f"Validation issue ({severity.value}): {issue}"
        )
    
    def add_suggestion(self, suggestion: str):
        """Add a suggestion for fixing issues."""
        self.suggestions.append(suggestion)
        logger.info(f"💡 Suggestion: {suggestion}")


@dataclass
class HealthCheckResult:
    """Result of health check process."""
    status: HealthStatus
    checks_passed: int = 0
    checks_failed: int = 0
    checks_total: int = 0
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_issue(self, issue: str, severity: HealthStatus = HealthStatus.CRITICAL):
        """Add a health issue."""
        if severity == HealthStatus.CRITICAL:
            self.issues.append(issue)
            self.checks_failed += 1
        else:
            self.warnings.append(issue)
        
        self.checks_total += 1
        
        # Update overall status
        if severity == HealthStatus.CRITICAL and self.status != HealthStatus.CRITICAL:
            self.status = HealthStatus.CRITICAL
        elif severity == HealthStatus.WARNING and self.status == HealthStatus.HEALTHY:
            self.status = HealthStatus.WARNING
    
    def add_success(self, check_name: str):
        """Add a successful check."""
        self.checks_passed += 1
        self.checks_total += 1
        logger.info(f"✅ Health check passed: {check_name}")


class HealthValidator:
    """
    Enhanced health validation system for external services and database.
    
    Provides comprehensive health checks including connectivity testing,
    schema validation, external service monitoring, and fallback handling.
    """
    
    def __init__(self, app: Flask, db: SQLAlchemy):
        self.app = app
        self.db = db
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize logging system
        log_level = LogLevel.DEBUG if app.debug else LogLevel.INFO
        self.init_logger = get_database_init_logger("health_validator", log_level)
        
        # Health check configuration
        self.connection_timeout = app.config.get('DATABASE_CONNECTION_TIMEOUT', 30)
        self.query_timeout = app.config.get('DATABASE_QUERY_TIMEOUT', 10)
        self.max_retries = app.config.get('DATABASE_MAX_RETRIES', 3)
        self.service_timeout = app.config.get('SERVICE_HEALTH_TIMEOUT', 10)
        
        # Service configurations with fallback options
        self.service_configs = {
            'openai': {
                'type': ServiceType.EXTERNAL_API,
                'url_key': 'OPENAI_API_KEY',
                'test_endpoint': 'https://api.openai.com/v1/models',
                'fallback': FallbackConfig(
                    enabled=True,
                    fallback_message="AI features disabled - using rule-based responses",
                    degraded_functionality=["AI chat responses", "Smart categorization", "Content generation"],
                    recovery_instructions=["Set valid OPENAI_API_KEY", "Check API quota and billing"]
                )
            },
            'redis': {
                'type': ServiceType.CACHE,
                'url_key': 'REDIS_URL',
                'fallback': FallbackConfig(
                    enabled=True,
                    fallback_service="simple_cache",
                    fallback_message="Using simple in-memory cache instead of Redis",
                    degraded_functionality=["Distributed caching", "Session sharing", "Task queues"],
                    recovery_instructions=["Configure REDIS_URL", "Start Redis server", "Check network connectivity"]
                )
            },
            'google_oauth': {
                'type': ServiceType.OAUTH,
                'url_key': 'GOOGLE_CLIENT_ID',
                'test_endpoint': 'https://www.googleapis.com/oauth2/v1/tokeninfo',
                'fallback': FallbackConfig(
                    enabled=True,
                    fallback_message="Google OAuth disabled - using email/password authentication only",
                    degraded_functionality=["Google sign-in", "Calendar integration", "Gmail integration"],
                    recovery_instructions=["Configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET", "Enable Google OAuth API"]
                )
            },
            'stripe': {
                'type': ServiceType.PAYMENT,
                'url_key': 'STRIPE_SECRET_KEY',
                'test_endpoint': 'https://api.stripe.com/v1/account',
                'fallback': FallbackConfig(
                    enabled=True,
                    fallback_message="Payment processing disabled - subscription features unavailable",
                    degraded_functionality=["Payment processing", "Subscription management", "Billing"],
                    recovery_instructions=["Configure STRIPE_SECRET_KEY", "Verify Stripe account status"]
                )
            },
            'telegram': {
                'type': ServiceType.MESSAGING,
                'url_key': 'TELEGRAM_BOT_TOKEN',
                'fallback': FallbackConfig(
                    enabled=True,
                    fallback_message="Telegram integration disabled - using email notifications only",
                    degraded_functionality=["Telegram notifications", "Bot interactions"],
                    recovery_instructions=["Configure TELEGRAM_BOT_TOKEN", "Verify bot permissions"]
                )
            },
            'signal': {
                'type': ServiceType.MESSAGING,
                'url_key': 'SIGNAL_CLI_PATH',
                'fallback': FallbackConfig(
                    enabled=True,
                    fallback_message="Signal integration disabled - using email notifications only",
                    degraded_functionality=["Signal notifications", "Secure messaging"],
                    recovery_instructions=["Install signal-cli", "Configure SIGNAL_CLI_PATH"]
                )
            }
        }
    
    def validate_connectivity(self) -> bool:
        """
        Validate database connectivity.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            self.init_logger.info(LogCategory.VALIDATION, "Testing database connectivity...")
            
            # Test basic connection
            with self.db.engine.connect() as conn:
                result = conn.execute(text('SELECT 1'))
                row = result.fetchone()
                
                if row and row[0] == 1:
                    self.init_logger.info(LogCategory.VALIDATION, "✅ Database connectivity test passed")
                    return True
                else:
                    self.init_logger.error(LogCategory.VALIDATION, "❌ Database connectivity test failed: Invalid response")
                    return False
        
        except Exception as e:
            self.init_logger.error(
                LogCategory.VALIDATION,
                f"❌ Database connectivity test failed: {str(e)}",
                error=e
            )
            return False
    
    def validate_schema_integrity(self) -> ValidationResult:
        """
        Validate database schema integrity.
        
        Returns:
            ValidationResult with schema validation details
        """
        result = ValidationResult(valid=True)
        
        try:
            self.init_logger.info(LogCategory.VALIDATION, "Validating database schema integrity...")
            
            # Get database inspector
            inspector = inspect(self.db.engine)
            
            # Check if tables exist
            existing_tables = inspector.get_table_names()
            
            # Define expected core tables
            expected_tables = [
                'tenants', 'users', 'roles', 'user_roles',
                'channels', 'threads', 'inbox_messages',
                'contacts', 'leads', 'tasks', 'notes',
                'knowledge_sources', 'documents', 'chunks', 'embeddings',
                'plans', 'subscriptions', 'usage_events', 'invoices',
                'counterparties', 'kyb_alerts', 'audit_logs'
            ]
            
            # Check for missing tables
            missing_tables = [table for table in expected_tables if table not in existing_tables]
            if missing_tables:
                result.valid = False
                for table in missing_tables:
                    result.add_issue(f"Missing table: {table}", ValidationSeverity.CRITICAL)
                    result.add_suggestion(f"Create table '{table}' using database migrations")
            
            # Check table structures for critical tables
            critical_tables = ['tenants', 'users', 'roles']
            for table_name in critical_tables:
                if table_name in existing_tables:
                    self._validate_table_structure(inspector, table_name, result)
            
            # Check for orphaned tables
            orphaned_tables = [table for table in existing_tables if table not in expected_tables and not table.startswith('alembic')]
            if orphaned_tables:
                for table in orphaned_tables:
                    result.add_issue(f"Orphaned table found: {table}", ValidationSeverity.WARNING)
                    result.add_suggestion(f"Review table '{table}' - may be leftover from old migrations")
            
            result.details['existing_tables'] = existing_tables
            result.details['expected_tables'] = expected_tables
            result.details['missing_tables'] = missing_tables
            result.details['orphaned_tables'] = orphaned_tables
            
            if result.valid:
                self.init_logger.info(LogCategory.VALIDATION, "✅ Schema integrity validation passed")
            else:
                self.init_logger.error(LogCategory.VALIDATION, f"❌ Schema integrity validation failed: {len(result.issues)} issues found")
        
        except Exception as e:
            result.valid = False
            result.add_issue(f"Schema validation failed with exception: {str(e)}", ValidationSeverity.CRITICAL)
            self.init_logger.error(
                LogCategory.VALIDATION,
                f"❌ Schema validation failed with exception: {str(e)}",
                error=e
            )
        
        return result
    
    def validate_data_integrity(self) -> ValidationResult:
        """
        Validate database data integrity.
        
        Returns:
            ValidationResult with data validation details
        """
        result = ValidationResult(valid=True)
        
        try:
            self.init_logger.info(LogCategory.VALIDATION, "Validating database data integrity...")
            
            # Check for essential system data
            self._validate_system_tenant(result)
            self._validate_admin_user(result)
            self._validate_system_roles(result)
            
            # Check for data consistency
            self._validate_data_consistency(result)
            
            if result.valid:
                self.init_logger.info(LogCategory.VALIDATION, "✅ Data integrity validation passed")
            else:
                self.init_logger.error(LogCategory.VALIDATION, f"❌ Data integrity validation failed: {len(result.issues)} issues found")
        
        except Exception as e:
            result.valid = False
            result.add_issue(f"Data validation failed with exception: {str(e)}", ValidationSeverity.CRITICAL)
            self.init_logger.error(
                LogCategory.VALIDATION,
                f"❌ Data validation failed with exception: {str(e)}",
                error=e
            )
        
        return result
    
    def generate_health_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive health report.
        
        Returns:
            Dictionary with health report details
        """
        start_time = time.time()
        
        self.init_logger.info(LogCategory.VALIDATION, "Generating comprehensive health report...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'database_type': self._get_database_type(),
            'connectivity': {
                'status': 'unknown',
                'details': {}
            },
            'schema': {
                'status': 'unknown',
                'details': {}
            },
            'data': {
                'status': 'unknown',
                'details': {}
            },
            'overall_status': HealthStatus.UNKNOWN.value,
            'recommendations': [],
            'duration': 0.0
        }
        
        try:
            # Test connectivity
            connectivity_ok = self.validate_connectivity()
            report['connectivity']['status'] = 'healthy' if connectivity_ok else 'critical'
            
            if connectivity_ok:
                # Validate schema
                schema_result = self.validate_schema_integrity()
                report['schema']['status'] = 'healthy' if schema_result.valid else 'critical'
                report['schema']['details'] = {
                    'issues': schema_result.issues,
                    'suggestions': schema_result.suggestions,
                    'table_info': schema_result.details
                }
                
                # Validate data
                data_result = self.validate_data_integrity()
                report['data']['status'] = 'healthy' if data_result.valid else 'critical'
                report['data']['details'] = {
                    'issues': data_result.issues,
                    'suggestions': data_result.suggestions,
                    'data_info': data_result.details
                }
                
                # Determine overall status
                if connectivity_ok and schema_result.valid and data_result.valid:
                    report['overall_status'] = HealthStatus.HEALTHY.value
                elif not connectivity_ok:
                    report['overall_status'] = HealthStatus.CRITICAL.value
                    report['recommendations'].append("Fix database connectivity issues before proceeding")
                elif not schema_result.valid:
                    report['overall_status'] = HealthStatus.CRITICAL.value
                    report['recommendations'].extend(schema_result.suggestions)
                elif not data_result.valid:
                    report['overall_status'] = HealthStatus.WARNING.value
                    report['recommendations'].extend(data_result.suggestions)
            else:
                report['overall_status'] = HealthStatus.CRITICAL.value
                report['recommendations'].append("Database connectivity must be restored")
        
        except Exception as e:
            report['overall_status'] = HealthStatus.CRITICAL.value
            report['error'] = str(e)
            report['recommendations'].append("Investigate health check system errors")
            self.init_logger.error(
                LogCategory.VALIDATION,
                f"❌ Health report generation failed: {str(e)}",
                error=e
            )
        
        finally:
            report['duration'] = time.time() - start_time
            self.init_logger.info(
                LogCategory.VALIDATION,
                f"Health report generated in {report['duration']:.2f}s - Status: {report['overall_status']}"
            )
        
        return report
    
    def validate_external_services(self) -> Dict[str, ServiceHealth]:
        """
        Validate external service connectivity and configuration.
        
        Returns:
            Dictionary mapping service names to their health status
        """
        self.init_logger.info(LogCategory.VALIDATION, "Validating external services...")
        
        services = {}
        
        for service_name, config in self.service_configs.items():
            try:
                service_health = self._check_service_health(service_name, config)
                services[service_name] = service_health
                
                # Log service status
                if service_health.status == ServiceStatus.HEALTHY:
                    self.init_logger.info(
                        LogCategory.VALIDATION,
                        f"✅ Service '{service_name}' is healthy: {service_health.message}"
                    )
                elif service_health.status == ServiceStatus.NOT_CONFIGURED:
                    self.init_logger.info(
                        LogCategory.VALIDATION,
                        f"ℹ️ Service '{service_name}' not configured: {service_health.message}"
                    )
                else:
                    self.init_logger.warning(
                        LogCategory.VALIDATION,
                        f"⚠️ Service '{service_name}' unhealthy: {service_health.message}"
                    )
                    
            except Exception as e:
                services[service_name] = ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.UNKNOWN,
                    message=f"Health check failed: {str(e)}",
                    details={'error': str(e)}
                )
                self.init_logger.error(
                    LogCategory.VALIDATION,
                    f"❌ Service '{service_name}' health check failed: {str(e)}",
                    error=e
                )
        
        return services
    
    def _check_service_health(self, service_name: str, config: Dict[str, Any]) -> ServiceHealth:
        """Check health of a specific service."""
        url_key = config.get('url_key')
        service_type = config.get('type')
        test_endpoint = config.get('test_endpoint')
        fallback_config = config.get('fallback')
        
        # Get configuration value
        config_value = self.app.config.get(url_key, '').strip()
        
        if not config_value or config_value.startswith('your-'):
            return ServiceHealth(
                name=service_name,
                status=ServiceStatus.NOT_CONFIGURED,
                message=f"{service_name} not configured",
                fallback_available=fallback_config.enabled if fallback_config else False,
                fallback_message=fallback_config.fallback_message if fallback_config else None,
                details={
                    'config_key': url_key,
                    'fallback_enabled': fallback_config.enabled if fallback_config else False
                }
            )
        
        # Perform service-specific health check
        if service_type == ServiceType.EXTERNAL_API and test_endpoint:
            return self._check_api_service(service_name, config_value, test_endpoint, fallback_config)
        elif service_type == ServiceType.CACHE:
            return self._check_cache_service(service_name, config_value, fallback_config)
        elif service_type == ServiceType.OAUTH:
            return self._check_oauth_service(service_name, config_value, fallback_config)
        elif service_type == ServiceType.MESSAGING:
            return self._check_messaging_service(service_name, config_value, fallback_config)
        else:
            return self._check_generic_service(service_name, config_value, fallback_config)
    
    def _check_api_service(self, service_name: str, api_key: str, endpoint: str, 
                          fallback_config: FallbackConfig) -> ServiceHealth:
        """Check external API service health."""
        try:
            headers = {}
            
            # Set appropriate headers based on service
            if service_name == 'openai':
                headers['Authorization'] = f'Bearer {api_key}'
            elif service_name == 'stripe':
                headers['Authorization'] = f'Bearer {api_key}'
            
            response = requests.get(
                endpoint,
                headers=headers,
                timeout=self.service_timeout
            )
            
            if response.status_code == 200:
                return ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.HEALTHY,
                    message=f"{service_name} API is accessible and responding",
                    details={
                        'response_time': response.elapsed.total_seconds(),
                        'status_code': response.status_code
                    }
                )
            elif response.status_code == 401:
                return ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.UNHEALTHY,
                    message=f"{service_name} API authentication failed",
                    fallback_available=fallback_config.enabled,
                    fallback_message=fallback_config.fallback_message,
                    details={
                        'status_code': response.status_code,
                        'error': 'Authentication failed - check API key'
                    }
                )
            else:
                return ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.DEGRADED,
                    message=f"{service_name} API returned status {response.status_code}",
                    fallback_available=fallback_config.enabled,
                    fallback_message=fallback_config.fallback_message,
                    details={'status_code': response.status_code}
                )
                
        except requests.exceptions.Timeout:
            return ServiceHealth(
                name=service_name,
                status=ServiceStatus.UNHEALTHY,
                message=f"{service_name} API timeout",
                fallback_available=fallback_config.enabled,
                fallback_message=fallback_config.fallback_message,
                details={'error': 'Request timeout'}
            )
        except requests.exceptions.ConnectionError:
            return ServiceHealth(
                name=service_name,
                status=ServiceStatus.UNHEALTHY,
                message=f"{service_name} API connection failed",
                fallback_available=fallback_config.enabled,
                fallback_message=fallback_config.fallback_message,
                details={'error': 'Connection failed'}
            )
        except Exception as e:
            return ServiceHealth(
                name=service_name,
                status=ServiceStatus.UNKNOWN,
                message=f"{service_name} API check failed: {str(e)}",
                fallback_available=fallback_config.enabled,
                fallback_message=fallback_config.fallback_message,
                details={'error': str(e)}
            )
    
    def _check_cache_service(self, service_name: str, redis_url: str, 
                           fallback_config: FallbackConfig) -> ServiceHealth:
        """Check Redis cache service health."""
        try:
            import redis
            
            r = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
            
            # Test basic operations
            test_key = f"health_check_{int(time.time())}"
            r.set(test_key, "test_value", ex=60)  # Expire in 60 seconds
            value = r.get(test_key)
            r.delete(test_key)
            
            if value == b"test_value":
                info = r.info()
                return ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.HEALTHY,
                    message="Redis is healthy and responding",
                    details={
                        'version': info.get('redis_version', 'unknown'),
                        'memory_used': info.get('used_memory_human', 'unknown'),
                        'connected_clients': info.get('connected_clients', 0)
                    }
                )
            else:
                return ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.DEGRADED,
                    message="Redis responding but operations failing",
                    fallback_available=fallback_config.enabled,
                    fallback_message=fallback_config.fallback_message
                )
                
        except ImportError:
            return ServiceHealth(
                name=service_name,
                status=ServiceStatus.DEGRADED,
                message="Redis package not installed",
                fallback_available=fallback_config.enabled,
                fallback_message=fallback_config.fallback_message,
                details={'error': 'redis package not installed'}
            )
        except Exception as e:
            return ServiceHealth(
                name=service_name,
                status=ServiceStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                fallback_available=fallback_config.enabled,
                fallback_message=fallback_config.fallback_message,
                details={'error': str(e)}
            )
    
    def _check_oauth_service(self, service_name: str, client_id: str, 
                           fallback_config: FallbackConfig) -> ServiceHealth:
        """Check OAuth service configuration."""
        # For OAuth, we mainly check configuration completeness
        if service_name == 'google_oauth':
            client_secret = self.app.config.get('GOOGLE_CLIENT_SECRET', '').strip()
            
            if not client_secret:
                return ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.DEGRADED,
                    message="Google OAuth partially configured - missing client secret",
                    fallback_available=fallback_config.enabled,
                    fallback_message=fallback_config.fallback_message,
                    details={'missing': 'GOOGLE_CLIENT_SECRET'}
                )
            
            # Basic format validation
            if not client_id.endswith('.apps.googleusercontent.com'):
                return ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.DEGRADED,
                    message="Google OAuth client ID format appears invalid",
                    fallback_available=fallback_config.enabled,
                    fallback_message=fallback_config.fallback_message,
                    details={'warning': 'Invalid client ID format'}
                )
            
            return ServiceHealth(
                name=service_name,
                status=ServiceStatus.HEALTHY,
                message="Google OAuth properly configured",
                details={'client_id_format': 'valid'}
            )
        
        return self._check_generic_service(service_name, client_id, fallback_config)
    
    def _check_messaging_service(self, service_name: str, config_value: str, 
                               fallback_config: FallbackConfig) -> ServiceHealth:
        """Check messaging service health."""
        if service_name == 'telegram':
            # For Telegram, check if bot token format is valid
            if not config_value.count(':') == 1:
                return ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.DEGRADED,
                    message="Telegram bot token format appears invalid",
                    fallback_available=fallback_config.enabled,
                    fallback_message=fallback_config.fallback_message,
                    details={'error': 'Invalid token format'}
                )
            
            # Could test with Telegram API, but for now just validate format
            return ServiceHealth(
                name=service_name,
                status=ServiceStatus.HEALTHY,
                message="Telegram bot token configured",
                details={'token_format': 'valid'}
            )
        
        elif service_name == 'signal':
            # For Signal, check if CLI path exists
            import os
            if os.path.exists(config_value):
                return ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.HEALTHY,
                    message="Signal CLI path exists",
                    details={'cli_path': config_value}
                )
            else:
                return ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.UNHEALTHY,
                    message="Signal CLI path not found",
                    fallback_available=fallback_config.enabled,
                    fallback_message=fallback_config.fallback_message,
                    details={'error': f'Path not found: {config_value}'}
                )
        
        return self._check_generic_service(service_name, config_value, fallback_config)
    
    def _check_generic_service(self, service_name: str, config_value: str, 
                             fallback_config: FallbackConfig) -> ServiceHealth:
        """Generic service health check."""
        return ServiceHealth(
            name=service_name,
            status=ServiceStatus.HEALTHY,
            message=f"{service_name} is configured",
            details={'configured': True}
        )
    
    def get_service_status_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all service statuses.
        
        Returns:
            Dictionary with service status summary
        """
        services = self.validate_external_services()
        
        summary = {
            'total_services': len(services),
            'healthy': 0,
            'degraded': 0,
            'unhealthy': 0,
            'not_configured': 0,
            'unknown': 0,
            'fallback_available': 0,
            'services': {},
            'recommendations': [],
            'last_check': datetime.now().isoformat()
        }
        
        for service_name, health in services.items():
            summary['services'][service_name] = {
                'status': health.status.value,
                'message': health.message,
                'fallback_available': health.fallback_available
            }
            
            # Count statuses
            if health.status == ServiceStatus.HEALTHY:
                summary['healthy'] += 1
            elif health.status == ServiceStatus.DEGRADED:
                summary['degraded'] += 1
            elif health.status == ServiceStatus.UNHEALTHY:
                summary['unhealthy'] += 1
            elif health.status == ServiceStatus.NOT_CONFIGURED:
                summary['not_configured'] += 1
            else:
                summary['unknown'] += 1
            
            if health.fallback_available:
                summary['fallback_available'] += 1
        
        # Generate recommendations
        if summary['unhealthy'] > 0:
            summary['recommendations'].append("Fix unhealthy services for full functionality")
        if summary['not_configured'] > 0:
            summary['recommendations'].append("Configure additional services to enable more features")
        if summary['degraded'] > 0:
            summary['recommendations'].append("Address degraded services to improve reliability")
        
        return summary

    def run_comprehensive_health_check(self) -> HealthCheckResult:
        """
        Run comprehensive health check.
        
        Returns:
            HealthCheckResult with complete health assessment
        """
        start_time = time.time()
        result = HealthCheckResult(status=HealthStatus.HEALTHY)
        
        self.init_logger.info(LogCategory.VALIDATION, "Running comprehensive health check...")
        
        try:
            # Check 1: Database connectivity
            if self.validate_connectivity():
                result.add_success("Database connectivity")
            else:
                result.add_issue("Database connectivity failed", HealthStatus.CRITICAL)
            
            # Check 2: Schema integrity
            schema_result = self.validate_schema_integrity()
            if schema_result.valid:
                result.add_success("Schema integrity")
            else:
                result.add_issue(f"Schema integrity failed: {len(schema_result.issues)} issues", HealthStatus.CRITICAL)
                result.details['schema_issues'] = schema_result.issues
            
            # Check 3: Data integrity
            data_result = self.validate_data_integrity()
            if data_result.valid:
                result.add_success("Data integrity")
            else:
                result.add_issue(f"Data integrity failed: {len(data_result.issues)} issues", HealthStatus.WARNING)
                result.details['data_issues'] = data_result.issues
            
            # Check 4: External services
            services = self.validate_external_services()
            healthy_services = sum(1 for s in services.values() if s.status == ServiceStatus.HEALTHY)
            total_services = len(services)
            
            if healthy_services == total_services:
                result.add_success("External services")
            elif healthy_services > 0:
                result.add_issue(f"Some external services unavailable: {healthy_services}/{total_services} healthy", HealthStatus.WARNING)
            else:
                result.add_issue("All external services unavailable - running in fallback mode", HealthStatus.WARNING)
            
            result.details['external_services'] = {
                service_name: {
                    'status': health.status.value,
                    'message': health.message,
                    'fallback_available': health.fallback_available
                }
                for service_name, health in services.items()
            }
            
            # Check 5: Performance metrics
            perf_result = self._check_performance_metrics()
            if perf_result['status'] == 'healthy':
                result.add_success("Performance metrics")
            else:
                result.add_issue(f"Performance issues detected: {perf_result['message']}", HealthStatus.WARNING)
                result.details['performance'] = perf_result
        
        except Exception as e:
            result.add_issue(f"Health check failed with exception: {str(e)}", HealthStatus.CRITICAL)
            self.init_logger.error(
                LogCategory.VALIDATION,
                f"❌ Comprehensive health check failed: {str(e)}",
                error=e
            )
        
        finally:
            result.duration = time.time() - start_time
            
            # Log final status
            if result.status == HealthStatus.HEALTHY:
                self.init_logger.info(
                    LogCategory.VALIDATION,
                    f"✅ Health check completed: {result.checks_passed}/{result.checks_total} checks passed"
                )
            else:
                self.init_logger.error(
                    LogCategory.VALIDATION,
                    f"❌ Health check completed with issues: {result.checks_failed} failed, {len(result.warnings)} warnings"
                )
        
        return result
    
    def _validate_table_structure(self, inspector, table_name: str, result: ValidationResult):
        """Validate structure of a specific table."""
        try:
            columns = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            # Define expected columns for critical tables
            expected_columns = {
                'tenants': ['id', 'name', 'slug', 'is_active', 'created_at'],
                'users': ['id', 'tenant_id', 'email', 'password_hash', 'is_active', 'created_at'],
                'roles': ['id', 'tenant_id', 'name', 'permissions', 'is_system_role', 'created_at']
            }
            
            if table_name in expected_columns:
                existing_columns = [col['name'] for col in columns]
                missing_columns = [col for col in expected_columns[table_name] if col not in existing_columns]
                
                if missing_columns:
                    result.add_issue(f"Table '{table_name}' missing columns: {missing_columns}", ValidationSeverity.ERROR)
                    result.add_suggestion(f"Add missing columns to table '{table_name}'")
            
            result.details[f'{table_name}_structure'] = {
                'columns': len(columns),
                'indexes': len(indexes),
                'foreign_keys': len(foreign_keys)
            }
        
        except Exception as e:
            result.add_issue(f"Failed to validate table '{table_name}' structure: {str(e)}", ValidationSeverity.WARNING)
    
    def _validate_system_tenant(self, result: ValidationResult):
        """Validate system tenant exists."""
        try:
            from app.models import Tenant
            
            system_tenant = Tenant.query.filter_by(slug='ai-secretary-system').first()
            if not system_tenant:
                result.add_issue("System tenant not found", ValidationSeverity.CRITICAL)
                result.add_suggestion("Run data seeding to create system tenant")
            else:
                result.details['system_tenant'] = {
                    'id': system_tenant.id,
                    'name': system_tenant.name,
                    'is_active': system_tenant.is_active
                }
        
        except Exception as e:
            result.add_issue(f"Failed to validate system tenant: {str(e)}", ValidationSeverity.ERROR)
    
    def _validate_admin_user(self, result: ValidationResult):
        """Validate admin user exists."""
        try:
            from app.models import User
            
            admin_user = User.query.filter_by(email='admin@ai-secretary.com').first()
            if not admin_user:
                result.add_issue("Admin user not found", ValidationSeverity.CRITICAL)
                result.add_suggestion("Run data seeding to create admin user")
            else:
                result.details['admin_user'] = {
                    'id': admin_user.id,
                    'email': admin_user.email,
                    'is_active': admin_user.is_active,
                    'role': admin_user.role
                }
        
        except Exception as e:
            result.add_issue(f"Failed to validate admin user: {str(e)}", ValidationSeverity.ERROR)
    
    def _validate_system_roles(self, result: ValidationResult):
        """Validate system roles exist."""
        try:
            from app.models import Role
            
            system_roles = Role.query.filter_by(is_system_role=True).all()
            expected_roles = ['Owner', 'Manager', 'Support', 'Accounting', 'Read Only']
            
            existing_role_names = [role.name for role in system_roles]
            missing_roles = [name for name in expected_roles if name not in existing_role_names]
            
            if missing_roles:
                result.add_issue(f"Missing system roles: {missing_roles}", ValidationSeverity.CRITICAL)
                result.add_suggestion("Run data seeding to create missing system roles")
            
            result.details['system_roles'] = {
                'total': len(system_roles),
                'expected': len(expected_roles),
                'missing': missing_roles
            }
        
        except Exception as e:
            result.add_issue(f"Failed to validate system roles: {str(e)}", ValidationSeverity.ERROR)
    
    def _validate_data_consistency(self, result: ValidationResult):
        """Validate data consistency across tables."""
        try:
            # Check for orphaned records
            self._check_orphaned_users(result)
            self._check_orphaned_roles(result)
            
        except Exception as e:
            result.add_issue(f"Failed to validate data consistency: {str(e)}", ValidationSeverity.WARNING)
    
    def _check_orphaned_users(self, result: ValidationResult):
        """Check for users without valid tenants."""
        try:
            from app.models import User, Tenant
            
            # Find users with non-existent tenant_id
            orphaned_users = self.db.session.query(User).outerjoin(Tenant).filter(Tenant.id.is_(None)).count()
            
            if orphaned_users > 0:
                result.add_issue(f"Found {orphaned_users} orphaned users", ValidationSeverity.WARNING)
                result.add_suggestion("Clean up orphaned user records")
            
            result.details['orphaned_users'] = orphaned_users
        
        except Exception as e:
            result.add_issue(f"Failed to check orphaned users: {str(e)}", ValidationSeverity.WARNING)
    
    def _check_orphaned_roles(self, result: ValidationResult):
        """Check for roles without valid tenants."""
        try:
            from app.models import Role, Tenant
            
            # Find roles with non-existent tenant_id
            orphaned_roles = self.db.session.query(Role).outerjoin(Tenant).filter(Tenant.id.is_(None)).count()
            
            if orphaned_roles > 0:
                result.add_issue(f"Found {orphaned_roles} orphaned roles", ValidationSeverity.WARNING)
                result.add_suggestion("Clean up orphaned role records")
            
            result.details['orphaned_roles'] = orphaned_roles
        
        except Exception as e:
            result.add_issue(f"Failed to check orphaned roles: {str(e)}", ValidationSeverity.WARNING)
    
    def _check_performance_metrics(self) -> Dict[str, Any]:
        """Check database performance metrics."""
        try:
            start_time = time.time()
            
            # Simple query performance test
            with self.db.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            
            query_time = time.time() - start_time
            
            if query_time > 1.0:  # More than 1 second for simple query
                return {
                    'status': 'warning',
                    'message': f'Slow query performance: {query_time:.2f}s',
                    'query_time': query_time
                }
            else:
                return {
                    'status': 'healthy',
                    'message': f'Good query performance: {query_time:.3f}s',
                    'query_time': query_time
                }
        
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Performance check failed: {str(e)}',
                'error': str(e)
            }
    
    def _get_database_type(self) -> str:
        """Get database type from engine."""
        try:
            return self.db.engine.dialect.name
        except:
            return 'unknown'
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get current health status summary.
        
        Returns:
            Dictionary with health status summary
        """
        try:
            connectivity = self.validate_connectivity()
            
            status = {
                'overall_status': HealthStatus.HEALTHY.value if connectivity else HealthStatus.CRITICAL.value,
                'connectivity': connectivity,
                'database_type': self._get_database_type(),
                'last_check': datetime.now().isoformat(),
                'checks': {
                    'connectivity': 'passed' if connectivity else 'failed',
                    'schema': 'unknown',
                    'data': 'unknown'
                }
            }
            
            if connectivity:
                # Quick schema check
                try:
                    inspector = inspect(self.db.engine)
                    tables = inspector.get_table_names()
                    status['checks']['schema'] = 'passed' if len(tables) > 0 else 'failed'
                except:
                    status['checks']['schema'] = 'failed'
                
                # Quick data check
                try:
                    from app.models import Tenant
                    tenant_count = Tenant.query.count()
                    status['checks']['data'] = 'passed' if tenant_count > 0 else 'warning'
                except:
                    status['checks']['data'] = 'failed'
            
            return status
        
        except Exception as e:
            return {
                'overall_status': HealthStatus.CRITICAL.value,
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }