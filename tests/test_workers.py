"""Tests for worker functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone

from app import create_app, db
from app.models.dead_letter import DeadLetterTask
from app.workers.base import BaseWorker, MonitoredWorker, get_task_status, revoke_task
from app.workers.dead_letter import (
    process_dead_letter_task, 
    retry_dead_letter_task,
    cleanup_old_dead_letter_tasks,
    get_dead_letter_stats
)
from app.workers.monitoring import TaskQueueMonitor, get_queue_health


class TestBaseWorker:
    """Test base worker functionality."""
    
    def test_base_worker_initialization(self):
        """Test BaseWorker initialization."""
        worker = BaseWorker()
        assert hasattr(worker, 'logger')
        assert worker.autoretry_for == (Exception,)
        assert worker.retry_kwargs['max_retries'] == 3
        assert worker.retry_kwargs['countdown'] == 60
    
    def test_monitored_worker_initialization(self):
        """Test MonitoredWorker initialization."""
        worker = MonitoredWorker()
        assert hasattr(worker, 'logger')
        assert hasattr(worker, 'metrics')
        assert isinstance(worker.metrics, dict)
    
    def test_base_worker_on_failure(self):
        """Test BaseWorker failure handling."""
        worker = BaseWorker()
        worker.name = 'test_task'
        
        # Mock the logger to avoid the LogRecord conflict
        with patch.object(worker, 'logger') as mock_logger:
            exc = Exception("Test error")
            task_id = "test-task-123"
            args = (1, 2, 3)
            kwargs = {'key': 'value'}
            einfo = Mock()
            einfo.__str__ = Mock(return_value="Error info")
            
            worker.on_failure(exc, task_id, args, kwargs, einfo)
            
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "failed permanently" in call_args[0][0]
    
    def test_base_worker_on_retry(self):
        """Test BaseWorker retry handling."""
        worker = BaseWorker()
        worker.name = 'test_task'
        
        # Mock the worker's logger directly
        with patch.object(worker, 'logger') as mock_logger:
            # Mock the request attribute properly
            with patch.object(type(worker), 'request', new_callable=lambda: Mock()) as mock_request:
                mock_request.retries = 1
                worker.max_retries = 3
            
                exc = Exception("Test error")
                task_id = "test-task-123"
                args = (1, 2, 3)
                kwargs = {'key': 'value'}
                einfo = Mock()
                
                worker.on_retry(exc, task_id, args, kwargs, einfo)
                
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args
                assert "retrying" in call_args[0][0]


class TestDeadLetterQueue:
    """Test dead letter queue functionality."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    def test_dead_letter_task_model(self, app):
        """Test DeadLetterTask model."""
        with app.app_context():
            task = DeadLetterTask(
                task_id='test-123',
                original_task_name='test.task',
                args=[1, 2, 3],
                kwargs={'key': 'value'},
                exception='Test exception',
                failure_reason='max_retries_exceeded'
            )
            
            db.session.add(task)
            db.session.commit()
            
            # Test retrieval
            retrieved = DeadLetterTask.query.filter_by(task_id='test-123').first()
            assert retrieved is not None
            assert retrieved.original_task_name == 'test.task'
            assert retrieved.args == [1, 2, 3]
            assert retrieved.kwargs == {'key': 'value'}
            assert retrieved.status == 'pending'
    
    def test_process_dead_letter_task(self, app):
        """Test processing dead letter task."""
        with app.app_context():
            task_data = {
                'task_id': 'test-123',
                'original_task': 'test.task',
                'args': [1, 2, 3],
                'kwargs': {'key': 'value'},
                'exception': 'Test exception',
                'failure_reason': 'max_retries_exceeded'
            }
            
            # Test the core logic function
            from app.workers.dead_letter import _process_dead_letter_task_logic
            
            result = _process_dead_letter_task_logic(task_data)
            
            assert result['status'] == 'stored'
            assert result['original_task'] == 'test.task'
            
            # Verify the task was stored in database
            stored_task = DeadLetterTask.query.filter_by(task_id='test-123').first()
            assert stored_task is not None
            assert stored_task.original_task_name == 'test.task'
            assert stored_task.args == [1, 2, 3]
            assert stored_task.kwargs == {'key': 'value'}
    
    def test_get_dead_letter_stats(self, app):
        """Test getting dead letter statistics."""
        with app.app_context():
            # Create test data
            task1 = DeadLetterTask(
                task_id='test-1',
                original_task_name='test.task1',
                status='pending',
                failure_reason='timeout'
            )
            task2 = DeadLetterTask(
                task_id='test-2',
                original_task_name='test.task2',
                status='processed',
                failure_reason='timeout'
            )
            task3 = DeadLetterTask(
                task_id='test-3',
                original_task_name='test.task3',
                status='pending',
                failure_reason='max_retries_exceeded'
            )
            
            db.session.add_all([task1, task2, task3])
            db.session.commit()
            
            stats = get_dead_letter_stats()
            
            assert stats['total_count'] == 3
            assert stats['pending_count'] == 2
            assert stats['processed_count'] == 1
            assert stats['failed_count'] == 0
            assert len(stats['failure_reasons']) == 2
    
    def test_cleanup_old_dead_letter_tasks(self, app):
        """Test cleanup of old dead letter tasks."""
        with app.app_context():
            # Create old task
            old_date = datetime.now(timezone.utc) - timedelta(days=35)
            old_task = DeadLetterTask(
                task_id='old-task',
                original_task_name='old.task',
                status='processed',
                created_at=old_date
            )
            
            # Create recent task
            recent_task = DeadLetterTask(
                task_id='recent-task',
                original_task_name='recent.task',
                status='processed'
            )
            
            db.session.add_all([old_task, recent_task])
            db.session.commit()
            
            # Test the core logic function
            from app.workers.dead_letter import _cleanup_old_dead_letter_tasks_logic
            
            result = _cleanup_old_dead_letter_tasks_logic(days_old=30)
            
            assert result['status'] == 'completed'
            assert result['cleaned_count'] == 1
            
            # Verify old task was deleted
            remaining_tasks = DeadLetterTask.query.all()
            assert len(remaining_tasks) == 1
            assert remaining_tasks[0].task_id == 'recent-task'


