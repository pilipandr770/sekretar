"""
Comprehensive tests for DatabaseInitializer class.

This module provides comprehensive unit and integration tests for the database
initialization system, covering all initialization steps, error scenarios,
and performance requirements.
"""
import pytest
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from app.utils.database_initializer import (
    DatabaseInitializer, InitializationResult, ValidationResult, 
    MigrationResult, SeedingResult, RepairResult, DatabaseConfiguration,
    InitializationStep, ValidationSeverity
)
from app.utils.environment_config import Environment, DatabaseType


class TestDatabaseConfiguration:
    """Test cases for DatabaseConfiguration class."""
    
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
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/testdb',
            'DB_SCHEMA': 'public',
            'DB_SSLMODE': 'require'
        }):
            params = db_config.get_connection_parameters()
            
            assert params['database_type'] == 'postgresql'
            assert params['connection_string'] == 'postgresql://user:pass@localhost:5432/testdb'
            assert params['timeout'] == 30
            assert 'host' in params
            assert 'port' in params
    
    def test_get_connection_parameters_sqlite(self, db_config):
        """Test SQLite connection parameters."""
        with patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///test.db'}):
            params = db_config.get_connection_parameters()
            
            assert params['database_type'] == 'sqlite'
            assert params['connection_string'] == 'sqlite:///test.db'
            assert 'database_path' in params
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
            assert any('Set DATABASE_URL' in suggestion for suggestion in result.suggestions)
    
    def test_validate_configuration_unknown_type(self, db_config):
        """Test configuration validation with unknown database type."""
        with patch.dict(os.environ, {'DATABASE_URL': 'unknown://test'}):
            result = db_config.validate_configuration()
            
            assert result.valid is False
            assert any('Unknown database type' in issue for issue in result.issues)
    
    def test_get_database_url_environment(self, db_config):
        """Test getting database URL from environment variable."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test'}):
            url = db_config._get_database_url()
            assert url == 'postgresql://test'
    
    def test_get_database_url_render_format(self, db_config):
        """Test handling Render.com postgres:// format."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgres://user:pass@host/db'}):
            url = db_config._get_database_url()
            assert url == 'postgresql://user:pass@host/db'
    
    def test_get_database_url_flask_config(self, db_config):
        """Test getting database URL from Flask config."""
        with patch.dict(os.environ, {}, clear=True):
            db_config.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flask.db'
            url = db_config._get_database_url()
            assert url == 'sqlite:///flask.db'
    
    def test_get_database_url_components(self, db_config):
        """Test building database URL from individual components."""
        with patch.dict(os.environ, {
            'DB_HOST': 'localhost',
            'DB_NAME': 'testdb',
            'DB_USER': 'testuser',
            'DB_PASSWORD': 'testpass',
            'DB_PORT': '5432'
        }, clear=True):
            db_config.app.config = {}
            url = db_config._get_database_url()
            assert url == 'postgresql://testuser:testpass@localhost:5432/testdb'
    
    def test_get_database_url_components_no_password(self, db_config):
        """Test building database URL without password."""
        with patch.dict(os.environ, {
            'DB_HOST': 'localhost',
            'DB_NAME': 'testdb',
            'DB_USER': 'testuser'
        }, clear=True):
            db_config.app.config = {}
            url = db_config._get_database_url()
            assert url == 'postgresql://testuser@localhost:5432/testdb'


