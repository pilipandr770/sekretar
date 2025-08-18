import os
from datetime import timedelta
from typing import Optional


class Config:
    """Base configuration class."""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://localhost/ai_secretary'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database Schema Configuration
    DB_SCHEMA = os.environ.get('DB_SCHEMA') or 'ai_secretary'
    
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'max_overflow': 0,
        'connect_args': {
            'options': f'-csearch_path={DB_SCHEMA},public'
        }
    }
    
    # Redis Configuration
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = REDIS_URL
    
    # Celery Configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/1'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/2'
    
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
    'default': DevelopmentConfig
}