"""Performance logging utilities."""
import time
import functools
from typing import Callable, Any, Dict, Optional
from flask import request, g, current_app
import structlog

logger = structlog.get_logger()


def log_performance(
    operation_name: str = None,
    log_args: bool = False,
    log_result: bool = False,
    threshold_ms: float = 1000.0
):
    """
    Decorator to log performance metrics for functions.
    
    Args:
        operation_name: Custom name for the operation (defaults to function name)
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        threshold_ms: Only log if execution time exceeds this threshold
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation = operation_name or f"{func.__module__}.{func.__name__}"
            
            # Prepare log context
            log_context = {
                "operation": operation,
                "start_time": start_time
            }
            
            # Add request context if available
            if request:
                log_context.update({
                    "request_id": getattr(g, 'request_id', None),
                    "user_id": getattr(g, 'user_id', None),
                    "tenant_id": getattr(g, 'tenant_id', None),
                    "endpoint": request.endpoint,
                    "method": request.method
                })
            
            # Log arguments if requested
            if log_args and (args or kwargs):
                log_context["args"] = {
                    "args": args[:3] if len(args) > 3 else args,  # Limit to first 3 args
                    "kwargs": {k: v for k, v in list(kwargs.items())[:5]}  # Limit to first 5 kwargs
                }
            
            try:
                result = func(*args, **kwargs)
                
                execution_time_ms = (time.time() - start_time) * 1000
                
                # Only log if execution time exceeds threshold
                if execution_time_ms >= threshold_ms:
                    log_context.update({
                        "execution_time_ms": round(execution_time_ms, 2),
                        "status": "success"
                    })
                    
                    if log_result and result is not None:
                        # Safely log result (avoid logging large objects)
                        if isinstance(result, (str, int, float, bool, list, dict)):
                            if isinstance(result, (list, dict)) and len(str(result)) > 1000:
                                log_context["result"] = f"<{type(result).__name__} with {len(result)} items>"
                            else:
                                log_context["result"] = result
                        else:
                            log_context["result"] = f"<{type(result).__name__}>"
                    
                    logger.info("Performance log", **log_context)
                
                return result
                
            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000
                
                log_context.update({
                    "execution_time_ms": round(execution_time_ms, 2),
                    "status": "error",
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                
                logger.error("Performance log - error", **log_context)
                raise
        
        return wrapper
    return decorator


def log_database_query(query_name: str = None):
    """
    Decorator specifically for database query performance logging.
    
    Args:
        query_name: Custom name for the query
    """
    return log_performance(
        operation_name=f"db_query:{query_name}" if query_name else None,
        threshold_ms=100.0  # Lower threshold for database queries
    )


def log_external_api_call(api_name: str = None):
    """
    Decorator specifically for external API call performance logging.
    
    Args:
        api_name: Name of the external API
    """
    return log_performance(
        operation_name=f"external_api:{api_name}" if api_name else None,
        threshold_ms=500.0,  # Higher threshold for external APIs
        log_args=True
    )


class PerformanceContext:
    """Context manager for performance logging."""
    
    def __init__(
        self, 
        operation_name: str,
        log_details: bool = True,
        threshold_ms: float = 100.0
    ):
        self.operation_name = operation_name
        self.log_details = log_details
        self.threshold_ms = threshold_ms
        self.start_time = None
        self.context = {}
    
    def __enter__(self):
        self.start_time = time.time()
        
        if self.log_details:
            self.context = {
                "operation": self.operation_name,
                "start_time": self.start_time
            }
            
            # Add request context if available
            if request:
                self.context.update({
                    "request_id": getattr(g, 'request_id', None),
                    "user_id": getattr(g, 'user_id', None),
                    "tenant_id": getattr(g, 'tenant_id', None),
                    "endpoint": request.endpoint,
                    "method": request.method
                })
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is None:
            return
        
        execution_time_ms = (time.time() - self.start_time) * 1000
        
        # Only log if execution time exceeds threshold
        if execution_time_ms >= self.threshold_ms:
            self.context.update({
                "execution_time_ms": round(execution_time_ms, 2),
                "status": "error" if exc_type else "success"
            })
            
            if exc_type:
                self.context.update({
                    "error": str(exc_val),
                    "error_type": exc_type.__name__
                })
                logger.error("Performance context - error", **self.context)
            else:
                logger.info("Performance context", **self.context)
    
    def add_context(self, **kwargs):
        """Add additional context to the performance log."""
        self.context.update(kwargs)


def measure_time(operation_name: str) -> PerformanceContext:
    """
    Create a performance context manager.
    
    Usage:
        with measure_time("complex_operation") as perf:
            # Do complex work
            perf.add_context(items_processed=100)
    """
    return PerformanceContext(operation_name)


class RequestPerformanceLogger:
    """Middleware for logging request performance."""
    
    def __init__(self, app=None, threshold_ms: float = 1000.0):
        self.threshold_ms = threshold_ms
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app."""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        app.teardown_appcontext(self.teardown_request)
    
    def before_request(self):
        """Record request start time."""
        g.request_start_time = time.time()
        g.request_id = self._generate_request_id()
    
    def after_request(self, response):
        """Log request performance."""
        if not hasattr(g, 'request_start_time'):
            return response
        
        execution_time_ms = (time.time() - g.request_start_time) * 1000
        
        # Only log slow requests
        if execution_time_ms >= self.threshold_ms:
            # Check if we're in a request context before accessing request
            try:
                from flask import has_request_context
                if has_request_context():
                    log_context = {
                        "request_id": getattr(g, 'request_id', None),
                        "method": request.method,
                        "path": request.path,
                        "endpoint": request.endpoint,
                        "status_code": response.status_code,
                        "execution_time_ms": round(execution_time_ms, 2),
                        "user_id": getattr(g, 'user_id', None),
                        "tenant_id": getattr(g, 'tenant_id', None),
                        "user_agent": request.headers.get('User-Agent', ''),
                        "remote_addr": request.remote_addr
                    }
                    
                    # Add query parameters for GET requests
                    if request.method == 'GET' and request.args:
                        log_context["query_params"] = dict(request.args)
                else:
                    # No request context, log minimal information
                    log_context = {
                        "execution_time_ms": round(execution_time_ms, 2),
                        "status_code": response.status_code if response else None,
                        "context": "no_request_context"
                    }
            except Exception:
                # Fallback if has_request_context is not available
                log_context = {
                    "execution_time_ms": round(execution_time_ms, 2),
                    "status_code": response.status_code if response else None,
                    "context": "context_check_failed"
                }
            
            # Log as warning if very slow, info otherwise
            if execution_time_ms >= 5000:  # 5 seconds
                logger.warning("Slow request", **log_context)
            else:
                logger.info("Request performance", **log_context)
        
        return response
    
    def teardown_request(self, exception):
        """Clean up request context."""
        if exception:
            execution_time_ms = 0
            if hasattr(g, 'request_start_time'):
                execution_time_ms = (time.time() - g.request_start_time) * 1000
            
            # Check if we're in a request context before accessing request
            try:
                from flask import has_request_context
                if has_request_context():
                    log_context = {
                        "request_id": getattr(g, 'request_id', None),
                        "method": request.method,
                        "path": request.path,
                        "endpoint": request.endpoint,
                        "execution_time_ms": round(execution_time_ms, 2),
                        "error": str(exception),
                        "error_type": type(exception).__name__,
                        "user_id": getattr(g, 'user_id', None),
                        "tenant_id": getattr(g, 'tenant_id', None)
                    }
                else:
                    # No request context, log minimal information
                    log_context = {
                        "execution_time_ms": round(execution_time_ms, 2),
                        "error": str(exception),
                        "error_type": type(exception).__name__,
                        "context": "no_request_context"
                    }
            except Exception:
                # Fallback if has_request_context is not available
                log_context = {
                    "execution_time_ms": round(execution_time_ms, 2),
                    "error": str(exception),
                    "error_type": type(exception).__name__,
                    "context": "context_check_failed"
                }
            
            logger.error("Request error", **log_context)
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        import uuid
        return f"req_{uuid.uuid4().hex[:8]}"


def init_performance_logging(app, threshold_ms: float = 1000.0):
    """Initialize performance logging for the application."""
    performance_logger = RequestPerformanceLogger(app, threshold_ms)
    logger.info("Performance logging initialized", threshold_ms=threshold_ms)
    return performance_logger