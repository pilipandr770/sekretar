"""Performance monitoring utilities."""
import time
import logging
import psutil
import threading
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, Optional, List
from flask import request, g, current_app
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.models.performance import PerformanceMetric, SlowQuery, ServiceHealth, PerformanceAlert
from app.utils.application_context_manager import get_context_manager, with_app_context, safe_context


logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Main performance monitoring class."""
    
    def __init__(self, app=None):
        self.app = app
        self.request_start_time = None
        self.db_query_count = 0
        self.db_query_time = 0.0
        self.cache_hits = 0
        self.cache_misses = 0
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize performance monitoring for Flask app."""
        self.app = app
        
        # Register request hooks
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        
        # Register database event listeners
        self._setup_db_monitoring()
        
        # Start background monitoring
        if app.config.get('MONITORING_ENABLED', True):
            self._start_background_monitoring()
        
        logger.info("✅ Performance monitoring initialized")
    
    def _before_request(self):
        """Called before each request."""
        g.request_start_time = time.time()
        g.db_query_count = 0
        g.db_query_time = 0.0
        g.cache_hits = 0
        g.cache_misses = 0
    
    def _after_request(self, response):
        """Called after each request."""
        if not hasattr(g, 'request_start_time'):
            return response
        
        # Calculate response time
        response_time_ms = (time.time() - g.request_start_time) * 1000
        
        # Get request information
        endpoint = request.endpoint or request.path
        method = request.method
        status_code = response.status_code
        
        # Get user information if available
        user_id = getattr(g, 'current_user_id', None)
        tenant_id = getattr(g, 'current_tenant_id', None)
        
        # Get system metrics
        memory_usage = self._get_memory_usage()
        cpu_usage = self._get_cpu_usage()
        
        # Log performance metric
        try:
            PerformanceMetric.log_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time_ms=response_time_ms,
                db_query_time_ms=getattr(g, 'db_query_time', 0.0),
                db_query_count=getattr(g, 'db_query_count', 0),
                cache_hits=getattr(g, 'cache_hits', 0),
                cache_misses=getattr(g, 'cache_misses', 0),
                user_id=user_id,
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                memory_usage_mb=memory_usage,
                cpu_usage_percent=cpu_usage
            )
        except Exception as e:
            logger.error(f"Failed to log performance metric: {e}")
        
        # Check for performance alerts
        self._check_performance_alerts(endpoint, response_time_ms, status_code)
        
        # Log slow requests
        slow_threshold = current_app.config.get('SLOW_REQUEST_THRESHOLD_MS', 2000)
        if response_time_ms >= slow_threshold:
            logger.warning(
                f"Slow request detected: {method} {endpoint} took {response_time_ms:.2f}ms"
            )
        
        return response
    
    def _setup_db_monitoring(self):
        """Set up database query monitoring."""
        
        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
        
        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if hasattr(context, '_query_start_time'):
                query_time = (time.time() - context._query_start_time) * 1000
                
                # Update request-level metrics
                if hasattr(g, 'db_query_count'):
                    g.db_query_count += 1
                    g.db_query_time += query_time
                
                # Log slow queries
                slow_threshold = current_app.config.get('SLOW_QUERY_THRESHOLD_MS', 1000)
                if query_time >= slow_threshold:
                    try:
                        SlowQuery.log_slow_query(
                            query_text=statement,
                            execution_time_ms=query_time,
                            endpoint=getattr(request, 'endpoint', None) if request else None,
                            user_id=getattr(g, 'current_user_id', None) if hasattr(g, 'current_user_id') else None,
                            tenant_id=getattr(g, 'current_tenant_id', None) if hasattr(g, 'current_tenant_id') else None
                        )
                    except Exception as e:
                        logger.error(f"Failed to log slow query: {e}")
    
    def _get_memory_usage(self) -> Optional[float]:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except Exception:
            return None
    
    def _get_cpu_usage(self) -> Optional[float]:
        """Get current CPU usage percentage."""
        try:
            return psutil.cpu_percent(interval=None)
        except Exception:
            return None
    
    def _check_performance_alerts(self, endpoint: str, response_time_ms: float, status_code: int):
        """Check for performance-related alerts."""
        try:
            # Check for slow requests
            slow_threshold = current_app.config.get('RESPONSE_TIME_THRESHOLD', 2000)
            if response_time_ms >= slow_threshold:
                PerformanceAlert.create_or_update_alert(
                    alert_type='slow_request',
                    severity='medium' if response_time_ms < slow_threshold * 2 else 'high',
                    title=f'Slow Request: {endpoint}',
                    description=f'Request to {endpoint} took {response_time_ms:.2f}ms',
                    endpoint=endpoint,
                    metric_value=response_time_ms,
                    threshold_value=slow_threshold
                )
            
            # Check for error rates
            if status_code >= 500:
                PerformanceAlert.create_or_update_alert(
                    alert_type='server_error',
                    severity='high',
                    title=f'Server Error: {endpoint}',
                    description=f'Server error {status_code} on {endpoint}',
                    endpoint=endpoint,
                    metric_value=status_code
                )
        except Exception as e:
            logger.error(f"Failed to check performance alerts: {e}")
    
    def _start_background_monitoring(self):
        """Start background monitoring tasks with proper Flask context."""
        context_manager = get_context_manager()
        
        def background_monitor():
            while True:
                try:
                    if context_manager:
                        with context_manager.create_background_context():
                            self._monitor_system_health()
                            self._cleanup_old_data()
                    else:
                        logger.warning("Context manager not available for background monitoring")
                        self._monitor_system_health()
                        self._cleanup_old_data()
                    time.sleep(60)  # Run every minute
                except Exception as e:
                    logger.error(f"Background monitoring error: {e}")
                    time.sleep(60)
        
        thread = threading.Thread(target=background_monitor, daemon=True)
        thread.start()
        logger.info("🔄 Background monitoring started")
    
    @safe_context
    def _monitor_system_health(self):
        """Monitor overall system health with proper Flask context."""
        try:
            # Monitor CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            cpu_threshold = current_app.config.get('CPU_ALERT_THRESHOLD', 85.0)
            
            if cpu_usage >= cpu_threshold:
                PerformanceAlert.create_or_update_alert(
                    alert_type='high_cpu_usage',
                    severity='high' if cpu_usage >= 95 else 'medium',
                    title='High CPU Usage',
                    description=f'CPU usage is {cpu_usage:.1f}%',
                    service_name='system',
                    metric_value=cpu_usage,
                    threshold_value=cpu_threshold
                )
            
            # Monitor memory usage
            memory = psutil.virtual_memory()
            memory_threshold = current_app.config.get('MEMORY_ALERT_THRESHOLD', 90.0)
            
            if memory.percent >= memory_threshold:
                PerformanceAlert.create_or_update_alert(
                    alert_type='high_memory_usage',
                    severity='high' if memory.percent >= 95 else 'medium',
                    title='High Memory Usage',
                    description=f'Memory usage is {memory.percent:.1f}%',
                    service_name='system',
                    metric_value=memory.percent,
                    threshold_value=memory_threshold
                )
            
            # Monitor disk usage
            disk = psutil.disk_usage('/')
            disk_threshold = current_app.config.get('DISK_ALERT_THRESHOLD', 95.0)
            disk_percent = (disk.used / disk.total) * 100
            
            if disk_percent >= disk_threshold:
                PerformanceAlert.create_or_update_alert(
                    alert_type='high_disk_usage',
                    severity='critical' if disk_percent >= 98 else 'high',
                    title='High Disk Usage',
                    description=f'Disk usage is {disk_percent:.1f}%',
                    service_name='system',
                    metric_value=disk_percent,
                    threshold_value=disk_threshold
                )
            
            # Update system health status
            ServiceHealth.update_service_status(
                service_name='system',
                service_type='system',
                status='healthy' if cpu_usage < cpu_threshold and memory.percent < memory_threshold else 'degraded',
                response_time_ms=None,
                extra_metadata={
                    'cpu_usage': cpu_usage,
                    'memory_usage': memory.percent,
                    'disk_usage': disk_percent
                }
            )
            
        except Exception as e:
            logger.error(f"System health monitoring error: {e}")
    
    @safe_context
    def _cleanup_old_data(self):
        """Clean up old performance data with proper Flask context."""
        try:
            retention_days = current_app.config.get('METRICS_RETENTION_DAYS', 30)
            
            # Clean up old performance metrics
            deleted_metrics = PerformanceMetric.cleanup_old_metrics(retention_days)
            if deleted_metrics > 0:
                logger.info(f"Cleaned up {deleted_metrics} old performance metrics")
            
            # Clean up old slow queries
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            deleted_queries = SlowQuery.query.filter(SlowQuery.timestamp < cutoff_date).delete()
            if deleted_queries > 0:
                logger.info(f"Cleaned up {deleted_queries} old slow queries")
            
            # Clean up resolved alerts older than 7 days
            alert_cutoff = datetime.utcnow() - timedelta(days=7)
            deleted_alerts = PerformanceAlert.query.filter(
                PerformanceAlert.status == 'resolved',
                PerformanceAlert.resolved_at < alert_cutoff
            ).delete()
            if deleted_alerts > 0:
                logger.info(f"Cleaned up {deleted_alerts} old resolved alerts")
            
        except Exception as e:
            logger.error(f"Data cleanup error: {e}")
    
    def record_cache_hit(self):
        """Record a cache hit."""
        if hasattr(g, 'cache_hits'):
            g.cache_hits += 1
    
    def record_cache_miss(self):
        """Record a cache miss."""
        if hasattr(g, 'cache_misses'):
            g.cache_misses += 1


