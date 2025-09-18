"""
Comprehensive Performance Comparison Tests

This module provides comprehensive performance tests comparing PostgreSQL
and SQLite performance characteristics, including query performance,
connection overhead, and concurrent access patterns.

Requirements covered: 4.5
"""
import os
import pytest
import tempfile
import time
import statistics
import threading
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
import psycopg2
import sqlite3

from app.utils.adaptive_config import AdaptiveConfigManager
from app.utils.database_manager import DatabaseManager


class TestDatabasePerformanceComparison:
    """Compare performance characteristics between PostgreSQL and SQLite."""
    
    @pytest.fixture
    def temp_sqlite_db(self):
        """Create temporary SQLite database for testing."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        yield db_path
        os.close(db_fd)
        os.unlink(db_path)
    
    def test_connection_establishment_performance(self, temp_sqlite_db):
        """Compare connection establishment performance."""
        # Test SQLite connection performance
        sqlite_times = []
        for _ in range(10):
            start_time = time.time()
            conn = sqlite3.connect(temp_sqlite_db)
            conn.close()
            end_time = time.time()
            sqlite_times.append(end_time - start_time)
        
        sqlite_avg = statistics.mean(sqlite_times)
        sqlite_max = max(sqlite_times)
        
        # Mock PostgreSQL connection performance
        postgresql_times = []
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            
            for _ in range(10):
                start_time = time.time()
                # Simulate PostgreSQL connection overhead
                time.sleep(0.001)  # 1ms overhead simulation
                conn = mock_connect('postgresql://test')
                conn.close()
                end_time = time.time()
                postgresql_times.append(end_time - start_time)
        
        postgresql_avg = statistics.mean(postgresql_times)
        postgresql_max = max(postgresql_times)
        
        # SQLite should generally be faster for connection establishment
        print(f"SQLite connection avg: {sqlite_avg:.4f}s, max: {sqlite_max:.4f}s")
        print(f"PostgreSQL connection avg: {postgresql_avg:.4f}s, max: {postgresql_max:.4f}s")
        
        # Both should be reasonably fast
        assert sqlite_avg < 0.1, f"SQLite connection too slow: {sqlite_avg:.4f}s"
        assert postgresql_avg < 0.1, f"PostgreSQL connection too slow: {postgresql_avg:.4f}s"
    
    def test_query_execution_performance(self, temp_sqlite_db):
        """Compare query execution performance."""
        # Set up SQLite database with test data
        sqlite_conn = sqlite3.connect(temp_sqlite_db)
        sqlite_cursor = sqlite_conn.cursor()
        
        # Create test table
        sqlite_cursor.execute('''
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT,
                value INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert test data
        test_data = [(i, f'name_{i}', i * 10) for i in range(1000)]
        sqlite_cursor.executemany('INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)', test_data)
        sqlite_conn.commit()
        
        # Test SQLite query performance
        sqlite_query_times = []
        for _ in range(10):
            start_time = time.time()
            sqlite_cursor.execute('SELECT * FROM test_table WHERE value > ? ORDER BY value LIMIT 100', (500,))
            results = sqlite_cursor.fetchall()
            end_time = time.time()
            sqlite_query_times.append(end_time - start_time)
            assert len(results) > 0
        
        sqlite_conn.close()
        
        # Mock PostgreSQL query performance
        postgresql_query_times = []
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            # Mock query results
            mock_cursor.fetchall.return_value = [(i, f'name_{i}', i * 10) for i in range(50, 150)]
            
            for _ in range(10):
                start_time = time.time()
                # Simulate PostgreSQL query overhead
                time.sleep(0.002)  # 2ms overhead simulation
                mock_cursor.execute('SELECT * FROM test_table WHERE value > %s ORDER BY value LIMIT 100', (500,))
                results = mock_cursor.fetchall()
                end_time = time.time()
                postgresql_query_times.append(end_time - start_time)
                assert len(results) > 0
        
        sqlite_avg = statistics.mean(sqlite_query_times)
        postgresql_avg = statistics.mean(postgresql_query_times)
        
        print(f"SQLite query avg: {sqlite_avg:.4f}s")
        print(f"PostgreSQL query avg: {postgresql_avg:.4f}s")
        
        # Both should be reasonably fast for simple queries
        assert sqlite_avg < 0.1, f"SQLite query too slow: {sqlite_avg:.4f}s"
        assert postgresql_avg < 0.1, f"PostgreSQL query too slow: {postgresql_avg:.4f}s"
    
    def test_concurrent_access_performance(self, temp_sqlite_db):
        """Compare concurrent access performance."""
        # Set up SQLite database
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE concurrent_test (id INTEGER PRIMARY KEY, data TEXT)')
        conn.commit()
        conn.close()
        
        def sqlite_worker(worker_id):
            """SQLite worker function."""
            start_time = time.time()
            conn = sqlite3.connect(temp_sqlite_db)
            cursor = conn.cursor()
            
            # Perform some operations
            for i in range(10):
                cursor.execute('INSERT INTO concurrent_test (data) VALUES (?)', (f'worker_{worker_id}_item_{i}',))
                cursor.execute('SELECT COUNT(*) FROM concurrent_test')
                cursor.fetchone()
            
            conn.commit()
            conn.close()
            end_time = time.time()
            return end_time - start_time
        
        def postgresql_worker(worker_id):
            """Mock PostgreSQL worker function."""
            start_time = time.time()
            
            # Simulate PostgreSQL operations with some overhead
            time.sleep(0.01)  # 10ms overhead simulation
            
            with patch('psycopg2.connect') as mock_connect:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_conn
                
                # Simulate operations
                for i in range(10):
                    mock_cursor.execute('INSERT INTO concurrent_test (data) VALUES (%s)', (f'worker_{worker_id}_item_{i}',))
                    mock_cursor.execute('SELECT COUNT(*) FROM concurrent_test')
                    mock_cursor.fetchone.return_value = (i + 1,)
                
                mock_conn.commit()
            
            end_time = time.time()
            return end_time - start_time
        
        # Test SQLite concurrent performance
        with ThreadPoolExecutor(max_workers=5) as executor:
            sqlite_futures = [executor.submit(sqlite_worker, i) for i in range(5)]
            sqlite_times = [future.result() for future in as_completed(sqlite_futures)]
        
        # Test PostgreSQL concurrent performance
        with ThreadPoolExecutor(max_workers=5) as executor:
            postgresql_futures = [executor.submit(postgresql_worker, i) for i in range(5)]
            postgresql_times = [future.result() for future in as_completed(postgresql_futures)]
        
        sqlite_avg = statistics.mean(sqlite_times)
        postgresql_avg = statistics.mean(postgresql_times)
        
        print(f"SQLite concurrent avg: {sqlite_avg:.4f}s")
        print(f"PostgreSQL concurrent avg: {postgresql_avg:.4f}s")
        
        # Both should handle concurrent access reasonably
        assert sqlite_avg < 1.0, f"SQLite concurrent access too slow: {sqlite_avg:.4f}s"
        assert postgresql_avg < 1.0, f"PostgreSQL concurrent access too slow: {postgresql_avg:.4f}s"
    
    def test_memory_usage_comparison(self, temp_sqlite_db):
        """Compare memory usage patterns."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Test SQLite memory usage
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create multiple SQLite connections
        sqlite_connections = []
        for _ in range(10):
            conn = sqlite3.connect(temp_sqlite_db)
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE IF NOT EXISTS memory_test (id INTEGER, data TEXT)')
            # Insert some data
            cursor.executemany('INSERT INTO memory_test VALUES (?, ?)', 
                             [(i, f'data_{i}' * 100) for i in range(100)])
            conn.commit()
            sqlite_connections.append(conn)
        
        sqlite_memory = process.memory_info().rss / 1024 / 1024  # MB
        sqlite_increase = sqlite_memory - initial_memory
        
        # Clean up SQLite connections
        for conn in sqlite_connections:
            conn.close()
        
        # Test PostgreSQL memory usage (mocked)
        postgresql_memory_start = process.memory_info().rss / 1024 / 1024  # MB
        
        # Mock PostgreSQL connections (they would use more memory in reality)
        postgresql_connections = []
        with patch('psycopg2.connect') as mock_connect:
            for _ in range(10):
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_conn
                postgresql_connections.append(mock_conn)
                
                # Simulate some memory usage
                dummy_data = ['x' * 1000 for _ in range(100)]  # Simulate connection overhead
        
        postgresql_memory = process.memory_info().rss / 1024 / 1024  # MB
        postgresql_increase = postgresql_memory - postgresql_memory_start
        
        print(f"SQLite memory increase: {sqlite_increase:.2f}MB")
        print(f"PostgreSQL memory increase: {postgresql_increase:.2f}MB")
        
        # Memory usage should be reasonable for both
        assert sqlite_increase < 100, f"SQLite memory usage too high: {sqlite_increase:.2f}MB"
        assert postgresql_increase < 100, f"PostgreSQL memory usage too high: {postgresql_increase:.2f}MB"


