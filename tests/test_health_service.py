"""Unit tests for health service."""

import pytest
from unittest.mock import Mock, patch, MagicMock, create_autospec
import time
import redis
import unittest.mock
from sqlalchemy.exc import OperationalError, TimeoutError as SQLTimeoutError
from app.services.health_service import HealthService, HealthCheckResult, OverallHealthResult


class TestHealthService:
    """Unit tests for HealthService class."""

    def test_health_check_result_dataclass(self):
        """Test HealthCheckResult dataclass creation."""
        result = HealthCheckResult(
            status="healthy",
            response_time_ms=50,
            error=None
        )
        
        assert result.status == "healthy"
        assert result.response_time_ms == 50
        assert result.error is None

    def test_overall_health_result_dataclass(self):
        """Test OverallHealthResult dataclass creation."""
        checks = {
            "database": HealthCheckResult("healthy", 50),
            "redis": HealthCheckResult("healthy", 25)
        }
        
        result = OverallHealthResult(
            status="healthy",
            checks=checks,
            timestamp="2025-08-10T22:48:26Z"
        )
        
        assert result.status == "healthy"
        assert len(result.checks) == 2
        assert result.timestamp == "2025-08-10T22:48:26Z"


class TestDatabaseHealthCheck:
    """Unit tests for database health check functionality."""

    @patch('app.services.health_service.db')
    @patch('app.services.health_service.current_app')
    def test_check_database_healthy(self, mock_app, mock_db):
        """Test database connectivity check when database is healthy."""
        # Setup mocks
        mock_app.config.get.return_value = 5  # timeout
        mock_connection = Mock()
        mock_db.engine.connect.return_value.__enter__.return_value = mock_connection
        
        # Mock time to control response time calculation
        with patch('time.time', side_effect=[0.0, 0.05]):  # 50ms response time
            result = HealthService.check_database()
        
        assert result.status == "healthy"
        assert result.response_time_ms == 50
        assert result.error is None
        
        # Verify database calls
        mock_db.engine.connect.assert_called_once()
        mock_connection.execute.assert_called()

    @patch('app.services.health_service.db')
    @patch('app.services.health_service.current_app')
    def test_check_database_connection_error(self, mock_app, mock_db):
        """Test database connectivity check when connection fails."""
        # Setup mocks
        mock_app.config.get.return_value = 5  # timeout
        mock_app.logger = Mock()
        mock_db.engine.connect.side_effect = OperationalError("Connection failed", None, None)
        
        # Mock time to control response time calculation
        with patch('time.time', side_effect=[0.0, 0.1]):  # 100ms response time
            result = HealthService.check_database()
        
        assert result.status == "unhealthy"
        assert result.response_time_ms == 100
        assert "Database connection failed" in result.error
        
        # Verify logging
        mock_app.logger.warning.assert_called_once()

    @patch('app.services.health_service.db')
    @patch('app.services.health_service.current_app')
    def test_check_database_timeout_error(self, mock_app, mock_db):
        """Test database connectivity check when timeout occurs."""
        # Setup mocks
        mock_app.config.get.return_value = 5  # timeout
        mock_app.logger = Mock()
        mock_db.engine.connect.side_effect = SQLTimeoutError("Query timed out", None, None)
        
        # Mock time to simulate timeout (6 seconds > 5 second timeout)
        with patch('time.time', side_effect=[0.0, 6.0]):
            result = HealthService.check_database()
        
        assert result.status == "unhealthy"
        assert result.response_time_ms is None  # Should be None for timeout
        assert "Database connection timeout after 5s" in result.error
        
        # Verify logging
        mock_app.logger.warning.assert_called_once()

    @patch('app.services.health_service.db')
    @patch('app.services.health_service.current_app')
    def test_check_database_authentication_error(self, mock_app, mock_db):
        """Test database connectivity check when authentication fails."""
        # Setup mocks
        mock_app.config.get.return_value = 5  # timeout
        mock_app.logger = Mock()
        mock_db.engine.connect.side_effect = Exception("authentication failed for user")
        
        # Mock time to control response time calculation
        with patch('time.time', side_effect=[0.0, 0.2]):  # 200ms response time
            result = HealthService.check_database()
        
        assert result.status == "unhealthy"
        assert result.response_time_ms == 200
        assert "Database authentication failed" in result.error
        
        # Verify logging
        mock_app.logger.warning.assert_called_once()

    @patch('app.services.health_service.db')
    @patch('app.services.health_service.current_app')
    def test_check_database_generic_error(self, mock_app, mock_db):
        """Test database connectivity check with generic error."""
        # Setup mocks
        mock_app.config.get.return_value = 5  # timeout
        mock_app.logger = Mock()
        mock_db.engine.connect.side_effect = Exception("Some other database error")
        
        # Mock time to control response time calculation
        with patch('time.time', side_effect=[0.0, 0.3]):  # 300ms response time
            result = HealthService.check_database()
        
        assert result.status == "unhealthy"
        assert result.response_time_ms == 300
        assert "Database error: Some other database error" in result.error
        
        # Verify logging
        mock_app.logger.warning.assert_called_once()

    @patch('app.services.health_service.db')
    @patch('app.services.health_service.current_app')
    def test_check_database_uses_config_timeout(self, mock_app, mock_db):
        """Test that database check uses configured timeout value."""
        # Setup mocks with custom timeout
        mock_app.config.get.return_value = 10  # 10 second timeout
        mock_connection = Mock()
        mock_db.engine.connect.return_value.__enter__.return_value = mock_connection
        
        with patch('time.time', side_effect=[0.0, 0.05]):
            HealthService.check_database()
        
        # Verify timeout was used in SQL statement
        mock_connection.execute.assert_any_call(
            unittest.mock.ANY  # The SET statement_timeout call
        )