class TestDatabaseInitializer:
    """Test cases for DatabaseInitializer class."""
    
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
    
    @pytest.fixture
    def initializer(self, mock_app, mock_db):
        """Create DatabaseInitializer instance."""
        with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
             patch('app.utils.database_initializer.EnvironmentDetector') as mock_detector, \
             patch('app.utils.database_initializer.EnvironmentInitializer') as mock_env_init, \
             patch('app.utils.database_initializer.get_database_init_logger') as mock_logger, \
             patch('app.utils.database_initializer.get_database_error_handler') as mock_error_handler, \
             patch('app.utils.database_initializer.initialize_recovery_system') as mock_recovery, \
             patch('app.utils.database_initializer.DataSeeder') as mock_seeder, \
             patch('app.utils.database_initializer.HealthValidator') as mock_validator:
            
            # Mock environment config
            env_config = Mock()
            env_config.environment = Environment.TESTING
            env_config.database_type = DatabaseType.SQLITE
            env_config.database_url = 'sqlite:///test.db'
            env_config.auto_seed_data = True
            mock_env_config.return_value = env_config
            
            # Mock other components
            mock_detector.return_value = Mock()
            mock_env_init.return_value = Mock()
            mock_logger.return_value = Mock()
            mock_error_handler.return_value = Mock()
            mock_recovery.return_value = Mock()
            mock_seeder.return_value = Mock()
            mock_validator.return_value = Mock()
            
            return DatabaseInitializer(mock_app, mock_db)
    
    def test_initialization_success(self, initializer):
        """Test successful database initialization."""
        # Mock all dependencies to succeed
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._test_connection = Mock(return_value=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///test.db'
        })
        
        # Mock data seeder
        seeding_result = SeedingResult(success=True)
        seeding_result.records_created = {'tenant': 1, 'admin_user': 1}
        initializer.data_seeder.seed_initial_data.return_value = seeding_result
        
        # Mock health validator
        validation_result = ValidationResult(valid=True)
        initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        result = initializer.initialize()
        
        assert result.success is True
        assert len(result.errors) == 0
        assert InitializationStep.CONNECTION_TEST.value in result.steps_completed
        assert InitializationStep.DATA_SEEDING.value in result.steps_completed
        assert result.database_type == 'sqlite'
    
    def test_initialization_environment_preparation_failure(self, initializer):
        """Test initialization failure during environment preparation."""
        initializer.env_initializer.prepare_environment.return_value = False
        
        result = initializer.initialize()
        
        assert result.success is False
        assert any('Failed to prepare environment' in error for error in result.errors)
    
    def test_initialization_configuration_validation_failure(self, initializer):
        """Test initialization failure during configuration validation."""
        initializer.env_initializer.prepare_environment.return_value = True
        
        config_result = ValidationResult(valid=False)
        config_result.add_issue("Invalid database URL", ValidationSeverity.CRITICAL)
        initializer.config.validate_configuration.return_value = config_result
        
        result = initializer.initialize()
        
        assert result.success is False
        assert any('Configuration error' in error for error in result.errors)
    
    def test_initialization_connection_failure(self, initializer):
        """Test initialization failure during connection test."""
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._test_connection = Mock(return_value=False)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///test.db'
        })
        
        result = initializer.initialize()
        
        assert result.success is False
        assert any('Database connection failed' in error for error in result.errors)
    
    def test_initialization_seeding_failure(self, initializer):
        """Test initialization failure during data seeding."""
        # Mock successful steps up to seeding
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._test_connection = Mock(return_value=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///test.db'
        })
        
        # Mock seeding failure
        seeding_result = SeedingResult(success=False)
        seeding_result.add_error("Failed to create admin user")
        initializer.data_seeder.seed_initial_data.return_value = seeding_result
        
        result = initializer.initialize()
        
        assert result.success is False
        assert any('Data seeding error' in error for error in result.errors)
    
    def test_initialization_with_auto_seeding_disabled(self, initializer):
        """Test initialization when auto-seeding is disabled."""
        # Disable auto-seeding
        initializer.env_config.auto_seed_data = False
        
        # Mock successful steps
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._test_connection = Mock(return_value=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///test.db'
        })
        
        # Mock health validator
        validation_result = ValidationResult(valid=True)
        initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        result = initializer.initialize()
        
        assert result.success is True
        assert InitializationStep.DATA_SEEDING.value in result.steps_completed
        # Data seeder should not be called
        initializer.data_seeder.seed_initial_data.assert_not_called()
    
    def test_get_initialization_status_not_initialized(self, initializer):
        """Test getting initialization status when not initialized."""
        status = initializer.get_initialization_status()
        
        assert status['initialized'] is False
        assert 'last_initialization' not in status
    
    def test_get_initialization_status_after_initialization(self, initializer):
        """Test getting initialization status after successful initialization."""
        # Mock successful initialization
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._test_connection = Mock(return_value=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///test.db'
        })
        
        seeding_result = SeedingResult(success=True)
        initializer.data_seeder.seed_initial_data.return_value = seeding_result
        
        initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        # Run initialization
        result = initializer.initialize()
        
        # Check status
        status = initializer.get_initialization_status()
        
        assert status['initialized'] is True
        assert status['success'] is True
        assert status['database_type'] == 'sqlite'
        assert 'last_initialization' in status
        assert 'duration' in status
    
    def test_validate_setup_success(self, initializer):
        """Test successful setup validation."""
        # Mock health validator
        health_result = Mock()
        health_result.status.value = 'healthy'
        health_result.checks_passed = 5
        health_result.checks_total = 5
        health_result.issues = []
        initializer.health_validator.run_comprehensive_health_check.return_value = health_result
        
        result = initializer.validate_setup()
        
        assert result.valid is True
        assert len(result.issues) == 0
    
    def test_validate_setup_failure(self, initializer):
        """Test setup validation failure."""
        # Mock health validator with issues
        health_result = Mock()
        health_result.status.value = 'critical'
        health_result.checks_passed = 2
        health_result.checks_total = 5
        health_result.issues = ['Database connectivity failed', 'Schema validation failed']
        initializer.health_validator.run_comprehensive_health_check.return_value = health_result
        
        result = initializer.validate_setup()
        
        assert result.valid is False
        assert len(result.issues) > 0
    
    def test_repair_if_needed_no_issues(self, initializer):
        """Test repair when no issues are found."""
        # Mock validation with no issues
        validation_result = ValidationResult(valid=True)
        initializer.validate_setup = Mock(return_value=validation_result)
        
        result = initializer.repair_if_needed()
        
        assert result.success is True
        assert len(result.repairs_performed) == 0
        assert "No repairs needed" in result.instructions[0]
    
    def test_repair_if_needed_with_issues(self, initializer):
        """Test repair when issues are found."""
        # Mock validation with issues
        validation_result = ValidationResult(valid=False)
        validation_result.add_issue("Database connectivity failed", ValidationSeverity.CRITICAL)
        initializer.validate_setup = Mock(return_value=validation_result)
        
        # Mock recovery manager
        initializer.recovery_manager.attempt_recovery.return_value = {
            'success': True,
            'repairs_performed': ['Fixed database connection'],
            'manual_intervention_required': False
        }
        
        result = initializer.repair_if_needed()
        
        assert result.success is True
        assert len(result.repairs_performed) > 0
    
    def test_mask_connection_string(self, initializer):
        """Test connection string masking for security."""
        # Test PostgreSQL URL masking
        masked = initializer._mask_connection_string('postgresql://user:password@localhost:5432/db')
        assert 'password' not in masked
        assert 'user:***@localhost:5432/db' in masked
        
        # Test SQLite URL (should not be masked)
        masked = initializer._mask_connection_string('sqlite:///test.db')
        assert masked == 'sqlite:///test.db'
        
        # Test None input
        masked = initializer._mask_connection_string(None)
        assert masked == 'Not configured'
    
    def test_test_connection_success(self, initializer):
        """Test successful database connection test."""
        # Mock successful connection
        mock_connection = Mock()
        mock_result = Mock()
        mock_result.fetchone.return_value = (1,)
        mock_connection.execute.return_value = mock_result
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        
        initializer.db.engine.connect.return_value = mock_connection
        
        conn_params = {
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///test.db'
        }
        
        result = initializer._test_connection(conn_params)
        
        assert result is True
    
    def test_test_connection_failure(self, initializer):
        """Test database connection test failure."""
        # Mock connection failure
        initializer.db.engine.connect.side_effect = Exception("Connection failed")
        
        conn_params = {
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///test.db'
        }
        
        result = initializer._test_connection(conn_params)
        
        assert result is False
    
    def test_get_environment_connection_parameters(self, initializer):
        """Test getting connection parameters from environment config."""
        params = initializer._get_environment_connection_parameters()
        
        assert params['database_type'] == 'sqlite'
        assert params['connection_string'] == 'sqlite:///test.db'
        assert 'timeout' in params
    
    def test_record_error(self, initializer):
        """Test error recording functionality."""
        error_details = {
            'error_code': 'DB_CONNECTION_FAILED',
            'message': 'Database connection failed',
            'timestamp': datetime.now().isoformat()
        }
        
        initializer._record_error(error_details)
        
        assert len(initializer._error_history) == 1
        assert initializer._error_history[0] == error_details
    
    def test_export_initialization_logs_json(self, initializer):
        """Test exporting initialization logs in JSON format."""
        # Mock logger with logs
        initializer.init_logger.export_logs.return_value = [
            {'level': 'INFO', 'message': 'Initialization started'},
            {'level': 'INFO', 'message': 'Initialization completed'}
        ]
        
        logs = initializer.export_initialization_logs('json')
        
        assert logs is not None
        assert len(logs) == 2
        assert logs[0]['message'] == 'Initialization started'
    
    def test_get_initialization_summary(self, initializer):
        """Test getting initialization summary."""
        # Mock successful initialization
        initializer._initialization_result = InitializationResult(success=True)
        initializer._initialization_result.database_type = 'sqlite'
        initializer._initialization_result.duration = 1.5
        initializer._initialization_result.steps_completed = ['connection_test', 'schema_creation']
        
        summary = initializer.get_initialization_summary()
        
        assert summary['initialization_success'] is True
        assert summary['database_type'] == 'sqlite'
        assert summary['duration'] == 1.5
        assert len(summary['steps_completed']) == 2