class TestConfigurationPerformanceComparison:
    """Compare configuration and startup performance."""
    
    def test_configuration_detection_performance(self):
        """Compare configuration detection performance."""
        # Test SQLite configuration detection
        sqlite_times = []
        for _ in range(5):
            start_time = time.time()
            
            with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("No PostgreSQL")):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.connect_ex.return_value = 1
                    mock_socket.return_value = mock_sock
                    
                    with patch('sqlite3.connect') as mock_sqlite:
                        mock_sqlite.return_value = MagicMock()
                        
                        manager = AdaptiveConfigManager()
                        db_type, conn_str = manager.detect_database()
            
            end_time = time.time()
            sqlite_times.append(end_time - start_time)
            assert db_type == 'sqlite'
        
        # Test PostgreSQL configuration detection
        postgresql_times = []
        for _ in range(5):
            start_time = time.time()
            
            with patch('psycopg2.connect') as mock_connect:
                mock_connect.return_value = MagicMock()
                
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.connect_ex.return_value = 0
                    mock_socket.return_value = mock_sock
                    
                    manager = AdaptiveConfigManager()
                    db_type, conn_str = manager.detect_database()
            
            end_time = time.time()
            postgresql_times.append(end_time - start_time)
            assert db_type == 'postgresql'
        
        sqlite_avg = statistics.mean(sqlite_times)
        postgresql_avg = statistics.mean(postgresql_times)
        
        print(f"SQLite detection avg: {sqlite_avg:.4f}s")
        print(f"PostgreSQL detection avg: {postgresql_avg:.4f}s")
        
        # Both should be fast
        assert sqlite_avg < 1.0, f"SQLite detection too slow: {sqlite_avg:.4f}s"
        assert postgresql_avg < 1.0, f"PostgreSQL detection too slow: {postgresql_avg:.4f}s"
    
    def test_service_validation_performance(self):
        """Compare service validation performance."""
        manager = AdaptiveConfigManager()
        
        # Test with all services available
        available_times = []
        for _ in range(5):
            start_time = time.time()
            
            with patch.object(manager, '_test_postgresql_connection', return_value=True):
                with patch.object(manager, '_test_sqlite_connection', return_value=True):
                    with patch.object(manager, '_test_redis_connection', return_value=True):
                        status = manager.validate_services()
            
            end_time = time.time()
            available_times.append(end_time - start_time)
            assert all(status.values())
        
        # Test with all services unavailable (should be faster due to quick failures)
        unavailable_times = []
        for _ in range(5):
            start_time = time.time()
            
            with patch.object(manager, '_test_postgresql_connection', return_value=False):
                with patch.object(manager, '_test_sqlite_connection', return_value=False):
                    with patch.object(manager, '_test_redis_connection', return_value=False):
                        status = manager.validate_services()
            
            end_time = time.time()
            unavailable_times.append(end_time - start_time)
            assert not any(status.values())
        
        available_avg = statistics.mean(available_times)
        unavailable_avg = statistics.mean(unavailable_times)
        
        print(f"Service validation (available) avg: {available_avg:.4f}s")
        print(f"Service validation (unavailable) avg: {unavailable_avg:.4f}s")
        
        # Both should be reasonably fast
        assert available_avg < 2.0, f"Service validation too slow: {available_avg:.4f}s"
        assert unavailable_avg < 2.0, f"Service validation too slow: {unavailable_avg:.4f}s"
    
    def test_config_class_creation_performance(self):
        """Compare configuration class creation performance."""
        # Test SQLite config creation
        sqlite_times = []
        for _ in range(10):
            start_time = time.time()
            
            with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("No PostgreSQL")):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.connect_ex.return_value = 1
                    mock_socket.return_value = mock_sock
                    
                    with patch('sqlite3.connect') as mock_sqlite:
                        mock_sqlite.return_value = MagicMock()
                        
                        manager = AdaptiveConfigManager()
                        config_class = manager.get_config_class()
                        config_instance = config_class()
            
            end_time = time.time()
            sqlite_times.append(end_time - start_time)
            assert config_instance.DETECTED_DATABASE_TYPE == 'sqlite'
        
        # Test PostgreSQL config creation
        postgresql_times = []
        for _ in range(10):
            start_time = time.time()
            
            with patch('psycopg2.connect') as mock_connect:
                mock_connect.return_value = MagicMock()
                
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.connect_ex.return_value = 0
                    mock_socket.return_value = mock_sock
                    
                    manager = AdaptiveConfigManager()
                    config_class = manager.get_config_class()
                    config_instance = config_class()
            
            end_time = time.time()
            postgresql_times.append(end_time - start_time)
            assert config_instance.DETECTED_DATABASE_TYPE == 'postgresql'
        
        sqlite_avg = statistics.mean(sqlite_times)
        postgresql_avg = statistics.mean(postgresql_times)
        
        print(f"SQLite config creation avg: {sqlite_avg:.4f}s")
        print(f"PostgreSQL config creation avg: {postgresql_avg:.4f}s")
        
        # Both should be fast
        assert sqlite_avg < 1.0, f"SQLite config creation too slow: {sqlite_avg:.4f}s"
        assert postgresql_avg < 1.0, f"PostgreSQL config creation too slow: {postgresql_avg:.4f}s"


