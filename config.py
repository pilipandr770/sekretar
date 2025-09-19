import os
import logging
from datetime import timedelta
from typing import Optional, Dict, Any, Union


logger = logging.getLogger(__name__)


class Config:
    """Base configuration class."""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)  # Longer for development
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # JWT Configuration for development
    JWT_COOKIE_SECURE = False  # Allow HTTP for development
    JWT_COOKIE_CSRF_PROTECT = False  # Disable CSRF for development
    JWT_COOKIE_SAMESITE = 'Lax'  # Allow cross-site requests
    JWT_TOKEN_LOCATION = ['headers', 'cookies']  # Accept tokens from headers and cookies
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///ai_secretary.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database Schema Configuration
    DB_SCHEMA = os.environ.get('DB_SCHEMA') or None
    
    @classmethod
    def get_sqlalchemy_engine_options(cls):
        """Get appropriate engine options based on database type with performance optimizations."""
        db_uri = cls.SQLALCHEMY_DATABASE_URI
        environment = cls.get_environment()
        
        if 'sqlite:///' in db_uri:
            # SQLite configuration with performance optimizations
            if environment == 'production':
                return {
                    'pool_pre_ping': True,
                    'pool_recycle': 300,
                    'connect_args': {
                        'check_same_thread': False,
                        'timeout': 30,
                        'isolation_level': None,  # Autocommit mode
                        # 'journal_mode': 'WAL',    # Write-Ahead Logging (not supported in connect_args)
                        # 'synchronous': 'NORMAL',  # Balance safety and performance (not supported in connect_args)
                        'cache_size': -64000,     # 64MB cache
                        'temp_store': 'MEMORY'    # Temp tables in memory
                    }
                }
            else:
                return {
                    'pool_pre_ping': True,
                    'pool_recycle': 300,
                    'connect_args': {
                        'check_same_thread': False,
                        'timeout': 20,
                        'isolation_level': None,
                        # 'journal_mode': 'WAL',    # Not supported in connect_args
                        # 'synchronous': 'NORMAL',  # Not supported in connect_args
                        'cache_size': -32000,     # 32MB cache for development
                        'temp_store': 'MEMORY'
                    }
                }
        else:
            # PostgreSQL configuration with performance optimizations
            schema = cls.DB_SCHEMA
            
            if environment == 'production':
                options = {
                    'pool_pre_ping': True,
                    'pool_recycle': 3600,         # 1 hour
                    'pool_timeout': 30,
                    'pool_size': 20,              # Larger pool for production
                    'max_overflow': 30,
                    'echo': False,
                    'connect_args': {
                        'connect_timeout': 10,
                        'application_name': 'ai_secretary_prod',
                        'sslmode': 'prefer',
                        'keepalives_idle': 600,
                        'keepalives_interval': 30,
                        'keepalives_count': 3
                    }
                }
            elif environment == 'testing':
                options = {
                    'pool_pre_ping': False,       # Skip ping in tests
                    'pool_recycle': -1,           # Don't recycle in tests
                    'connect_args': {
                        'connect_timeout': 5,
                        'application_name': 'ai_secretary_test'
                    }
                }
            else:
                # Development configuration
                options = {
                    'pool_pre_ping': True,
                    'pool_recycle': 1800,         # 30 minutes
                    'pool_timeout': 20,
                    'pool_size': 5,               # Smaller pool for development
                    'max_overflow': 10,
                    'echo': False,
                    'connect_args': {
                        'connect_timeout': 10,
                        'application_name': 'ai_secretary_dev'
                    }
                }
            
            if schema:
                options['connect_args']['options'] = f'-csearch_path={schema},public'
            
            return options
    
    SQLALCHEMY_ENGINE_OPTIONS = {}
    
    # Redis Configuration with fallback
    REDIS_URL = os.environ.get('REDIS_URL')
    
    @classmethod
    def get_cache_config(cls):
        """Get cache configuration with Redis fallback."""
        redis_url = cls.REDIS_URL
        
        if redis_url and cls._test_redis_connection(redis_url):
            return {
                'CACHE_TYPE': 'redis',
                'CACHE_REDIS_URL': redis_url
            }
        else:
            return {
                'CACHE_TYPE': 'simple'
            }
    
    @staticmethod
    def _test_redis_connection(redis_url):
        """Test Redis connection availability."""
        if not redis_url:
            return False
        
        try:
            import redis
            r = redis.from_url(redis_url, socket_connect_timeout=2)
            r.ping()
            return True
        except Exception:
            return False
    
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'simple')
    CACHE_REDIS_URL = REDIS_URL if REDIS_URL else None
    
    # Celery Configuration with fallback
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') if REDIS_URL else None
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') if REDIS_URL else None
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL') or 'gpt-4-turbo-preview'
    
    # Stripe Configuration
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI')
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_WEBHOOK_URL = os.environ.get('TELEGRAM_WEBHOOK_URL')
    
    # Signal Configuration
    SIGNAL_CLI_PATH = os.environ.get('SIGNAL_CLI_PATH', 'signal-cli')
    SIGNAL_PHONE_NUMBER = os.environ.get('SIGNAL_PHONE_NUMBER')
    SIGNAL_AUTO_INSTALL = os.environ.get('SIGNAL_AUTO_INSTALL', 'true').lower() == 'true'
    SIGNAL_POLLING_INTERVAL = int(os.environ.get('SIGNAL_POLLING_INTERVAL', 2))
    
    # Email Configuration
    SMTP_SERVER = os.environ.get('SMTP_SERVER') or 'smtp.gmail.com'
    SMTP_PORT = int(os.environ.get('SMTP_PORT') or 587)
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    
    # Application Settings
    APP_NAME = os.environ.get('APP_NAME') or 'AI Secretary'
    APP_URL = os.environ.get('APP_URL') or 'http://localhost:5000'
    FRONTEND_URL = os.environ.get('FRONTEND_URL') or 'http://localhost:3000'
    
    # API Information
    API_VERSION = os.environ.get('API_VERSION') or '1.0.0'
    BUILD_DATE = os.environ.get('BUILD_DATE')  # Will be set during build/deployment
    
    # Health Check Settings
    HEALTH_CHECK_TIMEOUT = int(os.environ.get('HEALTH_CHECK_TIMEOUT') or 5)  # seconds
    HEALTH_CHECK_DATABASE_ENABLED = os.environ.get('HEALTH_CHECK_DATABASE_ENABLED', 'true').lower() == 'true'
    HEALTH_CHECK_REDIS_ENABLED = os.environ.get('HEALTH_CHECK_REDIS_ENABLED', 'true').lower() == 'true'
    
    @staticmethod
    def get_environment() -> str:
        """Detect the current environment based on Flask configuration."""
        flask_env = os.environ.get('FLASK_ENV', '').lower()
        if flask_env in ['production', 'prod']:
            return 'production'
        elif flask_env in ['testing', 'test']:
            return 'testing'
        else:
            return 'development'
    
    # Service Detection Configuration
    SERVICE_DETECTION_ENABLED = os.environ.get('SERVICE_DETECTION_ENABLED', 'true').lower() == 'true'
    SERVICE_CONNECTION_TIMEOUT = int(os.environ.get('SERVICE_CONNECTION_TIMEOUT', '5'))
    
    # Database Service Detection
    DATABASE_DETECTION_ENABLED = os.environ.get('DATABASE_DETECTION_ENABLED', 'true').lower() == 'true'
    POSTGRESQL_FALLBACK_ENABLED = os.environ.get('POSTGRESQL_FALLBACK_ENABLED', 'true').lower() == 'true'
    SQLITE_FALLBACK_ENABLED = os.environ.get('SQLITE_FALLBACK_ENABLED', 'true').lower() == 'true'
    
    # SQLite Configuration Options
    SQLITE_DATABASE_URL = os.environ.get('SQLITE_DATABASE_URL', 'sqlite:///ai_secretary.db')
    SQLITE_TIMEOUT = int(os.environ.get('SQLITE_TIMEOUT', '20'))
    SQLITE_CHECK_SAME_THREAD = os.environ.get('SQLITE_CHECK_SAME_THREAD', 'false').lower() == 'true'
    
    # Cache Service Detection
    CACHE_DETECTION_ENABLED = os.environ.get('CACHE_DETECTION_ENABLED', 'true').lower() == 'true'
    REDIS_FALLBACK_ENABLED = os.environ.get('REDIS_FALLBACK_ENABLED', 'true').lower() == 'true'
    SIMPLE_CACHE_FALLBACK = os.environ.get('SIMPLE_CACHE_FALLBACK', 'true').lower() == 'true'
    
    # External Service Detection
    EXTERNAL_SERVICE_DETECTION_ENABLED = os.environ.get('EXTERNAL_SERVICE_DETECTION_ENABLED', 'true').lower() == 'true'
    EXTERNAL_SERVICE_TIMEOUT = int(os.environ.get('EXTERNAL_SERVICE_TIMEOUT', '10'))
    
    # Configuration Validation
    CONFIG_VALIDATION_ENABLED = os.environ.get('CONFIG_VALIDATION_ENABLED', 'true').lower() == 'true'
    CONFIG_VALIDATION_STRICT = os.environ.get('CONFIG_VALIDATION_STRICT', 'false').lower() == 'true'
    
    @classmethod
    def validate_configuration(cls) -> Dict[str, Any]:
        """
        Validate current configuration and return validation results.
        
        Returns:
            Dictionary containing validation results and any errors
        """
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'service_status': {},
            'configuration_issues': []
        }
        
        if not cls.CONFIG_VALIDATION_ENABLED:
            validation_results['warnings'].append("Configuration validation is disabled")
            return validation_results
        
        try:
            # Validate database configuration
            database_validation = cls._validate_database_config()
            validation_results['service_status']['database'] = database_validation
            
            if not database_validation['valid']:
                validation_results['errors'].extend(database_validation['errors'])
                validation_results['valid'] = False
            
            # Validate cache configuration
            cache_validation = cls._validate_cache_config()
            validation_results['service_status']['cache'] = cache_validation
            
            if not cache_validation['valid'] and cls.CONFIG_VALIDATION_STRICT:
                validation_results['errors'].extend(cache_validation['errors'])
                validation_results['valid'] = False
            else:
                validation_results['warnings'].extend(cache_validation.get('warnings', []))
            
            # Validate external services
            external_validation = cls._validate_external_services()
            validation_results['service_status']['external'] = external_validation
            validation_results['warnings'].extend(external_validation.get('warnings', []))
            
            # Check for configuration conflicts
            conflicts = cls._check_configuration_conflicts()
            if conflicts:
                validation_results['configuration_issues'].extend(conflicts)
                if cls.CONFIG_VALIDATION_STRICT:
                    validation_results['valid'] = False
                    validation_results['errors'].extend(conflicts)
                else:
                    validation_results['warnings'].extend(conflicts)
            
        except Exception as e:
            validation_results['valid'] = False
            validation_results['errors'].append(f"Configuration validation failed: {str(e)}")
            logger.error(f"Configuration validation error: {e}")
        
        return validation_results
    
    @classmethod
    def _validate_database_config(cls) -> Dict[str, Any]:
        """Validate database configuration."""
        result = {'valid': True, 'errors': [], 'warnings': []}
        
        # Check if DATABASE_URL is set
        if not cls.SQLALCHEMY_DATABASE_URI:
            result['valid'] = False
            result['errors'].append("DATABASE_URL is not configured")
            return result
        
        # Check database URL format
        db_url = cls.SQLALCHEMY_DATABASE_URI
        if not (db_url.startswith('postgresql://') or db_url.startswith('sqlite://')):
            result['valid'] = False
            result['errors'].append(f"Invalid database URL format: {db_url}")
        
        # PostgreSQL specific validation
        if db_url.startswith('postgresql://'):
            if not cls.DB_SCHEMA:
                result['warnings'].append("DB_SCHEMA not set for PostgreSQL")
        
        # SQLite specific validation
        if db_url.startswith('sqlite://'):
            if cls.DB_SCHEMA:
                result['warnings'].append("DB_SCHEMA is set but not used with SQLite")
        
        return result
    
    @classmethod
    def _validate_cache_config(cls) -> Dict[str, Any]:
        """Validate cache configuration."""
        result = {'valid': True, 'errors': [], 'warnings': []}
        
        # Check cache type
        if not hasattr(cls, 'CACHE_TYPE'):
            result['warnings'].append("CACHE_TYPE not explicitly set")
        
        # Redis specific validation
        if getattr(cls, 'CACHE_TYPE', None) == 'redis':
            if not cls.REDIS_URL:
                result['valid'] = False
                result['errors'].append("REDIS_URL required for Redis cache")
        
        return result
    
    @classmethod
    def _validate_external_services(cls) -> Dict[str, Any]:
        """Validate external service configuration."""
        result = {'warnings': []}
        
        # Check OpenAI configuration
        if not cls.OPENAI_API_KEY:
            result['warnings'].append("OPENAI_API_KEY not configured - AI features will be disabled")
        
        # Check Stripe configuration
        if not cls.STRIPE_SECRET_KEY:
            result['warnings'].append("STRIPE_SECRET_KEY not configured - billing features will be disabled")
        
        # Check Google OAuth configuration
        if not cls.GOOGLE_CLIENT_ID or not cls.GOOGLE_CLIENT_SECRET:
            result['warnings'].append("Google OAuth not configured - Google integration will be disabled")
        
        # Check Telegram configuration
        if not cls.TELEGRAM_BOT_TOKEN:
            result['warnings'].append("TELEGRAM_BOT_TOKEN not configured - Telegram integration will be disabled")
        
        return result
    
    @classmethod
    def _check_configuration_conflicts(cls) -> list:
        """Check for configuration conflicts."""
        conflicts = []
        
        # Check for conflicting database configurations
        if cls.SQLALCHEMY_DATABASE_URI.startswith('sqlite://') and cls.DB_SCHEMA:
            conflicts.append("DB_SCHEMA is set but SQLite doesn't support schemas")
        
        # Check for Redis dependencies
        if cls.CELERY_BROKER_URL and not cls.REDIS_URL:
            conflicts.append("Celery configured but Redis URL not available")
        
        if hasattr(cls, 'RATE_LIMIT_STORAGE_URL') and cls.RATE_LIMIT_STORAGE_URL and not cls.REDIS_URL:
            conflicts.append("Rate limiting configured but Redis URL not available")
        
        return conflicts
    
    @classmethod
    def get_adaptive_database_config(cls) -> Dict[str, Any]:
        """
        Get adaptive database configuration based on environment variables.
        
        Returns:
            Dictionary containing database configuration
        """
        config = {
            'primary_url': cls.SQLALCHEMY_DATABASE_URI,
            'fallback_url': cls.SQLITE_DATABASE_URL,
            'detection_enabled': cls.DATABASE_DETECTION_ENABLED,
            'postgresql_fallback': cls.POSTGRESQL_FALLBACK_ENABLED,
            'sqlite_fallback': cls.SQLITE_FALLBACK_ENABLED,
            'connection_timeout': cls.SERVICE_CONNECTION_TIMEOUT,
            'engine_options': cls.SQLALCHEMY_ENGINE_OPTIONS.copy()
        }
        
        # Add SQLite-specific options
        if cls.SQLITE_DATABASE_URL.startswith('sqlite://'):
            config['sqlite_options'] = {
                'timeout': cls.SQLITE_TIMEOUT,
                'check_same_thread': cls.SQLITE_CHECK_SAME_THREAD
            }
        
        return config
    
    @classmethod
    def get_adaptive_cache_config(cls) -> Dict[str, Any]:
        """
        Get adaptive cache configuration based on environment variables.
        
        Returns:
            Dictionary containing cache configuration
        """
        config = {
            'primary_type': cls.CACHE_TYPE,
            'redis_url': cls.REDIS_URL,
            'detection_enabled': cls.CACHE_DETECTION_ENABLED,
            'redis_fallback': cls.REDIS_FALLBACK_ENABLED,
            'simple_fallback': cls.SIMPLE_CACHE_FALLBACK,
            'connection_timeout': cls.SERVICE_CONNECTION_TIMEOUT
        }
        
        return config
    
    @classmethod
    def get_service_detection_config(cls) -> Dict[str, Any]:
        """
        Get service detection configuration.
        
        Returns:
            Dictionary containing service detection settings
        """
        return {
            'enabled': cls.SERVICE_DETECTION_ENABLED,
            'connection_timeout': cls.SERVICE_CONNECTION_TIMEOUT,
            'database_detection': cls.DATABASE_DETECTION_ENABLED,
            'cache_detection': cls.CACHE_DETECTION_ENABLED,
            'external_service_detection': cls.EXTERNAL_SERVICE_DETECTION_ENABLED,
            'external_service_timeout': cls.EXTERNAL_SERVICE_TIMEOUT,
            'validation_enabled': cls.CONFIG_VALIDATION_ENABLED,
            'validation_strict': cls.CONFIG_VALIDATION_STRICT
        }
    
    # Internationalization
    LANGUAGES = {
        'en': 'English',
        'de': 'Deutsch',
        'uk': 'Українська'
    }
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_DEFAULT_TIMEZONE = 'UTC'
    
    # File Upload Settings
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH') or 16 * 1024 * 1024)  # 16MB
    
    # Rate Limiting
    RATE_LIMIT_STORAGE_URL = os.environ.get('RATE_LIMIT_STORAGE_URL') or 'redis://localhost:6379/3'
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FORMAT = os.environ.get('LOG_FORMAT') or 'json'
    
    # Monitoring and Alerting
    MONITORING_ENABLED = os.environ.get('MONITORING_ENABLED', 'true').lower() == 'true'
    ALERTING_ENABLED = os.environ.get('ALERTING_ENABLED', 'true').lower() == 'true'
    ERROR_TRACKING_ENABLED = os.environ.get('ERROR_TRACKING_ENABLED', 'true').lower() == 'true'
    
    # Performance Monitoring
    PERFORMANCE_LOG_THRESHOLD_MS = int(os.environ.get('PERFORMANCE_LOG_THRESHOLD_MS') or 1000)
    METRICS_RETENTION_DAYS = int(os.environ.get('METRICS_RETENTION_DAYS') or 30)
    SLOW_QUERY_THRESHOLD_MS = int(os.environ.get('SLOW_QUERY_THRESHOLD_MS') or 1000)
    SLOW_REQUEST_THRESHOLD_MS = int(os.environ.get('SLOW_REQUEST_THRESHOLD_MS') or 2000)
    
    # Performance Optimization Settings
    ENABLE_QUERY_OPTIMIZATION = os.environ.get('ENABLE_QUERY_OPTIMIZATION', 'true').lower() == 'true'
    ENABLE_STATIC_OPTIMIZATION = os.environ.get('ENABLE_STATIC_OPTIMIZATION', 'true').lower() == 'true'
    ENABLE_CONNECTION_POOLING = os.environ.get('ENABLE_CONNECTION_POOLING', 'true').lower() == 'true'
    ENABLE_LAZY_LOADING = os.environ.get('ENABLE_LAZY_LOADING', 'true').lower() == 'true'
    
    # Cache Settings for Performance
    QUERY_CACHE_TIMEOUT = int(os.environ.get('QUERY_CACHE_TIMEOUT') or 300)  # 5 minutes
    STATIC_CACHE_TIMEOUT = int(os.environ.get('STATIC_CACHE_TIMEOUT') or 86400)  # 1 day
    
    # Alert Thresholds
    CPU_ALERT_THRESHOLD = float(os.environ.get('CPU_ALERT_THRESHOLD') or 85.0)
    MEMORY_ALERT_THRESHOLD = float(os.environ.get('MEMORY_ALERT_THRESHOLD') or 90.0)
    DISK_ALERT_THRESHOLD = float(os.environ.get('DISK_ALERT_THRESHOLD') or 95.0)
    ERROR_RATE_THRESHOLD = float(os.environ.get('ERROR_RATE_THRESHOLD') or 0.05)
    RESPONSE_TIME_THRESHOLD = float(os.environ.get('RESPONSE_TIME_THRESHOLD') or 2.0)
    
    # Alerting Configuration
    ALERTING_EMAIL = {
        'enabled': os.environ.get('ALERTING_EMAIL_ENABLED', 'false').lower() == 'true',
        'smtp': {
            'host': os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
            'port': int(os.environ.get('SMTP_PORT', 587)),
            'username': os.environ.get('SMTP_USERNAME'),
            'password': os.environ.get('SMTP_PASSWORD'),
            'use_tls': os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true',
            'from_email': os.environ.get('ALERT_FROM_EMAIL', 'alerts@ai-secretary.com')
        },
        'recipients': os.environ.get('CRITICAL_ALERT_EMAIL', '').split(',') if os.environ.get('CRITICAL_ALERT_EMAIL') else [],
        'min_severity': os.environ.get('EMAIL_MIN_SEVERITY', 'high')
    }
    
    ALERTING_SLACK = {
        'enabled': os.environ.get('ALERTING_SLACK_ENABLED', 'false').lower() == 'true',
        'webhook_url': os.environ.get('SLACK_WEBHOOK_URL'),
        'channel': os.environ.get('SLACK_ALERT_CHANNEL', '#alerts'),
        'min_severity': os.environ.get('SLACK_MIN_SEVERITY', 'medium')
    }
    
    ALERTING_WEBHOOK = {
        'enabled': os.environ.get('ALERTING_WEBHOOK_ENABLED', 'false').lower() == 'true',
        'url': os.environ.get('ALERTING_WEBHOOK_URL'),
        'headers': {},
        'timeout': int(os.environ.get('ALERTING_WEBHOOK_TIMEOUT', 10)),
        'min_severity': os.environ.get('WEBHOOK_MIN_SEVERITY', 'low')
    }
    
    # KYB API Configuration
    VIES_API_URL = os.environ.get('VIES_API_URL') or 'https://ec.europa.eu/taxation_customs/vies/services/checkVatService'
    GLEIF_API_URL = os.environ.get('GLEIF_API_URL') or 'https://api.gleif.org/api/v1'
    EU_SANCTIONS_API_URL = os.environ.get('EU_SANCTIONS_API_URL')
    OFAC_API_URL = os.environ.get('OFAC_API_URL')
    UK_SANCTIONS_API_URL = os.environ.get('UK_SANCTIONS_API_URL')
    
    # CORS Settings
    CORS_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']
    
    # WebSocket Settings
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_CORS_ALLOWED_ORIGINS = CORS_ORIGINS


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}  # Remove PostgreSQL-specific options for testing
    DB_SCHEMA = None  # Remove schema for SQLite testing
    WTF_CSRF_ENABLED = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    
    # Disable health checks for testing to avoid external dependencies
    HEALTH_CHECK_DATABASE_ENABLED = False
    HEALTH_CHECK_REDIS_ENABLED = False
    
    # Override service detection for testing
    SERVICE_DETECTION_ENABLED = False
    DATABASE_DETECTION_ENABLED = False
    CACHE_DETECTION_ENABLED = False
    EXTERNAL_SERVICE_DETECTION_ENABLED = False
    
    # Use simple cache for testing
    CACHE_TYPE = 'simple'
    CACHE_REDIS_URL = None
    
    # Disable external services for testing
    CELERY_BROKER_URL = None
    CELERY_RESULT_BACKEND = None
    RATE_LIMIT_STORAGE_URL = None
    
    @classmethod
    def get_sqlite_engine_options(cls) -> Dict[str, Any]:
        """Get SQLite-specific engine options for testing."""
        return {
            'pool_pre_ping': True,
            'connect_args': {
                'check_same_thread': False,
                'timeout': cls.SQLITE_TIMEOUT
            }
        }


