"""Performance monitoring middleware."""
import time
import logging
from flask import Flask, request, g
from werkzeug.exceptions import HTTPException

from app.utils.performance_monitor import performance_monitor
from app.utils.performance_alerts import alert_manager, threshold_checker


logger = logging.getLogger(__name__)


class PerformanceMiddleware:
    """Middleware to integrate performance monitoring into Flask app."""
    
    def __init__(self, app: Flask = None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize performance middleware with Flask app."""
        self.app = app
        
        # Initialize performance monitor
        performance_monitor.init_app(app)
        
        # Initialize alert manager
        alert_manager.init_app(app)
        
        # Initialize threshold checker
        threshold_checker.init_app(app)
        
        # Register error handlers for performance tracking
        self._register_error_handlers(app)
        
        # Register teardown handlers
        app.teardown_appcontext(self._teardown_performance_context)
        
        logger.info("✅ Performance middleware initialized")
    
    def _register_error_handlers(self, app: Flask):
        """Register error handlers to track error performance."""
        
        @app.errorhandler(Exception)
        def handle_exception(error):
            """Handle all exceptions and track performance."""
            # Record the error in performance metrics
            if hasattr(g, 'request_start_time'):
                response_time_ms = (time.time() - g.request_start_time) * 1000
                
                # Determine status code
                if isinstance(error, HTTPException):
                    status_code = error.code
                else:
                    status_code = 500
                
                # Log error performance
                try:
                    from app.models.performance import PerformanceMetric
                    
                    PerformanceMetric.log_request(
                        endpoint=request.endpoint or request.path,
                        method=request.method,
                        status_code=status_code,
                        response_time_ms=response_time_ms,
                        db_query_time_ms=getattr(g, 'db_query_time', 0.0),
                        db_query_count=getattr(g, 'db_query_count', 0),
                        cache_hits=getattr(g, 'cache_hits', 0),
                        cache_misses=getattr(g, 'cache_misses', 0),
                        user_id=getattr(g, 'current_user_id', None),
                        tenant_id=getattr(g, 'current_tenant_id', None),
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get('User-Agent')
                    )
                except Exception as e:
                    logger.error(f"Failed to log error performance metric: {e}")
            
            # Re-raise the original exception
            raise error
    
    def _teardown_performance_context(self, exception):
        """Clean up performance monitoring context."""
        # Clean up any performance monitoring resources
        if hasattr(g, 'performance_context'):
            delattr(g, 'performance_context')


def init_performance_monitoring(app: Flask):
    """Initialize complete performance monitoring system."""
    
    # Initialize middleware
    middleware = PerformanceMiddleware(app)
    
    # Add performance monitoring configuration
    if not app.config.get('PERFORMANCE_LOG_THRESHOLD_MS'):
        app.config['PERFORMANCE_LOG_THRESHOLD_MS'] = 1000
    
    if not app.config.get('SLOW_QUERY_THRESHOLD_MS'):
        app.config['SLOW_QUERY_THRESHOLD_MS'] = 1000
    
    if not app.config.get('SLOW_REQUEST_THRESHOLD_MS'):
        app.config['SLOW_REQUEST_THRESHOLD_MS'] = 2000
    
    if not app.config.get('METRICS_RETENTION_DAYS'):
        app.config['METRICS_RETENTION_DAYS'] = 30
    
    # Set up periodic tasks if Celery is available
    try:
        from celery import Celery
        if app.config.get('CELERY_BROKER_URL'):
            _setup_periodic_performance_tasks(app)
    except ImportError:
        logger.info("Celery not available, skipping periodic performance tasks")
    
    logger.info("🚀 Performance monitoring system fully initialized")
    
    return middleware


def _setup_periodic_performance_tasks(app: Flask):
    """Set up periodic performance monitoring tasks."""
    try:
        from celery import Celery
        from celery.schedules import crontab
        
        # This would be set up in the main Celery configuration
        # Here we just log that it should be configured
        logger.info("📅 Periodic performance tasks should be configured in Celery")
        
        # Example of what should be added to celery configuration:
        # CELERYBEAT_SCHEDULE = {
        #     'check-performance-thresholds': {
        #         'task': 'app.tasks.performance.check_thresholds',
        #         'schedule': crontab(minute='*/5'),  # Every 5 minutes
        #     },
        #     'send-performance-alerts': {
        #         'task': 'app.tasks.performance.send_alerts',
        #         'schedule': crontab(minute='*/10'),  # Every 10 minutes
        #     },
        #     'cleanup-performance-data': {
        #         'task': 'app.tasks.performance.cleanup_old_data',
        #         'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        #     },
        # }
        
    except Exception as e:
        logger.error(f"Failed to set up periodic performance tasks: {e}")


# Decorator for monitoring specific functions
def monitor_performance(threshold_ms: float = 1000, alert_on_slow: bool = False):
    """
    Decorator to monitor function performance.
    
    Args:
        threshold_ms: Threshold in milliseconds to log slow execution
        alert_on_slow: Whether to create alerts for slow execution
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = f"{func.__module__}.{func.__name__}"
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                # Log function error
                execution_time = (time.time() - start_time) * 1000
                logger.error(f"Function {function_name} failed after {execution_time:.2f}ms: {e}")
                raise
            finally:
                execution_time = (time.time() - start_time) * 1000
                
                if execution_time >= threshold_ms:
                    logger.warning(f"Slow function: {function_name} took {execution_time:.2f}ms")
                    
                    if alert_on_slow:
                        try:
                            from app.models.performance import PerformanceAlert
                            PerformanceAlert.create_or_update_alert(
                                alert_type='slow_function',
                                severity='medium' if execution_time < threshold_ms * 2 else 'high',
                                title=f'Slow Function: {function_name}',
                                description=f'Function {function_name} took {execution_time:.2f}ms',
                                service_name='application',
                                metric_value=execution_time,
                                threshold_value=threshold_ms
                            )
                        except Exception as e:
                            logger.error(f"Failed to create slow function alert: {e}")
        
        return wrapper
    return decorator


# Context manager for monitoring code blocks
class PerformanceContext:
    """Context manager for monitoring performance of code blocks."""
    
    def __init__(self, name: str, threshold_ms: float = 1000):
        self.name = name
        self.threshold_ms = threshold_ms
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            execution_time = (time.time() - self.start_time) * 1000
            
            if execution_time >= self.threshold_ms:
                logger.warning(f"Slow operation: {self.name} took {execution_time:.2f}ms")
            
            # Store in g for request-level aggregation
            if hasattr(g, 'performance_operations'):
                g.performance_operations.append({
                    'name': self.name,
                    'execution_time_ms': execution_time
                })
            else:
                g.performance_operations = [{
                    'name': self.name,
                    'execution_time_ms': execution_time
                }]