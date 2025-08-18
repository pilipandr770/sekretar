"""Task queue monitoring utilities."""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from app.workers.base import get_task_status, get_active_tasks, get_worker_stats
from app.workers.dead_letter import get_dead_letter_stats

logger = logging.getLogger(__name__)


class TaskQueueMonitor:
    """Monitor task queue health and performance."""
    
    def __init__(self):
        self.celery_app = celery
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics."""
        try:
            inspect = self.celery_app.control.inspect()
            
            # Get basic queue info
            active_queues = inspect.active_queues() or {}
            reserved_tasks = inspect.reserved() or {}
            scheduled_tasks = inspect.scheduled() or {}
            
            # Get worker info
            worker_stats = get_worker_stats()
            active_tasks = get_active_tasks()
            
            # Get dead letter stats
            dead_letter_stats = get_dead_letter_stats()
            
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'queues': {
                    'active_queues': active_queues,
                    'reserved_tasks_count': sum(len(tasks) for tasks in reserved_tasks.values()),
                    'scheduled_tasks_count': sum(len(tasks) for tasks in scheduled_tasks.values()),
                    'active_tasks_count': sum(len(tasks) for tasks in active_tasks.values())
                },
                'workers': {
                    'total_workers': len(worker_stats),
                    'worker_details': worker_stats
                },
                'dead_letter': dead_letter_stats,
                'health_status': self._assess_health(active_tasks, worker_stats, dead_letter_stats)
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e),
                'health_status': 'unhealthy'
            }
    
    def _assess_health(self, active_tasks: Dict, worker_stats: Dict, 
                      dead_letter_stats: Dict) -> str:
        """Assess overall queue health."""
        try:
            # Check if workers are running
            if not worker_stats:
                return 'critical'
            
            # Check dead letter queue
            pending_dead_letters = dead_letter_stats.get('pending_count', 0)
            if pending_dead_letters > 100:  # Threshold for concern
                return 'degraded'
            
            # Check for stuck tasks (running for too long)
            stuck_tasks = self._find_stuck_tasks(active_tasks)
            if stuck_tasks:
                return 'degraded'
            
            return 'healthy'
            
        except Exception as e:
            logger.error(f"Failed to assess health: {e}")
            return 'unknown'
    
    def _find_stuck_tasks(self, active_tasks: Dict, 
                         max_runtime_minutes: int = 60) -> List[Dict]:
        """Find tasks that have been running for too long."""
        stuck_tasks = []
        current_time = datetime.now(timezone.utc)
        
        try:
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    # Parse task start time
                    time_start = task.get('time_start')
                    if time_start:
                        start_time = datetime.fromtimestamp(time_start, tz=timezone.utc)
                        runtime = current_time - start_time
                        
                        if runtime > timedelta(minutes=max_runtime_minutes):
                            stuck_tasks.append({
                                'worker': worker,
                                'task_id': task.get('id'),
                                'task_name': task.get('name'),
                                'runtime_minutes': runtime.total_seconds() / 60,
                                'args': task.get('args'),
                                'kwargs': task.get('kwargs')
                            })
        
        except Exception as e:
            logger.error(f"Failed to find stuck tasks: {e}")
        
        return stuck_tasks
    
    def get_task_history(self, task_name: Optional[str] = None, 
                        hours: int = 24) -> Dict[str, Any]:
        """Get task execution history (requires result backend)."""
        try:
            # This would typically require a more sophisticated monitoring setup
            # For now, return basic info
            return {
                'message': 'Task history requires external monitoring setup',
                'suggestion': 'Consider using Flower or similar monitoring tool'
            }
        except Exception as e:
            logger.error(f"Failed to get task history: {e}")
            return {'error': str(e)}
    
    def purge_queue(self, queue_name: str) -> Dict[str, Any]:
        """Purge all tasks from a specific queue."""
        try:
            purged_count = self.celery_app.control.purge()
            
            logger.warning(
                f"Queue {queue_name} purged",
                extra={'purged_count': purged_count}
            )
            
            return {
                'status': 'success',
                'queue_name': queue_name,
                'purged_count': purged_count
            }
            
        except Exception as e:
            logger.error(f"Failed to purge queue {queue_name}: {e}")
            return {
                'status': 'error',
                'queue_name': queue_name,
                'error': str(e)
            }
    
    def get_failed_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recently failed tasks."""
        try:
            # This would typically require result backend or external monitoring
            # For now, return dead letter tasks as proxy for failed tasks
            from app.workers.dead_letter import get_dead_letter_tasks
            
            return get_dead_letter_tasks(status='pending', limit=limit)
            
        except Exception as e:
            logger.error(f"Failed to get failed tasks: {e}")
            return []


def create_monitoring_tasks():
    """Create periodic monitoring tasks."""
    
    def monitor_queue_health():
        """Periodic task to monitor queue health."""
        try:
            monitor = TaskQueueMonitor()
            stats = monitor.get_queue_stats()
            
            # Log health status
            health_status = stats.get('health_status', 'unknown')
            
            if health_status == 'critical':
                logger.critical("Task queue health is CRITICAL", extra=stats)
            elif health_status == 'degraded':
                logger.warning("Task queue health is DEGRADED", extra=stats)
            else:
                logger.info(f"Task queue health is {health_status.upper()}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Queue health monitoring failed: {e}")
            raise
    
    def cleanup_old_results(days_old: int = 7):
        """Clean up old task results."""
        try:
            # Clean up Celery result backend
            from celery.result import AsyncResult
            
            # This is a simplified cleanup - in production you might want
            # more sophisticated cleanup based on your result backend
            logger.info(f"Cleaning up task results older than {days_old} days")
            
            # Clean up dead letter tasks
            from app.workers.dead_letter import cleanup_old_dead_letter_tasks
            cleanup_result = cleanup_old_dead_letter_tasks.delay(days_old)
            
            return {
                'status': 'completed',
                'dead_letter_cleanup_task_id': cleanup_result.id
            }
            
        except Exception as e:
            logger.error(f"Result cleanup failed: {e}")
            raise
    
    return {
        'monitor_queue_health': monitor_queue_health,
        'cleanup_old_results': cleanup_old_results
    }


# Create monitoring task instances
monitoring_tasks = create_monitoring_tasks()


def setup_periodic_monitoring():
    """Set up periodic monitoring tasks."""
    try:
        from celery.schedules import crontab
        from celery_app import celery
        
        # Add to Celery beat schedule
        celery.conf.beat_schedule = {
            'monitor-queue-health': {
                'task': 'app.workers.monitoring.monitor_queue_health',
                'schedule': crontab(minute='*/5'),  # Every 5 minutes
            },
            'cleanup-old-results': {
                'task': 'app.workers.monitoring.cleanup_old_results',
                'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
                'kwargs': {'days_old': 7}
            },
        }
        
        logger.info("Periodic monitoring tasks configured")
        
    except Exception as e:
        logger.error(f"Failed to setup periodic monitoring: {e}")


# Health check function for API endpoints
def get_queue_health() -> Dict[str, Any]:
    """Get queue health for API health checks."""
    try:
        monitor = TaskQueueMonitor()
        stats = monitor.get_queue_stats()
        
        return {
            'status': stats.get('health_status', 'unknown'),
            'timestamp': stats.get('timestamp'),
            'workers_count': len(stats.get('workers', {}).get('worker_details', {})),
            'active_tasks_count': stats.get('queues', {}).get('active_tasks_count', 0),
            'dead_letter_pending': stats.get('dead_letter', {}).get('pending_count', 0)
        }
        
    except Exception as e:
        logger.error(f"Failed to get queue health: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }