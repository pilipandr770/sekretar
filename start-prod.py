#!/usr/bin/env python3
"""
AI Secretary - Production Startup Script for Render

This script prepares and starts the AI Secretary application for production deployment.
It automatically:
- Validates all required environment variables
- Applies database migrations
- Checks external service connectivity
- Starts the application with production settings
"""
import os
import sys
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging for production startup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s]: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def validate_environment_variables() -> Dict[str, Any]:
    """
    Validate required environment variables for production.
    
    Returns:
        Dictionary with validation results
    """
    logger.info("🔍 Validating production environment variables...")
    
    validation_results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'missing_required': [],
        'missing_optional': []
    }
    
    # Required environment variables for production
    required_vars = [
        ('SECRET_KEY', 'Application security'),
        ('JWT_SECRET_KEY', 'JWT token security'),
        ('DATABASE_URL', 'Database connection'),
    ]
    
    # Optional but recommended environment variables
    optional_vars = [
        ('OPENAI_API_KEY', 'AI features'),
        ('STRIPE_SECRET_KEY', 'Billing functionality'),
        ('GOOGLE_CLIENT_ID', 'Google OAuth'),
        ('GOOGLE_CLIENT_SECRET', 'Google OAuth'),
        ('TELEGRAM_BOT_TOKEN', 'Telegram integration'),
        ('REDIS_URL', 'Caching and background tasks'),
    ]
    
    # Check required variables
    for var_name, description in required_vars:
        value = os.environ.get(var_name)
        if not value:
            validation_results['missing_required'].append((var_name, description))
            validation_results['errors'].append(f"Required environment variable {var_name} is not set ({description})")
            validation_results['valid'] = False
        elif var_name in ['SECRET_KEY', 'JWT_SECRET_KEY'] and len(value) < 32:
            validation_results['warnings'].append(f"{var_name} should be at least 32 characters long for security")
    
    # Check optional variables
    for var_name, description in optional_vars:
        if not os.environ.get(var_name):
            validation_results['missing_optional'].append((var_name, description))
            validation_results['warnings'].append(f"Optional variable {var_name} not set - {description} will be disabled")
    
    # Validate DATABASE_URL format
    database_url = os.environ.get('DATABASE_URL', '')
    if database_url:
        if database_url.startswith('postgres://'):
            # Render.com uses postgres:// but SQLAlchemy needs postgresql://
            corrected_url = database_url.replace('postgres://', 'postgresql://', 1)
            os.environ['DATABASE_URL'] = corrected_url
            logger.info("🔧 Corrected DATABASE_URL format for SQLAlchemy compatibility")
        elif not database_url.startswith('postgresql://'):
            validation_results['warnings'].append("DATABASE_URL format may not be compatible with PostgreSQL")
    
    # Log validation results
    if validation_results['valid']:
        logger.info("✅ Environment variable validation passed")
    else:
        logger.error("❌ Environment variable validation failed")
        for error in validation_results['errors']:
            logger.error(f"   • {error}")
    
    if validation_results['warnings']:
        logger.info("⚠️  Environment warnings:")
        for warning in validation_results['warnings']:
            logger.warning(f"   • {warning}")
    
    return validation_results


def apply_database_migrations() -> bool:
    """
    Apply database migrations for production.
    
    Returns:
        True if migrations applied successfully, False otherwise
    """
    logger.info("🗄️  Applying database migrations...")
    
    try:
        from flask_migrate import upgrade
        from app import create_app
        
        app = create_app()
        
        with app.app_context():
            # Apply all pending migrations
            upgrade()
            logger.info("✅ Database migrations applied successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database migration failed: {e}")
        return False


def check_database_connectivity() -> bool:
    """
    Check database connectivity and basic operations.
    
    Returns:
        True if database is accessible, False otherwise
    """
    logger.info("🔍 Checking database connectivity...")
    
    try:
        from app import create_app
        
        app = create_app()
        
        with app.app_context():
            from app import db
            from sqlalchemy import text
            
            # Test basic connectivity
            with db.engine.connect() as conn:
                result = conn.execute(text('SELECT 1'))
                result.fetchone()
            
            # Test table access (basic health check)
            from app.models import User
            User.query.limit(1).all()
            
            logger.info("✅ Database connectivity check passed")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database connectivity check failed: {e}")
        return False


def check_external_services() -> Dict[str, bool]:
    """
    Check connectivity to external services.
    
    Returns:
        Dictionary with service availability status
    """
    logger.info("🔍 Checking external service connectivity...")
    
    service_status = {}
    
    # Check Redis connectivity
    redis_url = os.environ.get('REDIS_URL')
    if redis_url:
        try:
            import redis
            r = redis.from_url(redis_url, socket_connect_timeout=5)
            r.ping()
            service_status['redis'] = True
            logger.info("✅ Redis connectivity: Available")
        except Exception as e:
            service_status['redis'] = False
            logger.warning(f"⚠️  Redis connectivity: Unavailable ({e})")
    else:
        service_status['redis'] = False
        logger.info("ℹ️  Redis: Not configured")
    
    # Check OpenAI API
    openai_key = os.environ.get('OPENAI_API_KEY')
    if openai_key:
        try:
            import openai
            openai.api_key = openai_key
            # Simple API test (this is a minimal check)
            service_status['openai'] = True
            logger.info("✅ OpenAI API: Configured")
        except Exception as e:
            service_status['openai'] = False
            logger.warning(f"⚠️  OpenAI API: Configuration issue ({e})")
    else:
        service_status['openai'] = False
        logger.info("ℹ️  OpenAI API: Not configured")
    
    # Check Stripe API
    stripe_key = os.environ.get('STRIPE_SECRET_KEY')
    if stripe_key:
        try:
            import stripe
            stripe.api_key = stripe_key
            service_status['stripe'] = True
            logger.info("✅ Stripe API: Configured")
        except Exception as e:
            service_status['stripe'] = False
            logger.warning(f"⚠️  Stripe API: Configuration issue ({e})")
    else:
        service_status['stripe'] = False
        logger.info("ℹ️  Stripe API: Not configured")
    
    return service_status


def create_required_directories():
    """Create required directories for production."""
    directories = [
        'uploads',
        'logs',
        'instance'
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Created directory: {directory}")


def log_production_startup_summary(env_validation: Dict[str, Any], service_status: Dict[str, bool]):
    """Log comprehensive production startup summary."""
    logger.info("🚀 AI Secretary - Production Startup Summary")
    logger.info("=" * 60)
    
    # Environment information
    logger.info("🌍 Environment: PRODUCTION")
    logger.info(f"🐍 Python version: {sys.version.split()[0]}")
    
    # Database information
    database_url = os.environ.get('DATABASE_URL', 'Not configured')
    if 'postgresql://' in database_url:
        logger.info("🗄️  Database: PostgreSQL")
    else:
        logger.info(f"🗄️  Database: {database_url}")
    
    # Service status
    logger.info("🔗 External Service Status:")
    for service_name, available in service_status.items():
        status = "✅ Available" if available else "❌ Unavailable"
        logger.info(f"   {service_name.capitalize()}: {status}")
    
    # Environment variable status
    if env_validation['missing_required']:
        logger.error("❌ Missing required environment variables:")
        for var_name, description in env_validation['missing_required']:
            logger.error(f"   • {var_name}: {description}")
    
    if env_validation['missing_optional']:
        logger.info("ℹ️  Missing optional environment variables:")
        for var_name, description in env_validation['missing_optional']:
            logger.info(f"   • {var_name}: {description}")
    
    # Application URLs (Render automatically provides PORT)
    port = os.environ.get('PORT', '10000')
    logger.info("🌐 Application will be available on Render-provided URL")
    logger.info(f"🔍 Health check: /api/v1/health")
    logger.info(f"📚 API documentation: /api/v1/docs")
    
    logger.info("=" * 60)


def start_production_application():
    """Start the application in production mode."""
    logger.info("🚀 Starting AI Secretary in production mode...")
    
    try:
        from run import main
        main()
    except Exception as e:
        logger.error(f"❌ Production application startup failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


def main():
    """Main entry point for production startup."""
    logger.info("🚀 AI Secretary - Production Startup")
    logger.info("=" * 60)
    
    try:
        # Environment validation
        env_validation = validate_environment_variables()
        if not env_validation['valid']:
            logger.error("❌ Environment validation failed - cannot start application")
            sys.exit(1)
        
        # Create required directories
        create_required_directories()
        
        # Database setup
        if not apply_database_migrations():
            logger.error("❌ Database migration failed - cannot start application")
            sys.exit(1)
        
        if not check_database_connectivity():
            logger.error("❌ Database connectivity check failed - cannot start application")
            sys.exit(1)
        
        # External service checks (non-blocking)
        service_status = check_external_services()
        
        # Log startup summary
        log_production_startup_summary(env_validation, service_status)
        
        # Start the application
        start_production_application()
        
    except Exception as e:
        logger.error(f"❌ Production startup failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
