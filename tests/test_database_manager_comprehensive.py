"""
Comprehensive tests for Database Manager

This module provides comprehensive unit tests for the DatabaseManager class,
covering connection management, health monitoring, and error handling.

Requirements covered: 1.4, 2.1, 2.2, 2.3, 4.1, 4.2, 4.3, 4.5
"""
import os
import pytest
import tempfile
import time
from unittest.mock import patch, MagicMock
from datetime import datetime
import psycopg2
import sqlite3

from app.utils.database_manager import (
    DatabaseManager,
    get_database_manager,
    initialize_database_with_fallback
)


class TestDatabaseManagerComprehensive:
    """Comprehensive test cases for DatabaseManager."""
    
    def test_initialization_with_app(self):
        """Test DatabaseManager initialization with Flask app."""
        mock_app = MagicMock()
        mock_app.config = {
            'DATABASE_CONNECTION_TIMEOUT': 15,
            'DATABASE_HEALTH_CHECK_INTERVAL': 60,
            'DATABASE_HEALTH_MONITORING_ENABLED': True
        }
        mock_app.extensions = {}
        
        manager = DatabaseManager(mock_app)
        
        assert manager.app == mock_app
        assert manager.connection_timeout == 15
        assert manager._health_check_interval == 60
        assert 'database_manager' in mock_app.extensions
    
    def test_health_monitoring_lifecycle(self):
        """Test health monitoring start/stop lifecycle."""
        manager = DatabaseManager()
        
        # Test starting health monitoring
        manager.start_health_monitoring()
        assert manager._health_monitor_thread is not None
        assert manager._health_monitor_thread.is_alive()
        
        # Test stopping health monitoring
        manager.stop_health_monitoring()
        time.sleep(0.1)  # Give thread time to stop
        assert not manager._health_monitor_thread.is_alive()
    
    def test_health_callbacks(self):
        """Test health status change callbacks."""
        manager = DatabaseManager()
        
        # Add callback
        callback_calls = []
        def test_callback(is_healthy, db_type):
            callback_calls.append((is_healthy, db_type))
        
        manager.add_health_callback(test_callback)
        assert len(manager._health_callbacks) == 1
        
        # Simulate health status change
        manager._health_status = False
        manager._current_database_type = 'sqlite'
        
        # Manually trigger callback (normally done by health monitor)
        for callback in manager._health_callbacks:
            callback(manager._health_status, manager._current_database_type)
        
        assert len(callback_calls) == 1
        assert callback_calls[0] == (False, 'sqlite')
    
    @patch('psycopg2.connect')
    @patch('app.utils.database_manager.create_engine')
    def test_postgresql_connection_with_retries(self, mock_create_engine, mock_connect):
        """Test PostgreSQL connection with retry logic."""
        manager = DatabaseManager()
        manager.retry_attempts = 3
        manager.retry_delay = 0.1  # Fast retry for testing
        
        # Test successful connection after retries
        mock_connect.side_effect = [
            psycopg2.OperationalError("Connection failed"),
            psycopg2.OperationalError("Connection failed"),
            MagicMock()  # Success on third attempt
        ]
        
        mock_engine = MagicMock()
        mock_engine_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_engine_conn
        mock_create_engine.return_value = mock_engine
        
        result = manager.connect_postgresql('postgresql://test')
        
        assert result is True
        assert mock_connect.call_count == 3
        assert manager._current_database_type == 'postgresql'
        assert manager._connection_stats['postgresql_attempts'] == 1
        assert manager._connection_stats['successful_connections'] == 1
    
    def test_establish_connection_fallback_logic(self):
        """Test connection establishment with fallback logic."""
        manager = DatabaseManager()
        
        # Test PostgreSQL success
        with patch.object(manager, 'connect_postgresql', return_value=True):
            manager._current_database_type = 'postgresql'
            manager._current_connection_string = 'postgresql://test'
            
            success, db_type, connection_string = manager.establish_connection()
            
            assert success is True
            assert db_type == 'postgresql'
            assert connection_string == 'postgresql://test'
        
        # Test PostgreSQL failure, SQLite success
        with patch.object(manager, 'connect_postgresql', return_value=False):
            with patch.object(manager, 'connect_sqlite', return_value=True):
                manager._current_database_type = 'sqlite'
                manager._current_connection_string = 'sqlite:///test.db'
                
                success, db_type, connection_string = manager.establish_connection()
                
                assert success is True
                assert db_type == 'sqlite'
                assert connection_string == 'sqlite:///test.db'
        
        # Test both fail
        with patch.object(manager, 'connect_postgresql', return_value=False):
            with patch.object(manager, 'connect_sqlite', return_value=False):
                success, db_type, connection_string = manager.establish_connection()
                
                assert success is False
                assert db_type is None
                assert connection_string is None
    
    def test_connection_health_monitoring(self):
        """Test connection health monitoring functionality."""
        manager = DatabaseManager()
        
        # Test with no engine
        assert manager.test_connection_health() is False
        
        # Test with healthy connection
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        manager._engine = mock_engine
        
        assert manager.test_connection_health() is True
        mock_conn.execute.assert_called_once()
        
        # Test with unhealthy connection
        mock_engine.connect.side_effect = Exception("Connection lost")
        
        assert manager.test_connection_health() is False
    
    def test_connection_statistics(self):
        """Test connection statistics tracking."""
        manager = DatabaseManager()
        
        # Initial statistics
        stats = manager.get_connection_statistics()
        assert stats['total_connections'] == 0
        assert stats['success_rate'] == 0.0
        assert stats['failure_rate'] == 0.0
        
        # Simulate some connections
        manager._connection_stats['total_connections'] = 10
        manager._connection_stats['successful_connections'] = 8
        manager._connection_stats['failed_connections'] = 2
        
        stats = manager.get_connection_statistics()
        assert stats['success_rate'] == 0.8
        assert stats['failure_rate'] == 0.2
        
        # Test statistics reset
        manager.reset_statistics()
        stats = manager.get_connection_statistics()
        assert stats['total_connections'] == 0


class TestDatabaseManagerIntegration:
    """Integration tests for DatabaseManager."""
    
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
    
    def test_sqlite_connection_integration(self, temp_db_file):
        """Test SQLite connection integration."""
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
    
    def test_initialize_database_with_fallback_integration(self):
        """Test database initialization with fallback integration."""
        mock_app = MagicMock()
        mock_app.config = {'TESTING': True}
        mock_app.extensions = {}
        
        with patch('app.utils.database_manager.DatabaseManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            
            # Test successful initialization
            mock_manager.establish_connection.return_value = (True, 'sqlite', 'sqlite:///test.db')
            mock_manager.migrate_if_needed.return_value = True
            
            success, db_type, connection_string = initialize_database_with_fallback(mock_app)
            
            assert success is True
            assert db_type == 'sqlite'
            assert connection_string == 'sqlite:///test.db'
            
            mock_manager.establish_connection.assert_called_once()
            mock_manager.migrate_if_needed.assert_called_once()