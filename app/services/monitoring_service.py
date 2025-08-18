"""Monitoring and metrics collection service."""
import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import redis
from flask import current_app, g, request
from sqlalchemy import text
from app import db
import structlog

logger = structlog.get_logger()


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: float
    value: float
    labels: Dict[str, str] = None
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = {}


@dataclass
class SystemMetrics:
    """System-level metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    load_average: Optional[List[float]]
    timestamp: float


@dataclass
class ApplicationMetrics:
    """Application-level metrics."""
    active_connections: int
    request_count: int
    error_count: int
    response_time_avg: float
    response_time_p95: float
    response_time_p99: float
    database_connections: int
    redis_connections: int
    celery_active_tasks: int
    timestamp: float


class MetricsCollector:
    """Collects and stores application metrics."""
    
    def __init__(self, redis_client: redis.Redis = None):
        self.redis = redis_client
        self.metrics_buffer = defaultdict(lambda: deque(maxlen=1000))
        self.response_times = deque(maxlen=10000)  # Store last 10k response times
        self.request_count = 0
        self.error_count = 0
        self.lock = threading.Lock()
    
    def record_request(self, response_time_ms: float, status_code: int, endpoint: str = None):
        """Record a request with response time and status."""
        with self.lock:
            self.request_count += 1
            self.response_times.append(response_time_ms)
            
            if status_code >= 400:
                self.error_count += 1
            
            # Store in Redis if available
            if self.redis:
                try:
                    timestamp = time.time()
                    metric_key = f"metrics:requests:{int(timestamp // 60)}"  # Per minute
                    
                    pipeline = self.redis.pipeline()
                    pipeline.hincrby(metric_key, "count", 1)
                    pipeline.hincrby(metric_key, f"status_{status_code}", 1)
                    pipeline.expire(metric_key, 3600)  # Keep for 1 hour
                    
                    if endpoint:
                        endpoint_key = f"metrics:endpoints:{endpoint}:{int(timestamp // 60)}"
                        pipeline.hincrby(endpoint_key, "count", 1)
                        pipeline.hincrby(endpoint_key, "response_time_total", int(response_time_ms))
                        pipeline.expire(endpoint_key, 3600)
                    
                    pipeline.execute()
                    
                except Exception as e:
                    logger.warning("Failed to store request metrics", error=str(e))
    
    def record_error(self, error_type: str, endpoint: str = None, details: str = None):
        """Record an error occurrence."""
        with self.lock:
            self.error_count += 1
        
        if self.redis:
            try:
                timestamp = time.time()
                error_key = f"metrics:errors:{int(timestamp // 60)}"
                
                pipeline = self.redis.pipeline()
                pipeline.hincrby(error_key, error_type, 1)
                pipeline.expire(error_key, 3600)
                
                if endpoint:
                    endpoint_error_key = f"metrics:endpoint_errors:{endpoint}:{int(timestamp // 60)}"
                    pipeline.hincrby(endpoint_error_key, error_type, 1)
                    pipeline.expire(endpoint_error_key, 3600)
                
                pipeline.execute()
                
            except Exception as e:
                logger.warning("Failed to store error metrics", error=str(e))
    
    def get_response_time_percentiles(self) -> Dict[str, float]:
        """Calculate response time percentiles."""
        if not self.response_times:
            return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
        
        sorted_times = sorted(self.response_times)
        length = len(sorted_times)
        
        return {
            "avg": sum(sorted_times) / length,
            "p50": sorted_times[int(length * 0.5)],
            "p95": sorted_times[int(length * 0.95)],
            "p99": sorted_times[int(length * 0.99)]
        }
    
    def get_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Load average (Unix-like systems only)
            load_avg = None
            try:
                load_avg = list(psutil.getloadavg())
            except AttributeError:
                # Windows doesn't have load average
                pass
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                memory_available_mb=memory.available / (1024 * 1024),
                disk_usage_percent=disk.percent,
                disk_free_gb=disk.free / (1024 * 1024 * 1024),
                load_average=load_avg,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error("Failed to collect system metrics", error=str(e))
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                disk_free_gb=0.0,
                load_average=None,
                timestamp=time.time()
            )
    
    def get_application_metrics(self) -> ApplicationMetrics:
        """Collect current application metrics."""
        try:
            # Database connections
            db_connections = 0
            try:
                with db.engine.connect() as conn:
                    result = conn.execute(text("SELECT count(*) FROM pg_stat_activity"))
                    db_connections = result.scalar()
            except Exception:
                pass
            
            # Redis connections (approximate)
            redis_connections = 0
            if self.redis:
                try:
                    info = self.redis.info()
                    redis_connections = info.get('connected_clients', 0)
                except Exception:
                    pass
            
            # Response time metrics
            response_metrics = self.get_response_time_percentiles()
            
            return ApplicationMetrics(
                active_connections=0,  # Would need to track WebSocket connections
                request_count=self.request_count,
                error_count=self.error_count,
                response_time_avg=response_metrics["avg"],
                response_time_p95=response_metrics["p95"],
                response_time_p99=response_metrics["p99"],
                database_connections=db_connections,
                redis_connections=redis_connections,
                celery_active_tasks=0,  # Would need Celery integration
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error("Failed to collect application metrics", error=str(e))
            return ApplicationMetrics(
                active_connections=0,
                request_count=self.request_count,
                error_count=self.error_count,
                response_time_avg=0.0,
                response_time_p95=0.0,
                response_time_p99=0.0,
                database_connections=0,
                redis_connections=0,
                celery_active_tasks=0,
                timestamp=time.time()
            )


class MonitoringService:
    """Main monitoring service for collecting and exposing metrics."""
    
    def __init__(self):
        self.metrics_collector = None
        self.redis_client = None
        self._initialized = False
    
    def init_app(self, app):
        """Initialize monitoring service with Flask app."""
        try:
            # Initialize Redis client for metrics storage
            redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url)
            
            # Initialize metrics collector
            self.metrics_collector = MetricsCollector(self.redis_client)
            
            # Set up request monitoring middleware
            self._setup_request_monitoring(app)
            
            self._initialized = True
            logger.info("Monitoring service initialized")
            
        except Exception as e:
            logger.error("Failed to initialize monitoring service", error=str(e))
    
    def _setup_request_monitoring(self, app):
        """Set up request monitoring middleware."""
        
        @app.before_request
        def before_request():
            """Record request start time."""
            g.start_time = time.time()
        
        @app.after_request
        def after_request(response):
            """Record request completion and metrics."""
            if hasattr(g, 'start_time') and self.metrics_collector:
                response_time_ms = (time.time() - g.start_time) * 1000
                endpoint = request.endpoint or request.path
                
                self.metrics_collector.record_request(
                    response_time_ms=response_time_ms,
                    status_code=response.status_code,
                    endpoint=endpoint
                )
            
            return response
        
        @app.errorhandler(Exception)
        def handle_exception(e):
            """Record application errors."""
            if self.metrics_collector:
                error_type = type(e).__name__
                endpoint = request.endpoint or request.path
                
                self.metrics_collector.record_error(
                    error_type=error_type,
                    endpoint=endpoint,
                    details=str(e)
                )
            
            # Re-raise the exception to let Flask handle it normally
            raise e
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        if not self._initialized or not self.metrics_collector:
            return {"error": "Monitoring service not initialized"}
        
        try:
            system_metrics = self.metrics_collector.get_system_metrics()
            app_metrics = self.metrics_collector.get_application_metrics()
            
            return {
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "system": asdict(system_metrics),
                "application": asdict(app_metrics),
                "health_status": self._get_health_status(system_metrics, app_metrics)
            }
            
        except Exception as e:
            logger.error("Failed to get metrics summary", error=str(e))
            return {"error": str(e)}
    
    def _get_health_status(self, system_metrics: SystemMetrics, app_metrics: ApplicationMetrics) -> str:
        """Determine overall health status based on metrics."""
        # Check for critical issues
        if system_metrics.cpu_percent > 90:
            return "critical"
        
        if system_metrics.memory_percent > 90:
            return "critical"
        
        if system_metrics.disk_usage_percent > 95:
            return "critical"
        
        # Check for warnings
        if (system_metrics.cpu_percent > 70 or 
            system_metrics.memory_percent > 70 or
            app_metrics.response_time_p95 > 5000):  # 5 second response time
            return "warning"
        
        return "healthy"
    
    def get_endpoint_metrics(self, endpoint: str, minutes: int = 60) -> Dict[str, Any]:
        """Get metrics for a specific endpoint."""
        if not self.redis_client:
            return {"error": "Redis not available"}
        
        try:
            current_time = int(time.time() // 60)
            metrics = {
                "endpoint": endpoint,
                "timeframe_minutes": minutes,
                "total_requests": 0,
                "total_response_time": 0,
                "avg_response_time": 0.0,
                "request_rate": 0.0
            }
            
            for i in range(minutes):
                minute_key = f"metrics:endpoints:{endpoint}:{current_time - i}"
                minute_data = self.redis_client.hgetall(minute_key)
                
                if minute_data:
                    count = int(minute_data.get(b'count', 0))
                    response_time_total = int(minute_data.get(b'response_time_total', 0))
                    
                    metrics["total_requests"] += count
                    metrics["total_response_time"] += response_time_total
            
            if metrics["total_requests"] > 0:
                metrics["avg_response_time"] = metrics["total_response_time"] / metrics["total_requests"]
                metrics["request_rate"] = metrics["total_requests"] / minutes
            
            return metrics
            
        except Exception as e:
            logger.error("Failed to get endpoint metrics", error=str(e), endpoint=endpoint)
            return {"error": str(e)}


# Global monitoring service instance
monitoring_service = MonitoringService()


def init_monitoring(app):
    """Initialize monitoring service."""
    monitoring_service.init_app(app)
    return monitoring_service