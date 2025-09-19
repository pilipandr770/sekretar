"""
Smart Database Connection Manager

This module provides intelligent database connection management with
automatic type detection and proper fallback logic.
"""
import os
import time
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import psycopg2
import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Engine

from .database_url_parser import (
    DatabaseURLParser, DatabaseConfig, DatabaseType, ConnectionResult
)
from .error_rate_limiter import get_error_rate_limiter
from .improved_error_messages import log_actionable_error


logger = logging.getLogger(__name__)


class DatabaseConnector(ABC):
    """Abstract base class for database connectors."""
    
    @abstractmethod
    def connect(self, config: DatabaseConfig) -> ConnectionResult:
        """
        Connect to database using the provided configuration.
        
        Args:
            config: Database configuration
            
        Returns:
            ConnectionResult with connection details
        """
        pass
    
    @abstractmethod
    def test_connection(self, engine: Engine) -> bool:
        """
        Test if the database connection is healthy.
        
        Args:
            engine: SQLAlchemy engine to test
            
        Returns:
            True if connection is healthy, False otherwise
        """
        pass


class PostgreSQLConnector(DatabaseConnector):
    """PostgreSQL database connector."""
    
    def __init__(self, connection_timeout: int = 10, retry_attempts: int = 3):
        """
        Initialize PostgreSQL connector.
        
        Args:
            connection_timeout: Connection timeout in seconds
            retry_attempts: Number of retry attempts
        """
        self.connection_timeout = connection_timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = 1  # seconds
    
    def connect(self, config: DatabaseConfig) -> ConnectionResult:
        """Connect to PostgreSQL database."""
        if config.type != DatabaseType.POSTGRESQL:
            return ConnectionResult(
                success=False,
                database_type=config.type,
                connection_string=config.connection_string,
                error_message="Invalid database type for PostgreSQL connector"
            )
        
        connection_string = config.connection_string
        logger.info(f"Attempting PostgreSQL connection: {self._mask_password(connection_string)}")
        
        for attempt in range(self.retry_attempts):
            try:
                start_time = time.time()
                
                # Test connection with psycopg2 first (faster)
                conn = psycopg2.connect(
                    connection_string,
                    connect_timeout=self.connection_timeout
                )
                conn.close()
                
                # Create SQLAlchemy engine
                engine_options = {
                    'pool_pre_ping': True,
                    'pool_timeout': self.connection_timeout,
                    'connect_args': {'connect_timeout': self.connection_timeout}
                }
                
                # Add any additional options from config
                if config.options:
                    connect_args = engine_options.get('connect_args', {})
                    for key, value in config.options.items():
                        if key in ['connect_timeout', 'application_name', 'sslmode']:
                            connect_args[key] = value
                    engine_options['connect_args'] = connect_args
                
                engine = create_engine(connection_string, **engine_options)
                
                # Test the engine connection
                if not self.test_connection(engine):
                    engine.dispose()
                    raise Exception("Engine connection test failed")
                
                connection_time = time.time() - start_time
                logger.info(f"✅ PostgreSQL connection successful (took {connection_time:.2f}s)")
                
                return ConnectionResult(
                    success=True,
                    database_type=DatabaseType.POSTGRESQL,
                    connection_string=connection_string,
                    engine=engine
                )
                
            except Exception as e:
                logger.debug(f"PostgreSQL connection attempt {attempt + 1} failed: {e}")
                
                if attempt < self.retry_attempts - 1:
                    logger.debug(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    # Use rate limiting and improved error messages
                    error_limiter = get_error_rate_limiter()
                    context = {
                        'connection_string': self._mask_password(connection_string), 
                        'attempts': self.retry_attempts,
                        'database_type': 'postgresql',
                        'service_name': 'PostgreSQL Database'
                    }
                    
                    if error_limiter.should_log_error(
                        'PostgreSQLConnectionError',
                        f"Connection failed: {str(e)}",
                        context=context
                    ):
                        # Log with actionable error information
                        log_actionable_error(
                            e, 
                            context=context,
                            log_level='warning',
                            logger_name=__name__
                        )
                    
                    return ConnectionResult(
                        success=False,
                        database_type=DatabaseType.POSTGRESQL,
                        connection_string=connection_string,
                        error_message=str(e)
                    )
        
        return ConnectionResult(
            success=False,
            database_type=DatabaseType.POSTGRESQL,
            connection_string=connection_string,
            error_message="All connection attempts failed"
        )
    
    def test_connection(self, engine: Engine) -> bool:
        """Test PostgreSQL connection health."""
        try:
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return True
        except Exception as e:
            logger.debug(f"PostgreSQL connection test failed: {e}")
            return False
    
    def _mask_password(self, connection_string: str) -> str:
        """Mask password in connection string for logging."""
        if '://' in connection_string and '@' in connection_string:
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


class SQLiteConnector(DatabaseConnector):
    """SQLite database connector."""
    
    def __init__(self, connection_timeout: int = 10):
        """
        Initialize SQLite connector.
        
        Args:
            connection_timeout: Connection timeout in seconds
        """
        self.connection_timeout = connection_timeout
    
    def connect(self, config: DatabaseConfig) -> ConnectionResult:
        """Connect to SQLite database."""
        if config.type != DatabaseType.SQLITE:
            return ConnectionResult(
                success=False,
                database_type=config.type,
                connection_string=config.connection_string,
                error_message="Invalid database type for SQLite connector"
            )
        
        connection_string = config.connection_string
        logger.info(f"Attempting SQLite connection: {connection_string}")
        
        try:
            start_time = time.time()
            
            # Extract database path from connection string
            if connection_string.startswith('sqlite:///'):
                db_path = connection_string[10:]  # Remove 'sqlite:///'
                
                if db_path != ':memory:':
                    # Ensure directory exists for file-based SQLite
                    db_dir = os.path.dirname(db_path)
                    if db_dir and not os.path.exists(db_dir):
                        os.makedirs(db_dir, exist_ok=True)
                        logger.info(f"📁 Created directory for SQLite database: {db_dir}")
                
                # Test connection with sqlite3
                if db_path == ':memory:':
                    conn = sqlite3.connect(':memory:', timeout=self.connection_timeout)
                else:
                    conn = sqlite3.connect(db_path, timeout=self.connection_timeout)
                
                conn.execute('SELECT 1')
                conn.close()
            
            # Create SQLAlchemy engine
            engine_options = {
                'pool_pre_ping': True,
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': self.connection_timeout
                }
            }
            
            # Add any additional options from config
            if config.options:
                connect_args = engine_options.get('connect_args', {})
                for key, value in config.options.items():
                    if key in ['timeout', 'check_same_thread', 'isolation_level']:
                        connect_args[key] = value
                engine_options['connect_args'] = connect_args
            
            engine = create_engine(connection_string, **engine_options)
            
            # Test the engine connection
            if not self.test_connection(engine):
                engine.dispose()
                raise Exception("Engine connection test failed")
            
            connection_time = time.time() - start_time
            logger.info(f"✅ SQLite connection successful (took {connection_time:.2f}s)")
            
            return ConnectionResult(
                success=True,
                database_type=DatabaseType.SQLITE,
                connection_string=connection_string,
                engine=engine
            )
            
        except Exception as e:
            # Use rate limiting and improved error messages
            error_limiter = get_error_rate_limiter()
            context = {
                'connection_string': connection_string,
                'database_type': 'sqlite',
                'service_name': 'SQLite Database'
            }
            
            if error_limiter.should_log_error(
                'SQLiteConnectionError',
                f"Connection failed: {str(e)}",
                context=context
            ):
                # Log with actionable error information
                log_actionable_error(
                    e, 
                    context=context,
                    log_level='error',
                    logger_name=__name__
                )
            
            return ConnectionResult(
                success=False,
                database_type=DatabaseType.SQLITE,
                connection_string=connection_string,
                error_message=str(e)
            )
    
    def test_connection(self, engine: Engine) -> bool:
        """Test SQLite connection health."""
        try:
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return True
        except Exception as e:
            logger.debug(f"SQLite connection test failed: {e}")
            return False


