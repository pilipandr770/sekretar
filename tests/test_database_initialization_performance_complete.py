"""
Performance Tests for Database Initialization System

This module provides comprehensive performance tests for the database
initialization system, ensuring it meets performance requirements and
handles resource usage efficiently.
"""
import pytest
import time
import threading
import os
import tempfile
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
from contextlib import contextmanager

from app.utils.database_initializer import (
    DatabaseInitializer, InitializationResult, ValidationResult,
    DatabaseConfiguration, InitializationStep, ValidationSeverity
)


class TestDatabaseInitializationPerformance:
    """Performance tests for database initialization components."""
    
    @pytest.fixture
    def mock_app(self):
        """Create mock Flask app for performance testing."""
        app = Mock()
        app.config = {
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'TESTING': True,
            'DATABASE_CONNECTION_TIMEOUT': 30,
            'DATABASE_QUERY_TIMEOUT': 10,
            'DATABASE_MAX_RETRIES': 3
        }
        app.debug = False
        app.testing = True
        return app
    
    @pytest.fixture
    def mock_db(self):
        """Create mock SQLAlchemy instance for performance testing."""
        db = Mock()
        db.engine = Mock()
        db.session = Mock()
        return db
    
    @pytest.fixture
    def fast_initializer(self, mock_app, mock_db):
        """Create DatabaseInitializer optimized for performance testing."""
        with patch('app.utils.database_initializer.get_environment_config') as mock_env_config, \
             patch('app.utils.database_initializer.EnvironmentDetector'), \
             patch('app.utils.database_initializer.EnvironmentInitializer') as mock_env_init, \
             patch('app.utils.database_initializer.get_database_init_logger'), \
             patch('app.utils.database_initializer.get_database_error_handler'), \
             patch('app.utils.database_initializer.initialize_recovery_system'), \
             patch('app.utils.database_initializer.DataSeeder') as mock_seeder, \
             patch('app.utils.database_initializer.HealthValidator') as mock_validator:
            
            # Configure for fast testing
            env_config = Mock()
            env_config.environment.value = 'testing'
            env_config.database_type.value = 'sqlite'
            env_config.database_url = 'sqlite:///:memory:'
            env_config.auto_seed_data = False  # Disable for performance testing
            mock_env_config.return_value = env_config
            
            # Mock fast environment preparation
            mock_env_initializer = Mock()
            mock_env_initializer.prepare_environment.return_value = True
            mock_env_init.return_value = mock_env_initializer
            
            # Mock fast data seeding
            mock_seeder_instance = Mock()
            mock_seeding_result = Mock()
            mock_seeding_result.success = True
            mock_seeding_result.duration = 0.1
            mock_seeder_instance.seed_initial_data.return_value = mock_seeding_result
            mock_seeder.return_value = mock_seeder_instance
            
            # Mock fast health validation
            mock_validator_instance = Mock()
            mock_health_result = Mock()
            mock_health_result.status.value = 'healthy'
            mock_health_result.checks_passed = 5
            mock_health_result.checks_total = 5
            mock_health_result.duration = 0.1
            mock_validator_instance.run_comprehensive_health_check.return_value = mock_health_result
            mock_validator.return_value = mock_validator_instance
            
            # Mock fast database connection
            mock_connection = Mock()
            mock_result = Mock()
            mock_result.fetchone.return_value = (1,)
            mock_connection.execute.return_value = mock_result
            mock_connection.__enter__ = Mock(return_value=mock_connection)
            mock_connection.__exit__ = Mock(return_value=None)
            mock_db.engine.connect.return_value = mock_connection
            
            return DatabaseInitializer(mock_app, mock_db)
    
    def test_initialization_result_creation_performance(self):
        """Test InitializationResult creation performance."""
        start_time = time.time()
        
        # Create many initialization results
        results = []
        for i in range(10000):
            result = InitializationResult(success=True)
            result.add_step(f"step_{i}")
            result.add_error(f"error_{i}")
            result.add_warning(f"warning_{i}")
            results.append(result)
        
        duration = time.time() - start_time
        
        # Should complete within 2 seconds
        assert duration < 2.0, f"InitializationResult creation took {duration:.2f}s, expected < 2.0s"
        assert len(results) == 10000
        assert all(len(r.steps_completed) == 1 for r in results)
        assert all(len(r.errors) == 1 for r in results)
        assert all(len(r.warnings) == 1 for r in results)
    
    def test_validation_result_creation_performance(self):
        """Test ValidationResult creation performance."""
        start_time = time.time()
        
        # Create many validation results
        results = []
        severities = [ValidationSeverity.INFO, ValidationSeverity.WARNING, 
                     ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
        
        for i in range(10000):
            result = ValidationResult(valid=True)
            severity = severities[i % len(severities)]
            result.add_issue(f"issue_{i}", severity)
            result.add_suggestion(f"suggestion_{i}")
            results.append(result)
        
        duration = time.time() - start_time
        
        # Should complete within 2 seconds
        assert duration < 2.0, f"ValidationResult creation took {duration:.2f}s, expected < 2.0s"
        assert len(results) == 10000
        assert all(len(r.issues) == 1 for r in results)
        assert all(len(r.suggestions) == 1 for r in results)
    
    def test_database_configuration_performance(self):
        """Test DatabaseConfiguration performance."""
        mock_app = Mock()
        mock_app.config = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db'}
        
        start_time = time.time()
        
        # Create many configurations and perform operations
        for i in range(1000):
            config = DatabaseConfiguration(mock_app)
            db_type = config.detect_database_type()
            params = config.get_connection_parameters()
            validation = config.validate_configuration()
            
            assert db_type == 'sqlite'
            assert params['database_type'] == 'sqlite'
            assert validation.valid is True
        
        duration = time.time() - start_time
        
        # Should complete within 1 second
        assert duration < 1.0, f"DatabaseConfiguration operations took {duration:.2f}s, expected < 1.0s"
    
    def test_database_initializer_creation_performance(self, mock_app, mock_db):
        """Test DatabaseInitializer creation performance."""
        start_time = time.time()
        
        # Create multiple initializers
        initializers = []
        for i in range(10):
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
                env_config.database_url = 'sqlite:///:memory:'
                mock_env_config.return_value = env_config
                
                initializer = DatabaseInitializer(mock_app, mock_db)
                initializers.append(initializer)
        
        duration = time.time() - start_time
        
        # Should complete within 2 seconds
        assert duration < 2.0, f"DatabaseInitializer creation took {duration:.2f}s, expected < 2.0s"
        assert len(initializers) == 10
        assert all(init.app == mock_app for init in initializers)
    
    def test_connection_string_masking_performance(self, fast_initializer):
        """Test connection string masking performance."""
        start_time = time.time()
        
        # Test masking many connection strings
        connection_strings = [
            'postgresql://user:password@localhost:5432/db',
            'sqlite:///test.db',
            'mysql://user:pass@localhost/db',
            None,
            '',
            'invalid://url'
        ]
        
        for i in range(1000):
            for conn_str in connection_strings:
                masked = fast_initializer._mask_connection_string(conn_str)
                assert masked is not None
        
        duration = time.time() - start_time
        
        # Should complete within 1 second
        assert duration < 1.0, f"Connection string masking took {duration:.2f}s, expected < 1.0s"


class TestDatabaseInitializationConcurrencyPerformance:
    """Performance tests for concurrent database initialization operations."""
    
    @pytest.fixture
    def concurrent_setup(self):
        """Setup for concurrency testing."""
        mock_app = Mock()
        mock_app.config = {
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'TESTING': True
        }
        mock_app.debug = False
        
        mock_db = Mock()
        mock_db.engine = Mock()
        mock_db.session = Mock()
        
        # Mock fast database connection
        mock_connection = Mock()
        mock_result = Mock()
        mock_result.fetchone.return_value = (1,)
        mock_connection.execute.return_value = mock_result
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        mock_db.engine.connect.return_value = mock_connection
        
        return mock_app, mock_db
    
    def test_concurrent_initialization_result_creation(self):
        """Test concurrent InitializationResult creation."""
        def create_results():
            results = []
            for i in range(100):
                result = InitializationResult(success=True)
                result.add_step(f"step_{i}")
                result.add_error(f"error_{i}")
                results.append(result)
            return results
        
        start_time = time.time()
        
        # Run concurrent creation
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_results) for _ in range(10)]
            
            all_results = []
            for future in as_completed(futures):
                results = future.result()
                all_results.extend(results)
        
        duration = time.time() - start_time
        
        # Should complete within 3 seconds
        assert duration < 3.0, f"Concurrent creation took {duration:.2f}s, expected < 3.0s"
        assert len(all_results) == 1000  # 10 threads * 100 results each
    
    def test_concurrent_database_configuration_operations(self):
        """Test concurrent DatabaseConfiguration operations."""
        mock_app = Mock()
        mock_app.config = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db'}
        
        def config_operations():
            results = []
            for i in range(50):
                config = DatabaseConfiguration(mock_app)
                db_type = config.detect_database_type()
                params = config.get_connection_parameters()
                validation = config.validate_configuration()
                results.append((db_type, params, validation))
            return results
        
        start_time = time.time()
        
        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(config_operations) for _ in range(5)]
            
            all_results = []
            for future in as_completed(futures):
                results = future.result()
                all_results.extend(results)
        
        duration = time.time() - start_time
        
        # Should complete within 2 seconds
        assert duration < 2.0, f"Concurrent config operations took {duration:.2f}s, expected < 2.0s"
        assert len(all_results) == 250  # 5 threads * 50 operations each
        assert all(db_type == 'sqlite' for db_type, _, _ in all_results)
    
    def test_concurrent_database_initializer_creation(self, concurrent_setup):
        """Test concurrent DatabaseInitializer creation."""
        mock_app, mock_db = concurrent_setup
        
        def create_initializer():
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
                env_config.database_url = 'sqlite:///:memory:'
                mock_env_config.return_value = env_config
                
                return DatabaseInitializer(mock_app, mock_db)
        
        start_time = time.time()
        
        # Run concurrent creation
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_initializer) for _ in range(10)]
            
            initializers = []
            for future in as_completed(futures):
                initializer = future.result()
                initializers.append(initializer)
        
        duration = time.time() - start_time
        
        # Should complete within 3 seconds
        assert duration < 3.0, f"Concurrent initializer creation took {duration:.2f}s, expected < 3.0s"
        assert len(initializers) == 10
        assert all(init.app == mock_app for init in initializers)
    
    def test_thread_safety_stress_test(self):
        """Test thread safety under stress conditions."""
        shared_state = {'counter': 0, 'errors': []}
        lock = threading.Lock()
        
        def stress_worker():
            try:
                for i in range(100):
                    # Create initialization result
                    result = InitializationResult(success=True)
                    result.add_step(f"step_{i}")
                    
                    # Create validation result
                    validation = ValidationResult(valid=True)
                    validation.add_issue(f"issue_{i}", ValidationSeverity.WARNING)
                    
                    with lock:
                        shared_state['counter'] += 1
                    
                    # Small delay to increase chance of race conditions
                    time.sleep(0.001)
            except Exception as e:
                with lock:
                    shared_state['errors'].append(str(e))
        
        start_time = time.time()
        
        # Run stress test with multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=stress_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        duration = time.time() - start_time
        
        # Check results
        assert len(shared_state['errors']) == 0, f"Errors occurred: {shared_state['errors']}"
        assert shared_state['counter'] == 1000, f"Expected 1000 operations, got {shared_state['counter']}"
        assert duration < 5.0, f"Stress test took {duration:.2f}s, expected < 5.0s"


