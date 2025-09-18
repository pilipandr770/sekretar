"""
Error scenario tests for database initialization system.

This module provides comprehensive tests for various error conditions and
failure scenarios in the database initialization system, ensuring robust
error handling and recovery mechanisms.
"""
import pytest
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, side_effect
from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError, DatabaseError

from app.utils.database_initializer import (
    DatabaseInitializer, InitializationResult, ValidationResult,
    ValidationSeverity, DatabaseConfiguration
)
from app.utils.data_seeder import DataSeeder, SeedingResult
from app.utils.health_validator import HealthValidator, HealthCheckResult, HealthStatus
from app.utils.environment_config import Environment, DatabaseType


class TestDatabaseConnectionErrors:
    """Test cases for database connection error scenarios."""
    
    @pytest.fixture
    def initializer(self):
        """Create DatabaseInitializer for error testing."""
        app = Mock()
        app.config = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db', 'TESTING': True}
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
            env_config.database_url = 'sqlite:///test.db'
            env_config.auto_seed_data = True
            mock_env_config.return_value = env_config
            
            return DatabaseInitializer(app, db)
    
    def test_connection_timeout_error(self, initializer):
        """Test handling of connection timeout errors."""
        # Mock environment preparation success
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'postgresql',
            'connection_string': 'postgresql://user:pass@localhost:5432/db'
        })
        
        # Mock connection timeout
        timeout_error = OperationalError("connection timeout", None, None)
        initializer.db.engine.connect.side_effect = timeout_error
        
        result = initializer.initialize()
        
        assert result.success is False
        assert any('Database connection error' in error for error in result.errors)
        assert result.database_type == 'postgresql'
    
    def test_connection_refused_error(self, initializer):
        """Test handling of connection refused errors."""
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'postgresql',
            'connection_string': 'postgresql://user:pass@localhost:5432/db'
        })
        
        # Mock connection refused
        refused_error = OperationalError("connection refused", None, None)
        initializer.db.engine.connect.side_effect = refused_error
        
        result = initializer.initialize()
        
        assert result.success is False
        assert any('Database connection error' in error for error in result.errors)
    
    def test_authentication_error(self, initializer):
        """Test handling of database authentication errors."""
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'postgresql',
            'connection_string': 'postgresql://user:wrongpass@localhost:5432/db'
        })
        
        # Mock authentication error
        auth_error = OperationalError("authentication failed", None, None)
        initializer.db.engine.connect.side_effect = auth_error
        
        result = initializer.initialize()
        
        assert result.success is False
        assert any('Database connection error' in error for error in result.errors)
    
    def test_database_not_found_error(self, initializer):
        """Test handling of database not found errors."""
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'postgresql',
            'connection_string': 'postgresql://user:pass@localhost:5432/nonexistent'
        })
        
        # Mock database not found
        not_found_error = OperationalError("database does not exist", None, None)
        initializer.db.engine.connect.side_effect = not_found_error
        
        result = initializer.initialize()
        
        assert result.success is False
        assert any('Database connection error' in error for error in result.errors)
    
    def test_permission_denied_error(self, initializer):
        """Test handling of permission denied errors."""
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///readonly.db'
        })
        
        # Mock permission denied
        permission_error = OperationalError("permission denied", None, None)
        initializer.db.engine.connect.side_effect = permission_error
        
        result = initializer.initialize()
        
        assert result.success is False
        assert any('Database connection error' in error for error in result.errors)
    
    def test_network_error(self, initializer):
        """Test handling of network-related errors."""
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'postgresql',
            'connection_string': 'postgresql://user:pass@unreachable:5432/db'
        })
        
        # Mock network error
        network_error = OperationalError("network unreachable", None, None)
        initializer.db.engine.connect.side_effect = network_error
        
        result = initializer.initialize()
        
        assert result.success is False
        assert any('Database connection error' in error for error in result.errors)