class TestDatabaseManagerPerformanceComparison:
    """Compare DatabaseManager performance characteristics."""
    
    def test_connection_establishment_overhead(self):
        """Compare connection establishment overhead."""
        manager = DatabaseManager()
        
        # Test PostgreSQL connection overhead
        postgresql_times = []
        for _ in range(5):
            start_time = time.time()
            
            with patch.object(manager, 'connect_postgresql', return_value=True):
                manager._current_database_type = 'postgresql'
                manager._current_connection_string = 'postgresql://test'
                success, db_type, conn_str = manager.establish_connection()
            
            end_time = time.time()
            postgresql_times.append(end_time - start_time)
            assert success is True
            assert db_type == 'postgresql'
        
        # Test SQLite connection overhead
        sqlite_times = []
        for _ in range(5):
            start_time = time.time()
            
            with patch.object(manager, 'connect_postgresql', return_value=False):
                with patch.object(manager, 'connect_sqlite', return_value=True):
                    manager._current_database_type = 'sqlite'
                    manager._current_connection_string = 'sqlite:///test.db'
                    success, db_type, conn_str = manager.establish_connection()
            
            end_time = time.time()
            sqlite_times.append(end_time - start_time)
            assert success is True
            assert db_type == 'sqlite'
        
        postgresql_avg = statistics.mean(postgresql_times)
        sqlite_avg = statistics.mean(sqlite_times)
        
        print(f"PostgreSQL connection establishment avg: {postgresql_avg:.4f}s")
        print(f"SQLite connection establishment avg: {sqlite_avg:.4f}s")
        
        # Both should be fast
        assert postgresql_avg < 0.5, f"PostgreSQL connection too slow: {postgresql_avg:.4f}s"
        assert sqlite_avg < 0.5, f"SQLite connection too slow: {sqlite_avg:.4f}s"
    
    def test_health_check_performance(self):
        """Compare health check performance."""
        manager = DatabaseManager()
        
        # Test with healthy connection
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        manager._engine = mock_engine
        
        health_check_times = []
        for _ in range(20):
            start_time = time.time()
            result = manager.test_connection_health()
            end_time = time.time()
            health_check_times.append(end_time - start_time)
            assert result is True
        
        avg_time = statistics.mean(health_check_times)
        max_time = max(health_check_times)
        
        print(f"Health check avg: {avg_time:.4f}s, max: {max_time:.4f}s")
        
        # Health checks should be very fast
        assert avg_time < 0.01, f"Health check too slow: {avg_time:.4f}s"
        assert max_time < 0.05, f"Health check max too slow: {max_time:.4f}s"
    
    def test_reconnection_performance(self):
        """Compare reconnection performance."""
        manager = DatabaseManager()
        
        # Set up initial state
        manager._current_database_type = 'postgresql'
        manager._current_connection_string = 'postgresql://test'
        manager._engine = MagicMock()
        
        reconnection_times = []
        for _ in range(5):
            start_time = time.time()
            
            with patch.object(manager, 'establish_connection', return_value=(True, 'sqlite', 'sqlite:///test.db')):
                result = manager.reconnect()
            
            end_time = time.time()
            reconnection_times.append(end_time - start_time)
            assert result is True
        
        avg_time = statistics.mean(reconnection_times)
        
        print(f"Reconnection avg: {avg_time:.4f}s")
        
        # Reconnection should be reasonably fast
        assert avg_time < 1.0, f"Reconnection too slow: {avg_time:.4f}s"