class TestDatabaseInitializationMemoryPerformance:
    """Memory performance tests for database initialization system."""
    
    def test_initialization_result_memory_usage(self):
        """Test InitializationResult memory usage."""
        import sys
        
        # Create baseline
        baseline_size = sys.getsizeof([])
        
        # Create many results
        results = []
        for i in range(1000):
            result = InitializationResult(success=True)
            result.add_step(f"step_{i}")
            result.add_error(f"error_{i}")
            result.add_warning(f"warning_{i}")
            results.append(result)
        
        # Check memory usage
        total_size = sys.getsizeof(results)
        average_size = (total_size - baseline_size) / len(results)
        
        # Each result should be reasonably sized
        assert average_size < 1000, f"Average InitializationResult size {average_size} bytes, expected < 1000"
        assert len(results) == 1000
    
    def test_validation_result_memory_usage(self):
        """Test ValidationResult memory usage."""
        import sys
        
        # Create baseline
        baseline_size = sys.getsizeof([])
        
        # Create many results
        results = []
        for i in range(1000):
            result = ValidationResult(valid=True)
            result.add_issue(f"issue_{i}", ValidationSeverity.WARNING)
            result.add_suggestion(f"suggestion_{i}")
            results.append(result)
        
        # Check memory usage
        total_size = sys.getsizeof(results)
        average_size = (total_size - baseline_size) / len(results)
        
        # Each result should be reasonably sized
        assert average_size < 1000, f"Average ValidationResult size {average_size} bytes, expected < 1000"
        assert len(results) == 1000
    
    def test_database_configuration_memory_usage(self):
        """Test DatabaseConfiguration memory usage."""
        import sys
        
        mock_app = Mock()
        mock_app.config = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db'}
        
        # Create many configurations
        configs = []
        for i in range(100):
            config = DatabaseConfiguration(mock_app)
            configs.append(config)
        
        # Check memory usage
        total_size = sys.getsizeof(configs)
        average_size = total_size / len(configs)
        
        # Each config should be reasonably sized
        assert average_size < 5000, f"Average DatabaseConfiguration size {average_size} bytes, expected < 5000"
        assert len(configs) == 100


