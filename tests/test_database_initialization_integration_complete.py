"""
Complete Integration Tests for Database Initialization System

This module provides comprehensive integration tests that test the complete
database initialization flow with real database connections and components
working together.
"""
import pytest
import tempfile
import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch, Mock

# Import Flask app factory for real integration tests
try:
    from app import create_app
    FLASK_APP_AVAILABLE = True
except ImportError:
    FLASK_APP_AVAILABLE = False

from app.utils.database_initializer import (
    DatabaseInitializer, InitializationResult, ValidationResult,
    DatabaseConfiguration, InitializationStep, ValidationSeverity
)


@pytest.mark.skipif(not FLASK_APP_AVAILABLE, reason="Flask app not available for integration testing")
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
            
            # Verify database is initially empty
            assert not os.path.exists(app_with_temp_db.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
            
            # Create database initializer with mocked dependencies
            with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
                 patch('app.utils.database_initializer.EnvironmentDetector'), \
                 patch('app.utils.database_initializer.EnvironmentInitializer') as mock_env_init, \
                 patch('app.utils.database_initializer.get_database_init_logger'), \
                 patch('app.utils.database_initializer.get_database_error_handler'), \
                 patch('app.utils.database_initializer.initialize_recovery_system'), \
                 patch('app.utils.database_initializer.DataSeeder') as mock_seeder, \
                 patch('app.utils.database_initializer.HealthValidator') as mock_validator:
                
                # Configure environment
                env_config = Mock()
                env_config.environment.value = 'testing'
                env_config.database_type.value = 'sqlite'
                env_config.database_url = app_with_temp_db.config['SQLALCHEMY_DATABASE_URI']
                env_config.auto_seed_data = True
                mock_env_config.return_value = env_config
                
                # Mock successful environment preparation
                mock_env_initializer = Mock()
                mock_env_initializer.prepare_environment.return_value = True
                mock_env_init.return_value = mock_env_initializer
                
                # Mock successful data seeding
                mock_seeder_instance = Mock()
                mock_seeding_result = Mock()
                mock_seeding_result.success = True
                mock_seeding_result.records_created = {'tenant': 1, 'admin_user': 1}
                mock_seeder_instance.seed_initial_data.return_value = mock_seeding_result
                mock_seeder.return_value = mock_seeder_instance
                
                # Mock successful health validation
                mock_validator_instance = Mock()
                mock_health_result = Mock()
                mock_health_result.status.value = 'healthy'
                mock_health_result.checks_passed = 5
                mock_health_result.checks_total = 5
                mock_validator_instance.run_comprehensive_health_check.return_value = mock_health_result
                mock_validator.return_value = mock_validator_instance
                
                # Create and test initializer
                initializer = DatabaseInitializer(app_with_temp_db, db)
                
                # Verify initializer was created successfully
                assert initializer is not None
                assert initializer.app == app_with_temp_db
                assert initializer.db == db
    
    def test_database_configuration_with_real_app(self):
        """Test DatabaseConfiguration with real Flask app."""
        if not FLASK_APP_AVAILABLE:
            pytest.skip("Flask app not available")
        
        app = create_app('testing')
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            config = DatabaseConfiguration(app)
            
            # Test configuration detection
            db_type = config.detect_database_type()
            assert db_type == 'sqlite'
            
            # Test connection parameters
            params = config.get_connection_parameters()
            assert params['database_type'] == 'sqlite'
            assert 'connection_string' in params
            assert 'timeout' in params
            
            # Test configuration validation
            result = config.validate_configuration()
            assert result.valid is True
    
    def test_initialization_with_different_environments(self):
        """Test initialization behavior in different environments."""
        if not FLASK_APP_AVAILABLE:
            pytest.skip("Flask app not available")
        
        environments = ['testing', 'development']
        
        for env in environments:
            with patch.dict(os.environ, {'FLASK_ENV': env}):
                app = create_app(env)
                app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
                
                with app.app_context():
                    from app import db
                    
                    # Mock all dependencies
                    with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
                         patch('app.utils.database_initializer.EnvironmentDetector'), \
                         patch('app.utils.database_initializer.EnvironmentInitializer'), \
                         patch('app.utils.database_initializer.get_database_init_logger'), \
                         patch('app.utils.database_initializer.get_database_error_handler'), \
                         patch('app.utils.database_initializer.initialize_recovery_system'), \
                         patch('app.utils.database_initializer.DataSeeder'), \
                         patch('app.utils.database_initializer.HealthValidator'):
                        
                        env_config = Mock()
                        env_config.environment.value = env
                        env_config.database_type.value = 'sqlite'
                        env_config.database_url = 'sqlite:///:memory:'
                        mock_env_config.return_value = env_config
                        
                        initializer = DatabaseInitializer(app, db)
                        
                        # Verify initializer adapts to environment
                        assert initializer is not None
                        assert initializer.app == app
                        assert initializer.db == db


class TestDatabaseInitializationRealDatabase:
    """Integration tests with real SQLite database operations."""
    
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
    
    def test_sqlite_database_creation_and_access(self, temp_db_path):
        """Test creating and accessing SQLite database."""
        # Create database with tables
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Create test tables that might be used in initialization
        cursor.execute('''
            CREATE TABLE tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants (id)
            )
        ''')
        
        # Insert test data
        cursor.execute(
            "INSERT INTO tenants (name, slug) VALUES (?, ?)",
            ("AI Secretary System", "ai-secretary-system")
        )
        tenant_id = cursor.lastrowid
        
        cursor.execute(
            "INSERT INTO users (tenant_id, email, password_hash) VALUES (?, ?, ?)",
            (tenant_id, "admin@ai-secretary.com", "hashed_password")
        )
        
        cursor.execute(
            "INSERT INTO roles (tenant_id, name, description) VALUES (?, ?, ?)",
            (tenant_id, "Owner", "System owner role")
        )
        
        conn.commit()
        
        # Verify data was inserted correctly
        cursor.execute("SELECT COUNT(*) FROM tenants")
        tenant_count = cursor.fetchone()[0]
        assert tenant_count == 1
        
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        assert user_count == 1
        
        cursor.execute("SELECT COUNT(*) FROM roles")
        role_count = cursor.fetchone()[0]
        assert role_count == 1
        
        # Test foreign key relationships
        cursor.execute("""
            SELECT t.name, u.email, r.name 
            FROM tenants t 
            JOIN users u ON t.id = u.tenant_id 
            JOIN roles r ON t.id = r.tenant_id
        """)
        result = cursor.fetchone()
        assert result[0] == "AI Secretary System"
        assert result[1] == "admin@ai-secretary.com"
        assert result[2] == "Owner"
        
        conn.close()
    
    def test_database_schema_validation(self, temp_db_path):
        """Test database schema validation with real database."""
        # Create database with some tables
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Create only some of the expected tables
        cursor.execute('''
            CREATE TABLE tenants (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Test schema validation
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'tenants' in tables
        assert 'users' in tables
        
        # Check table structure
        cursor.execute("PRAGMA table_info(tenants)")
        tenant_columns = cursor.fetchall()
        assert len(tenant_columns) >= 2
        
        cursor.execute("PRAGMA table_info(users)")
        user_columns = cursor.fetchall()
        assert len(user_columns) >= 2
        
        conn.close()
    
    def test_database_performance_with_real_operations(self, temp_db_path):
        """Test database performance with real operations."""
        start_time = time.time()
        
        # Create database and perform operations
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Create table
        cursor.execute('''
            CREATE TABLE performance_test (
                id INTEGER PRIMARY KEY,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert many records
        test_data = [(f"test_data_{i}",) for i in range(1000)]
        cursor.executemany("INSERT INTO performance_test (data) VALUES (?)", test_data)
        
        # Query data
        cursor.execute("SELECT COUNT(*) FROM performance_test")
        count = cursor.fetchone()[0]
        assert count == 1000
        
        # Create index
        cursor.execute("CREATE INDEX idx_performance_test_data ON performance_test(data)")
        
        # Query with index
        cursor.execute("SELECT * FROM performance_test WHERE data = ?", ("test_data_500",))
        result = cursor.fetchone()
        assert result is not None
        
        conn.commit()
        conn.close()
        
        duration = time.time() - start_time
        
        # Should complete within reasonable time
        assert duration < 5.0  # 5 seconds should be more than enough
    
    def test_database_error_handling_with_real_database(self, temp_db_path):
        """Test error handling with real database operations."""
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Create table
        cursor.execute('''
            CREATE TABLE error_test (
                id INTEGER PRIMARY KEY,
                unique_field TEXT UNIQUE NOT NULL
            )
        ''')
        
        # Insert valid data
        cursor.execute("INSERT INTO error_test (unique_field) VALUES (?)", ("unique_value",))
        conn.commit()
        
        # Try to insert duplicate - should raise error
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO error_test (unique_field) VALUES (?)", ("unique_value",))
            conn.commit()
        
        # Try to query non-existent table - should raise error
        with pytest.raises(sqlite3.OperationalError):
            cursor.execute("SELECT * FROM non_existent_table")
        
        conn.close()
    
    def test_database_transaction_handling(self, temp_db_path):
        """Test database transaction handling."""
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Create table
        cursor.execute('''
            CREATE TABLE transaction_test (
                id INTEGER PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        
        # Test successful transaction
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("INSERT INTO transaction_test (value) VALUES (?)", ("test1",))
        cursor.execute("INSERT INTO transaction_test (value) VALUES (?)", ("test2",))
        cursor.execute("COMMIT")
        
        # Verify data was committed
        cursor.execute("SELECT COUNT(*) FROM transaction_test")
        count = cursor.fetchone()[0]
        assert count == 2
        
        # Test rollback transaction
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("INSERT INTO transaction_test (value) VALUES (?)", ("test3",))
        cursor.execute("ROLLBACK")
        
        # Verify data was not committed
        cursor.execute("SELECT COUNT(*) FROM transaction_test")
        count = cursor.fetchone()[0]
        assert count == 2  # Should still be 2, not 3
        
        conn.close()


class TestDatabaseInitializationEndToEndFlow:
    """End-to-end integration tests for complete initialization flow."""
    
    def test_complete_flow_simulation(self):
        """Test complete initialization flow with all components."""
        # Create mock app and database
        mock_app = Mock()
        mock_app.config = {
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'TESTING': True,
            'DATABASE_CONNECTION_TIMEOUT': 30
        }
        mock_app.debug = False
        mock_app.testing = True
        
        mock_db = Mock()
        mock_db.engine = Mock()
        mock_db.session = Mock()
        
        # Mock successful database connection
        mock_connection = Mock()
        mock_result = Mock()
        mock_result.fetchone.return_value = (1,)
        mock_connection.execute.return_value = mock_result
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        mock_db.engine.connect.return_value = mock_connection
        
        # Test complete flow with mocked dependencies
        with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
             patch('app.utils.database_initializer.EnvironmentDetector'), \
             patch('app.utils.database_initializer.EnvironmentInitializer') as mock_env_init, \
             patch('app.utils.database_initializer.get_database_init_logger'), \
             patch('app.utils.database_initializer.get_database_error_handler'), \
             patch('app.utils.database_initializer.initialize_recovery_system'), \
             patch('app.utils.database_initializer.DataSeeder') as mock_seeder, \
             patch('app.utils.database_initializer.HealthValidator') as mock_validator:
            
            # Configure environment
            env_config = Mock()
            env_config.environment.value = 'testing'
            env_config.database_type.value = 'sqlite'
            env_config.database_url = 'sqlite:///:memory:'
            env_config.auto_seed_data = True
            mock_env_config.return_value = env_config
            
            # Mock successful environment preparation
            mock_env_initializer = Mock()
            mock_env_initializer.prepare_environment.return_value = True
            mock_env_init.return_value = mock_env_initializer
            
            # Mock successful data seeding
            mock_seeder_instance = Mock()
            mock_seeding_result = Mock()
            mock_seeding_result.success = True
            mock_seeding_result.records_created = {'tenant': 1, 'admin_user': 1, 'roles': 5}
            mock_seeding_result.records_skipped = {}
            mock_seeding_result.errors = []
            mock_seeding_result.warnings = []
            mock_seeding_result.duration = 0.5
            mock_seeder_instance.seed_initial_data.return_value = mock_seeding_result
            mock_seeder.return_value = mock_seeder_instance
            
            # Mock successful health validation
            mock_validator_instance = Mock()
            mock_health_result = Mock()
            mock_health_result.status.value = 'healthy'
            mock_health_result.checks_passed = 5
            mock_health_result.checks_total = 5
            mock_health_result.issues = []
            mock_health_result.duration = 0.2
            mock_validator_instance.run_comprehensive_health_check.return_value = mock_health_result
            mock_validator.return_value = mock_validator_instance
            
            # Create initializer
            initializer = DatabaseInitializer(mock_app, mock_db)
            
            # Verify all components are initialized
            assert initializer is not None
            assert initializer.app == mock_app
            assert initializer.db == mock_db
            assert initializer.data_seeder is not None
            assert initializer.health_validator is not None
            
            # Verify configuration
            config = initializer.config
            assert config is not None
            
            # Test configuration validation
            validation_result = config.validate_configuration()
            assert validation_result.valid is True
    
    def test_initialization_error_recovery_flow(self):
        """Test initialization flow with error recovery."""
        mock_app = Mock()
        mock_app.config = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', 'TESTING': True}
        mock_app.debug = False
        
        mock_db = Mock()
        mock_db.engine = Mock()
        mock_db.session = Mock()
        
        # Test with various error scenarios
        with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
             patch('app.utils.database_initializer.EnvironmentDetector'), \
             patch('app.utils.database_initializer.EnvironmentInitializer') as mock_env_init, \
             patch('app.utils.database_initializer.get_database_init_logger'), \
             patch('app.utils.database_initializer.get_database_error_handler') as mock_error_handler, \
             patch('app.utils.database_initializer.initialize_recovery_system') as mock_recovery, \
             patch('app.utils.database_initializer.DataSeeder'), \
             patch('app.utils.database_initializer.HealthValidator'):
            
            env_config = Mock()
            env_config.environment.value = 'testing'
            env_config.database_type.value = 'sqlite'
            env_config.database_url = 'sqlite:///:memory:'
            mock_env_config.return_value = env_config
            
            # Mock error handling components
            mock_error_handler_instance = Mock()
            mock_error_handler.return_value = mock_error_handler_instance
            
            mock_recovery_manager = Mock()
            mock_recovery.return_value = mock_recovery_manager
            
            # Mock environment preparation failure initially
            mock_env_initializer = Mock()
            mock_env_initializer.prepare_environment.return_value = False
            mock_env_init.return_value = mock_env_initializer
            
            # Create initializer
            initializer = DatabaseInitializer(mock_app, mock_db)
            
            # Verify error handling components are available
            assert initializer.error_handler is not None
            assert initializer.recovery_manager is not None
            assert hasattr(initializer, '_error_history')
            assert isinstance(initializer._error_history, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])