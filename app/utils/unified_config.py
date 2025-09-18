"""
Unified Configuration System

This module provides a unified configuration system that automatically
adapts based on available services while maintaining compatibility with
the existing configuration structure.
"""
import os
from datetime import timedelta
from typing import Optional, Dict, Any, Type
from config import Config, DevelopmentConfig, TestingConfig, ProductionConfig
from app.utils.adaptive_config import AdaptiveConfigManager


class UnifiedConfig(Config):
    """
    Unified configuration that adapts based on available services.
    
    This class extends the base Config class and automatically configures
    itself based on detected services like PostgreSQL, SQLite, Redis, etc.
    """
    
    def __init__(self):
        """Initialize unified configuration."""
        super().__init__()
        self._adaptive_manager = AdaptiveConfigManager()
        self._configure_services()
    
    def _configure_services(self):
        """Configure services based on availability."""
        # Get adaptive configuration
        adaptive_config = self._adaptive_manager.create_adaptive_config()
        
        # Configure database
        self._configure_database(adaptive_config.database)
        
        # Configure cache
        self._configure_cache(adaptive_config.services)
        
        # Configure features
        self._configure_features(adaptive_config.features)
        
        # Store service status for monitoring
        self.SERVICE_STATUS = adaptive_config.services
        self.FEATURES = adaptive_config.features
        self.DETECTED_DATABASE_TYPE = adaptive_config.database.type
    
    def _configure_database(self, database_config):
        """Configure database settings."""
        self.SQLALCHEMY_DATABASE_URI = database_config.connection_string
        self.SQLALCHEMY_ENGINE_OPTIONS = database_config.engine_options
        
        if database_config.type == 'sqlite':
            # SQLite-specific configuration
            if hasattr(self, 'DB_SCHEMA'):
                delattr(self, 'DB_SCHEMA')
        else:
            # PostgreSQL-specific configuration
            self.DB_SCHEMA = database_config.schema or os.environ.get('DB_SCHEMA', 'ai_secretary')
    
    def _configure_cache(self, services):
        """Configure cache settings based on Redis availability."""
        redis_service = services.get('redis')
        
        if redis_service and redis_service.available:
            # Use Redis cache
            self.CACHE_TYPE = 'redis'
            self.CACHE_REDIS_URL = redis_service.connection_string or self.REDIS_URL
        else:
            # Use simple cache
            self.CACHE_TYPE = 'simple'
            if hasattr(self, 'CACHE_REDIS_URL'):
                delattr(self, 'CACHE_REDIS_URL')
    
    def _configure_features(self, features):
        """Configure feature flags based on service availability."""
        # Celery configuration
        if not features.get('cache_redis', False):
            self.CELERY_BROKER_URL = None
            self.CELERY_RESULT_BACKEND = None
        
        # Rate limiting configuration
        if not features.get('cache_redis', False):
            if hasattr(self, 'RATE_LIMIT_STORAGE_URL'):
                delattr(self, 'RATE_LIMIT_STORAGE_URL')
        
        # Health check configuration
        self.HEALTH_CHECK_DATABASE_ENABLED = features.get('database_postgresql', False) or features.get('database_sqlite', False)
        self.HEALTH_CHECK_REDIS_ENABLED = features.get('cache_redis', False)


class UnifiedDevelopmentConfig(UnifiedConfig, DevelopmentConfig):
    """Unified development configuration."""
    
    def __init__(self):
        DevelopmentConfig.__init__(self)
        UnifiedConfig.__init__(self)


class UnifiedTestingConfig(UnifiedConfig, TestingConfig):
    """Unified testing configuration."""
    
    def __init__(self):
        TestingConfig.__init__(self)
        UnifiedConfig.__init__(self)


class UnifiedProductionConfig(UnifiedConfig, ProductionConfig):
    """Unified production configuration."""
    
    def __init__(self):
        ProductionConfig.__init__(self)
        UnifiedConfig.__init__(self)


