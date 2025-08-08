"""Test CRM models."""
import pytest
from datetime import datetime, timedelta
from app.models.tenant import Tenant
from app.models.user import User
from app.models.contact import Contact
from app.models.pipeline import Pipeline, Stage
from app.models.lead import Lead
from app.models.task import Task
from app.models.note import Note
from app import db


class TestContact:
    """Test Contact model."""
    
    def test_create_contact(self, app):
        """Test contact creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            contact = Contact(
                tenant_id=tenant.id,
                first_name="John",
                last_name="Doe",
                email="john@example.com",
                company="Test Company"
            )
            contact.save()
            
            assert contact.id is not None
            assert contact.full_name == "John Doe"
            assert contact.display_name == "John Doe (Test Company)"
            assert contact.email == "john@example.com"
    
    def test_contact_custom_fields_and_tags(self, app):
        """Test contact custom fields and tags."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            contact = Contact(tenant_id=tenant.id, email="test@example.com")
            contact.save()
            
            # Test custom fields
            contact.set_custom_field("industry", "Technology")
            contact.set_custom_field("budget", 50000)
            contact.save()
            
            assert contact.get_custom_field("industry") == "Technology"
            assert contact.get_custom_field("budget") == 50000
            assert contact.get_custom_field("nonexistent") is None
            
            # Test tags
            contact.add_tag("vip")
            contact.add_tag("hot_lead")
            contact.save()
            
            assert contact.has_tag("vip")
            assert contact.has_tag("hot_lead")
            assert len(contact.tags) == 2
            
            contact.remove_tag("vip")
            contact.save()
            
            assert not contact.has_tag("vip")
            assert contact.has_tag("hot_lead")
    
    def test_find_or_create_by_email(self, app):
        """Test finding or creating contact by email."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Test creating new contact
            contact1, created1 = Contact.find_or_create_by_email(
                tenant_id=tenant.id,
                email="new@example.com",
                first_name="New",
                last_name="User"
            )
            
            assert created1 is True
            assert contact1.email == "new@example.com"
            assert contact1.first_name == "New"
            
            # Test finding existing contact
            contact2, created2 = Contact.find_or_create_by_email(
                tenant_id=tenant.id,
                email="new@example.com"
            )
            
            assert created2 is False
            assert contact2.id == contact1.id


class TestPipeline:
    """Test Pipeline and Stage models."""
    
    def test_create_pipeline(self, app):
        """Test pipeline creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            pipeline = Pipeline(
                tenant_id=tenant.id,
                name="Sales Pipeline",
                description="Main sales pipeline"
            )
            pipeline.save()
            
            assert pipeline.id is not None
            assert pipeline.name == "Sales Pipeline"
            assert pipeline.is_active is True
    
    def test_create_default_pipeline(self, app):
        """Test creating default pipeline with stages."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            pipeline = Pipeline.create_default(tenant_id=tenant.id)
            
            assert pipeline.is_default is True
            assert len(pipeline.stages) == 6  # Default stages
            assert pipeline.stages_order is not None
            assert len(pipeline.stages_order) == 6
            
            # Test stage ordering
            ordered_stages = pipeline.get_ordered_stages()
            assert len(ordered_stages) == 6
            assert ordered_stages[0].name == "Lead"
            assert ordered_stages[-1].name == "Closed Lost"
    
    def test_pipeline_stage_management(self, app):
        """Test pipeline stage management."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            pipeline = Pipeline(tenant_id=tenant.id, name="Test Pipeline")
            pipeline.save()
            
            # Add stages
            stage1 = pipeline.add_stage("New Lead", color="#3498db")
            stage2 = pipeline.add_stage("Qualified", color="#f39c12")
            stage3 = pipeline.add_stage("Closed Won", color="#27ae60", is_won=True, is_closed=True)
            
            assert len(pipeline.stages) == 3
            assert len(pipeline.stages_order) == 3
            
            # Test stage relationships
            assert stage1.pipeline_id == pipeline.id
            assert stage2.position == 1
            assert stage3.is_won is True
            
            # Test getting stages by name
            found_stage = pipeline.get_stage_by_name("Qualified")
            assert found_stage.id == stage2.id


