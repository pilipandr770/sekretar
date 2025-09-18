"""
Graceful Degradation System

This module provides graceful degradation for unavailable services,
clear error messages for configuration issues, and user-friendly
notifications for service unavailability.
"""
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from flask import current_app, request, g
import structlog

logger = structlog.get_logger(__name__)


class ServiceLevel(Enum):
    """Service availability levels."""
    FULL = "full"
    DEGRADED = "degraded"
    MINIMAL = "minimal"
    UNAVAILABLE = "unavailable"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ServiceDegradation:
    """Service degradation configuration."""
    service_name: str
    level: ServiceLevel
    reason: str
    fallback_enabled: bool = True
    user_message: Optional[str] = None
    admin_message: Optional[str] = None
    recovery_instructions: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConfigurationIssue:
    """Configuration issue details."""
    issue_type: str
    severity: ErrorSeverity
    message: str
    service_affected: Optional[str] = None
    resolution_steps: List[str] = field(default_factory=list)
    environment_variables: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class GracefulDegradationManager:
    """
    Manages graceful degradation of services and provides user-friendly
    error messages and notifications.
    """
    
    def __init__(self, app=None):
        """Initialize graceful degradation manager."""
        self.app = app
        self._service_degradations: Dict[str, ServiceDegradation] = {}
        self._configuration_issues: List[ConfigurationIssue] = []
        self._user_notifications: List[Dict[str, Any]] = []
        self._admin_notifications: List[Dict[str, Any]] = []
        
        # Configuration
        self._notification_enabled = True
        self._user_friendly_messages = True
        self._admin_detailed_messages = True
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['graceful_degradation'] = self
        
        # Load configuration
        self._notification_enabled = app.config.get('GRACEFUL_DEGRADATION_ENABLED', True)
        self._user_friendly_messages = app.config.get('USER_FRIENDLY_MESSAGES', True)
        self._admin_detailed_messages = app.config.get('ADMIN_DETAILED_MESSAGES', True)
        
        # Register request context processor
        app.context_processor(self._inject_service_status)
        
        # Perform initial service assessment
        self._assess_service_availability()
        
        logger.info("🛡️ Graceful degradation manager initialized")
    
    def _inject_service_status(self):
        """Inject service status into template context."""
        return {
            'service_degradations': self.get_user_visible_degradations(),
            'service_notifications': self.get_user_notifications(),
            'service_level': self.get_overall_service_level()
        }
    
    def _assess_service_availability(self):
        """Assess availability of all services and configure degradation."""
        logger.info("🔍 Assessing service availability for graceful degradation")
        
        # Database services
        self._assess_database_services()
        
        # Cache services
        self._assess_cache_services()
        
        # External API services
        self._assess_external_services()
        
        # Configuration validation
        self._validate_configuration()
        
        # Generate notifications
        self._generate_notifications()
        
        logger.info(f"📊 Service assessment complete: {len(self._service_degradations)} degradations, {len(self._configuration_issues)} issues")
    
    def _assess_database_services(self):
        """Assess database service availability."""
        try:
            from app.utils.database_manager import get_database_manager
            
            if self.app:
                db_manager = get_database_manager(self.app)
                
                # Check PostgreSQL
                postgresql_available = db_manager.test_postgresql_connection()
                if not postgresql_available:
                    self.add_service_degradation(ServiceDegradation(
                        service_name='postgresql',
                        level=ServiceLevel.UNAVAILABLE,
                        reason='PostgreSQL database connection failed',
                        fallback_enabled=True,
                        user_message='Database is running in compatibility mode',
                        admin_message='PostgreSQL unavailable, using SQLite fallback',
                        recovery_instructions='Check PostgreSQL connection settings and service status'
                    ))
                
                # Check SQLite fallback
                sqlite_available = db_manager.test_sqlite_connection()
                if not sqlite_available and not postgresql_available:
                    self.add_service_degradation(ServiceDegradation(
                        service_name='database',
                        level=ServiceLevel.UNAVAILABLE,
                        reason='No database connection available',
                        fallback_enabled=False,
                        user_message='Database services are temporarily unavailable',
                        admin_message='Both PostgreSQL and SQLite connections failed',
                        recovery_instructions='Check database configuration and file permissions'
                    ))
                elif sqlite_available and not postgresql_available:
                    self.add_service_degradation(ServiceDegradation(
                        service_name='database',
                        level=ServiceLevel.DEGRADED,
                        reason='Running on SQLite fallback',
                        fallback_enabled=True,
                        user_message='Database is running in compatibility mode',
                        admin_message='Using SQLite instead of PostgreSQL',
                        recovery_instructions='Restore PostgreSQL connection for full performance'
                    ))
                    
        except Exception as e:
            logger.error(f"Database service assessment failed: {e}")
            self.add_configuration_issue(ConfigurationIssue(
                issue_type='database_assessment_error',
                severity=ErrorSeverity.HIGH,
                message=f'Failed to assess database services: {str(e)}',
                service_affected='database',
                resolution_steps=[
                    'Check database configuration',
                    'Verify database manager initialization',
                    'Review application logs for detailed errors'
                ]
            ))
    
    def _assess_cache_services(self):
        """Assess cache service availability."""
        try:
            # Check Redis availability
            redis_url = os.environ.get('REDIS_URL')
            if redis_url:
                try:
                    import redis
                    r = redis.from_url(redis_url, socket_connect_timeout=5)
                    r.ping()
                    logger.debug("✅ Redis cache available")
                except Exception as e:
                    self.add_service_degradation(ServiceDegradation(
                        service_name='redis_cache',
                        level=ServiceLevel.UNAVAILABLE,
                        reason=f'Redis connection failed: {str(e)}',
                        fallback_enabled=True,
                        user_message='Caching is running in reduced performance mode',
                        admin_message='Redis unavailable, using in-memory cache',
                        recovery_instructions='Check Redis connection settings and service status'
                    ))
            else:
                self.add_service_degradation(ServiceDegradation(
                    service_name='redis_cache',
                    level=ServiceLevel.UNAVAILABLE,
                    reason='Redis URL not configured',
                    fallback_enabled=True,
                    user_message='Caching is running in basic mode',
                    admin_message='Redis not configured, using simple cache',
                    recovery_instructions='Configure REDIS_URL environment variable'
                ))
                
        except Exception as e:
            logger.error(f"Cache service assessment failed: {e}")
            self.add_configuration_issue(ConfigurationIssue(
                issue_type='cache_assessment_error',
                severity=ErrorSeverity.MEDIUM,
                message=f'Failed to assess cache services: {str(e)}',
                service_affected='cache',
                resolution_steps=[
                    'Check Redis configuration',
                    'Verify Redis service status',
                    'Review cache fallback settings'
                ]
            ))
    
    def _assess_external_services(self):
        """Assess external service availability."""
        external_services = [
            ('OPENAI_API_KEY', 'openai', 'AI features', 'OpenAI API key'),
            ('STRIPE_SECRET_KEY', 'stripe', 'Payment processing', 'Stripe API key'),
            ('GOOGLE_CLIENT_ID', 'google_oauth', 'Google login', 'Google OAuth credentials'),
            ('TELEGRAM_BOT_TOKEN', 'telegram', 'Telegram integration', 'Telegram bot token'),
            ('SIGNAL_PHONE_NUMBER', 'signal', 'Signal integration', 'Signal configuration')
        ]
        
        for env_var, service_name, feature_name, config_name in external_services:
            if not os.environ.get(env_var):
                self.add_service_degradation(ServiceDegradation(
                    service_name=service_name,
                    level=ServiceLevel.UNAVAILABLE,
                    reason=f'{config_name} not configured',
                    fallback_enabled=False,
                    user_message=f'{feature_name} is not available',
                    admin_message=f'{config_name} not configured - {feature_name} disabled',
                    recovery_instructions=f'Configure {env_var} environment variable'
                ))
    
    def _validate_configuration(self):
        """Validate configuration and identify issues."""
        try:
            # Check required environment variables
            required_vars = ['SECRET_KEY', 'JWT_SECRET_KEY']
            for var in required_vars:
                if not os.environ.get(var):
                    self.add_configuration_issue(ConfigurationIssue(
                        issue_type='missing_required_config',
                        severity=ErrorSeverity.CRITICAL,
                        message=f'Required environment variable {var} is not set',
                        environment_variables=[var],
                        resolution_steps=[
                            f'Set {var} environment variable',
                            'Restart the application',
                            'Verify configuration in .env file'
                        ]
                    ))
            
            # Check for weak or default secrets
            secret_key = os.environ.get('SECRET_KEY', '')
            jwt_secret = os.environ.get('JWT_SECRET_KEY', '')
            
            if secret_key and len(secret_key) < 32:
                self.add_configuration_issue(ConfigurationIssue(
                    issue_type='weak_secret_key',
                    severity=ErrorSeverity.HIGH,
                    message='SECRET_KEY is too short (should be at least 32 characters)',
                    environment_variables=['SECRET_KEY'],
                    resolution_steps=[
                        'Generate a strong SECRET_KEY with at least 32 characters',
                        'Use a cryptographically secure random generator',
                        'Update environment configuration'
                    ]
                ))
            
            if jwt_secret and len(jwt_secret) < 32:
                self.add_configuration_issue(ConfigurationIssue(
                    issue_type='weak_jwt_secret',
                    severity=ErrorSeverity.HIGH,
                    message='JWT_SECRET_KEY is too short (should be at least 32 characters)',
                    environment_variables=['JWT_SECRET_KEY'],
                    resolution_steps=[
                        'Generate a strong JWT_SECRET_KEY with at least 32 characters',
                        'Use a cryptographically secure random generator',
                        'Update environment configuration'
                    ]
                ))
            
            # Check for development defaults in production
            if os.environ.get('FLASK_ENV') == 'production':
                if os.environ.get('SECRET_KEY') == 'dev-secret-key-change-in-production':
                    self.add_configuration_issue(ConfigurationIssue(
                        issue_type='insecure_production_config',
                        severity=ErrorSeverity.CRITICAL,
                        message='Using default SECRET_KEY in production environment',
                        environment_variables=['SECRET_KEY'],
                        resolution_steps=[
                            'Generate a secure SECRET_KEY',
                            'Update production environment variables',
                            'Restart the application'
                        ]
                    ))
                
                if os.environ.get('JWT_SECRET_KEY') == 'jwt-secret-key-change-in-production':
                    self.add_configuration_issue(ConfigurationIssue(
                        issue_type='insecure_production_config',
                        severity=ErrorSeverity.CRITICAL,
                        message='Using default JWT_SECRET_KEY in production environment',
                        environment_variables=['JWT_SECRET_KEY'],
                        resolution_steps=[
                            'Generate a secure JWT_SECRET_KEY',
                            'Update production environment variables',
                            'Restart the application'
                        ]
                    ))
            
            # Check database configuration conflicts
            database_url = os.environ.get('DATABASE_URL', '')
            db_schema = os.environ.get('DB_SCHEMA')
            
            if database_url.startswith('sqlite://') and db_schema:
                self.add_configuration_issue(ConfigurationIssue(
                    issue_type='configuration_conflict',
                    severity=ErrorSeverity.MEDIUM,
                    message='DB_SCHEMA is set but SQLite does not support schemas',
                    service_affected='database',
                    environment_variables=['DATABASE_URL', 'DB_SCHEMA'],
                    resolution_steps=[
                        'Remove DB_SCHEMA when using SQLite',
                        'Or switch to PostgreSQL for schema support'
                    ]
                ))
            
            # Check for missing database URL
            if not database_url:
                self.add_configuration_issue(ConfigurationIssue(
                    issue_type='missing_database_config',
                    severity=ErrorSeverity.CRITICAL,
                    message='DATABASE_URL is not configured',
                    service_affected='database',
                    environment_variables=['DATABASE_URL'],
                    resolution_steps=[
                        'Set DATABASE_URL environment variable',
                        'Use PostgreSQL URL for production: postgresql://user:pass@host:port/dbname',
                        'Use SQLite URL for development: sqlite:///path/to/database.db'
                    ]
                ))
            
            # Check for Redis configuration when Celery is enabled
            celery_broker = os.environ.get('CELERY_BROKER_URL')
            redis_url = os.environ.get('REDIS_URL')
            
            if celery_broker and celery_broker.startswith('redis://') and not redis_url:
                self.add_configuration_issue(ConfigurationIssue(
                    issue_type='redis_dependency_missing',
                    severity=ErrorSeverity.MEDIUM,
                    message='Celery is configured to use Redis but REDIS_URL is not set',
                    service_affected='celery',
                    environment_variables=['CELERY_BROKER_URL', 'REDIS_URL'],
                    resolution_steps=[
                        'Set REDIS_URL environment variable',
                        'Or configure Celery to use a different broker',
                        'Ensure Redis service is running'
                    ]
                ))
            
            # Check for file permissions on SQLite database
            if database_url.startswith('sqlite:///'):
                db_path = database_url.replace('sqlite:///', '')
                db_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else '.'
                
                if not os.access(db_dir, os.W_OK):
                    self.add_configuration_issue(ConfigurationIssue(
                        issue_type='sqlite_permissions',
                        severity=ErrorSeverity.HIGH,
                        message=f'SQLite database directory is not writable: {db_dir}',
                        service_affected='database',
                        resolution_steps=[
                            f'Ensure directory {db_dir} exists and is writable',
                            'Check file permissions and ownership',
                            'Create directory if it does not exist'
                        ]
                    ))
            
            # Check for upload directory permissions
            upload_folder = os.environ.get('UPLOAD_FOLDER', 'uploads')
            if not os.path.exists(upload_folder):
                try:
                    os.makedirs(upload_folder, exist_ok=True)
                except OSError as e:
                    self.add_configuration_issue(ConfigurationIssue(
                        issue_type='upload_directory_creation_failed',
                        severity=ErrorSeverity.MEDIUM,
                        message=f'Cannot create upload directory: {str(e)}',
                        service_affected='file_upload',
                        resolution_steps=[
                            f'Create directory {upload_folder} manually',
                            'Check parent directory permissions',
                            'Ensure sufficient disk space'
                        ]
                    ))
            elif not os.access(upload_folder, os.W_OK):
                self.add_configuration_issue(ConfigurationIssue(
                    issue_type='upload_directory_permissions',
                    severity=ErrorSeverity.MEDIUM,
                    message=f'Upload directory is not writable: {upload_folder}',
                    service_affected='file_upload',
                    resolution_steps=[
                        f'Make directory {upload_folder} writable',
                        'Check file permissions and ownership',
                        'Ensure sufficient disk space'
                    ]
                ))
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
    
    def _generate_notifications(self):
        """Generate user and admin notifications based on degradations and issues."""
        self._user_notifications.clear()
        self._admin_notifications.clear()
        
        # Generate user notifications for service degradations
        for degradation in self._service_degradations.values():
            if degradation.user_message and degradation.level in [ServiceLevel.DEGRADED, ServiceLevel.UNAVAILABLE]:
                self._user_notifications.append({
                    'type': 'warning' if degradation.level == ServiceLevel.DEGRADED else 'error',
                    'title': f'Service Notice: {degradation.service_name.title()}',
                    'message': degradation.user_message,
                    'dismissible': True,
                    'timestamp': degradation.timestamp.isoformat()
                })
        
        # Generate admin notifications for configuration issues
        for issue in self._configuration_issues:
            if issue.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                self._admin_notifications.append({
                    'type': 'error' if issue.severity == ErrorSeverity.CRITICAL else 'warning',
                    'title': f'Configuration Issue: {issue.issue_type.replace("_", " ").title()}',
                    'message': issue.message,
                    'resolution_steps': issue.resolution_steps,
                    'environment_variables': issue.environment_variables,
                    'service_affected': issue.service_affected,
                    'dismissible': False,
                    'timestamp': issue.timestamp.isoformat()
                })
    
    def add_service_degradation(self, degradation: ServiceDegradation):
        """Add a service degradation."""
        self._service_degradations[degradation.service_name] = degradation
        
        logger.warning(
            "Service degradation detected",
            service=degradation.service_name,
            level=degradation.level.value,
            reason=degradation.reason,
            fallback_enabled=degradation.fallback_enabled
        )
    
    def remove_service_degradation(self, service_name: str):
        """Remove a service degradation."""
        if service_name in self._service_degradations:
            del self._service_degradations[service_name]
            logger.info(f"Service degradation removed: {service_name}")
    
    def add_configuration_issue(self, issue: ConfigurationIssue):
        """Add a configuration issue."""
        self._configuration_issues.append(issue)
        
        logger.error(
            "Configuration issue detected",
            issue_type=issue.issue_type,
            severity=issue.severity.value,
            message=issue.message,
            service_affected=issue.service_affected
        )
    
    def get_service_degradations(self) -> Dict[str, ServiceDegradation]:
        """Get all service degradations."""
        return self._service_degradations.copy()
    
    def get_user_visible_degradations(self) -> List[Dict[str, Any]]:
        """Get user-visible service degradations."""
        visible = []
        for degradation in self._service_degradations.values():
            if degradation.user_message:
                visible.append({
                    'service': degradation.service_name,
                    'level': degradation.level.value,
                    'message': degradation.user_message,
                    'fallback_enabled': degradation.fallback_enabled
                })
        return visible
    
    def get_configuration_issues(self) -> List[ConfigurationIssue]:
        """Get all configuration issues."""
        return self._configuration_issues.copy()
    
    def get_user_notifications(self) -> List[Dict[str, Any]]:
        """Get user notifications."""
        return self._user_notifications.copy()
    
    def get_admin_notifications(self) -> List[Dict[str, Any]]:
        """Get admin notifications."""
        return self._admin_notifications.copy()
    
    def get_overall_service_level(self) -> ServiceLevel:
        """Get overall service level."""
        if not self._service_degradations:
            return ServiceLevel.FULL
        
        levels = [d.level for d in self._service_degradations.values()]
        
        if ServiceLevel.UNAVAILABLE in levels:
            # Check if any critical services are unavailable
            critical_services = ['database']
            for service_name, degradation in self._service_degradations.items():
                if service_name in critical_services and degradation.level == ServiceLevel.UNAVAILABLE:
                    return ServiceLevel.UNAVAILABLE
            return ServiceLevel.DEGRADED
        elif ServiceLevel.DEGRADED in levels:
            return ServiceLevel.DEGRADED
        elif ServiceLevel.MINIMAL in levels:
            return ServiceLevel.MINIMAL
        else:
            return ServiceLevel.FULL
    
    def is_service_available(self, service_name: str) -> bool:
        """Check if a service is available."""
        degradation = self._service_degradations.get(service_name)
        if not degradation:
            return True
        return degradation.level != ServiceLevel.UNAVAILABLE
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled based on service availability."""
        feature_service_mapping = {
            'ai_features': 'openai',
            'payment_processing': 'stripe',
            'google_login': 'google_oauth',
            'telegram_integration': 'telegram',
            'signal_integration': 'signal',
            'redis_cache': 'redis_cache',
            'database': 'database'
        }
        
        service_name = feature_service_mapping.get(feature_name)
        if service_name:
            return self.is_service_available(service_name)
        
        return True  # Unknown features are assumed available
    
    def get_service_status_summary(self) -> Dict[str, Any]:
        """Get service status summary for monitoring."""
        return {
            'overall_level': self.get_overall_service_level().value,
            'degraded_services': len([d for d in self._service_degradations.values() 
                                    if d.level in [ServiceLevel.DEGRADED, ServiceLevel.MINIMAL]]),
            'unavailable_services': len([d for d in self._service_degradations.values() 
                                       if d.level == ServiceLevel.UNAVAILABLE]),
            'configuration_issues': len(self._configuration_issues),
            'critical_issues': len([i for i in self._configuration_issues 
                                  if i.severity == ErrorSeverity.CRITICAL]),
            'user_notifications': len(self._user_notifications),
            'admin_notifications': len(self._admin_notifications)
        }


# Global instance
_graceful_degradation_manager = None


def get_graceful_degradation_manager(app=None) -> GracefulDegradationManager:
    """Get or create graceful degradation manager instance."""
    global _graceful_degradation_manager
    
    if _graceful_degradation_manager is None:
        _graceful_degradation_manager = GracefulDegradationManager(app)
    elif app is not None and _graceful_degradation_manager.app is None:
        _graceful_degradation_manager.init_app(app)
    
    return _graceful_degradation_manager


def init_graceful_degradation(app):
    """Initialize graceful degradation for Flask app."""
    manager = get_graceful_degradation_manager(app)
    return manager