"""
Comprehensive Service Degradation Tests

This module provides comprehensive tests for service degradation scenarios,
testing how the application behaves when various external services become
unavailable or experience issues.

Requirements covered: 4.1, 4.2, 4.3, 4.5
"""
import os
import pytest
import tempfile
import time
import threading
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import psycopg2
import redis
import sqlite3

from app.utils.adaptive_config import AdaptiveConfigManager, get_adaptive_config
from app.utils.database_manager import DatabaseManager


class TestDatabaseServiceDegradation:
    """Test database service degradation scenarios."""
    
    def test_postgresql_service_interruption(self):
        """Test behavior when PostgreSQL service is interrupted."""
        manager = AdaptiveConfigManager()
        
        # Initially PostgreSQL is available
        with patch('psycopg2.connect') as mock_connect:
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                mock_sock.connect_ex.return_value = 0  # Success
                mock_socket.return_value = mock_sock
                mock_connect.return_value = MagicMock()
                
                # First detection should succeed
                result1 = manager._test_postgresql_connection()
                assert result1 is True
                assert manager.services['postgresql'].available is True
        
        # Then PostgreSQL becomes unavailable
        with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("Connection refused")):
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                mock_sock.connect_ex.return_value = 1  # Connection failed
                mock_socket.return_value = mock_sock
                
                # Second detection should fail
                result2 = manager._test_postgresql_connection()
                assert result2 is False
                assert manager.services['postgresql'].available is False
                assert 'Cannot connect to PostgreSQL' in manager.services['postgresql'].error_message
    
    def test_sqlite_fallback_when_postgresql_fails(self):
        """Test SQLite fallback when PostgreSQL fails."""
        manager = AdaptiveConfigManager()
        
        # Mock PostgreSQL failure
        with patch.object(manager, '_test_postgresql_connection', return_value=False):
            with patch.object(manager, '_get_sqlite_connection_string', return_value='sqlite:///fallback.db'):
                with patch('sqlite3.connect') as mock_sqlite:
                    mock_sqlite.return_value = MagicMock()
                    
                    db_type, connection_string = manager.detect_database()
                    
                    assert db_type == 'sqlite'
                    assert connection_string == 'sqlite:///fallback.db'
                    assert manager.services['sqlite'].available is True
    
    def test_both_databases_unavailable(self):
        """Test behavior when both PostgreSQL and SQLite are unavailable."""
        manager = AdaptiveConfigManager()
        
        # Mock both database failures
        with patch.object(manager, '_test_postgresql_connection', return_value=False):
            with patch('sqlite3.connect', side_effect=sqlite3.OperationalError("Database locked")):
                # SQLite should also fail
                result = manager._test_sqlite_connection()
                assert result is False
                assert manager.services['sqlite'].available is False
                
                # Database detection should still return SQLite as last resort
                db_type, connection_string = manager.detect_database()
                assert db_type == 'sqlite'  # Still returns SQLite even if test failed
    
    def test_database_connection_recovery(self):
        """Test database connection recovery after failure."""
        db_manager = DatabaseManager()
        
        # Initially connection fails
        with patch.object(db_manager, 'connect_postgresql', return_value=False):
            with patch.object(db_manager, 'connect_sqlite', return_value=False):
                success, db_type, conn_str = db_manager.establish_connection()
                assert success is False
        
        # Then connection recovers
        with patch.object(db_manager, 'connect_postgresql', return_value=False):
            with patch.object(db_manager, 'connect_sqlite', return_value=True):
                db_manager._current_database_type = 'sqlite'
                db_manager._current_connection_string = 'sqlite:///recovered.db'
                
                success, db_type, conn_str = db_manager.establish_connection()
                assert success is True
                assert db_type == 'sqlite'
                assert conn_str == 'sqlite:///recovered.db'