class TestLead:
    """Test Lead model."""
    
    def test_create_lead(self, app):
        """Test lead creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            contact = Contact(tenant_id=tenant.id, email="lead@example.com")
            contact.save()
            
            pipeline = Pipeline.create_default(tenant_id=tenant.id)
            first_stage = pipeline.get_first_stage()
            
            lead = Lead(
                tenant_id=tenant.id,
                contact_id=contact.id,
                pipeline_id=pipeline.id,
                stage_id=first_stage.id,
                title="Test Lead",
                value=5000,
                probability=75
            )
            lead.save()
            
            assert lead.id is not None
            assert lead.title == "Test Lead"
            assert lead.value == 5000
            assert lead.probability == 75
            assert lead.weighted_value == 3750.0  # 5000 * 0.75
            assert lead.is_open is True
    
    def test_lead_status_management(self, app):
        """Test lead status management."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            pipeline = Pipeline.create_default(tenant_id=tenant.id)
            first_stage = pipeline.get_first_stage()
            
            lead = Lead(
                tenant_id=tenant.id,
                pipeline_id=pipeline.id,
                stage_id=first_stage.id,
                title="Test Lead"
            )
            lead.save()
            
            # Test marking as won
            lead.mark_as_won()
            lead.save()
            
            assert lead.is_won is True
            assert lead.status == "won"
            assert lead.probability == 100
            
            # Test reopening
            lead.reopen()
            lead.save()
            
            assert lead.is_open is True
            assert lead.status == "open"
            assert lead.probability == 50  # Reset to default
    
    def test_create_lead_from_contact(self, app):
        """Test creating lead from contact."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            contact = Contact(tenant_id=tenant.id, email="lead@example.com")
            contact.save()
            
            pipeline = Pipeline.create_default(tenant_id=tenant.id)
            
            lead = Lead.create_from_contact(
                tenant_id=tenant.id,
                contact_id=contact.id,
                title="New Opportunity",
                value=10000
            )
            
            assert lead.contact_id == contact.id
            assert lead.pipeline_id == pipeline.id
            assert lead.stage_id == pipeline.get_first_stage().id
            assert lead.title == "New Opportunity"


class TestTask:
    """Test Task model."""
    
    def test_create_task(self, app):
        """Test task creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="user@test.com",
                password="password",
                tenant_id=tenant.id
            )
            
            task = Task(
                tenant_id=tenant.id,
                title="Call prospect",
                description="Follow up on the proposal",
                assigned_to_id=user.id,
                priority="high",
                due_date=(datetime.utcnow() + timedelta(days=1)).isoformat()
            )
            task.save()
            
            assert task.id is not None
            assert task.title == "Call prospect"
            assert task.priority == "high"
            assert task.status == "pending"
            assert task.is_completed is False
    
    def test_task_completion(self, app):
        """Test task completion."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            task = Task(
                tenant_id=tenant.id,
                title="Test task"
            )
            task.save()
            
            # Test completion
            task.complete()
            task.save()
            
            assert task.is_completed is True
            assert task.status == "completed"
            assert task.completed_at is not None
            
            # Test reopening
            task.reopen()
            task.save()
            
            assert task.is_completed is False
            assert task.status == "pending"
            assert task.completed_at is None
    
    def test_task_due_date_checks(self, app):
        """Test task due date checks."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Task due yesterday (overdue)
            overdue_task = Task(
                tenant_id=tenant.id,
                title="Overdue task",
                due_date=(datetime.utcnow() - timedelta(days=1)).isoformat()
            )
            overdue_task.save()
            
            # Task due today
            today_task = Task(
                tenant_id=tenant.id,
                title="Today task",
                due_date=datetime.utcnow().isoformat()
            )
            today_task.save()
            
            assert overdue_task.is_overdue is True
            assert overdue_task.is_due_today is False
            
            assert today_task.is_overdue is False
            assert today_task.is_due_today is True


class TestNote:
    """Test Note model."""
    
    def test_create_note(self, app):
        """Test note creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="user@test.com",
                password="password",
                tenant_id=tenant.id
            )
            
            note = Note(
                tenant_id=tenant.id,
                user_id=user.id,
                title="Meeting notes",
                content="Discussed project requirements and timeline.",
                note_type="meeting"
            )
            note.save()
            
            assert note.id is not None
            assert note.title == "Meeting notes"
            assert note.display_title == "Meeting notes"
            assert note.note_type == "meeting"
            assert note.is_private is False
    
    def test_note_privacy(self, app):
        """Test note privacy settings."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user1 = User.create(
                email="user1@test.com",
                password="password",
                tenant_id=tenant.id
            )
            
            user2 = User.create(
                email="user2@test.com",
                password="password",
                tenant_id=tenant.id,
                role="manager"
            )
            
            # Create private note
            private_note = Note(
                tenant_id=tenant.id,
                user_id=user1.id,
                content="Private thoughts",
                is_private=True
            )
            private_note.save()
            
            # Create public note
            public_note = Note(
                tenant_id=tenant.id,
                user_id=user1.id,
                content="Public information",
                is_private=False
            )
            public_note.save()
            
            # Test visibility
            assert private_note.can_be_viewed_by(user1) is True  # Owner can view
            assert private_note.can_be_viewed_by(user2) is False  # Others cannot view private
            
            assert public_note.can_be_viewed_by(user1) is True  # Owner can view
            assert public_note.can_be_viewed_by(user2) is True  # Others can view public
            
            # Test editing
            assert private_note.can_be_edited_by(user1) is True  # Owner can edit
            assert private_note.can_be_edited_by(user2) is False  # Others cannot edit private
            
            assert public_note.can_be_edited_by(user1) is True  # Owner can edit
            assert public_note.can_be_edited_by(user2) is True  # Manager can edit public