class TestInitializationResult:
    """Test cases for InitializationResult dataclass."""
    
    def test_initialization_result_creation(self):
        """Test creating InitializationResult."""
        result = InitializationResult(success=True)
        
        assert result.success is True
        assert result.steps_completed == []
        assert result.errors == []
        assert result.warnings == []
        assert result.duration == 0.0
        assert result.database_type is None
        assert isinstance(result.timestamp, datetime)
    
    def test_add_step(self):
        """Test adding completed step."""
        result = InitializationResult(success=True)
        
        result.add_step("connection_test")
        
        assert "connection_test" in result.steps_completed
        assert len(result.steps_completed) == 1
    
    def test_add_error(self):
        """Test adding error message."""
        result = InitializationResult(success=True)
        
        result.add_error("Database connection failed")
        
        assert "Database connection failed" in result.errors
        assert len(result.errors) == 1
    
    def test_add_warning(self):
        """Test adding warning message."""
        result = InitializationResult(success=True)
        
        result.add_warning("Schema validation warning")
        
        assert "Schema validation warning" in result.warnings
        assert len(result.warnings) == 1


class TestValidationResult:
    """Test cases for ValidationResult dataclass."""
    
    def test_validation_result_creation(self):
        """Test creating ValidationResult."""
        result = ValidationResult(valid=True)
        
        assert result.valid is True
        assert result.issues == []
        assert result.suggestions == []
        assert result.severity == ValidationSeverity.INFO
        assert result.details == {}
        assert isinstance(result.timestamp, datetime)
    
    def test_add_issue(self):
        """Test adding validation issue."""
        result = ValidationResult(valid=True)
        
        result.add_issue("Missing table", ValidationSeverity.ERROR)
        
        assert "Missing table" in result.issues
        assert result.severity == ValidationSeverity.ERROR
    
    def test_add_suggestion(self):
        """Test adding suggestion."""
        result = ValidationResult(valid=True)
        
        result.add_suggestion("Run database migrations")
        
        assert "Run database migrations" in result.suggestions


