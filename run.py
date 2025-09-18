#!/usr/bin/env python3
"""
AI Secretary Application Entry Point

This script provides a unified entry point for the AI Secretary application
with adaptive configuration that automatically detects available services
and gracefully handles service unavailability.
"""
import os
import sys
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app import create_app, socketio
from app.utils.adaptive_config import AdaptiveConfigManager, validate_current_services
from app.utils.database_manager import DatabaseManager


# Configure basic logging for startup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def validate_startup_environment() -> Dict[str, Any]:
    """
    Validate the startup environment and detect available services.
    
    Returns:
        Dictionary with validation results and service status
    """
    logger.info("🔍 Validating startup environment...")
    
    validation_results = {
        'environment': os.environ.get('FLASK_ENV', 'development'),
        'services': {},
        'warnings': [],
        'errors': [],
        'recommendations': []
    }
    
    try:
        # Validate services using adaptive config manager
        config_manager = AdaptiveConfigManager()
        service_status = config_manager.validate_services()
        
        validation_results['services'] = service_status
        
        # Check for common configuration issues
        _check_environment_variables(validation_results)
        _check_file_permissions(validation_results)
        _check_port_availability(validation_results)
        
        # Generate recommendations based on detected services
        _generate_service_recommendations(validation_results)
        
        logger.info("✅ Environment validation completed")
        return validation_results
        
    except Exception as e:
        logger.error(f"❌ Environment validation failed: {e}")
        validation_results['errors'].append(f"Environment validation failed: {e}")
        return validation_results


def _check_environment_variables(validation_results: Dict[str, Any]):
    """Check for important environment variables."""
    important_vars = [
        ('SECRET_KEY', 'Application security'),
        ('JWT_SECRET_KEY', 'JWT token security'),
        ('FLASK_ENV', 'Environment configuration')
    ]
    
    for var_name, description in important_vars:
        if not os.environ.get(var_name):
            validation_results['warnings'].append(
                f"Environment variable {var_name} not set ({description})"
            )


def _check_file_permissions(validation_results: Dict[str, Any]):
    """Check file and directory permissions."""
    paths_to_check = [
        ('uploads', 'Upload directory'),
        ('logs', 'Log directory'),
        ('instance', 'Instance directory')
    ]
    
    for path_name, description in paths_to_check:
        path = Path(path_name)
        if path.exists() and not os.access(path, os.W_OK):
            validation_results['warnings'].append(
                f"No write permission for {description}: {path}"
            )


def _check_port_availability(validation_results: Dict[str, Any]):
    """Check if the application port is available."""
    import socket
    
    port = int(os.environ.get('PORT', 5000))
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            if result == 0:
                validation_results['warnings'].append(
                    f"Port {port} is already in use. Application may fail to start."
                )
    except Exception as e:
        validation_results['warnings'].append(
            f"Could not check port {port} availability: {e}"
        )


def _generate_service_recommendations(validation_results: Dict[str, Any]):
    """Generate recommendations based on service availability."""
    services = validation_results['services']
    recommendations = validation_results['recommendations']
    
    if not services.get('postgresql', False):
        if services.get('sqlite', False):
            recommendations.append(
                "PostgreSQL unavailable - using SQLite fallback. "
                "For production use, consider setting up PostgreSQL."
            )
        else:
            validation_results['errors'].append(
                "Both PostgreSQL and SQLite are unavailable. Database connection will fail."
            )
    
    if not services.get('redis', False):
        recommendations.append(
            "Redis unavailable - using simple cache fallback. "
            "Some features like rate limiting and Celery tasks will be disabled."
        )