class TestCacheServiceDegradation:
    """Test cache service degradation scenarios."""
    
    def test_redis_service_interruption(self):
        """Test behavior when Redis service is interrupted."""
        manager = AdaptiveConfigManager()
        
        # Initially Redis is available
        with patch('redis.from_url') as mock_redis:
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                mock_sock.connect_ex.return_value = 0  # Success
                mock_socket.return_value = mock_sock
                mock_redis_conn = MagicMock()
                mock_redis.return_value = mock_redis_conn
                
                result1 = manager._test_redis_connection()
                assert result1 is True
                assert manager.services['redis'].available is True
        
        # Then Redis becomes unavailable
        with patch('redis.from_url') as mock_redis:
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                mock_sock.connect_ex.return_value = 1  # Connection failed
                mock_socket.return_value = mock_sock
                
                result2 = manager._test_redis_connection()
                assert result2 is False
                assert manager.services['redis'].available is False
    
    def test_simple_cache_fallback(self):
        """Test simple cache fallback when Redis is unavailable."""
        manager = AdaptiveConfigManager()
        
        # Mock Redis failure
        with patch.object(manager, '_test_redis_connection', return_value=False):
            backend = manager.detect_cache_backend()
            assert backend == 'simple'
    
    def test_cache_dependent_features_disabled(self):
        """Test that cache-dependent features are disabled when Redis unavailable."""
        manager = AdaptiveConfigManager()
        
        # Mock Redis as unavailable
        manager.services = {
            'redis': MagicMock(available=False),
            'postgresql': MagicMock(available=True)
        }
        
        features = manager._get_feature_flags()
        
        # Features that depend on Redis should be disabled
        assert features['cache_redis'] is False
        assert features['celery'] is False  # Celery requires Redis
        assert features['rate_limiting'] is False  # Rate limiting requires Redis
        
        # Features that don't depend on Redis should still be available
        assert features['cache_simple'] is True
        assert features['websockets'] is True


class TestApplicationBehaviorDuringDegradation:
    """Test application behavior during service degradation."""
    
    def test_app_startup_with_degraded_services(self):
        """Test application startup when services are degraded."""
        # Mock all external services as unavailable
        with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("No PostgreSQL")):
            with patch('redis.from_url', side_effect=redis.ConnectionError("No Redis")):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.connect_ex.return_value = 1  # All connections fail
                    mock_socket.return_value = mock_sock
                    
                    # App should still be able to get configuration
                    config_class = get_adaptive_config('testing')
                    config = config_class()
                    
                    # Should fallback to minimal configuration
                    assert config.DETECTED_DATABASE_TYPE == 'sqlite'
                    assert config.CACHE_TYPE == 'simple'
                    
                    # Feature flags should reflect degraded state
                    features = config.FEATURES
                    assert features['database_postgresql'] is False
                    assert features['cache_redis'] is False
                    assert features['celery'] is False
                    assert features['rate_limiting'] is False
                    
                    # Core features should still be available
                    assert features['database_sqlite'] is True
                    assert features['cache_simple'] is True
                    assert features['websockets'] is True
    
    def test_graceful_degradation_with_partial_services(self):
        """Test graceful degradation with some services available."""
        # Mock PostgreSQL available, Redis unavailable
        with patch('psycopg2.connect') as mock_pg:
            mock_pg.return_value = MagicMock()
            
            with patch('redis.from_url', side_effect=redis.ConnectionError("No Redis")):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    # PostgreSQL socket succeeds, Redis fails
                    mock_sock.connect_ex.side_effect = [0, 1]  # First call succeeds, second fails
                    mock_socket.return_value = mock_sock
                    
                    config_class = get_adaptive_config('testing')
                    config = config_class()
                    
                    # Should use PostgreSQL but fallback cache
                    assert config.DETECTED_DATABASE_TYPE == 'postgresql'
                    assert config.CACHE_TYPE == 'simple'
                    
                    # Mixed feature availability
                    features = config.FEATURES
                    assert features['database_postgresql'] is True
                    assert features['cache_redis'] is False
                    assert features['cache_simple'] is True
                    assert features['celery'] is False  # Still requires Redis
    
    def test_service_recovery_detection(self):
        """Test detection of service recovery."""
        manager = AdaptiveConfigManager()
        
        # Initially service is down
        with patch.object(manager, '_test_postgresql_connection', return_value=False):
            status1 = manager.validate_services()
            assert status1['postgresql'] is False
        
        # Service recovers
        with patch.object(manager, '_test_postgresql_connection', return_value=True):
            status2 = manager.validate_services()
            assert status2['postgresql'] is True
            
            # Service status should be updated
            assert manager.services['postgresql'].available is True
    
    def test_concurrent_service_degradation(self):
        """Test behavior when multiple services degrade simultaneously."""
        manager = AdaptiveConfigManager()
        
        # All services start healthy
        with patch.object(manager, '_test_postgresql_connection', return_value=True):
            with patch.object(manager, '_test_sqlite_connection', return_value=True):
                with patch.object(manager, '_test_redis_connection', return_value=True):
                    initial_status = manager.validate_services()
                    assert all(initial_status.values())
        
        # All services fail simultaneously
        with patch.object(manager, '_test_postgresql_connection', return_value=False):
            with patch.object(manager, '_test_sqlite_connection', return_value=False):
                with patch.object(manager, '_test_redis_connection', return_value=False):
                    degraded_status = manager.validate_services()
                    assert not any(degraded_status.values())
                    
                    # Feature flags should reflect complete degradation
                    features = manager._get_feature_flags()
                    assert features['database_postgresql'] is False
                    assert features['cache_redis'] is False
                    assert features['celery'] is False
                    assert features['rate_limiting'] is False
                    
                    # Only basic features should remain
                    assert features['cache_simple'] is True
                    assert features['websockets'] is True


