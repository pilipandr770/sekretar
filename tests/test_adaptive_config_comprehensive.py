"""
Comprehensive tests for Adaptive Configuration System

This module provides comprehensive unit tests for the AdaptiveConfigManager
and DatabaseManager classes, covering all functionality including error
handling, service detection, and configuration adaptation.

Requirements covered: 1.4, 2.1, 2.2, 2.3, 4.1, 4.2, 4.3, 4.5
"""
import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime
import psycopg2
import redis
import sqlite3

from app.utils.adaptive_config import (
    AdaptiveConfigManager,
    ServiceStatus,
    get_adaptive_config,
    validate_current_services
)


class TestAdaptiveConfigManagerComprehensive:
    """Comprehensive test cases for AdaptiveConfigManager."""
    
    def test_initialization_with_different_environments(self):
        """Test AdaptiveConfigManager initialization with different environments."""
        # Test with explicit environment
        manager_dev = AdaptiveConfigManager('development')
        assert manager_dev.environment == 'development'
        
        manager_test = AdaptiveConfigManager('testing')
        assert manager_test.environment == 'testing'
        
        manager_prod = AdaptiveConfigManager('production')
        assert manager_prod.environment == 'production'
        
        # Test with environment detection
        with patch.dict(os.environ, {'FLASK_ENV': 'production'}):
            manager_auto = AdaptiveConfigManager()
            assert manager_auto.environment == 'production'
    
    def test_environment_detection_edge_cases(self):
        """Test environment detection with various edge cases."""
        manager = AdaptiveConfigManager()
        
        # Test case variations
        test_cases = [
            ('prod', 'production'),
            ('PRODUCTION', 'production'),
            ('test', 'testing'),
            ('TESTING', 'testing'),
            ('dev', 'development'),
            ('development', 'development'),
            ('', 'development'),  # Default
            ('invalid', 'development'),  # Default
        ]
        
        for env_value, expected in test_cases:
            with patch.dict(os.environ, {'FLASK_ENV': env_value}):
                detected = manager._detect_environment()
                assert detected == expected, f"Expected {expected} for {env_value}, got {detected}"
    
    @patch('psycopg2.connect')
    @patch('socket.socket')
    def test_postgresql_connection_with_different_urls(self, mock_socket, mock_connect):
        """Test PostgreSQL connection with different URL formats."""
        # Mock successful socket connection
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock
        
        # Mock successful database connection
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        manager = AdaptiveConfigManager()
        
        # Test different URL formats
        test_urls = [
            'postgresql://user:pass@localhost:5432/db',
            'postgres://user:pass@localhost:5432/db',  # Should be converted
            'postgresql://user@localhost:5432/db',  # No password
            'postgresql://user:pass@remote.host:5433/custom_db',
        ]
        
        for url in test_urls:
            with patch.dict(os.environ, {'DATABASE_URL': url}):
                result = manager._test_postgresql_connection()
                assert result is True
                assert 'postgresql' in manager.services
                assert manager.services['postgresql'].available is True
    
    def test_database_detection_priority_logic(self):
        """Test database detection priority and fallback logic."""
        manager = AdaptiveConfigManager()
        
        # Test PostgreSQL preferred when available
        with patch.object(manager, '_test_postgresql_connection', return_value=True):
            with patch.object(manager, '_get_postgresql_connection_string', return_value='postgresql://test'):
                db_type, connection_string = manager.detect_database()
                assert db_type == 'postgresql'
                assert connection_string == 'postgresql://test'
        
        # Test SQLite fallback when PostgreSQL unavailable
        with patch.object(manager, '_test_postgresql_connection', return_value=False):
            with patch.object(manager, '_get_sqlite_connection_string', return_value='sqlite:///test.db'):
                db_type, connection_string = manager.detect_database()
                assert db_type == 'sqlite'
                assert connection_string == 'sqlite:///test.db'
    
    def test_feature_flags_generation(self):
        """Test feature flags generation based on service availability."""
        manager = AdaptiveConfigManager()
        
        # Mock different service combinations
        test_scenarios = [
            # All services available
            {
                'services': {
                    'postgresql': ServiceStatus('postgresql', True, datetime.now()),
                    'redis': ServiceStatus('redis', True, datetime.now())
                },
                'expected_features': {
                    'database_postgresql': True,
                    'cache_redis': True,
                    'cache_simple': True,
                    'celery': True,
                    'rate_limiting': True,
                    'websockets': True
                }
            },
            # Only SQLite available
            {
                'services': {
                    'postgresql': ServiceStatus('postgresql', False, datetime.now()),
                    'sqlite': ServiceStatus('sqlite', True, datetime.now()),
                    'redis': ServiceStatus('redis', False, datetime.now())
                },
                'expected_features': {
                    'database_postgresql': False,
                    'database_sqlite': True,
                    'cache_redis': False,
                    'cache_simple': True,
                    'celery': False,
                    'rate_limiting': False,
                    'websockets': True
                }
            }
        ]
        
        for scenario in test_scenarios:
            manager.services = scenario['services']
            features = manager._get_feature_flags()
            
            for feature, expected_value in scenario['expected_features'].items():
                assert features[feature] == expected_value, \
                    f"Feature {feature} should be {expected_value}, got {features[feature]}"
    
    def test_service_validation_comprehensive(self):
        """Test comprehensive service validation."""
        manager = AdaptiveConfigManager()
        
        # Mock all service tests
        with patch.object(manager, '_test_postgresql_connection', return_value=True):
            with patch.object(manager, '_test_sqlite_connection', return_value=True):
                with patch.object(manager, '_test_redis_connection', return_value=False):
                    status = manager.validate_services()
                    
                    assert status['postgresql'] is True
                    assert status['sqlite'] is True
                    assert status['redis'] is False
                    
                    # Check that services dict is updated
                    assert 'postgresql' in manager.services
                    assert 'sqlite' in manager.services
                    assert 'redis' in manager.services


