"""
Comprehensive tests for database connection fixes.

This module tests the DatabaseURLParser, SmartConnectionManager, and related
components to ensure proper database connection handling and fallback logic.
"""
import os
import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

# Import the components to test
from app.services.database_url_parser import (
    DatabaseURLParser, DatabaseConfig, DatabaseType, ValidationResult, ValidationError
)
from app.utils.database_url_parser import (
    DatabaseURLParser as UtilsParser, DatabaseConfig as UtilsConfig, 
    DatabaseType as UtilsType, ConnectionResult, ValidationResult as UtilsValidationResult
)
from app.utils.smart_connection_manager import (
    SmartConnectionManager, PostgreSQLConnector, SQLiteConnector
)


class TestDatabaseURLParser:
    """Test the DatabaseURLParser class with various URL formats."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = DatabaseURLParser()
    
    def test_parse_empty_url(self):
        """Test parsing empty or None URLs."""
        # Test None URL
        config = self.parser.parse_url(None)
        assert config.type == DatabaseType.SQLITE
        assert config.is_valid is True
        assert "Empty or None URL provided" in config.error_message
        
        # Test empty string
        config = self.parser.parse_url("")
        assert config.type == DatabaseType.SQLITE
        assert config.is_valid is True
        
        # Test whitespace only
        config = self.parser.parse_url("   ")
        assert config.type == DatabaseType.SQLITE
        assert config.is_valid is True
    
    def test_detect_postgresql_urls(self):
        """Test detection of PostgreSQL URL formats."""
        postgresql_urls = [
            "postgresql://user:pass@localhost:5432/dbname",
            "postgres://user:pass@localhost:5432/dbname",
            "psql://user:pass@localhost:5432/dbname",
            "POSTGRESQL://USER:PASS@LOCALHOST:5432/DBNAME",  # Case insensitive
        ]
        
        for url in postgresql_urls:
            db_type = self.parser.detect_database_type(url)
            assert db_type == DatabaseType.POSTGRESQL, f"Failed to detect PostgreSQL for: {url}"
    
    def test_detect_sqlite_urls(self):
        """Test detection of SQLite URL formats."""
        sqlite_urls = [
            "sqlite:///path/to/database.db",
            "sqlite:///:memory:",
            "SQLITE:///PATH/TO/DATABASE.DB",  # Case insensitive
        ]
        
        for url in sqlite_urls:
            db_type = self.parser.detect_database_type(url)
            assert db_type == DatabaseType.SQLITE, f"Failed to detect SQLite for: {url}"
    
    def test_detect_unknown_urls(self):
        """Test detection of unknown URL formats."""
        unknown_urls = [
            "mysql://user:pass@localhost:3306/dbname",
            "mongodb://localhost:27017/dbname",
            "redis://localhost:6379/0",
            "invalid_url_format",
            "http://example.com",
        ]
        
        for url in unknown_urls:
            db_type = self.parser.detect_database_type(url)
            assert db_type == DatabaseType.UNKNOWN, f"Should detect unknown for: {url}"
    
    def test_parse_valid_postgresql_url(self):
        """Test parsing valid PostgreSQL URLs."""
        url = "postgresql://testuser:testpass@localhost:5432/testdb"
        config = self.parser.parse_url(url)
        
        assert config.type == DatabaseType.POSTGRESQL
        assert config.is_valid is True
        assert config.driver == "psycopg2"
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "testdb"
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.error_message is None
    
    def test_parse_postgresql_url_without_port(self):
        """Test parsing PostgreSQL URL without explicit port."""
        url = "postgresql://testuser:testpass@localhost/testdb"
        config = self.parser.parse_url(url)
        
        assert config.type == DatabaseType.POSTGRESQL
        assert config.is_valid is True
        assert config.port is None
        assert config.host == "localhost"
    
    def test_parse_postgresql_url_with_query_params(self):
        """Test parsing PostgreSQL URL with query parameters."""
        url = "postgresql://testuser:testpass@localhost:5432/testdb?sslmode=require&application_name=test"
        config = self.parser.parse_url(url)
        
        assert config.type == DatabaseType.POSTGRESQL
        assert config.is_valid is True
        assert "sslmode" in config.options
        assert config.options["sslmode"] == "require"
        assert config.options["application_name"] == "test"
    
    def test_parse_invalid_postgresql_url(self):
        """Test parsing invalid PostgreSQL URLs."""
        invalid_urls = [
            "postgresql://",  # Missing components
            "postgresql://localhost",  # Missing database
            "postgresql://:password@localhost/db",  # Missing username
            "postgresql://user@localhost:invalid_port/db",  # Invalid port
        ]
        
        for url in invalid_urls:
            config = self.parser.parse_url(url)
            assert config.is_valid is False, f"Should be invalid: {url}"
            assert config.error_message is not None
    
    def test_parse_valid_sqlite_url(self):
        """Test parsing valid SQLite URLs."""
        # File database
        url = "sqlite:///path/to/database.db"
        config = self.parser.parse_url(url)
        
        assert config.type == DatabaseType.SQLITE
        assert config.is_valid is True
        assert config.driver == "sqlite3"
        assert config.database == "path/to/database.db"
        
        # Memory database
        url = "sqlite:///:memory:"
        config = self.parser.parse_url(url)
        
        assert config.type == DatabaseType.SQLITE
        assert config.is_valid is True
        assert config.database == ":memory:"
    
    def test_parse_invalid_sqlite_url(self):
        """Test parsing invalid SQLite URLs."""
        invalid_urls = [
            "sqlite://",  # Missing path
            "sqlite:///",  # Empty path
        ]
        
        for url in invalid_urls:
            config = self.parser.parse_url(url)
            assert config.is_valid is False, f"Should be invalid: {url}"
    
    def test_validate_url_comprehensive(self):
        """Test comprehensive URL validation."""
        # Valid URLs
        valid_urls = [
            "postgresql://user:pass@localhost:5432/db",
            "sqlite:///test.db",
            "sqlite:///:memory:",
        ]
        
        for url in valid_urls:
            validation = self.parser.validate_url(url)
            assert validation.result == ValidationResult.VALID, f"Should be valid: {url}"
        
        # Invalid URLs
        invalid_urls = [
            "",  # Empty
            "invalid://format",  # Unknown scheme
            "postgresql://",  # Missing components
            "sqlite://",  # Missing path
        ]
        
        for url in invalid_urls:
            validation = self.parser.validate_url(url)
            assert validation.result != ValidationResult.VALID, f"Should be invalid: {url}"
            assert validation.message is not None
    
    def test_caching_behavior(self):
        """Test URL validation caching."""
        url = "postgresql://user:pass@localhost:5432/db"
        
        # First parse
        config1 = self.parser.parse_url(url)
        
        # Second parse should use cache
        config2 = self.parser.parse_url(url)
        
        assert config1.type == config2.type
        assert config1.is_valid == config2.is_valid
        
        # Check cache stats
        stats = self.parser.get_cache_stats()
        assert stats['cache_size'] > 0
        assert url in stats['cached_urls']
        
        # Clear cache
        self.parser.clear_cache()
        stats = self.parser.get_cache_stats()
        assert stats['cache_size'] == 0
    
    def test_example_urls(self):
        """Test that example URLs are valid."""
        examples = self.parser.get_example_urls()
        
        for name, url in examples.items():
            config = self.parser.parse_url(url)
            assert config.is_valid is True, f"Example URL {name} should be valid: {url}"


class TestUtilsDatabaseURLParser:
    """Test the utils version of DatabaseURLParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = UtilsParser()
    
    def test_parse_empty_url(self):
        """Test parsing empty URLs."""
        config = self.parser.parse_url("")
        assert config.type == UtilsType.UNKNOWN
        assert config.is_valid is False
        assert "Empty or None URL provided" in config.error_message
    
    def test_detect_database_types(self):
        """Test database type detection."""
        test_cases = [
            ("postgresql://user:pass@host/db", UtilsType.POSTGRESQL),
            ("postgres://user:pass@host/db", UtilsType.POSTGRESQL),
            ("sqlite:///path/to/db.sqlite", UtilsType.SQLITE),
            ("mysql://user:pass@host/db", UtilsType.UNKNOWN),
        ]
        
        for url, expected_type in test_cases:
            detected_type = self.parser.detect_database_type(url)
            assert detected_type == expected_type, f"Failed for {url}"
    
    def test_parse_postgresql_url(self):
        """Test PostgreSQL URL parsing."""
        url = "postgresql://user:pass@localhost:5432/testdb?sslmode=require"
        config = self.parser.parse_url(url)
        
        assert config.type == UtilsType.POSTGRESQL
        assert config.is_valid is True
        assert config.driver == "psycopg2"
        assert "sslmode" in config.options
    
    def test_parse_sqlite_url(self):
        """Test SQLite URL parsing."""
        url = "sqlite:///test.db"
        config = self.parser.parse_url(url)
        
        assert config.type == UtilsType.SQLITE
        assert config.is_valid is True
        assert config.driver == "sqlite3"
    
    def test_validate_url(self):
        """Test URL validation."""
        # Valid URL
        result = self.parser.validate_url("postgresql://user:pass@host:5432/db")
        assert result.is_valid is True
        
        # Invalid URL
        result = self.parser.validate_url("")
        assert result.is_valid is False
        assert result.error_message is not None
    
    def test_default_configs(self):
        """Test default configuration methods."""
        # Default SQLite config
        config = self.parser.get_default_sqlite_config()
        assert config.type == UtilsType.SQLITE
        assert config.is_valid is True
        assert "ai_secretary.db" in config.connection_string
        
        # Memory SQLite config
        config = self.parser.get_memory_sqlite_config()
        assert config.type == UtilsType.SQLITE
        assert config.is_valid is True
        assert ":memory:" in config.connection_string


