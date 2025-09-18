"""
Tests for Database Error Handling and Recovery System

This module tests the comprehensive error handling, recovery mechanisms,
and user-friendly error messages for database initialization failures.
"""
import os
import pytest
import tempfile
import sqlite3
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.utils.database_errors import (
    DatabaseErrorHandler,
    DatabaseErrorCode,
    ErrorContext,
    ErrorSeverity,
    DatabaseInitializationError,
    DatabaseConnectionError,
    DatabaseSchemaError,
    handle_database_error,
    create_error_context
)
from app.utils.database_recovery import DatabaseRecoveryManager
from app.utils.database_error_logger import DatabaseErrorLogger


class TestDatabaseErrorHandler:
    """Test the DatabaseErrorHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = DatabaseErrorHandler()
    
    def test_classify_connection_refused_error(self):
        """Test classification of connection refused errors."""
        error = Exception("connection refused")
        context = create_error_context(database_type="postgresql", operation="connection_test")
        
        error_code, db_error = self.error_handler._classify_error(error, context)
        
        assert error_code == DatabaseErrorCode.CONNECTION_REFUSED
        assert isinstance(db_error, DatabaseConnectionError)
        assert "connection was refused" in str(db_error).lower()
    
    def test_classify_authentication_failed_error(self):
        """Test classification of authentication failed errors."""
        error = Exception("authentication failed for user")
        context = create_error_context(database_type="postgresql", operation="connection_test")
        
        error_code, db_error = self.error_handler._classify_error(error, context)
        
        assert error_code == DatabaseErrorCode.AUTHENTICATION_FAILED
        assert isinstance(db_error, DatabaseConnectionError)
        assert "authentication failed" in str(db_error).lower()
    
    def test_classify_schema_error(self):
        """Test classification of schema-related errors."""
        error = Exception("no such table: users")
        context = create_error_context(database_type="sqlite", operation="schema_check")
        
        error_code, db_error = self.error_handler._classify_error(error, context)
        
        assert error_code == DatabaseErrorCode.SCHEMA_CREATION_FAILED
        assert isinstance(db_error, DatabaseSchemaError)
        assert "required database tables are missing" in str(db_error).lower()
    
    def test_classify_sqlite_file_locked_error(self):
        """Test classification of SQLite file locked errors."""
        error = Exception("database is locked")
        context = create_error_context(database_type="sqlite", operation="connection_test")
        
        error_code, db_error = self.error_handler._classify_error(error, context)
        
        assert error_code == DatabaseErrorCode.DATABASE_FILE_LOCKED
        assert "locked by another process" in str(db_error).lower()
    
    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        error = Exception("some unknown database error")
        context = create_error_context(database_type="postgresql", operation="unknown")
        
        error_code, db_error = self.error_handler._classify_error(error, context)
        
        assert error_code == DatabaseErrorCode.UNKNOWN_ERROR
        assert isinstance(db_error, DatabaseInitializationError)
    
    def test_handle_error_with_context(self):
        """Test error handling with context information."""
        error = Exception("connection refused")
        context = create_error_context(
            database_type="postgresql",
            connection_string="postgresql://user:pass@localhost:5432/db",
            operation="connection_test"
        )
        
        result = self.error_handler.handle_error(error, context, auto_recover=False)
        
        assert result['error_code'] == DatabaseErrorCode.CONNECTION_REFUSED.value
        assert result['severity'] == ErrorSeverity.CRITICAL.value
        assert 'resolution' in result
        assert 'recovery_steps' in result['resolution']
        assert len(result['resolution']['recovery_steps']) > 0
    
    def test_handle_error_without_context(self):
        """Test error handling without context information."""
        error = Exception("some database error")
        
        result = self.error_handler.handle_error(error, auto_recover=False)
        
        assert 'error_code' in result
        assert 'message' in result
        assert 'severity' in result
        assert 'resolution' in result
    
    def test_error_history_tracking(self):
        """Test error history tracking."""
        initial_count = len(self.error_handler.get_error_history())
        
        error = Exception("test error")
        self.error_handler.handle_error(error, auto_recover=False)
        
        history = self.error_handler.get_error_history()
        assert len(history) == initial_count + 1
        assert history[-1]['message'] == str(error)
    
    def test_error_statistics(self):
        """Test error statistics generation."""
        # Generate some test errors
        for i in range(5):
            error = Exception(f"test error {i}")
            self.error_handler.handle_error(error, auto_recover=False)
        
        stats = self.error_handler.get_error_statistics()
        
        assert 'total_errors' in stats
        assert stats['total_errors'] >= 5
        assert 'error_counts' in stats
        assert 'severity_counts' in stats
    
    def test_clear_error_history(self):
        """Test clearing error history."""
        # Add some errors
        error = Exception("test error")
        self.error_handler.handle_error(error, auto_recover=False)
        
        assert len(self.error_handler.get_error_history()) > 0
        
        self.error_handler.clear_error_history()
        assert len(self.error_handler.get_error_history()) == 0


class TestDatabaseRecoveryManager:
    """Test the DatabaseRecoveryManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.recovery_manager = DatabaseRecoveryManager()
    
    def test_recovery_connection_timeout(self):
        """Test recovery from connection timeout."""
        error = DatabaseInitializationError(
            "Connection timeout",
            DatabaseErrorCode.CONNECTION_TIMEOUT
        )
        context = create_error_context(
            database_type="postgresql",
            connection_string="postgresql://user:pass@localhost:5432/db"
        )
        
        with patch.object(self.recovery_manager, '_test_database_connection', return_value=True):
            result = self.recovery_manager._recover_connection_timeout(error, context)
            
            assert result['success'] is True
            assert result['method'] == 'retry_with_backoff'
            assert 'attempts' in result
    
    def test_recovery_sqlite_file_not_found(self):
        """Test recovery from missing SQLite file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "subdir", "test.db")
            
            error = DatabaseInitializationError(
                "Database file not found",
                DatabaseErrorCode.DATABASE_FILE_NOT_FOUND
            )
            context = create_error_context(
                database_type="sqlite",
                database_path=db_path
            )
            context.additional_info['database_path'] = db_path
            
            result = self.recovery_manager._recover_sqlite_file_not_found(error, context)
            
            assert result['success'] is True
            assert result['method'] == 'create_directory_structure'
            assert os.path.exists(os.path.dirname(db_path))
            assert os.path.exists(db_path)
    
    def test_recovery_sqlite_file_locked(self):
        """Test recovery from SQLite file lock."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            lock_file = f"{db_path}-shm"
            
            # Create database and lock file
            conn = sqlite3.connect(db_path)
            conn.close()
            
            with open(lock_file, 'w') as f:
                f.write("lock")
            
            error = DatabaseInitializationError(
                "Database file locked",
                DatabaseErrorCode.DATABASE_FILE_LOCKED
            )
            context = create_error_context(database_type="sqlite")
            context.additional_info['database_path'] = db_path
            
            result = self.recovery_manager._recover_sqlite_file_locked(error, context)
            
            assert result['success'] is True
            assert result['method'] == 'remove_lock_files'
            assert not os.path.exists(lock_file)
    
    def test_recovery_missing_database_url(self):
        """Test recovery from missing database URL."""
        error = DatabaseInitializationError(
            "Missing database URL",
            DatabaseErrorCode.MISSING_DATABASE_URL
        )
        
        # Clear any existing DATABASE_URL
        original_url = os.environ.get('DATABASE_URL')
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        
        try:
            result = self.recovery_manager._recover_missing_database_url(error, None)
            
            assert result['success'] is True
            assert result['method'] == 'set_default_sqlite_url'
            assert 'DATABASE_URL' in os.environ
            assert os.environ['DATABASE_URL'].startswith('sqlite:///')
        
        finally:
            # Restore original URL
            if original_url:
                os.environ['DATABASE_URL'] = original_url
            elif 'DATABASE_URL' in os.environ:
                del os.environ['DATABASE_URL']


