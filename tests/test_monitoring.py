"""Tests for monitoring and metrics functionality."""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, g
import redis

from app.services.monitoring_service import (
    MetricsCollector, MonitoringService, SystemMetrics, ApplicationMetrics,
    MetricPoint, monitoring_service, init_monitoring
)


class TestMetricPoint:
    """Test MetricPoint dataclass."""
    
    def test_metric_point_creation(self):
        """Test creating a metric point."""
        point = MetricPoint(timestamp=1234567890, value=42.5)
        
        assert point.timestamp == 1234567890
        assert point.value == 42.5
        assert point.labels == {}
    
    def test_metric_point_with_labels(self):
        """Test creating a metric point with labels."""
        labels = {"endpoint": "/api/v1/test", "method": "GET"}
        point = MetricPoint(timestamp=1234567890, value=42.5, labels=labels)
        
        assert point.labels == labels


class TestMetricsCollector:
    """Test MetricsCollector functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return Mock(spec=redis.Redis)
    
    @pytest.fixture
    def metrics_collector(self, mock_redis):
        """MetricsCollector with mocked Redis."""
        return MetricsCollector(mock_redis)
    
    def test_record_request_success(self, metrics_collector, mock_redis):
        """Test recording a successful request."""
        # Mock Redis pipeline
        mock_pipeline = Mock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        metrics_collector.record_request(
            response_time_ms=150.5,
            status_code=200,
            endpoint="/api/v1/test"
        )
        
        assert metrics_collector.request_count == 1
        assert len(metrics_collector.response_times) == 1
        assert metrics_collector.response_times[0] == 150.5
        assert metrics_collector.error_count == 0
        
        # Verify Redis calls
        mock_redis.pipeline.assert_called_once()
        mock_pipeline.execute.assert_called_once()
    
    def test_record_request_error(self, metrics_collector, mock_redis):
        """Test recording a request with error status."""
        mock_pipeline = Mock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        metrics_collector.record_request(
            response_time_ms=250.0,
            status_code=500,
            endpoint="/api/v1/test"
        )
        
        assert metrics_collector.request_count == 1
        assert metrics_collector.error_count == 1
    
    def test_record_request_redis_failure(self, metrics_collector, mock_redis):
        """Test recording request when Redis fails."""
        mock_redis.pipeline.side_effect = redis.ConnectionError("Redis connection failed")
        
        # Should not raise exception
        metrics_collector.record_request(
            response_time_ms=150.5,
            status_code=200,
            endpoint="/api/v1/test"
        )
        
        assert metrics_collector.request_count == 1
    
    def test_record_error(self, metrics_collector, mock_redis):
        """Test recording an error."""
        mock_pipeline = Mock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        metrics_collector.record_error(
            error_type="ValidationError",
            endpoint="/api/v1/test",
            details="Invalid input"
        )
        
        assert metrics_collector.error_count == 1
        mock_redis.pipeline.assert_called_once()
    
    def test_get_response_time_percentiles_empty(self, metrics_collector):
        """Test getting percentiles with no data."""
        percentiles = metrics_collector.get_response_time_percentiles()
        
        expected = {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
        assert percentiles == expected
    
    def test_get_response_time_percentiles_with_data(self, metrics_collector):
        """Test getting percentiles with data."""
        # Add some response times
        response_times = [100, 150, 200, 250, 300, 400, 500, 600, 700, 1000]
        metrics_collector.response_times.extend(response_times)
        
        percentiles = metrics_collector.get_response_time_percentiles()
        
        assert percentiles["avg"] == 420.0  # Average of the times
        assert percentiles["p50"] == 300  # 50th percentile
        assert percentiles["p95"] == 700  # 95th percentile
        assert percentiles["p99"] == 1000  # 99th percentile
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.getloadavg')
    def test_get_system_metrics(self, mock_loadavg, mock_disk, mock_memory, mock_cpu, metrics_collector):
        """Test collecting system metrics."""
        # Mock system calls
        mock_cpu.return_value = 45.5
        
        mock_memory_obj = Mock()
        mock_memory_obj.percent = 60.2
        mock_memory_obj.used = 8 * 1024 * 1024 * 1024  # 8GB
        mock_memory_obj.available = 8 * 1024 * 1024 * 1024  # 8GB
        mock_memory.return_value = mock_memory_obj
        
        mock_disk_obj = Mock()
        mock_disk_obj.percent = 75.0
        mock_disk_obj.free = 100 * 1024 * 1024 * 1024  # 100GB
        mock_disk.return_value = mock_disk_obj
        
        mock_loadavg.return_value = [1.5, 1.2, 1.0]
        
        metrics = metrics_collector.get_system_metrics()
        
        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent == 45.5
        assert metrics.memory_percent == 60.2
        assert metrics.memory_used_mb == 8192.0  # 8GB in MB
        assert metrics.disk_usage_percent == 75.0
        assert metrics.load_average == [1.5, 1.2, 1.0]
    
    @patch('psutil.cpu_percent')
    def test_get_system_metrics_error(self, mock_cpu, metrics_collector):
        """Test system metrics collection with error."""
        mock_cpu.side_effect = Exception("System error")
        
        metrics = metrics_collector.get_system_metrics()
        
        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent == 0.0
        assert metrics.memory_percent == 0.0
    
    @patch('app.services.monitoring_service.db')
    def test_get_application_metrics(self, mock_db, metrics_collector, mock_redis):
        """Test collecting application metrics."""
        # Mock database connection
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.scalar.return_value = 5
        mock_conn.execute.return_value = mock_result
        mock_db.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock Redis info
        mock_redis.info.return_value = {'connected_clients': 10}
        
        # Add some response times
        metrics_collector.response_times.extend([100, 200, 300])
        metrics_collector.request_count = 100
        metrics_collector.error_count = 5
        
        metrics = metrics_collector.get_application_metrics()
        
        assert isinstance(metrics, ApplicationMetrics)
        assert metrics.request_count == 100
        assert metrics.error_count == 5
        assert metrics.database_connections == 5
        assert metrics.redis_connections == 10
        assert metrics.response_time_avg == 200.0


class TestMonitoringService:
    """Test MonitoringService functionality."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask application."""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['REDIS_URL'] = 'redis://localhost:6379/0'
        return app
    
    @pytest.fixture
    def monitoring_service_instance(self):
        """Create MonitoringService instance."""
        return MonitoringService()
    
    @patch('app.services.monitoring_service.redis.from_url')
    def test_init_app(self, mock_redis_from_url, app, monitoring_service_instance):
        """Test initializing monitoring service with Flask app."""
        mock_redis_client = Mock()
        mock_redis_from_url.return_value = mock_redis_client
        
        monitoring_service_instance.init_app(app)
        
        assert monitoring_service_instance._initialized is True
        assert monitoring_service_instance.redis_client == mock_redis_client
        assert monitoring_service_instance.metrics_collector is not None
    
    def test_init_app_error(self, app, monitoring_service_instance):
        """Test initialization error handling."""
        with patch('app.services.monitoring_service.redis.from_url', side_effect=Exception("Redis error")):
            monitoring_service_instance.init_app(app)
            
            # Should not crash, but not be initialized
            assert monitoring_service_instance._initialized is False
    
    def test_get_metrics_summary_not_initialized(self, monitoring_service_instance):
        """Test getting metrics when service is not initialized."""
        result = monitoring_service_instance.get_metrics_summary()
        
        assert "error" in result
        assert result["error"] == "Monitoring service not initialized"
    
    @patch('app.services.monitoring_service.redis.from_url')
    def test_get_metrics_summary_success(self, mock_redis_from_url, app, monitoring_service_instance):
        """Test getting metrics summary successfully."""
        mock_redis_client = Mock()
        mock_redis_from_url.return_value = mock_redis_client
        
        monitoring_service_instance.init_app(app)
        
        with patch.object(monitoring_service_instance.metrics_collector, 'get_system_metrics') as mock_system:
            with patch.object(monitoring_service_instance.metrics_collector, 'get_application_metrics') as mock_app:
                mock_system.return_value = SystemMetrics(
                    cpu_percent=50.0, memory_percent=60.0, memory_used_mb=4096.0,
                    memory_available_mb=4096.0, disk_usage_percent=70.0,
                    disk_free_gb=100.0, load_average=[1.0, 1.0, 1.0], timestamp=time.time()
                )
                
                mock_app.return_value = ApplicationMetrics(
                    active_connections=10, request_count=100, error_count=5,
                    response_time_avg=200.0, response_time_p95=500.0, response_time_p99=1000.0,
                    database_connections=5, redis_connections=10, celery_active_tasks=0,
                    timestamp=time.time()
                )
                
                result = monitoring_service_instance.get_metrics_summary()
                
                assert "error" not in result
                assert "system" in result
                assert "application" in result
                assert "health_status" in result
                assert "timestamp" in result
    
    def test_get_health_status_healthy(self, monitoring_service_instance):
        """Test health status determination - healthy."""
        system_metrics = SystemMetrics(
            cpu_percent=50.0, memory_percent=60.0, memory_used_mb=4096.0,
            memory_available_mb=4096.0, disk_usage_percent=70.0,
            disk_free_gb=100.0, load_average=[1.0, 1.0, 1.0], timestamp=time.time()
        )
        
        app_metrics = ApplicationMetrics(
            active_connections=10, request_count=100, error_count=5,
            response_time_avg=200.0, response_time_p95=500.0, response_time_p99=1000.0,
            database_connections=5, redis_connections=10, celery_active_tasks=0,
            timestamp=time.time()
        )
        
        status = monitoring_service_instance._get_health_status(system_metrics, app_metrics)
        assert status == "healthy"
    
    def test_get_health_status_critical(self, monitoring_service_instance):
        """Test health status determination - critical."""
        system_metrics = SystemMetrics(
            cpu_percent=95.0, memory_percent=95.0, memory_used_mb=4096.0,
            memory_available_mb=4096.0, disk_usage_percent=98.0,
            disk_free_gb=1.0, load_average=[5.0, 5.0, 5.0], timestamp=time.time()
        )
        
        app_metrics = ApplicationMetrics(
            active_connections=10, request_count=100, error_count=5,
            response_time_avg=200.0, response_time_p95=500.0, response_time_p99=1000.0,
            database_connections=5, redis_connections=10, celery_active_tasks=0,
            timestamp=time.time()
        )
        
        status = monitoring_service_instance._get_health_status(system_metrics, app_metrics)
        assert status == "critical"
    
    def test_get_health_status_warning(self, monitoring_service_instance):
        """Test health status determination - warning."""
        system_metrics = SystemMetrics(
            cpu_percent=75.0, memory_percent=75.0, memory_used_mb=4096.0,
            memory_available_mb=4096.0, disk_usage_percent=80.0,
            disk_free_gb=50.0, load_average=[2.0, 2.0, 2.0], timestamp=time.time()
        )
        
        app_metrics = ApplicationMetrics(
            active_connections=10, request_count=100, error_count=5,
            response_time_avg=200.0, response_time_p95=6000.0, response_time_p99=8000.0,
            database_connections=5, redis_connections=10, celery_active_tasks=0,
            timestamp=time.time()
        )
        
        status = monitoring_service_instance._get_health_status(system_metrics, app_metrics)
        assert status == "warning"
    
    @patch('app.services.monitoring_service.redis.from_url')
    def test_get_endpoint_metrics(self, mock_redis_from_url, app, monitoring_service_instance):
        """Test getting endpoint-specific metrics."""
        mock_redis_client = Mock()
        mock_redis_from_url.return_value = mock_redis_client
        
        monitoring_service_instance.init_app(app)
        
        # Mock Redis data
        mock_redis_client.hgetall.return_value = {
            b'count': b'10',
            b'response_time_total': b'2000'
        }
        
        result = monitoring_service_instance.get_endpoint_metrics("/api/v1/test", 60)
        
        assert result["endpoint"] == "/api/v1/test"
        assert result["timeframe_minutes"] == 60
        assert result["total_requests"] == 600  # 10 requests * 60 minutes
        assert result["avg_response_time"] == 200.0  # 2000 / 10
    
    def test_get_endpoint_metrics_no_redis(self, monitoring_service_instance):
        """Test getting endpoint metrics when Redis is not available."""
        result = monitoring_service_instance.get_endpoint_metrics("/api/v1/test", 60)
        
        assert "error" in result
        assert result["error"] == "Redis not available"


