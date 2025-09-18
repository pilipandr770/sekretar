"""
Database Connection Manager

This module provides database connection management with automatic fallback
from PostgreSQL to SQLite when PostgreSQL is unavailable.
"""
import os
import logging
import time
import threading
from typing import Optional, Tuple, Dict, Any, Callable
from contextlib import contextmanager
from datetime import datetime, timedelta
import psycopg2
import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app


logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections with automatic fallback logic.
    
    This class handles connection attempts to PostgreSQL with automatic
    fallback to SQLite when PostgreSQL is unavailable. It includes
    connection health monitoring, logging, and timeout handling.
    """
    
    def __init__(self, app=None):
        """Initialize database manager."""
        self.app = app
        self.connection_timeout = 10  # seconds
        self.retry_attempts = 3
        self.retry_delay = 1  # seconds
        self._current_database_type = None
        self._current_connection_string = None
        self._engine = None
        
        # Health monitoring
        self._health_check_interval = 30  # seconds
        self._last_health_check = None
        self._health_status = False
        self._health_monitor_thread = None
        self._health_monitor_stop_event = threading.Event()
        self._health_callbacks = []
        
        # Connection statistics
        self._connection_stats = {
            'total_connections': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'postgresql_attempts': 0,
            'sqlite_fallbacks': 0,
            'last_connection_time': None,
            'last_failure_time': None,
            'last_failure_reason': None
        }
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize database manager with Flask app."""
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['database_manager'] = self
        
        # Configure timeouts from app config
        self.connection_timeout = app.config.get('DATABASE_CONNECTION_TIMEOUT', 10)
        self._health_check_interval = app.config.get('DATABASE_HEALTH_CHECK_INTERVAL', 30)
        
        # Start health monitoring if enabled
        if app.config.get('DATABASE_HEALTH_MONITORING_ENABLED', True):
            self.start_health_monitoring()
    
    def start_health_monitoring(self):
        """Start background health monitoring."""
        if self._health_monitor_thread and self._health_monitor_thread.is_alive():
            return
        
        self._health_monitor_stop_event.clear()
        self._health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True,
            name='DatabaseHealthMonitor'
        )
        self._health_monitor_thread.start()
        logger.info("🔍 Database health monitoring started")
    
    def stop_health_monitoring(self):
        """Stop background health monitoring."""
        if self._health_monitor_thread:
            self._health_monitor_stop_event.set()
            self._health_monitor_thread.join(timeout=5)
            logger.info("⏹️ Database health monitoring stopped")
    
    def add_health_callback(self, callback: Callable[[bool, str], None]):
        """
        Add callback for health status changes.
        
        Args:
            callback: Function called with (is_healthy, database_type) when status changes
        """
        self._health_callbacks.append(callback)
    
    def _health_monitor_loop(self):
        """Background health monitoring loop."""
        while not self._health_monitor_stop_event.wait(self._health_check_interval):
            try:
                previous_status = self._health_status
                self._health_status = self.test_connection_health()
                self._last_health_check = datetime.now()
                
                # Call callbacks if status changed
                if previous_status != self._health_status:
                    for callback in self._health_callbacks:
                        try:
                            callback(self._health_status, self._current_database_type)
                        except Exception as e:
                            logger.error(f"Health callback error: {e}")
                
                if not self._health_status:
                    logger.warning(f"⚠️ Database health check failed for {self._current_database_type}")
                    # Attempt reconnection if unhealthy
                    if self.reconnect():
                        logger.info("✅ Database reconnection successful during health check")
                
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
    
    def connect_postgresql(self, connection_string: Optional[str] = None) -> bool:
        """
        Attempt to connect to PostgreSQL.
        
        Args:
            connection_string: Optional PostgreSQL connection string
            
        Returns:
            True if connection successful, False otherwise
        """
        if connection_string is None:
            connection_string = self._get_postgresql_connection_string()
        
        logger.info(f"Attempting PostgreSQL connection: {self._mask_password(connection_string)}")
        
        self._connection_stats['total_connections'] += 1
        self._connection_stats['postgresql_attempts'] += 1
        
        for attempt in range(self.retry_attempts):
            try:
                start_time = time.time()
                
                # Test connection with psycopg2 first (faster)
                conn = psycopg2.connect(
                    connection_string,
                    connect_timeout=self.connection_timeout
                )
                conn.close()
                
                # Test with SQLAlchemy engine
                engine = create_engine(
                    connection_string,
                    pool_pre_ping=True,
                    pool_timeout=self.connection_timeout,
                    connect_args={'connect_timeout': self.connection_timeout}
                )
                
                with engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
                
                connection_time = time.time() - start_time
                
                self._current_database_type = 'postgresql'
                self._current_connection_string = connection_string
                self._engine = engine
                self._health_status = True
                
                # Update statistics
                self._connection_stats['successful_connections'] += 1
                self._connection_stats['last_connection_time'] = datetime.now()
                
                logger.info(f"✅ PostgreSQL connection successful (took {connection_time:.2f}s)")
                return True
                
            except Exception as e:
                logger.debug(f"PostgreSQL connection attempt {attempt + 1} failed: {e}")
                
                # Update failure statistics
                self._connection_stats['failed_connections'] += 1
                self._connection_stats['last_failure_time'] = datetime.now()
                self._connection_stats['last_failure_reason'] = str(e)
                
                if attempt < self.retry_attempts - 1:
                    logger.debug(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.warning(f"❌ PostgreSQL connection failed after {self.retry_attempts} attempts: {e}")
        
        return False
    
    def connect_sqlite(self, connection_string: Optional[str] = None) -> bool:
        """
        Attempt to connect to SQLite.
        
        Args:
            connection_string: Optional SQLite connection string
            
        Returns:
            True if connection successful, False otherwise
        """
        if connection_string is None:
            connection_string = self._get_sqlite_connection_string()
        
        logger.info(f"Attempting SQLite connection: {connection_string}")
        
        self._connection_stats['total_connections'] += 1
        self._connection_stats['sqlite_fallbacks'] += 1
        
        try:
            start_time = time.time()
            
            # Test connection with sqlite3 first
            if connection_string.startswith('sqlite:///'):
                db_path = connection_string[10:]  # Remove 'sqlite:///'
                
                if db_path != ':memory:':
                    # Ensure directory exists for file-based SQLite
                    db_dir = os.path.dirname(db_path)
                    if db_dir and not os.path.exists(db_dir):
                        os.makedirs(db_dir, exist_ok=True)
                        logger.info(f"📁 Created directory for SQLite database: {db_dir}")
                
                # Test connection
                if db_path == ':memory:':
                    conn = sqlite3.connect(':memory:', timeout=self.connection_timeout)
                else:
                    conn = sqlite3.connect(db_path, timeout=self.connection_timeout)
                
                conn.execute('SELECT 1')
                conn.close()
            
            # Test with SQLAlchemy engine
            # SQLite doesn't support pool_timeout, use connect_args instead
            engine = create_engine(
                connection_string,
                pool_pre_ping=True,
                connect_args={
                    'check_same_thread': False,
                    'timeout': self.connection_timeout
                }
            )
            
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            
            connection_time = time.time() - start_time
            
            self._current_database_type = 'sqlite'
            self._current_connection_string = connection_string
            self._engine = engine
            self._health_status = True
            
            # Update statistics
            self._connection_stats['successful_connections'] += 1
            self._connection_stats['last_connection_time'] = datetime.now()
            
            logger.info(f"✅ SQLite connection successful (took {connection_time:.2f}s)")
            return True
            
        except Exception as e:
            # Update failure statistics
            self._connection_stats['failed_connections'] += 1
            self._connection_stats['last_failure_time'] = datetime.now()
            self._connection_stats['last_failure_reason'] = str(e)
            
            logger.error(f"❌ SQLite connection failed: {e}")
            return False
    
    def get_connection_string(self) -> Optional[str]:
        """
        Get the current active connection string.
        
        Returns:
            Current connection string or None if no connection
        """
        return self._current_connection_string
    
    def get_database_type(self) -> Optional[str]:
        """
        Get the current active database type.
        
        Returns:
            'postgresql', 'sqlite', or None if no connection
        """
        return self._current_database_type
    
    def get_engine(self):
        """
        Get the current SQLAlchemy engine.
        
        Returns:
            SQLAlchemy engine or None if no connection
        """
        return self._engine
    
    def establish_connection(self) -> Tuple[bool, str, str]:
        """
        Establish database connection with automatic fallback.
        
        Tries PostgreSQL first, then falls back to SQLite if PostgreSQL
        is unavailable.
        
        Returns:
            Tuple of (success, database_type, connection_string)
        """
        logger.info("🔍 Establishing database connection with automatic fallback...")
        
        # Try PostgreSQL first
        if self.connect_postgresql():
            return True, self._current_database_type, self._current_connection_string
        
        # Fallback to SQLite
        logger.info("🔄 PostgreSQL unavailable, falling back to SQLite...")
        if self.connect_sqlite():
            return True, self._current_database_type, self._current_connection_string
        
        # Both failed
        logger.error("❌ Both PostgreSQL and SQLite connections failed")
        return False, None, None
    
    def migrate_if_needed(self) -> bool:
        """
        Run database migrations if needed.
        
        Returns:
            True if migrations successful or not needed, False otherwise
        """
        if not self._engine:
            logger.error("No database connection available for migration")
            return False
        
        try:
            from flask_migrate import upgrade
            
            logger.info("🔄 Checking for database migrations...")
            
            # Run migrations in app context
            if self.app:
                with self.app.app_context():
                    upgrade()
                    logger.info("✅ Database migrations completed")
            else:
                logger.warning("No Flask app context available for migrations")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Database migration failed: {e}")
            return False
    
    def test_connection_health(self) -> bool:
        """
        Test the health of the current database connection.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        if not self._engine:
            return False
        
        try:
            with self._engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return True
            
        except Exception as e:
            logger.debug(f"Database health check failed: {e}")
            return False
    
    def reconnect(self) -> bool:
        """
        Attempt to reconnect to the database.
        
        Returns:
            True if reconnection successful, False otherwise
        """
        logger.info("🔄 Attempting database reconnection...")
        
        # Clear current connection
        self._current_database_type = None
        self._current_connection_string = None
        if self._engine:
            self._engine.dispose()
            self._engine = None
        
        # Re-establish connection
        success, db_type, connection_string = self.establish_connection()
        
        if success:
            logger.info(f"✅ Database reconnection successful: {db_type}")
        else:
            logger.error("❌ Database reconnection failed")
        
        return success
    
    @contextmanager
    def get_connection(self):
        """
        Get a database connection context manager.
        
        Yields:
            SQLAlchemy connection
        """
        if not self._engine:
            raise RuntimeError("No database connection available")
        
        connection = self._engine.connect()
        try:
            yield connection
        finally:
            connection.close()
    
    def _get_postgresql_connection_string(self) -> str:
        """Get PostgreSQL connection string from environment."""
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Handle Render.com format
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            return database_url
        
        # Build from individual components
        host = os.environ.get('DB_HOST', 'localhost')
        port = os.environ.get('DB_PORT', '5432')
        database = os.environ.get('DB_NAME', 'ai_secretary')
        username = os.environ.get('DB_USER', 'postgres')
        password = os.environ.get('DB_PASSWORD', '')
        
        if password:
            return f'postgresql://{username}:{password}@{host}:{port}/{database}'
        else:
            return f'postgresql://{username}@{host}:{port}/{database}'
    
    def _get_sqlite_connection_string(self) -> str:
        """Get SQLite connection string."""
        # Check for explicit SQLite URL
        sqlite_url = os.environ.get('SQLITE_DATABASE_URL')
        if sqlite_url:
            return sqlite_url
        
        # Use default SQLite database
        if self.app and self.app.config.get('TESTING'):
            return 'sqlite:///:memory:'
        else:
            return 'sqlite:///ai_secretary.db'
    
    def _mask_password(self, connection_string: str) -> str:
        """Mask password in connection string for logging."""
        if '://' in connection_string and '@' in connection_string:
            # Extract and mask password
            parts = connection_string.split('://', 1)
            if len(parts) == 2:
                protocol = parts[0]
                rest = parts[1]
                
                if '@' in rest:
                    auth_part, host_part = rest.split('@', 1)
                    if ':' in auth_part:
                        username, password = auth_part.split(':', 1)
                        masked_auth = f"{username}:{'*' * len(password)}"
                        return f"{protocol}://{masked_auth}@{host_part}"
        
        return connection_string
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get information about the current database connection.
        
        Returns:
            Dictionary with connection information
        """
        return {
            'database_type': self._current_database_type,
            'connection_string': self._mask_password(self._current_connection_string) if self._current_connection_string else None,
            'is_connected': self._engine is not None,
            'is_healthy': self._health_status,
            'connection_timeout': self.connection_timeout,
            'retry_attempts': self.retry_attempts,
            'last_health_check': self._last_health_check.isoformat() if self._last_health_check else None,
            'health_check_interval': self._health_check_interval,
            'statistics': self._connection_stats.copy()
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get detailed health status information.
        
        Returns:
            Dictionary with health status details
        """
        return {
            'is_healthy': self._health_status,
            'database_type': self._current_database_type,
            'last_check': self._last_health_check.isoformat() if self._last_health_check else None,
            'check_interval_seconds': self._health_check_interval,
            'monitoring_active': self._health_monitor_thread and self._health_monitor_thread.is_alive(),
            'connection_available': self._engine is not None,
            'can_execute_queries': self.test_connection_health() if self._engine else False
        }
    
    def get_connection_statistics(self) -> Dict[str, Any]:
        """
        Get connection statistics.
        
        Returns:
            Dictionary with connection statistics
        """
        stats = self._connection_stats.copy()
        
        # Add calculated metrics
        if stats['total_connections'] > 0:
            stats['success_rate'] = stats['successful_connections'] / stats['total_connections']
            stats['failure_rate'] = stats['failed_connections'] / stats['total_connections']
        else:
            stats['success_rate'] = 0.0
            stats['failure_rate'] = 0.0
        
        # Format datetime objects
        if stats['last_connection_time']:
            stats['last_connection_time'] = stats['last_connection_time'].isoformat()
        if stats['last_failure_time']:
            stats['last_failure_time'] = stats['last_failure_time'].isoformat()
        
        return stats
    
    def reset_statistics(self):
        """Reset connection statistics."""
        self._connection_stats = {
            'total_connections': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'postgresql_attempts': 0,
            'sqlite_fallbacks': 0,
            'last_connection_time': None,
            'last_failure_time': None,
            'last_failure_reason': None
        }
        logger.info("📊 Connection statistics reset")


    def cleanup(self):
        """Clean up resources and stop monitoring."""
        logger.info("🧹 Cleaning up database manager...")
        
        # Stop health monitoring
        self.stop_health_monitoring()
        
        # Dispose of engine
        if self._engine:
            self._engine.dispose()
            self._engine = None
        
        # Clear state
        self._current_database_type = None
        self._current_connection_string = None
        self._health_status = False
        self._health_callbacks.clear()
        
        logger.info("✅ Database manager cleanup completed")
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore errors during cleanup


def get_database_manager(app=None) -> DatabaseManager:
    """
    Get or create database manager instance.
    
    Args:
        app: Optional Flask app instance
        
    Returns:
        DatabaseManager instance
    """
    if app is None:
        app = current_app
    
    if 'database_manager' not in app.extensions:
        manager = DatabaseManager(app)
    else:
        manager = app.extensions['database_manager']
    
    return manager


def initialize_database_with_fallback(app) -> Tuple[bool, str, str]:
    """
    Initialize database connection with automatic fallback.
    
    This is a convenience function that creates a DatabaseManager,
    establishes a connection, and returns the result.
    
    Args:
        app: Flask application instance
        
    Returns:
        Tuple of (success, database_type, connection_string)
    """
    manager = DatabaseManager(app)
    success, db_type, connection_string = manager.establish_connection()
    
    if success:
        logger.info(f"🎉 Database initialized successfully with {db_type}")
        
        # Run migrations if needed
        if manager.migrate_if_needed():
            logger.info("✅ Database migrations completed")
        else:
            logger.warning("⚠️ Database migrations may have failed")
    else:
        logger.error("❌ Failed to initialize database connection")
    
    return success, db_type, connection_string