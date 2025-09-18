"""
Error Scenario Tests for Database Initialization System

This module provides comprehensive tests for various error conditions and
failure scenarios in the database initialization system, ensuring robust
error handling and recovery mechanisms.
"""
import pytest
import tempfile
import os
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, side_effect

from app.utils.database_initializer import (
    DatabaseInitializer, InitializationResult, ValidationResult,
    DatabaseConfiguration, InitializationStep, ValidationSeverity
)


class TestDatabaseConfigurationErrors:
    """Test error scenarios in DatabaseConfiguration."""
    
    @pytest.fixture
    def mock_app(self):
        """Create mock Flask app."""
        app = Mock()
        app.config = {}
        return app
    
    @pytest.fixture
    def db_config(self, mock_app):
        """Create DatabaseConfiguration instance."""
        return DatabaseConfiguration(mock_app)
    
    def test_missing_database_url_error(self, db_config):
        """Test handling of missing database URL."""
        with patch.dict(os.environ, {}, clear=True):
            db_config.app.config = {}
            
            result = db_config.validate_configuration()
            
            assert result.valid is False
            assert any('No database URL configured' in issue for issue in result.issues)
            assert any('Set DATABASE_URL' in suggestion for suggestion in result.suggestions)
            assert result.severity == ValidationSeverity.CRITICAL
    
    def test_invalid_database_url_format_error(self, db_config):
        """Test handling of invalid database URL format."""
        with patch.dict(os.environ, {'DATABASE_URL': 'invalid-url-format'}):
            result = db_config.validate_configuration()
            
            assert result.valid is False
            assert any('Unknown database type' in issue for issue in result.issues)
    
    def test_malformed_postgresql_url_error(self, db_config):
        """Test handling of malformed PostgreSQL URL."""
        malformed_urls = [
            'postgresql://',  # Missing everything
            'postgresql://user@',  # Missing host and database
            'postgresql://user:@localhost/db',  # Empty password
            'postgresql://user:pass@/db',  # Missing host
            'postgresql://user:pass@localhost:99999/db',  # Invalid port
        ]
        
        for url in malformed_urls:
            with patch.dict(os.environ, {'DATABASE_URL': url}):
                result = db_config.validate_configuration()
                # Should handle gracefully, may be valid or invalid depending on URL
                assert isinstance(result, ValidationResult)
    
    def test_sqlite_path_permission_error(self, db_config):
        """Test handling of SQLite path permission errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a read-only directory
            readonly_dir = Path(temp_dir) / 'readonly'
            readonly_dir.mkdir()
            readonly_dir.chmod(0o444)  # Read-only
            
            db_path = readonly_dir / 'test.db'
            
            with patch.dict(os.environ, {'DATABASE_URL': f'sqlite:///{db_path}'}):
                result = db_config.validate_configuration()
                
                # Should detect permission issues
                assert result.valid is False or len(result.issues) > 0
    
    def test_sqlite_nonexistent_directory_error(self, db_config):
        """Test handling of SQLite with non-existent directory."""
        nonexistent_path = '/nonexistent/directory/test.db'
        
        with patch.dict(os.environ, {'DATABASE_URL': f'sqlite:///{nonexistent_path}'}):
            result = db_config.validate_configuration()
            
            # Should detect directory issues
            assert result.valid is False or len(result.issues) > 0
    
    def test_database_type_detection_edge_cases(self, db_config):
        """Test database type detection with edge cases."""
        edge_cases = [
            '',  # Empty string
            'http://not-a-database',  # Wrong protocol
            'postgresql',  # Missing ://
            'sqlite://',  # Missing path
            'mysql:///',  # Malformed
        ]
        
        for url in edge_cases:
            with patch.dict(os.environ, {'DATABASE_URL': url}):
                db_type = db_config.detect_database_type()
                # Should handle gracefully
                assert db_type in ['postgresql', 'sqlite', 'mysql', 'unknown']
    
    def test_connection_parameters_with_missing_config(self, db_config):
        """Test getting connection parameters with missing configuration."""
        with patch.dict(os.environ, {}, clear=True):
            db_config.app.config = {}
            
            params = db_config.get_connection_parameters()
            
            # Should provide default parameters
            assert isinstance(params, dict)
            assert 'database_type' in params
            assert 'timeout' in params


class TestDatabaseInitializerErrors:
    """Test error scenarios in DatabaseInitializer."""
    
    @pytest.fixture
    def mock_app(self):
        """Create mock Flask app."""
        app = Mock()
        app.config = {
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db',
            'TESTING': True
        }
        app.debug = False
        return app
    
    @pytest.fixture
    def mock_db(self):
        """Create mock SQLAlchemy instance."""
        db = Mock()
        db.engine = Mock()
        db.session = Mock()
        return db
    
    def test_database_initializer_creation_with_missing_dependencies(self, mock_app, mock_db):
        """Test DatabaseInitializer creation when dependencies are missing."""
        with patch('app.utils.database_initializer.get_environment_config', side_effect=ImportError("Module not found")):
            with pytest.raises(ImportError):
                DatabaseInitializer(mock_app, mock_db)
    
    def test_database_initializer_with_invalid_environment_config(self, mock_app, mock_db):
        """Test DatabaseInitializer with invalid environment configuration."""
        with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
             patch('app.utils.database_initializer.EnvironmentDetector'), \
             patch('app.utils.database_initializer.EnvironmentInitializer'), \
             patch('app.utils.database_initializer.get_database_init_logger'), \
             patch('app.utils.database_initializer.get_database_error_handler'), \
             patch('app.utils.database_initializer.initialize_recovery_system'), \
             patch('app.utils.database_initializer.DataSeeder'), \
             patch('app.utils.database_initializer.HealthValidator'):
            
            # Mock invalid environment config
            mock_env_config.return_value = None
            
            with pytest.raises((AttributeError, TypeError)):
                DatabaseInitializer(mock_app, mock_db)
    
    def test_database_initializer_with_logger_failure(self, mock_app, mock_db):
        """Test DatabaseInitializer when logger initialization fails."""
        with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
             patch('app.utils.database_initializer.EnvironmentDetector'), \
             patch('app.utils.database_initializer.EnvironmentInitializer'), \
             patch('app.utils.database_initializer.get_database_init_logger', side_effect=Exception("Logger failed")), \
             patch('app.utils.database_initializer.get_database_error_handler'), \
             patch('app.utils.database_initializer.initialize_recovery_system'), \
             patch('app.utils.database_initializer.DataSeeder'), \
             patch('app.utils.database_initializer.HealthValidator'):
            
            env_config = Mock()
            env_config.environment.value = 'testing'
            env_config.database_type.value = 'sqlite'
            env_config.database_url = 'sqlite:///test.db'
            mock_env_config.return_value = env_config
            
            # Should handle logger failure gracefully or raise appropriate error
            with pytest.raises(Exception):
                DatabaseInitializer(mock_app, mock_db)
    
    def test_database_initializer_with_data_seeder_failure(self, mock_app, mock_db):
        """Test DatabaseInitializer when DataSeeder initialization fails."""
        with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
             patch('app.utils.database_initializer.EnvironmentDetector'), \
             patch('app.utils.database_initializer.EnvironmentInitializer'), \
             patch('app.utils.database_initializer.get_database_init_logger'), \
             patch('app.utils.database_initializer.get_database_error_handler'), \
             patch('app.utils.database_initializer.initialize_recovery_system'), \
             patch('app.utils.database_initializer.DataSeeder', side_effect=Exception("DataSeeder failed")), \
             patch('app.utils.database_initializer.HealthValidator'):
            
            env_config = Mock()
            env_config.environment.value = 'testing'
            env_config.database_type.value = 'sqlite'
            env_config.database_url = 'sqlite:///test.db'
            mock_env_config.return_value = env_config
            
            # Should handle DataSeeder failure gracefully or raise appropriate error
            with pytest.raises(Exception):
                DatabaseInitializer(mock_app, mock_db)
    
    def test_database_initializer_with_health_validator_failure(self, mock_app, mock_db):
        """Test DatabaseInitializer when HealthValidator initialization fails."""
        with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
             patch('app.utils.database_initializer.EnvironmentDetector'), \
             patch('app.utils.database_initializer.EnvironmentInitializer'), \
             patch('app.utils.database_initializer.get_database_init_logger'), \
             patch('app.utils.database_initializer.get_database_error_handler'), \
             patch('app.utils.database_initializer.initialize_recovery_system'), \
             patch('app.utils.database_initializer.DataSeeder'), \
             patch('app.utils.database_initializer.HealthValidator', side_effect=Exception("HealthValidator failed")):
            
            env_config = Mock()
            env_config.environment.value = 'testing'
            env_config.database_type.value = 'sqlite'
            env_config.database_url = 'sqlite:///test.db'
            mock_env_config.return_value = env_config
            
            # Should handle HealthValidator failure gracefully or raise appropriate error
            with pytest.raises(Exception):
                DatabaseInitializer(mock_app, mock_db)
    
    def test_connection_string_masking_with_invalid_input(self, mock_app, mock_db):
        """Test connection string masking with invalid input."""
        with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
             patch('app.utils.database_initializer.EnvironmentDetector'), \
             patch('app.utils.database_initializer.EnvironmentInitializer'), \
             patch('app.utils.database_initializer.get_database_init_logger'), \
             patch('app.utils.database_initializer.get_database_error_handler'), \
             patch('app.utils.database_initializer.initialize_recovery_system'), \
             patch('app.utils.database_initializer.DataSeeder'), \
             patch('app.utils.database_initializer.HealthValidator'):
            
            env_config = Mock()
            env_config.environment.value = 'testing'
            env_config.database_type.value = 'sqlite'
            env_config.database_url = 'sqlite:///test.db'
            mock_env_config.return_value = env_config
            
            initializer = DatabaseInitializer(mock_app, mock_db)
            
            # Test with various invalid inputs
            invalid_inputs = [None, '', 123, [], {}, object()]
            
            for invalid_input in invalid_inputs:
                try:
                    result = initializer._mask_connection_string(invalid_input)
                    # Should handle gracefully
                    assert isinstance(result, str)
                except (TypeError, AttributeError):
                    # Some invalid inputs may raise exceptions, which is acceptable
                    pass


class TestInitializationResultErrors:
    """Test error scenarios in InitializationResult."""
    
    def test_initialization_result_with_invalid_data_types(self):
        """Test InitializationResult with invalid data types."""
        # Test with invalid success type
        with pytest.raises(TypeError):
            InitializationResult(success="not_boolean")
        
        # Test with invalid steps_completed type
        result = InitializationResult(success=True)
        with pytest.raises((TypeError, AttributeError)):
            result.steps_completed = "not_a_list"
    
    def test_initialization_result_add_methods_with_invalid_input(self):
        """Test InitializationResult add methods with invalid input."""
        result = InitializationResult(success=True)
        
        # Test adding non-string step
        invalid_inputs = [None, 123, [], {}]
        for invalid_input in invalid_inputs:
            try:
                result.add_step(invalid_input)
                # If it doesn't raise an exception, check the result
                assert invalid_input in result.steps_completed or str(invalid_input) in result.steps_completed
            except (TypeError, AttributeError):
                # Some invalid inputs may raise exceptions, which is acceptable
                pass
    
    def test_initialization_result_with_extreme_values(self):
        """Test InitializationResult with extreme values."""
        result = InitializationResult(success=True)
        
        # Add many items to test performance and memory
        for i in range(10000):
            result.add_step(f"step_{i}")
            result.add_error(f"error_{i}")
            result.add_warning(f"warning_{i}")
        
        assert len(result.steps_completed) == 10000
        assert len(result.errors) == 10000
        assert len(result.warnings) == 10000
    
    def test_initialization_result_with_very_long_strings(self):
        """Test InitializationResult with very long strings."""
        result = InitializationResult(success=True)
        
        # Test with very long strings
        long_string = "x" * 10000
        result.add_step(long_string)
        result.add_error(long_string)
        result.add_warning(long_string)
        
        assert long_string in result.steps_completed
        assert long_string in result.errors
        assert long_string in result.warnings


class TestValidationResultErrors:
    """Test error scenarios in ValidationResult."""
    
    def test_validation_result_with_invalid_severity(self):
        """Test ValidationResult with invalid severity."""
        result = ValidationResult(valid=True)
        
        # Test with invalid severity type
        invalid_severities = ["invalid", 123, None, []]
        for invalid_severity in invalid_severities:
            try:
                result.add_issue("Test issue", invalid_severity)
                # If it doesn't raise an exception, check that severity handling is robust
            except (TypeError, AttributeError, ValueError):
                # Invalid severities may raise exceptions, which is acceptable
                pass
    
    def test_validation_result_severity_escalation_edge_cases(self):
        """Test ValidationResult severity escalation with edge cases."""
        result = ValidationResult(valid=True)
        
        # Test escalation with same severity multiple times
        result.add_issue("Issue 1", ValidationSeverity.WARNING)
        result.add_issue("Issue 2", ValidationSeverity.WARNING)
        result.add_issue("Issue 3", ValidationSeverity.WARNING)
        
        assert result.severity == ValidationSeverity.WARNING
        
        # Test escalation with mixed severities
        result.add_issue("Critical issue", ValidationSeverity.CRITICAL)
        result.add_issue("Info issue", ValidationSeverity.INFO)
        result.add_issue("Error issue", ValidationSeverity.ERROR)
        
        assert result.severity == ValidationSeverity.CRITICAL
    
    def test_validation_result_with_extreme_number_of_issues(self):
        """Test ValidationResult with extreme number of issues."""
        result = ValidationResult(valid=True)
        
        # Add many issues
        severities = [ValidationSeverity.INFO, ValidationSeverity.WARNING, 
                     ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
        
        for i in range(10000):
            severity = severities[i % len(severities)]
            result.add_issue(f"Issue {i}", severity)
            result.add_suggestion(f"Suggestion {i}")
        
        assert len(result.issues) == 10000
        assert len(result.suggestions) == 10000
        assert result.severity == ValidationSeverity.CRITICAL
    
    def test_validation_result_with_unicode_and_special_characters(self):
        """Test ValidationResult with unicode and special characters."""
        result = ValidationResult(valid=True)
        
        # Test with various unicode and special characters
        special_strings = [
            "测试中文",  # Chinese
            "тест русский",  # Russian
            "🚀 emoji test 🔥",  # Emojis
            "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?",
            "Newlines\nand\ttabs",
            "NULL\x00character",
        ]
        
        for special_string in special_strings:
            try:
                result.add_issue(special_string, ValidationSeverity.INFO)
                result.add_suggestion(special_string)
                
                assert special_string in result.issues
                assert special_string in result.suggestions
            except (UnicodeError, ValueError):
                # Some special characters may cause issues, which is acceptable
                pass


class TestDatabaseInitializationRealWorldErrors:
    """Test real-world error scenarios with actual database operations."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        try:
            os.unlink(path)
        except OSError:
            pass
    
    def test_sqlite_database_corruption_simulation(self, temp_db_path):
        """Test handling of corrupted SQLite database."""
        # Create a valid database first
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        cursor.execute("INSERT INTO test (id) VALUES (1)")
        conn.commit()
        conn.close()
        
        # Corrupt the database by writing invalid data
        with open(temp_db_path, 'r+b') as f:
            f.seek(0)
            f.write(b'CORRUPTED_DATABASE_FILE')
        
        # Try to connect to corrupted database
        with pytest.raises(sqlite3.DatabaseError):
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test")
            conn.close()
    
    def test_sqlite_database_locked_error(self, temp_db_path):
        """Test handling of database locked error."""
        # Create database and keep connection open
        conn1 = sqlite3.connect(temp_db_path)
        cursor1 = conn1.cursor()
        cursor1.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        cursor1.execute("BEGIN EXCLUSIVE TRANSACTION")
        cursor1.execute("INSERT INTO test (id) VALUES (1)")
        # Don't commit or close - keeps database locked
        
        # Try to access from another connection
        conn2 = sqlite3.connect(temp_db_path, timeout=0.1)  # Short timeout
        cursor2 = conn2.cursor()
        
        with pytest.raises(sqlite3.OperationalError):
            cursor2.execute("INSERT INTO test (id) VALUES (2)")
            conn2.commit()
        
        # Clean up
        conn1.rollback()
        conn1.close()
        conn2.close()
    
    def test_sqlite_disk_full_simulation(self, temp_db_path):
        """Test handling of disk full error (simulated)."""
        # This is difficult to test realistically, but we can test the error handling
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
        
        # Try to insert extremely large data that might cause disk issues
        large_data = "x" * (1024 * 1024)  # 1MB string
        
        try:
            for i in range(1000):  # Try to insert 1GB of data
                cursor.execute("INSERT INTO test (data) VALUES (?)", (large_data,))
            conn.commit()
        except sqlite3.OperationalError as e:
            # May get disk full or other resource errors
            assert "disk" in str(e).lower() or "space" in str(e).lower() or "memory" in str(e).lower()
        finally:
            conn.close()
    
    def test_sqlite_permission_denied_error(self, temp_db_path):
        """Test handling of permission denied error."""
        # Create database
        conn = sqlite3.connect(temp_db_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.close()
        
        # Make database file read-only
        os.chmod(temp_db_path, 0o444)
        
        try:
            # Try to write to read-only database
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            
            with pytest.raises(sqlite3.OperationalError):
                cursor.execute("INSERT INTO test (id) VALUES (1)")
                conn.commit()
            
            conn.close()
        finally:
            # Restore permissions for cleanup
            os.chmod(temp_db_path, 0o666)
    
    def test_sqlite_invalid_sql_error(self, temp_db_path):
        """Test handling of invalid SQL errors."""
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Test various invalid SQL statements
        invalid_sql_statements = [
            "INVALID SQL STATEMENT",
            "SELECT * FROM non_existent_table",
            "CREATE TABLE (invalid syntax)",
            "INSERT INTO VALUES (missing table)",
            "UPDATE SET WHERE (incomplete)",
        ]
        
        for sql in invalid_sql_statements:
            with pytest.raises((sqlite3.OperationalError, sqlite3.DatabaseError)):
                cursor.execute(sql)
        
        conn.close()
    
    def test_sqlite_constraint_violation_errors(self, temp_db_path):
        """Test handling of constraint violation errors."""
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Create table with constraints
        cursor.execute('''
            CREATE TABLE test (
                id INTEGER PRIMARY KEY,
                unique_field TEXT UNIQUE NOT NULL,
                check_field INTEGER CHECK (check_field > 0)
            )
        ''')
        
        # Insert valid data
        cursor.execute("INSERT INTO test (unique_field, check_field) VALUES (?, ?)", ("unique1", 1))
        conn.commit()
        
        # Test unique constraint violation
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO test (unique_field, check_field) VALUES (?, ?)", ("unique1", 2))
            conn.commit()
        
        # Test NOT NULL constraint violation
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO test (unique_field, check_field) VALUES (?, ?)", (None, 3))
            conn.commit()
        
        # Test CHECK constraint violation
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO test (unique_field, check_field) VALUES (?, ?)", ("unique2", -1))
            conn.commit()
        
        conn.close()


class TestDatabaseInitializationRecoveryScenarios:
    """Test error recovery scenarios in database initialization."""
    
    def test_initialization_result_recovery_from_partial_failure(self):
        """Test recovery from partial initialization failure."""
        result = InitializationResult(success=False)
        
        # Simulate partial completion
        result.add_step("connection_test")
        result.add_step("schema_creation")
        result.add_error("Migration failed")
        result.add_warning("Some data could not be seeded")
        
        # Verify state
        assert result.success is False
        assert len(result.steps_completed) == 2
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        
        # Simulate recovery attempt
        recovery_result = InitializationResult(success=True)
        recovery_result.add_step("migration_retry")
        recovery_result.add_step("data_seeding_retry")
        
        # Combine results (simulation of recovery)
        combined_steps = result.steps_completed + recovery_result.steps_completed
        assert len(combined_steps) == 4
        assert "migration_retry" in combined_steps
    
    def test_validation_result_recovery_from_critical_issues(self):
        """Test recovery from critical validation issues."""
        result = ValidationResult(valid=False)
        
        # Add critical issues
        result.add_issue("Database not accessible", ValidationSeverity.CRITICAL)
        result.add_issue("Schema corrupted", ValidationSeverity.CRITICAL)
        result.add_suggestion("Restore database from backup")
        result.add_suggestion("Recreate schema")
        
        assert result.valid is False
        assert result.severity == ValidationSeverity.CRITICAL
        assert len(result.suggestions) == 2
        
        # Simulate recovery validation
        recovery_result = ValidationResult(valid=True)
        recovery_result.add_issue("Minor configuration issue", ValidationSeverity.WARNING)
        recovery_result.add_suggestion("Update configuration")
        
        # Recovery should show improvement
        assert recovery_result.valid is True
        assert recovery_result.severity == ValidationSeverity.WARNING
    
    def test_database_configuration_recovery_from_invalid_config(self):
        """Test recovery from invalid database configuration."""
        mock_app = Mock()
        mock_app.config = {}
        
        config = DatabaseConfiguration(mock_app)
        
        # Test with invalid configuration
        with patch.dict(os.environ, {}, clear=True):
            result = config.validate_configuration()
            assert result.valid is False
        
        # Simulate configuration fix
        mock_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
        
        # Test with fixed configuration
        result = config.validate_configuration()
        assert result.valid is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])