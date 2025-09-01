"""
API endpoint tests for task and activity management functionality.
Tests requirement 3.4: Task and activity management API endpoints.
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


class TestTaskAPIEndpoints:
    """Test task management API endpoints."""
    
    @pytest.fixture
    def api_setup(self, app):
        """Set up API test environment with real company data."""
        with app.app_context():
            # Load real company data
            import json
            with open('comprehensive_test_dataset.json', 'r') as f:
                dataset = json.load(f)
            # Convert companies dict to list and take first 3
            companies = list(dataset['companies'].values())[:3]
            
            # Create tenant
            tenant = Tenant(name="API Test Corp", slug="api-test")
            tenant.save()
            
            # Create users
            manager = User(
                tenant_id=tenant.id,
                email="manager@apitest.com",
                first_name="API",
                last_name="Manager",
                is_active=True
            )
            manager.save()
            
            sales_rep = User(
                tenant_id=tenant.id,
                email="sales@apitest.com",
                first_name="Sales",
                last_name="Rep",
                is_active=True
            )
            sales_rep.save()
            
            # Create pipeline
            pipeline = Pipeline(
                tenant_id=tenant.id,
                name="API Test Pipeline",
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
            
            for company_data in companies:
                contact = Contact(
                    tenant_id=tenant.id,
                    first_name="Contact",
                    last_name=f"From {company_data['name'][:15]}",
                    company=company_data['name'],
                    email=f"contact@{company_data['name'].lower().replace(' ', '').replace(',', '')[:15]}.com",
                    country=company_data['country_code'],
                    contact_type="prospect"
                )
                contact.save()
                contacts.append(contact)
                
                lead = Lead(
                    tenant_id=tenant.id,
                    title=f"API Lead for {company_data['name'][:25]}",
                    description=f"API test opportunity with {company_data['name']}",
                    contact_id=contact.id,
                    pipeline_id=pipeline.id,
                    stage_id=stage.id,
                    value=75000,
                    assigned_to_id=sales_rep.id
                )
                lead.save()
                leads.append(lead)
            
            return {
                'tenant': tenant,
                'manager': manager,
                'sales_rep': sales_rep,
                'contacts': contacts,
                'leads': leads,
                'companies': companies
            }
    
    @pytest.fixture
    def auth_headers(self, app, api_setup):
        """Create authentication headers for API requests."""
        with app.app_context():
            # Mock JWT token for sales rep
            from flask_jwt_extended import create_access_token
            
            # Create access token for sales rep
            access_token = create_access_token(identity=api_setup['sales_rep'].id)
            
            return {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
    
    def test_create_task_via_api(self, client, auth_headers, api_setup):
        """Test creating tasks via API with real company data."""
        setup = api_setup
        lead = setup['leads'][0]  # Use first lead
        company = setup['companies'][0]
        
        # Test creating different types of tasks
        task_data = {
            'title': f'API Call task for {company["name"]}',
            'description': f'Initial discovery call with {company["name"]} via API',
            'lead_id': lead.id,
            'assigned_to_id': setup['sales_rep'].id,
            'task_type': 'call',
            'priority': 'high',
            'category': 'sales',
            'due_date': (datetime.utcnow() + timedelta(days=2)).isoformat(),
            'tags': ['api-test', 'discovery', 'high-priority'],
            'extra_data': {
                'company_country': company['country_code'],
                'company_vat': company.get('vat_number', ''),
                'api_created': True
            }
        }
        
        response = client.post(
            '/api/v1/crm/tasks',
            headers=auth_headers,
            json=task_data
        )
        
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == task_data['title']
        assert data['data']['lead_id'] == lead.id
        assert data['data']['assigned_to_id'] == setup['sales_rep'].id
        assert data['data']['task_type'] == 'call'
        assert data['data']['priority'] == 'high'
        assert company['name'] in data['data']['title']
        
        # Verify extra data was stored
        assert data['data']['extra_data']['company_country'] == company['country_code']
        assert data['data']['extra_data']['api_created'] is True
        
        # Verify tags were stored
        assert 'api-test' in data['data']['tags']
        assert 'discovery' in data['data']['tags']
    
    def test_list_tasks_with_filters(self, client, auth_headers, api_setup):
        """Test listing tasks with various filters."""
        setup = api_setup
        
        # Create multiple tasks with different properties
        tasks_data = [
            {
                'title': f'High priority task for {setup["companies"][0]["name"]}',
                'lead_id': setup['leads'][0].id,
                'priority': 'high',
                'status': 'pending',
                'task_type': 'call'
            },
            {
                'title': f'Medium priority task for {setup["companies"][1]["name"]}',
                'lead_id': setup['leads'][1].id,
                'priority': 'medium',
                'status': 'in_progress',
                'task_type': 'email'
            },
            {
                'title': f'Completed task for {setup["companies"][2]["name"]}',
                'lead_id': setup['leads'][2].id,
                'priority': 'low',
                'status': 'completed',
                'task_type': 'follow_up'
            }
        ]
        
        created_tasks = []
        for task_data in tasks_data:
            response = client.post(
                '/api/v1/crm/tasks',
                headers=auth_headers,
                json=task_data
            )
            assert response.status_code == 201
            created_tasks.append(json.loads(response.data)['data'])
        
        # Test listing all tasks
        response = client.get('/api/v1/crm/tasks', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 3
        
        # Test filtering by status
        response = client.get('/api/v1/crm/tasks?status=pending', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        pending_tasks = data['data']['items']
        assert all(task['status'] == 'pending' for task in pending_tasks)
        
        # Test filtering by priority
        response = client.get('/api/v1/crm/tasks?priority=high', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        high_priority_tasks = data['data']['items']
        assert all(task['priority'] == 'high' for task in high_priority_tasks)
        
        # Test filtering by task type
        response = client.get('/api/v1/crm/tasks?task_type=call', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        call_tasks = data['data']['items']
        assert all(task['task_type'] == 'call' for task in call_tasks)
        
        # Test filtering by lead
        response = client.get(f'/api/v1/crm/tasks?lead_id={setup["leads"][0].id}', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        lead_tasks = data['data']['items']
        assert all(task['lead_id'] == setup['leads'][0].id for task in lead_tasks)
    
    def test_update_task_via_api(self, client, auth_headers, api_setup):
        """Test updating tasks via API."""
        setup = api_setup
        lead = setup['leads'][0]
        company = setup['companies'][0]
        
        # Create task first
        task_data = {
            'title': f'Update test task for {company["name"]}',
            'description': 'Original description',
            'lead_id': lead.id,
            'priority': 'medium',
            'status': 'pending'
        }
        
        response = client.post('/api/v1/crm/tasks', headers=auth_headers, json=task_data)
        assert response.status_code == 201
        
        created_task = json.loads(response.data)['data']
        task_id = created_task['id']
        
        # Update task
        update_data = {
            'title': f'Updated task for {company["name"]}',
            'description': 'Updated description with more details',
            'priority': 'high',
            'assigned_to_id': setup['manager'].id,
            'due_date': (datetime.utcnow() + timedelta(days=5)).isoformat(),
            'extra_data': {
                'updated_via_api': True,
                'update_reason': 'Priority escalation'
            }
        }
        
        response = client.put(
            f'/api/v1/crm/tasks/{task_id}',
            headers=auth_headers,
            json=update_data
        )
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == update_data['title']
        assert data['data']['description'] == update_data['description']
        assert data['data']['priority'] == 'high'
        assert data['data']['assigned_to_id'] == setup['manager'].id
        assert data['data']['due_date'] is not None
        
        # Verify extra data was updated
        assert data['data']['extra_data']['updated_via_api'] is True
        assert data['data']['extra_data']['update_reason'] == 'Priority escalation'
    
    def test_update_task_status_via_api(self, client, auth_headers, api_setup):
        """Test updating task status via dedicated API endpoint."""
        setup = api_setup
        lead = setup['leads'][0]
        
        # Create task
        task_data = {
            'title': 'Status update test task',
            'lead_id': lead.id,
            'status': 'pending'
        }
        
        response = client.post('/api/v1/crm/tasks', headers=auth_headers, json=task_data)
        assert response.status_code == 201
        
        task_id = json.loads(response.data)['data']['id']
        
        # Test status transitions
        status_transitions = [
            ('in_progress', 'Task started'),
            ('completed', 'Task completed successfully')
        ]
        
        for new_status, expected_message in status_transitions:
            response = client.put(
                f'/api/v1/crm/tasks/{task_id}/status',
                headers=auth_headers,
                json={'status': new_status}
            )
            
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['data']['status'] == new_status
            
            if new_status == 'completed':
                assert data['data']['completed_at'] is not None
                assert data['data']['is_completed'] is True
    
    def test_delete_task_via_api(self, client, auth_headers, api_setup):
        """Test deleting tasks via API."""
        setup = api_setup
        lead = setup['leads'][0]
        
        # Create task
        task_data = {
            'title': 'Delete test task',
            'lead_id': lead.id
        }
        
        response = client.post('/api/v1/crm/tasks', headers=auth_headers, json=task_data)
        assert response.status_code == 201
        
        task_id = json.loads(response.data)['data']['id']
        
        # Delete task
        response = client.delete(f'/api/v1/crm/tasks/{task_id}', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Verify task is deleted (soft delete)
        response = client.get(f'/api/v1/crm/tasks/{task_id}', headers=auth_headers)
        assert response.status_code == 404
    
    def test_task_api_validation_errors(self, client, auth_headers, api_setup):
        """Test API validation errors for task operations."""
        setup = api_setup
        
        # Test creating task without required title
        response = client.post(
            '/api/v1/crm/tasks',
            headers=auth_headers,
            json={'description': 'Task without title'}
        )
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'title' in str(data['message']).lower()
        
        # Test creating task with invalid lead_id
        response = client.post(
            '/api/v1/crm/tasks',
            headers=auth_headers,
            json={
                'title': 'Task with invalid lead',
                'lead_id': 99999
            }
        )
        assert response.status_code == 404
        
        # Test creating task with invalid assigned_to_id
        response = client.post(
            '/api/v1/crm/tasks',
            headers=auth_headers,
            json={
                'title': 'Task with invalid assignee',
                'assigned_to_id': 99999
            }
        )
        assert response.status_code == 400
        
        # Test updating non-existent task
        response = client.put(
            '/api/v1/crm/tasks/99999',
            headers=auth_headers,
            json={'title': 'Updated title'}
        )
        assert response.status_code == 404
    
    def test_overdue_and_due_today_filters(self, client, auth_headers, api_setup):
        """Test API filters for overdue and due today tasks."""
        setup = api_setup
        lead = setup['leads'][0]
        now = datetime.utcnow()
        
        # Create overdue task
        overdue_task_data = {
            'title': 'Overdue task',
            'lead_id': lead.id,
            'due_date': (now - timedelta(days=2)).isoformat(),
            'status': 'pending'
        }
        
        response = client.post('/api/v1/crm/tasks', headers=auth_headers, json=overdue_task_data)
        assert response.status_code == 201
        
        # Create due today task
        due_today_task_data = {
            'title': 'Due today task',
            'lead_id': lead.id,
            'due_date': now.replace(hour=23, minute=59).isoformat(),
            'status': 'pending'
        }
        
        response = client.post('/api/v1/crm/tasks', headers=auth_headers, json=due_today_task_data)
        assert response.status_code == 201
        
        # Create future task
        future_task_data = {
            'title': 'Future task',
            'lead_id': lead.id,
            'due_date': (now + timedelta(days=5)).isoformat(),
            'status': 'pending'
        }
        
        response = client.post('/api/v1/crm/tasks', headers=auth_headers, json=future_task_data)
        assert response.status_code == 201
        
        # Test overdue filter
        response = client.get('/api/v1/crm/tasks?overdue=true', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        overdue_tasks = data['data']['items']
        assert len(overdue_tasks) >= 1
        assert any('Overdue task' in task['title'] for task in overdue_tasks)
        
        # Test due today filter
        response = client.get('/api/v1/crm/tasks?due_today=true', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        due_today_tasks = data['data']['items']
        assert len(due_today_tasks) >= 1
        assert any('Due today task' in task['title'] for task in due_today_tasks)


class TestActivityNotesAPIEndpoints:
    """Test activity notes API endpoints for task tracking."""
    
    @pytest.fixture
    def notes_setup(self, app):
        """Set up environment for notes API testing."""
        with app.app_context():
            # Create tenant and user
            tenant = Tenant(name="Notes Test Corp", slug="notes-test")
            tenant.save()
            
            user = User(
                tenant_id=tenant.id,
                email="user@notestest.com",
                first_name="Notes",
                last_name="User",
                is_active=True
            )
            user.save()
            
            # Create contact and lead
            contact = Contact(
                tenant_id=tenant.id,
                first_name="Notes",
                last_name="Contact",
                company="Notes Company",
                email="contact@notescompany.com"
            )
            contact.save()
            
            pipeline = Pipeline(tenant_id=tenant.id, name="Notes Pipeline", is_default=True)
            pipeline.save()
            
            stage = Stage(tenant_id=tenant.id, pipeline_id=pipeline.id, name="Notes Stage", position=1)
            stage.save()
            
            lead = Lead(
                tenant_id=tenant.id,
                title="Notes Lead",
                contact_id=contact.id,
                pipeline_id=pipeline.id,
                stage_id=stage.id
            )
            lead.save()
            
            # Create task
            task = Task(
                tenant_id=tenant.id,
                lead_id=lead.id,
                title='Notes test task',
                assigned_to_id=user.id
            )
            task.save()
            
            return {
                'tenant': tenant,
                'user': user,
                'contact': contact,
                'lead': lead,
                'task': task
            }
    
    @pytest.fixture
    def notes_auth_headers(self, app, notes_setup):
        """Create authentication headers for notes API requests."""
        with app.app_context():
            from flask_jwt_extended import create_access_token
            
            access_token = create_access_token(identity=notes_setup['user'].id)
            
            return {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
    
    def test_create_activity_note_via_api(self, client, notes_auth_headers, notes_setup):
        """Test creating activity notes via API."""
        setup = notes_setup
        
        # Create activity note for task creation
        note_data = {
            'title': 'Task Activity: Created',
            'content': f'Created task: {setup["task"].title}',
            'lead_id': setup['lead'].id,
            'note_type': 'activity',
            'is_private': False,
            'extra_data': {
                'related_task_id': setup['task'].id,
                'activity_type': 'task_created',
                'task_title': setup['task'].title
            },
            'tags': ['activity', 'task', 'created']
        }
        
        response = client.post(
            '/api/v1/crm/notes',
            headers=notes_auth_headers,
            json=note_data
        )
        
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['note_type'] == 'activity'
        assert data['data']['lead_id'] == setup['lead'].id
        assert data['data']['extra_data']['related_task_id'] == setup['task'].id
        assert data['data']['extra_data']['activity_type'] == 'task_created'
        assert 'activity' in data['data']['tags']
    
    def test_list_activity_notes_for_lead(self, client, notes_auth_headers, notes_setup):
        """Test listing activity notes for a specific lead."""
        setup = notes_setup
        
        # Create multiple activity notes
        activity_types = [
            ('task_created', 'Task was created'),
            ('task_started', 'Task was started'),
            ('task_updated', 'Task priority was updated'),
            ('task_completed', 'Task was completed')
        ]
        
        created_notes = []
        for activity_type, content in activity_types:
            note_data = {
                'title': f'Task Activity: {activity_type.replace("_", " ").title()}',
                'content': content,
                'lead_id': setup['lead'].id,
                'note_type': 'activity',
                'extra_data': {
                    'related_task_id': setup['task'].id,
                    'activity_type': activity_type
                }
            }
            
            response = client.post('/api/v1/crm/notes', headers=notes_auth_headers, json=note_data)
            assert response.status_code == 201
            created_notes.append(json.loads(response.data)['data'])
        
        # List all notes for the lead
        response = client.get(f'/api/v1/crm/notes?lead_id={setup["lead"].id}', headers=notes_auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 4
        
        # Filter by note type (activity)
        response = client.get(
            f'/api/v1/crm/notes?lead_id={setup["lead"].id}&note_type=activity',
            headers=notes_auth_headers
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        activity_notes = data['data']['items']
        assert all(note['note_type'] == 'activity' for note in activity_notes)
        assert len(activity_notes) >= 4
        
        # Verify activity types are present
        activity_types_found = [
            note['extra_data']['activity_type'] 
            for note in activity_notes 
            if note['extra_data'] and 'activity_type' in note['extra_data']
        ]
        assert 'task_created' in activity_types_found
        assert 'task_completed' in activity_types_found
    
    def test_search_activity_notes(self, client, notes_auth_headers, notes_setup):
        """Test searching activity notes."""
        setup = notes_setup
        
        # Create searchable activity notes
        searchable_notes = [
            {
                'title': 'Task Priority Changed',
                'content': 'Task priority was changed from medium to high due to client urgency',
                'note_type': 'activity',
                'lead_id': setup['lead'].id,
                'extra_data': {'activity_type': 'priority_change'}
            },
            {
                'title': 'Task Assignment Updated',
                'content': 'Task was reassigned to senior sales representative',
                'note_type': 'activity',
                'lead_id': setup['lead'].id,
                'extra_data': {'activity_type': 'assignment_change'}
            },
            {
                'title': 'Task Due Date Extended',
                'content': 'Due date was extended by 3 days due to client availability',
                'note_type': 'activity',
                'lead_id': setup['lead'].id,
                'extra_data': {'activity_type': 'due_date_change'}
            }
        ]
        
        for note_data in searchable_notes:
            response = client.post('/api/v1/crm/notes', headers=notes_auth_headers, json=note_data)
            assert response.status_code == 201
        
        # Search for notes containing "priority"
        response = client.get('/api/v1/crm/notes?search=priority', headers=notes_auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        priority_notes = data['data']['items']
        assert len(priority_notes) >= 1
        assert any('priority' in note['content'].lower() for note in priority_notes)
        
        # Search for notes containing "assignment"
        response = client.get('/api/v1/crm/notes?search=assignment', headers=notes_auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assignment_notes = data['data']['items']
        assert len(assignment_notes) >= 1
        assert any('assignment' in note['content'].lower() for note in assignment_notes)
    
    def test_update_activity_note_via_api(self, client, notes_auth_headers, notes_setup):
        """Test updating activity notes via API."""
        setup = notes_setup
        
        # Create activity note
        note_data = {
            'title': 'Original Activity Note',
            'content': 'Original activity content',
            'lead_id': setup['lead'].id,
            'note_type': 'activity',
            'extra_data': {
                'related_task_id': setup['task'].id,
                'activity_type': 'task_updated'
            }
        }
        
        response = client.post('/api/v1/crm/notes', headers=notes_auth_headers, json=note_data)
        assert response.status_code == 201
        
        note_id = json.loads(response.data)['data']['id']
        
        # Update the note
        update_data = {
            'title': 'Updated Activity Note',
            'content': 'Updated activity content with more details',
            'extra_data': {
                'related_task_id': setup['task'].id,
                'activity_type': 'task_updated',
                'update_reason': 'Added more context'
            }
        }
        
        response = client.put(
            f'/api/v1/crm/notes/{note_id}',
            headers=notes_auth_headers,
            json=update_data
        )
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == 'Updated Activity Note'
        assert data['data']['content'] == 'Updated activity content with more details'
        assert data['data']['extra_data']['update_reason'] == 'Added more context'
    
    def test_activity_note_permissions(self, client, notes_auth_headers, notes_setup):
        """Test activity note permissions and privacy."""
        setup = notes_setup
        
        # Create private activity note
        private_note_data = {
            'title': 'Private Activity Note',
            'content': 'This is a private activity note',
            'lead_id': setup['lead'].id,
            'note_type': 'activity',
            'is_private': True,
            'extra_data': {
                'related_task_id': setup['task'].id,
                'activity_type': 'private_update'
            }
        }
        
        response = client.post('/api/v1/crm/notes', headers=notes_auth_headers, json=private_note_data)
        assert response.status_code == 201
        
        private_note_id = json.loads(response.data)['data']['id']
        
        # Create public activity note
        public_note_data = {
            'title': 'Public Activity Note',
            'content': 'This is a public activity note',
            'lead_id': setup['lead'].id,
            'note_type': 'activity',
            'is_private': False,
            'extra_data': {
                'related_task_id': setup['task'].id,
                'activity_type': 'public_update'
            }
        }
        
        response = client.post('/api/v1/crm/notes', headers=notes_auth_headers, json=public_note_data)
        assert response.status_code == 201
        
        # List notes - should include both since user is the creator
        response = client.get(f'/api/v1/crm/notes?lead_id={setup["lead"].id}', headers=notes_auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        notes = data['data']['items']
        
        # Should find both private and public notes for the creator
        private_found = any(note['id'] == private_note_id for note in notes)
        public_found = any(note['title'] == 'Public Activity Note' for note in notes)
        
        assert private_found is True
        assert public_found is True
    
    def test_delete_activity_note_via_api(self, client, notes_auth_headers, notes_setup):
        """Test deleting activity notes via API."""
        setup = notes_setup
        
        # Create activity note
        note_data = {
            'title': 'Delete Test Activity Note',
            'content': 'This note will be deleted',
            'lead_id': setup['lead'].id,
            'note_type': 'activity'
        }
        
        response = client.post('/api/v1/crm/notes', headers=notes_auth_headers, json=note_data)
        assert response.status_code == 201
        
        note_id = json.loads(response.data)['data']['id']
        
        # Delete the note
        response = client.delete(f'/api/v1/crm/notes/{note_id}', headers=notes_auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Verify note is deleted (soft delete)
        response = client.get(f'/api/v1/crm/notes/{note_id}', headers=notes_auth_headers)
        assert response.status_code == 404


class TestTaskActivityIntegrationAPI:
    """Test integration between tasks and activity tracking via API."""
    
    @pytest.fixture
    def integration_setup(self, app):
        """Set up integration test environment."""
        with app.app_context():
            # Load real company data
            import json
            with open('comprehensive_test_dataset.json', 'r') as f:
                dataset = json.load(f)
            # Convert companies dict to list and take first company
            company = list(dataset['companies'].values())[0]
            
            # Create tenant and user
            tenant = Tenant(name="Integration Test Corp", slug="integration-test")
            tenant.save()
            
            user = User(
                tenant_id=tenant.id,
                email="user@integrationtest.com",
                first_name="Integration",
                last_name="User",
                is_active=True
            )
            user.save()
            
            # Create contact and lead with real company data
            contact = Contact(
                tenant_id=tenant.id,
                first_name="Integration",
                last_name="Contact",
                company=company['name'],
                email=f"contact@{company['name'].lower().replace(' ', '').replace(',', '')[:15]}.com",
                country=company['country_code']
            )
            contact.save()
            
            pipeline = Pipeline(tenant_id=tenant.id, name="Integration Pipeline", is_default=True)
            pipeline.save()
            
            stage = Stage(tenant_id=tenant.id, pipeline_id=pipeline.id, name="Integration Stage", position=1)
            stage.save()
            
            lead = Lead(
                tenant_id=tenant.id,
                title=f"Integration Lead for {company['name']}",
                contact_id=contact.id,
                pipeline_id=pipeline.id,
                stage_id=stage.id
            )
            lead.save()
            
            return {
                'tenant': tenant,
                'user': user,
                'contact': contact,
                'lead': lead,
                'company': company
            }
    
    @pytest.fixture
    def integration_auth_headers(self, app, integration_setup):
        """Create authentication headers for integration tests."""
        with app.app_context():
            from flask_jwt_extended import create_access_token
            
            access_token = create_access_token(identity=integration_setup['user'].id)
            
            return {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
    
    def test_complete_task_lifecycle_with_activity_tracking(self, client, integration_auth_headers, integration_setup):
        """Test complete task lifecycle with automatic activity tracking."""
        setup = integration_setup
        company = setup['company']
        
        # 1. Create task
        task_data = {
            'title': f'Complete lifecycle task for {company["name"]}',
            'description': f'Full lifecycle test with {company["name"]}',
            'lead_id': setup['lead'].id,
            'assigned_to_id': setup['user'].id,
            'priority': 'medium',
            'task_type': 'call',
            'due_date': (datetime.utcnow() + timedelta(days=3)).isoformat()
        }
        
        response = client.post('/api/v1/crm/tasks', headers=integration_auth_headers, json=task_data)
        assert response.status_code == 201
        
        task = json.loads(response.data)['data']
        task_id = task['id']
        
        # Create activity note for task creation
        creation_note_data = {
            'title': 'Task Created',
            'content': f'Created task: {task["title"]}',
            'lead_id': setup['lead'].id,
            'note_type': 'activity',
            'extra_data': {
                'related_task_id': task_id,
                'activity_type': 'task_created',
                'company_name': company['name'],
                'company_country': company['country_code']
            }
        }
        
        response = client.post('/api/v1/crm/notes', headers=integration_auth_headers, json=creation_note_data)
        assert response.status_code == 201
        
        # 2. Start task
        response = client.put(
            f'/api/v1/crm/tasks/{task_id}/status',
            headers=integration_auth_headers,
            json={'status': 'in_progress'}
        )
        assert response.status_code == 200
        
        # Create activity note for task start
        start_note_data = {
            'title': 'Task Started',
            'content': f'Started working on task: {task["title"]}',
            'lead_id': setup['lead'].id,
            'note_type': 'activity',
            'extra_data': {
                'related_task_id': task_id,
                'activity_type': 'task_started'
            }
        }
        
        response = client.post('/api/v1/crm/notes', headers=integration_auth_headers, json=start_note_data)
        assert response.status_code == 201
        
        # 3. Update task priority
        update_data = {
            'priority': 'high',
            'extra_data': {
                'priority_change_reason': 'Client urgency increased'
            }
        }
        
        response = client.put(f'/api/v1/crm/tasks/{task_id}', headers=integration_auth_headers, json=update_data)
        assert response.status_code == 200
        
        # Create activity note for priority change
        priority_note_data = {
            'title': 'Task Priority Updated',
            'content': 'Task priority changed from medium to high due to client urgency',
            'lead_id': setup['lead'].id,
            'note_type': 'activity',
            'extra_data': {
                'related_task_id': task_id,
                'activity_type': 'priority_changed',
                'old_priority': 'medium',
                'new_priority': 'high'
            }
        }
        
        response = client.post('/api/v1/crm/notes', headers=integration_auth_headers, json=priority_note_data)
        assert response.status_code == 201
        
        # 4. Complete task
        response = client.put(
            f'/api/v1/crm/tasks/{task_id}/status',
            headers=integration_auth_headers,
            json={'status': 'completed'}
        )
        assert response.status_code == 200
        
        completed_task = json.loads(response.data)['data']
        assert completed_task['status'] == 'completed'
        assert completed_task['completed_at'] is not None
        
        # Create activity note for task completion
        completion_note_data = {
            'title': 'Task Completed',
            'content': f'Successfully completed task: {task["title"]}',
            'lead_id': setup['lead'].id,
            'note_type': 'activity',
            'extra_data': {
                'related_task_id': task_id,
                'activity_type': 'task_completed',
                'completion_time': completed_task['completed_at']
            }
        }
        
        response = client.post('/api/v1/crm/notes', headers=integration_auth_headers, json=completion_note_data)
        assert response.status_code == 201
        
        # 5. Verify complete activity history
        response = client.get(
            f'/api/v1/crm/notes?lead_id={setup["lead"].id}&note_type=activity',
            headers=integration_auth_headers
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        activity_notes = data['data']['items']
        
        # Should have at least 4 activity notes
        assert len(activity_notes) >= 4
        
        # Verify all activity types are present
        activity_types = [
            note['extra_data']['activity_type'] 
            for note in activity_notes 
            if note['extra_data'] and 'activity_type' in note['extra_data']
        ]
        
        expected_activities = ['task_created', 'task_started', 'priority_changed', 'task_completed']
        for expected_activity in expected_activities:
            assert expected_activity in activity_types
        
        # Verify company information is tracked
        company_notes = [
            note for note in activity_notes 
            if note['extra_data'] and 'company_name' in note['extra_data']
        ]
        assert len(company_notes) >= 1
        assert company_notes[0]['extra_data']['company_name'] == company['name']
        assert company_notes[0]['extra_data']['company_country'] == company['country_code']