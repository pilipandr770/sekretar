"""
Simple unit tests for task and activity management functionality.
Tests requirement 3.4: Task and activity management for leads.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from app.models.task import Task
from app.models.note import Note


class TestTaskModel:
    """Test Task model functionality without database dependencies."""
    
    def test_task_properties(self):
        """Test task property calculations."""
        # Create mock task
        task = Task()
        task.status = 'pending'
        task.due_date = None
        task.completed_at = None
        
        # Test completion status
        assert task.is_completed is False
        
        task.status = 'completed'
        assert task.is_completed is True
        
        # Test overdue calculation with no due date
        task.status = 'pending'
        assert task.is_overdue is False
        
        # Test overdue with past due date
        past_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
        task.due_date = past_date
        assert task.is_overdue is True
        
        # Test not overdue with future due date
        future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
        task.due_date = future_date
        assert task.is_overdue is False
        
        # Test completed task is not overdue
        task.status = 'completed'
        task.due_date = past_date
        assert task.is_overdue is False
    
    def test_task_due_today(self):
        """Test due today calculation."""
        task = Task()
        task.status = 'pending'
        task.completed_at = None
        
        # Test with no due date
        task.due_date = None
        assert task.is_due_today is False
        
        # Test with today's date
        today = datetime.utcnow().replace(hour=14, minute=30)
        task.due_date = today.isoformat()
        assert task.is_due_today is True
        
        # Test with yesterday's date
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        task.due_date = yesterday
        assert task.is_due_today is False
        
        # Test with tomorrow's date
        tomorrow = (datetime.utcnow() + timedelta(days=1)).isoformat()
        task.due_date = tomorrow
        assert task.is_due_today is False
        
        # Test completed task is not due today
        task.status = 'completed'
        task.due_date = today.isoformat()
        assert task.is_due_today is False
    
    def test_task_metadata_operations(self):
        """Test task metadata operations."""
        task = Task()
        task.extra_data = {}
        
        # Test setting metadata
        task.set_metadata('priority_reason', 'Client urgency')
        task.set_metadata('estimated_hours', 4)
        
        assert task.get_metadata('priority_reason') == 'Client urgency'
        assert task.get_metadata('estimated_hours') == 4
        assert task.get_metadata('nonexistent') is None
        assert task.get_metadata('nonexistent', 'default') == 'default'
        
        # Test with None extra_data
        task.extra_data = None
        task.set_metadata('new_key', 'new_value')
        assert task.extra_data == {'new_key': 'new_value'}
    
    def test_task_tag_operations(self):
        """Test task tag operations."""
        task = Task()
        task.tags = []
        
        # Test adding tags
        task.add_tag('urgent')
        task.add_tag('client-call')
        task.add_tag('urgent')  # Duplicate should not be added
        
        assert len(task.tags) == 2
        assert 'urgent' in task.tags
        assert 'client-call' in task.tags
        assert task.has_tag('urgent') is True
        assert task.has_tag('nonexistent') is False
        
        # Test removing tags
        task.remove_tag('urgent')
        assert 'urgent' not in task.tags
        assert task.has_tag('urgent') is False
        
        # Test with None tags
        task.tags = None
        task.add_tag('new-tag')
        assert task.tags == ['new-tag']
    
    def test_task_status_transitions(self):
        """Test task status transition methods."""
        task = Task()
        task.status = 'pending'
        task.completed_at = None
        
        # Test starting task
        task.start()
        assert task.status == 'in_progress'
        
        # Test completing task
        task.complete()
        assert task.status == 'completed'
        assert task.completed_at is not None
        
        # Test reopening task
        task.reopen()
        assert task.status == 'pending'
        assert task.completed_at is None
        
        # Test cancelling task
        task.cancel()
        assert task.status == 'cancelled'
    
    def test_task_assignment_operations(self):
        """Test task assignment operations."""
        task = Task()
        task.assigned_to_id = None
        
        # Test assigning task
        task.assign_to_user(123)
        assert task.assigned_to_id == 123
        
        # Test unassigning task
        task.unassign()
        assert task.assigned_to_id is None
    
    def test_task_basic_properties(self):
        """Test task basic property calculations."""
        task = Task()
        task.id = 1
        task.title = 'Test Task'
        task.status = 'pending'
        task.due_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
        task.extra_data = {'test': 'value'}
        task.tags = ['test', 'unit']
        
        # Test basic properties
        assert task.id == 1
        assert task.title == 'Test Task'
        assert task.status == 'pending'
        assert task.is_completed is False
        assert task.is_overdue is False
        assert task.is_due_today is False
        assert task.extra_data == {'test': 'value'}
        assert task.tags == ['test', 'unit']


class TestTaskBusinessLogic:
    """Test task business logic and workflows."""
    
    def test_task_creation_workflow(self):
        """Test task creation workflow with real company data simulation."""
        # Simulate real company data
        company_data = {
            'name': 'SAP SE',
            'country_code': 'DE',
            'vat_number': 'DE143593636',
            'industry': 'Technology'
        }
        
        # Create task with company context
        task = Task()
        task.title = f'Discovery call with {company_data["name"]}'
        task.description = f'Initial discovery call with {company_data["name"]} in {company_data["country_code"]}'
        task.task_type = 'call'
        task.priority = 'high'
        task.status = 'pending'
        task.due_date = (datetime.utcnow() + timedelta(days=3)).isoformat()
        
        # Set company metadata
        task.set_metadata('company_name', company_data['name'])
        task.set_metadata('company_country', company_data['country_code'])
        task.set_metadata('company_vat', company_data['vat_number'])
        task.set_metadata('company_industry', company_data['industry'])
        
        # Add relevant tags
        task.add_tag('discovery')
        task.add_tag('high-priority')
        task.add_tag(f'country-{company_data["country_code"].lower()}')
        task.add_tag(f'industry-{company_data["industry"].lower()}')
        
        # Verify task setup
        assert company_data['name'] in task.title
        assert task.task_type == 'call'
        assert task.priority == 'high'
        assert task.get_metadata('company_name') == company_data['name']
        assert task.get_metadata('company_country') == company_data['country_code']
        assert task.has_tag('discovery')
        assert task.has_tag('country-de')
        assert task.has_tag('industry-technology')
    
    def test_task_assignment_workflow(self):
        """Test task assignment workflow."""
        # Create task
        task = Task()
        task.title = 'Assignment test task'
        task.status = 'pending'
        
        # Simulate user IDs
        sales_rep_id = 100
        manager_id = 200
        
        # Initial assignment
        task.assign_to_user(sales_rep_id)
        assert task.assigned_to_id == sales_rep_id
        
        # Track assignment change
        assignment_history = []
        assignment_history.append({
            'from_user_id': None,
            'to_user_id': sales_rep_id,
            'timestamp': datetime.utcnow().isoformat(),
            'reason': 'Initial assignment'
        })
        
        # Reassign to manager
        old_assignee = task.assigned_to_id
        task.assign_to_user(manager_id)
        assignment_history.append({
            'from_user_id': old_assignee,
            'to_user_id': manager_id,
            'timestamp': datetime.utcnow().isoformat(),
            'reason': 'Escalation to manager'
        })
        
        # Store assignment history in metadata
        task.set_metadata('assignment_history', assignment_history)
        
        # Verify assignment tracking
        history = task.get_metadata('assignment_history')
        assert len(history) == 2
        assert history[0]['to_user_id'] == sales_rep_id
        assert history[1]['to_user_id'] == manager_id
        assert history[1]['from_user_id'] == sales_rep_id
    
    def test_task_lifecycle_tracking(self):
        """Test complete task lifecycle with activity tracking."""
        task = Task()
        task.title = 'Lifecycle test task'
        task.status = 'pending'
        task.priority = 'medium'
        
        # Track lifecycle events
        lifecycle_events = []
        
        # Task creation
        lifecycle_events.append({
            'event': 'created',
            'timestamp': datetime.utcnow().isoformat(),
            'status': task.status,
            'priority': task.priority
        })
        
        # Start task
        task.start()
        lifecycle_events.append({
            'event': 'started',
            'timestamp': datetime.utcnow().isoformat(),
            'status': task.status,
            'previous_status': 'pending'
        })
        
        # Update priority
        old_priority = task.priority
        task.priority = 'high'
        lifecycle_events.append({
            'event': 'priority_changed',
            'timestamp': datetime.utcnow().isoformat(),
            'old_priority': old_priority,
            'new_priority': task.priority,
            'reason': 'Client urgency increased'
        })
        
        # Complete task
        task.complete()
        lifecycle_events.append({
            'event': 'completed',
            'timestamp': datetime.utcnow().isoformat(),
            'status': task.status,
            'completed_at': task.completed_at
        })
        
        # Store lifecycle in metadata
        task.set_metadata('lifecycle_events', lifecycle_events)
        
        # Verify lifecycle tracking
        events = task.get_metadata('lifecycle_events')
        assert len(events) == 4
        
        event_types = [event['event'] for event in events]
        assert 'created' in event_types
        assert 'started' in event_types
        assert 'priority_changed' in event_types
        assert 'completed' in event_types
        
        # Verify priority change details
        priority_event = next(e for e in events if e['event'] == 'priority_changed')
        assert priority_event['old_priority'] == 'medium'
        assert priority_event['new_priority'] == 'high'
        assert priority_event['reason'] == 'Client urgency increased'
    
    def test_task_time_tracking(self):
        """Test task time tracking functionality."""
        task = Task()
        task.title = 'Time tracking test task'
        
        # Initialize time tracking
        task.set_metadata('time_tracking_enabled', True)
        task.set_metadata('time_entries', [])
        task.set_metadata('total_time_spent', 0)
        
        # Simulate time entries
        time_entries = []
        
        # First work session
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=2, minutes=30)
        time_entries.append({
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_minutes': 150,
            'description': 'Research and initial planning',
            'user_id': 100
        })
        
        # Second work session
        start_time = datetime.utcnow() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1, minutes=45)
        time_entries.append({
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_minutes': 105,
            'description': 'Implementation and testing',
            'user_id': 100
        })
        
        # Update task with time tracking data
        total_time = sum(entry['duration_minutes'] for entry in time_entries)
        task.set_metadata('time_entries', time_entries)
        task.set_metadata('total_time_spent', total_time)
        
        # Verify time tracking
        assert task.get_metadata('time_tracking_enabled') is True
        assert len(task.get_metadata('time_entries')) == 2
        assert task.get_metadata('total_time_spent') == 255  # 4 hours 15 minutes
        
        # Verify individual entries
        entries = task.get_metadata('time_entries')
        assert entries[0]['duration_minutes'] == 150
        assert entries[1]['duration_minutes'] == 105
        assert 'Research and initial planning' in entries[0]['description']
        assert 'Implementation and testing' in entries[1]['description']


class TestActivityNoteModel:
    """Test Note model for activity tracking."""
    
    def test_activity_note_creation(self):
        """Test creating activity notes for task tracking."""
        # Create activity note
        note = Note()
        note.title = 'Task Status Changed'
        note.content = 'Task status changed from pending to in_progress'
        note.note_type = 'activity'
        note.is_private = False
        
        # Set activity metadata
        note.extra_data = {
            'related_task_id': 123,
            'activity_type': 'status_change',
            'old_status': 'pending',
            'new_status': 'in_progress',
            'changed_by_user_id': 100
        }
        
        # Add activity tags
        note.tags = ['activity', 'status-change', 'automated']
        
        # Verify note setup
        assert note.note_type == 'activity'
        assert note.is_private is False
        assert note.extra_data['related_task_id'] == 123
        assert note.extra_data['activity_type'] == 'status_change'
        assert 'activity' in note.tags
    
    def test_activity_note_metadata_operations(self):
        """Test activity note metadata operations."""
        note = Note()
        note.extra_data = {}
        
        # Test setting activity metadata
        note.set_metadata('related_task_id', 456)
        note.set_metadata('activity_type', 'assignment_change')
        note.set_metadata('company_name', 'Test Company')
        note.set_metadata('timestamp', datetime.utcnow().isoformat())
        
        assert note.get_metadata('related_task_id') == 456
        assert note.get_metadata('activity_type') == 'assignment_change'
        assert note.get_metadata('company_name') == 'Test Company'
        assert note.get_metadata('timestamp') is not None
    
    def test_activity_note_types(self):
        """Test different types of activity notes."""
        activity_types = [
            {
                'type': 'task_created',
                'title': 'Task Created',
                'content': 'New task created for lead',
                'metadata': {'task_id': 1, 'lead_id': 10}
            },
            {
                'type': 'task_started',
                'title': 'Task Started',
                'content': 'Work began on task',
                'metadata': {'task_id': 1, 'started_by': 100}
            },
            {
                'type': 'task_completed',
                'title': 'Task Completed',
                'content': 'Task successfully completed',
                'metadata': {'task_id': 1, 'completed_by': 100, 'completion_time': datetime.utcnow().isoformat()}
            },
            {
                'type': 'priority_changed',
                'title': 'Priority Updated',
                'content': 'Task priority changed from medium to high',
                'metadata': {'task_id': 1, 'old_priority': 'medium', 'new_priority': 'high'}
            },
            {
                'type': 'assignment_changed',
                'title': 'Assignment Updated',
                'content': 'Task reassigned to different user',
                'metadata': {'task_id': 1, 'old_assignee': 100, 'new_assignee': 200}
            }
        ]
        
        created_notes = []
        for activity in activity_types:
            note = Note()
            note.title = activity['title']
            note.content = activity['content']
            note.note_type = 'activity'
            note.extra_data = {
                'activity_type': activity['type'],
                **activity['metadata']
            }
            note.tags = ['activity', activity['type'].replace('_', '-')]
            
            created_notes.append(note)
        
        # Verify all activity types were created
        assert len(created_notes) == 5
        
        # Verify specific activity types
        creation_note = next(n for n in created_notes if n.extra_data['activity_type'] == 'task_created')
        assert creation_note.title == 'Task Created'
        assert creation_note.extra_data['task_id'] == 1
        assert creation_note.extra_data['lead_id'] == 10
        
        priority_note = next(n for n in created_notes if n.extra_data['activity_type'] == 'priority_changed')
        assert priority_note.extra_data['old_priority'] == 'medium'
        assert priority_note.extra_data['new_priority'] == 'high'
        
        completion_note = next(n for n in created_notes if n.extra_data['activity_type'] == 'task_completed')
        assert completion_note.extra_data['completed_by'] == 100
        assert 'completion_time' in completion_note.extra_data


class TestTaskActivityIntegration:
    """Test integration between tasks and activity tracking."""
    
    def test_task_with_activity_logging(self):
        """Test task operations with automatic activity logging."""
        # Create task
        task = Task()
        task.id = 1
        task.title = 'Integration test task'
        task.status = 'pending'
        task.priority = 'medium'
        task.assigned_to_id = 100
        
        # Initialize activity log
        activity_log = []
        
        # Function to log activity
        def log_activity(activity_type, title, content, metadata=None):
            activity_log.append({
                'activity_type': activity_type,
                'title': title,
                'content': content,
                'timestamp': datetime.utcnow().isoformat(),
                'task_id': task.id,
                'metadata': metadata or {}
            })
        
        # Log task creation
        log_activity(
            'task_created',
            'Task Created',
            f'Created task: {task.title}',
            {'priority': task.priority, 'assigned_to': task.assigned_to_id}
        )
        
        # Start task and log activity
        old_status = task.status
        task.start()
        log_activity(
            'task_started',
            'Task Started',
            f'Started working on task: {task.title}',
            {'old_status': old_status, 'new_status': task.status}
        )
        
        # Change priority and log activity
        old_priority = task.priority
        task.priority = 'high'
        log_activity(
            'priority_changed',
            'Priority Updated',
            f'Task priority changed from {old_priority} to {task.priority}',
            {'old_priority': old_priority, 'new_priority': task.priority}
        )
        
        # Complete task and log activity
        old_status = task.status
        task.complete()
        log_activity(
            'task_completed',
            'Task Completed',
            f'Successfully completed task: {task.title}',
            {'old_status': old_status, 'completion_time': task.completed_at}
        )
        
        # Store activity log in task metadata
        task.set_metadata('activity_log', activity_log)
        
        # Verify activity logging
        logged_activities = task.get_metadata('activity_log')
        assert len(logged_activities) == 4
        
        # Verify activity types
        activity_types = [activity['activity_type'] for activity in logged_activities]
        assert 'task_created' in activity_types
        assert 'task_started' in activity_types
        assert 'priority_changed' in activity_types
        assert 'task_completed' in activity_types
        
        # Verify specific activity details
        creation_activity = next(a for a in logged_activities if a['activity_type'] == 'task_created')
        assert creation_activity['metadata']['priority'] == 'medium'
        assert creation_activity['metadata']['assigned_to'] == 100
        
        priority_activity = next(a for a in logged_activities if a['activity_type'] == 'priority_changed')
        assert priority_activity['metadata']['old_priority'] == 'medium'
        assert priority_activity['metadata']['new_priority'] == 'high'
        
        completion_activity = next(a for a in logged_activities if a['activity_type'] == 'task_completed')
        assert completion_activity['metadata']['completion_time'] == task.completed_at
    
    def test_task_reminder_functionality(self):
        """Test task reminder functionality."""
        task = Task()
        task.title = 'Reminder test task'
        task.due_date = (datetime.utcnow() + timedelta(days=2)).isoformat()
        
        # Set up reminder configuration
        reminder_config = {
            'enabled': True,
            'hours_before': [24, 4, 1],  # Remind 24h, 4h, and 1h before due
            'methods': ['email', 'notification'],
            'sent_reminders': []
        }
        
        task.set_metadata('reminder_config', reminder_config)
        
        # Simulate reminder processing
        due_date = datetime.fromisoformat(task.due_date.replace('Z', '+00:00'))
        current_time = datetime.utcnow()
        
        # Check if reminders should be sent
        for hours_before in reminder_config['hours_before']:
            reminder_time = due_date - timedelta(hours=hours_before)
            
            # Simulate time passing to reminder time
            if current_time >= reminder_time:
                # Send reminder (simulated)
                reminder_sent = {
                    'hours_before': hours_before,
                    'sent_at': current_time.isoformat(),
                    'methods': reminder_config['methods'],
                    'task_id': task.id if hasattr(task, 'id') else None
                }
                
                reminder_config['sent_reminders'].append(reminder_sent)
        
        # Update task with reminder status
        task.set_metadata('reminder_config', reminder_config)
        
        # Verify reminder configuration
        config = task.get_metadata('reminder_config')
        assert config['enabled'] is True
        assert len(config['hours_before']) == 3
        assert 'email' in config['methods']
        assert 'notification' in config['methods']
    
    def test_task_performance_metrics(self):
        """Test task performance metrics tracking."""
        task = Task()
        task.title = 'Performance metrics test task'
        task.status = 'completed'
        task.priority = 'high'
        
        # Set task dates
        created_at = datetime.utcnow() - timedelta(days=5)
        started_at = created_at + timedelta(hours=2)
        completed_at = started_at + timedelta(days=3, hours=4)
        
        task.created_at = created_at.isoformat()
        task.completed_at = completed_at.isoformat()
        
        # Calculate performance metrics
        total_duration = completed_at - created_at
        work_duration = completed_at - started_at
        
        metrics = {
            'total_duration_hours': total_duration.total_seconds() / 3600,
            'work_duration_hours': work_duration.total_seconds() / 3600,
            'created_at': created_at.isoformat(),
            'started_at': started_at.isoformat(),
            'completed_at': completed_at.isoformat(),
            'priority': task.priority,
            'status': task.status,
            'efficiency_score': 85,  # Simulated score
            'quality_score': 92      # Simulated score
        }
        
        task.set_metadata('performance_metrics', metrics)
        
        # Verify metrics
        stored_metrics = task.get_metadata('performance_metrics')
        assert stored_metrics['total_duration_hours'] > 0
        assert stored_metrics['work_duration_hours'] > 0
        assert stored_metrics['priority'] == 'high'
        assert stored_metrics['status'] == 'completed'
        assert stored_metrics['efficiency_score'] == 85
        assert stored_metrics['quality_score'] == 92