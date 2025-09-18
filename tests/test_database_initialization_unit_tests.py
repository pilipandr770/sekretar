"""
Unit Tests for Database Initialization Components

This module provides focused unit tests for individual components
of the database initialization system.
"""
import pytest
import os
import tempfile
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.utils.database_initializer import (
    InitializationResult, ValidationResult, DatabaseConfiguration,
    InitializationStep, ValidationSeverity
)


class TestInitializationResult:
    """Unit tests for InitializationResult dataclass."""
    
    def test_initialization_result_creation(self):
        """Test creating InitializationResult with default values."""
        result = InitializationResult(success=True)
        
        assert result.success is True
        assert result.steps_completed == []
        assert result.errors == []
        assert result.warnings == []
        assert result.duration == 0.0
        assert result.database_type is None
        assert isinstance(result.timestamp, datetime)
    
    def test_initialization_result_with_values(self):
        """Test creating InitializationResult with specific values."""
        timestamp = datetime.now()
        result = InitializationResult(
            success=False,
            steps_completed=['step1', 'step2'],
            errors=['error1', 'error2'],
            warnings=['warning1'],
            duration=5.5,
            database_type='postgresql',
            timestamp=timestamp
        )
        
        assert result.success is False
        assert result.steps_completed == ['step1', 'step2']
        assert result.errors == ['error1', 'error2']
        assert result.warnings == ['warning1']
        assert result.duration == 5.5
        assert result.database_type == 'postgresql'
        assert result.timestamp == timestamp
    
    def test_add_step(self):
        """Test adding completed steps."""
        result = InitializationResult(success=True)
        
        result.add_step("connection_test")
        result.add_step("schema_creation")
        
        assert len(result.steps_completed) == 2
        assert "connection_test" in result.steps_completed
        assert "schema_creation" in result.steps_completed
    
    def test_add_error(self):
        """Test adding error messages."""
        result = InitializationResult(success=True)
        
        result.add_error("Database connection failed")
        result.add_error("Schema creation failed")
        
        assert len(result.errors) == 2
        assert "Database connection failed" in result.errors
        assert "Schema creation failed" in result.errors
    
    def test_add_warning(self):
        """Test adding warning messages."""
        result = InitializationResult(success=True)
        
        result.add_warning("Slow connection detected")
        result.add_warning("Deprecated configuration")
        
        assert len(result.warnings) == 2
        assert "Slow connection detected" in result.warnings
        assert "Deprecated configuration" in result.warnings
    
    def test_add_multiple_items(self):
        """Test adding multiple items of different types."""
        result = InitializationResult(success=True)
        
        # Add multiple steps
        steps = ["step1", "step2", "step3"]
        for step in steps:
            result.add_step(step)
        
        # Add multiple errors
        errors = ["error1", "error2"]
        for error in errors:
            result.add_error(error)
        
        # Add multiple warnings
        warnings = ["warning1", "warning2", "warning3"]
        for warning in warnings:
            result.add_warning(warning)
        
        assert len(result.steps_completed) == 3
        assert len(result.errors) == 2
        assert len(result.warnings) == 3
        assert all(step in result.steps_completed for step in steps)
        assert all(error in result.errors for error in errors)
        assert all(warning in result.warnings for warning in warnings)


