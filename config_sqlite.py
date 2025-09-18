"""
Конфигурация для работы с SQLite.

Эта конфигурация позволяет запускать приложение с SQLite
вместо PostgreSQL для локальной разработки и тестирования.
"""
import os
from datetime import timedelta
from pathlib import Path


class SQLiteConfig:
    """Конфигурация для SQLite."""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-sqlite'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-sqlite'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Database Configuration - SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///ai_secretary.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SQLite не поддерживает схемы, поэтому убираем эту настройку
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'max_overflow': 0,
    }
    
    # Redis Configuration (опциональный для SQLite режима)
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CACHE_TYPE = 'simple'  # Используем простой кеш вместо Redis
    
    # Celery Configuration (отключаем для SQLite режима)
    CELERY_BROKER_URL = None
    CELERY_RESULT_BACKEND = None
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL') or 'gpt-4-turbo-preview'
    
    # Gemini Configuration
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL') or 'gemini-pro'
    
    # Stripe Configuration
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI') or 'http://localhost:5000/api/v1/auth/google/callback'
    
    # Google Calendar Configuration
    GOOGLE_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID')
    GOOGLE_CALENDAR_EMBED_URL = os.environ.get('GOOGLE_CALENDAR_EMBED_URL')
    GOOGLE_CALENDAR_TIMEZONE = os.environ.get('GOOGLE_CALENDAR_TIMEZONE') or 'Europe/Berlin'
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_WEBHOOK_URL = os.environ.get('TELEGRAM_WEBHOOK_URL')
    
    # Signal Configuration
    SIGNAL_CLI_PATH = os.environ.get('SIGNAL_CLI_PATH') or 'signal-cli'
    SIGNAL_PHONE_NUMBER = os.environ.get('SIGNAL_PHONE_NUMBER')
    
    # Email Configuration
    SMTP_SERVER = os.environ.get('SMTP_SERVER') or 'smtp.gmail.com'
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    
    # Application Settings
    APP_NAME = os.environ.get('APP_NAME') or 'AI Secretary (SQLite)'
    APP_URL = os.environ.get('APP_URL') or 'http://localhost:5000'
    FRONTEND_URL = os.environ.get('FRONTEND_URL') or 'http://localhost:3000'
    
    # Internationalization
    DEFAULT_LANGUAGE = os.environ.get('DEFAULT_LANGUAGE') or 'en'
    LANGUAGES = ['en', 'uk', 'de']
    
    # File Storage
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    
    # Rate Limiting (отключаем для SQLite режима)
    RATELIMIT_STORAGE_URL = None
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FORMAT = os.environ.get('LOG_FORMAT') or 'text'
    
    # KYB API Configuration
    VIES_API_URL = os.environ.get('VIES_API_URL') or 'https://ec.europa.eu/taxation_customs/vies/services/checkVatService'
    GLEIF_API_URL = os.environ.get('GLEIF_API_URL') or 'https://api.gleif.org/api/v1'
    EU_SANCTIONS_API_URL = os.environ.get('EU_SANCTIONS_API_URL') or 'https://webgate.ec.europa.eu/fsd/fsf'
    OFAC_API_URL = os.environ.get('OFAC_API_URL') or 'https://api.trade.gov/consolidated_screening_list'
    UK_SANCTIONS_API_URL = os.environ.get('UK_SANCTIONS_API_URL') or 'https://ofsistorage.blob.core.windows.net/publishlive'
    
    # SQLite specific settings
    SQLITE_MODE = True
    DEBUG = True
    TESTING = False
    
    # Disable features that require external services in SQLite mode
    ENABLE_CELERY = False
    ENABLE_REDIS_CACHE = False
    ENABLE_RATE_LIMITING = False
    ENABLE_WEBSOCKETS = True  # SocketIO может работать без Redis
    
    @staticmethod
    def init_app(app):
        """Initialize app with SQLite configuration."""
        # Создаем папку для загрузок если её нет
        upload_folder = Path(app.config['UPLOAD_FOLDER'])
        upload_folder.mkdir(exist_ok=True)
        
        # Создаем папку для логов
        logs_folder = Path('logs')
        logs_folder.mkdir(exist_ok=True)
        
        print("✅ SQLite конфигурация инициализирована")
        print(f"📍 База данных: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"📁 Папка загрузок: {app.config['UPLOAD_FOLDER']}")


class DevelopmentSQLiteConfig(SQLiteConfig):
    """Конфигурация для разработки с SQLite."""
    DEBUG = True
    TESTING = False


class TestingSQLiteConfig(SQLiteConfig):
    """Конфигурация для тестирования с SQLite."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test_ai_secretary.db'
    WTF_CSRF_ENABLED = False


# Словарь конфигураций
config = {
    'development': DevelopmentSQLiteConfig,
    'testing': TestingSQLiteConfig,
    'default': DevelopmentSQLiteConfig
}