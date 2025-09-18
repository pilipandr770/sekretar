"""
Test environment-specific database initialization handling.

This test suite verifies that the database initialization system correctly
handles different environments (development, testing, production) with
appropriate database configurations and initialization options.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.utils.environment_config import (
    EnvironmentDetector,
    EnvironmentInitializer,
    EnvironmentConfig,
    Environment,
    DatabaseType,
    get_environment_config
)


class TestEnvironmentDetection:
    """Test environment detection logic."""
    
    def test_detect_development_environment(self):
        """Test detection of development environment."""
        with patch.dict(os.environ, {'FLASK_ENV': 'development'}, clear=False):
            detector = EnvironmentDetector()
            env = detector.detect_environment()
            assert env == Environment.DEVELOPMENT
    
    def test_detect_testing_environment(self):
        """Test detection of testing environment."""
        with patch.dict(os.environ, {'FLASK_ENV': 'testing'}, clear=False):
            detector = EnvironmentDetector()
            env = detector.detect_environment()
            assert env == Environment.TESTING
    
    def test_detect_production_environment(self):
        """Test detection of production environment."""
        with patch.dict(os.environ, {'FLASK_ENV': 'production'}, clear=False):
            detector = EnvironmentDetector()
            env = detector.detect_environment()
            assert env == Environment.PRODUCTION
    
    def test_detect_testing_from_testing_flag(self):
        """Test detection of testing environment from TESTING flag."""
        with patch.dict(os.environ, {'TESTING': 'true'}, clear=True):
            detector = EnvironmentDetector()
            env = detector.detect_environment()
            assert env == Environment.TESTING
    
    def test_detect_production_from_platform(self):
        """Test detection of production environment from deployment platform."""
        with patch.dict(os.environ, {'RENDER': 'true'}, clear=True):
            detector = EnvironmentDetector()
            env = detector.detect_environment()
            assert env == Environment.PRODUCTION
    
    def test_detect_testing_from_database_url(self):
        """Test detection of testing environment from database URL."""
        with patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///:memory:'}, clear=True):
            detector = EnvironmentDetector()
            env = detector.detect_environment()
            assert env == Environment.TESTING
    
    def test_default_to_development(self):
        """Test default environment detection."""
        with patch.dict(os.environ, {'TESTING': 'false'}, clear=True):
            detector = EnvironmentDetector()
            env = detector.detect_environment()
            assert env == Environment.DEVELOPMENT


class TestDevelopmentEnvironmentInitialization:
    """Test development environment initialization."""
    
    def test_sqlite_development_initialization(self):
        """Test SQLite initialization in development environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / 'test_dev.db'
            
            config = EnvironmentConfig(
                environment=Environment.DEVELOPMENT,
                database_type=DatabaseType.SQLITE,
                database_url=f'sqlite:///{db_path}',
                database_file_path=str(db_path),
                auto_create_database=True,
                initialization_options={'create_directories': True, 'validate_permissions': True}
            )
            
            initializer = EnvironmentInitializer(config)
            success = initializer._prepare_sqlite_development()
            
            assert success is True
            assert db_path.parent.exists()
            
            state = initializer.get_initialization_state()
            assert 'directory_created' in state
            assert 'database_path' in state
    
    def test_sqlite_development_with_corruption_reset(self):
        """Test SQLite development initialization with corrupted database reset."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / 'corrupted.db'
            
            # Create a corrupted database file
            db_path.write_text("corrupted data")
            
            config = EnvironmentConfig(
                environment=Environment.DEVELOPMENT,
                database_type=DatabaseType.SQLITE,
                database_url=f'sqlite:///{db_path}',
                database_file_path=str(db_path),
                initialization_options={'reset_on_corruption': True}
            )
            
            initializer = EnvironmentInitializer(config)
            success = initializer._prepare_sqlite_development()
            
            assert success is True
            state = initializer.get_initialization_state()
            assert state.get('corrupted_db_removed') is True
    
    def test_postgresql_development_initialization(self):
        """Test PostgreSQL initialization in development environment."""
        config = EnvironmentConfig(
            environment=Environment.DEVELOPMENT,
            database_type=DatabaseType.POSTGRESQL,
            database_url='postgresql://user:pass@localhost:5432/dev_db',
            initialization_options={'create_schema': True, 'retry_attempts': 3}
        )
        
        initializer = EnvironmentInitializer(config)
        success = initializer._prepare_postgresql_development()
        
        assert success is True
    
    def test_development_fallback_to_sqlite(self):
        """Test fallback to SQLite for unsupported database types in development."""
        config = EnvironmentConfig(
            environment=Environment.DEVELOPMENT,
            database_type=DatabaseType.MYSQL,  # Unsupported
            database_url='mysql://user:pass@localhost:3306/db'
        )
        
        initializer = EnvironmentInitializer(config)
        success = initializer._prepare_development_environment()
        
        assert success is True
        assert config.database_type == DatabaseType.SQLITE


class TestTestingEnvironmentInitialization:
    """Test testing environment initialization."""
    
    def test_sqlite_memory_testing_initialization(self):
        """Test in-memory SQLite initialization for testing."""
        config = EnvironmentConfig(
            environment=Environment.TESTING,
            database_type=DatabaseType.SQLITE,
            database_url='sqlite:///:memory:',
            database_file_path=':memory:',
            isolated_database=True
        )
        
        initializer = EnvironmentInitializer(config)
        success = initializer._prepare_sqlite_testing()
        
        assert success is True
        state = initializer.get_initialization_state()
        assert state.get('memory_database') is True
    
    def test_sqlite_file_testing_with_isolation(self):
        """Test file-based SQLite testing with isolation."""
        config = EnvironmentConfig(
            environment=Environment.TESTING,
            database_type=DatabaseType.SQLITE,
            database_url='sqlite:///regular.db',
            database_file_path='regular.db',
            isolated_database=True,
            initialization_options={'create_directories': True}
        )
        
        initializer = EnvironmentInitializer(config)
        success = initializer._prepare_sqlite_testing()
        
        assert success is True
        state = initializer.get_initialization_state()
        assert 'isolated_path_created' in state
        assert 'test_database_path' in state
        
        # Verify the path was changed to be isolated
        assert config.database_file_path != 'regular.db'
        assert 'test_' in config.database_file_path
    
    def test_postgresql_testing_with_isolation(self):
        """Test PostgreSQL testing initialization with database isolation."""
        config = EnvironmentConfig(
            environment=Environment.TESTING,
            database_type=DatabaseType.POSTGRESQL,
            database_url='postgresql://user:pass@localhost:5432/regular_db',
            isolated_database=True
        )
        
        initializer = EnvironmentInitializer(config)
        success = initializer._prepare_postgresql_testing()
        
        assert success is True
        state = initializer.get_initialization_state()
        assert 'isolated_test_db' in state
        
        # Verify the database URL was changed to be isolated
        assert 'test_' in config.database_url
        assert config.engine_options['pool_size'] == 1
        assert config.initialization_options['fast_initialization'] is True
    
    def test_testing_fallback_to_memory(self):
        """Test fallback to in-memory SQLite for unsupported database types in testing."""
        config = EnvironmentConfig(
            environment=Environment.TESTING,
            database_type=DatabaseType.MYSQL,  # Unsupported
            database_url='mysql://user:pass@localhost:3306/db'
        )
        
        initializer = EnvironmentInitializer(config)
        success = initializer._prepare_testing_environment()
        
        assert success is True
        assert config.database_type == DatabaseType.SQLITE
        assert config.database_url == 'sqlite:///:memory:'
        assert config.isolated_database is True
        
        state = initializer.get_initialization_state()
        assert state.get('fallback_to_memory') is True


class TestProductionEnvironmentInitialization:
    """Test production environment initialization."""
    
    def test_postgresql_production_initialization(self):
        """Test PostgreSQL initialization in production environment."""
        config = EnvironmentConfig(
            environment=Environment.PRODUCTION,
            database_type=DatabaseType.POSTGRESQL,
            database_url='postgresql://user:pass@prod-host:5432/prod_db',
            initialization_options={'strict_validation': True, 'backup_before_migration': True}
        )
        
        initializer = EnvironmentInitializer(config)
        success = initializer._prepare_postgresql_production()
        
        assert success is True
        state = initializer.get_initialization_state()
        assert state.get('production_database') == 'postgresql'
        assert state.get('strict_validation') is True
    
    def test_sqlite_production_initialization(self):
        """Test SQLite initialization in production environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / 'prod.db'
            
            config = EnvironmentConfig(
                environment=Environment.PRODUCTION,
                database_type=DatabaseType.SQLITE,
                database_url=f'sqlite:///{db_path}',
                database_file_path=str(db_path),
                initialization_options={'validate_permissions': True, 'strict_validation': True}
            )
            
            initializer = EnvironmentInitializer(config)
            success = initializer._prepare_sqlite_production()
            
            assert success is True
            state = initializer.get_initialization_state()
            assert state.get('production_database') == 'sqlite'
            assert state.get('strict_validation') is True
    
    def test_production_unsupported_database_type(self):
        """Test production environment with unsupported database type."""
        config = EnvironmentConfig(
            environment=Environment.PRODUCTION,
            database_type=DatabaseType.MYSQL,  # Unsupported in production
            database_url='mysql://user:pass@localhost:3306/db'
        )
        
        initializer = EnvironmentInitializer(config)
        success = initializer._prepare_production_environment()
        
        assert success is False
        state = initializer.get_initialization_state()
        assert 'error' in state