class SmartConnectionManager:
    """
    Smart database connection manager that uses URL parsing to determine
    the correct connection strategy and provides intelligent fallback.
    """
    
    def __init__(self, connection_timeout: int = 10, retry_attempts: int = 3):
        """
        Initialize smart connection manager.
        
        Args:
            connection_timeout: Connection timeout in seconds
            retry_attempts: Number of retry attempts for PostgreSQL
        """
        self.parser = DatabaseURLParser()
        self.connection_timeout = connection_timeout
        self.retry_attempts = retry_attempts
        
        # Initialize connectors
        self.connectors = {
            DatabaseType.POSTGRESQL: PostgreSQLConnector(
                connection_timeout=connection_timeout,
                retry_attempts=retry_attempts
            ),
            DatabaseType.SQLITE: SQLiteConnector(
                connection_timeout=connection_timeout
            )
        }
        
        # Current connection state
        self._current_result: Optional[ConnectionResult] = None
    
    def connect(self, url: Optional[str] = None) -> ConnectionResult:
        """
        Connect using intelligent type detection and fallback.
        
        Args:
            url: Database URL to connect to. If None, uses DATABASE_URL environment variable
            
        Returns:
            ConnectionResult with connection details
        """
        # Get URL from environment if not provided
        if not url:
            url = os.environ.get('DATABASE_URL', '')
        
        # If still no URL, use default SQLite
        if not url:
            logger.info("No DATABASE_URL provided, using default SQLite")
            return self._fallback_to_sqlite()
        
        # Parse the URL
        config = self.parser.parse_url(url)
        
        if not config.is_valid:
            # Use rate limiting and improved error messages
            error_limiter = get_error_rate_limiter()
            context = {
                'url_provided': bool(url), 
                'error': config.error_message,
                'service_name': 'Database Configuration'
            }
            
            if error_limiter.should_log_error(
                'InvalidDatabaseURLError',
                f"Invalid database URL: {config.error_message}",
                context=context
            ):
                # Create a configuration error for better messaging
                config_error = ValueError(f"Invalid database URL: {config.error_message}")
                log_actionable_error(
                    config_error,
                    context=context,
                    log_level='error',
                    logger_name=__name__
                )
                logger.info("Falling back to SQLite due to invalid URL")
            
            return self._fallback_to_sqlite()
        
        # Get appropriate connector
        connector = self.connectors.get(config.type)
        if not connector:
            logger.warning(f"Unsupported database type: {config.type}")
            logger.info("Falling back to SQLite due to unsupported database type")
            return self._fallback_to_sqlite()
        
        # Attempt connection
        logger.info(f"🔍 Connecting to {config.type.value} database...")
        result = connector.connect(config)
        
        if result.success:
            self._current_result = result
            return result
        
        # If PostgreSQL failed, try fallback to SQLite
        if config.type == DatabaseType.POSTGRESQL:
            logger.info("🔄 PostgreSQL connection failed, falling back to SQLite...")
            fallback_result = self._fallback_to_sqlite()
            fallback_result.fallback_used = True
            return fallback_result
        
        # SQLite failed - this is more serious
        logger.error("❌ SQLite connection failed - no fallback available")
        return result
    
    def _fallback_to_sqlite(self) -> ConnectionResult:
        """
        Fallback to SQLite with safe defaults.
        
        Returns:
            ConnectionResult for SQLite connection
        """
        # Try environment-specific SQLite URL first
        sqlite_url = os.environ.get('SQLITE_DATABASE_URL')
        if sqlite_url:
            config = self.parser.parse_url(sqlite_url)
            if config.is_valid and config.type == DatabaseType.SQLITE:
                connector = self.connectors[DatabaseType.SQLITE]
                result = connector.connect(config)
                if result.success:
                    self._current_result = result
                    return result
        
        # Use default SQLite configuration
        config = self.parser.get_default_sqlite_config()
        connector = self.connectors[DatabaseType.SQLITE]
        result = connector.connect(config)
        
        if result.success:
            self._current_result = result
            logger.info("✅ Fallback to SQLite successful")
        else:
            logger.error("❌ Fallback to SQLite failed")
        
        return result
    
    def get_current_connection(self) -> Optional[ConnectionResult]:
        """
        Get the current active connection result.
        
        Returns:
            Current ConnectionResult or None if no connection
        """
        return self._current_result
    
    def test_current_connection(self) -> bool:
        """
        Test the health of the current connection.
        
        Returns:
            True if current connection is healthy, False otherwise
        """
        if not self._current_result or not self._current_result.success:
            return False
        
        connector = self.connectors.get(self._current_result.database_type)
        if not connector:
            return False
        
        return connector.test_connection(self._current_result.engine)
    
    def reconnect(self) -> ConnectionResult:
        """
        Attempt to reconnect using the last successful configuration.
        
        Returns:
            ConnectionResult for reconnection attempt
        """
        if self._current_result:
            # Try to reconnect with the same URL
            return self.connect(self._current_result.connection_string)
        else:
            # No previous connection, try from environment
            return self.connect()
    
    def disconnect(self):
        """Disconnect and clean up current connection."""
        if self._current_result and self._current_result.engine:
            try:
                self._current_result.engine.dispose()
                logger.info("🧹 Database connection disposed")
            except Exception as e:
                logger.warning(f"Error disposing database connection: {e}")
        
        self._current_result = None
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get information about the current connection.
        
        Returns:
            Dictionary with connection information
        """
        if not self._current_result:
            return {
                'connected': False,
                'database_type': None,
                'connection_string': None,
                'fallback_used': False,
                'is_healthy': False
            }
        
        return {
            'connected': self._current_result.success,
            'database_type': self._current_result.database_type.value if self._current_result.database_type else None,
            'connection_string': self._mask_password(self._current_result.connection_string),
            'fallback_used': self._current_result.fallback_used,
            'is_healthy': self.test_current_connection(),
            'error_message': self._current_result.error_message
        }
    
    def _mask_password(self, connection_string: str) -> str:
        """Mask password in connection string for logging."""
        if not connection_string:
            return connection_string
        
        if '://' in connection_string and '@' in connection_string:
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