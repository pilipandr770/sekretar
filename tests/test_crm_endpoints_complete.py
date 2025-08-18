"""Comprehensive tests for CRM management endpoints."""
import pytest
import json
from datetime import datetime
from app.models.tenant import Tenant
from app.models.user import User
from app.models.contact import Contact
from app.models.pipeline import Pipeline, Stage
from app.models.lead import Lead
from app.models.task import Task
from app.models.note import Note
from flask_jwt_extended import create_access_token


class TestCRMEndpoints:
    """Test CRM endpoints functionality."""
    
    @pytest.fixture
    def setup_data(self, app, db_session):
        """Set up test data."""
        with app.app_context():
            # Create tenant
            tenant = Tenant(
                name="CRM Test Tenant",
                domain="crm-test.example.com",
                slug="crm-test-tenant",
                settings={"test": True}
            )
            db_session.add(tenant)
            db_session.commit()
            
            # Create user
            user = User(
                tenant_id=tenant.id,
                email="crm-test@example.com",
                password_hash="hashed_password",
                first_name="CRM",
                last_name="Tester",
                role="manager",
                is_active=True
            )
            db_session.add(user)
            db_session.commit()
            
            # Create contact
            contact = Contact.create(
                tenant_id=tenant.id,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
                company="Acme Corp"
            )
            
            # Create pipeline
            pipeline = Pipeline.create_default(tenant.id)
            
            # Create lead
            lead = Lead.create_from_contact(
                tenant_id=tenant.id,
                contact_id=contact.id,
                title="Test Lead",
                pipeline_id=pipeline.id,
                value=1000.00
            )
            
            # Create task
            task = Task.create(
                tenant_id=tenant.id,
                lead_id=lead.id,
                title="Follow up call",
                assigned_to_id=user.id,
                priority="high"
            )
            
            # Create note
            note = Note.create(
                tenant_id=tenant.id,
                lead_id=lead.id,
                user_id=user.id,
                content="Initial conversation notes"
            )
            
            return {
                'tenant': tenant,
                'user': user,
                'contact': contact,
                'pipeline': pipeline,
                'lead': lead,
                'task': task,
                'note': note
            }
    
    @pytest.fixture
    def auth_headers(self, app, setup_data):
        """Create authentication headers."""
        with app.app_context():
            user = setup_data['user']
            access_token = create_access_token(
                identity=user.id,
                additional_claims={
                    'tenant_id': user.tenant_id,
                    'user_id': user.id,
                    'role': user.role
                }
            )
            
            return {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
    
    def test_list_contacts(self, client, setup_data, auth_headers):
        """Test listing contacts."""
        response = client.get('/api/v1/crm/contacts', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert len(data['data']['items']) >= 1
        
        # Check contact data structure
        contact = data['data']['items'][0]
        assert 'id' in contact
        assert 'full_name' in contact
        assert 'email' in contact
        assert 'company' in contact
    
    def test_create_contact(self, client, setup_data, auth_headers):
        """Test creating a new contact."""
        contact_data = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane.smith@example.com',
            'company': 'Tech Corp',
            'phone': '+1234567890'
        }
        
        response = client.post(
            '/api/v1/crm/contacts',
            headers=auth_headers,
            data=json.dumps(contact_data)
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['first_name'] == 'Jane'
        assert data['data']['last_name'] == 'Smith'
        assert data['data']['email'] == 'jane.smith@example.com'
    
    def test_get_contact(self, client, setup_data, auth_headers):
        """Test getting a specific contact."""
        contact_id = setup_data['contact'].id
        
        response = client.get(f'/api/v1/crm/contacts/{contact_id}', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == contact_id
        assert data['data']['first_name'] == 'John'
        assert data['data']['last_name'] == 'Doe'
    
    def test_update_contact(self, client, setup_data, auth_headers):
        """Test updating a contact."""
        contact_id = setup_data['contact'].id
        update_data = {
            'first_name': 'Johnny',
            'phone': '+9876543210'
        }
        
        response = client.put(
            f'/api/v1/crm/contacts/{contact_id}',
            headers=auth_headers,
            data=json.dumps(update_data)
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['first_name'] == 'Johnny'
        assert data['data']['phone'] == '+9876543210'
    
    def test_list_pipelines(self, client, setup_data, auth_headers):
        """Test listing pipelines."""
        response = client.get('/api/v1/crm/pipelines', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']) >= 1
        
        # Check pipeline data structure
        pipeline = data['data'][0]
        assert 'id' in pipeline
        assert 'name' in pipeline
        assert 'stages' in pipeline
        assert len(pipeline['stages']) >= 1
    
    def test_create_pipeline(self, client, setup_data, auth_headers):
        """Test creating a new pipeline."""
        pipeline_data = {
            'name': 'Custom Pipeline',
            'description': 'A custom sales pipeline',
            'stages': [
                {'name': 'Initial Contact', 'color': '#3498db'},
                {'name': 'Qualified', 'color': '#f39c12'},
                {'name': 'Closed Won', 'color': '#27ae60', 'is_closed': True, 'is_won': True}
            ]
        }
        
        response = client.post(
            '/api/v1/crm/pipelines',
            headers=auth_headers,
            data=json.dumps(pipeline_data)
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['name'] == 'Custom Pipeline'
        assert len(data['data']['stages']) == 3
    
    def test_list_leads(self, client, setup_data, auth_headers):
        """Test listing leads."""
        response = client.get('/api/v1/crm/leads', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 1
        
        # Check lead data structure
        lead = data['data']['items'][0]
        assert 'id' in lead
        assert 'title' in lead
        assert 'contact_name' in lead
        assert 'stage_name' in lead
        assert 'pipeline_name' in lead
    
    def test_create_lead(self, client, setup_data, auth_headers):
        """Test creating a new lead."""
        lead_data = {
            'title': 'New Opportunity',
            'description': 'A promising new lead',
            'contact_id': setup_data['contact'].id,
            'pipeline_id': setup_data['pipeline'].id,
            'value': 2500.00,
            'priority': 'high'
        }
        
        response = client.post(
            '/api/v1/crm/leads',
            headers=auth_headers,
            data=json.dumps(lead_data)
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == 'New Opportunity'
        assert data['data']['value'] == '2500.00'
        assert data['data']['priority'] == 'high'
    
    def test_move_lead_stage(self, client, setup_data, auth_headers):
        """Test moving lead to different stage."""
        lead_id = setup_data['lead'].id
        pipeline = setup_data['pipeline']
        second_stage = pipeline.get_ordered_stages()[1]
        
        stage_data = {
            'stage_id': second_stage.id
        }
        
        response = client.put(
            f'/api/v1/crm/leads/{lead_id}/stage',
            headers=auth_headers,
            data=json.dumps(stage_data)
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['stage_id'] == second_stage.id
        assert data['data']['stage_name'] == second_stage.name
    
    def test_list_tasks(self, client, setup_data, auth_headers):
        """Test listing tasks."""
        response = client.get('/api/v1/crm/tasks', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 1
        
        # Check task data structure
        task = data['data']['items'][0]
        assert 'id' in task
        assert 'title' in task
        assert 'status' in task
        assert 'priority' in task
        assert 'lead_title' in task
    
    def test_create_task(self, client, setup_data, auth_headers):
        """Test creating a new task."""
        task_data = {
            'title': 'Send proposal',
            'description': 'Prepare and send detailed proposal',
            'lead_id': setup_data['lead'].id,
            'assigned_to_id': setup_data['user'].id,
            'priority': 'high',
            'task_type': 'email',
            'due_date': datetime.utcnow().isoformat()
        }
        
        response = client.post(
            '/api/v1/crm/tasks',
            headers=auth_headers,
            data=json.dumps(task_data)
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == 'Send proposal'
        assert data['data']['priority'] == 'high'
        assert data['data']['task_type'] == 'email'
    
    def test_update_task_status(self, client, setup_data, auth_headers):
        """Test updating task status."""
        task_id = setup_data['task'].id
        status_data = {
            'status': 'completed'
        }
        
        response = client.put(
            f'/api/v1/crm/tasks/{task_id}/status',
            headers=auth_headers,
            data=json.dumps(status_data)
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['status'] == 'completed'
        assert data['data']['is_completed'] is True
    
    def test_list_notes(self, client, setup_data, auth_headers):
        """Test listing notes."""
        response = client.get('/api/v1/crm/notes', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 1
        
        # Check note data structure
        note = data['data']['items'][0]
        assert 'id' in note
        assert 'content' in note
        assert 'user_name' in note
        assert 'lead_title' in note
    
    def test_create_note(self, client, setup_data, auth_headers):
        """Test creating a new note."""
        note_data = {
            'title': 'Meeting notes',
            'content': 'Had a productive meeting with the client. They are interested in our premium package.',
            'lead_id': setup_data['lead'].id,
            'note_type': 'meeting'
        }
        
        response = client.post(
            '/api/v1/crm/notes',
            headers=auth_headers,
            data=json.dumps(note_data)
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == 'Meeting notes'
        assert data['data']['note_type'] == 'meeting'
        assert 'premium package' in data['data']['content']
    
    def test_get_lead_history(self, client, setup_data, auth_headers):
        """Test getting lead history with tasks and notes."""
        lead_id = setup_data['lead'].id
        
        response = client.get(f'/api/v1/crm/leads/{lead_id}/history', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'lead' in data['data']
        assert 'tasks' in data['data']
        assert 'notes' in data['data']
        assert 'threads' in data['data']
        
        # Verify lead data
        assert data['data']['lead']['id'] == lead_id
        
        # Verify tasks and notes are included
        assert len(data['data']['tasks']) >= 1
        assert len(data['data']['notes']) >= 1
    
    def test_search_contacts(self, client, setup_data, auth_headers):
        """Test searching contacts."""
        response = client.get('/api/v1/crm/contacts?search=John', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 1
        
        # Verify search results contain the search term
        contact = data['data']['items'][0]
        assert 'John' in contact['first_name'] or 'John' in contact['full_name']
    
    def test_filter_leads_by_status(self, client, setup_data, auth_headers):
        """Test filtering leads by status."""
        response = client.get('/api/v1/crm/leads?status=open', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        
        # All returned leads should have 'open' status
        for lead in data['data']['items']:
            assert lead['status'] == 'open'
    
    def test_filter_tasks_by_priority(self, client, setup_data, auth_headers):
        """Test filtering tasks by priority."""
        response = client.get('/api/v1/crm/tasks?priority=high', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        
        # All returned tasks should have 'high' priority
        for task in data['data']['items']:
            assert task['priority'] == 'high'
    
    def test_unauthorized_access(self, client, setup_data):
        """Test that endpoints require authentication."""
        endpoints = [
            '/api/v1/crm/contacts',
            '/api/v1/crm/pipelines',
            '/api/v1/crm/leads',
            '/api/v1/crm/tasks',
            '/api/v1/crm/notes'
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401
    
    def test_invalid_contact_creation(self, client, setup_data, auth_headers):
        """Test creating contact with invalid data."""
        # Missing required fields
        invalid_data = {
            'email': 'invalid-email'  # No name or company
        }
        
        response = client.post(
            '/api/v1/crm/contacts',
            headers=auth_headers,
            data=json.dumps(invalid_data)
        )
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'error' in data
    
    def test_duplicate_contact_email(self, client, setup_data, auth_headers):
        """Test creating contact with duplicate email."""
        existing_email = setup_data['contact'].email
        
        duplicate_data = {
            'first_name': 'Another',
            'last_name': 'Person',
            'email': existing_email
        }
        
        response = client.post(
            '/api/v1/crm/contacts',
            headers=auth_headers,
            data=json.dumps(duplicate_data)
        )
        assert response.status_code == 409  # Conflict
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'already exists' in data['message']
    
    def test_nonexistent_resource_access(self, client, setup_data, auth_headers):
        """Test accessing non-existent resources."""
        endpoints = [
            '/api/v1/crm/contacts/99999',
            '/api/v1/crm/leads/99999',
            '/api/v1/crm/tasks/99999',
            '/api/v1/crm/notes/99999'
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint, headers=auth_headers)
            assert response.status_code == 404
            
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'not found' in data['message'].lower()