class TestSmartConnectionManager:
    """Test the SmartConnectionManager with PostgreSQL and SQLite connections."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = SmartConnectionManager(connection_timeout=5, retry_attempts=2)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_connect_with_no_url(self):
        """Test connection when no URL is provided."""
        result = self.manager.connect()
        
        # Should fallback to SQLite
        assert result.database_type == DatabaseType.SQLITE
        assert result.success is True
        assert "ai_secretary.db" in result.connection_string
    
    @patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///test.db'})
    def test_connect_with_sqlite_url(self):
        """Test connection with SQLite URL."""
        result = self.manager.connect()
        
        assert result.database_type == DatabaseType.SQLITE
        assert result.success is True
        assert result.connection_string == 'sqlite:///test.db'
        assert result.engine is not None
    
    @patch.dict(os.environ, {'DATABASE_URL': 'invalid://url/format'})
    def test_connect_with_invalid_url(self):
        """Test connection with invalid URL falls back to SQLite."""
        result = self.manager.connect()
        
        # Should fallback to SQLite
        assert result.database_type == DatabaseType.SQLITE
        assert result.success is True
        assert result.fallback_used is True
    
    @patch('psycopg2.connect')
    @patch('sqlalchemy.create_engine')
    def test_connect_postgresql_success(self, mock_create_engine, mock_psycopg2_connect):
        """Test successful PostgreSQL connection."""
        # Mock successful psycopg2 connection
        mock_conn = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        
        # Mock successful SQLAlchemy engine
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        # Mock successful engine test
        mock_engine.connect.return_value.__enter__ = Mock()
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value.execute = Mock()
        
        url = "postgresql://user:pass@localhost:5432/testdb"
        result = self.manager.connect(url)
        
        assert result.success is True
        assert result.database_type == DatabaseType.POSTGRESQL
        assert result.engine == mock_engine
        
        # Verify psycopg2 was called for initial test
        mock_psycopg2_connect.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('psycopg2.connect')
    def test_connect_postgresql_failure_fallback(self, mock_psycopg2_connect):
        """Test PostgreSQL connection failure with fallback to SQLite."""
        # Mock failed psycopg2 connection
        mock_psycopg2_connect.side_effect = Exception("Connection failed")
        
        url = "postgresql://user:pass@localhost:5432/testdb"
        result = self.manager.connect(url)
        
        # Should fallback to SQLite
        assert result.database_type == DatabaseType.SQLITE
        assert result.success is True
        assert result.fallback_used is True
    
    def test_connect_sqlite_memory(self):
        """Test SQLite memory database connection."""
        url = "sqlite:///:memory:"
        result = self.manager.connect(url)
        
        assert result.success is True
        assert result.database_type == DatabaseType.SQLITE
        assert result.engine is not None
    
    def test_connect_sqlite_file(self):
        """Test SQLite file database connection."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            url = f"sqlite:///{tmp_path}"
            result = self.manager.connect(url)
            
            assert result.success is True
            assert result.database_type == DatabaseType.SQLITE
            assert result.engine is not None
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_get_current_connection(self):
        """Test getting current connection information."""
        # Initially no connection
        assert self.manager.get_current_connection() is None
        
        # After connection
        result = self.manager.connect("sqlite:///:memory:")
        assert result.success is True
        
        current = self.manager.get_current_connection()
        assert current is not None
        assert current.database_type == DatabaseType.SQLITE
    
    def test_test_current_connection(self):
        """Test testing current connection health."""
        # No connection initially
        assert self.manager.test_current_connection() is False
        
        # After successful connection
        result = self.manager.connect("sqlite:///:memory:")
        assert result.success is True
        assert self.manager.test_current_connection() is True
    
    def test_reconnect(self):
        """Test reconnection functionality."""
        # Initial connection
        result1 = self.manager.connect("sqlite:///:memory:")
        assert result1.success is True
        
        # Reconnect
        result2 = self.manager.reconnect()
        assert result2.success is True
        assert result2.database_type == DatabaseType.SQLITE
    
    def test_disconnect(self):
        """Test disconnection and cleanup."""
        # Connect first
        result = self.manager.connect("sqlite:///:memory:")
        assert result.success is True
        assert self.manager.get_current_connection() is not None
        
        # Disconnect
        self.manager.disconnect()
        assert self.manager.get_current_connection() is None
    
    def test_get_connection_info(self):
        """Test getting connection information."""
        # No connection
        info = self.manager.get_connection_info()
        assert info['connected'] is False
        assert info['database_type'] is None
        
        # With connection
        result = self.manager.connect("sqlite:///:memory:")
        assert result.success is True
        
        info = self.manager.get_connection_info()
        assert info['connected'] is True
        assert info['database_type'] == 'sqlite'
        assert info['is_healthy'] is True
        assert info['fallback_used'] is False


