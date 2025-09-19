#!/usr/bin/env python3
"""
AI Secretary - Local Development Startup Script

This script sets up and starts the AI Secretary application for local development.
It automatically:
- Checks and creates .env file if missing
- Validates environment configuration
- Initializes database and runs migrations
- Starts the application with development settings
"""
import os
import sys
import logging
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging for startup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        logger.error("❌ Python 3.8 or higher is required")
        logger.error(f"Current version: {sys.version}")
        sys.exit(1)
    logger.info(f"✅ Python version: {sys.version.split()[0]}")


def create_env_file_if_missing():
    """Create .env file from .env.example if it doesn't exist."""
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if not env_file.exists():
        if env_example.exists():
            logger.info("📝 Creating .env file from .env.example...")
            shutil.copy(env_example, env_file)
            logger.info("✅ .env file created successfully")
            logger.info("💡 Please review and update .env file with your settings")
        else:
            logger.warning("⚠️  Neither .env nor .env.example found")
            logger.info("📝 Creating basic .env file...")
            create_basic_env_file()
    else:
        logger.info("✅ .env file exists")


def create_basic_env_file():
    """Create a basic .env file with essential settings."""
    basic_env_content = """# AI Secretary - Local Development Configuration
# Generated automatically - modify as needed

# === CRITICAL CONFIGURATION ===
SECRET_KEY=dev-secret-key-change-in-production
JWT_SECRET_KEY=dev-jwt-secret-key

# === DATABASE CONFIGURATION ===
# Using SQLite for local development
DATABASE_URL=sqlite:///ai_secretary.db

# === APPLICATION SETTINGS ===
FLASK_ENV=development
DEBUG=true
APP_NAME=AI Secretary (Development)
APP_URL=http://localhost:5000

# === EXTERNAL SERVICES ===
# Add your API keys here when needed
# OPENAI_API_KEY=your-openai-key-here
# STRIPE_SECRET_KEY=sk_test_your-stripe-key
"""
    
    with open('.env', 'w') as f:
        f.write(basic_env_content)
    
    logger.info("✅ Basic .env file created")


def create_required_directories():
    """Create required directories if they don't exist."""
    directories = [
        'uploads',
        'logs',
        'instance',
        'migrations/versions'
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Created directory: {directory}")
        
        # Create .gitkeep for empty directories
        gitkeep_file = dir_path / '.gitkeep'
        if not any(dir_path.iterdir()) and not gitkeep_file.exists():
            gitkeep_file.touch()


def check_dependencies():
    """Check if required dependencies are installed."""
    logger.info("🔍 Checking dependencies...")
    
    try:
        import flask
        import sqlalchemy
        import flask_migrate
        logger.info("✅ Core dependencies available")
        return True
    except ImportError as e:
        logger.error(f"❌ Missing dependency: {e}")
        logger.error("💡 Run: pip install -r requirements.txt")
        return False


def initialize_database():
    """Initialize database and run migrations."""
    logger.info("🗄️  Initializing database...")
    
    try:
        # Import after ensuring dependencies are available
        from flask_migrate import upgrade, init, migrate
        from app import create_app
        from app.utils.migration_manager import get_migration_manager
        
        app = create_app()
        
        with app.app_context():
            # Check if migrations directory exists
            migrations_dir = Path('migrations')
            if not migrations_dir.exists():
                logger.info("📝 Initializing migration repository...")
                init()
            
            # Check if there are any migration files
            versions_dir = migrations_dir / 'versions'
            if versions_dir.exists() and any(versions_dir.glob('*.py')):
                logger.info("🔄 Running database migrations...")
                upgrade()
            
            # Ensure all required tables exist using MigrationManager
            logger.info("🔍 Ensuring all required tables exist...")
            migration_manager = get_migration_manager(app)
            migration_result = migration_manager.ensure_tables_exist()
            
            if migration_result.success:
                if migration_result.tables_created:
                    logger.info(f"✅ Created {len(migration_result.tables_created)} missing tables: {migration_result.tables_created}")
                else:
                    logger.info("✅ All required tables already exist")
            else:
                logger.error(f"❌ Failed to create {len(migration_result.tables_failed)} tables: {migration_result.tables_failed}")
                for error in migration_result.errors:
                    logger.error(f"   - {error}")
                # Continue with startup even if some tables failed to create
            
            logger.info("✅ Database initialized successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.error("💡 Check your database configuration in .env")
        return False


def validate_configuration():
    """Validate application configuration."""
    logger.info("🔍 Validating configuration...")
    
    try:
        from app import create_app
        
        app = create_app()
        
        # Check critical configuration
        critical_config = ['SECRET_KEY', 'SQLALCHEMY_DATABASE_URI']
        missing_config = []
        
        for config_key in critical_config:
            if not app.config.get(config_key):
                missing_config.append(config_key)
        
        if missing_config:
            logger.error(f"❌ Missing critical configuration: {', '.join(missing_config)}")
            return False
        
        # Test database connection
        with app.app_context():
            from app import db
            from sqlalchemy import text
            with db.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
        
        logger.info("✅ Configuration validation passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        return False


def start_application():
    """Start the application."""
    logger.info("🚀 Starting AI Secretary application...")
    logger.info("=" * 60)
    
    try:
        from run import main
        main()
    except KeyboardInterrupt:
        logger.info("⏹️  Application stopped by user")
    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        sys.exit(1)


def main():
    """Main entry point for local development startup."""
    logger.info("🚀 AI Secretary - Local Development Startup")
    logger.info("=" * 60)
    
    try:
        # Pre-flight checks
        check_python_version()
        
        # Environment setup
        create_env_file_if_missing()
        create_required_directories()
        
        # Dependency and configuration checks
        if not check_dependencies():
            sys.exit(1)
        
        # Database initialization
        if not initialize_database():
            logger.warning("⚠️  Database initialization failed, but continuing...")
        
        # Configuration validation
        if not validate_configuration():
            logger.error("❌ Configuration validation failed")
            sys.exit(1)
        
        # Start the application
        start_application()
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
