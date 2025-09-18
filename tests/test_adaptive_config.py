"""
Tests for Adaptive Configuration System

This module tests the adaptive configuration manager and database manager
to ensure they correctly detect and configure available services.
"""
import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
import psycopg2
import redis
import sqlite3

from app.utils.adaptive_config import (
    AdaptiveConfigManager,
    ServiceStatus,
    DatabaseConfig,
    AdaptiveApplicationConfig,
    get_adaptive_config,
    validate_current_services
)
from app.utils.database_manager import DatabaseManager
from app.utils.unified_config import create_unified_config_class
from config import Config, DevelopmentConfig, TestingConfig


class TestAdaptiveConfigManager:
    """Test cases for AdaptiveConfigManager."""
    
    def test_init(self):
        """Test AdaptiveConfigManager initialization."""
        manager = AdaptiveConfigManager()
        assert manager.environment in ['development', 'testing', 'production']
        assert manager.services == {}
        assert manager._connection_timeout == 5
    
    def test_init_with_environment(self):
        """Test AdaptiveConfigManager initialization with specific environment."""
        manager = AdaptiveConfigManager('production')
        assert manager.environment == 'production'
    
    def test_detect_environment(self):
        """Test environment detection."""
        manager = AdaptiveConfigManager()
        
        # Test default
        with patch.dict(os.environ, {}, clear=True):
            assert manager._detect_environment() == 'development'
        
        # Test production
        with patch.dict(os.environ, {'FLASK_ENV': 'production'}):
            assert manager._detect_environment() == 'production'
        
        # Test testing
        with patch.dict(os.environ, {'FLASK_ENV': 'testing'}):
            assert manager._detect_environment() == 'testing'
    
    @patch('psycopg2.connect')
    @patch('socket.socket')
    def test_test_postgresql_connection_success(self, mock_socket, mock_connect):
        """Test successful PostgreSQL connection."""
        # Mock socket connection
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock
        
        # Mock database connection
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        manager = AdaptiveConfigManager()
        
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user:pass@localhost:5432/test'}):
            result = manager._test_postgresql_connection()
        
        assert result is True
        assert 'postgresql' in manager.services
        assert manager.services['postgresql'].available is True
        mock_connect.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('psycopg2.connect')
    @patch('socket.socket')
    def test_test_postgresql_connection_socket_failure(self, mock_socket, mock_connect):
        """Test PostgreSQL connection failure at socket level."""
        # Mock socket connection failure
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1  # Connection failed
        mock_socket.return_value = mock_sock
        
        manager = AdaptiveConfigManager()
        
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user:pass@localhost:5432/test'}):
            result = manager._test_postgresql_connection()
        
        assert result is False
        assert 'postgresql' in manager.services
        assert manager.services['postgresql'].available is False
        mock_connect.assert_not_called()
    
    @patch('psycopg2.connect')
    @patch('socket.socket')
    def test_test_postgresql_connection_db_failure(self, mock_socket, mock_connect):
        """Test PostgreSQL connection failure at database level."""
        # Mock socket connection success
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock
        
        # Mock database connection failure
        mock_connect.side_effect = psycopg2.OperationalError("Connection failed")
        
        manager = AdaptiveConfigManager()
        
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user:pass@localhost:5432/test'}):
            result = manager._test_postgresql_connection()
        
        assert result is False
        assert 'postgresql' in manager.services
        assert manager.services['postgresql'].available is False
        assert "Connection failed" in manager.services['postgresql'].error_message
    
    @patch('sqlite3.connect')
    def test_test_sqlite_connection_success(self, mock_connect):
        """Test successful SQLite connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        manager = AdaptiveConfigManager()
        result = manager._test_sqlite_connection()
        
        assert result is True
        assert 'sqlite' in manager.services
        assert manager.services['sqlite'].available is True
        mock_connect.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('sqlite3.connect')
    def test_test_sqlite_connection_memory_db(self, mock_connect):
        """Test SQLite connection with in-memory database."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        manager = AdaptiveConfigManager()
        
        with patch.dict(os.environ, {'SQLITE_DATABASE_URL': 'sqlite:///:memory:'}):
            result = manager._test_sqlite_connection()
        
        assert result is True
        assert 'sqlite' in manager.services
        assert manager.services['sqlite'].available is True
    
    @patch('sqlite3.connect')
    def test_test_sqlite_connection_failure(self, mock_connect):
        """Test SQLite connection failure."""
        mock_connect.side_effect = sqlite3.OperationalError("Database locked")
        
        manager = AdaptiveConfigManager()
        result = manager._test_sqlite_connection()
        
        assert result is False
        assert 'sqlite' in manager.services
        assert manager.services['sqlite'].available is False
        assert "Database locked" in manager.services['sqlite'].error_message
    
    @patch('redis.from_url')
    @patch('socket.socket')
    def test_test_redis_connection_success(self, mock_socket, mock_redis):
        """Test successful Redis connection."""
        # Mock socket connection
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock
        
        # Mock Redis connection
        mock_redis_conn = MagicMock()
        mock_redis.return_value = mock_redis_conn
        
        manager = AdaptiveConfigManager()
        result = manager._test_redis_connection()
        
        assert result is True
        assert 'redis' in manager.services
        assert manager.services['redis'].available is True
        mock_redis_conn.ping.assert_called_once()
    
    @patch('redis.from_url')
    @patch('socket.socket')
    def test_test_redis_connection_socket_failure(self, mock_socket, mock_redis):
        """Test Redis connection failure at socket level."""
        # Mock socket connection failure
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1
        mock_socket.return_value = mock_sock
        
        manager = AdaptiveConfigManager()
        result = manager._test_redis_connection()
        
        assert result is False
        assert 'redis' in manager.services
        assert manager.services['redis'].available is False
        mock_redis.assert_not_called()
    
    @patch('redis.from_url')
    @patch('socket.socket')
    def test_test_redis_connection_redis_failure(self, mock_socket, mock_redis):
        """Test Redis connection failure at Redis level."""
        # Mock socket connection success
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock
        
        # Mock Redis connection failure
        mock_redis_conn = MagicMock()
        mock_redis_conn.ping.side_effect = redis.ConnectionError("Redis unavailable")
        mock_redis.return_value = mock_redis_conn
        
        manager = AdaptiveConfigManager()
        result = manager._test_redis_connection()
        
        assert result is False
        assert 'redis' in manager.services
        assert manager.services['redis'].available is False
        assert "Redis unavailable" in manager.services['redis'].error_message
    
    def test_detect_database_postgresql_available(self):
        """Test database detection when PostgreSQL is available."""
        manager = AdaptiveConfigManager()
        
        with patch.object(manager, '_test_postgresql_connection', return_value=True):
            with patch.object(manager, '_get_postgresql_connection_string', return_value='postgresql://test'):
                db_type, connection_string = manager.detect_database()
        
        assert db_type == 'postgresql'
        assert connection_string == 'postgresql://test'
    
    def test_detect_database_sqlite_fallback(self):
        """Test database detection fallback to SQLite."""
        manager = AdaptiveConfigManager()
        
        with patch.object(manager, '_test_postgresql_connection', return_value=False):
            with patch.object(manager, '_get_sqlite_connection_string', return_value='sqlite:///test.db'):
                db_type, connection_string = manager.detect_database()
        
        assert db_type == 'sqlite'
        assert connection_string == 'sqlite:///test.db'
    
    def test_detect_cache_backend_redis_available(self):
        """Test cache backend detection when Redis is available."""
        manager = AdaptiveConfigManager()
        
        with patch.object(manager, '_test_redis_connection', return_value=True):
            backend = manager.detect_cache_backend()
        
        assert backend == 'redis'
    
    def test_detect_cache_backend_simple_fallback(self):
        """Test cache backend detection fallback to simple."""
        manager = AdaptiveConfigManager()
        
        with patch.object(manager, '_test_redis_connection', return_value=False):
            backend = manager.detect_cache_backend()
        
        assert backend == 'simple'
    
    def test_get_config_class_postgresql(self):
        """Test getting config class with PostgreSQL."""
        manager = AdaptiveConfigManager('development')
        
        with patch.object(manager, 'detect_database', return_value=('postgresql', 'postgresql://test')):
            with patch.object(manager, 'detect_cache_backend', return_value='redis'):
                config_class = manager.get_config_class()
        
        config_instance = config_class()
        assert config_instance.SQLALCHEMY_DATABASE_URI == 'postgresql://test'
        assert config_instance.DETECTED_DATABASE_TYPE == 'postgresql'
        assert config_instance.CACHE_TYPE == 'redis'
    
    def test_get_config_class_sqlite(self):
        """Test getting config class with SQLite."""
        manager = AdaptiveConfigManager('development')
        
        with patch.object(manager, 'detect_database', return_value=('sqlite', 'sqlite:///test.db')):
            with patch.object(manager, 'detect_cache_backend', return_value='simple'):
                config_class = manager.get_config_class()
        
        config_instance = config_class()
        assert config_instance.SQLALCHEMY_DATABASE_URI == 'sqlite:///test.db'
        assert config_instance.DETECTED_DATABASE_TYPE == 'sqlite'
        assert config_instance.CACHE_TYPE == 'simple'
        assert config_instance.DB_SCHEMA is None
    
    def test_get_feature_flags(self):
        """Test feature flags generation."""
        manager = AdaptiveConfigManager()
        
        # Mock service status
        manager.services = {
            'postgresql': ServiceStatus('postgresql', True, datetime.now()),
            'redis': ServiceStatus('redis', False, datetime.now())
        }
        
        features = manager._get_feature_flags()
        
        assert features['database_postgresql'] is True
        assert features['cache_redis'] is False
        assert features['cache_simple'] is True
        assert features['celery'] is False  # Requires Redis
        assert features['rate_limiting'] is False  # Requires Redis
        assert features['websockets'] is True  # Always available
    
    def test_validate_services(self):
        """Test service validation."""
        manager = AdaptiveConfigManager()
        
        with patch.object(manager, '_test_postgresql_connection', return_value=True):
            with patch.object(manager, '_test_sqlite_connection', return_value=True):
                with patch.object(manager, '_test_redis_connection', return_value=False):
                    status = manager.validate_services()
        
        assert status['postgresql'] is True
        assert status['sqlite'] is True
        assert status['redis'] is False
    
    def test_create_adaptive_config(self):
        """Test creating complete adaptive configuration."""
        manager = AdaptiveConfigManager('development')
        
        with patch.object(manager, 'detect_database', return_value=('sqlite', 'sqlite:///test.db')):
            with patch.object(manager, 'detect_cache_backend', return_value='simple'):
                adaptive_config = manager.create_adaptive_config()
        
        assert isinstance(adaptive_config, AdaptiveApplicationConfig)
        assert adaptive_config.database.type == 'sqlite'
        assert adaptive_config.database.connection_string == 'sqlite:///test.db'
        assert adaptive_config.environment == 'development'
        assert isinstance(adaptive_config.features, dict)
        assert isinstance(adaptive_config.services, dict)