def monitor_function_performance(threshold_ms: float = 1000):
    """Decorator to monitor function performance."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                execution_time = (time.time() - start_time) * 1000
                if execution_time >= threshold_ms:
                    logger.warning(
                        f"Slow function execution: {func.__name__} took {execution_time:.2f}ms"
                    )
        return wrapper
    return decorator


class PerformanceCollector:
    """Collect and aggregate performance metrics."""
    
    @staticmethod
    def get_endpoint_performance_summary(hours: int = 24) -> List[Dict[str, Any]]:
        """Get performance summary for all endpoints."""
        from sqlalchemy import func, case
        from app.models.performance import PerformanceMetric
        
        since = datetime.utcnow() - timedelta(hours=hours)
        
        results = PerformanceMetric.query.with_entities(
            PerformanceMetric.endpoint,
            func.count(PerformanceMetric.id).label('request_count'),
            func.avg(PerformanceMetric.response_time_ms).label('avg_response_time'),
            func.min(PerformanceMetric.response_time_ms).label('min_response_time'),
            func.max(PerformanceMetric.response_time_ms).label('max_response_time'),
            func.sum(case([(PerformanceMetric.status_code >= 400, 1)], else_=0)).label('error_count')
        ).filter(
            PerformanceMetric.timestamp >= since
        ).group_by(
            PerformanceMetric.endpoint
        ).order_by(
            func.avg(PerformanceMetric.response_time_ms).desc()
        ).all()
        
        return [
            {
                'endpoint': result.endpoint,
                'request_count': result.request_count,
                'avg_response_time': float(result.avg_response_time or 0),
                'min_response_time': float(result.min_response_time or 0),
                'max_response_time': float(result.max_response_time or 0),
                'error_count': result.error_count or 0,
                'error_rate': (result.error_count or 0) / max(result.request_count, 1)
            }
            for result in results
        ]
    
    @staticmethod
    def get_slow_queries_summary(hours: int = 24) -> List[Dict[str, Any]]:
        """Get summary of slow queries."""
        slow_queries = SlowQuery.get_frequent_slow_queries(hours=hours, limit=20)
        
        return [
            {
                'query_hash': query.query_hash,
                'normalized_query': query.normalized_query[:200] + '...' if len(query.normalized_query) > 200 else query.normalized_query,
                'occurrence_count': query.occurrence_count,
                'avg_execution_time': float(query.avg_execution_time),
                'max_execution_time': float(query.max_execution_time)
            }
            for query in slow_queries
        ]
    
    @staticmethod
    def get_system_health_summary() -> Dict[str, Any]:
        """Get overall system health summary."""
        try:
            # Get service health status
            service_summary = ServiceHealth.get_service_status_summary()
            service_counts = {status: count for status, count in service_summary}
            
            # Get active alerts
            active_alerts = PerformanceAlert.get_active_alerts()
            alert_counts = {}
            for alert in active_alerts:
                alert_counts[alert.severity] = alert_counts.get(alert.severity, 0) + 1
            
            # Get system metrics
            cpu_usage = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'services': service_counts,
                'alerts': {
                    'total': len(active_alerts),
                    'by_severity': alert_counts
                },
                'system': {
                    'cpu_usage': cpu_usage,
                    'memory_usage': memory.percent,
                    'disk_usage': (disk.used / disk.total) * 100,
                    'uptime': time.time() - psutil.boot_time()
                }
            }
        except Exception as e:
            logger.error(f"Failed to get system health summary: {e}")
            return {'error': str(e)}


# Global performance monitor instance
performance_monitor = PerformanceMonitor()