"""
Application monitoring utilities for AI Secretary.
Provides metrics collection, health checks, and performance monitoring.
"""

import time
import psutil
import logging
from functools import wraps
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from flask import request, g, current_app
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import structlog

# Prometheus metrics
REQUEST_COUNT = Counter(
    'flask_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'flask_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'flask_active_connections',
    'Number of active connections'
)

DATABASE_CONNECTIONS = Gauge(
    'database_connections_active',
    'Number of active database connections'
)

REDIS_CONNECTIONS = Gauge(
    'redis_connections_active',
    'Number of active Redis connections'
)

CELERY_TASKS = Counter(
    'celery_tasks_total',
    'Total number of Celery tasks',
    ['task_name', 'status']
)

CELERY_TASK_DURATION = Histogram(
    'celery_task_duration_seconds',
    'Celery task duration in seconds',
    ['task_name']
)

AI_REQUESTS = Counter(
    'ai_requests_total',
    'Total number of AI API requests',
    ['provider', 'model', 'status']
)

AI_REQUEST_DURATION = Histogram(
    'ai_request_duration_seconds',
    'AI API request duration in seconds',
    ['provider', 'model']
)

SYSTEM_CPU_USAGE = Gauge('system_cpu_usage_percent', 'System CPU usage percentage')
SYSTEM_MEMORY_USAGE = Gauge('system_memory_usage_percent', 'System memory usage percentage')
SYSTEM_DISK_USAGE = Gauge('system_disk_usage_percent', 'System disk usage percentage')

# Structured logger
logger = structlog.get_logger(__name__)


class HealthChecker:
    """Health check system for monitoring service status."""
    
    def __init__(self):
        self.checks = {}
        self.last_check_time = None
        self.check_interval = 30  # seconds
    
    def register_check(self, name: str, check_func: callable, critical: bool = True):
        """Register a health check function."""
        self.checks[name] = {
            'func': check_func,
            'critical': critical,
            'last_result': None,
            'last_check': None
        }
    
    def run_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {},
            'system': self._get_system_metrics()
        }
        
        for name, check in self.checks.items():
            try:
                start_time = time.time()
                result = check['func']()
                duration = time.time() - start_time
                
                check_result = {
                    'status': 'healthy' if result else 'unhealthy',
                    'duration': duration,
                    'timestamp': datetime.utcnow().isoformat(),
                    'critical': check['critical']
                }
                
                if not result and check['critical']:
                    results['status'] = 'unhealthy'
                
                results['checks'][name] = check_result
                check['last_result'] = result
                check['last_check'] = datetime.utcnow()
                
                logger.info(
                    "Health check completed",
                    check_name=name,
                    status=check_result['status'],
                    duration=duration
                )
                
            except Exception as e:
                check_result = {
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat(),
                    'critical': check['critical']
                }
                
                if check['critical']:
                    results['status'] = 'unhealthy'
                
                results['checks'][name] = check_result
                
                logger.error(
                    "Health check failed",
                    check_name=name,
                    error=str(e)
                )
        
        self.last_check_time = datetime.utcnow()
        return results
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Update Prometheus metrics
            SYSTEM_CPU_USAGE.set(cpu_percent)
            SYSTEM_MEMORY_USAGE.set(memory.percent)
            SYSTEM_DISK_USAGE.set(disk.percent)
            
            return {
                'cpu_usage_percent': cpu_percent,
                'memory_usage_percent': memory.percent,
                'memory_available_mb': memory.available // 1024 // 1024,
                'disk_usage_percent': disk.percent,
                'disk_free_gb': disk.free // 1024 // 1024 // 1024
            }
        except Exception as e:
            logger.error("Failed to get system metrics", error=str(e))
            return {}


# Global health checker instance
health_checker = HealthChecker()


def monitor_request_metrics():
    """Middleware to monitor HTTP request metrics."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                response = f(*args, **kwargs)
                status_code = getattr(response, 'status_code', 200)
            except Exception as e:
                status_code = 500
                raise
            finally:
                duration = time.time() - start_time
                
                # Record metrics
                REQUEST_COUNT.labels(
                    method=request.method,
                    endpoint=request.endpoint or 'unknown',
                    status_code=status_code
                ).inc()
                
                REQUEST_DURATION.labels(
                    method=request.method,
                    endpoint=request.endpoint or 'unknown'
                ).observe(duration)
                
                # Log request
                logger.info(
                    "HTTP request completed",
                    method=request.method,
                    endpoint=request.endpoint,
                    status_code=status_code,
                    duration=duration,
                    remote_addr=request.remote_addr
                )
            
            return response
        return wrapper
    return decorator


def monitor_celery_task(task_name: str):
    """Decorator to monitor Celery task metrics."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            
            try:
                result = f(*args, **kwargs)
                return result
            except Exception as e:
                status = 'failure'
                logger.error(
                    "Celery task failed",
                    task_name=task_name,
                    error=str(e)
                )
                raise
            finally:
                duration = time.time() - start_time
                
                CELERY_TASKS.labels(
                    task_name=task_name,
                    status=status
                ).inc()
                
                CELERY_TASK_DURATION.labels(
                    task_name=task_name
                ).observe(duration)
                
                logger.info(
                    "Celery task completed",
                    task_name=task_name,
                    status=status,
                    duration=duration
                )
        
        return wrapper
    return decorator