class TestDatabaseErrorLogger:
    """Test the DatabaseErrorLogger class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.error_logger = DatabaseErrorLogger(log_dir=self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        try:
            # Close any open file handlers
            for handler in self.error_logger.logger.handlers[:]:
                handler.close()
                self.error_logger.logger.removeHandler(handler)
            
            # Remove temporary directory
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass
    
    def test_log_database_error(self):
        """Test logging database errors."""
        self.error_logger.log_database_error(
            error_code=DatabaseErrorCode.CONNECTION_REFUSED,
            message="Test connection error",
            severity=ErrorSeverity.HIGH,
            context={'database_type': 'postgresql'},
            recovery_attempted=True,
            recovery_successful=False
        )
        
        # Check that error was recorded
        assert len(self.error_logger._recent_errors) > 0
        recent_error = self.error_logger._recent_errors[-1]
        
        assert recent_error['error_code'] == DatabaseErrorCode.CONNECTION_REFUSED.value
        assert recent_error['message'] == "Test connection error"
        assert recent_error['severity'] == ErrorSeverity.HIGH.value
        assert recent_error['recovery_attempted'] is True
        assert recent_error['recovery_successful'] is False
    
    def test_log_recovery_attempt(self):
        """Test logging recovery attempts."""
        self.error_logger.log_recovery_attempt(
            error_code=DatabaseErrorCode.CONNECTION_TIMEOUT,
            recovery_method="retry_with_backoff",
            success=True,
            details={'attempts': 2}
        )
        
        # This should be logged but not affect recent_errors
        # (recovery attempts are separate from errors)
    
    def test_get_error_summary(self):
        """Test error summary generation."""
        # Add some test errors
        for i in range(3):
            self.error_logger.log_database_error(
                error_code=DatabaseErrorCode.CONNECTION_REFUSED,
                message=f"Test error {i}",
                severity=ErrorSeverity.HIGH,
                recovery_attempted=i % 2 == 0,
                recovery_successful=i == 0
            )
        
        summary = self.error_logger.get_error_summary(hours=1)
        
        assert summary['total_errors'] == 3
        assert DatabaseErrorCode.CONNECTION_REFUSED.value in summary['error_counts']
        assert summary['error_counts'][DatabaseErrorCode.CONNECTION_REFUSED.value] == 3
        assert summary['recovery_stats']['attempted'] == 2
        assert summary['recovery_stats']['successful'] == 1
    
    def test_get_error_patterns(self):
        """Test error pattern analysis."""
        # Create a pattern of repeated errors
        for i in range(5):
            self.error_logger.log_database_error(
                error_code=DatabaseErrorCode.CONNECTION_REFUSED,
                message=f"Repeated error {i}",
                severity=ErrorSeverity.HIGH
            )
        
        patterns = self.error_logger.get_error_patterns()
        
        assert 'patterns' in patterns
        assert 'trends' in patterns
        
        # Should detect the repeated error pattern
        repeated_patterns = [p for p in patterns['patterns'] if p['pattern'] == 'repeated_error']
        assert len(repeated_patterns) > 0
    
    def test_generate_troubleshooting_report(self):
        """Test troubleshooting report generation."""
        # Add some test data
        self.error_logger.log_database_error(
            error_code=DatabaseErrorCode.CONNECTION_REFUSED,
            message="Test error for report",
            severity=ErrorSeverity.CRITICAL,
            context={'database_type': 'postgresql'}
        )
        
        report = self.error_logger.generate_troubleshooting_report(hours=1)
        
        assert 'report_metadata' in report
        assert 'error_summary' in report
        assert 'error_patterns' in report
        assert 'recent_errors' in report
        assert 'recommendations' in report
        assert 'log_files' in report
        
        # Check metadata
        metadata = report['report_metadata']
        assert metadata['time_period_hours'] == 1
        assert metadata['total_errors_analyzed'] >= 1


class TestErrorContext:
    """Test the ErrorContext class."""
    
    def test_create_error_context(self):
        """Test creating error context."""
        context = create_error_context(
            database_type="postgresql",
            connection_string="postgresql://user:pass@localhost:5432/db",
            operation="connection_test",
            custom_field="custom_value"
        )
        
        assert context.database_type == "postgresql"
        assert context.connection_string == "postgresql://user:pass@localhost:5432/db"
        assert context.operation == "connection_test"
        assert context.additional_info['custom_field'] == "custom_value"
        assert isinstance(context.timestamp, datetime)


class TestIntegration:
    """Integration tests for the complete error handling system."""
    
    def test_end_to_end_error_handling(self):
        """Test complete error handling flow."""
        # Simulate a database connection error
        error = Exception("connection refused")
        context = create_error_context(
            database_type="postgresql",
            connection_string="postgresql://user:pass@localhost:5432/db",
            operation="connection_test"
        )
        
        # Handle the error
        result = handle_database_error(error, context, auto_recover=False)
        
        # Verify the result contains all expected information
        assert 'error_code' in result
        assert 'message' in result
        assert 'severity' in result
        assert 'resolution' in result
        assert 'context' in result
        assert 'timestamp' in result
        
        # Verify resolution contains recovery steps
        resolution = result['resolution']
        assert 'title' in resolution
        assert 'description' in resolution
        assert 'recovery_steps' in resolution
        assert len(resolution['recovery_steps']) > 0
        
        # Verify recovery steps have required fields
        for step in resolution['recovery_steps']:
            assert 'action' in step
            assert 'description' in step
            assert 'automated' in step
            assert 'risk_level' in step
    
    def test_error_handler_with_recovery(self):
        """Test error handler with recovery enabled."""
        with patch('app.utils.database_recovery.DatabaseRecoveryManager') as mock_recovery:
            # Mock successful recovery
            mock_recovery.return_value._recover_connection_timeout.return_value = {
                'success': True,
                'method': 'retry_with_backoff',
                'attempts': 2
            }
            
            error = Exception("connection timeout")
            context = create_error_context(
                database_type="postgresql",
                operation="connection_test"
            )
            
            result = handle_database_error(error, context, auto_recover=True)
            
            assert 'recovery_result' in result
            # Note: The actual recovery result depends on the mock setup


if __name__ == '__main__':
    pytest.main([__file__])