def create_unified_config_class(environment: Optional[str] = None) -> Type[Config]:
    """
    Create a unified configuration class for the specified environment.
    
    This function creates a configuration class that automatically adapts
    to available services while maintaining the structure of the original
    configuration classes.
    
    Args:
        environment: Environment name ('development', 'testing', 'production')
        
    Returns:
        Configuration class adapted for available services
    """
    if environment is None:
        environment = os.environ.get('FLASK_ENV', 'development')
    
    # Create adaptive configuration manager
    manager = AdaptiveConfigManager(environment)
    adaptive_config = manager.create_adaptive_config()
    
    # Get base configuration class
    base_configs = {
        'development': DevelopmentConfig,
        'testing': TestingConfig,
        'production': ProductionConfig
    }
    
    base_config_class = base_configs.get(environment, DevelopmentConfig)
    
    # Create dynamic configuration class
    class DynamicUnifiedConfig(base_config_class):
        """Dynamically created unified configuration class."""
        
        def __init__(self):
            super().__init__()
            self._apply_adaptive_config(adaptive_config)
        
        def _apply_adaptive_config(self, config):
            """Apply adaptive configuration settings."""
            # Database configuration
            self.SQLALCHEMY_DATABASE_URI = config.database.connection_string
            self.SQLALCHEMY_ENGINE_OPTIONS = config.database.engine_options
            
            if config.database.type == 'sqlite':
                # Remove PostgreSQL-specific settings for SQLite
                self.DB_SCHEMA = None
            else:
                # Keep PostgreSQL settings
                self.DB_SCHEMA = config.database.schema or os.environ.get('DB_SCHEMA', 'ai_secretary')
            
            # Cache configuration
            redis_service = config.services.get('redis')
            if redis_service and redis_service.available:
                self.CACHE_TYPE = 'redis'
                self.CACHE_REDIS_URL = redis_service.connection_string or getattr(self, 'REDIS_URL', 'redis://localhost:6379/0')
            else:
                self.CACHE_TYPE = 'simple'
                self.CACHE_REDIS_URL = None
            
            # Feature-based configuration
            if not config.features.get('cache_redis', False):
                # Disable Celery if Redis is not available
                self.CELERY_BROKER_URL = None
                self.CELERY_RESULT_BACKEND = None
                
                # Disable rate limiting if Redis is not available
                self.RATE_LIMIT_STORAGE_URL = None
            
            # Health check configuration
            self.HEALTH_CHECK_DATABASE_ENABLED = (
                config.features.get('database_postgresql', False) or 
                config.features.get('database_sqlite', False)
            )
            self.HEALTH_CHECK_REDIS_ENABLED = config.features.get('cache_redis', False)
            
            # Store adaptive configuration information
            self.SERVICE_STATUS = config.services
            self.FEATURES = config.features
            self.DETECTED_DATABASE_TYPE = config.database.type
            self.DETECTED_CACHE_BACKEND = 'redis' if config.features.get('cache_redis') else 'simple'
            self.ADAPTIVE_CONFIG_APPLIED = True
        
        @staticmethod
        def init_app(app):
            """Initialize app with unified configuration."""
            # Call parent init_app if it exists
            if hasattr(base_config_class, 'init_app'):
                base_config_class.init_app(app)
            
            # Log configuration information
            import logging
            logger = logging.getLogger(__name__)
            
            logger.info("🔧 Unified Configuration Applied")
            logger.info(f"📊 Environment: {environment}")
            logger.info(f"🗄️  Database: {app.config.get('DETECTED_DATABASE_TYPE', 'unknown')}")
            logger.info(f"💾 Cache: {app.config.get('DETECTED_CACHE_BACKEND', 'unknown')}")
            
            # Log service status
            service_status = app.config.get('SERVICE_STATUS', {})
            for service_name, status in service_status.items():
                status_icon = "✅" if status.available else "❌"
                logger.info(f"{status_icon} {service_name.title()}: {'Available' if status.available else 'Unavailable'}")
                if not status.available and status.error_message:
                    logger.debug(f"   Error: {status.error_message}")
            
            # Log feature flags
            features = app.config.get('FEATURES', {})
            enabled_features = [name for name, enabled in features.items() if enabled]
            disabled_features = [name for name, enabled in features.items() if not enabled]
            
            if enabled_features:
                logger.info(f"🟢 Enabled features: {', '.join(enabled_features)}")
            if disabled_features:
                logger.info(f"🔴 Disabled features: {', '.join(disabled_features)}")
    
    return DynamicUnifiedConfig


# Unified configuration mapping
unified_config = {
    'development': lambda: create_unified_config_class('development'),
    'testing': lambda: create_unified_config_class('testing'),
    'production': lambda: create_unified_config_class('production'),
    'default': lambda: create_unified_config_class('development')
}


def get_unified_config(environment: Optional[str] = None) -> Type[Config]:
    """
    Get unified configuration for the specified environment.
    
    Args:
        environment: Environment name
        
    Returns:
        Unified configuration class
    """
    if environment is None:
        environment = os.environ.get('FLASK_ENV', 'default')
    
    config_factory = unified_config.get(environment, unified_config['default'])
    return config_factory()