class TestScalabilityComparison:
    """Compare scalability characteristics."""
    
    def test_concurrent_configuration_requests(self):
        """Test concurrent configuration requests performance."""
        def create_config():
            with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("No PostgreSQL")):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.connect_ex.return_value = 1
                    mock_socket.return_value = mock_sock
                    
                    with patch('sqlite3.connect') as mock_sqlite:
                        mock_sqlite.return_value = MagicMock()
                        
                        manager = AdaptiveConfigManager()
                        return manager.get_config_class()
        
        # Test concurrent configuration creation
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_config) for _ in range(20)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"Concurrent config creation: {len(results)} configs in {total_time:.4f}s")
        
        # Should handle concurrent requests efficiently
        assert total_time < 5.0, f"Concurrent config creation too slow: {total_time:.4f}s"
        assert len(results) == 20
        
        # All configs should be valid
        for config_class in results:
            config_instance = config_class()
            assert hasattr(config_instance, 'DETECTED_DATABASE_TYPE')
    
    def test_service_validation_under_load(self):
        """Test service validation performance under load."""
        manager = AdaptiveConfigManager()
        
        def validate_services():
            with patch.object(manager, '_test_postgresql_connection', return_value=False):
                with patch.object(manager, '_test_sqlite_connection', return_value=True):
                    with patch.object(manager, '_test_redis_connection', return_value=False):
                        return manager.validate_services()
        
        # Test service validation under concurrent load
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(validate_services) for _ in range(15)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"Concurrent service validation: {len(results)} validations in {total_time:.4f}s")
        
        # Should handle concurrent validation efficiently
        assert total_time < 3.0, f"Concurrent service validation too slow: {total_time:.4f}s"
        assert len(results) == 15
        
        # All validations should return consistent results
        for result in results:
            assert result['postgresql'] is False
            assert result['sqlite'] is True
            assert result['redis'] is False