class TestDatabaseManager:
    """Test cases for DatabaseManager."""
    
    def test_init(self):
        """Test DatabaseManager initialization."""
        manager = DatabaseManager()
        assert manager.connection_timeout == 10
        assert manager.retry_attempts == 3
        assert manager.retry_delay == 1
        assert manager._current_database_type is None
    
    @patch('app.utils.database_manager.create_engine')
    @patch('psycopg2.connect')
    def test_connect_postgresql_success(self, mock_connect, mock_create_engine):
        """Test successful PostgreSQL connection."""
        # Mock psycopg2 connection
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # Mock SQLAlchemy engine
        mock_engine = MagicMock()
        mock_engine_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_engine_conn
        mock_create_engine.return_value = mock_engine
        
        manager = DatabaseManager()
        result = manager.connect_postgresql('postgresql://test')
        
        assert result is True
        assert manager._current_database_type == 'postgresql'
        assert manager._current_connection_string == 'postgresql://test'
        assert manager._engine == mock_engine
    
    @patch('psycopg2.connect')
    def test_connect_postgresql_failure(self, mock_connect):
        """Test PostgreSQL connection failure."""
        mock_connect.side_effect = psycopg2.OperationalError("Connection failed")
        
        manager = DatabaseManager()
        result = manager.connect_postgresql('postgresql://test')
        
        assert result is False
        assert manager._current_database_type is None
    
    @patch('os.makedirs')
    @patch('app.utils.database_manager.create_engine')
    @patch('sqlite3.connect')
    def test_connect_sqlite_success(self, mock_connect, mock_create_engine, mock_makedirs):
        """Test successful SQLite connection."""
        # Mock sqlite3 connection
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # Mock SQLAlchemy engine
        mock_engine = MagicMock()
        mock_engine_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_engine_conn
        mock_create_engine.return_value = mock_engine
        
        manager = DatabaseManager()
        result = manager.connect_sqlite('sqlite:///test.db')
        
        assert result is True
        assert manager._current_database_type == 'sqlite'
        assert manager._current_connection_string == 'sqlite:///test.db'
        assert manager._engine == mock_engine
    
    @patch('sqlite3.connect')
    def test_connect_sqlite_failure(self, mock_connect):
        """Test SQLite connection failure."""
        mock_connect.side_effect = sqlite3.OperationalError("Database locked")
        
        manager = DatabaseManager()
        result = manager.connect_sqlite('sqlite:///test.db')
        
        assert result is False
        assert manager._current_database_type is None
    
    def test_establish_connection_postgresql_success(self):
        """Test establishing connection with PostgreSQL success."""
        manager = DatabaseManager()
        
        with patch.object(manager, 'connect_postgresql', return_value=True):
            manager._current_database_type = 'postgresql'
            manager._current_connection_string = 'postgresql://test'
            
            success, db_type, connection_string = manager.establish_connection()
        
        assert success is True
        assert db_type == 'postgresql'
        assert connection_string == 'postgresql://test'
    
    def test_establish_connection_sqlite_fallback(self):
        """Test establishing connection with SQLite fallback."""
        manager = DatabaseManager()
        
        with patch.object(manager, 'connect_postgresql', return_value=False):
            with patch.object(manager, 'connect_sqlite', return_value=True):
                manager._current_database_type = 'sqlite'
                manager._current_connection_string = 'sqlite:///test.db'
                
                success, db_type, connection_string = manager.establish_connection()
        
        assert success is True
        assert db_type == 'sqlite'
        assert connection_string == 'sqlite:///test.db'
    
    def test_establish_connection_both_fail(self):
        """Test establishing connection when both databases fail."""
        manager = DatabaseManager()
        
        with patch.object(manager, 'connect_postgresql', return_value=False):
            with patch.object(manager, 'connect_sqlite', return_value=False):
                success, db_type, connection_string = manager.establish_connection()
        
        assert success is False
        assert db_type is None
        assert connection_string is None
    
    def test_test_connection_health_success(self):
        """Test connection health check success."""
        manager = DatabaseManager()
        
        # Mock engine
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        manager._engine = mock_engine
        
        result = manager.test_connection_health()
        
        assert result is True
        mock_conn.execute.assert_called_once()
    
    def test_test_connection_health_failure(self):
        """Test connection health check failure."""
        manager = DatabaseManager()
        
        # Mock engine with failure
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Connection lost")
        manager._engine = mock_engine
        
        result = manager.test_connection_health()
        
        assert result is False
    
    def test_test_connection_health_no_engine(self):
        """Test connection health check with no engine."""
        manager = DatabaseManager()
        result = manager.test_connection_health()
        assert result is False
    
    def test_get_connection_info(self):
        """Test getting connection information."""
        manager = DatabaseManager()
        manager._current_database_type = 'postgresql'
        manager._current_connection_string = 'postgresql://user:pass@localhost/db'
        
        # Mock engine
        mock_engine = MagicMock()
        manager._engine = mock_engine
        
        with patch.object(manager, 'test_connection_health', return_value=True):
            info = manager.get_connection_info()
        
        assert info['database_type'] == 'postgresql'
        assert 'user:****@localhost' in info['connection_string']  # Password masked
        assert info['is_connected'] is True
        assert info['is_healthy'] is True
    
    def test_mask_password(self):
        """Test password masking in connection strings."""
        manager = DatabaseManager()
        
        # Test PostgreSQL connection string
        masked = manager._mask_password('postgresql://user:password@localhost:5432/db')
        assert masked == 'postgresql://user:********@localhost:5432/db'
        
        # Test connection string without password
        masked = manager._mask_password('postgresql://user@localhost:5432/db')
        assert masked == 'postgresql://user@localhost:5432/db'
        
        # Test SQLite connection string
        masked = manager._mask_password('sqlite:///test.db')
        assert masked == 'sqlite:///test.db'