class TestHealthMonitoringDuringDegradation:
    """Test health monitoring during service degradation."""
    
    def test_health_monitoring_detects_degradation(self):
        """Test that health monitoring detects service degradation."""
        db_manager = DatabaseManager()
        db_manager._health_check_interval = 0.1  # Fast checking for testing
        
        # Set up initial healthy state
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        db_manager._engine = mock_engine
        db_manager._current_database_type = 'postgresql'
        db_manager._health_status = True
        
        # Add callback to track health changes
        health_changes = []
        def health_callback(is_healthy, db_type):
            health_changes.append((is_healthy, db_type))
        
        db_manager.add_health_callback(health_callback)
        
        # Start health monitoring
        db_manager.start_health_monitoring()
        
        try:
            # Simulate connection failure
            mock_engine.connect.side_effect = Exception("Connection lost")
            
            # Wait for health check to detect failure
            time.sleep(0.2)
            
            # Health status should be updated
            assert db_manager._health_status is False
            
        finally:
            db_manager.stop_health_monitoring()
    
    def test_health_monitoring_recovery_detection(self):
        """Test that health monitoring detects service recovery."""
        db_manager = DatabaseManager()
        db_manager._health_check_interval = 0.1
        
        # Set up initial unhealthy state
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Connection lost")
        db_manager._engine = mock_engine
        db_manager._current_database_type = 'postgresql'
        db_manager._health_status = False
        
        # Start health monitoring
        db_manager.start_health_monitoring()
        
        try:
            # Simulate connection recovery
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_engine.connect.side_effect = None  # Clear the exception
            
            # Wait for health check to detect recovery
            time.sleep(0.2)
            
            # Health status should be updated
            assert db_manager._health_status is True
            
        finally:
            db_manager.stop_health_monitoring()
    
    def test_health_monitoring_with_intermittent_failures(self):
        """Test health monitoring with intermittent service failures."""
        db_manager = DatabaseManager()
        db_manager._health_check_interval = 0.05  # Very fast for testing
        
        mock_engine = MagicMock()
        db_manager._engine = mock_engine
        db_manager._current_database_type = 'postgresql'
        
        # Track health status changes
        health_history = []
        def track_health(is_healthy, db_type):
            health_history.append((datetime.now(), is_healthy, db_type))
        
        db_manager.add_health_callback(track_health)
        
        # Start health monitoring
        db_manager.start_health_monitoring()
        
        try:
            # Simulate intermittent failures
            call_count = 0
            def intermittent_failure(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count % 3 == 0:  # Fail every third call
                    raise Exception("Intermittent failure")
                return MagicMock().__enter__()
            
            mock_engine.connect.side_effect = intermittent_failure
            
            # Let it run for a bit
            time.sleep(0.3)
            
            # Should have detected multiple health changes
            assert len(health_history) > 0
            
        finally:
            db_manager.stop_health_monitoring()


class TestErrorHandlingDuringDegradation:
    """Test error handling during service degradation."""
    
    def test_graceful_error_handling_on_service_failure(self):
        """Test graceful error handling when services fail."""
        manager = AdaptiveConfigManager()
        
        # Test various failure scenarios
        failure_scenarios = [
            (psycopg2.OperationalError("Connection timeout"), "Connection timeout"),
            (psycopg2.DatabaseError("Database error"), "Database error"),
            (Exception("Unexpected error"), "Unexpected error"),
            (ConnectionRefusedError("Connection refused"), "Connection refused"),
        ]
        
        for exception, expected_message in failure_scenarios:
            with patch('psycopg2.connect', side_effect=exception):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.connect_ex.return_value = 1
                    mock_socket.return_value = mock_sock
                    
                    # Should handle error gracefully
                    result = manager._test_postgresql_connection()
                    assert result is False
                    assert manager.services['postgresql'].available is False
                    assert expected_message.lower() in manager.services['postgresql'].error_message.lower()
    
    def test_service_status_error_message_accuracy(self):
        """Test that service status error messages are accurate."""
        manager = AdaptiveConfigManager()
        
        # Test specific error scenarios
        test_cases = [
            {
                'exception': psycopg2.OperationalError("FATAL: password authentication failed"),
                'expected_keywords': ['password', 'authentication', 'failed']
            },
            {
                'exception': psycopg2.OperationalError("could not connect to server"),
                'expected_keywords': ['connect', 'server']
            },
            {
                'exception': sqlite3.OperationalError("database is locked"),
                'expected_keywords': ['database', 'locked']
            },
            {
                'exception': redis.ConnectionError("Connection refused"),
                'expected_keywords': ['connection', 'refused']
            }
        ]
        
        for test_case in test_cases:
            # Test PostgreSQL errors
            if isinstance(test_case['exception'], psycopg2.Error):
                with patch('psycopg2.connect', side_effect=test_case['exception']):
                    with patch('socket.socket') as mock_socket:
                        mock_sock = MagicMock()
                        mock_sock.connect_ex.return_value = 1
                        mock_socket.return_value = mock_sock
                        
                        manager._test_postgresql_connection()
                        error_msg = manager.services['postgresql'].error_message.lower()
                        
                        for keyword in test_case['expected_keywords']:
                            assert keyword in error_msg, f"Expected '{keyword}' in error message: {error_msg}"
            
            # Test SQLite errors
            elif isinstance(test_case['exception'], sqlite3.Error):
                with patch('sqlite3.connect', side_effect=test_case['exception']):
                    manager._test_sqlite_connection()
                    error_msg = manager.services['sqlite'].error_message.lower()
                    
                    for keyword in test_case['expected_keywords']:
                        assert keyword in error_msg, f"Expected '{keyword}' in error message: {error_msg}"
            
            # Test Redis errors
            elif isinstance(test_case['exception'], redis.RedisError):
                with patch('redis.from_url') as mock_redis:
                    mock_redis_conn = MagicMock()
                    mock_redis_conn.ping.side_effect = test_case['exception']
                    mock_redis.return_value = mock_redis_conn
                    
                    with patch('socket.socket') as mock_socket:
                        mock_sock = MagicMock()
                        mock_sock.connect_ex.return_value = 0
                        mock_socket.return_value = mock_sock
                        
                        manager._test_redis_connection()
                        error_msg = manager.services['redis'].error_message.lower()
                        
                        for keyword in test_case['expected_keywords']:
                            assert keyword in error_msg, f"Expected '{keyword}' in error message: {error_msg}"
    
    def test_service_degradation_logging(self):
        """Test that service degradation is properly logged."""
        manager = AdaptiveConfigManager()
        
        with patch('app.utils.adaptive_config.logger') as mock_logger:
            # Mock service failure
            with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("Service down")):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.connect_ex.return_value = 1
                    mock_socket.return_value = mock_sock
                    
                    manager._test_postgresql_connection()
                    
                    # Should log the failure
                    mock_logger.debug.assert_called()
                    log_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
                    assert any('PostgreSQL connection failed' in call for call in log_calls)