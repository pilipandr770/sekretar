import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_caching import Cache
from config import config
import structlog


# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
socketio = SocketIO()
cache = Cache()


def create_app(config_name=None):
    """Application factory pattern."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, origins=app.config['CORS_ORIGINS'])
    socketio.init_app(
        app, 
        cors_allowed_origins=app.config['SOCKETIO_CORS_ALLOWED_ORIGINS'],
        async_mode=app.config['SOCKETIO_ASYNC_MODE']
    )
    cache.init_app(app)
    
    # Initialize Babel for i18n
    from app.utils.i18n import init_babel
    init_babel(app)
    
    # Initialize middleware
    from app.utils.middleware import init_middleware
    init_middleware(app)
    
    # Configure structured logging
    configure_logging(app)
    
    # Initialize database schema
    initialize_database_schema(app)
    
    # Initialize middleware
    initialize_middleware(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register JWT handlers
    register_jwt_handlers(app)
    
    return app


def configure_logging(app):
    """Configure structured logging."""
    log_level = getattr(logging, app.config['LOG_LEVEL'].upper())
    
    if app.config['LOG_FORMAT'] == 'json':
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    # Configure Flask's logger
    app.logger.setLevel(log_level)
    
    # Remove default handlers
    for handler in app.logger.handlers[:]:
        app.logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    if app.config['LOG_FORMAT'] == 'json':
        formatter = logging.Formatter('%(message)s')
    else:
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s: %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    app.logger.addHandler(console_handler)


def register_blueprints(app):
    """Register application blueprints."""
    from app.api import api_bp
    from app.api.i18n import i18n_bp
    from app.auth import auth_bp
    from app.channels import channels_bp
    from app.inbox import inbox_bp
    from app.crm import crm_bp
    from app.calendar import calendar_bp
    from app.knowledge import knowledge_bp
    from app.billing import billing_bp
    from app.kyb import kyb_bp
    
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(i18n_bp, url_prefix='/api/v1/i18n')
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(channels_bp, url_prefix='/api/v1/channels')
    app.register_blueprint(inbox_bp, url_prefix='/api/v1/inbox')
    app.register_blueprint(crm_bp, url_prefix='/api/v1/crm')
    app.register_blueprint(calendar_bp, url_prefix='/api/v1/calendar')
    app.register_blueprint(knowledge_bp, url_prefix='/api/v1/knowledge')
    app.register_blueprint(billing_bp, url_prefix='/api/v1/billing')
    app.register_blueprint(kyb_bp, url_prefix='/api/v1/kyb')


def register_error_handlers(app):
    """Register error handlers."""
    from app.utils.errors import register_error_handlers as register_handlers
    register_handlers(app)


def register_jwt_handlers(app):
    """Register JWT handlers."""
    from app.utils.jwt_handlers import register_jwt_handlers as register_handlers
    register_handlers(jwt)


def initialize_database_schema(app):
    """Initialize database schema."""
    from app.utils.schema import init_database_schema
    
    # Only initialize schema in non-testing environments
    if not app.config.get('TESTING'):
        init_database_schema(app)


def initialize_middleware(app):
    """Initialize middleware."""
    from app.utils.middleware import init_middleware
    init_middleware(app)