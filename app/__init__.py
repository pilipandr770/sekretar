import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_caching import Cache
import sys
import os
# Add root directory to path to import root config.py
root_dir = os.path.dirname(os.path.dirname(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
from config import config
from app.utils.adaptive_config import get_adaptive_config, validate_current_services
from app.utils.database_manager import get_database_manager, initialize_database_with_fallback
from app.utils.service_health_monitor import get_service_health_monitor
import structlog


# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
# SocketIO will be initialized by WebSocket manager
socketio = None
cache = Cache()


def _log_service_availability(app, service_status):
    """Log service availability status."""
    app.logger.info("🔍 Service Detection Results:")
    app.logger.info("=" * 50)
    
    for service_name, status in service_status.items():
        # Handle ServiceStatus objects
        if hasattr(status, 'available'):
            available = status.available
            connection_string = getattr(status, 'connection_string', None)
            error_message = getattr(status, 'error_message', None)
        else:
            # Fallback for simple boolean values
            available = status
            connection_string = None
            error_message = None
        
        if available:
            app.logger.info(f"✅ {service_name.upper()}: Available")
            if connection_string:
                # Mask sensitive connection details
                masked_connection = _mask_connection_string(connection_string)
                app.logger.info(f"   Connection: {masked_connection}")
        else:
            app.logger.warning(f"❌ {service_name.upper()}: Unavailable")
            if error_message:
                app.logger.warning(f"   Error: {error_message}")
    
    # Log detected configuration
    detected_db = app.config.get('DETECTED_DATABASE_TYPE', 'unknown')
    detected_cache = app.config.get('DETECTED_CACHE_BACKEND', 'unknown')
    
    app.logger.info("=" * 50)
    app.logger.info(f"🗄️  Database: {detected_db.upper()}")
    app.logger.info(f"💾 Cache: {detected_cache.upper()}")
    
    # Log feature flags
    features = app.config.get('FEATURES', {})
    enabled_features = [name for name, enabled in features.items() if enabled]
    disabled_features = [name for name, enabled in features.items() if not enabled]
    
    if enabled_features:
        app.logger.info(f"🟢 Enabled features: {', '.join(enabled_features)}")
    if disabled_features:
        app.logger.info(f"🔴 Disabled features: {', '.join(disabled_features)}")
    
    app.logger.info("=" * 50)


def _mask_connection_string(connection_string):
    """Mask sensitive information in connection strings."""
    if not connection_string:
        return "N/A"
    
    # Mask password in PostgreSQL connection strings
    if connection_string.startswith('postgresql://'):
        parts = connection_string.split('@')
        if len(parts) > 1:
            user_pass = parts[0].split('//')[-1]
            if ':' in user_pass:
                user = user_pass.split(':')[0]
                return f"postgresql://{user}:***@{parts[1]}"
    
    # For SQLite, just show the file path
    if connection_string.startswith('sqlite:///'):
        return connection_string
    
    return "***"


def _initialize_database_with_fallback(app):
    """Initialize database connection with automatic fallback."""
    try:
        # Get database manager and establish connection
        db_manager = get_database_manager(app)
        success, db_type, connection_string = initialize_database_with_fallback(app)
        
        if success:
            app.logger.info(f"✅ Database connection established: {db_type}")
            
            # Update app config with actual connection details
            app.config['SQLALCHEMY_DATABASE_URI'] = connection_string
            app.config['DETECTED_DATABASE_TYPE'] = db_type
            
            # Log connection statistics
            stats = db_manager.get_connection_statistics()
            app.logger.info(f"📊 Connection stats: {stats['successful_connections']} successful, {stats['failed_connections']} failed")
            
        else:
            app.logger.error(f"❌ Database connection failed: {db_type}")
            raise Exception(f"Failed to establish database connection to {db_type}")
            
    except Exception as e:
        app.logger.error(f"❌ Database initialization failed: {e}")
        # Don't raise the exception - let the app continue with whatever config it has
        app.logger.warning("⚠️  Continuing with existing database configuration")


def _initialize_database_system(app, db):
    """
    Initialize comprehensive database system with schema, migrations, and seeding.
    
    This function integrates the DatabaseInitializer to perform complete database
    setup including schema creation, migration execution, and initial data seeding.
    
    Args:
        app: Flask application instance
        db: SQLAlchemy database instance
        
    Returns:
        bool: True if initialization succeeded, False if critical failure occurred
    """
    try:
        # Import DatabaseInitializer
        from app.utils.database_initializer import DatabaseInitializer
        
        # Log environment-specific initialization details
        environment = app.config.get('FLASK_ENV', 'development')
        testing = app.config.get('TESTING', False)
        debug = app.config.get('DEBUG', False)
        
        app.logger.info("🚀 Starting comprehensive database initialization...")
        app.logger.info(f"   Environment: {environment}")
        app.logger.info(f"   Testing Mode: {testing}")
        app.logger.info(f"   Debug Mode: {debug}")
        
        # Environment-specific initialization settings
        if testing:
            app.logger.info("🧪 Using testing environment database initialization")
            # In testing, we might want to be more strict about failures
            app.config['ABORT_ON_DATABASE_FAILURE'] = app.config.get('ABORT_ON_DATABASE_FAILURE', True)
        elif environment == 'development':
            app.logger.info("🛠️  Using development environment database initialization")
            # In development, we're more lenient with failures
            app.config['ABORT_ON_DATABASE_FAILURE'] = app.config.get('ABORT_ON_DATABASE_FAILURE', False)
        elif environment == 'production':
            app.logger.info("🏭 Using production environment database initialization")
            # In production, we might want to be strict about critical failures
            app.config['ABORT_ON_DATABASE_FAILURE'] = app.config.get('ABORT_ON_DATABASE_FAILURE', True)
        
        # Create database initializer instance
        db_initializer = DatabaseInitializer(app, db)
        
        # Store initializer in app context for later access
        app.db_initializer = db_initializer
        
        # Perform initialization
        initialization_result = db_initializer.initialize()
        
        # Store initialization result in app config for monitoring
        app.config['DATABASE_INITIALIZATION_RESULT'] = {
            'success': initialization_result.success,
            'timestamp': initialization_result.timestamp.isoformat(),
            'duration': initialization_result.duration,
            'database_type': initialization_result.database_type,
            'steps_completed': initialization_result.steps_completed,
            'errors': initialization_result.errors,
            'warnings': initialization_result.warnings,
            'environment': environment
        }
        
        # Log initialization results
        if initialization_result.success:
            app.logger.info("✅ Database initialization completed successfully")
            app.logger.info(f"   Duration: {initialization_result.duration:.2f}s")
            app.logger.info(f"   Database Type: {initialization_result.database_type}")
            app.logger.info(f"   Steps Completed: {len(initialization_result.steps_completed)}")
            
            # Log completed steps
            for step in initialization_result.steps_completed:
                app.logger.info(f"   ✓ {step}")
            
            # Log warnings if any
            if initialization_result.warnings:
                app.logger.warning(f"   Warnings: {len(initialization_result.warnings)}")
                for warning in initialization_result.warnings:
                    app.logger.warning(f"   ⚠️  {warning}")
            
            return True
            
        else:
            # Critical initialization failure
            app.logger.error("❌ Database initialization failed with critical errors")
            app.logger.error(f"   Duration: {initialization_result.duration:.2f}s")
            app.logger.error(f"   Steps Completed: {len(initialization_result.steps_completed)}")
            app.logger.error(f"   Errors: {len(initialization_result.errors)}")
            
            # Log completed steps
            for step in initialization_result.steps_completed:
                app.logger.info(f"   ✓ {step}")
            
            # Log errors
            for error in initialization_result.errors:
                app.logger.error(f"   ❌ {error}")
            
            # Check if this is a critical failure that should prevent startup
            critical_errors = [
                'Configuration error',
                'Failed to establish database connection',
                'Health validation error'
            ]
            
            has_critical_error = any(
                any(critical in error for critical in critical_errors)
                for error in initialization_result.errors
            )
            
            if has_critical_error:
                app.logger.critical("🚨 Critical database initialization failure detected")
                return False
            else:
                app.logger.warning("⚠️  Non-critical database initialization failure - continuing with degraded functionality")
                return True
                
    except ImportError as e:
        app.logger.error(f"❌ Database initialization system not available: {e}")
        app.logger.warning("⚠️  Continuing without comprehensive database initialization")
        return True  # Non-critical - continue startup
        
    except Exception as e:
        app.logger.error(f"❌ Unexpected error during database initialization: {e}")
        app.logger.error(f"   Error type: {type(e).__name__}")
        
        # Log stack trace in debug mode
        if app.debug:
            import traceback
            app.logger.debug(f"   Stack trace: {traceback.format_exc()}")
        
        # Determine if this should be treated as critical based on environment
        critical_exceptions = [
            'DatabaseError',
            'OperationalError',
            'IntegrityError',
            'ProgrammingError'
        ]
        
        is_critical = any(critical in str(type(e)) for critical in critical_exceptions)
        
        # In testing environment, treat more exceptions as critical
        if app.config.get('TESTING'):
            is_critical = True
        
        if is_critical:
            app.logger.critical("🚨 Critical database exception detected")
            return False
        else:
            app.logger.warning("⚠️  Non-critical database exception - continuing with degraded functionality")
            return True


def _handle_database_initialization_failure(app):
    """
    Handle database initialization failure with graceful degradation.
    
    This function implements graceful degradation strategies when database
    initialization fails, allowing the application to continue running with
    limited functionality.
    
    Args:
        app: Flask application instance
    """
    app.logger.warning("🔄 Implementing graceful degradation for database initialization failure")
    
    # Set degraded mode flag
    app.config['DATABASE_DEGRADED_MODE'] = True
    app.config['DEGRADED_SERVICES'] = app.config.get('DEGRADED_SERVICES', [])
    app.config['DEGRADED_SERVICES'].append('database_initialization')
    
    # Disable database-dependent features
    features_to_disable = [
        'user_registration',
        'data_persistence',
        'user_authentication',
        'tenant_management',
        'crm_functionality',
        'knowledge_base',
        'calendar_integration',
        'billing_system'
    ]
    
    app.config['DISABLED_FEATURES'] = app.config.get('DISABLED_FEATURES', [])
    app.config['DISABLED_FEATURES'].extend(features_to_disable)
    
    # Log degraded functionality
    app.logger.warning("⚠️  Application running in degraded mode:")
    app.logger.warning("   - Database initialization failed")
    app.logger.warning("   - User authentication may not work")
    app.logger.warning("   - Data persistence is not guaranteed")
    app.logger.warning("   - Some API endpoints may return errors")
    
    # Set up error responses for disabled features
    app.config['DEGRADATION_MESSAGES'] = {
        'database': 'Database initialization failed. Some features may not be available.',
        'authentication': 'User authentication is currently unavailable due to database issues.',
        'data_persistence': 'Data may not be saved due to database initialization problems.'
    }
    
    app.logger.warning("🔧 Graceful degradation implemented - application will continue with limited functionality")


def _initialize_redis_fallback(app):
    """Initialize Redis fallback manager."""
    try:
        from app.utils.redis_fallback import init_redis_fallback
        redis_manager = init_redis_fallback(app)
        
        app.logger.info("✅ Redis fallback manager initialized")
        
        # Log Redis status
        status = redis_manager.get_status()
        app.logger.info(f"🔗 Redis available: {status['redis_available']}")
        app.logger.info(f"💾 Cache type: {status['cache_type']}")
        app.logger.info(f"🔄 Celery enabled: {status['celery_enabled']}")
        
        return redis_manager
        
    except Exception as e:
        app.logger.error(f"❌ Redis fallback manager initialization failed: {e}")
        # Set fallback configuration manually
        app.config['CACHE_TYPE'] = 'simple'
        app.config['CELERY_ENABLED'] = False
        app.config['RATE_LIMITING_ENABLED'] = False
        return None


def _initialize_services_with_graceful_degradation(app):
    """Initialize services with graceful degradation for unavailable services."""
    services_initialized = []
    services_skipped = []
    
    # Cache initialization (already configured by Redis fallback manager)
    try:
        cache.init_app(app)
        cache_type = app.config.get('CACHE_TYPE', 'unknown')
        services_initialized.append(f'Cache ({cache_type})')
    except Exception as e:
        app.logger.warning(f"⚠️  Cache initialization failed: {e}")
        services_skipped.append('Cache (failed)')
    
    # External service initialization
    external_services = [
        ('OPENAI_API_KEY', 'OpenAI API'),
        ('STRIPE_SECRET_KEY', 'Stripe API'),
        ('GOOGLE_CLIENT_ID', 'Google OAuth'),
        ('TELEGRAM_BOT_TOKEN', 'Telegram Bot'),
        ('SIGNAL_PHONE_NUMBER', 'Signal CLI')
    ]
    
    for config_key, service_name in external_services:
        if app.config.get(config_key):
            services_initialized.append(service_name)
        else:
            services_skipped.append(service_name)
    
    # Log service initialization results
    if services_initialized:
        app.logger.info(f"✅ Services initialized: {', '.join(services_initialized)}")
    if services_skipped:
        app.logger.info(f"⏭️  Services skipped: {', '.join(services_skipped)}")
    
    return len(services_initialized), len(services_skipped)


def _initialize_monitoring_services(app):
    """Initialize monitoring services with graceful error handling."""
    monitoring_services = [
        ('app.services.monitoring_service', 'init_monitoring', 'Monitoring Service'),
        ('app.services.alerting_service', 'init_alerting', 'Alerting Service'),
        ('app.services.error_tracking_service', 'init_error_tracking', 'Error Tracking Service'),
        ('app.services.dashboard_service', 'init_dashboard_service', 'Dashboard Service'),
        ('app.services.signal_cli_service', 'init_signal_cli_service', 'Signal CLI Service')
    ]
    
    initialized_services = []
    failed_services = []
    
    for module_name, function_name, service_name in monitoring_services:
        try:
            module = __import__(module_name, fromlist=[function_name])
            init_function = getattr(module, function_name)
            init_function(app)
            initialized_services.append(service_name)
            app.logger.debug(f"✅ {service_name} initialized")
        except ImportError as e:
            app.logger.warning(f"⚠️  {service_name} module not found: {e}")
            failed_services.append(f"{service_name} (module not found)")
        except AttributeError as e:
            app.logger.warning(f"⚠️  {service_name} function not found: {e}")
            failed_services.append(f"{service_name} (function not found)")
        except Exception as e:
            app.logger.warning(f"⚠️  {service_name} initialization failed: {e}")
            failed_services.append(f"{service_name} (init failed)")
    
    # Log monitoring services status
    if initialized_services:
        app.logger.info(f"🔍 Monitoring services initialized: {', '.join(initialized_services)}")
    if failed_services:
        app.logger.info(f"⚠️  Monitoring services skipped: {', '.join(failed_services)}")
    
    return len(initialized_services), len(failed_services)


def _initialize_service_health_monitoring(app):
    """Initialize service health monitoring system."""
    try:
        # Initialize service health monitor
        monitor = get_service_health_monitor(app)
        
        # Add health status callback to update app config
        def health_callback(service_name, result):
            """Update app config with health status changes."""
            try:
                # Update service status in app config
                if not hasattr(app.config, 'SERVICE_HEALTH_STATUS'):
                    app.config['SERVICE_HEALTH_STATUS'] = {}
                
                app.config['SERVICE_HEALTH_STATUS'][service_name] = {
                    'healthy': result.status.value == 'healthy',
                    'last_check': result.timestamp.isoformat(),
                    'response_time_ms': result.response_time_ms
                }
                
                # Update feature flags in app config
                app.config['FEATURE_FLAGS'] = monitor.get_feature_flags()
                
                # Log significant health changes
                if result.status.value != 'healthy':
                    app.logger.warning(f"⚠️ Service {service_name} is {result.status.value}: {result.error_message}")
                else:
                    app.logger.debug(f"✅ Service {service_name} is healthy")
                    
            except Exception as e:
                app.logger.error(f"Health callback error for {service_name}: {e}")
        
        monitor.add_health_callback(health_callback)
        
        # Perform initial health checks
        app.logger.info("🔍 Performing initial service health checks...")
        service_status = monitor.get_service_status()
        feature_flags = monitor.get_feature_flags()
        
        # Update app config with initial status
        app.config['SERVICE_HEALTH_STATUS'] = {
            name: {
                'healthy': status['healthy'],
                'last_check': status['last_check'],
                'response_time_ms': status['response_time_ms']
            }
            for name, status in service_status.items()
        }
        app.config['FEATURE_FLAGS'] = feature_flags
        
        # Log health monitoring initialization
        healthy_services = sum(1 for status in service_status.values() if status['healthy'])
        total_services = len(service_status)
        enabled_features = sum(1 for enabled in feature_flags.values() if enabled)
        total_features = len(feature_flags)
        
        app.logger.info(f"🏥 Service health monitoring initialized")
        app.logger.info(f"   Services: {healthy_services}/{total_services} healthy")
        app.logger.info(f"   Features: {enabled_features}/{total_features} enabled")
        
        return True
        
    except Exception as e:
        app.logger.error(f"❌ Service health monitoring initialization failed: {e}")
        return False


def _initialize_complete_health_system(app):
    """Initialize the complete health monitoring system."""
    try:
        from app.utils.health_system_init import init_complete_health_system
        
        app.logger.info("🏥 Initializing complete health monitoring system...")
        
        # Initialize the complete health system
        result = init_complete_health_system(app)
        
        if result['success']:
            app.logger.info("✅ Complete health monitoring system initialized successfully")
            
            # Log initialized components
            components = result.get('components', {})
            for component_name, component in components.items():
                if component:
                    app.logger.info(f"   ✓ {component_name.title()} service initialized")
                else:
                    app.logger.warning(f"   ⚠️  {component_name.title()} service failed to initialize")
            
            # Store health system status in app config
            app.config['HEALTH_SYSTEM_STATUS'] = {
                'initialized': True,
                'components': list(components.keys()),
                'initialization_time': result.get('initialization_time'),
                'message': result.get('message')
            }
            
            return True
            
        else:
            app.logger.error(f"❌ Complete health monitoring system initialization failed: {result.get('message')}")
            app.logger.error(f"   Error: {result.get('error')}")
            
            # Store failure status
            app.config['HEALTH_SYSTEM_STATUS'] = {
                'initialized': False,
                'error': result.get('error'),
                'message': result.get('message')
            }
            
            return False
            
    except ImportError as e:
        app.logger.warning(f"⚠️  Health system initialization module not available: {e}")
        app.config['HEALTH_SYSTEM_STATUS'] = {
            'initialized': False,
            'error': 'Module not available',
            'message': 'Health system initialization skipped'
        }
        return False
        
    except Exception as e:
        app.logger.error(f"❌ Unexpected error during health system initialization: {e}")
        app.config['HEALTH_SYSTEM_STATUS'] = {
            'initialized': False,
            'error': str(e),
            'message': 'Health system initialization failed with exception'
        }
        return False


def _initialize_additional_services(app):
    """Initialize additional services with graceful error handling."""
    additional_services = [
        ('app.utils.i18n', 'init_babel', 'Internationalization (i18n)'),
        ('app.services.translation_cache_service', 'init_translation_cache', 'Translation Cache'),
        ('app.services.translation_monitoring_service', 'init_translation_monitoring', 'Translation Monitoring'),
        ('app.utils.i18n_performance', 'init_i18n_performance', 'I18n Performance'),
        ('app.utils.middleware', 'init_middleware', 'Middleware'),
        ('app.utils.rate_limiter', 'init_rate_limiting', 'Rate Limiting'),
        ('app.utils.performance_logger', 'init_performance_logging', 'Performance Logging')
    ]
    
    initialized_services = []
    failed_services = []
    
    for module_name, function_name, service_name in additional_services:
        try:
            module = __import__(module_name, fromlist=[function_name])
            init_function = getattr(module, function_name)
            
            # Special handling for performance logging which needs threshold parameter
            if function_name == 'init_performance_logging':
                threshold_ms = app.config.get('PERFORMANCE_LOG_THRESHOLD_MS', 1000)
                init_function(app, threshold_ms=threshold_ms)
            else:
                init_function(app)
                
            initialized_services.append(service_name)
            app.logger.debug(f"✅ {service_name} initialized")
        except ImportError as e:
            app.logger.warning(f"⚠️  {service_name} module not found: {e}")
            failed_services.append(f"{service_name} (module not found)")
        except AttributeError as e:
            app.logger.warning(f"⚠️  {service_name} function not found: {e}")
            failed_services.append(f"{service_name} (function not found)")
        except Exception as e:
            app.logger.warning(f"⚠️  {service_name} initialization failed: {e}")
            failed_services.append(f"{service_name} (init failed)")
    
    # Log additional services status
    if initialized_services:
        app.logger.info(f"🔧 Additional services initialized: {', '.join(initialized_services)}")
    if failed_services:
        app.logger.info(f"⚠️  Additional services skipped: {', '.join(failed_services)}")
    
    return len(initialized_services), len(failed_services)


def create_app(config_name=None):
    """Application factory pattern with adaptive configuration."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    app = Flask(__name__)
    
    # Initialize configuration with proper fallback
    try:
        # Import config utilities
        from config import get_config_class
        
        # Get appropriate config class
        config_class = get_config_class(config_name)
        app.config.from_object(config_class)
        
        # Initialize config-specific settings
        if hasattr(config_class, 'init_app'):
            config_class.init_app(app)
        
        # Set engine options based on database type
        if hasattr(config_class, 'get_sqlalchemy_engine_options'):
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = config_class.get_sqlalchemy_engine_options()
        elif hasattr(config_class, 'get_sqlalchemy_engine_options'):
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = config_class.get_sqlalchemy_engine_options()
        
        # Set cache configuration
        if hasattr(config_class, 'get_cache_config'):
            cache_config = config_class.get_cache_config()
            app.config.update(cache_config)
        
        app.logger.info(f"✅ Configuration initialized: {config_class.__name__}")
        app.logger.info(f"📍 Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        app.logger.info(f"💾 Cache: {app.config.get('CACHE_TYPE', 'unknown')}")
        
    except Exception as e:
        # Fallback to basic configuration
        app.logger.error(f"❌ Configuration initialization failed: {e}")
        # config is already imported at module level
        fallback_config = config.get(config_name, config['default'])
        app.config.from_object(fallback_config)
        app.logger.warning("⚠️  Using fallback configuration")
    
    # Initialize comprehensive error handling system
    _initialize_comprehensive_error_handling(app)
    
    # Ensure upload directory exists
    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    
    # Initialize core extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, origins=app.config.get('CORS_ORIGINS', ['*']))
    
    # Initialize WebSocket manager with graceful error handling
    try:
        from app.utils.websocket_manager import init_websocket_manager
        websocket_manager = init_websocket_manager(app)
        app.logger.info("✅ WebSocket manager initialized")
        
        # Register WebSocket handlers if available
        try:
            from app.main.websocket_handlers import register_websocket_handlers
            register_websocket_handlers()
        except Exception as handler_error:
            app.logger.warning(f"⚠️  WebSocket handlers registration failed: {handler_error}")
            
    except Exception as e:
        app.logger.warning(f"⚠️  WebSocket manager initialization failed: {e}")
        # Ensure WebSocket features are disabled
        app.config['WEBSOCKET_ENABLED'] = False
        app.config['REAL_TIME_NOTIFICATIONS'] = False
    
    # Initialize Redis fallback manager
    _initialize_redis_fallback(app)
    
    # Initialize Application Context Manager for background services
    try:
        from app.utils.application_context_manager import init_context_manager
        context_manager = init_context_manager(app)
        app.logger.info("✅ Application Context Manager initialized")
    except Exception as e:
        app.logger.warning(f"⚠️  Application Context Manager initialization failed: {e}")
    
    # Initialize services with graceful degradation
    services_initialized, services_skipped = _initialize_services_with_graceful_degradation(app)
    
    # Initialize performance optimizations
    try:
        from app.utils.performance_init import init_all_performance_optimizations
        performance_success = init_all_performance_optimizations(app)
        if performance_success:
            app.logger.info("✅ Performance optimizations initialized successfully")
        else:
            app.logger.warning("⚠️  Some performance optimizations failed to initialize")
    except Exception as e:
        app.logger.error(f"❌ Performance optimization initialization failed: {e}")
    
    # Initialize additional services with graceful error handling
    _initialize_additional_services(app)
    
    # Initialize monitoring services with graceful error handling
    _initialize_monitoring_services(app)
    
    # Initialize service health monitoring
    _initialize_service_health_monitoring(app)
    
    # Initialize complete health monitoring system
    _initialize_complete_health_system(app)
    
    # Configure structured logging
    configure_logging(app)
    
    # Initialize comprehensive database system (schema, migrations, seeding)
    database_init_success = _initialize_database_system(app, db)
    
    # Handle database initialization failure
    if not database_init_success:
        _handle_database_initialization_failure(app)
        
        # Check if we should abort startup for critical failures
        abort_on_db_failure = app.config.get('ABORT_ON_DATABASE_FAILURE', False)
        
        if abort_on_db_failure:
            app.logger.critical("🚨 Critical database initialization failure - aborting application startup")
            app.logger.critical("   Set ABORT_ON_DATABASE_FAILURE=False to continue with degraded functionality")
            raise RuntimeError("Critical database initialization failure")
        else:
            app.logger.warning("⚠️  Application starting with degraded database functionality")
            app.logger.warning("   Set ABORT_ON_DATABASE_FAILURE=True to abort startup on database failures")
    
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
    
    # Log application initialization summary
    _log_initialization_summary(app)
    
    return app


def _initialize_comprehensive_error_handling(app):
    """Initialize comprehensive error handling system."""
    try:
        from app.utils.error_handling_init import init_comprehensive_error_handling
        
        # Initialize all error handling components
        error_handling_result = init_comprehensive_error_handling(app)
        
        # Log initialization results
        successful_components = error_handling_result['successful_components']
        failed_components = error_handling_result['failed_components']
        
        if failed_components == 0:
            app.logger.info(f"🛡️ Comprehensive error handling initialized successfully ({successful_components} components)")
        else:
            app.logger.warning(f"⚠️ Error handling initialized with issues: {successful_components} successful, {failed_components} failed")
            
            # Log specific failures
            for error in error_handling_result['initialization_errors']:
                app.logger.warning(f"   - {error}")
        
        return error_handling_result
        
    except Exception as e:
        app.logger.error(f"❌ Critical error during comprehensive error handling initialization: {e}")
        
        # Fallback to basic error handling
        try:
            from app.utils.errors import register_error_handlers
            register_error_handlers(app)
            app.logger.warning("⚠️ Using fallback basic error handling")
        except Exception as fallback_error:
            app.logger.critical(f"🚨 Even fallback error handling failed: {fallback_error}")
        
        return {
            'error_handlers': {},
            'initialization_errors': [str(e)],
            'successful_components': 0,
            'failed_components': 1
        }
        
        # Initialize comprehensive error handler
        from app.utils.comprehensive_error_handler import init_comprehensive_error_handler
        error_handler = init_comprehensive_error_handler(app)
        app.logger.info("✅ Comprehensive error handler initialized")
        
        # Create initial notifications based on service status
        _create_initial_service_notifications(app, degradation_manager, notification_manager)
        
        return True
        
    except Exception as e:
        app.logger.error(f"❌ Error handling systems initialization failed: {e}")
        return False


def _create_initial_service_notifications(app, degradation_manager, notification_manager):
    """Create initial notifications based on service degradations."""
    try:
        degradations = degradation_manager.get_service_degradations()
        
        for service_name, degradation in degradations.items():
            if degradation.level.value in ['degraded', 'unavailable']:
                notification_manager.notify_service_degradation(
                    service_name=service_name,
                    level=degradation.level.value,
                    reason=degradation.reason
                )
        
        configuration_issues = degradation_manager.get_configuration_issues()
        
        for issue in configuration_issues:
            if issue.severity.value in ['high', 'critical']:
                notification_manager.notify_configuration_issue(
                    issue_type=issue.issue_type,
                    message=issue.message,
                    severity=issue.severity.value
                )
        
        app.logger.info(f"📢 Created {len(degradations)} service notifications and {len(configuration_issues)} configuration notifications")
        
    except Exception as e:
        app.logger.error(f"Failed to create initial service notifications: {e}")


def _log_initialization_summary(app):
    """Log application initialization summary."""
    app.logger.info("🚀 Application Initialization Complete")
    app.logger.info("=" * 60)
    
    # Database status with initialization details
    db_type = app.config.get('DETECTED_DATABASE_TYPE', 'unknown')
    db_init_result = app.config.get('DATABASE_INITIALIZATION_RESULT')
    
    if db_init_result:
        if db_init_result['success']:
            app.logger.info(f"🗄️  Database: {db_type.upper()} (✅ Initialized in {db_init_result['duration']:.2f}s)")
            app.logger.info(f"   Steps: {len(db_init_result['steps_completed'])} completed")
            if db_init_result['warnings']:
                app.logger.info(f"   Warnings: {len(db_init_result['warnings'])}")
        else:
            app.logger.info(f"🗄️  Database: {db_type.upper()} (❌ Initialization failed)")
            app.logger.info(f"   Errors: {len(db_init_result['errors'])}")
            if app.config.get('DATABASE_DEGRADED_MODE'):
                app.logger.info(f"   Mode: DEGRADED")
    else:
        app.logger.info(f"🗄️  Database: {db_type.upper()} (⚠️  Basic connection only)")
    
    # Cache status
    cache_type = app.config.get('CACHE_TYPE', 'unknown')
    app.logger.info(f"💾 Cache: {cache_type.upper()}")
    
    # Service status summary
    service_status = app.config.get('SERVICE_STATUS', {})
    available_services = sum(1 for status in service_status.values() if getattr(status, 'available', False))
    total_services = len(service_status)
    
    if total_services > 0:
        app.logger.info(f"🔗 Services: {available_services}/{total_services} available")
    
    # Feature flags summary
    features = app.config.get('FEATURES', {})
    enabled_features = sum(1 for enabled in features.values() if enabled)
    total_features = len(features)
    
    if total_features > 0:
        app.logger.info(f"🎛️  Features: {enabled_features}/{total_features} enabled")
    
    # Degraded services summary
    degraded_services = app.config.get('DEGRADED_SERVICES', [])
    disabled_features = app.config.get('DISABLED_FEATURES', [])
    
    if degraded_services:
        app.logger.warning(f"⚠️  Degraded services: {', '.join(degraded_services)}")
    
    if disabled_features:
        app.logger.warning(f"🚫 Disabled features: {', '.join(disabled_features)}")
    
    # Environment info
    environment = app.config.get('FLASK_ENV', 'unknown')
    app.logger.info(f"🌍 Environment: {environment.upper()}")
    
    app.logger.info("=" * 60)
    
    # Final status message
    if app.config.get('DATABASE_DEGRADED_MODE'):
        app.logger.warning("⚠️  AI Secretary application ready with limited functionality!")
        app.logger.warning("   Some features may not work due to database initialization issues")
    else:
        app.logger.info("✅ AI Secretary application ready to serve requests!")
    
    app.logger.info("=" * 60)


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
    from app.api.i18n import i18n_bp, user_bp
    from app.api.tenant import tenant_bp
    from app.api.gdpr import gdpr_bp
    from app.api.health import health_bp
    from app.api.service_status import service_status_bp
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.channels import channels_bp
    from app.inbox import inbox_bp
    from app.crm import crm_bp
    from app.calendar_module import calendar_bp
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
    app.register_blueprint(i18n_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(tenant_bp, url_prefix='/api/v1/tenant')
    app.register_blueprint(gdpr_bp)  # GDPR blueprint has its own url_prefix
    app.register_blueprint(health_bp, url_prefix='/api/v1')
    app.register_blueprint(service_status_bp, url_prefix='/api/v1/service')
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