class TestUnifiedConfig:
    """Test cases for unified configuration system."""
    
    def test_create_unified_config_class_development(self):
        """Test creating unified config class for development."""
        with patch('app.utils.unified_config.AdaptiveConfigManager') as mock_manager_class:
            # Mock adaptive config manager
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            
            # Mock adaptive config
            mock_adaptive_config = MagicMock()
            mock_adaptive_config.database.type = 'sqlite'
            mock_adaptive_config.database.connection_string = 'sqlite:///test.db'
            mock_adaptive_config.database.engine_options = {}
            mock_adaptive_config.services = {}
            mock_adaptive_config.features = {'cache_redis': False}
            mock_manager.create_adaptive_config.return_value = mock_adaptive_config
            
            config_class = create_unified_config_class('development')
            config_instance = config_class()
            
            assert config_instance.SQLALCHEMY_DATABASE_URI == 'sqlite:///test.db'
            assert config_instance.DETECTED_DATABASE_TYPE == 'sqlite'
            assert config_instance.CACHE_TYPE == 'simple'
    
    def test_get_adaptive_config_function(self):
        """Test get_adaptive_config function."""
        with patch('app.utils.adaptive_config.AdaptiveConfigManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            
            # Mock config class
            mock_config_class = MagicMock()
            mock_manager.get_config_class.return_value = mock_config_class
            
            result = get_adaptive_config('development')
            
            assert result == mock_config_class
            mock_manager_class.assert_called_once_with('development')
    
    def test_validate_current_services_function(self):
        """Test validate_current_services function."""
        with patch('app.utils.adaptive_config.AdaptiveConfigManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            
            mock_status = {'postgresql': True, 'redis': False}
            mock_manager.validate_services.return_value = mock_status
            
            result = validate_current_services()
            
            assert result == mock_status
            mock_manager_class.assert_called_once_with()


@pytest.fixture
def temp_db_file():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_path = f.name
    yield temp_path
    try:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    except PermissionError:
        # On Windows, the file might still be locked
        pass


class TestIntegration:
    """Integration tests for the adaptive configuration system."""
    
    def test_full_sqlite_configuration(self, temp_db_file):
        """Test full configuration with SQLite."""
        with patch.dict(os.environ, {
            'SQLITE_DATABASE_URL': f'sqlite:///{temp_db_file}',
            'FLASK_ENV': 'testing'
        }):
            # Mock PostgreSQL as unavailable
            with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("No PostgreSQL")):
                # Mock Redis as unavailable
                with patch('redis.from_url', side_effect=redis.ConnectionError("No Redis")):
                    config_class = get_adaptive_config('testing')
                    config_instance = config_class()
                    
                    assert config_instance.DETECTED_DATABASE_TYPE == 'sqlite'
                    assert config_instance.CACHE_TYPE == 'simple'
                    assert not hasattr(config_instance, 'DB_SCHEMA')
                    assert config_instance.CELERY_BROKER_URL is None
    
    def test_database_manager_integration(self, temp_db_file):
        """Test database manager integration."""
        manager = DatabaseManager()
        
        # Test SQLite connection
        result = manager.connect_sqlite(f'sqlite:///{temp_db_file}')
        assert result is True
        assert manager.get_database_type() == 'sqlite'
        
        # Test connection health
        assert manager.test_connection_health() is True
        
        # Test connection info
        info = manager.get_connection_info()
        assert info['database_type'] == 'sqlite'
        assert info['is_connected'] is True
        assert info['is_healthy'] is True