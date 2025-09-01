"""
Comprehensive tests for task and activity management functionality.
Tests requirement 3.4: Task and activity management for leads.
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from app.models.tenant import Tenant
from app.models.user import User
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.task import Task
from app.models.note import Note
from app.models.pipeline import Pipeline, Stage
from app import db


class TestTaskCreationAndAssignment:
    """Test task creation and assignment functionality for leads."""
    
    @pytest.fixture
    def real_company_data(self):
        """Load real company data for testing."""
        import json
        with open('comprehensive_test_dataset.json', 'r') as f:
            dataset = json.load(f)
        # Convert companies dict to list and take first 5
        companies_list = list(dataset['companies'].values())[:5]
        return companies_list
    
    @pytest.fixture
    def test_setup(self, app, real_company_data):
        """Set up test environment with real company data."""
        with app.app_context():
            # Create tenant
            tenant = Tenant(name="Test Corp", slug="test-corp")
            tenant.save()
            
            # Create users
            manager = User(
                tenant_id=tenant.id,
                email="manager@testcorp.com",
                first_name="Test",
                last_name="Manager",
                is_active=True
            )
            manager.save()
            
            sales_rep = User(
                tenant_id=tenant.id,
                email="sales@testcorp.com",
                first_name="Sales",
                last_name="Rep",
                is_active=True
            )
            sales_rep.save()
            
            # Create pipeline
            pipeline = Pipeline(
                tenant_id=tenant.id,
                name="Sales Pipeline",
                is_default=True
            )
            pipeline.save()
            
            stage = Stage(
                tenant_id=tenant.id,
                pipeline_id=pipeline.id,
                name="Qualified",
                position=1
            )
            stage.save()
            
            # Create contacts and leads from real company data
            contacts = []
            leads = []
            
            for company_data in real_company_data:
                contact = Contact(
                    tenant_id=tenant.id,
                    first_name="Contact",
                    last_name=f"From {company_data['name'][:20]}",
                    company=company_data['name'],
                    email=f"contact@{company_data['name'].lower().replace(' ', '').replace(',', '')[:20]}.com",
                    phone="+49123456789",
                    country=company_data['country_code'],
                    contact_type="prospect"
                )
                contact.save()
                contacts.append(contact)
                
                lead = Lead(
                    tenant_id=tenant.id,
                    title=f"Lead for {company_data['name'][:30]}",
                    description=f"Sales opportunity with {company_data['name']}",
                    contact_id=contact.id,
                    pipeline_id=pipeline.id,
                    stage_id=stage.id,
                    value=50000,
                    probability=60,
                    assigned_to_id=sales_rep.id
                )
                lead.save()
                leads.append(lead)
            
            return {
                'tenant': tenant,
                'manager': manager,
                'sales_rep': sales_rep,
                'pipeline': pipeline,
                'stage': stage,
                'contacts': contacts,
                'leads': leads
            }
    
    def test_create_task_for_lead_with_real_data(self, app, test_setup):
        """Test creating tasks for leads using real company data."""
        with app.app_context():
            setup = test_setup
            lead = setup['leads'][0]  # Use first lead
            manager = setup['manager']
            sales_rep = setup['sales_rep']
            
            # Test creating different types of tasks
            task_types = [
                {
                    'title': f'Call {lead.contact.company}',
                    'description': f'Initial discovery call with {lead.contact.company}',
                    'task_type': 'call',
                    'priority': 'high',
                    'category': 'sales'
                },
                {
                    'title': f'Send proposal to {lead.contact.company}',
                    'description': f'Prepare and send detailed proposal for {lead.contact.company}',
                    'task_type': 'email',
                    'priority': 'medium',
                    'category': 'proposal'
                },
                {
                    'title': f'Follow up with {lead.contact.company}',
                    'description': f'Follow up on proposal sent to {lead.contact.company}',
                    'task_type': 'follow_up',
                    'priority': 'medium',
                    'category': 'follow_up'
                }
            ]
            
            created_tasks = []
            for task_data in task_types:
                task = Task(
                    tenant_id=setup['tenant'].id,
                    lead_id=lead.id,
                    title=task_data['title'],
                    description=task_data['description'],
                    task_type=task_data['task_type'],
                    priority=task_data['priority'],
                    category=task_data['category'],
                    assigned_to_id=sales_rep.id,
                    due_date=(datetime.utcnow() + timedelta(days=3)).isoformat(),
                    status='pending'
                )
                task.save()
                created_tasks.append(task)
            
            # Verify tasks were created correctly
            assert len(created_tasks) == 3
            
            for task in created_tasks:
                assert task.id is not None
                assert task.tenant_id == setup['tenant'].id
                assert task.lead_id == lead.id
                assert task.assigned_to_id == sales_rep.id
                assert task.status == 'pending'
                assert task.lead.contact.company in task.title
                
            # Test task assignment to different users
            reassign_task = created_tasks[0]
            reassign_task.assign_to_user(manager.id)
            reassign_task.save()
            
            assert reassign_task.assigned_to_id == manager.id
            assert reassign_task.assigned_to.email == manager.email
    
    def test_task_assignment_validation(self, app, test_setup):
        """Test task assignment validation with real company data."""
        with app.app_context():
            setup = test_setup
            lead = setup['leads'][1]  # Use second lead
            
            # Test assigning task to valid user
            task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=lead.id,
                title=f'Valid assignment task for {lead.contact.company}',
                assigned_to_id=setup['sales_rep'].id
            )
            task.save()
            
            assert task.assigned_to_id == setup['sales_rep'].id
            assert task.assigned_to.full_name == "Sales Rep"
            
            # Test unassigning task
            task.unassign()
            task.save()
            
            assert task.assigned_to_id is None
            assert task.assigned_to is None
            
            # Test reassigning
            task.assign_to_user(setup['manager'].id)
            task.save()
            
            assert task.assigned_to_id == setup['manager'].id
    
    def test_bulk_task_creation_for_multiple_leads(self, app, test_setup):
        """Test creating tasks for multiple leads with real company data."""
        with app.app_context():
            setup = test_setup
            leads = setup['leads']
            
            # Create follow-up tasks for all leads
            tasks = []
            for i, lead in enumerate(leads):
                task = Task(
                    tenant_id=setup['tenant'].id,
                    lead_id=lead.id,
                    title=f'Weekly follow-up with {lead.contact.company}',
                    description=f'Regular check-in with {lead.contact.company} - Week {i+1}',
                    task_type='follow_up',
                    priority='medium',
                    assigned_to_id=setup['sales_rep'].id,
                    due_date=(datetime.utcnow() + timedelta(days=7*(i+1))).isoformat()
                )
                task.save()
                tasks.append(task)
            
            # Verify all tasks were created
            assert len(tasks) == len(leads)
            
            # Verify each task is associated with correct lead
            for task, lead in zip(tasks, leads):
                assert task.lead_id == lead.id
                assert task.lead.contact.company in task.title
                assert task.assigned_to_id == setup['sales_rep'].id
            
            # Test querying tasks by lead
            first_lead_tasks = Task.get_by_lead(leads[0].id)
            assert len(first_lead_tasks) == 1
            assert first_lead_tasks[0].lead_id == leads[0].id


class TestDueDateAndReminderFunctionality:
    """Test due date and reminder functionality for tasks."""
    
    @pytest.fixture
    def task_setup(self, app):
        """Set up tasks with various due dates."""
        with app.app_context():
            # Create tenant and user
            tenant = Tenant(name="Task Test Corp", slug="task-test")
            tenant.save()
            
            user = User(
                tenant_id=tenant.id,
                email="user@tasktest.com",
                first_name="Task",
                last_name="User",
                is_active=True
            )
            user.save()
            
            # Create contact and lead
            contact = Contact(
                tenant_id=tenant.id,
                first_name="Test",
                last_name="Contact",
                company="Test Company",
                email="test@company.com"
            )
            contact.save()
            
            pipeline = Pipeline(tenant_id=tenant.id, name="Test Pipeline", is_default=True)
            pipeline.save()
            
            stage = Stage(tenant_id=tenant.id, pipeline_id=pipeline.id, name="Test Stage", position=1)
            stage.save()
            
            lead = Lead(
                tenant_id=tenant.id,
                title="Test Lead",
                contact_id=contact.id,
                pipeline_id=pipeline.id,
                stage_id=stage.id
            )
            lead.save()
            
            return {
                'tenant': tenant,
                'user': user,
                'contact': contact,
                'lead': lead
            }
    
    def test_due_date_functionality(self, app, task_setup):
        """Test task due date functionality."""
        with app.app_context():
            setup = task_setup
            
            # Create tasks with different due dates
            now = datetime.utcnow()
            
            # Overdue task
            overdue_task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Overdue task',
                assigned_to_id=setup['user'].id,
                due_date=(now - timedelta(days=2)).isoformat(),
                status='pending'
            )
            overdue_task.save()
            
            # Due today task
            due_today_task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Due today task',
                assigned_to_id=setup['user'].id,
                due_date=now.replace(hour=23, minute=59).isoformat(),
                status='pending'
            )
            due_today_task.save()
            
            # Future task
            future_task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Future task',
                assigned_to_id=setup['user'].id,
                due_date=(now + timedelta(days=5)).isoformat(),
                status='pending'
            )
            future_task.save()
            
            # Completed overdue task (should not be considered overdue)
            completed_task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Completed overdue task',
                assigned_to_id=setup['user'].id,
                due_date=(now - timedelta(days=1)).isoformat(),
                status='completed'
            )
            completed_task.save()
            
            # Test overdue detection
            assert overdue_task.is_overdue is True
            assert due_today_task.is_overdue is False
            assert future_task.is_overdue is False
            assert completed_task.is_overdue is False
            
            # Test due today detection
            assert overdue_task.is_due_today is False
            assert due_today_task.is_due_today is True
            assert future_task.is_due_today is False
            assert completed_task.is_due_today is False
    
    def test_overdue_tasks_query(self, app, task_setup):
        """Test querying overdue tasks."""
        with app.app_context():
            setup = task_setup
            now = datetime.utcnow()
            
            # Create overdue tasks
            overdue_tasks = []
            for i in range(3):
                task = Task(
                    tenant_id=setup['tenant'].id,
                    lead_id=setup['lead'].id,
                    title=f'Overdue task {i+1}',
                    assigned_to_id=setup['user'].id,
                    due_date=(now - timedelta(days=i+1)).isoformat(),
                    status='pending'
                )
                task.save()
                overdue_tasks.append(task)
            
            # Create non-overdue task
            future_task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Future task',
                assigned_to_id=setup['user'].id,
                due_date=(now + timedelta(days=1)).isoformat(),
                status='pending'
            )
            future_task.save()
            
            # Query overdue tasks
            overdue_results = Task.get_overdue(setup['tenant'].id)
            assert len(overdue_results) == 3
            
            # Query overdue tasks for specific user
            user_overdue = Task.get_overdue(setup['tenant'].id, setup['user'].id)
            assert len(user_overdue) == 3
            
            # Verify tasks are ordered by due date
            for i in range(len(user_overdue) - 1):
                current_due = datetime.fromisoformat(user_overdue[i].due_date.replace('Z', '+00:00'))
                next_due = datetime.fromisoformat(user_overdue[i+1].due_date.replace('Z', '+00:00'))
                assert current_due <= next_due
    
    def test_due_today_tasks_query(self, app, task_setup):
        """Test querying tasks due today."""
        with app.app_context():
            setup = task_setup
            now = datetime.utcnow()
            today = now.date()
            
            # Create tasks due today at different times
            due_today_tasks = []
            for i in range(3):
                due_time = datetime.combine(today, datetime.min.time()) + timedelta(hours=8+i*2)
                task = Task(
                    tenant_id=setup['tenant'].id,
                    lead_id=setup['lead'].id,
                    title=f'Due today task {i+1}',
                    assigned_to_id=setup['user'].id,
                    due_date=due_time.isoformat(),
                    status='pending'
                )
                task.save()
                due_today_tasks.append(task)
            
            # Create task due tomorrow
            tomorrow_task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Due tomorrow task',
                assigned_to_id=setup['user'].id,
                due_date=(now + timedelta(days=1)).isoformat(),
                status='pending'
            )
            tomorrow_task.save()
            
            # Query tasks due today
            due_today_results = Task.get_due_today(setup['tenant'].id)
            assert len(due_today_results) == 3
            
            # Query tasks due today for specific user
            user_due_today = Task.get_due_today(setup['tenant'].id, setup['user'].id)
            assert len(user_due_today) == 3
    
    def test_task_reminder_metadata(self, app, task_setup):
        """Test task reminder functionality through metadata."""
        with app.app_context():
            setup = task_setup
            
            # Create task with reminder settings
            task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Task with reminders',
                assigned_to_id=setup['user'].id,
                due_date=(datetime.utcnow() + timedelta(days=3)).isoformat()
            )
            
            # Set reminder metadata
            task.set_metadata('reminder_enabled', True)
            task.set_metadata('reminder_hours_before', 24)
            task.set_metadata('reminder_sent', False)
            task.set_metadata('reminder_email', True)
            task.set_metadata('reminder_sms', False)
            task.save()
            
            # Verify reminder metadata
            assert task.get_metadata('reminder_enabled') is True
            assert task.get_metadata('reminder_hours_before') == 24
            assert task.get_metadata('reminder_sent') is False
            assert task.get_metadata('reminder_email') is True
            assert task.get_metadata('reminder_sms') is False
            
            # Test updating reminder status
            task.set_metadata('reminder_sent', True)
            task.set_metadata('reminder_sent_at', datetime.utcnow().isoformat())
            task.save()
            
            assert task.get_metadata('reminder_sent') is True
            assert task.get_metadata('reminder_sent_at') is not None


class TestActivityLoggingAndTracking:
    """Test activity logging and tracking functionality."""
    
    @pytest.fixture
    def activity_setup(self, app):
        """Set up environment for activity tracking tests."""
        with app.app_context():
            # Create tenant and users
            tenant = Tenant(name="Activity Test Corp", slug="activity-test")
            tenant.save()
            
            manager = User(
                tenant_id=tenant.id,
                email="manager@activitytest.com",
                first_name="Activity",
                last_name="Manager",
                is_active=True
            )
            manager.save()
            
            sales_rep = User(
                tenant_id=tenant.id,
                email="sales@activitytest.com",
                first_name="Sales",
                last_name="Rep",
                is_active=True
            )
            sales_rep.save()
            
            # Create contact and lead
            contact = Contact(
                tenant_id=tenant.id,
                first_name="Activity",
                last_name="Contact",
                company="Activity Company",
                email="contact@activitycompany.com"
            )
            contact.save()
            
            pipeline = Pipeline(tenant_id=tenant.id, name="Activity Pipeline", is_default=True)
            pipeline.save()
            
            stage = Stage(tenant_id=tenant.id, pipeline_id=pipeline.id, name="Activity Stage", position=1)
            stage.save()
            
            lead = Lead(
                tenant_id=tenant.id,
                title="Activity Lead",
                contact_id=contact.id,
                pipeline_id=pipeline.id,
                stage_id=stage.id,
                assigned_to_id=sales_rep.id
            )
            lead.save()
            
            return {
                'tenant': tenant,
                'manager': manager,
                'sales_rep': sales_rep,
                'contact': contact,
                'lead': lead
            }
    
    def test_task_status_change_tracking(self, app, activity_setup):
        """Test tracking task status changes as activities."""
        with app.app_context():
            setup = activity_setup
            
            # Create task
            task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Status tracking task',
                assigned_to_id=setup['sales_rep'].id,
                status='pending'
            )
            task.save()
            
            # Track status changes
            status_changes = []
            
            # Start task
            old_status = task.status
            task.start()
            task.save()
            status_changes.append({
                'from': old_status,
                'to': task.status,
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': setup['sales_rep'].id
            })
            
            # Complete task
            old_status = task.status
            task.complete()
            task.save()
            status_changes.append({
                'from': old_status,
                'to': task.status,
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': setup['sales_rep'].id
            })
            
            # Store activity log in task metadata
            task.set_metadata('status_changes', status_changes)
            task.save()
            
            # Verify activity tracking
            logged_changes = task.get_metadata('status_changes')
            assert len(logged_changes) == 2
            assert logged_changes[0]['from'] == 'pending'
            assert logged_changes[0]['to'] == 'in_progress'
            assert logged_changes[1]['from'] == 'in_progress'
            assert logged_changes[1]['to'] == 'completed'
            
            # Verify task completion timestamp
            assert task.completed_at is not None
            assert task.is_completed is True
    
    def test_task_assignment_change_tracking(self, app, activity_setup):
        """Test tracking task assignment changes."""
        with app.app_context():
            setup = activity_setup
            
            # Create task assigned to sales rep
            task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Assignment tracking task',
                assigned_to_id=setup['sales_rep'].id
            )
            task.save()
            
            # Track assignment changes
            assignment_changes = []
            
            # Reassign to manager
            old_assignee = task.assigned_to_id
            task.assign_to_user(setup['manager'].id)
            task.save()
            assignment_changes.append({
                'from_user_id': old_assignee,
                'to_user_id': task.assigned_to_id,
                'timestamp': datetime.utcnow().isoformat(),
                'changed_by': setup['manager'].id
            })
            
            # Unassign task
            old_assignee = task.assigned_to_id
            task.unassign()
            task.save()
            assignment_changes.append({
                'from_user_id': old_assignee,
                'to_user_id': None,
                'timestamp': datetime.utcnow().isoformat(),
                'changed_by': setup['manager'].id
            })
            
            # Store assignment log in task metadata
            task.set_metadata('assignment_changes', assignment_changes)
            task.save()
            
            # Verify assignment tracking
            logged_changes = task.get_metadata('assignment_changes')
            assert len(logged_changes) == 2
            assert logged_changes[0]['from_user_id'] == setup['sales_rep'].id
            assert logged_changes[0]['to_user_id'] == setup['manager'].id
            assert logged_changes[1]['from_user_id'] == setup['manager'].id
            assert logged_changes[1]['to_user_id'] is None
    
    def test_task_activity_notes_creation(self, app, activity_setup):
        """Test creating activity notes for task interactions."""
        with app.app_context():
            setup = activity_setup
            
            # Create task
            task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Activity notes task',
                assigned_to_id=setup['sales_rep'].id
            )
            task.save()
            
            # Create activity notes for different task interactions
            activity_notes = []
            
            # Note for task creation
            creation_note = Note(
                tenant_id=setup['tenant'].id,
                user_id=setup['sales_rep'].id,
                lead_id=setup['lead'].id,
                title='Task Created',
                content=f'Created task: {task.title}',
                note_type='activity',
                is_private=False
            )
            creation_note.set_metadata('related_task_id', task.id)
            creation_note.set_metadata('activity_type', 'task_created')
            creation_note.save()
            activity_notes.append(creation_note)
            
            # Note for task progress update
            progress_note = Note(
                tenant_id=setup['tenant'].id,
                user_id=setup['sales_rep'].id,
                lead_id=setup['lead'].id,
                title='Task Progress Update',
                content=f'Started working on task: {task.title}',
                note_type='activity',
                is_private=False
            )
            progress_note.set_metadata('related_task_id', task.id)
            progress_note.set_metadata('activity_type', 'task_started')
            progress_note.save()
            activity_notes.append(progress_note)
            
            # Note for task completion
            completion_note = Note(
                tenant_id=setup['tenant'].id,
                user_id=setup['sales_rep'].id,
                lead_id=setup['lead'].id,
                title='Task Completed',
                content=f'Completed task: {task.title}',
                note_type='activity',
                is_private=False
            )
            completion_note.set_metadata('related_task_id', task.id)
            completion_note.set_metadata('activity_type', 'task_completed')
            completion_note.save()
            activity_notes.append(completion_note)
            
            # Verify activity notes were created
            assert len(activity_notes) == 3
            
            # Query activity notes for the lead
            lead_activity_notes = Note.query.filter_by(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                note_type='activity'
            ).all()
            
            assert len(lead_activity_notes) == 3
            
            # Verify each note has correct metadata
            for note in lead_activity_notes:
                assert note.get_metadata('related_task_id') == task.id
                assert note.get_metadata('activity_type') in ['task_created', 'task_started', 'task_completed']
    
    def test_task_time_tracking(self, app, activity_setup):
        """Test time tracking functionality for tasks."""
        with app.app_context():
            setup = activity_setup
            
            # Create task with time tracking
            task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Time tracking task',
                assigned_to_id=setup['sales_rep'].id
            )
            
            # Initialize time tracking metadata
            task.set_metadata('time_tracking_enabled', True)
            task.set_metadata('time_entries', [])
            task.set_metadata('total_time_spent', 0)  # in minutes
            task.save()
            
            # Simulate time tracking entries
            time_entries = []
            
            # First work session
            start_time = datetime.utcnow()
            end_time = start_time + timedelta(hours=2)
            time_entries.append({
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_minutes': 120,
                'description': 'Initial research and planning',
                'user_id': setup['sales_rep'].id
            })
            
            # Second work session
            start_time = datetime.utcnow() + timedelta(days=1)
            end_time = start_time + timedelta(hours=1, minutes=30)
            time_entries.append({
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_minutes': 90,
                'description': 'Follow-up calls and documentation',
                'user_id': setup['sales_rep'].id
            })
            
            # Update task with time entries
            total_time = sum(entry['duration_minutes'] for entry in time_entries)
            task.set_metadata('time_entries', time_entries)
            task.set_metadata('total_time_spent', total_time)
            task.save()
            
            # Verify time tracking
            assert task.get_metadata('time_tracking_enabled') is True
            assert len(task.get_metadata('time_entries')) == 2
            assert task.get_metadata('total_time_spent') == 210  # 3.5 hours
            
            # Test time tracking summary
            entries = task.get_metadata('time_entries')
            assert entries[0]['duration_minutes'] == 120
            assert entries[1]['duration_minutes'] == 90
            assert 'research and planning' in entries[0]['description']
            assert 'Follow-up calls' in entries[1]['description']
    
    def test_task_interaction_history(self, app, activity_setup):
        """Test comprehensive task interaction history tracking."""
        with app.app_context():
            setup = activity_setup
            
            # Create task
            task = Task(
                tenant_id=setup['tenant'].id,
                lead_id=setup['lead'].id,
                title='Interaction history task',
                assigned_to_id=setup['sales_rep'].id,
                priority='medium'
            )
            task.save()
            
            # Track various interactions
            interaction_history = []
            
            # Task creation
            interaction_history.append({
                'action': 'created',
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': setup['sales_rep'].id,
                'details': {
                    'title': task.title,
                    'priority': task.priority,
                    'assigned_to': task.assigned_to_id
                }
            })
            
            # Priority change
            old_priority = task.priority
            task.priority = 'high'
            task.save()
            interaction_history.append({
                'action': 'priority_changed',
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': setup['manager'].id,
                'details': {
                    'from': old_priority,
                    'to': task.priority
                }
            })
            
            # Due date added
            due_date = (datetime.utcnow() + timedelta(days=5)).isoformat()
            task.due_date = due_date
            task.save()
            interaction_history.append({
                'action': 'due_date_set',
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': setup['sales_rep'].id,
                'details': {
                    'due_date': due_date
                }
            })
            
            # Task completion
            task.complete()
            task.save()
            interaction_history.append({
                'action': 'completed',
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': setup['sales_rep'].id,
                'details': {
                    'completed_at': task.completed_at
                }
            })
            
            # Store interaction history
            task.set_metadata('interaction_history', interaction_history)
            task.save()
            
            # Verify interaction history
            history = task.get_metadata('interaction_history')
            assert len(history) == 4
            
            # Verify specific interactions
            actions = [entry['action'] for entry in history]
            assert 'created' in actions
            assert 'priority_changed' in actions
            assert 'due_date_set' in actions
            assert 'completed' in actions
            
            # Verify details are captured
            priority_change = next(entry for entry in history if entry['action'] == 'priority_changed')
            assert priority_change['details']['from'] == 'medium'
            assert priority_change['details']['to'] == 'high'
            
            completion_entry = next(entry for entry in history if entry['action'] == 'completed')
            assert completion_entry['details']['completed_at'] is not None