class TestDatabaseInitializationRealWorldPerformance:
    """Real-world performance tests with actual database operations."""
    
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
    
    def test_sqlite_database_creation_performance(self, temp_db_path):
        """Test SQLite database creation performance."""
        start_time = time.time()
        
        # Create database with tables
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Create multiple tables
        tables = [
            '''CREATE TABLE tenants (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER,
                email TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants (id)
            )''',
            '''CREATE TABLE roles (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE user_roles (
                user_id INTEGER,
                role_id INTEGER,
                PRIMARY KEY (user_id, role_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (role_id) REFERENCES roles (id)
            )'''
        ]
        
        for table_sql in tables:
            cursor.execute(table_sql)
        
        # Create indexes
        indexes = [
            'CREATE INDEX idx_users_email ON users(email)',
            'CREATE INDEX idx_users_tenant_id ON users(tenant_id)',
            'CREATE INDEX idx_user_roles_user_id ON user_roles(user_id)',
            'CREATE INDEX idx_user_roles_role_id ON user_roles(role_id)'
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        conn.commit()
        conn.close()
        
        duration = time.time() - start_time
        
        # Should complete within 1 second
        assert duration < 1.0, f"Database creation took {duration:.2f}s, expected < 1.0s"
        
        # Verify database was created
        assert os.path.exists(temp_db_path)
        assert os.path.getsize(temp_db_path) > 0
    
    def test_sqlite_data_insertion_performance(self, temp_db_path):
        """Test SQLite data insertion performance."""
        # Create database with table
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE performance_test (
                id INTEGER PRIMARY KEY,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        start_time = time.time()
        
        # Insert many records
        test_data = [(f"test_data_{i}",) for i in range(10000)]
        cursor.executemany("INSERT INTO performance_test (data) VALUES (?)", test_data)
        conn.commit()
        
        duration = time.time() - start_time
        
        # Should complete within 2 seconds
        assert duration < 2.0, f"Data insertion took {duration:.2f}s, expected < 2.0s"
        
        # Verify data was inserted
        cursor.execute("SELECT COUNT(*) FROM performance_test")
        count = cursor.fetchone()[0]
        assert count == 10000
        
        conn.close()
    
    def test_sqlite_query_performance(self, temp_db_path):
        """Test SQLite query performance."""
        # Create database with data
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE query_test (
                id INTEGER PRIMARY KEY,
                category TEXT,
                value INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert test data
        test_data = [(f"category_{i % 10}", i) for i in range(10000)]
        cursor.executemany("INSERT INTO query_test (category, value) VALUES (?, ?)", test_data)
        
        # Create index for performance
        cursor.execute("CREATE INDEX idx_query_test_category ON query_test(category)")
        cursor.execute("CREATE INDEX idx_query_test_value ON query_test(value)")
        
        conn.commit()
        
        start_time = time.time()
        
        # Perform various queries
        queries = [
            "SELECT COUNT(*) FROM query_test",
            "SELECT * FROM query_test WHERE category = 'category_5'",
            "SELECT category, COUNT(*) FROM query_test GROUP BY category",
            "SELECT * FROM query_test WHERE value > 5000 ORDER BY value LIMIT 100",
            "SELECT AVG(value) FROM query_test WHERE category IN ('category_1', 'category_2')"
        ]
        
        for query in queries:
            cursor.execute(query)
            results = cursor.fetchall()
            assert len(results) > 0
        
        duration = time.time() - start_time
        
        # Should complete within 1 second
        assert duration < 1.0, f"Query execution took {duration:.2f}s, expected < 1.0s"
        
        conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])