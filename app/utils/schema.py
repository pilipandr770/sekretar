"""Database schema management utilities."""
import os
from flask import current_app
from sqlalchemy import text
from app import db
import structlog

logger = structlog.get_logger()


def get_schema_name():
    """Get current database schema name."""
    try:
        # Check if we're using SQLite (no schema support)
        detected_db_type = current_app.config.get('DETECTED_DATABASE_TYPE')
        if detected_db_type == 'sqlite' or current_app.config.get('TESTING', False):
            return None
        
        schema = current_app.config.get('DB_SCHEMA')
        return schema
    except RuntimeError:
        # Fallback when outside application context
        import os
        testing = os.environ.get('TESTING', 'False').lower() == 'true'
        if testing:
            return None
        
        # Check if SQLite is being used
        database_url = os.environ.get('DATABASE_URL', '')
        if database_url.startswith('sqlite://') or os.environ.get('DETECTED_DATABASE_TYPE') == 'sqlite':
            return None
        
        return os.environ.get('DB_SCHEMA')


def create_schema_if_not_exists():
    """Create database schema if it doesn't exist."""
    schema_name = get_schema_name()
    
    try:
        # Check if schema exists
        result = db.session.execute(
            text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema"),
            {'schema': schema_name}
        )
        
        if not result.fetchone():
            # Create schema
            db.session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
            db.session.commit()
            logger.info(f"Created database schema: {schema_name}")
        else:
            logger.info(f"Database schema already exists: {schema_name}")
            
    except Exception as e:
        logger.error(f"Failed to create schema {schema_name}: {str(e)}")
        db.session.rollback()
        raise


def set_search_path():
    """Set PostgreSQL search_path to use our schema first."""
    schema_name = get_schema_name()
    
    try:
        db.session.execute(text(f'SET search_path TO "{schema_name}", public'))
        db.session.commit()
        logger.info(f"Set search_path to: {schema_name}, public")
    except Exception as e:
        logger.error(f"Failed to set search_path: {str(e)}")
        db.session.rollback()
        raise


def drop_schema(confirm_schema_name=None):
    """Drop database schema (use with caution!)."""
    schema_name = get_schema_name()
    
    if confirm_schema_name != schema_name:
        raise ValueError(f"Schema name confirmation required. Expected: {schema_name}")
    
    try:
        db.session.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        db.session.commit()
        logger.warning(f"Dropped database schema: {schema_name}")
    except Exception as e:
        logger.error(f"Failed to drop schema {schema_name}: {str(e)}")
        db.session.rollback()
        raise


class SchemaAwareModel:
    """Mixin for models that should be schema-aware."""
    
    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Automatically set schema for all subclasses."""
        super().__init_subclass__(**kwargs)
        
        # Set schema in table args
        schema_name = get_schema_name()
        if hasattr(cls, '__table_args__'):
            if isinstance(cls.__table_args__, dict):
                cls.__table_args__['schema'] = schema_name
            elif isinstance(cls.__table_args__, tuple):
                # Convert tuple to dict and add schema
                args = list(cls.__table_args__)
                if args and isinstance(args[-1], dict):
                    args[-1]['schema'] = schema_name
                else:
                    args.append({'schema': schema_name})
                cls.__table_args__ = tuple(args)
        else:
            cls.__table_args__ = {'schema': schema_name}


def init_database_schema(app):
    """Initialize database schema for the application."""
    with app.app_context():
        try:
            # Create schema if it doesn't exist
            create_schema_if_not_exists()
            
            # Set search path
            set_search_path()
            
            logger.info("Database schema initialization completed")
            
        except Exception as e:
            logger.error(f"Database schema initialization failed: {str(e)}")
            raise