class TestIntegrationScenarios:
    """Integration test scenarios for adaptive configuration."""
    
    @pytest.fixture
    def temp_db_file(self):
        """Create a temporary database file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name
        yield temp_path
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except PermissionError:
            pass
    
    def test_full_sqlite_configuration_flow(self, temp_db_file):
        """Test complete configuration flow with SQLite."""
        with patch.dict(os.environ, {
            'SQLITE_DATABASE_URL': f'sqlite:///{temp_db_file}',
            'FLASK_ENV': 'testing'
        }):
            # Mock PostgreSQL as unavailable
            with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("No PostgreSQL")):
                # Mock Redis as unavailable
                with patch('redis.from_url', side_effect=redis.ConnectionError("No Redis")):
                    with patch('socket.socket') as mock_socket:
                        # Mock socket failures for both PostgreSQL and Redis
                        mock_sock = MagicMock()
                        mock_sock.connect_ex.return_value = 1  # Connection failed
                        mock_socket.return_value = mock_sock
                        
                        config_class = get_adaptive_config('testing')
                        config_instance = config_class()
                        
                        assert config_instance.DETECTED_DATABASE_TYPE == 'sqlite'
                        assert config_instance.CACHE_TYPE == 'simple'
                        assert config_instance.DB_SCHEMA is None
                        
                        # Test feature flags
                        features = config_instance.FEATURES
                        assert features['database_sqlite'] is True
                        assert features['database_postgresql'] is False
                        assert features['cache_redis'] is False
                        assert features['cache_simple'] is True
                        assert features['celery'] is False
                        assert features['websockets'] is True
    
    def test_service_validation_integration(self):
        """Test service validation integration."""
        # Mock different service availability scenarios
        with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("No PostgreSQL")):
            with patch('sqlite3.connect') as mock_sqlite:
                mock_sqlite.return_value = MagicMock()
                
                with patch('redis.from_url', side_effect=redis.ConnectionError("No Redis")):
                    with patch('socket.socket') as mock_socket:
                        mock_sock = MagicMock()
                        mock_sock.connect_ex.return_value = 1  # Connection failed
                        mock_socket.return_value = mock_sock
                        
                        status = validate_current_services()
                        
                        assert status['postgresql'] is False
                        assert status['sqlite'] is True
                        assert status['redis'] is False