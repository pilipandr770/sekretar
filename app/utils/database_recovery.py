"""
Database Recovery Handlers

This module provides automated recovery mechanisms for common database initialization issues.
"""
import os
import time
import logging
import sqlite3
import subprocess
from typing import Dict, Any, Optional
from pathlib import Path

from .database_errors import (
    DatabaseErrorCode,
    DatabaseInitializationError,
    ErrorContext,
    get_database_error_handler
)


class DatabaseRecoveryManager:
    """
    Manager for automated database recovery operations.
    
    Provides recovery handlers for common database issues that can be
    automatically resolved without manual intervention.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._register_recovery_handlers()
    
    def _register_recovery_handlers(self):
        """Register all available recovery handlers."""
        error_handler = get_database_error_handler()
        
        # Connection recovery handlers
        error_handler.register_recovery_handler(
            DatabaseErrorCode.CONNECTION_TIMEOUT,
            self._recover_connection_timeout
        )
        
        error_handler.register_recovery_handler(
            DatabaseErrorCode.DATABASE_FILE_LOCKED,
            self._recover_sqlite_file_locked
        )
        
        error_handler.register_recovery_handler(
            DatabaseErrorCode.DATABASE_FILE_NOT_FOUND,
            self._recover_sqlite_file_not_found
        )
        
        # Schema recovery handlers
        error_handler.register_recovery_handler(
            DatabaseErrorCode.SCHEMA_CREATION_FAILED,
            self._recover_schema_creation_failed
        )
        
        # Configuration recovery handlers
        error_handler.register_recovery_handler(
            DatabaseErrorCode.MISSING_DATABASE_URL,
            self._recover_missing_database_url
        )
        
        self.logger.info("Database recovery handlers registered")
    
    def _recover_connection_timeout(
        self,
        error: DatabaseInitializationError,
        context: Optional[ErrorContext]
    ) -> Dict[str, Any]:
        """
        Recover from connection timeout by retrying with exponential backoff.
        
        Args:
            error: The database initialization error
            context: Error context information
            
        Returns:
            Recovery result dictionary
        """
        self.logger.info("Attempting recovery from connection timeout")
        
        max_retries = 3
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                delay = base_delay * (2 ** attempt)
                self.logger.info(f"Retry attempt {attempt + 1}/{max_retries} after {delay}s delay")
                time.sleep(delay)
                
                # Test connection with longer timeout
                if self._test_database_connection(context, timeout=60):
                    self.logger.info("Connection timeout recovery successful")
                    return {
                        'success': True,
                        'method': 'retry_with_backoff',
                        'attempts': attempt + 1,
                        'total_delay': sum(base_delay * (2 ** i) for i in range(attempt + 1))
                    }
                
            except Exception as retry_error:
                self.logger.warning(f"Retry attempt {attempt + 1} failed: {retry_error}")
        
        return {
            'success': False,
            'method': 'retry_with_backoff',
            'attempts': max_retries,
            'reason': 'All retry attempts failed'
        }
    
    def _recover_sqlite_file_locked(
        self,
        error: DatabaseInitializationError,
        context: Optional[ErrorContext]
    ) -> Dict[str, Any]:
        """
        Recover from SQLite file lock by removing lock files and retrying.
        
        Args:
            error: The database initialization error
            context: Error context information
            
        Returns:
            Recovery result dictionary
        """
        self.logger.info("Attempting recovery from SQLite file lock")
        
        if not context or not context.additional_info.get('database_path'):
            return {
                'success': False,
                'method': 'remove_lock_files',
                'reason': 'Database path not available in context'
            }
        
        db_path = context.additional_info['database_path']
        lock_files = [f"{db_path}-shm", f"{db_path}-wal"]
        removed_files = []
        
        try:
            # Wait a moment for any processes to release the lock
            time.sleep(2)
            
            # Remove lock files if they exist
            for lock_file in lock_files:
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                        removed_files.append(lock_file)
                        self.logger.info(f"Removed lock file: {lock_file}")
                    except OSError as e:
                        self.logger.warning(f"Could not remove lock file {lock_file}: {e}")
            
            # Test if database is now accessible
            if self._test_sqlite_access(db_path):
                self.logger.info("SQLite file lock recovery successful")
                return {
                    'success': True,
                    'method': 'remove_lock_files',
                    'removed_files': removed_files
                }
            else:
                return {
                    'success': False,
                    'method': 'remove_lock_files',
                    'reason': 'Database still locked after removing lock files',
                    'removed_files': removed_files
                }
                
        except Exception as recovery_error:
            return {
                'success': False,
                'method': 'remove_lock_files',
                'reason': f'Recovery failed: {str(recovery_error)}',
                'removed_files': removed_files
            }
    
    def _recover_sqlite_file_not_found(
        self,
        error: DatabaseInitializationError,
        context: Optional[ErrorContext]
    ) -> Dict[str, Any]:
        """
        Recover from missing SQLite file by creating directory structure.
        
        Args:
            error: The database initialization error
            context: Error context information
            
        Returns:
            Recovery result dictionary
        """
        self.logger.info("Attempting recovery from missing SQLite file")
        
        if not context or not context.additional_info.get('database_path'):
            return {
                'success': False,
                'method': 'create_directory_structure',
                'reason': 'Database path not available in context'
            }
        
        db_path = context.additional_info['database_path']
        
        try:
            # Create directory structure if it doesn't exist
            db_dir = os.path.dirname(os.path.abspath(db_path))
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                self.logger.info(f"Created database directory: {db_dir}")
            
            # Check if directory is writable
            if not os.access(db_dir, os.W_OK):
                return {
                    'success': False,
                    'method': 'create_directory_structure',
                    'reason': f'Database directory is not writable: {db_dir}'
                }
            
            # Test if we can create the database file
            try:
                # Create empty database file
                conn = sqlite3.connect(db_path)
                conn.close()
                self.logger.info(f"Created SQLite database file: {db_path}")
                
                return {
                    'success': True,
                    'method': 'create_directory_structure',
                    'created_directory': db_dir,
                    'created_file': db_path
                }
                
            except sqlite3.Error as sqlite_error:
                return {
                    'success': False,
                    'method': 'create_directory_structure',
                    'reason': f'Could not create SQLite file: {str(sqlite_error)}'
                }
                
        except Exception as recovery_error:
            return {
                'success': False,
                'method': 'create_directory_structure',
                'reason': f'Recovery failed: {str(recovery_error)}'
            }
    
    def _recover_schema_creation_failed(
        self,
        error: DatabaseInitializationError,
        context: Optional[ErrorContext]
    ) -> Dict[str, Any]:
        """
        Recover from schema creation failure by attempting alternative methods.
        
        Args:
            error: The database initialization error
            context: Error context information
            
        Returns:
            Recovery result dictionary
        """
        self.logger.info("Attempting recovery from schema creation failure")
        
        recovery_methods = []
        
        try:
            # Method 1: Try to run database initialization script
            if self._try_run_init_script():
                recovery_methods.append("init_script")
                return {
                    'success': True,
                    'method': 'run_init_script',
                    'recovery_methods': recovery_methods
                }
            
            # Method 2: Try to create schema using SQLAlchemy metadata
            if self._try_create_schema_with_metadata(context):
                recovery_methods.append("sqlalchemy_metadata")
                return {
                    'success': True,
                    'method': 'sqlalchemy_metadata',
                    'recovery_methods': recovery_methods
                }
            
            return {
                'success': False,
                'method': 'multiple_attempts',
                'reason': 'All schema creation methods failed',
                'attempted_methods': recovery_methods
            }
            
        except Exception as recovery_error:
            return {
                'success': False,
                'method': 'multiple_attempts',
                'reason': f'Recovery failed: {str(recovery_error)}',
                'attempted_methods': recovery_methods
            }
    
    def _recover_missing_database_url(
        self,
        error: DatabaseInitializationError,
        context: Optional[ErrorContext]
    ) -> Dict[str, Any]:
        """
        Recover from missing database URL by setting default SQLite configuration.
        
        Args:
            error: The database initialization error
            context: Error context information
            
        Returns:
            Recovery result dictionary
        """
        self.logger.info("Attempting recovery from missing database URL")
        
        try:
            # Set default SQLite database URL
            default_db_path = os.path.join(os.getcwd(), 'ai_secretary.db')
            default_url = f'sqlite:///{default_db_path}'
            
            # Set environment variable
            os.environ['DATABASE_URL'] = default_url
            
            self.logger.info(f"Set default DATABASE_URL to: {default_url}")
            
            return {
                'success': True,
                'method': 'set_default_sqlite_url',
                'database_url': default_url,
                'database_path': default_db_path
            }
            
        except Exception as recovery_error:
            return {
                'success': False,
                'method': 'set_default_sqlite_url',
                'reason': f'Recovery failed: {str(recovery_error)}'
            }
    
    def _test_database_connection(
        self,
        context: Optional[ErrorContext],
        timeout: int = 30
    ) -> bool:
        """
        Test database connection with specified timeout.
        
        Args:
            context: Error context with connection information
            timeout: Connection timeout in seconds
            
        Returns:
            True if connection successful, False otherwise
        """
        if not context or not context.connection_string:
            return False
        
        try:
            from sqlalchemy import create_engine, text
            
            engine = create_engine(
                context.connection_string,
                connect_args={'timeout': timeout} if 'sqlite' in context.connection_string else {},
                pool_timeout=timeout
            )
            
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            
            engine.dispose()
            return True
            
        except Exception as e:
            self.logger.debug(f"Connection test failed: {e}")
            return False
    
    def _test_sqlite_access(self, db_path: str) -> bool:
        """
        Test if SQLite database file is accessible.
        
        Args:
            db_path: Path to SQLite database file
            
        Returns:
            True if accessible, False otherwise
        """
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            conn.close()
            return True
        except Exception as e:
            self.logger.debug(f"SQLite access test failed: {e}")
            return False
    
    def _try_run_init_script(self) -> bool:
        """
        Try to run database initialization script.
        
        Returns:
            True if successful, False otherwise
        """
        init_scripts = ['init_database.py', 'scripts/init-db.py']
        
        for script in init_scripts:
            if os.path.exists(script):
                try:
                    result = subprocess.run(
                        ['python', script],
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minute timeout
                    )
                    
                    if result.returncode == 0:
                        self.logger.info(f"Successfully ran initialization script: {script}")
                        return True
                    else:
                        self.logger.warning(f"Initialization script failed: {script}")
                        self.logger.warning(f"Script output: {result.stderr}")
                        
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"Initialization script timed out: {script}")
                except Exception as e:
                    self.logger.warning(f"Error running initialization script {script}: {e}")
        
        return False
    
    def _try_create_schema_with_metadata(self, context: Optional[ErrorContext]) -> bool:
        """
        Try to create schema using SQLAlchemy metadata.
        
        Args:
            context: Error context with connection information
            
        Returns:
            True if successful, False otherwise
        """
        if not context or not context.connection_string:
            return False
        
        try:
            from sqlalchemy import create_engine, MetaData
            from app import db
            
            engine = create_engine(context.connection_string)
            
            # Create all tables using SQLAlchemy metadata
            db.metadata.create_all(engine)
            
            engine.dispose()
            self.logger.info("Successfully created schema using SQLAlchemy metadata")
            return True
            
        except Exception as e:
            self.logger.warning(f"Schema creation with metadata failed: {e}")
            return False


# Global recovery manager instance
_recovery_manager = None


def get_database_recovery_manager() -> DatabaseRecoveryManager:
    """Get the global database recovery manager instance."""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = DatabaseRecoveryManager()
    return _recovery_manager


def initialize_recovery_system():
    """Initialize the database recovery system."""
    recovery_manager = get_database_recovery_manager()
    logging.getLogger(__name__).info("Database recovery system initialized")
    return recovery_manager