class TestEnvironmentConfigurationIntegration:
    """Test complete environment configuration integration."""
    
    def test_get_development_config(self):
        """Test getting development environment configuration."""
        with patch.dict(os.environ, {'FLASK_ENV': 'development', 'DATABASE_URL': 'sqlite:///dev.db'}, clear=False):
            config = get_environment_config(Environment.DEVELOPMENT)
            
            assert config.environment == Environment.DEVELOPMENT
            assert config.auto_create_database is True
            assert config.auto_run_migrations is True
            assert config.auto_seed_data is True
            assert config.isolated_database is False
    
    def test_get_testing_config(self):
        """Test getting testing environment configuration."""
        with patch.dict(os.environ, {'FLASK_ENV': 'testing'}, clear=False):
            config = get_environment_config(Environment.TESTING)
            
            assert config.environment == Environment.TESTING
            assert config.auto_create_database is True
            assert config.auto_run_migrations is True
            assert config.auto_seed_data is True
            assert config.isolated_database is True
            assert config.pool_size == 1
    
    def test_get_production_config(self):
        """Test getting production environment configuration."""
        with patch.dict(os.environ, {'FLASK_ENV': 'production', 'DATABASE_URL': 'postgresql://user:pass@host:5432/db'}, clear=False):
            config = get_environment_config(Environment.PRODUCTION)
            
            assert config.environment == Environment.PRODUCTION
            assert config.auto_create_database is False
            assert config.auto_run_migrations is True
            assert config.auto_seed_data is False
            assert config.isolated_database is False
            assert config.pool_size == 10
    
    def test_environment_auto_detection(self):
        """Test automatic environment detection."""
        with patch.dict(os.environ, {'FLASK_ENV': 'testing'}, clear=False):
            config = get_environment_config()  # No explicit environment
            
            assert config.environment == Environment.TESTING
    
    def test_initialization_state_tracking(self):
        """Test initialization state tracking."""
        config = EnvironmentConfig(
            environment=Environment.DEVELOPMENT,
            database_type=DatabaseType.SQLITE,
            database_url='sqlite:///:memory:',
            database_file_path=':memory:'
        )
        
        initializer = EnvironmentInitializer(config)
        success = initializer.prepare_environment()
        
        assert success is True
        
        state = initializer.get_initialization_state()
        assert 'start_time' in state
        assert 'environment' in state
        assert 'database_type' in state
        assert 'preparation_duration' in state
        assert state['environment'] == 'development'
        assert state['database_type'] == 'sqlite'


if __name__ == '__main__':
    pytest.main([__file__])