class TestTaskQueueMonitoring:
    """Test task queue monitoring functionality."""
    
    @patch('app.workers.monitoring.celery')
    def test_task_queue_monitor_initialization(self, mock_celery):
        """Test TaskQueueMonitor initialization."""
        monitor = TaskQueueMonitor()
        assert monitor.celery_app == mock_celery
    
    @patch('app.workers.monitoring.get_worker_stats')
    @patch('app.workers.monitoring.get_active_tasks')
    @patch('app.workers.monitoring.get_dead_letter_stats')
    def test_get_queue_stats(self, mock_dead_letter_stats, mock_active_tasks, mock_worker_stats):
        """Test getting queue statistics."""
        # Mock return values
        mock_worker_stats.return_value = {'worker1': {'status': 'online'}}
        mock_active_tasks.return_value = {'worker1': [{'id': 'task1'}]}
        mock_dead_letter_stats.return_value = {'pending_count': 5}
        
        monitor = TaskQueueMonitor()
        
        with patch.object(monitor.celery_app.control, 'inspect') as mock_inspect:
            mock_inspect_instance = Mock()
            mock_inspect_instance.active_queues.return_value = {'worker1': ['default']}
            mock_inspect_instance.reserved.return_value = {'worker1': []}
            mock_inspect_instance.scheduled.return_value = {'worker1': []}
            mock_inspect.return_value = mock_inspect_instance
            
            stats = monitor.get_queue_stats()
            
            assert 'timestamp' in stats
            assert 'queues' in stats
            assert 'workers' in stats
            assert 'dead_letter' in stats
            assert 'health_status' in stats
            assert stats['workers']['total_workers'] == 1
    
    def test_assess_health_healthy(self):
        """Test health assessment - healthy state."""
        monitor = TaskQueueMonitor()
        
        active_tasks = {'worker1': []}
        worker_stats = {'worker1': {'status': 'online'}}
        dead_letter_stats = {'pending_count': 5}
        
        health = monitor._assess_health(active_tasks, worker_stats, dead_letter_stats)
        assert health == 'healthy'
    
    def test_assess_health_critical(self):
        """Test health assessment - critical state."""
        monitor = TaskQueueMonitor()
        
        active_tasks = {}
        worker_stats = {}  # No workers
        dead_letter_stats = {'pending_count': 5}
        
        health = monitor._assess_health(active_tasks, worker_stats, dead_letter_stats)
        assert health == 'critical'
    
    def test_assess_health_degraded(self):
        """Test health assessment - degraded state."""
        monitor = TaskQueueMonitor()
        
        active_tasks = {'worker1': []}
        worker_stats = {'worker1': {'status': 'online'}}
        dead_letter_stats = {'pending_count': 150}  # High pending count
        
        health = monitor._assess_health(active_tasks, worker_stats, dead_letter_stats)
        assert health == 'degraded'
    
    def test_find_stuck_tasks(self):
        """Test finding stuck tasks."""
        monitor = TaskQueueMonitor()
        
        # Create a task that started 2 hours ago
        two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()
        
        active_tasks = {
            'worker1': [
                {
                    'id': 'stuck-task',
                    'name': 'long.running.task',
                    'time_start': two_hours_ago,
                    'args': [],
                    'kwargs': {}
                },
                {
                    'id': 'normal-task',
                    'name': 'quick.task',
                    'time_start': datetime.now(timezone.utc).timestamp(),
                    'args': [],
                    'kwargs': {}
                }
            ]
        }
        
        stuck_tasks = monitor._find_stuck_tasks(active_tasks, max_runtime_minutes=60)
        
        assert len(stuck_tasks) == 1
        assert stuck_tasks[0]['task_id'] == 'stuck-task'
        assert stuck_tasks[0]['runtime_minutes'] > 60


