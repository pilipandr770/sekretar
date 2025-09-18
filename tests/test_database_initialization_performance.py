"""
Performance tests for database initialization system.

This module provides performance and load tests for the database initialization
system, ensuring it meets performance requirements and handles resource usage
efficiently.
"""
import pytest
import time
import threading
import psutil
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
from contextlib import contextmanager

from app.utils.database_initializer import DatabaseInitializer, InitializationResult, ValidationResult
from app.utils.data_seeder import DataSeeder, SeedingResult
from app.utils.health_validator import HealthValidator, HealthCheckResult, HealthStatus
from app.utils.environment_config import Environment, DatabaseType


class TestInitializationPerformance:
    """Test cases for initialization performance requirements."""
    
    @pytest.fixture
    def fast_initializer(self):
        """Create DatabaseInitializer optimized for fast testing."""
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
            env_config.auto_seed_data = False  # Disable for performance testing
            mock_env_config.return_value = env_config
            
            initializer = DatabaseInitializer(app, db)
            
            # Mock all components to succeed quickly
            initializer.env_initializer.prepare_environment.return_value = True
            initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
            initializer._test_connection = Mock(return_value=True)
            initializer._get_environment_connection_parameters = Mock(return_value={
                'database_type': 'sqlite',
                'connection_string': 'sqlite:///:memory:'
            })
            
            # Mock fast health validation
            initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
                status=Mock(value='healthy'),
                checks_passed=5,
                checks_total=5
            )
            
            return initializer
    
    def test_initialization_time_under_5_seconds(self, fast_initializer):
        """Test that initialization completes within 5 seconds."""
        start_time = time.time()
        
        result = fast_initializer.initialize()
        
        duration = time.time() - start_time
        
        assert result.success is True
        assert duration < 5.0, f"Initialization took {duration:.2f}s, expected < 5.0s"
        assert result.duration < 5.0
    
    def test_initialization_time_under_2_seconds_memory_db(self, fast_initializer):
        """Test that initialization with in-memory DB completes within 2 seconds."""
        # Ensure we're using in-memory database
        fast_initializer._get_environment_connection_parameters.return_value = {
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///:memory:'
        }
        
        start_time = time.time()
        
        result = fast_initializer.initialize()
        
        duration = time.time() - start_time
        
        assert result.success is True
        assert duration < 2.0, f"In-memory initialization took {duration:.2f}s, expected < 2.0s"
    
    def test_validation_time_under_1_second(self, fast_initializer):
        """Test that validation completes within 1 second."""
        # Mock fast validation
        fast_initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5,
            issues=[]
        )
        
        start_time = time.time()
        
        result = fast_initializer.validate_setup()
        
        duration = time.time() - start_time
        
        assert result.valid is True
        assert duration < 1.0, f"Validation took {duration:.2f}s, expected < 1.0s"
    
    def test_connection_test_time_under_500ms(self, fast_initializer):
        """Test that connection test completes within 500ms."""
        # Mock very fast connection
        mock_connection = Mock()
        mock_result = Mock()
        mock_result.fetchone.return_value = (1,)
        mock_connection.execute.return_value = mock_result
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        
        fast_initializer.db.engine.connect.return_value = mock_connection
        
        conn_params = {
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///:memory:'
        }
        
        start_time = time.time()
        
        result = fast_initializer._test_connection(conn_params)
        
        duration = time.time() - start_time
        
        assert result is True
        assert duration < 0.5, f"Connection test took {duration:.3f}s, expected < 0.5s"
    
    def test_multiple_initializations_performance(self, fast_initializer):
        """Test performance of multiple consecutive initializations."""
        durations = []
        
        for i in range(5):
            start_time = time.time()
            result = fast_initializer.initialize()
            duration = time.time() - start_time
            
            assert result.success is True
            durations.append(duration)
        
        # Each initialization should be fast
        for i, duration in enumerate(durations):
            assert duration < 5.0, f"Initialization {i+1} took {duration:.2f}s, expected < 5.0s"
        
        # Average should be reasonable
        avg_duration = sum(durations) / len(durations)
        assert avg_duration < 3.0, f"Average initialization time {avg_duration:.2f}s, expected < 3.0s"
    
    @contextmanager
    def measure_memory_usage(self):
        """Context manager to measure memory usage."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        yield
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50, f"Memory increased by {memory_increase:.1f}MB, expected < 50MB"
    
    def test_initialization_memory_usage(self, fast_initializer):
        """Test that initialization doesn't use excessive memory."""
        with self.measure_memory_usage():
            result = fast_initializer.initialize()
            assert result.success is True
    
    def test_repeated_initialization_memory_stability(self, fast_initializer):
        """Test that repeated initializations don't cause memory leaks."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Run multiple initializations
        for _ in range(10):
            result = fast_initializer.initialize()
            assert result.success is True
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory should not increase significantly with repeated initializations
        assert memory_increase < 20, f"Memory increased by {memory_increase:.1f}MB after 10 initializations"


class TestDataSeedingPerformance:
    """Test cases for data seeding performance requirements."""
    
    @pytest.fixture
    def fast_seeder(self):
        """Create DataSeeder optimized for fast testing."""
        app = Mock()
        app.config = {'TESTING': True}
        app.debug = False
        
        db = Mock()
        db.session = Mock()
        
        with patch('app.utils.data_seeder.get_database_init_logger'):
            seeder = DataSeeder(app, db)
            
            # Mock fast operations
            mock_tenant = Mock()
            mock_tenant.id = 1
            seeder._create_system_tenant = Mock(return_value={
                'success': True,
                'tenant': mock_tenant,
                'created': True
            })
            
            seeder._create_system_roles = Mock(return_value={
                'success': True,
                'created_count': 5,
                'skipped_count': 0
            })
            
            mock_user = Mock()
            seeder._create_admin_user = Mock(return_value={
                'success': True,
                'user': mock_user,
                'created': True
            })
            
            return seeder
    
    def test_seeding_time_under_3_seconds(self, fast_seeder):
        """Test that data seeding completes within 3 seconds."""
        start_time = time.time()
        
        result = fast_seeder.seed_initial_data()
        
        duration = time.time() - start_time
        
        assert result.success is True
        assert duration < 3.0, f"Seeding took {duration:.2f}s, expected < 3.0s"
        assert result.duration < 3.0
    
    def test_seeding_with_existing_data_performance(self, fast_seeder):
        """Test performance when seeding with existing data (should be faster)."""
        # Mock existing data (should skip creation)
        mock_tenant = Mock()
        mock_tenant.id = 1
        fast_seeder._create_system_tenant = Mock(return_value={
            'success': True,
            'tenant': mock_tenant,
            'created': False  # Already exists
        })
        
        fast_seeder._create_system_roles = Mock(return_value={
            'success': True,
            'created_count': 0,
            'skipped_count': 5  # All skipped
        })
        
        mock_user = Mock()
        fast_seeder._create_admin_user = Mock(return_value={
            'success': True,
            'user': mock_user,
            'created': False  # Already exists
        })
        
        start_time = time.time()
        
        result = fast_seeder.seed_initial_data()
        
        duration = time.time() - start_time
        
        assert result.success is True
        assert duration < 1.0, f"Seeding with existing data took {duration:.2f}s, expected < 1.0s"
    
    def test_validation_performance(self, fast_seeder):
        """Test performance of seed data validation."""
        with patch('app.utils.data_seeder.Tenant') as mock_tenant, \
             patch('app.utils.data_seeder.User') as mock_user, \
             patch('app.utils.data_seeder.Role') as mock_role:
            
            # Mock existing data
            mock_system_tenant = Mock()
            mock_system_tenant.id = 1
            mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
            
            mock_admin_user = Mock()
            mock_admin_user.check_password.return_value = True
            mock_admin_user.has_role.return_value = True
            mock_user.query.filter_by.return_value.first.return_value = mock_admin_user
            
            mock_roles = [Mock() for _ in range(5)]
            mock_role.query.filter_by.return_value.first.side_effect = mock_roles
            
            start_time = time.time()
            
            result = fast_seeder.validate_seed_data()
            
            duration = time.time() - start_time
            
            assert result is True
            assert duration < 0.5, f"Validation took {duration:.3f}s, expected < 0.5s"


class TestHealthValidationPerformance:
    """Test cases for health validation performance requirements."""
    
    @pytest.fixture
    def fast_validator(self):
        """Create HealthValidator optimized for fast testing."""
        app = Mock()
        app.config = {'TESTING': True}
        app.debug = False
        
        db = Mock()
        db.engine = Mock()
        db.session = Mock()
        
        with patch('app.utils.health_validator.get_database_init_logger'):
            validator = HealthValidator(app, db)
            
            # Mock fast connectivity
            mock_connection = Mock()
            mock_result = Mock()
            mock_result.fetchone.return_value = (1,)
            mock_connection.execute.return_value = mock_result
            mock_connection.__enter__ = Mock(return_value=mock_connection)
            mock_connection.__exit__ = Mock(return_value=None)
            
            validator.db.engine.connect.return_value = mock_connection
            
            return validator
    
    def test_connectivity_validation_time_under_1_second(self, fast_validator):
        """Test that connectivity validation completes within 1 second."""
        start_time = time.time()
        
        result = fast_validator.validate_connectivity()
        
        duration = time.time() - start_time
        
        assert result is True
        assert duration < 1.0, f"Connectivity validation took {duration:.3f}s, expected < 1.0s"
    
    @patch('app.utils.health_validator.inspect')
    def test_schema_validation_time_under_2_seconds(self, mock_inspect, fast_validator):
        """Test that schema validation completes within 2 seconds."""
        # Mock inspector with reasonable data
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = [
            'tenants', 'users', 'roles', 'user_roles',
            'channels', 'threads', 'inbox_messages'
        ]
        mock_inspect.return_value = mock_inspector
        
        # Mock table structure validation
        fast_validator._validate_table_structure = Mock()
        
        start_time = time.time()
        
        result = fast_validator.validate_schema_integrity()
        
        duration = time.time() - start_time
        
        assert result.valid is True
        assert duration < 2.0, f"Schema validation took {duration:.2f}s, expected < 2.0s"
    
    @patch('app.utils.health_validator.Tenant')
    @patch('app.utils.health_validator.User')
    @patch('app.utils.health_validator.Role')
    def test_data_validation_time_under_1_second(self, mock_role, mock_user, mock_tenant, fast_validator):
        """Test that data validation completes within 1 second."""
        # Mock existing data
        mock_system_tenant = Mock()
        mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
        
        mock_admin_user = Mock()
        mock_user.query.filter_by.return_value.first.return_value = mock_admin_user
        
        mock_system_roles = [Mock() for _ in range(5)]
        mock_role.query.filter_by.return_value.all.return_value = mock_system_roles
        mock_role.query.filter_by.return_value.first.side_effect = mock_system_roles
        
        # Mock data consistency checks
        fast_validator._validate_data_consistency = Mock()
        
        start_time = time.time()
        
        result = fast_validator.validate_data_integrity()
        
        duration = time.time() - start_time
        
        assert result.valid is True
        assert duration < 1.0, f"Data validation took {duration:.3f}s, expected < 1.0s"
    
    def test_comprehensive_health_check_time_under_5_seconds(self, fast_validator):
        """Test that comprehensive health check completes within 5 seconds."""
        # Mock all validations to succeed quickly
        fast_validator.validate_connectivity = Mock(return_value=True)
        
        schema_result = ValidationResult(valid=True)
        fast_validator.validate_schema_integrity = Mock(return_value=schema_result)
        
        data_result = ValidationResult(valid=True)
        fast_validator.validate_data_integrity = Mock(return_value=data_result)
        
        fast_validator._check_performance_metrics = Mock(return_value={'status': 'healthy'})
        
        start_time = time.time()
        
        result = fast_validator.run_comprehensive_health_check()
        
        duration = time.time() - start_time
        
        assert result.status == HealthStatus.HEALTHY
        assert duration < 5.0, f"Comprehensive health check took {duration:.2f}s, expected < 5.0s"
        assert result.duration < 5.0
    
    def test_health_report_generation_time_under_3_seconds(self, fast_validator):
        """Test that health report generation completes within 3 seconds."""
        # Mock all validations to succeed quickly
        fast_validator.validate_connectivity = Mock(return_value=True)
        
        schema_result = ValidationResult(valid=True)
        fast_validator.validate_schema_integrity = Mock(return_value=schema_result)
        
        data_result = ValidationResult(valid=True)
        fast_validator.validate_data_integrity = Mock(return_value=data_result)
        
        fast_validator._get_database_type = Mock(return_value='sqlite')
        
        start_time = time.time()
        
        report = fast_validator.generate_health_report()
        
        duration = time.time() - start_time
        
        assert report['overall_status'] == HealthStatus.HEALTHY.value
        assert duration < 3.0, f"Health report generation took {duration:.2f}s, expected < 3.0s"
        assert report['duration'] < 3.0


class TestConcurrencyPerformance:
    """Test cases for concurrent initialization performance."""
    
    @pytest.fixture
    def concurrent_initializer(self):
        """Create DatabaseInitializer for concurrency testing."""
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
    
    def test_concurrent_initialization_attempts(self, concurrent_initializer):
        """Test performance with multiple concurrent initialization attempts."""
        # Mock all components to succeed
        concurrent_initializer.env_initializer.prepare_environment.return_value = True
        concurrent_initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        concurrent_initializer._test_connection = Mock(return_value=True)
        concurrent_initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///:memory:'
        })
        
        concurrent_initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        def run_initialization():
            start_time = time.time()
            result = concurrent_initializer.initialize()
            duration = time.time() - start_time
            return result.success, duration
        
        # Run 5 concurrent initializations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(run_initialization) for _ in range(5)]
            
            results = []
            for future in as_completed(futures):
                success, duration = future.result()
                results.append((success, duration))
        
        # All should succeed
        for success, duration in results:
            assert success is True
            assert duration < 10.0, f"Concurrent initialization took {duration:.2f}s, expected < 10.0s"
        
        # Average duration should be reasonable
        avg_duration = sum(duration for _, duration in results) / len(results)
        assert avg_duration < 7.0, f"Average concurrent initialization time {avg_duration:.2f}s"
    
    def test_concurrent_validation_attempts(self, concurrent_initializer):
        """Test performance with multiple concurrent validation attempts."""
        # Mock health validator
        concurrent_initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5,
            issues=[]
        )
        
        def run_validation():
            start_time = time.time()
            result = concurrent_initializer.validate_setup()
            duration = time.time() - start_time
            return result.valid, duration
        
        # Run 10 concurrent validations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(run_validation) for _ in range(10)]
            
            results = []
            for future in as_completed(futures):
                valid, duration = future.result()
                results.append((valid, duration))
        
        # All should succeed
        for valid, duration in results:
            assert valid is True
            assert duration < 5.0, f"Concurrent validation took {duration:.2f}s, expected < 5.0s"
    
    def test_thread_safety_stress_test(self, concurrent_initializer):
        """Test thread safety under stress conditions."""
        # Mock components
        concurrent_initializer.env_initializer.prepare_environment.return_value = True
        concurrent_initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        concurrent_initializer._test_connection = Mock(return_value=True)
        concurrent_initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///:memory:'
        })
        
        concurrent_initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        # Shared state to check for race conditions
        shared_state = {'counter': 0, 'errors': []}
        lock = threading.Lock()
        
        def stress_test_worker():
            try:
                for _ in range(10):
                    result = concurrent_initializer.initialize()
                    
                    with lock:
                        if result.success:
                            shared_state['counter'] += 1
                        else:
                            shared_state['errors'].append("Initialization failed")
                    
                    # Small delay to increase chance of race conditions
                    time.sleep(0.01)
            except Exception as e:
                with lock:
                    shared_state['errors'].append(str(e))
        
        # Run stress test with multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=stress_test_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(shared_state['errors']) == 0, f"Errors occurred: {shared_state['errors']}"
        assert shared_state['counter'] == 50, f"Expected 50 successful initializations, got {shared_state['counter']}"


class TestResourceUsagePerformance:
    """Test cases for resource usage performance requirements."""
    
    @pytest.fixture
    def resource_initializer(self):
        """Create DatabaseInitializer for resource testing."""
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
            env_config.auto_seed_data = True
            mock_env_config.return_value = env_config
            
            return DatabaseInitializer(app, db)
    
    def test_cpu_usage_during_initialization(self, resource_initializer):
        """Test CPU usage during initialization stays reasonable."""
        # Mock components
        resource_initializer.env_initializer.prepare_environment.return_value = True
        resource_initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        resource_initializer._test_connection = Mock(return_value=True)
        resource_initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///:memory:'
        })
        
        seeding_result = SeedingResult(success=True)
        resource_initializer.data_seeder.seed_initial_data.return_value = seeding_result
        
        resource_initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        # Monitor CPU usage
        process = psutil.Process(os.getpid())
        cpu_percent_before = process.cpu_percent()
        
        start_time = time.time()
        result = resource_initializer.initialize()
        duration = time.time() - start_time
        
        # Let CPU measurement settle
        time.sleep(0.1)
        cpu_percent_after = process.cpu_percent()
        
        assert result.success is True
        
        # CPU usage should not be excessive (this is a rough check)
        # Note: CPU percentage can be unreliable in short tests
        if duration > 0.5:  # Only check if test took reasonable time
            assert cpu_percent_after < 80, f"CPU usage too high: {cpu_percent_after}%"
    
    def test_memory_efficiency_large_dataset(self, resource_initializer):
        """Test memory efficiency with simulated large dataset operations."""
        # Mock components with simulated large operations
        resource_initializer.env_initializer.prepare_environment.return_value = True
        resource_initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        resource_initializer._test_connection = Mock(return_value=True)
        resource_initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///:memory:'
        })
        
        # Mock seeding with large dataset simulation
        def simulate_large_seeding():
            # Simulate processing large amounts of data
            large_data = [{'id': i, 'data': f'data_{i}' * 100} for i in range(1000)]
            # Process and clean up
            processed = [item['id'] for item in large_data]
            del large_data  # Explicit cleanup
            return SeedingResult(success=True)
        
        resource_initializer.data_seeder.seed_initial_data.side_effect = simulate_large_seeding
        
        resource_initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        # Monitor memory usage
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        result = resource_initializer.initialize()
        
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before
        
        assert result.success is True
        assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB, expected < 100MB"
    
    def test_file_handle_usage(self, resource_initializer):
        """Test that file handle usage is reasonable."""
        # Mock components
        resource_initializer.env_initializer.prepare_environment.return_value = True
        resource_initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        resource_initializer._test_connection = Mock(return_value=True)
        resource_initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///:memory:'
        })
        
        seeding_result = SeedingResult(success=True)
        resource_initializer.data_seeder.seed_initial_data.return_value = seeding_result
        
        resource_initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        # Monitor file handles
        process = psutil.Process(os.getpid())
        try:
            fds_before = process.num_fds() if hasattr(process, 'num_fds') else len(process.open_files())
        except (AttributeError, psutil.AccessDenied):
            pytest.skip("Cannot access file descriptor information on this platform")
        
        result = resource_initializer.initialize()
        
        try:
            fds_after = process.num_fds() if hasattr(process, 'num_fds') else len(process.open_files())
        except (AttributeError, psutil.AccessDenied):
            pytest.skip("Cannot access file descriptor information on this platform")
        
        fd_increase = fds_after - fds_before
        
        assert result.success is True
        assert fd_increase < 10, f"File descriptors increased by {fd_increase}, expected < 10"
    
    def test_initialization_scalability(self, resource_initializer):
        """Test that initialization performance scales reasonably."""
        # Mock components
        resource_initializer.env_initializer.prepare_environment.return_value = True
        resource_initializer.config.validate_configuration.return_value = ValidationResult(valid=True)
        resource_initializer._test_connection = Mock(return_value=True)
        resource_initializer._get_environment_connection_parameters = Mock(return_value={
            'database_type': 'sqlite',
            'connection_string': 'sqlite:///:memory:'
        })
        
        seeding_result = SeedingResult(success=True)
        resource_initializer.data_seeder.seed_initial_data.return_value = seeding_result
        
        resource_initializer.health_validator.run_comprehensive_health_check.return_value = Mock(
            status=Mock(value='healthy'),
            checks_passed=5,
            checks_total=5
        )
        
        # Test with increasing load
        durations = []
        for load_factor in [1, 2, 3]:
            # Simulate increased load by running multiple operations
            start_time = time.time()
            
            for _ in range(load_factor):
                result = resource_initializer.initialize()
                assert result.success is True
            
            duration = time.time() - start_time
            durations.append(duration / load_factor)  # Average per operation
        
        # Performance should not degrade significantly
        for i in range(1, len(durations)):
            degradation = durations[i] / durations[0]
            assert degradation < 2.0, f"Performance degraded by {degradation:.1f}x at load factor {i+1}"


if __name__ == '__main__':
    pytest.main([__file__])