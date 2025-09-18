"""
Fast Development Configuration
Optimized for speed and reliability without external dependencies
"""

import os
from datetime import timedelta

class FastDevelopmentConfig:
    """Fast development configuration with minimal dependencies"""
    
    # Core Flask settings
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    
    # Database - SQLite only
    SQLALCHEMY_DATABASE_URI = 'sqlite:///ai_secretary.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {'timeout': 20, 'check_same_thread': False}
    }
    
    # Disable all external services
    REDIS_URL = None
    CELERY_BROKER_URL = None
    CELERY_RESULT_BACKEND = None
    
    # Use simple cache
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Disable rate limiting
    RATELIMIT_ENABLED = False
    
    # JWT settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # Disable service detection
    SERVICE_DETECTION_ENABLED = False
    
    # Performance optimizations
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 year
    TEMPLATES_AUTO_RELOAD = False
    
    # Disable unnecessary features
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    
    # SocketIO settings
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_LOGGER = False
    SOCKETIO_ENGINEIO_LOGGER = False
    
    # Logging
    LOG_LEVEL = 'WARNING'  # Reduce log verbosity
    
    @staticmethod
    def init_app(app):
        """Initialize app with fast config"""
        # Disable debug toolbar
        app.config['DEBUG_TB_ENABLED'] = False
        
        # Optimize Jinja2
        app.jinja_env.auto_reload = False
        app.jinja_env.cache_size = 400
        
        # Disable Flask-DebugToolbar
        app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