class SQLiteConfig(Config):
    """SQLite-specific configuration for local development and testing."""
    
    # Override database configuration for SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLITE_DATABASE_URL', 'sqlite:///ai_secretary.db')
    DB_SCHEMA = None  # SQLite doesn't support schemas
    
    # SQLite-specific engine options
    @classmethod
    def get_sqlalchemy_engine_options(cls):
        return {
            'pool_pre_ping': True,
            'connect_args': {
                'check_same_thread': False,
                'timeout': int(os.environ.get('SQLITE_TIMEOUT', '20'))
            }
        }
    
    SQLALCHEMY_ENGINE_OPTIONS = {}  # Will be set by init_app
    
    # Use simple cache instead of Redis for SQLite mode
    CACHE_TYPE = 'simple'
    CACHE_REDIS_URL = None
    
    # Disable services that require Redis
    CELERY_BROKER_URL = None
    CELERY_RESULT_BACKEND = None
    RATE_LIMIT_STORAGE_URL = None
    
    # Disable health checks for external services
    HEALTH_CHECK_REDIS_ENABLED = False
    
    # Enable SQLite-specific features
    SQLITE_MODE = True
    ENABLE_CELERY = False
    ENABLE_REDIS_CACHE = False
    ENABLE_RATE_LIMITING = False
    ENABLE_WEBSOCKETS = True  # SocketIO can work without Redis
    
    @classmethod
    def init_app(cls, app):
        """Initialize app with SQLite configuration."""
        # Set proper engine options for SQLite
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = cls.get_sqlalchemy_engine_options()
        
        # Create necessary directories
        import os
        from pathlib import Path
        
        # Create upload folder
        upload_folder = Path(app.config.get('UPLOAD_FOLDER', 'uploads'))
        upload_folder.mkdir(exist_ok=True)
        
        # Create logs folder
        logs_folder = Path('logs')
        logs_folder.mkdir(exist_ok=True)
        
        # Create instance folder for SQLite database
        instance_folder = Path('instance')
        instance_folder.mkdir(exist_ok=True)
        
        logger.info("✅ SQLite configuration initialized")
        logger.info(f"📍 Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        logger.info(f"📁 Upload folder: {app.config.get('UPLOAD_FOLDER', 'uploads')}")
        logger.info("🔧 External services disabled for SQLite mode")


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    
    # Enhanced security for production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Database connection pooling for production
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'pool_timeout': 20,
        'pool_size': 10,
        'max_overflow': 20,
        'connect_args': {
            'options': f'-csearch_path={Config.DB_SCHEMA},public'
        }
    }
    
    # Render.com specific settings
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        
        # Handle Render.com DATABASE_URL format
        import os
        database_url = os.environ.get('DATABASE_URL')
        if database_url and database_url.startswith('postgres://'):
            # Render.com uses postgres:// but SQLAlchemy needs postgresql://
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'sqlite': SQLiteConfig,
    'default': DevelopmentConfig
}