def monitor_ai_request(provider: str, model: str):
    """Decorator to monitor AI API request metrics."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            
            try:
                result = f(*args, **kwargs)
                return result
            except Exception as e:
                status = 'failure'
                logger.error(
                    "AI request failed",
                    provider=provider,
                    model=model,
                    error=str(e)
                )
                raise
            finally:
                duration = time.time() - start_time
                
                AI_REQUESTS.labels(
                    provider=provider,
                    model=model,
                    status=status
                ).inc()
                
                AI_REQUEST_DURATION.labels(
                    provider=provider,
                    model=model
                ).observe(duration)
                
                logger.info(
                    "AI request completed",
                    provider=provider,
                    model=model,
                    status=status,
                    duration=duration
                )
        
        return wrapper
    return decorator


class PerformanceMonitor:
    """Performance monitoring and alerting system."""
    
    def __init__(self):
        self.thresholds = {
            'response_time_p95': 2.0,  # seconds
            'error_rate': 0.05,  # 5%
            'cpu_usage': 80.0,  # percent
            'memory_usage': 85.0,  # percent
            'disk_usage': 90.0,  # percent
        }
        self.alerts = []
    
    def check_performance_thresholds(self) -> list:
        """Check if any performance thresholds are exceeded."""
        alerts = []
        
        try:
            # Check system metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('/').percent
            
            if cpu_usage > self.thresholds['cpu_usage']:
                alerts.append({
                    'type': 'high_cpu_usage',
                    'severity': 'warning',
                    'message': f'CPU usage is {cpu_usage:.1f}%',
                    'threshold': self.thresholds['cpu_usage'],
                    'current_value': cpu_usage
                })
            
            if memory_usage > self.thresholds['memory_usage']:
                alerts.append({
                    'type': 'high_memory_usage',
                    'severity': 'warning',
                    'message': f'Memory usage is {memory_usage:.1f}%',
                    'threshold': self.thresholds['memory_usage'],
                    'current_value': memory_usage
                })
            
            if disk_usage > self.thresholds['disk_usage']:
                alerts.append({
                    'type': 'high_disk_usage',
                    'severity': 'critical',
                    'message': f'Disk usage is {disk_usage:.1f}%',
                    'threshold': self.thresholds['disk_usage'],
                    'current_value': disk_usage
                })
            
        except Exception as e:
            logger.error("Failed to check performance thresholds", error=str(e))
        
        return alerts
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get current performance summary."""
        try:
            return {
                'cpu_usage': psutil.cpu_percent(interval=1),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None,
                'active_connections': len(psutil.net_connections()),
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error("Failed to get performance summary", error=str(e))
            return {}


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def setup_health_checks():
    """Set up default health checks."""
    from app.models import db
    from app.utils.redis_client import redis_client
    
    def check_database():
        """Check database connectivity."""
        try:
            db.session.execute('SELECT 1')
            return True
        except Exception:
            return False
    
    def check_redis():
        """Check Redis connectivity."""
        try:
            redis_client.ping()
            return True
        except Exception:
            return False
    
    def check_disk_space():
        """Check available disk space."""
        try:
            disk_usage = psutil.disk_usage('/').percent
            return disk_usage < 95  # Alert if disk usage > 95%
        except Exception:
            return False
    
    def check_memory():
        """Check memory usage."""
        try:
            memory_usage = psutil.virtual_memory().percent
            return memory_usage < 90  # Alert if memory usage > 90%
        except Exception:
            return False
    
    # Register health checks
    health_checker.register_check('database', check_database, critical=True)
    health_checker.register_check('redis', check_redis, critical=True)
    health_checker.register_check('disk_space', check_disk_space, critical=True)
    health_checker.register_check('memory', check_memory, critical=False)


def get_metrics():
    """Get Prometheus metrics."""
    return generate_latest()


def get_metrics_content_type():
    """Get Prometheus metrics content type."""
    return CONTENT_TYPE_LATEST