class TestRedisHealthCheck:
    """Unit tests for Redis health check functionality."""

    @patch('app.services.health_service.redis')
    @patch('app.services.health_service.current_app')
    def test_check_redis_healthy(self, mock_app, mock_redis_module):
        """Test Redis connectivity check when Redis is healthy."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_TIMEOUT': 5,
            'REDIS_URL': 'redis://localhost:6379/0'
        }.get(key, default)
        
        mock_redis_client = Mock()
        mock_redis_module.from_url.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        # Mock time to control response time calculation
        with patch('time.time', side_effect=[0.0, 0.025]):  # 25ms response time
            result = HealthService.check_redis()
        
        assert result.status == "healthy"
        assert result.response_time_ms == 25
        assert result.error is None
        
        # Verify Redis client creation and ping
        mock_redis_module.from_url.assert_called_once_with(
            'redis://localhost:6379/0',
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=30,
            retry_on_timeout=False,
            retry_on_error=[]
        )
        mock_redis_client.ping.assert_called_once()

    @patch('app.services.health_service.redis')
    @patch('app.services.health_service.current_app')
    def test_check_redis_timeout_error(self, mock_app, mock_redis_module):
        """Test Redis connectivity check when timeout occurs."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_TIMEOUT': 5,
            'REDIS_URL': 'redis://localhost:6379/0'
        }.get(key, default)
        mock_app.logger = Mock()
        
        mock_redis_client = Mock()
        mock_redis_module.from_url.return_value = mock_redis_client
        mock_redis_client.ping.side_effect = redis.TimeoutError("Connection timed out")
        
        # Mock time to simulate timeout (6 seconds > 5 second timeout)
        with patch('time.time', side_effect=[0.0, 6.0]):
            result = HealthService.check_redis()
        
        assert result.status == "unhealthy"
        assert result.response_time_ms is None  # Should be None for timeout
        assert "Redis connection timeout after 5s" in result.error
        
        # Verify logging
        mock_app.logger.warning.assert_called_once()

    @patch('app.services.health_service.redis')
    @patch('app.services.health_service.current_app')
    def test_check_redis_connection_error(self, mock_app, mock_redis_module):
        """Test Redis connectivity check when connection fails."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_TIMEOUT': 5,
            'REDIS_URL': 'redis://localhost:6379/0'
        }.get(key, default)
        mock_app.logger = Mock()
        
        mock_redis_client = Mock()
        mock_redis_module.from_url.return_value = mock_redis_client
        mock_redis_client.ping.side_effect = redis.ConnectionError("Connection refused")
        
        # Mock time to control response time calculation
        with patch('time.time', side_effect=[0.0, 0.1]):  # 100ms response time
            result = HealthService.check_redis()
        
        assert result.status == "unhealthy"
        assert result.response_time_ms == 100
        assert "Redis connection failed" in result.error
        
        # Verify logging
        mock_app.logger.warning.assert_called_once()

    @patch('app.services.health_service.redis')
    @patch('app.services.health_service.current_app')
    def test_check_redis_authentication_error(self, mock_app, mock_redis_module):
        """Test Redis connectivity check when authentication fails."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_TIMEOUT': 5,
            'REDIS_URL': 'redis://localhost:6379/0'
        }.get(key, default)
        mock_app.logger = Mock()
        
        mock_redis_client = Mock()
        mock_redis_module.from_url.return_value = mock_redis_client
        mock_redis_client.ping.side_effect = redis.AuthenticationError("Authentication failed")
        
        # Mock time to control response time calculation
        with patch('time.time', side_effect=[0.0, 0.05]):  # 50ms response time
            result = HealthService.check_redis()
        
        assert result.status == "unhealthy"
        assert result.response_time_ms == 50
        assert "Redis authentication failed" in result.error
        
        # Verify logging
        mock_app.logger.warning.assert_called_once()

    @patch('app.services.health_service.redis')
    @patch('app.services.health_service.current_app')
    def test_check_redis_generic_error(self, mock_app, mock_redis_module):
        """Test Redis connectivity check with generic error."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_TIMEOUT': 5,
            'REDIS_URL': 'redis://localhost:6379/0'
        }.get(key, default)
        mock_app.logger = Mock()
        
        mock_redis_client = Mock()
        mock_redis_module.from_url.return_value = mock_redis_client
        mock_redis_client.ping.side_effect = Exception("Some Redis error")
        
        # Mock time to control response time calculation
        with patch('time.time', side_effect=[0.0, 0.2]):  # 200ms response time
            result = HealthService.check_redis()
        
        assert result.status == "unhealthy"
        assert result.response_time_ms == 200
        assert "Redis error: Some Redis error" in result.error
        
        # Verify logging
        mock_app.logger.warning.assert_called_once()


class TestOverallHealthAggregation:
    """Unit tests for overall health aggregation logic."""

    @patch('app.services.health_service.HealthService.check_database')
    @patch('app.services.health_service.HealthService.check_redis')
    @patch('app.services.health_service.datetime')
    @patch('app.services.health_service.current_app')
    def test_get_overall_health_all_healthy(self, mock_app, mock_datetime, mock_check_redis, mock_check_database):
        """Test overall health when all services are healthy."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_DATABASE_ENABLED': True,
            'HEALTH_CHECK_REDIS_ENABLED': True
        }.get(key, default)
        
        mock_datetime.utcnow.return_value.isoformat.return_value = "2025-08-10T22:48:26"
        
        mock_check_database.return_value = HealthCheckResult("healthy", 50)
        mock_check_redis.return_value = HealthCheckResult("healthy", 25)
        
        result = HealthService.get_overall_health()
        
        assert result.status == "healthy"
        assert len(result.checks) == 2
        assert result.checks['database'].status == "healthy"
        assert result.checks['redis'].status == "healthy"
        assert result.timestamp == "2025-08-10T22:48:26Z"

    @patch('app.services.health_service.HealthService.check_database')
    @patch('app.services.health_service.HealthService.check_redis')
    @patch('app.services.health_service.datetime')
    @patch('app.services.health_service.current_app')
    def test_get_overall_health_database_unhealthy(self, mock_app, mock_datetime, mock_check_redis, mock_check_database):
        """Test overall health when database is unhealthy."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_DATABASE_ENABLED': True,
            'HEALTH_CHECK_REDIS_ENABLED': True
        }.get(key, default)
        mock_app.logger = Mock()
        
        mock_datetime.utcnow.return_value.isoformat.return_value = "2025-08-10T22:48:26"
        
        mock_check_database.return_value = HealthCheckResult("unhealthy", None, "Connection failed")
        mock_check_redis.return_value = HealthCheckResult("healthy", 25)
        
        result = HealthService.get_overall_health()
        
        assert result.status == "unhealthy"  # Database failure makes overall unhealthy
        assert len(result.checks) == 2
        assert result.checks['database'].status == "unhealthy"
        assert result.checks['redis'].status == "healthy"
        
        # Verify error logging for database
        mock_app.logger.error.assert_called_once()

    @patch('app.services.health_service.HealthService.check_database')
    @patch('app.services.health_service.HealthService.check_redis')
    @patch('app.services.health_service.datetime')
    @patch('app.services.health_service.current_app')
    def test_get_overall_health_redis_unhealthy(self, mock_app, mock_datetime, mock_check_redis, mock_check_database):
        """Test overall health when Redis is unhealthy (should still be healthy overall)."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_DATABASE_ENABLED': True,
            'HEALTH_CHECK_REDIS_ENABLED': True
        }.get(key, default)
        mock_app.logger = Mock()
        
        mock_datetime.utcnow.return_value.isoformat.return_value = "2025-08-10T22:48:26"
        
        mock_check_database.return_value = HealthCheckResult("healthy", 50)
        mock_check_redis.return_value = HealthCheckResult("unhealthy", None, "Connection failed")
        
        result = HealthService.get_overall_health()
        
        # Per requirement 1.5: Redis failure should still return healthy overall status
        assert result.status == "healthy"
        assert len(result.checks) == 2
        assert result.checks['database'].status == "healthy"
        assert result.checks['redis'].status == "unhealthy"
        
        # Verify warning logging for Redis
        mock_app.logger.warning.assert_called_once()

    @patch('app.services.health_service.HealthService.check_database')
    @patch('app.services.health_service.datetime')
    @patch('app.services.health_service.current_app')
    def test_get_overall_health_database_disabled(self, mock_app, mock_datetime, mock_check_database):
        """Test overall health when database check is disabled."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_DATABASE_ENABLED': False,
            'HEALTH_CHECK_REDIS_ENABLED': False
        }.get(key, default)
        mock_app.logger = Mock()
        
        mock_datetime.utcnow.return_value.isoformat.return_value = "2025-08-10T22:48:26"
        
        result = HealthService.get_overall_health()
        
        assert result.status == "unhealthy"  # No checks performed
        assert len(result.checks) == 0
        
        # Verify error logging for no checks
        mock_app.logger.error.assert_called_once_with("No health checks were performed - all checks disabled")
        
        # Database check should not have been called
        mock_check_database.assert_not_called()

    @patch('app.services.health_service.HealthService.check_database')
    @patch('app.services.health_service.HealthService.check_redis')
    @patch('app.services.health_service.datetime')
    @patch('app.services.health_service.current_app')
    def test_get_overall_health_service_exception(self, mock_app, mock_datetime, mock_check_redis, mock_check_database):
        """Test overall health when health check service itself fails."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_DATABASE_ENABLED': True,
            'HEALTH_CHECK_REDIS_ENABLED': True
        }.get(key, default)
        mock_app.logger = Mock()
        
        mock_datetime.utcnow.return_value.isoformat.return_value = "2025-08-10T22:48:26"
        
        # Database check raises exception
        mock_check_database.side_effect = Exception("Health check service failed")
        mock_check_redis.return_value = HealthCheckResult("healthy", 25)
        
        result = HealthService.get_overall_health()
        
        assert result.status == "unhealthy"  # Service failure makes overall unhealthy
        assert len(result.checks) == 2
        assert result.checks['database'].status == "unhealthy"
        assert result.checks['database'].error == "Health check service failed"
        assert result.checks['redis'].status == "healthy"
        
        # Verify error logging for service failure
        mock_app.logger.error.assert_called_once()

    @patch('app.services.health_service.HealthService.check_database')
    @patch('app.services.health_service.HealthService.check_redis')
    @patch('app.services.health_service.datetime')
    @patch('app.services.health_service.current_app')
    def test_get_overall_health_redis_service_exception(self, mock_app, mock_datetime, mock_check_redis, mock_check_database):
        """Test overall health when Redis health check service fails."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_DATABASE_ENABLED': True,
            'HEALTH_CHECK_REDIS_ENABLED': True
        }.get(key, default)
        mock_app.logger = Mock()
        
        mock_datetime.utcnow.return_value.isoformat.return_value = "2025-08-10T22:48:26"
        
        mock_check_database.return_value = HealthCheckResult("healthy", 50)
        # Redis check raises exception
        mock_check_redis.side_effect = Exception("Redis health check service failed")
        
        result = HealthService.get_overall_health()
        
        # Should still be healthy overall since Redis failure doesn't affect overall status
        assert result.status == "healthy"
        assert len(result.checks) == 2
        assert result.checks['database'].status == "healthy"
        assert result.checks['redis'].status == "unhealthy"
        assert result.checks['redis'].error == "Health check service failed"
        
        # Verify warning logging for Redis service failure
        mock_app.logger.warning.assert_called_once()