def get_config_class(environment: Optional[str] = None) -> type:
    """
    Get configuration class for the specified environment.
    
    Args:
        environment: Environment name or None to auto-detect
        
    Returns:
        Configuration class for the environment
    """
    if environment is None:
        environment = Config.get_environment()
    
    # Check for SQLite mode override or SQLite database URL
    database_url = os.environ.get('DATABASE_URL', '')
    if (os.environ.get('SQLITE_MODE', '').lower() == 'true' or 
        'sqlite:///' in database_url):
        environment = 'sqlite'
    
    config_class = config.get(environment, config['default'])
    
    # Log configuration selection
    logger.info(f"🔧 Selected configuration: {config_class.__name__} for environment: {environment}")
    
    return config_class


def validate_environment_variables() -> Dict[str, Any]:
    """
    Validate required environment variables and return validation results.
    
    Returns:
        Dictionary containing validation results
    """
    validation_results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'missing_required': [],
        'missing_optional': []
    }
    
    # Required environment variables
    required_vars = [
        'SECRET_KEY',
        'JWT_SECRET_KEY'
    ]
    
    # Optional but recommended environment variables
    optional_vars = [
        'DATABASE_URL',
        'REDIS_URL',
        'OPENAI_API_KEY',
        'STRIPE_SECRET_KEY',
        'GOOGLE_CLIENT_ID',
        'GOOGLE_CLIENT_SECRET'
    ]
    
    # Check required variables
    for var in required_vars:
        if not os.environ.get(var):
            validation_results['missing_required'].append(var)
            validation_results['errors'].append(f"Required environment variable {var} is not set")
            validation_results['valid'] = False
    
    # Check optional variables
    for var in optional_vars:
        if not os.environ.get(var):
            validation_results['missing_optional'].append(var)
            validation_results['warnings'].append(f"Optional environment variable {var} is not set")
    
    # Check for development-specific issues
    if Config.get_environment() == 'production':
        if os.environ.get('SECRET_KEY') == 'dev-secret-key-change-in-production':
            validation_results['errors'].append("Using default SECRET_KEY in production")
            validation_results['valid'] = False
        
        if os.environ.get('JWT_SECRET_KEY') == 'jwt-secret-key-change-in-production':
            validation_results['errors'].append("Using default JWT_SECRET_KEY in production")
            validation_results['valid'] = False
    
    return validation_results


def create_error_report(validation_results: Dict[str, Any]) -> str:
    """
    Create a formatted error report from validation results.
    
    Args:
        validation_results: Results from validate_environment_variables()
        
    Returns:
        Formatted error report string
    """
    report_lines = []
    
    if validation_results['valid']:
        report_lines.append("✅ Configuration validation passed")
    else:
        report_lines.append("❌ Configuration validation failed")
    
    if validation_results['errors']:
        report_lines.append("\n🚨 Errors:")
        for error in validation_results['errors']:
            report_lines.append(f"  • {error}")
    
    if validation_results['warnings']:
        report_lines.append("\n⚠️  Warnings:")
        for warning in validation_results['warnings']:
            report_lines.append(f"  • {warning}")
    
    if validation_results['missing_required']:
        report_lines.append(f"\n❌ Missing required variables: {', '.join(validation_results['missing_required'])}")
    
    if validation_results['missing_optional']:
        report_lines.append(f"\n⚠️  Missing optional variables: {', '.join(validation_results['missing_optional'])}")
    
    return '\n'.join(report_lines)