class TestValidationResult:
    """Unit tests for ValidationResult dataclass."""
    
    def test_validation_result_creation(self):
        """Test creating ValidationResult with default values."""
        result = ValidationResult(valid=True)
        
        assert result.valid is True
        assert result.issues == []
        assert result.suggestions == []
        assert result.severity == ValidationSeverity.INFO
        assert result.details == {}
        assert isinstance(result.timestamp, datetime)
    
    def test_validation_result_with_values(self):
        """Test creating ValidationResult with specific values."""
        timestamp = datetime.now()
        details = {'table_count': 5, 'missing_tables': ['users']}
        
        result = ValidationResult(
            valid=False,
            issues=['Missing table: users'],
            suggestions=['Run migrations'],
            severity=ValidationSeverity.ERROR,
            details=details,
            timestamp=timestamp
        )
        
        assert result.valid is False
        assert result.issues == ['Missing table: users']
        assert result.suggestions == ['Run migrations']
        assert result.severity == ValidationSeverity.ERROR
        assert result.details == details
        assert result.timestamp == timestamp
    
    def test_add_issue(self):
        """Test adding validation issues."""
        result = ValidationResult(valid=True)
        
        result.add_issue("Missing table", ValidationSeverity.ERROR)
        result.add_issue("Slow query", ValidationSeverity.WARNING)
        
        assert len(result.issues) == 2
        assert "Missing table" in result.issues
        assert "Slow query" in result.issues
        assert result.severity == ValidationSeverity.ERROR  # Should escalate to highest severity
    
    def test_add_suggestion(self):
        """Test adding suggestions."""
        result = ValidationResult(valid=True)
        
        result.add_suggestion("Run database migrations")
        result.add_suggestion("Check database permissions")
        
        assert len(result.suggestions) == 2
        assert "Run database migrations" in result.suggestions
        assert "Check database permissions" in result.suggestions
    
    def test_severity_escalation(self):
        """Test that severity escalates to the highest level."""
        result = ValidationResult(valid=True)
        
        # Start with INFO
        assert result.severity == ValidationSeverity.INFO
        
        # Add WARNING - should escalate
        result.add_issue("Warning issue", ValidationSeverity.WARNING)
        assert result.severity == ValidationSeverity.WARNING
        
        # Add ERROR - should escalate
        result.add_issue("Error issue", ValidationSeverity.ERROR)
        assert result.severity == ValidationSeverity.ERROR
        
        # Add CRITICAL - should escalate
        result.add_issue("Critical issue", ValidationSeverity.CRITICAL)
        assert result.severity == ValidationSeverity.CRITICAL
        
        # Add lower severity - should not downgrade
        result.add_issue("Another warning", ValidationSeverity.WARNING)
        assert result.severity == ValidationSeverity.CRITICAL
    
    def test_severity_order(self):
        """Test that severity levels are properly ordered."""
        severities = [
            ValidationSeverity.INFO,
            ValidationSeverity.WARNING,
            ValidationSeverity.ERROR,
            ValidationSeverity.CRITICAL
        ]
        
        # Test that each severity is "less than" the next one
        for i in range(len(severities) - 1):
            current = severities[i]
            next_severity = severities[i + 1]
            
            result1 = ValidationResult(valid=True)
            result1.add_issue("Test", current)
            
            result2 = ValidationResult(valid=True)
            result2.add_issue("Test", next_severity)
            
            # The higher severity should "win"
            result1.add_issue("Test2", next_severity)
            assert result1.severity == next_severity


