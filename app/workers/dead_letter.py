"""Dead letter queue handler for failed tasks."""
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from app import db
from app.models.dead_letter import DeadLetterTask
from app.workers.base import BaseWorker

logger = logging.getLogger(__name__)


def _process_dead_letter_task_logic(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """Core logic for processing dead letter tasks."""
    # Store the dead letter task in database
    dead_letter_task = DeadLetterTask(
        task_id=task_data['task_id'],
        original_task_name=task_data['original_task'],
        args=task_data.get('args'),
        kwargs=task_data.get('kwargs'),
        exception=task_data.get('exception'),
        failure_reason=task_data.get('failure_reason', 'unknown')
    )
    
    db.session.add(dead_letter_task)
    db.session.commit()
    
    logger.error(
        f"Dead letter task stored: {task_data['original_task']}",
        extra={
            'dead_letter_id': dead_letter_task.id,
            'original_task_id': task_data['task_id'],
            'original_task_name': task_data['original_task'],
            'failure_reason': task_data.get('failure_reason')
        }
    )
    
    # Optionally send notification about dead letter task
    _notify_dead_letter_task(dead_letter_task)
    
    return {
        'dead_letter_id': dead_letter_task.id,
        'status': 'stored',
        'original_task': task_data['original_task']
    }


def process_dead_letter_task(task_data: Dict[str, Any]):
    """Process a task that has been sent to the dead letter queue."""
    try:
        return _process_dead_letter_task_logic(task_data)
    except Exception as e:
        logger.error(f"Failed to process dead letter task: {e}")
        raise


def retry_dead_letter_task(dead_letter_id: int, max_retries: int = 1):
    """Retry a task from the dead letter queue."""
    try:
        dead_letter_task = DeadLetterTask.query.get(dead_letter_id)
        if not dead_letter_task:
            raise ValueError(f"Dead letter task {dead_letter_id} not found")
        
        if dead_letter_task.retry_count >= max_retries:
            logger.warning(f"Dead letter task {dead_letter_id} exceeded max retries")
            return {'status': 'max_retries_exceeded'}
        
        # Attempt to re-queue the original task
        original_task_name = dead_letter_task.original_task_name
        
        # Get the original task
        from celery_app import celery
        task_func = celery.tasks.get(original_task_name)
        if not task_func:
            raise ValueError(f"Original task {original_task_name} not found")
        
        # Re-queue the task
        result = task_func.apply_async(
            args=dead_letter_task.args or [],
            kwargs=dead_letter_task.kwargs or {}
        )
        
        # Update dead letter task
        dead_letter_task.retry_count += 1
        dead_letter_task.processed_at = datetime.now(timezone.utc)
        dead_letter_task.status = 'retried'
        db.session.commit()
        
        logger.info(
            f"Dead letter task {dead_letter_id} retried as {result.id}",
            extra={
                'dead_letter_id': dead_letter_id,
                'new_task_id': result.id,
                'retry_count': dead_letter_task.retry_count
            }
        )
        
        return {
            'status': 'retried',
            'new_task_id': result.id,
            'retry_count': dead_letter_task.retry_count
        }
        
    except Exception as e:
        logger.error(f"Failed to retry dead letter task {dead_letter_id}: {e}")
        raise


def _cleanup_old_dead_letter_tasks_logic(days_old: int = 30) -> Dict[str, Any]:
    """Core logic for cleaning up old dead letter tasks."""
    from datetime import timedelta
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
    
    old_tasks = DeadLetterTask.query.filter(
        DeadLetterTask.created_at < cutoff_date,
        DeadLetterTask.status.in_(['processed', 'failed'])
    ).all()
    
    count = len(old_tasks)
    
    for task in old_tasks:
        db.session.delete(task)
    
    db.session.commit()
    
    logger.info(f"Cleaned up {count} old dead letter tasks")
    
    return {
        'status': 'completed',
        'cleaned_count': count,
        'cutoff_date': cutoff_date.isoformat()
    }


def cleanup_old_dead_letter_tasks(days_old: int = 30):
    """Clean up old dead letter tasks."""
    try:
        return _cleanup_old_dead_letter_tasks_logic(days_old)
    except Exception as e:
        logger.error(f"Failed to cleanup old dead letter tasks: {e}")
        raise


def _notify_dead_letter_task(dead_letter_task: DeadLetterTask):
    """Send notification about dead letter task (optional)."""
    try:
        # This could send an email, Slack message, etc.
        # For now, just log it
        logger.warning(
            f"Dead letter task notification: {dead_letter_task.original_task_name}",
            extra={
                'dead_letter_id': dead_letter_task.id,
                'task_id': dead_letter_task.task_id,
                'failure_reason': dead_letter_task.failure_reason
            }
        )
    except Exception as e:
        logger.error(f"Failed to send dead letter notification: {e}")


def get_dead_letter_stats() -> Dict[str, Any]:
    """Get statistics about dead letter tasks."""
    try:
        total_count = DeadLetterTask.query.count()
        pending_count = DeadLetterTask.query.filter_by(status='pending').count()
        processed_count = DeadLetterTask.query.filter_by(status='processed').count()
        failed_count = DeadLetterTask.query.filter_by(status='failed').count()
        
        # Get most common failure reasons
        from sqlalchemy import func
        failure_reasons = db.session.query(
            DeadLetterTask.failure_reason,
            func.count(DeadLetterTask.id).label('count')
        ).group_by(DeadLetterTask.failure_reason).all()
        
        return {
            'total_count': total_count,
            'pending_count': pending_count,
            'processed_count': processed_count,
            'failed_count': failed_count,
            'failure_reasons': [
                {'reason': reason, 'count': count}
                for reason, count in failure_reasons
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get dead letter stats: {e}")
        return {
            'error': str(e)
        }


def get_dead_letter_tasks(status: str = None, limit: int = 100) -> list:
    """Get dead letter tasks with optional filtering."""
    try:
        query = DeadLetterTask.query
        
        if status:
            query = query.filter_by(status=status)
        
        tasks = query.order_by(DeadLetterTask.created_at.desc()).limit(limit).all()
        
        return [
            {
                'id': task.id,
                'task_id': task.task_id,
                'original_task_name': task.original_task_name,
                'failure_reason': task.failure_reason,
                'created_at': task.created_at.isoformat(),
                'processed_at': task.processed_at.isoformat() if task.processed_at else None,
                'retry_count': task.retry_count,
                'status': task.status
            }
            for task in tasks
        ]
        
    except Exception as e:
        logger.error(f"Failed to get dead letter tasks: {e}")
        return []