class TestPerformanceRequirements:
    """Test cases for performance requirements."""
    
    @pytest.fixture
    def initializer(self):
        """Create DatabaseInitializer for performance testing."""
        app = Mock()
        app.config = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', 'TESTING': True}
        app.debug = False
        
        db = Mock()
        db.engine = Mock()
        db.session = Mock()
        
        with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
             patch('app.utils.database_initializer.EnvironmentDetector'), \
             patch('app.utils.database_initializer.EnvironmentInitializer'), \
             patch('app.utils.database_initializer.get_database_init_logger'), \
             patch('app.utils.database_initializer.get_database_error_handler'), \
             patch('app.utils.database_initializer.initialize_recovery_system'), \
             patch('app.utils.database_initializer.DataSeeder'), \
             patch('app.utils.database_initializer.HealthValidator'):
            
            env_config = Mock()
            env_config.environment = Environment.TESTING
            env_config.database_type = DatabaseType.SQLITE
            env_config.database_url = 'sqlite:///:memory:'
            env_config.auto_seed_data = False
            mock_env_config.return_value = env_config
            
            return DatabaseInitializer(app, db)
    
    def test_initialization_performance_under_5_seconds(self, initializer):
        """Test that initialization completes within 5 seconds."""
        # Mock all dependencies to succeed quickly
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._test_connection = Mock(return_value=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///:memory:'
        })
        
        initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        start_time = time.time()
        result = initializer.initialize()
        duration = time.time() - start_time
        
        assert result.success is True
        assert duration < 5.0  # Should complete within 5 seconds
        assert result.duration < 5.0
    
    def test_validation_performance_under_2_seconds(self, initializer):
        """Test that validation completes within 2 seconds."""
        # Mock health validator to return quickly
        initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5,
            issues=[]
        )
        
        start_time = time.time()
        result = initializer.validate_setup()
        duration = time.time() - start_time
        
        assert duration < 2.0  # Should complete within 2 seconds
    
    def test_connection_test_performance_under_1_second(self, initializer):
        """Test that connection test completes within 1 second."""
        # Mock quick connection
        mock_connection = Mock()
        mock_result = Mock()
        mock_result.fetchone.return_value = (1,)
        mock_connection.execute.return_value = mock_result
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        
        initializer.db.engine.connect.return_value = mock_connection
        
        conn_params = {
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///:memory:'
        }
        
        start_time = time.time()
        result = initializer._test_connection(conn_params)
        duration = time.time() - start_time
        
        assert result is True
        assert duration < 1.0  # Should complete within 1 second
    
    def test_memory_usage_reasonable(self, initializer):
        """Test that initialization doesn't use excessive memory."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Mock successful initialization
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._test_connection = Mock(return_value=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///:memory:'
        })
        
        initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        # Run initialization
        result = initializer.initialize()
        
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        assert result.success is True
        assert memory_increase < 50  # Should not increase memory by more than 50MB


if __name__ == '__main__':
    pytest.main([__file__])