"""Base worker classes and utilities."""
import logging
from typing import Any, Dict, Optional
from celery import Task
from celery.exceptions import Retry, MaxRetriesExceededError
from app import db
from app.utils.application_context_manager import get_context_manager, with_app_context, safe_context

logger = logging.getLogger(__name__)


class BaseWorker(Task):
    """Base worker class with common functionality."""
    
    # Default retry settings
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 60}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure with enhanced logging."""
        self.logger.error(
            f"Task {self.name} failed permanently",
            extra={
                'task_id': task_id,
                'exception': str(exc),
                'task_args': args,
                'task_kwargs': kwargs,
                'traceback': str(einfo)
            }
        )
        
        # Send to dead letter queue if max retries exceeded
        if isinstance(exc, MaxRetriesExceededError):
            self._send_to_dead_letter_queue(task_id, args, kwargs, exc)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry with enhanced logging."""
        self.logger.warning(
            f"Task {self.name} retrying (attempt {self.request.retries + 1})",
            extra={
                'task_id': task_id,
                'exception': str(exc),
                'retry_count': self.request.retries,
                'max_retries': self.max_retries
            }
        )
    
    def _send_to_dead_letter_queue(self, task_id: str, args: tuple, 
                                  kwargs: dict, exception: Exception):
        """Send failed task to dead letter queue."""
        from app.workers.dead_letter import process_dead_letter_task
        
        try:
            process_dead_letter_task.apply_async(
                args=[{
                    'original_task': self.name,
                    'task_id': task_id,
                    'task_args': args,
                    'task_kwargs': kwargs,
                    'exception': str(exception),
                    'failure_reason': 'max_retries_exceeded'
                }],
                queue='dead_letter'
            )
        except Exception as e:
            self.logger.error(f"Failed to send task to dead letter queue: {e}")
    
    def _safe_db_operation(self, operation_func, *args, **kwargs):
        """Safely execute database operations with rollback on error and proper context."""
        context_manager = get_context_manager()
        
        def db_operation():
            try:
                result = operation_func(*args, **kwargs)
                db.session.commit()
                return result
            except Exception as e:
                db.session.rollback()
                self.logger.error(f"Database operation failed: {e}")
                raise
        
        if context_manager:
            return context_manager.run_with_context(db_operation)
        else:
            return db_operation()


class MonitoredWorker(BaseWorker):
    """Worker with enhanced monitoring capabilities."""
    
    def __init__(self):
        super().__init__()
        self.metrics = {}
    
    def before_start(self, task_id, args, kwargs):
        """Called before task execution starts."""
        import time
        self.metrics['start_time'] = time.time()
        self.logger.info(
            f"Starting task {self.name}",
            extra={
                'task_id': task_id,
                'task_args': args,
                'kwargs': kwargs
            }
        )
    
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Called after task execution completes."""
        import time
        
        if 'start_time' in self.metrics:
            execution_time = time.time() - self.metrics['start_time']
            self.logger.info(
                f"Task {self.name} completed",
                extra={
                    'task_id': task_id,
                    'status': status,
                    'execution_time': execution_time,
                    'result_preview': str(retval)[:200] if retval else None
                }
            )
            
            # Record metrics (could be sent to monitoring system)
            self._record_metrics(task_id, status, execution_time)
    
    def _record_metrics(self, task_id: str, status: str, execution_time: float):
        """Record task metrics for monitoring."""
        # This could be extended to send metrics to Prometheus, DataDog, etc.
        self.logger.debug(
            f"Task metrics recorded",
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'status': status,
                'execution_time': execution_time
            }
        )


def create_task_decorator(queue_name: str = 'default', **task_kwargs):
    """Create a task decorator with predefined settings."""
    def decorator(func):
        # Delay celery import to avoid circular imports
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Store task configuration for later registration
        wrapper._task_config = {
            'bind': True,
            'base': MonitoredWorker,
            'queue': queue_name,
            'serializer': 'json',
            'compression': 'gzip',
            **task_kwargs
        }
        wrapper._original_func = func
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        
        return wrapper
    
    return decorator


def register_worker_tasks(celery_app):
    """Register worker tasks with Celery after app initialization."""
    import importlib
    import pkgutil
    import app.workers
    
    # Import all worker modules to collect task decorators
    for importer, modname, ispkg in pkgutil.iter_modules(app.workers.__path__, app.workers.__name__ + "."):
        if modname != 'app.workers.base':  # Skip base module
            try:
                module = importlib.import_module(modname)
                # Look for functions with task configuration
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if hasattr(attr, '_task_config') and hasattr(attr, '_original_func'):
                        # Register the task with Celery
                        task_func = celery_app.task(**attr._task_config)(attr._original_func)
                        # Replace the wrapper with the actual Celery task
                        setattr(module, attr_name, task_func)
            except ImportError as e:
                logger.warning(f"Could not import worker module {modname}: {e}")


def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get detailed task status information."""
    try:
        from celery_app import celery
        result = celery.AsyncResult(task_id)
        return {
            'task_id': task_id,
            'status': result.status,
            'result': result.result,
            'traceback': result.traceback,
            'date_done': result.date_done,
            'successful': result.successful(),
            'failed': result.failed(),
            'ready': result.ready()
        }
    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}")
        return {
            'task_id': task_id,
            'status': 'UNKNOWN',
            'error': str(e)
        }


def revoke_task(task_id: str, terminate: bool = False) -> bool:
    """Revoke a running task."""
    try:
        from celery_app import celery
        celery.control.revoke(task_id, terminate=terminate)
        logger.info(f"Task {task_id} revoked (terminate={terminate})")
        return True
    except Exception as e:
        logger.error(f"Failed to revoke task {task_id}: {e}")
        return False


def get_active_tasks() -> Dict[str, Any]:
    """Get information about currently active tasks."""
    try:
        from celery_app import celery
        inspect = celery.control.inspect()
        active_tasks = inspect.active()
        return active_tasks or {}
    except Exception as e:
        logger.error(f"Failed to get active tasks: {e}")
        return {}


def get_worker_stats() -> Dict[str, Any]:
    """Get worker statistics."""
    try:
        from celery_app import celery
        inspect = celery.control.inspect()
        stats = inspect.stats()
        return stats or {}
    except Exception as e:
        logger.error(f"Failed to get worker stats: {e}")
        return {}