class TestInitMonitoring:
    """Test monitoring initialization function."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask application."""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['REDIS_URL'] = 'redis://localhost:6379/0'
        return app
    
    @patch('app.services.monitoring_service.redis.from_url')
    def test_init_monitoring(self, mock_redis_from_url, app):
        """Test monitoring initialization function."""
        mock_redis_client = Mock()
        mock_redis_from_url.return_value = mock_redis_client
        
        result = init_monitoring(app)
        
        assert result == monitoring_service
        assert monitoring_service._initialized is True


class TestMonitoringMiddleware:
    """Test monitoring middleware functionality."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask application with monitoring."""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['REDIS_URL'] = 'redis://localhost:6379/0'
        
        @app.route('/test')
        def test_endpoint():
            return "test response"
        
        return app
    
    @patch('app.services.monitoring_service.redis.from_url')
    def test_request_monitoring_middleware(self, mock_redis_from_url, app):
        """Test that request monitoring middleware works."""
        mock_redis_client = Mock()
        mock_redis_from_url.return_value = mock_redis_client
        
        # Initialize monitoring
        init_monitoring(app)
        
        with app.test_client() as client:
            response = client.get('/test')
            
            assert response.status_code == 200
            # Verify that metrics were recorded
            assert monitoring_service.metrics_collector.request_count > 0