def log_startup_summary(validation_results: Dict[str, Any], app_config: Dict[str, Any]):
    """Log a comprehensive startup summary."""
    logger.info("🚀 AI Secretary Application Startup Summary")
    logger.info("=" * 60)
    
    # Environment information
    environment = validation_results['environment']
    logger.info(f"🌍 Environment: {environment.upper()}")
    
    # Service status
    services = validation_results['services']
    logger.info("🔗 Service Status:")
    for service_name, available in services.items():
        status = "✅ Available" if available else "❌ Unavailable"
        logger.info(f"   {service_name.capitalize()}: {status}")
    
    # Database and cache information
    db_type = app_config.get('DETECTED_DATABASE_TYPE', 'unknown')
    cache_type = app_config.get('DETECTED_CACHE_BACKEND', 'unknown')
    logger.info(f"🗄️  Database: {db_type.upper()}")
    logger.info(f"💾 Cache: {cache_type.upper()}")
    
    # Feature flags
    features = app_config.get('FEATURES', {})
    enabled_features = [name for name, enabled in features.items() if enabled]
    disabled_features = [name for name, enabled in features.items() if not enabled]
    
    if enabled_features:
        logger.info(f"🟢 Enabled features: {', '.join(enabled_features)}")
    if disabled_features:
        logger.info(f"🔴 Disabled features: {', '.join(disabled_features)}")
    
    # Warnings and recommendations
    if validation_results['warnings']:
        logger.info("⚠️  Warnings:")
        for warning in validation_results['warnings']:
            logger.info(f"   • {warning}")
    
    if validation_results['recommendations']:
        logger.info("💡 Recommendations:")
        for recommendation in validation_results['recommendations']:
            logger.info(f"   • {recommendation}")
    
    # Errors
    if validation_results['errors']:
        logger.error("❌ Errors:")
        for error in validation_results['errors']:
            logger.error(f"   • {error}")
    
    # Application URLs
    port = int(os.environ.get('PORT', 5000))
    logger.info("🌐 Application URLs:")
    logger.info(f"   Main: http://localhost:{port}")
    logger.info(f"   Health: http://localhost:{port}/api/v1/health")
    logger.info(f"   API Docs: http://localhost:{port}/api/v1/docs")
    
    # Authentication information
    logger.info("🔑 Default Admin Credentials:")
    logger.info("   Email: admin@ai-secretary.com")
    logger.info("   Password: admin123")
    
    logger.info("=" * 60)


def create_application_with_validation() -> Optional[object]:
    """
    Create the Flask application with comprehensive validation.
    
    Returns:
        Flask application instance or None if creation failed
    """
    try:
        logger.info("🏗️  Creating AI Secretary application...")
        
        # Perform startup validation
        validation_results = validate_startup_environment()
        
        # Check for critical errors
        if validation_results['errors']:
            logger.error("❌ Critical errors detected during validation:")
            for error in validation_results['errors']:
                logger.error(f"   • {error}")
            logger.error("Application startup aborted.")
            return None
        
        # Create the application
        app = create_app()
        
        # Log startup summary
        log_startup_summary(validation_results, app.config)
        
        # Perform post-creation validation
        if not _validate_application_health(app):
            logger.error("❌ Application health check failed")
            return None
        
        logger.info("✅ Application created successfully")
        return app
        
    except Exception as e:
        logger.error(f"❌ Application creation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def _validate_application_health(app) -> bool:
    """
    Validate application health after creation.
    
    Args:
        app: Flask application instance
        
    Returns:
        True if application is healthy, False otherwise
    """
    try:
        with app.app_context():
            # Test database connection
            from app import db
            from sqlalchemy import text
            with db.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            
            # Test basic route registration
            if not app.url_map:
                logger.warning("⚠️  No routes registered in application")
                return False
            
            # Test configuration
            required_config = ['SECRET_KEY', 'SQLALCHEMY_DATABASE_URI']
            for config_key in required_config:
                if not app.config.get(config_key):
                    logger.error(f"❌ Required configuration missing: {config_key}")
                    return False
            
            logger.info("✅ Application health check passed")
            return True
            
    except Exception as e:
        logger.error(f"❌ Application health check failed: {e}")
        return False


def run_application(app, host: str = '0.0.0.0', port: int = None, debug: bool = None):
    """
    Run the application with appropriate server configuration.
    
    Args:
        app: Flask application instance
        host: Host to bind to
        port: Port to bind to
        debug: Debug mode flag
    """
    if port is None:
        port = int(os.environ.get('PORT', 5000))
    
    if debug is None:
        debug = app.config.get('DEBUG', False)
    
    try:
        logger.info(f"🌐 Starting server on {host}:{port}")
        logger.info(f"🐛 Debug mode: {'enabled' if debug else 'disabled'}")
        
        # Use SocketIO's run method for development
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True
        )
        
    except KeyboardInterrupt:
        logger.info("⏹️  Application stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        raise


def main():
    """Main entry point for the application."""
    logger.info("🚀 Starting AI Secretary Application")
    logger.info("=" * 60)
    
    try:
        # Create application with validation
        app = create_application_with_validation()
        
        if app is None:
            logger.error("❌ Failed to create application")
            sys.exit(1)
        
        # Run the application
        run_application(app)
        
    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()