class TestPostgreSQLConnector:
    """Test PostgreSQL connector specifically."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.connector = PostgreSQLConnector(connection_timeout=5, retry_attempts=2)
    
    def test_invalid_database_type(self):
        """Test connector with invalid database type."""
        config = UtilsConfig(
            type=UtilsType.SQLITE,  # Wrong type
            connection_string="sqlite:///test.db",
            driver="sqlite3",
            options={},
            is_valid=True
        )
        
        result = self.connector.connect(config)
        assert result.success is False
        assert "Invalid database type" in result.error_message
    
    @patch('psycopg2.connect')
    @patch('sqlalchemy.create_engine')
    def test_successful_connection(self, mock_create_engine, mock_psycopg2_connect):
        """Test successful PostgreSQL connection."""
        # Mock successful connections
        mock_conn = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        mock_engine.connect.return_value.__enter__ = Mock()
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value.execute = Mock()
        
        config = UtilsConfig(
            type=UtilsType.POSTGRESQL,
            connection_string="postgresql://user:pass@localhost:5432/db",
            driver="psycopg2",
            options={},
            is_valid=True
        )
        
        result = self.connector.connect(config)
        
        assert result.success is True
        assert result.database_type == DatabaseType.POSTGRESQL
        assert result.engine == mock_engine
    
    @patch('psycopg2.connect')
    def test_connection_failure(self, mock_psycopg2_connect):
        """Test PostgreSQL connection failure."""
        mock_psycopg2_connect.side_effect = Exception("Connection failed")
        
        config = UtilsConfig(
            type=UtilsType.POSTGRESQL,
            connection_string="postgresql://user:pass@localhost:5432/db",
            driver="psycopg2",
            options={},
            is_valid=True
        )
        
        result = self.connector.connect(config)
        
        assert result.success is False
        assert "Connection failed" in result.error_message


class TestSQLiteConnector:
    """Test SQLite connector specifically."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.connector = SQLiteConnector(connection_timeout=5)
    
    def test_invalid_database_type(self):
        """Test connector with invalid database type."""
        config = UtilsConfig(
            type=UtilsType.POSTGRESQL,  # Wrong type
            connection_string="postgresql://user:pass@host/db",
            driver="psycopg2",
            options={},
            is_valid=True
        )
        
        result = self.connector.connect(config)
        assert result.success is False
        assert "Invalid database type" in result.error_message
    
    def test_memory_database_connection(self):
        """Test SQLite memory database connection."""
        config = UtilsConfig(
            type=UtilsType.SQLITE,
            connection_string="sqlite:///:memory:",
            driver="sqlite3",
            options={},
            is_valid=True
        )
        
        result = self.connector.connect(config)
        
        assert result.success is True
        assert result.database_type == DatabaseType.SQLITE
        assert result.engine is not None
    
    def test_file_database_connection(self):
        """Test SQLite file database connection."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            config = UtilsConfig(
                type=UtilsType.SQLITE,
                connection_string=f"sqlite:///{tmp_path}",
                driver="sqlite3",
                options={},
                is_valid=True
            )
            
            result = self.connector.connect(config)
            
            assert result.success is True
            assert result.database_type == DatabaseType.SQLITE
            assert result.engine is not None
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_directory_creation(self):
        """Test that SQLite connector creates directories as needed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "subdir", "test.db")
            
            config = UtilsConfig(
                type=UtilsType.SQLITE,
                connection_string=f"sqlite:///{db_path}",
                driver="sqlite3",
                options={},
                is_valid=True
            )
            
            result = self.connector.connect(config)
            
            assert result.success is True
            assert os.path.exists(os.path.dirname(db_path))
    
    @patch('sqlite3.connect')
    def test_connection_failure(self, mock_sqlite_connect):
        """Test SQLite connection failure."""
        mock_sqlite_connect.side_effect = Exception("SQLite error")
        
        config = UtilsConfig(
            type=UtilsType.SQLITE,
            connection_string="sqlite:///test.db",
            driver="sqlite3",
            options={},
            is_valid=True
        )
        
        result = self.connector.connect(config)
        
        assert result.success is False
        assert "SQLite error" in result.error_message


