"""
Integration tests for database initialization system.

This module provides comprehensive integration tests that test the complete
database initialization flow with real database connections and components
working together.
"""
import pytest
import tempfile
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.utils.database_initializer import DatabaseInitializer, InitializationResult
from app.utils.data_seeder import DataSeeder
from app.utils.health_validator import HealthValidator
from app.utils.environment_initializer import Environment, DatabaseType
from app.models import User, Tenant, Role


class TestDatabaseInitializationIntegration:
    """Integration tests for complete database initialization flow."""
    
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
    
    @pytest.fixture
    def app_with_temp_db(self, temp_db_path):
        """Create Flask app with temporary database."""
        app = create_app('testing')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{temp_db_path}'
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        return app
    
    def test_complete_initialization_flow_empty_database(self, app_with_temp_db):
        """Test complete initialization flow starting from empty database."""
        with app_with_temp_db.app_context():
            from app import db
            initializer = DatabaseInitializer(app_with_temp_db, db)
            
            # Test initialization from completely empty database
            result = initializer.initialize()
            
            # Verify initialization succeeded
            assert result.success is True
            assert result.database_type == 'sqlite'
            assert len(result.errors) == 0
            
            # Verify initialization steps were completed
            expected_steps = [
                'connection_test',
                'schema_creation',
                'migration_execution',
                'data_seeding',
                'health_validation',
                'cleanup'
            ]
            for step in expected_steps:
                assert step in result.steps_completed
            
            # Verify admin user was created
            admin_user = User.query.filter_by(email='admin@ai-secretary.com').first()
            assert admin_user is not None
            assert admin_user.is_admin is True
            
            # Verify system tenant was created
            system_tenant = Tenant.query.filter_by(name='System').first()
            assert system_tenant is not None
            
            # Verify roles were created
            admin_role = Role.query.filter_by(name='admin').first()
            assert admin_role is not None
    
    def test_testing_environment_initialization(self):
        """Test complete initialization in testing environment."""
        with patch.dict(os.environ, {
            'FLASK_ENV': 'testing',
            'DATABASE_URL': 'sqlite:///:memory:'
        }, clear=False):
            app = create_app('testing')
            
            with app.app_context():
                from app import db
                initializer = DatabaseInitializer(app, db)
                
                # Verify environment configuration
                assert initializer.env_config.environment == Environment.TESTING
                assert initializer.env_config.database_type == DatabaseType.SQLITE
                assert initializer.env_config.isolated_database is True
                assert initializer.env_config.auto_seed_data is True
                
                # Test initialization
                result = initializer.initialize()
                
                # Verify initialization succeeded
                assert result.success is True
                assert result.database_type == 'sqlite'
                assert len(result.errors) == 0
                
                # Verify fast initialization options were used
                env_state = initializer.env_initializer.get_initialization_state()
                assert env_state.get('memory_database') is True
    
    def test_production_environment_initialization(self):
        """Test complete initialization in production environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / 'prod_test.db'
            
            with patch.dict(os.environ, {
                'FLASK_ENV': 'production',
                'DATABASE_URL': f'sqlite:///{db_path}',
                'TESTING': 'false'
            }, clear=False):
                app = create_app('testing')  # Use testing config to avoid external dependencies
                
                with app.app_context():
                    from app import db
                    initializer = DatabaseInitializer(app, db)
                    
                    # Verify environment configuration
                    assert initializer.env_config.environment == Environment.PRODUCTION
                    assert initializer.env_config.database_type == DatabaseType.SQLITE
                    assert initializer.env_config.auto_create_database is False
                    assert initializer.env_config.auto_seed_data is False
                    
                    # Test initialization
                    result = initializer.initialize()
                    
                    # Verify initialization succeeded
                    assert result.success is True
                    assert result.database_type == 'sqlite'
                    
                    # Verify production-specific settings
                    env_state = initializer.env_initializer.get_initialization_state()
                    assert env_state.get('production_database') == 'sqlite'
                    assert env_state.get('strict_validation') is True
    
    def test_environment_switching(self):
        """Test that environment switching works correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test development first
            dev_db_path = Path(temp_dir) / 'dev.db'
            
            with patch.dict(os.environ, {
                'FLASK_ENV': 'development',
                'DATABASE_URL': f'sqlite:///{dev_db_path}',
                'TESTING': 'false'
            }, clear=False):
                app = create_app('testing')
                
                with app.app_context():
                    from app import db
                    initializer = DatabaseInitializer(app, db)
                    
                    assert initializer.env_config.environment == Environment.DEVELOPMENT
                    assert initializer.env_config.auto_seed_data is True
            
            # Test production next
            prod_db_path = Path(temp_dir) / 'prod.db'
            
            with patch.dict(os.environ, {
                'FLASK_ENV': 'production',
                'DATABASE_URL': f'sqlite:///{prod_db_path}',
                'TESTING': 'false'
            }, clear=False):
                app = create_app('testing')
                
                with app.app_context():
                    from app import db
                    initializer = DatabaseInitializer(app, db)
                    
                    assert initializer.env_config.environment == Environment.PRODUCTION
                    assert initializer.env_config.auto_seed_data is False
    
    def test_database_type_switching(self):
        """Test switching between database types in different environments."""
        # Test SQLite in development
        with patch.dict(os.environ, {
            'FLASK_ENV': 'development',
            'DATABASE_URL': 'sqlite:///dev.db',
            'TESTING': 'false'
        }, clear=False):
            app = create_app('testing')
            
            with app.app_context():
                from app import db
                initializer = DatabaseInitializer(app, db)
                
                assert initializer.env_config.database_type == DatabaseType.SQLITE
                assert initializer.env_config.auto_create_database is True
        
        # Test PostgreSQL in production
        with patch.dict(os.environ, {
            'FLASK_ENV': 'production',
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/prod_db',
            'TESTING': 'false'
        }, clear=False):
            app = create_app('testing')
            
            with app.app_context():
                from app import db
                initializer = DatabaseInitializer(app, db)
                
                assert initializer.env_config.database_type == DatabaseType.POSTGRESQL
                assert initializer.env_config.auto_create_database is False
    
    def test_initialization_status_tracking(self):
        """Test that initialization status is properly tracked."""
        with patch.dict(os.environ, {
            'FLASK_ENV': 'testing',
            'DATABASE_URL': 'sqlite:///:memory:'
        }, clear=False):
            app = create_app('testing')
            
            with app.app_context():
                from app import db
                initializer = DatabaseInitializer(app, db)
                
                # Before initialization
                status = initializer.get_initialization_status()
                assert status['initialized'] is False
                
                # After initialization
                result = initializer.initialize()
                assert result.success is True
                
                status = initializer.get_initialization_status()
                assert status['initialized'] is True
                assert status['success'] is True
                assert status['database_type'] == 'sqlite'
                assert status['connection_available'] is True
                assert 'last_initialization' in status
                assert 'duration' in status
    
    def test_error_handling_in_different_environments(self):
        """Test error handling works correctly in different environments."""
        # Test with invalid database URL
        with patch.dict(os.environ, {
            'FLASK_ENV': 'development',
            'DATABASE_URL': 'invalid://invalid/url',
            'TESTING': 'false'
        }, clear=False):
            app = create_app('testing')
            
            with app.app_context():
                from app import db
                initializer = DatabaseInitializer(app, db)
                
                # Should fallback to SQLite in development
                assert initializer.env_config.database_type == DatabaseType.SQLITE
                
                # Initialization should still succeed due to fallback
                result = initializer.initialize()
                assert result.success is True
    
    def test_comprehensive_logging(self):
        """Test that comprehensive logging works in all environments."""
        with patch.dict(os.environ, {
            'FLASK_ENV': 'development',
            'DATABASE_URL': 'sqlite:///:memory:',
            'TESTING': 'false'
        }, clear=False):
            app = create_app('testing')
            
            with app.app_context():
                from app import db
                initializer = DatabaseInitializer(app, db)
                
                # Test initialization with logging
                result = initializer.initialize()
                assert result.success is True
                
                # Test log export
                logs_json = initializer.export_initialization_logs('json')
                assert logs_json is not None
                assert len(logs_json) > 0
                
                # Test initialization summary
                summary = initializer.get_initialization_summary()
                assert 'initialization_success' in summary
                assert 'database_type' in summary
                assert 'steps_completed' in summary


if __name__ == '__main__':
    pytest.main([__file__])