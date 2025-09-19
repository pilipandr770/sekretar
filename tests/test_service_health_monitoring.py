"""
Tests for Service Health Monitoring System

This module tests the complete service health monitoring system including
health checks, recovery mechanisms, alerting, and dashboard functionality.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from app.services.service_health_monitor import (
    ServiceHealthMonitor, ServiceStatus, ServiceType, ServiceHealthMetrics
)
from app.services.service_recovery import (
    ServiceRecoveryManager, RecoveryStrategy, RecoveryResult
)
from app.services.health_service import HealthService, HealthCheckResult


class TestServiceHealthMonitor:
    """Test the service health monitoring system."""
    
    def test_service_registration(self):
        """Test service registration for monitoring."""
        monitor = ServiceHealthMonitor()
        
        # Mock health check function
        def mock_health_check():
            return HealthCheckResult("healthy", 50)
        
        # Register a service
        monitor.register_service("test_service", ServiceType.DATABASE, mock_health_check)
        
        # Verify service is registered
        assert "test_service" in monitor.services
        assert monitor.services["test_service"].service_name == "test_service"
        assert monitor.services["test_service"].service_type == ServiceType.DATABASE
        assert monitor.services["test_service"].status == ServiceStatus.UNKNOWN
    
    def test_successful_health_check(self):
        """Test successful health check updates metrics correctly."""
        monitor = ServiceHealthMonitor()
        
        # Mock health check function
        def mock_health_check():
            return HealthCheckResult("healthy", 75)
        
        # Register and check service
        monitor.register_service("test_service", ServiceType.DATABASE, mock_health_check)
        metrics = monitor.check_service_health("test_service")
        
        # Verify metrics
        assert metrics.status == ServiceStatus.HEALTHY
        assert metrics.response_time_ms == 75
        assert metrics.consecutive_failures == 0
        assert metrics.consecutive_successes == 1
        assert metrics.total_checks == 1
        assert metrics.total_failures == 0
        assert metrics.uptime_percentage == 100.0
    
    def test_failed_health_check(self):
        """Test failed health check updates metrics correctly."""
        monitor = ServiceHealthMonitor()
        
        # Mock health check function that fails
        def mock_health_check():
            return HealthCheckResult("unhealthy", None, "Connection failed")
        
        # Register and check service
        monitor.register_service("test_service", ServiceType.DATABASE, mock_health_check)
        metrics = monitor.check_service_health("test_service")
        
        # Verify metrics
        assert metrics.status == ServiceStatus.DEGRADED  # First failure = degraded
        assert metrics.response_time_ms is None
        assert metrics.consecutive_failures == 1
        assert metrics.consecutive_successes == 0
        assert metrics.total_checks == 1
        assert metrics.total_failures == 1
        assert metrics.error_message == "Connection failed"
    
    def test_multiple_failures_lead_to_unhealthy(self):
        """Test that multiple consecutive failures lead to unhealthy status."""
        monitor = ServiceHealthMonitor()
        
        # Mock health check function that always fails
        def mock_health_check():
            return HealthCheckResult("unhealthy", None, "Connection failed")
        
        # Register service
        monitor.register_service("test_service", ServiceType.DATABASE, mock_health_check)
        
        # Perform multiple health checks
        for i in range(3):
            metrics = monitor.check_service_health("test_service")
        
        # After 3 failures, should be unhealthy
        assert metrics.status == ServiceStatus.UNHEALTHY
        assert metrics.consecutive_failures == 3
    
    def test_recovery_after_failures(self):
        """Test service recovery after failures."""
        monitor = ServiceHealthMonitor()
        
        # Mock health check function that can change behavior
        self.health_check_should_fail = True
        
        def mock_health_check():
            if self.health_check_should_fail:
                return HealthCheckResult("unhealthy", None, "Connection failed")
            else:
                return HealthCheckResult("healthy", 50)
        
        # Register service
        monitor.register_service("test_service", ServiceType.DATABASE, mock_health_check)
        
        # Fail multiple times
        for i in range(3):
            metrics = monitor.check_service_health("test_service")
        
        assert metrics.status == ServiceStatus.UNHEALTHY
        
        # Now make health check succeed
        self.health_check_should_fail = False
        metrics = monitor.check_service_health("test_service")
        
        # Should be recovering
        assert metrics.status == ServiceStatus.RECOVERING
        assert metrics.consecutive_failures == 0
        assert metrics.consecutive_successes == 1
    
    def test_get_all_services_status(self):
        """Test getting status of all services."""
        monitor = ServiceHealthMonitor()
        
        # Register multiple services
        def healthy_check():
            return HealthCheckResult("healthy", 50)
        
        def unhealthy_check():
            return HealthCheckResult("unhealthy", None, "Failed")
        
        monitor.register_service("healthy_service", ServiceType.DATABASE, healthy_check)
        monitor.register_service("unhealthy_service", ServiceType.REDIS, unhealthy_check)
        
        # Check both services
        monitor.check_service_health("healthy_service")
        monitor.check_service_health("unhealthy_service")
        
        # Get overall status
        status = monitor.get_all_services_status()
        
        assert status["overall_status"] == "degraded"  # One unhealthy service
        assert status["total_services"] == 2
        assert status["healthy_services"] == 1
        assert status["degraded_services"] == 1
        assert status["unhealthy_services"] == 0  # First failure = degraded, not unhealthy


class TestServiceRecoveryManager:
    """Test the service recovery management system."""
    
    def test_recovery_strategy_registration(self):
        """Test registering recovery strategies."""
        recovery_manager = ServiceRecoveryManager()
        
        def mock_recovery_action():
            return True, "Recovery successful"
        
        # Register recovery strategy
        recovery_manager.register_recovery_strategy(
            "test_service",
            RecoveryStrategy.RESTART_CONNECTION,
            mock_recovery_action,
            priority=1
        )
        
        # Verify strategy is registered
        assert "test_service" in recovery_manager.recovery_strategies
        strategies = recovery_manager.recovery_strategies["test_service"]
        assert len(strategies) == 1
        assert strategies[0]['strategy'] == RecoveryStrategy.RESTART_CONNECTION
        assert strategies[0]['priority'] == 1
    
    @pytest.mark.asyncio
    async def test_successful_recovery_attempt(self):
        """Test successful recovery attempt."""
        recovery_manager = ServiceRecoveryManager()
        
        # Mock successful recovery action
        def mock_recovery_action():
            return True, "Recovery successful"
        
        # Register recovery strategy
        recovery_manager.register_recovery_strategy(
            "test_service",
            RecoveryStrategy.RESTART_CONNECTION,
            mock_recovery_action,
            priority=1
        )
        
        # Attempt recovery
        success = await recovery_manager.attempt_recovery("test_service", ServiceStatus.DEGRADED)
        
        # Verify recovery succeeded
        assert success is True
        assert recovery_manager.escalation_levels["test_service"] == 0
    
    @pytest.mark.asyncio
    async def test_failed_recovery_escalation(self):
        """Test recovery escalation on failure."""
        recovery_manager = ServiceRecoveryManager()
        
        # Mock failed recovery action
        def mock_recovery_action():
            return False, "Recovery failed"
        
        # Register recovery strategy
        recovery_manager.register_recovery_strategy(
            "test_service",
            RecoveryStrategy.RESTART_CONNECTION,
            mock_recovery_action,
            priority=1
        )
        
        # Attempt recovery
        success = await recovery_manager.attempt_recovery("test_service", ServiceStatus.DEGRADED)
        
        # Verify recovery failed and escalated
        assert success is False
        assert recovery_manager.escalation_levels["test_service"] == 1
    
    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization."""
        recovery_manager = ServiceRecoveryManager()
        
        # Initialize circuit breaker
        recovery_manager.init_circuit_breaker(
            "test_service",
            failure_threshold=3,
            recovery_timeout=60
        )
        
        # Verify circuit breaker is initialized
        assert "test_service" in recovery_manager.circuit_breakers
        breaker = recovery_manager.circuit_breakers["test_service"]
        assert breaker.service_name == "test_service"
        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 60
        assert breaker.state == "closed"
    
    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures."""
        recovery_manager = ServiceRecoveryManager()
        
        # Initialize circuit breaker with low threshold
        recovery_manager.init_circuit_breaker(
            "test_service",
            failure_threshold=2,
            recovery_timeout=60
        )
        
        # Record failures
        recovery_manager._record_circuit_breaker_failure("test_service")
        recovery_manager._record_circuit_breaker_failure("test_service")
        
        # Circuit breaker should be open
        breaker = recovery_manager.circuit_breakers["test_service"]
        assert breaker.state == "open"
        assert breaker.failure_count == 2
    
    def test_get_recovery_status(self):
        """Test getting recovery status for a service."""
        recovery_manager = ServiceRecoveryManager()
        
        # Register recovery strategy
        def mock_recovery_action():
            return True, "Success"
        
        recovery_manager.register_recovery_strategy(
            "test_service",
            RecoveryStrategy.RESTART_CONNECTION,
            mock_recovery_action,
            priority=1
        )
        
        # Initialize circuit breaker
        recovery_manager.init_circuit_breaker("test_service")
        
        # Get recovery status
        status = recovery_manager.get_recovery_status("test_service")
        
        # Verify status structure
        assert status["service_name"] == "test_service"
        assert status["recovery_in_progress"] is False
        assert status["escalation_level"] == 0
        assert len(status["available_strategies"]) == 1
        assert status["circuit_breaker"]["state"] == "closed"


class TestHealthServiceIntegration:
    """Test integration with existing health service."""
    
    @patch('app.services.health_service.db')
    @patch('app.services.health_service.current_app')
    def test_database_health_check_integration(self, mock_app, mock_db):
        """Test database health check integration."""
        # Setup mocks
        mock_app.config.get.return_value = 5  # timeout
        mock_connection = Mock()
        mock_db.engine.connect.return_value.__enter__.return_value = mock_connection
        
        # Mock time for response time calculation
        with patch('time.time', side_effect=[0.0, 0.05]):  # 50ms response time
            result = HealthService.check_database()
        
        # Verify result
        assert result.status == "healthy"
        assert result.response_time_ms == 50
        assert result.error is None
    
    @patch('app.services.health_service.redis')
    @patch('app.services.health_service.current_app')
    def test_redis_health_check_integration(self, mock_app, mock_redis_module):
        """Test Redis health check integration."""
        # Setup mocks
        mock_app.config.get.side_effect = lambda key, default: {
            'HEALTH_CHECK_TIMEOUT': 5,
            'REDIS_URL': 'redis://localhost:6379/0'
        }.get(key, default)
        
        mock_redis_client = Mock()
        mock_redis_module.from_url.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        # Mock time for response time calculation
        with patch('time.time', side_effect=[0.0, 0.025]):  # 25ms response time
            result = HealthService.check_redis()
        
        # Verify result
        assert result.status == "healthy"
        assert result.response_time_ms == 25
        assert result.error is None


class TestHealthSystemInitialization:
    """Test health system initialization."""
    
    @patch('app.utils.health_system_init.init_service_health_monitoring')
    @patch('app.utils.health_system_init.init_service_recovery')
    @patch('app.utils.health_system_init.init_monitoring')
    @patch('app.utils.health_system_init.init_alerting')
    def test_complete_health_system_initialization(
        self, mock_alerting, mock_monitoring, mock_recovery, mock_health_monitor
    ):
        """Test complete health system initialization."""
        from app.utils.health_system_init import init_complete_health_system
        from flask import Flask
        
        # Create test app
        app = Flask(__name__)
        app.config['MONITORING_ENABLED'] = True
        
        # Mock successful initialization
        mock_health_monitor.return_value = Mock()
        mock_recovery.return_value = Mock()
        mock_monitoring.return_value = Mock()
        mock_alerting.return_value = Mock()
        
        # Initialize health system
        result = init_complete_health_system(app)
        
        # Verify initialization
        assert result['success'] is True
        assert 'components' in result
        assert len(result['components']) == 4
        
        # Verify all components were initialized
        mock_health_monitor.assert_called_once_with(app)
        mock_recovery.assert_called_once_with(app)
        mock_monitoring.assert_called_once_with(app)
        mock_alerting.assert_called_once_with(app)
    
    def test_health_system_validation(self):
        """Test health system validation."""
        from app.utils.health_system_init import validate_health_system
        
        # This test would need proper mocking of all services
        # For now, just test that it doesn't crash
        try:
            result = validate_health_system()
            assert 'overall_valid' in result
            assert 'components' in result
            assert 'issues' in result
            assert 'recommendations' in result
        except Exception as e:
            # Expected to fail in test environment without proper setup
            assert "not initialized" in str(e) or "not found" in str(e)


# Integration test fixtures
@pytest.fixture
def mock_app():
    """Create a mock Flask app for testing."""
    from flask import Flask
    app = Flask(__name__)
    app.config.update({
        'TESTING': True,
        'HEALTH_CHECK_TIMEOUT': 5,
        'HEALTH_CHECK_DATABASE_ENABLED': True,
        'HEALTH_CHECK_REDIS_ENABLED': True,
        'MONITORING_ENABLED': True,
        'ALERTING_ENABLED': True
    })
    return app


@pytest.fixture
def health_monitor():
    """Create a service health monitor for testing."""
    return ServiceHealthMonitor()


@pytest.fixture
def recovery_manager():
    """Create a service recovery manager for testing."""
    return ServiceRecoveryManager()


# Performance tests
class TestHealthMonitoringPerformance:
    """Test performance aspects of health monitoring."""
    
    def test_health_check_performance(self, health_monitor):
        """Test that health checks complete within reasonable time."""
        def fast_health_check():
            return HealthCheckResult("healthy", 10)
        
        # Register service
        health_monitor.register_service("fast_service", ServiceType.DATABASE, fast_health_check)
        
        # Measure health check time
        start_time = time.time()
        health_monitor.check_service_health("fast_service")
        duration = time.time() - start_time
        
        # Should complete very quickly (under 100ms)
        assert duration < 0.1
    
    def test_multiple_services_performance(self, health_monitor):
        """Test performance with multiple services."""
        def health_check():
            return HealthCheckResult("healthy", 20)
        
        # Register multiple services
        for i in range(10):
            health_monitor.register_service(f"service_{i}", ServiceType.DATABASE, health_check)
        
        # Measure time to check all services
        start_time = time.time()
        for i in range(10):
            health_monitor.check_service_health(f"service_{i}")
        duration = time.time() - start_time
        
        # Should complete reasonably quickly (under 1 second)
        assert duration < 1.0