class TestFallbackBehavior:
    """Test fallback behavior and error handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = SmartConnectionManager()
    
    @patch('psycopg2.connect')
    def test_postgresql_to_sqlite_fallback(self, mock_psycopg2_connect):
        """Test fallback from PostgreSQL to SQLite."""
        mock_psycopg2_connect.side_effect = Exception("PostgreSQL unavailable")
        
        url = "postgresql://user:pass@localhost:5432/db"
        result = self.manager.connect(url)
        
        # Should fallback to SQLite
        assert result.database_type == DatabaseType.SQLITE
        assert result.success is True
        assert result.fallback_used is True
    
    def test_invalid_url_fallback(self):
        """Test fallback when URL is invalid."""
        url = "invalid://url/format"
        result = self.manager.connect(url)
        
        # Should fallback to SQLite
        assert result.database_type == DatabaseType.SQLITE
        assert result.success is True
        assert result.fallback_used is True
    
    @patch.dict(os.environ, {'SQLITE_DATABASE_URL': 'sqlite:///custom.db'})
    def test_custom_sqlite_fallback(self):
        """Test fallback to custom SQLite URL from environment."""
        url = "invalid://url"
        result = self.manager.connect(url)
        
        assert result.database_type == DatabaseType.SQLITE
        assert result.success is True
        assert "custom.db" in result.connection_string


if __name__ == '__main__':
    pytest.main([__file__, '-v'])