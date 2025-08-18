"""Test CRM API endpoints."""
import pytest
import json
from datetime import datetime, timedelta
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.pipeline import Pipeline, Stage
from app.models.task import Task
from app.models.note import Note
from app.models.user import User
from app.models.tenant import Tenant


class TestContactEndpoints:
    """Test contact management endpoints."""
    
    def test_list_contacts(self, client, auth_headers, test_tenant):
        """Test listing contacts."""
        # Create test contact
        contact = Contact.create(
            tenant_id=test_tenant.id,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            company="Test Company"
        )
        
        response = client.get('/api/v1/crm/contacts', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 1
        
        # Check contact data
        contact_data = next((c for c in data['data']['items'] if c['id'] == contact.id), None)
        assert contact_data is not None
        assert contact_data['first_name'] == "John"
        assert contact_data['last_name'] == "Doe"
        assert contact_data['email'] == "john.doe@example.com"
    
    def test_create_contact(self, client, auth_headers, test_tenant):
        """Test creating a contact."""
        contact_data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane.smith@example.com",
            "company": "Smith Corp",
            "phone": "+1234567890",
            "contact_type": "prospect"
        }
        
        response = client.post(
            '/api/v1/crm/contacts',
            headers=auth_headers,
            json=contact_data
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['first_name'] == "Jane"
        assert data['data']['email'] == "jane.smith@example.com"
    
    def test_get_contact(self, client, auth_headers, test_tenant):
        """Test getting a specific contact."""
        contact = Contact.create(
            tenant_id=test_tenant.id,
            first_name="Bob",
            last_name="Johnson",
            email="bob.johnson@example.com"
        )
        
        response = client.get(f'/api/v1/crm/contacts/{contact.id}', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == contact.id
        assert data['data']['first_name'] == "Bob"
    
    def test_update_contact(self, client, auth_headers, test_tenant):
        """Test updating a contact."""
        contact = Contact.create(
            tenant_id=test_tenant.id,
            first_name="Alice",
            last_name="Brown",
            email="alice.brown@example.com"
        )
        
        update_data = {
            "first_name": "Alice Updated",
            "phone": "+9876543210"
        }
        
        response = client.put(
            f'/api/v1/crm/contacts/{contact.id}',
            headers=auth_headers,
            json=update_data
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['first_name'] == "Alice Updated"
        assert data['data']['phone'] == "+9876543210"
    
    def test_delete_contact(self, client, auth_headers, test_tenant):
        """Test deleting a contact."""
        contact = Contact.create(
            tenant_id=test_tenant.id,
            first_name="Delete",
            last_name="Me",
            email="delete.me@example.com"
        )
        
        response = client.delete(f'/api/v1/crm/contacts/{contact.id}', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True


class TestPipelineEndpoints:
    """Test pipeline management endpoints."""
    
    def test_list_pipelines(self, client, auth_headers, test_tenant):
        """Test listing pipelines."""
        # Create test pipeline
        pipeline = Pipeline.create_default(test_tenant.id)
        
        response = client.get('/api/v1/crm/pipelines', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']) >= 1
        
        # Check pipeline data
        pipeline_data = next((p for p in data['data'] if p['id'] == pipeline.id), None)
        assert pipeline_data is not None
        assert pipeline_data['name'] == "Sales Pipeline"
        assert pipeline_data['is_default'] is True
    
    def test_create_pipeline(self, client, auth_headers, test_tenant):
        """Test creating a pipeline."""
        pipeline_data = {
            "name": "Custom Pipeline",
            "description": "A custom sales pipeline",
            "stages": [
                {"name": "Initial", "color": "#3498db"},
                {"name": "Final", "color": "#27ae60", "is_closed": True, "is_won": True}
            ]
        }
        
        response = client.post(
            '/api/v1/crm/pipelines',
            headers=auth_headers,
            json=pipeline_data
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['name'] == "Custom Pipeline"
        assert len(data['data']['stages']) == 2
    
    def test_get_pipeline(self, client, auth_headers, test_tenant):
        """Test getting a specific pipeline."""
        pipeline = Pipeline.create_default(test_tenant.id)
        
        response = client.get(f'/api/v1/crm/pipelines/{pipeline.id}', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == pipeline.id
        assert data['data']['name'] == "Sales Pipeline"


class TestLeadEndpoints:
    """Test lead management endpoints."""
    
    def test_list_leads(self, client, auth_headers, test_tenant, test_user):
        """Test listing leads."""
        # Create test data
        contact = Contact.create(
            tenant_id=test_tenant.id,
            first_name="Lead",
            last_name="Contact",
            email="lead.contact@example.com"
        )
        
        pipeline = Pipeline.create_default(test_tenant.id)
        first_stage = pipeline.get_first_stage()
        
        lead = Lead.create(
            tenant_id=test_tenant.id,
            title="Test Lead",
            contact_id=contact.id,
            pipeline_id=pipeline.id,
            stage_id=first_stage.id,
            assigned_to_id=test_user.id
        )
        
        response = client.get('/api/v1/crm/leads', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 1
        
        # Check lead data
        lead_data = next((l for l in data['data']['items'] if l['id'] == lead.id), None)
        assert lead_data is not None
        assert lead_data['title'] == "Test Lead"
        assert lead_data['contact_name'] == "Lead Contact"
    
    def test_create_lead(self, client, auth_headers, test_tenant, test_user):
        """Test creating a lead."""
        # Create test contact and pipeline
        contact = Contact.create(
            tenant_id=test_tenant.id,
            first_name="New",
            last_name="Lead",
            email="new.lead@example.com"
        )
        
        pipeline = Pipeline.create_default(test_tenant.id)
        
        lead_data = {
            "title": "New Business Opportunity",
            "description": "Potential new client",
            "contact_id": contact.id,
            "pipeline_id": pipeline.id,
            "value": 10000.00,
            "probability": 75,
            "assigned_to_id": test_user.id
        }
        
        response = client.post(
            '/api/v1/crm/leads',
            headers=auth_headers,
            json=lead_data
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == "New Business Opportunity"
        assert data['data']['value'] == "10000.00"
    
    def test_get_lead(self, client, auth_headers, test_tenant):
        """Test getting a specific lead."""
        contact = Contact.create(
            tenant_id=test_tenant.id,
            first_name="Get",
            last_name="Lead",
            email="get.lead@example.com"
        )
        
        pipeline = Pipeline.create_default(test_tenant.id)
        first_stage = pipeline.get_first_stage()
        
        lead = Lead.create(
            tenant_id=test_tenant.id,
            title="Get Lead Test",
            contact_id=contact.id,
            pipeline_id=pipeline.id,
            stage_id=first_stage.id
        )
        
        response = client.get(f'/api/v1/crm/leads/{lead.id}', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == lead.id
        assert data['data']['title'] == "Get Lead Test"


class TestTaskEndpoints:
    """Test task management endpoints."""
    
    def test_list_tasks(self, client, auth_headers, test_tenant, test_user):
        """Test listing tasks."""
        # Create test task
        task = Task.create(
            tenant_id=test_tenant.id,
            title="Test Task",
            description="A test task",
            assigned_to_id=test_user.id,
            priority="high"
        )
        
        response = client.get('/api/v1/crm/tasks', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 1
        
        # Check task data
        task_data = next((t for t in data['data']['items'] if t['id'] == task.id), None)
        assert task_data is not None
        assert task_data['title'] == "Test Task"
        assert task_data['priority'] == "high"
    
    def test_create_task(self, client, auth_headers, test_tenant, test_user):
        """Test creating a task."""
        task_data = {
            "title": "New Task",
            "description": "A new task to complete",
            "assigned_to_id": test_user.id,
            "priority": "medium",
            "task_type": "call",
            "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat()
        }
        
        response = client.post(
            '/api/v1/crm/tasks',
            headers=auth_headers,
            json=task_data
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == "New Task"
        assert data['data']['task_type'] == "call"
    
    def test_update_task_status(self, client, auth_headers, test_tenant, test_user):
        """Test updating task status."""
        task = Task.create(
            tenant_id=test_tenant.id,
            title="Status Test Task",
            assigned_to_id=test_user.id
        )
        
        status_data = {"status": "completed"}
        
        response = client.put(
            f'/api/v1/crm/tasks/{task.id}/status',
            headers=auth_headers,
            json=status_data
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['status'] == "completed"
        assert data['data']['is_completed'] is True


class TestNoteEndpoints:
    """Test note management endpoints."""
    
    def test_list_notes(self, client, auth_headers, test_tenant, test_user):
        """Test listing notes."""
        # Create test note
        note = Note.create(
            tenant_id=test_tenant.id,
            user_id=test_user.id,
            title="Test Note",
            content="This is a test note content"
        )
        
        response = client.get('/api/v1/crm/notes', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 1
        
        # Check note data
        note_data = next((n for n in data['data']['items'] if n['id'] == note.id), None)
        assert note_data is not None
        assert note_data['title'] == "Test Note"
        assert note_data['content'] == "This is a test note content"
    
    def test_create_note(self, client, auth_headers, test_tenant, test_user):
        """Test creating a note."""
        note_data = {
            "title": "New Note",
            "content": "This is a new note with important information",
            "note_type": "meeting",
            "is_pinned": True
        }
        
        response = client.post(
            '/api/v1/crm/notes',
            headers=auth_headers,
            json=note_data
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == "New Note"
        assert data['data']['note_type'] == "meeting"
        assert data['data']['is_pinned'] is True
    
    def test_create_note_with_lead(self, client, auth_headers, test_tenant, test_user):
        """Test creating a note linked to a lead."""
        # Create test lead
        contact = Contact.create(
            tenant_id=test_tenant.id,
            first_name="Note",
            last_name="Lead",
            email="note.lead@example.com"
        )
        
        pipeline = Pipeline.create_default(test_tenant.id)
        first_stage = pipeline.get_first_stage()
        
        lead = Lead.create(
            tenant_id=test_tenant.id,
            title="Lead with Note",
            contact_id=contact.id,
            pipeline_id=pipeline.id,
            stage_id=first_stage.id
        )
        
        note_data = {
            "content": "Important note about this lead",
            "lead_id": lead.id,
            "note_type": "call"
        }
        
        response = client.post(
            '/api/v1/crm/notes',
            headers=auth_headers,
            json=note_data
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['lead_id'] == lead.id
        assert data['data']['lead_title'] == "Lead with Note"


class TestCRMIntegration:
    """Test CRM integration scenarios."""
    
    def test_lead_with_tasks_and_notes(self, client, auth_headers, test_tenant, test_user):
        """Test creating a lead with associated tasks and notes."""
        # Create contact and pipeline
        contact = Contact.create(
            tenant_id=test_tenant.id,
            first_name="Integration",
            last_name="Test",
            email="integration.test@example.com"
        )
        
        pipeline = Pipeline.create_default(test_tenant.id)
        first_stage = pipeline.get_first_stage()
        
        # Create lead
        lead_data = {
            "title": "Integration Test Lead",
            "contact_id": contact.id,
            "pipeline_id": pipeline.id,
            "value": 5000.00
        }
        
        response = client.post(
            '/api/v1/crm/leads',
            headers=auth_headers,
            json=lead_data
        )
        assert response.status_code == 201
        lead_id = json.loads(response.data)['data']['id']
        
        # Create task for the lead
        task_data = {
            "title": "Follow up call",
            "lead_id": lead_id,
            "assigned_to_id": test_user.id,
            "task_type": "call"
        }
        
        response = client.post(
            '/api/v1/crm/tasks',
            headers=auth_headers,
            json=task_data
        )
        assert response.status_code == 201
        
        # Create note for the lead
        note_data = {
            "content": "Initial conversation went well",
            "lead_id": lead_id,
            "note_type": "call"
        }
        
        response = client.post(
            '/api/v1/crm/notes',
            headers=auth_headers,
            json=note_data
        )
        assert response.status_code == 201
        
        # Verify lead has associated task and note counts
        response = client.get(f'/api/v1/crm/leads/{lead_id}', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['data']['task_count'] == 1
        assert data['data']['note_count'] == 1
    
    def test_pipeline_stage_management(self, client, auth_headers, test_tenant):
        """Test pipeline and stage management."""
        # Create custom pipeline
        pipeline_data = {
            "name": "Custom Sales Process",
            "description": "Our custom sales process",
            "stages": [
                {"name": "Inquiry", "color": "#3498db"},
                {"name": "Demo", "color": "#f39c12"},
                {"name": "Proposal", "color": "#e74c3c"},
                {"name": "Won", "color": "#27ae60", "is_closed": True, "is_won": True},
                {"name": "Lost", "color": "#95a5a6", "is_closed": True, "is_won": False}
            ]
        }
        
        response = client.post(
            '/api/v1/crm/pipelines',
            headers=auth_headers,
            json=pipeline_data
        )
        assert response.status_code == 201
        
        pipeline_id = json.loads(response.data)['data']['id']
        stages = json.loads(response.data)['data']['stages']
        
        # Test stage ordering
        stage_ids = [stage['id'] for stage in stages]
        reorder_data = {
            "stages_order": [stage_ids[1], stage_ids[0], stage_ids[2], stage_ids[3], stage_ids[4]]
        }
        
        response = client.put(
            f'/api/v1/crm/pipelines/{pipeline_id}/stages',
            headers=auth_headers,
            json=reorder_data
        )
        assert response.status_code == 200
        
        # Verify new order
        response = client.get(f'/api/v1/crm/pipelines/{pipeline_id}', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        reordered_stages = data['data']['stages']
        assert reordered_stages[0]['name'] == "Demo"  # Was second, now first
        assert reordered_stages[1]['name'] == "Inquiry"  # Was first, now second