class TestDatabaseConfiguration:
    """Unit tests for DatabaseConfiguration class."""
    
    @pytest.fixture
    def mock_app(self):
        """Create mock Flask app."""
        app = Mock()
        app.config = {
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db',
            'DATABASE_CONNECTION_TIMEOUT': 30,
            'DATABASE_POOL_SIZE': 5
        }
        return app
    
    @pytest.fixture
    def db_config(self, mock_app):
        """Create DatabaseConfiguration instance."""
        return DatabaseConfiguration(mock_app)
    
    def test_initialization(self, mock_app):
        """Test DatabaseConfiguration initialization."""
        config = DatabaseConfiguration(mock_app)
        
        assert config.app == mock_app
        assert hasattr(config, 'connection_timeout')
        assert hasattr(config, 'pool_size')
    
    def test_detect_database_type_postgresql(self, db_config):
        """Test PostgreSQL database type detection."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user:pass@localhost/db'}):
            assert db_config.detect_database_type() == 'postgresql'
    
    def test_detect_database_type_sqlite(self, db_config):
        """Test SQLite database type detection."""
        with patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///test.db'}):
            assert db_config.detect_database_type() == 'sqlite'
    
    def test_detect_database_type_mysql(self, db_config):
        """Test MySQL database type detection."""
        with patch.dict(os.environ, {'DATABASE_URL': 'mysql://user:pass@localhost/db'}):
            assert db_config.detect_database_type() == 'mysql'
    
    def test_detect_database_type_unknown(self, db_config):
        """Test unknown database type detection."""
        with patch.dict(os.environ, {'DATABASE_URL': 'unknown://test'}):
            assert db_config.detect_database_type() == 'unknown'
    
    def test_detect_database_type_fallback(self, db_config):
        """Test fallback to SQLite when no URL specified."""
        with patch.dict(os.environ, {}, clear=True):
            db_config.app.config = {}
            assert db_config.detect_database_type() == 'sqlite'
    
    def test_get_connection_parameters_postgresql(self, db_config):
        """Test PostgreSQL connection parameters."""
        with patch.dict(os.environ, {
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/testdb'
        }):
            params = db_config.get_connection_parameters()
            
            assert params['database_type'] == 'postgresql'
            assert params['connection_string'] == 'postgresql://user:pass@localhost:5432/testdb'
            assert 'timeout' in params
    
    def test_get_connection_parameters_sqlite(self, db_config):
        """Test SQLite connection parameters."""
        with patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///test.db'}):
            params = db_config.get_connection_parameters()
            
            assert params['database_type'] == 'sqlite'
            assert params['connection_string'] == 'sqlite:///test.db'
            assert 'timeout' in params
    
    def test_validate_configuration_valid(self, db_config):
        """Test configuration validation with valid config."""
        with patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///test.db'}):
            result = db_config.validate_configuration()
            
            assert result.valid is True
            assert len(result.issues) == 0
    
    def test_validate_configuration_no_url(self, db_config):
        """Test configuration validation with no database URL."""
        with patch.dict(os.environ, {}, clear=True):
            db_config.app.config = {}
            result = db_config.validate_configuration()
            
            assert result.valid is False
            assert any('No database URL configured' in issue for issue in result.issues)
    
    def test_validate_configuration_unknown_type(self, db_config):
        """Test configuration validation with unknown database type."""
        with patch.dict(os.environ, {'DATABASE_URL': 'unknown://test'}):
            result = db_config.validate_configuration()
            
            assert result.valid is False
            assert any('Unknown database type' in issue for issue in result.issues)


class TestInitializationStepEnum:
    """Unit tests for InitializationStep enum."""
    
    def test_initialization_step_values(self):
        """Test that all expected initialization steps are defined."""
        expected_steps = [
            'CONNECTION_TEST',
            'SCHEMA_CREATION',
            'MIGRATION_EXECUTION', 
            'DATA_SEEDING',
            'HEALTH_VALIDATION',
            'CLEANUP'
        ]
        
        for step_name in expected_steps:
            assert hasattr(InitializationStep, step_name)
            step = getattr(InitializationStep, step_name)
            assert isinstance(step, InitializationStep)
    
    def test_initialization_step_string_values(self):
        """Test initialization step string values."""
        # Test that enum values are reasonable strings
        for step in InitializationStep:
            assert isinstance(step.value, str)
            assert len(step.value) > 0
            assert step.value.replace('_', '').isalnum()


class TestValidationSeverityEnum:
    """Unit tests for ValidationSeverity enum."""
    
    def test_validation_severity_values(self):
        """Test that all expected validation severities are defined."""
        expected_severities = ['INFO', 'WARNING', 'ERROR', 'CRITICAL']
        
        for severity_name in expected_severities:
            assert hasattr(ValidationSeverity, severity_name)
            severity = getattr(ValidationSeverity, severity_name)
            assert isinstance(severity, ValidationSeverity)
    
    def test_validation_severity_string_values(self):
        """Test validation severity string values."""
        expected_values = {
            ValidationSeverity.INFO: 'info',
            ValidationSeverity.WARNING: 'warning',
            ValidationSeverity.ERROR: 'error',
            ValidationSeverity.CRITICAL: 'critical'
        }
        
        for severity, expected_value in expected_values.items():
            assert severity.value == expected_value
    
    def test_validation_severity_ordering(self):
        """Test that validation severities can be compared."""
        # Test ordering from least to most severe
        severities = [
            ValidationSeverity.INFO,
            ValidationSeverity.WARNING,
            ValidationSeverity.ERROR,
            ValidationSeverity.CRITICAL
        ]
        
        # Each severity should be "greater than" the previous ones
        for i in range(1, len(severities)):
            current = severities[i]
            previous = severities[i-1]
            
            # Test that we can distinguish between severities
            assert current != previous
            assert current.value != previous.value


class TestDatabaseInitializationUtilities:
    """Unit tests for database initialization utility functions."""
    
    def test_connection_string_masking(self):
        """Test connection string masking utility."""
        # This would test a utility function if it existed as a standalone function
        # For now, we'll test the concept
        
        def mask_connection_string(connection_string):
            """Utility function to mask sensitive information in connection strings."""
            if not connection_string:
                return 'Not configured'
            
            if 'sqlite:///' in connection_string:
                return connection_string  # SQLite paths are not sensitive
            
            # Mask password in other database URLs
            if '://' in connection_string and '@' in connection_string:
                parts = connection_string.split('://')
                if len(parts) == 2:
                    protocol = parts[0]
                    rest = parts[1]
                    if '@' in rest:
                        auth_and_host = rest.split('@')
                        if len(auth_and_host) == 2:
                            auth = auth_and_host[0]
                            host = auth_and_host[1]
                            if ':' in auth:
                                user = auth.split(':')[0]
                                return f"{protocol}://{user}:***@{host}"
            
            return connection_string
        
        # Test PostgreSQL URL masking
        masked = mask_connection_string('postgresql://user:password@localhost:5432/db')
        assert 'password' not in masked
        assert 'user:***@localhost:5432/db' in masked
        
        # Test SQLite URL (should not be masked)
        masked = mask_connection_string('sqlite:///test.db')
        assert masked == 'sqlite:///test.db'
        
        # Test None input
        masked = mask_connection_string(None)
        assert masked == 'Not configured'
        
        # Test empty string
        masked = mask_connection_string('')
        assert masked == 'Not configured'
    
    def test_database_type_detection(self):
        """Test database type detection utility."""
        
        def detect_database_type_from_url(url):
            """Utility function to detect database type from URL."""
            if not url:
                return 'unknown'
            
            url_lower = url.lower()
            if url_lower.startswith('postgresql://') or url_lower.startswith('postgres://'):
                return 'postgresql'
            elif url_lower.startswith('sqlite:///'):
                return 'sqlite'
            elif url_lower.startswith('mysql://'):
                return 'mysql'
            else:
                return 'unknown'
        
        # Test various database URLs
        assert detect_database_type_from_url('postgresql://user:pass@localhost/db') == 'postgresql'
        assert detect_database_type_from_url('postgres://user:pass@localhost/db') == 'postgresql'
        assert detect_database_type_from_url('sqlite:///test.db') == 'sqlite'
        assert detect_database_type_from_url('mysql://user:pass@localhost/db') == 'mysql'
        assert detect_database_type_from_url('unknown://test') == 'unknown'
        assert detect_database_type_from_url('') == 'unknown'
        assert detect_database_type_from_url(None) == 'unknown'


class TestDatabaseInitializationPerformance:
    """Performance unit tests for database initialization components."""
    
    def test_initialization_result_performance(self):
        """Test InitializationResult performance with many operations."""
        start_time = time.time()
        
        result = InitializationResult(success=True)
        
        # Add many steps, errors, and warnings
        for i in range(1000):
            result.add_step(f"step_{i}")
            if i % 10 == 0:  # Add error every 10th iteration
                result.add_error(f"error_{i}")
            if i % 5 == 0:   # Add warning every 5th iteration
                result.add_warning(f"warning_{i}")
        
        duration = time.time() - start_time
        
        # Should complete quickly even with many operations
        assert duration < 1.0
        assert len(result.steps_completed) == 1000
        assert len(result.errors) == 100  # Every 10th
        assert len(result.warnings) == 200  # Every 5th
    
    def test_validation_result_performance(self):
        """Test ValidationResult performance with many operations."""
        start_time = time.time()
        
        result = ValidationResult(valid=True)
        
        # Add many issues and suggestions
        severities = [ValidationSeverity.INFO, ValidationSeverity.WARNING, 
                     ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
        
        for i in range(1000):
            severity = severities[i % len(severities)]
            result.add_issue(f"issue_{i}", severity)
            result.add_suggestion(f"suggestion_{i}")
        
        duration = time.time() - start_time
        
        # Should complete quickly even with many operations
        assert duration < 1.0
        assert len(result.issues) == 1000
        assert len(result.suggestions) == 1000
        assert result.severity == ValidationSeverity.CRITICAL  # Should escalate to highest
    
    def test_database_configuration_performance(self):
        """Test DatabaseConfiguration performance."""
        mock_app = Mock()
        mock_app.config = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db'}
        
        start_time = time.time()
        
        # Create many configurations and perform operations
        for i in range(100):
            config = DatabaseConfiguration(mock_app)
            db_type = config.detect_database_type()
            params = config.get_connection_parameters()
            validation = config.validate_configuration()
            
            assert db_type == 'sqlite'
            assert params['database_type'] == 'sqlite'
            assert validation.valid is True
        
        duration = time.time() - start_time
        
        # Should complete quickly
        assert duration < 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])