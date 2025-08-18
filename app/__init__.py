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
    
    # Initialize rate limiting
    from app.utils.rate_limiter import init_rate_limiting
    init_rate_limiting(app)
    
    # Initialize monitoring services
    from app.services.monitoring_service import init_monitoring
    from app.services.alerting_service import init_alerting
    from app.services.error_tracking_service import init_error_tracking
    from app.services.dashboard_service import init_dashboard_service
    from app.services.signal_cli_service import init_signal_cli_service
    
    init_monitoring(app)
    init_alerting(app)
    init_error_tracking(app)
    init_dashboard_service(app)
    init_signal_cli_service(app)
    
    # Initialize performance logging
    from app.utils.performance_logger import init_performance_logging
    init_performance_logging(app, threshold_ms=app.config.get('PERFORMANCE_LOG_THRESHOLD_MS', 1000))
    
    # Configure structured logging
    configure_logging(app)
    
    # Initialize database schema (commented out for now)
    # initialize_database_schema(app)
    
    # Initialize middleware
    initialize_middleware(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register JWT handlers
    register_jwt_handlers(app)
    
    # Register CLI commands
    register_cli_commands(app)
    
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
    from app.api.tenant import tenant_bp
    from app.api.gdpr import gdpr_bp
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.channels import channels_bp
    from app.inbox import inbox_bp
    from app.crm import crm_bp
    from app.calendar import calendar_bp
    from app.knowledge import knowledge_bp
    from app.billing import billing_bp
    from app.kyb import kyb_bp
    from app.main import main_bp
    from app.secretary import secretary_bp
    from app.api.notifications import notifications_bp
    from app.api.signal import signal_bp
    from app.api.monitoring import monitoring_bp
    from app.api.docs import docs_bp
    
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(i18n_bp, url_prefix='/api/v1/i18n')
    app.register_blueprint(tenant_bp, url_prefix='/api/v1/tenant')
    app.register_blueprint(gdpr_bp)  # GDPR blueprint has its own url_prefix
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/v1/admin')
    app.register_blueprint(channels_bp, url_prefix='/api/v1/channels')
    app.register_blueprint(inbox_bp, url_prefix='/api/v1/inbox')
    app.register_blueprint(crm_bp, url_prefix='/api/v1/crm')
    app.register_blueprint(calendar_bp, url_prefix='/api/v1/calendar')
    app.register_blueprint(knowledge_bp, url_prefix='/api/v1/knowledge')
    app.register_blueprint(billing_bp, url_prefix='/api/v1/billing')
    app.register_blueprint(kyb_bp, url_prefix='/api/v1/kyb')
    app.register_blueprint(notifications_bp)
    app.register_blueprint(signal_bp, url_prefix='/api/v1/signal')
    app.register_blueprint(secretary_bp, url_prefix='/api/v1/secretary')
    app.register_blueprint(monitoring_bp, url_prefix='/api/v1/monitoring')
    app.register_blueprint(docs_bp, url_prefix='/api/v1/docs')
    app.register_blueprint(main_bp)
    
    # Register root welcome endpoint
    register_root_routes(app)


def register_root_routes(app):
    """Register root-level routes."""
    from app.utils.response import welcome_response, error_response
    
    @app.route('/')
    def welcome():
        """Welcome endpoint providing API information and available endpoints."""
        try:
            endpoints = {
                "health": "/api/v1/health",
                "version": "/api/v1/version",
                "auth": "/api/v1/auth",
                "docs": "/api/v1/docs"
            }
            
            return welcome_response(
                message="Welcome to AI Secretary API",
                version=app.config.get('API_VERSION', '1.0.0'),
                environment=app.config.get('FLASK_ENV', 'development'),
                endpoints=endpoints
            )
            
        except Exception as e:
            return error_response(
                error_code="WELCOME_ENDPOINT_FAILED",
                message="Failed to load welcome information",
                status_code=500,
                details=str(e)
            )


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


def register_cli_commands(app):
    """Register CLI commands."""
    from app.cli import init_app as init_cli
    init_cli(app)