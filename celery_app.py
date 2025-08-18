"""Celery application factory."""
import logging
from celery import Celery
from celery.signals import task_failure, task_retry, task_success
from app import create_app

logger = logging.getLogger(__name__)


def create_celery_app(app=None):
    """Create Celery app with Flask app context."""
    app = app or create_app()
    
    celery = Celery(
        app.import_name,
        broker=app.config['CELERY_BROKER_URL'],
        backend=app.config['CELERY_RESULT_BACKEND']
    )
    
    # Update configuration with enhanced settings
    celery.conf.update(
        # Serialization
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        
        # Timezone
        timezone='UTC',
        enable_utc=True,
        
        # Task execution
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 minutes
        task_soft_time_limit=25 * 60,  # 25 minutes
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        
        # Worker settings
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        worker_disable_rate_limits=False,
        
        # Retry settings
        task_default_retry_delay=60,  # 1 minute
        task_max_retries=3,
        
        # Result backend settings
        result_expires=3600,  # 1 hour
        result_persistent=True,
        
        # Monitoring
        worker_send_task_events=True,
        task_send_sent_event=True,
        
        # Dead letter queue configuration
        task_routes={
            'app.workers.billing.*': {'queue': 'billing'},
            'app.workers.kyb.*': {'queue': 'kyb'},
            'app.workers.notifications.*': {'queue': 'notifications'},
            'app.workers.dead_letter.*': {'queue': 'dead_letter'},
        },
        
        # Queue configuration
        task_default_queue='default',
        task_queues={
            'default': {
                'exchange': 'default',
                'exchange_type': 'direct',
                'routing_key': 'default',
            },
            'billing': {
                'exchange': 'billing',
                'exchange_type': 'direct',
                'routing_key': 'billing',
            },
            'kyb': {
                'exchange': 'kyb',
                'exchange_type': 'direct',
                'routing_key': 'kyb',
            },
            'notifications': {
                'exchange': 'notifications',
                'exchange_type': 'direct',
                'routing_key': 'notifications',
            },
            'dead_letter': {
                'exchange': 'dead_letter',
                'exchange_type': 'direct',
                'routing_key': 'dead_letter',
            },
        },
    )
    
    # Create task context with enhanced error handling
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context."""
        
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
        
        def on_failure(self, exc, task_id, args, kwargs, einfo):
            """Handle task failure."""
            logger.error(
                f"Task {self.name} failed: {exc}",
                extra={
                    'task_id': task_id,
                    'task_name': self.name,
                    'args': args,
                    'kwargs': kwargs,
                    'exception': str(exc),
                    'traceback': str(einfo)
                }
            )
        
        def on_retry(self, exc, task_id, args, kwargs, einfo):
            """Handle task retry."""
            logger.warning(
                f"Task {self.name} retrying: {exc}",
                extra={
                    'task_id': task_id,
                    'task_name': self.name,
                    'args': args,
                    'kwargs': kwargs,
                    'exception': str(exc),
                    'retry_count': self.request.retries
                }
            )
        
        def on_success(self, retval, task_id, args, kwargs):
            """Handle task success."""
            logger.info(
                f"Task {self.name} completed successfully",
                extra={
                    'task_id': task_id,
                    'task_name': self.name,
                    'result': str(retval)[:200] if retval else None
                }
            )
    
    celery.Task = ContextTask
    
    # Register signal handlers
    register_signal_handlers(celery)
    
    # Register worker tasks after app initialization
    try:
        from app.workers.base import register_worker_tasks
        register_worker_tasks(celery)
    except ImportError as e:
        logger.warning(f"Could not register worker tasks: {e}")
    
    return celery


def register_signal_handlers(celery_app):
    """Register Celery signal handlers for monitoring."""
    
    @task_failure.connect
    def task_failure_handler(sender=None, task_id=None, exception=None, 
                           traceback=None, einfo=None, **kwargs):
        """Handle task failure signal."""
        logger.error(
            f"Task failure signal: {sender}",
            extra={
                'task_id': task_id,
                'exception': str(exception),
                'sender': sender
            }
        )
    
    @task_retry.connect
    def task_retry_handler(sender=None, task_id=None, reason=None, 
                          einfo=None, **kwargs):
        """Handle task retry signal."""
        logger.warning(
            f"Task retry signal: {sender}",
            extra={
                'task_id': task_id,
                'reason': str(reason),
                'sender': sender
            }
        )
    
    @task_success.connect
    def task_success_handler(sender=None, result=None, **kwargs):
        """Handle task success signal."""
        logger.debug(
            f"Task success signal: {sender}",
            extra={
                'sender': sender,
                'result_preview': str(result)[:100] if result else None
            }
        )


# Create celery instance
celery = create_celery_app()