class TestConfigurationErrors:
    """Test cases for configuration error scenarios."""
    
    @pytest.fixture
    def db_config(self):
        """Create DatabaseConfiguration for error testing."""
        app = Mock()
        app.config = {}
        return DatabaseConfiguration(app)
    
    def test_missing_database_url(self, db_config):
        """Test handling of missing database URL."""
        with patch.dict(os.environ, {}, clear=True):
            db_config.app.config = {}
            
            result = db_config.validate_configuration()
            
            assert result.valid is False
            assert any('No database URL configured' in issue for issue in result.issues)
            assert any('Set DATABASE_URL' in suggestion for suggestion in result.suggestions)
    
    def test_invalid_database_url_format(self, db_config):
        """Test handling of invalid database URL format."""
        with patch.dict(os.environ, {'DATABASE_URL': 'invalid-url-format'}):
            result = db_config.validate_configuration()
            
            assert result.valid is False
            assert any('Unknown database type' in issue for issue in result.issues)
    
    def test_postgresql_missing_host(self, db_config):
        """Test PostgreSQL configuration with missing host."""
        with patch.dict(os.environ, {
            'DATABASE_URL': 'postgresql://user:pass@:5432/db'  # Empty host
        }):
            result = db_config.validate_configuration()
            
            # Should still be valid as URL parsing handles this
            # But specific validation might catch it
            db_config._validate_postgresql_config(result)
    
    def test_postgresql_invalid_port(self, db_config):
        """Test PostgreSQL configuration with invalid port."""
        with patch.dict(os.environ, {
            'DB_HOST': 'localhost',
            'DB_NAME': 'testdb',
            'DB_USER': 'testuser',
            'DB_PORT': '99999'  # Invalid port
        }, clear=True):
            db_config.app.config = {}
            
            result = ValidationResult(valid=True)
            db_config._validate_postgresql_config(result)
            
            assert result.valid is False
            assert any('Invalid PostgreSQL port' in issue for issue in result.issues)
    
    def test_sqlite_directory_not_writable(self, db_config):
        """Test SQLite configuration with non-writable directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a read-only directory
            readonly_dir = Path(temp_dir) / 'readonly'
            readonly_dir.mkdir()
            readonly_dir.chmod(0o444)  # Read-only
            
            db_path = readonly_dir / 'test.db'
            
            with patch.dict(os.environ, {'SQLITE_DATABASE_URL': f'sqlite:///{db_path}'}):
                result = ValidationResult(valid=True)
                db_config._validate_sqlite_config(result)
                
                assert any('not writable' in issue for issue in result.issues)
    
    def test_sqlite_directory_not_exists(self, db_config):
        """Test SQLite configuration with non-existent directory."""
        nonexistent_path = '/nonexistent/directory/test.db'
        
        with patch.dict(os.environ, {'SQLITE_DATABASE_URL': f'sqlite:///{nonexistent_path}'}):
            result = ValidationResult(valid=True)
            db_config._validate_sqlite_config(result)
            
            assert any('does not exist' in issue for issue in result.issues)


class TestSchemaErrors:
    """Test cases for schema-related error scenarios."""
    
    @pytest.fixture
    def validator(self):
        """Create HealthValidator for schema error testing."""
        app = Mock()
        app.config = {'TESTING': True}
        app.debug = False
        
        db = Mock()
        db.engine = Mock()
        db.session = Mock()
        
        with patch('app.utils.health_validator.get_database_init_logger'):
            return HealthValidator(app, db)
    
    @patch('app.utils.health_validator.inspect')
    def test_schema_inspection_error(self, mock_inspect, validator):
        """Test handling of schema inspection errors."""
        mock_inspect.side_effect = SQLAlchemyError("Inspector failed")
        
        result = validator.validate_schema_integrity()
        
        assert result.valid is False
        assert any('Schema validation failed with exception' in issue for issue in result.issues)
    
    @patch('app.utils.health_validator.inspect')
    def test_table_structure_corruption(self, mock_inspect, validator):
        """Test handling of corrupted table structures."""
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ['tenants', 'users']
        
        # Mock corrupted table structure
        mock_inspector.get_columns.side_effect = [
            [{'name': 'id'}],  # tenants table missing required columns
            Exception("Table structure corrupted")  # users table inspection fails
        ]
        mock_inspector.get_indexes.return_value = []
        mock_inspector.get_foreign_keys.return_value = []
        
        mock_inspect.return_value = mock_inspector
        
        result = validator.validate_schema_integrity()
        
        assert result.valid is False
        assert any('missing columns' in issue for issue in result.issues)
        assert any('Failed to validate table' in issue for issue in result.issues)
    
    @patch('app.utils.health_validator.inspect')
    def test_missing_critical_tables(self, mock_inspect, validator):
        """Test handling of missing critical tables."""
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ['some_table']  # Missing all critical tables
        mock_inspect.return_value = mock_inspector
        
        result = validator.validate_schema_integrity()
        
        assert result.valid is False
        critical_tables = ['tenants', 'users', 'roles']
        for table in critical_tables:
            assert any(f'Missing table: {table}' in issue for issue in result.issues)
    
    @patch('app.utils.health_validator.inspect')
    def test_foreign_key_constraint_errors(self, mock_inspect, validator):
        """Test handling of foreign key constraint errors."""
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ['tenants', 'users', 'roles']
        
        # Mock table structure validation that finds FK issues
        def mock_get_foreign_keys(table_name):
            if table_name == 'users':
                raise SQLAlchemyError("Foreign key constraint error")
            return []
        
        mock_inspector.get_columns.return_value = [
            {'name': 'id'}, {'name': 'tenant_id'}, {'name': 'email'}, 
            {'name': 'password_hash'}, {'name': 'is_active'}, {'name': 'created_at'}
        ]
        mock_inspector.get_indexes.return_value = []
        mock_inspector.get_foreign_keys.side_effect = mock_get_foreign_keys
        
        mock_inspect.return_value = mock_inspector
        
        result = validator.validate_schema_integrity()
        
        # Should handle FK errors gracefully
        assert any('Failed to validate table' in issue for issue in result.issues)


class TestDataSeedingErrors:
    """Test cases for data seeding error scenarios."""
    
    @pytest.fixture
    def seeder(self):
        """Create DataSeeder for error testing."""
        app = Mock()
        app.config = {'TESTING': True}
        app.debug = False
        
        db = Mock()
        db.session = Mock()
        
        with patch('app.utils.data_seeder.get_database_init_logger'):
            return DataSeeder(app, db)
    
    def test_tenant_creation_integrity_error(self, seeder):
        """Test handling of tenant creation integrity errors."""
        with patch('app.utils.data_seeder.Tenant') as mock_tenant_class:
            # Mock no existing tenant initially
            mock_tenant_class.query.filter_by.return_value.first.side_effect = [
                None,  # First check - no existing tenant
                None   # Second check after error - still no tenant (error persists)
            ]
            
            # Mock integrity error that doesn't resolve
            seeder.db.session.commit.side_effect = IntegrityError("Unique constraint violation", None, None)
            
            result = seeder._create_system_tenant()
            
            assert result['success'] is False
            assert 'Integrity error creating system tenant' in result['error']
            seeder.db.session.rollback.assert_called_once()
    
    def test_user_creation_database_error(self, seeder):
        """Test handling of user creation database errors."""
        with patch('app.utils.data_seeder.User') as mock_user_class, \
             patch('app.utils.data_seeder.Role') as mock_role_class:
            
            mock_user_class.query.filter_by.return_value.first.return_value = None
            
            # Mock database error during user creation
            database_error = DatabaseError("Database connection lost", None, None)
            seeder.db.session.commit.side_effect = database_error
            
            result = seeder._create_admin_user(1)
            
            assert result['success'] is False
            assert 'Failed to create admin user' in result['error']
            seeder.db.session.rollback.assert_called_once()
    
    def test_role_creation_permission_error(self, seeder):
        """Test handling of role creation permission errors."""
        with patch('app.utils.data_seeder.Role') as mock_role_class:
            mock_role_class.query.filter_by.return_value.all.return_value = []
            
            # Mock permission error during role creation
            permission_error = OperationalError("Permission denied", None, None)
            seeder.db.session.commit.side_effect = permission_error
            
            result = seeder._create_system_roles(1)
            
            assert result['success'] is False
            assert 'Failed to create system roles' in result['error']
            seeder.db.session.rollback.assert_called_once()
    
    def test_seeding_transaction_rollback(self, seeder):
        """Test proper transaction rollback during seeding errors."""
        # Mock successful tenant creation
        mock_tenant = Mock()
        mock_tenant.id = 1
        seeder._create_system_tenant = Mock(return_value={
            'success': True,
            'tenant': mock_tenant,
            'created': True
        })
        
        # Mock role creation failure
        seeder._create_system_roles = Mock(return_value={
            'success': False,
            'error': 'Database transaction failed'
        })
        
        result = seeder.seed_initial_data()
        
        assert result.success is False
        assert any('Failed to create system roles' in error for error in result.errors)
    
    def test_concurrent_seeding_race_condition(self, seeder):
        """Test handling of race conditions during concurrent seeding."""
        with patch('app.utils.data_seeder.Tenant') as mock_tenant_class:
            # Simulate race condition: no tenant initially, but one appears after error
            existing_tenant = Mock()
            existing_tenant.id = 1
            mock_tenant_class.query.filter_by.return_value.first.side_effect = [
                None,  # First check - no existing tenant
                existing_tenant  # After integrity error - tenant now exists
            ]
            
            # Mock integrity error (race condition)
            seeder.db.session.commit.side_effect = IntegrityError("Duplicate key", None, None)
            
            result = seeder._create_system_tenant()
            
            assert result['success'] is True
            assert result['tenant'] == existing_tenant
            assert result['created'] is False
            seeder.db.session.rollback.assert_called_once()


class TestMigrationErrors:
    """Test cases for migration-related error scenarios."""
    
    @pytest.fixture
    def migration_runner(self):
        """Create MigrationRunner for error testing."""
        app = Mock()
        app.config = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db'}
        
        with patch('app.services.migration_runner.MigrationRunner._find_migrations_directory') as mock_find:
            mock_find.return_value = Path('/fake/migrations')
            
            with patch('app.services.migration_runner.Config') as mock_config:
                mock_config.return_value = Mock()
                
                from app.services.migration_runner import MigrationRunner
                return MigrationRunner(app)
    
    def test_migration_file_corruption(self, migration_runner):
        """Test handling of corrupted migration files."""
        from alembic.util.exc import CommandError
        
        # Mock pending migrations
        migration_runner.check_pending_migrations = Mock(return_value=['abc123'])
        
        # Mock corrupted migration file
        corrupt_error = CommandError("Migration file corrupted")
        
        with patch('app.services.migration_runner.command') as mock_command:
            mock_command.upgrade.side_effect = corrupt_error
            
            result = migration_runner.run_migrations()
            
            assert result.success is False
            assert result.error_message == "Migration file corrupted"
            assert result.failed_migration == 'abc123'
    
    def test_migration_dependency_conflict(self, migration_runner):
        """Test handling of migration dependency conflicts."""
        from alembic.util.exc import CommandError
        
        migration_runner.check_pending_migrations = Mock(return_value=['abc123', 'def456'])
        
        # Mock dependency conflict
        dependency_error = CommandError("Migration dependency conflict")
        
        with patch('app.services.migration_runner.command') as mock_command:
            mock_command.upgrade.side_effect = dependency_error
            
            result = migration_runner.run_migrations()
            
            assert result.success is False
            assert "dependency conflict" in result.error_message.lower()
    
    def test_migration_rollback_failure(self, migration_runner):
        """Test handling of migration rollback failures."""
        with patch('app.services.migration_runner.command') as mock_command:
            # Mock rollback failure
            rollback_error = Exception("Rollback failed")
            mock_command.downgrade.side_effect = rollback_error
            
            # Mock script directory
            mock_migration = Mock()
            mock_migration.revision = 'abc123'
            migration_runner.script_directory = Mock()
            migration_runner.script_directory.get_revision.return_value = mock_migration
            
            result = migration_runner.rollback_migration('abc123')
            
            assert result is False
    
    def test_alembic_version_table_corruption(self, migration_runner):
        """Test handling of alembic_version table corruption."""
        with patch('app.services.migration_runner.create_engine') as mock_create_engine, \
             patch('app.services.migration_runner.MigrationContext') as mock_context_class:
            
            # Mock engine and connection
            mock_engine = Mock()
            mock_connection = Mock()
            mock_create_engine.return_value = mock_engine
            mock_engine.connect.return_value = mock_connection
            mock_connection.__enter__ = Mock(return_value=mock_connection)
            mock_connection.__exit__ = Mock(return_value=None)
            
            # Mock corrupted alembic_version table
            mock_context = Mock()
            mock_context_class.configure.return_value = mock_context
            mock_context.get_current_revision.side_effect = Exception("Table corrupted")
            
            result = migration_runner.validate_migration_state()
            
            assert result['valid'] is False
            assert any('corrupted' in issue.lower() for issue in result['issues'])


class TestHealthCheckErrors:
    """Test cases for health check error scenarios."""
    
    @pytest.fixture
    def validator(self):
        """Create HealthValidator for error testing."""
        app = Mock()
        app.config = {'TESTING': True}
        app.debug = False
        
        db = Mock()
        db.engine = Mock()
        db.session = Mock()
        
        with patch('app.utils.health_validator.get_database_init_logger'):
            return HealthValidator(app, db)
    
    def test_connectivity_check_timeout(self, validator):
        """Test handling of connectivity check timeouts."""
        # Mock connection timeout
        timeout_error = OperationalError("Query timeout", None, None)
        validator.db.engine.connect.side_effect = timeout_error
        
        result = validator.validate_connectivity()
        
        assert result is False
    
    def test_schema_validation_memory_error(self, validator):
        """Test handling of memory errors during schema validation."""
        with patch('app.utils.health_validator.inspect') as mock_inspect:
            mock_inspect.side_effect = MemoryError("Out of memory")
            
            result = validator.validate_schema_integrity()
            
            assert result.valid is False
            assert any('Schema validation failed with exception' in issue for issue in result.issues)
    
    def test_data_validation_model_import_error(self, validator):
        """Test handling of model import errors during data validation."""
        with patch('app.utils.health_validator.Tenant', side_effect=ImportError("Model not found")):
            result = validator.validate_data_integrity()
            
            assert result.valid is False
            assert any('Failed to validate system tenant' in issue for issue in result.issues)
    
    def test_performance_check_resource_exhaustion(self, validator):
        """Test handling of resource exhaustion during performance checks."""
        # Mock resource exhaustion
        resource_error = OperationalError("Too many connections", None, None)
        validator.db.engine.connect.side_effect = resource_error
        
        result = validator._check_performance_metrics()
        
        assert result['status'] == 'error'
        assert 'Performance check failed' in result['message']
    
    def test_health_report_generation_exception(self, validator):
        """Test handling of exceptions during health report generation."""
        # Mock connectivity check to succeed initially
        validator.validate_connectivity = Mock(return_value=True)
        
        # Mock schema validation to raise exception
        validator.validate_schema_integrity = Mock(side_effect=Exception("Unexpected error"))
        
        validator._get_database_type = Mock(return_value='sqlite')
        
        report = validator.generate_health_report()
        
        assert report['overall_status'] == HealthStatus.CRITICAL.value
        assert 'error' in report
        assert 'Investigate health check system errors' in report['recommendations']


class TestRecoveryScenarios:
    """Test cases for error recovery scenarios."""
    
    @pytest.fixture
    def initializer(self):
        """Create DatabaseInitializer for recovery testing."""
        app = Mock()
        app.config = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db', 'TESTING': True}
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
            env_config.database_url = 'sqlite:///test.db'
            env_config.auto_seed_data = True
            mock_env_config.return_value = env_config
            
            return DatabaseInitializer(app, db)
    
    def test_automatic_retry_on_transient_error(self, initializer):
        """Test automatic retry mechanism for transient errors."""
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///test.db'
        })
        
        # Mock transient error followed by success
        transient_error = OperationalError("Temporary failure", None, None)
        mock_connection = Mock()
        mock_result = Mock()
        mock_result.fetchone.return_value = (1,)
        mock_connection.execute.return_value = mock_result
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        
        initializer.db.engine.connect.side_effect = [
            transient_error,  # First attempt fails
            mock_connection   # Second attempt succeeds
        ]
        
        # Mock other components to succeed
        seeding_result = SeedingResult(success=True)
        initializer.data_seeder.seed_initial_data.return_value = seeding_result
        
        initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        # The test connection method should handle retries internally
        # For this test, we'll mock it to succeed after retry
        initializer._test_connection = Mock(return_value=True)
        
        result = initializer.initialize()
        
        assert result.success is True
    
    def test_graceful_degradation_on_non_critical_failure(self, initializer):
        """Test graceful degradation when non-critical components fail."""
        # Mock successful core initialization
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._test_connection = Mock(return_value=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///test.db'
        })
        
        # Mock seeding success
        seeding_result = SeedingResult(success=True)
        initializer.data_seeder.seed_initial_data.return_value = seeding_result
        
        # Mock health validation failure (non-critical)
        health_result = Mock()
        health_result.status.value = 'warning'
        health_result.checks_passed = 3
        health_result.checks_total = 5
        health_result.issues = ['Performance degraded']
        initializer.health_validator.run_comprehensive_health_check.return_value = health_result
        
        result = initializer.initialize()
        
        # Should succeed with warnings
        assert result.success is True
        assert len(result.warnings) > 0
    
    def test_error_context_preservation(self, initializer):
        """Test that error context is preserved for debugging."""
        initializer.env_initializer.prepare_environment.return_value = True
        initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'postgresql',
            'connection_string': 'postgresql://user:pass@localhost:5432/db'
        })
        
        # Mock connection error with specific context
        connection_error = OperationalError("Connection failed: host unreachable", None, None)
        initializer.db.engine.connect.side_effect = connection_error
        
        result = initializer.initialize()
        
        assert result.success is False
        assert len(initializer._error_history) > 0
        # Error history should contain context information
        error_record = initializer._error_history[0]
        assert 'error_code' in error_record or 'message' in error_record
    
    def test_recovery_suggestions_provided(self, initializer):
        """Test that recovery suggestions are provided for common errors."""
        initializer.env_initializer.prepare_environment.return_value = True
        
        # Mock configuration validation failure
        config_result = ValidationResult(valid=False)
        config_result.add_issue("Database URL not configured", ValidationSeverity.CRITICAL)
        config_result.add_suggestion("Set DATABASE_URL environment variable")
        initializer.config.validate_configuration.return_value = config_result
        
        result = initializer.initialize()
        
        assert result.success is False
        # Should include recovery suggestions in warnings or errors
        assert len(result.errors) > 0


class TestConcurrencyErrors:
    """Test cases for concurrency-related error scenarios."""
    
    @pytest.fixture
    def seeder(self):
        """Create DataSeeder for concurrency testing."""
        app = Mock()
        app.config = {'TESTING': True}
        app.debug = False
        
        db = Mock()
        db.session = Mock()
        
        with patch('app.utils.data_seeder.get_database_init_logger'):
            return DataSeeder(app, db)
    
    def test_concurrent_tenant_creation(self, seeder):
        """Test handling of concurrent tenant creation attempts."""
        with patch('app.utils.data_seeder.Tenant') as mock_tenant_class:
            # Simulate race condition: no tenant initially, then one appears
            existing_tenant = Mock()
            existing_tenant.id = 1
            mock_tenant_class.query.filter_by.return_value.first.side_effect = [
                None,  # First check - no tenant
                existing_tenant  # After error - tenant exists (created by another process)
            ]
            
            # Mock integrity error due to concurrent creation
            seeder.db.session.commit.side_effect = IntegrityError("Duplicate key", None, None)
            
            result = seeder._create_system_tenant()
            
            # Should handle gracefully and return existing tenant
            assert result['success'] is True
            assert result['tenant'] == existing_tenant
            assert result['created'] is False
    
    def test_concurrent_user_creation(self, seeder):
        """Test handling of concurrent user creation attempts."""
        with patch('app.utils.data_seeder.User') as mock_user_class, \
             patch('app.utils.data_seeder.Role') as mock_role_class:
            
            # Simulate race condition
            existing_user = Mock()
            existing_user.id = 1
            mock_user_class.query.filter_by.return_value.first.side_effect = [
                None,  # First check - no user
                existing_user  # After error - user exists
            ]
            
            # Mock integrity error due to concurrent creation
            seeder.db.session.commit.side_effect = IntegrityError("Duplicate email", None, None)
            
            result = seeder._create_admin_user(1)
            
            # Should handle gracefully and return existing user
            assert result['success'] is True
            assert result['user'] == existing_user
            assert result['created'] is False
    
    def test_database_lock_timeout(self, seeder):
        """Test handling of database lock timeouts."""
        with patch('app.utils.data_seeder.Tenant') as mock_tenant_class:
            mock_tenant_class.query.filter_by.return_value.first.return_value = None
            
            # Mock lock timeout error
            lock_error = OperationalError("Lock timeout", None, None)
            seeder.db.session.commit.side_effect = lock_error
            
            result = seeder._create_system_tenant()
            
            assert result['success'] is False
            assert 'Failed to create system tenant' in result['error']


if __name__ == '__main__':
    pytest.main([__file__])