class TestTaskUtilities:
    """Test task utility functions."""
    
    @patch('celery_app.celery')
    def test_get_task_status(self, mock_celery):
        """Test getting task status."""
        mock_result = Mock()
        mock_result.status = 'SUCCESS'
        mock_result.result = 'Task completed'
        mock_result.traceback = None
        mock_result.date_done = datetime.now(timezone.utc)
        mock_result.successful.return_value = True
        mock_result.failed.return_value = False
        mock_result.ready.return_value = True
        
        mock_celery.AsyncResult.return_value = mock_result
        
        status = get_task_status('test-task-123')
        
        assert status['task_id'] == 'test-task-123'
        assert status['status'] == 'SUCCESS'
        assert status['result'] == 'Task completed'
        assert status['successful'] is True
        assert status['failed'] is False
        assert status['ready'] is True
    
    @patch('celery_app.celery')
    def test_revoke_task(self, mock_celery):
        """Test revoking a task."""
        mock_celery.control.revoke = Mock()
        
        result = revoke_task('test-task-123', terminate=True)
        
        assert result is True
        mock_celery.control.revoke.assert_called_once_with('test-task-123', terminate=True)
    
    @patch('celery_app.celery')
    def test_revoke_task_failure(self, mock_celery):
        """Test revoking a task with failure."""
        mock_celery.control.revoke.side_effect = Exception("Revoke failed")
        
        result = revoke_task('test-task-123')
        
        assert result is False
    
    @patch('app.workers.monitoring.TaskQueueMonitor')
    def test_get_queue_health(self, mock_monitor_class):
        """Test getting queue health."""
        mock_monitor = Mock()
        mock_monitor.get_queue_stats.return_value = {
            'health_status': 'healthy',
            'timestamp': '2023-01-01T00:00:00',
            'workers': {'worker_details': {'worker1': {}}},
            'queues': {'active_tasks_count': 5},
            'dead_letter': {'pending_count': 2}
        }
        mock_monitor_class.return_value = mock_monitor
        
        health = get_queue_health()
        
        assert health['status'] == 'healthy'
        assert health['workers_count'] == 1
        assert health['active_tasks_count'] == 5
        assert health['dead_letter_pending'] == 2


class TestCeleryConfiguration:
    """Test Celery configuration."""
    
    @patch('celery_app.create_app')
    def test_celery_app_creation(self, mock_create_app):
        """Test Celery app creation."""
        from celery_app import create_celery_app
        
        mock_app = Mock()
        mock_app.import_name = 'test_app'
        mock_app.config = {
            'CELERY_BROKER_URL': 'redis://localhost:6379/1',
            'CELERY_RESULT_BACKEND': 'redis://localhost:6379/2'
        }
        mock_create_app.return_value = mock_app
        
        celery_app = create_celery_app(mock_app)
        
        assert celery_app is not None
        assert celery_app.main == 'test_app'
    
    def test_context_task_functionality(self):
        """Test ContextTask functionality."""
        from celery_app import create_celery_app
        
        mock_app = Mock()
        mock_app.import_name = 'test_app'
        mock_app.config = {
            'CELERY_BROKER_URL': 'redis://localhost:6379/1',
            'CELERY_RESULT_BACKEND': 'redis://localhost:6379/2'
        }
        mock_app.app_context.return_value.__enter__ = Mock()
        mock_app.app_context.return_value.__exit__ = Mock()
        
        celery_app = create_celery_app(mock_app)
        
        # Test that ContextTask is set
        assert celery_app.Task is not None
        assert hasattr(celery_app.Task, '__call__')


if __name__ == '__main__':
    pytest.main([__file__])