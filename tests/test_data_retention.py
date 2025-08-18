"""Tests for data retention and GDPR compliance functionality."""
import pytest
import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from app import create_app, db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.inbox_message import InboxMessage
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.gdpr_compliance import (
    DataRetentionPolicy, ConsentRecord, ConsentType, ConsentStatus,
    PIIDetectionLog, DataDeletionRequest, DataExportRequest
)
from app.services.data_retention_service import DataRetentionService
from app.services.consent_service import ConsentService
from app.services.pii_service import PIIDetector, DataMinimizer
from app.services.gdpr_request_service import GDPRRequestService
from app.workers.data_retention import (
    cleanup_expired_data, check_expired_consents,
    process_data_deletion_request, process_data_export_request
)


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def tenant(app):
    """Create test tenant."""
    tenant = Tenant.create(
        name="Test Company",
        slug="test-company",
        email="test@example.com"
    )
    return tenant


@pytest.fixture
def user(app, tenant):
    """Create test user."""
    user = User.create(
        tenant_id=tenant.id,
        email="user@example.com",
        password="password123",
        role="owner"
    )
    return user


@pytest.fixture
def retention_service(app):
    """Create data retention service."""
    return DataRetentionService(db.session)


@pytest.fixture
def consent_service(app):
    """Create consent service."""
    return ConsentService(db.session)


@pytest.fixture
def pii_detector():
    """Create PII detector."""
    return PIIDetector()


@pytest.fixture
def data_minimizer(app):
    """Create data minimizer."""
    return DataMinimizer(db.session)


@pytest.fixture
def gdpr_service(app):
    """Create GDPR request service."""
    return GDPRRequestService(db.session)


class TestDataRetentionService:
    """Test data retention service functionality."""
    
    def test_create_retention_policy(self, retention_service, tenant):
        """Test creating a data retention policy."""
        policy = retention_service.create_retention_policy(
            tenant_id=tenant.id,
            name="Test Policy",
            data_type="messages",
            table_name="inbox_messages",
            retention_days=365,
            auto_delete=True,
            legal_basis="legitimate_interest",
            description="Test retention policy"
        )
        
        assert policy.id is not None
        assert policy.name == "Test Policy"
        assert policy.data_type == "messages"
        assert policy.retention_days == 365
        assert policy.auto_delete is True
        assert policy.is_active is True
    
    def test_get_tenant_policies(self, retention_service, tenant):
        """Test getting tenant retention policies."""
        # Create test policies
        policy1 = retention_service.create_retention_policy(
            tenant_id=tenant.id,
            name="Policy 1",
            data_type="messages",
            table_name="inbox_messages",
            retention_days=365
        )
        
        policy2 = retention_service.create_retention_policy(
            tenant_id=tenant.id,
            name="Policy 2",
            data_type="contacts",
            table_name="contacts",
            retention_days=1095,
            auto_delete=False
        )
        
        # Test getting all policies
        policies = retention_service.get_tenant_policies(tenant.id, active_only=False)
        assert len(policies) == 2
        
        # Test getting only active policies
        policy2.is_active = False
        policy2.save()
        
        active_policies = retention_service.get_tenant_policies(tenant.id, active_only=True)
        assert len(active_policies) == 1
        assert active_policies[0].name == "Policy 1"
    
    def test_find_expired_data(self, retention_service, tenant):
        """Test finding expired data."""
        # Create retention policy
        policy = retention_service.create_retention_policy(
            tenant_id=tenant.id,
            name="Message Retention",
            data_type="messages",
            table_name="inbox_messages",
            retention_days=30
        )
        
        # Create old message (should be expired)
        old_date = datetime.utcnow() - timedelta(days=35)
        old_message = InboxMessage.create(
            tenant_id=tenant.id,
            channel_id=1,
            sender_id="test_sender",
            content="Old message",
            created_at=old_date
        )
        
        # Create recent message (should not be expired)
        recent_message = InboxMessage.create(
            tenant_id=tenant.id,
            channel_id=1,
            sender_id="test_sender",
            content="Recent message"
        )
        
        # Find expired data
        expired_data = retention_service.find_expired_data(tenant.id)
        
        assert expired_data['tenant_id'] == tenant.id
        assert expired_data['total_expired_records'] > 0
        assert 'messages' in expired_data['expired_data']
    
    def test_cleanup_expired_data_dry_run(self, retention_service, tenant):
        """Test cleanup expired data in dry run mode."""
        # Create retention policy
        policy = retention_service.create_retention_policy(
            tenant_id=tenant.id,
            name="Message Retention",
            data_type="messages",
            table_name="inbox_messages",
            retention_days=30,
            auto_delete=True
        )
        
        # Create old message
        old_date = datetime.utcnow() - timedelta(days=35)
        old_message = InboxMessage.create(
            tenant_id=tenant.id,
            channel_id=1,
            sender_id="test_sender",
            content="Old message",
            created_at=old_date
        )
        
        # Run cleanup in dry run mode
        cleanup_report = retention_service.cleanup_expired_data(
            tenant_id=tenant.id,
            dry_run=True
        )
        
        assert cleanup_report['dry_run'] is True
        assert cleanup_report['total_deleted'] >= 0
        
        # Verify message still exists
        assert InboxMessage.query.get(old_message.id) is not None
    
    def test_cleanup_expired_data_actual(self, retention_service, tenant):
        """Test actual cleanup of expired data."""
        # Create retention policy
        policy = retention_service.create_retention_policy(
            tenant_id=tenant.id,
            name="Message Retention",
            data_type="messages",
            table_name="inbox_messages",
            retention_days=30,
            auto_delete=True
        )
        
        # Create old message
        old_date = datetime.utcnow() - timedelta(days=35)
        old_message = InboxMessage.create(
            tenant_id=tenant.id,
            channel_id=1,
            sender_id="test_sender",
            content="Old message",
            created_at=old_date
        )
        
        # Run actual cleanup
        cleanup_report = retention_service.cleanup_expired_data(
            tenant_id=tenant.id,
            dry_run=False
        )
        
        assert cleanup_report['dry_run'] is False
        
        # Verify message is soft deleted
        updated_message = InboxMessage.query.get(old_message.id)
        assert updated_message.is_deleted is True
    
    def test_create_default_policies(self, retention_service, tenant):
        """Test creating default retention policies."""
        policies = retention_service.create_default_policies(tenant.id)
        
        assert len(policies) > 0
        
        # Check that different data types are covered
        data_types = [policy.data_type for policy in policies]
        expected_types = ['messages', 'contacts', 'leads', 'documents', 'audit_logs']
        
        for expected_type in expected_types:
            assert expected_type in data_types


class TestConsentService:
    """Test consent management service."""
    
    def test_grant_consent(self, consent_service, tenant, user):
        """Test granting consent."""
        consent_record = consent_service.grant_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            purpose="Marketing communications",
            user_id=user.id,
            legal_basis="consent",
            source="web"
        )
        
        assert consent_record.id is not None
        assert consent_record.consent_type == ConsentType.MARKETING
        assert consent_record.status == ConsentStatus.GRANTED
        assert consent_record.user_id == user.id
        assert consent_record.is_valid() is True
    
    def test_withdraw_consent(self, consent_service, tenant, user):
        """Test withdrawing consent."""
        # First grant consent
        consent_record = consent_service.grant_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            purpose="Marketing communications",
            user_id=user.id
        )
        
        # Then withdraw it
        success = consent_service.withdraw_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            user_id=user.id,
            reason="User request"
        )
        
        assert success is True
        
        # Verify consent is withdrawn
        updated_consent = ConsentRecord.query.get(consent_record.id)
        assert updated_consent.status == ConsentStatus.WITHDRAWN
        assert updated_consent.is_valid() is False
    
    def test_has_valid_consent(self, consent_service, tenant, user):
        """Test checking for valid consent."""
        # Initially no consent
        has_consent = consent_service.has_valid_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            user_id=user.id
        )
        assert has_consent is False
        
        # Grant consent
        consent_service.grant_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            purpose="Marketing communications",
            user_id=user.id
        )
        
        # Now should have consent
        has_consent = consent_service.has_valid_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            user_id=user.id
        )
        assert has_consent is True
    
    def test_check_expired_consents(self, consent_service, tenant, user):
        """Test checking for expired consents."""
        # Create consent that expires in the past
        expired_date = datetime.utcnow() - timedelta(days=1)
        consent_record = consent_service.grant_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            purpose="Marketing communications",
            user_id=user.id,
            expires_at=expired_date
        )
        
        # Check expired consents
        report = consent_service.check_expired_consents(tenant.id)
        
        assert report['expired_count'] == 1
        
        # Verify consent status is updated
        updated_consent = ConsentRecord.query.get(consent_record.id)
        assert updated_consent.status == ConsentStatus.EXPIRED
    
    def test_get_consent_summary(self, consent_service, tenant, user):
        """Test getting consent summary."""
        # Create various consents
        consent_service.grant_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            purpose="Marketing",
            user_id=user.id
        )
        
        consent_service.grant_consent(
            tenant_id=tenant.id,
            consent_type="analytics",
            purpose="Analytics",
            user_id=user.id
        )
        
        # Get summary
        summary = consent_service.get_consent_summary(tenant.id)
        
        assert summary['tenant_id'] == tenant.id
        assert summary['total_consents'] == 2
        assert 'by_type' in summary
        assert 'by_status' in summary
        assert summary['by_type']['marketing']['granted'] == 1
        assert summary['by_type']['analytics']['granted'] == 1


class TestPIIDetector:
    """Test PII detection functionality."""
    
    def test_detect_email_in_text(self, pii_detector):
        """Test detecting email addresses."""
        text = "Please contact me at john.doe@example.com for more information."
        
        detected_pii = pii_detector.detect_pii_in_text(text)
        
        assert len(detected_pii) == 1
        assert detected_pii[0]['type'] == 'email'
        assert detected_pii[0]['value'] == 'john.doe@example.com'
        assert detected_pii[0]['confidence'] == 'high'
    
    def test_detect_phone_in_text(self, pii_detector):
        """Test detecting phone numbers."""
        text = "Call me at (555) 123-4567 or 555-987-6543."
        
        detected_pii = pii_detector.detect_pii_in_text(text)
        
        assert len(detected_pii) == 2
        phone_values = [item['value'] for item in detected_pii]
        assert '(555) 123-4567' in phone_values
        assert '555-987-6543' in phone_values
    
    def test_detect_multiple_pii_types(self, pii_detector):
        """Test detecting multiple PII types."""
        text = "Contact John at john@example.com or call (555) 123-4567. SSN: 123-45-6789"
        
        detected_pii = pii_detector.detect_pii_in_text(text)
        
        pii_types = [item['type'] for item in detected_pii]
        assert 'email' in pii_types
        assert 'phone' in pii_types
        assert 'ssn' in pii_types
    
    def test_mask_pii_in_text(self, pii_detector):
        """Test masking PII in text."""
        text = "Contact me at john.doe@example.com"
        
        masked_text, masked_items = pii_detector.mask_pii_in_text(text)
        
        assert 'john.doe@example.com' not in masked_text
        assert len(masked_items) == 1
        assert masked_items[0]['type'] == 'email'
        assert masked_items[0]['original_value'] == 'john.doe@example.com'
    
    def test_detect_pii_in_data(self, pii_detector):
        """Test detecting PII in structured data."""
        data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'phone': '555-123-4567',
            'message': 'Please call me at (555) 987-6543'
        }
        
        field_mapping = {
            'email': 'email',
            'phone': 'phone'
        }
        
        detected_pii = pii_detector.detect_pii_in_data(data, field_mapping)
        
        assert 'email' in detected_pii
        assert 'phone' in detected_pii
        assert 'message' in detected_pii  # Should detect phone in message content
    
    def test_anonymize_data(self, pii_detector):
        """Test anonymizing structured data."""
        data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'phone': '555-123-4567'
        }
        
        field_mapping = {
            'email': 'email',
            'phone': 'phone'
        }
        
        anonymized_data, log = pii_detector.anonymize_data(data, field_mapping)
        
        assert anonymized_data['email'] != data['email']
        assert anonymized_data['phone'] != data['phone']
        assert len(log) >= 2  # Should have logs for email and phone


class TestDataMinimizer:
    """Test data minimization functionality."""
    
    def test_minimize_message_data(self, data_minimizer):
        """Test minimizing message data."""
        message_data = {
            'id': 1,
            'content': 'Please contact me at john@example.com',
            'sender_email': 'sender@example.com',
            'sender_name': 'John Doe',
            'sender_phone': '555-123-4567'
        }
        
        minimized_data = data_minimizer.minimize_message_data(message_data)
        
        # Should mask PII in content and sender fields
        assert minimized_data['sender_email'] != message_data['sender_email']
        assert minimized_data['content'] != message_data['content']
    
    def test_minimize_contact_data(self, data_minimizer):
        """Test minimizing contact data."""
        contact_data = {
            'id': 1,
            'name': 'John Doe',
            'email': 'john@example.com',
            'phone': '555-123-4567',
            'company': 'Example Corp'
        }
        
        minimized_data = data_minimizer.minimize_contact_data(contact_data)
        
        # Should mask PII fields
        assert minimized_data['email'] != contact_data['email']
        assert minimized_data['phone'] != contact_data['phone']


class TestGDPRRequestService:
    """Test GDPR request processing."""
    
    def test_create_deletion_request(self, gdpr_service, tenant, user):
        """Test creating a data deletion request."""
        deletion_request = gdpr_service.create_deletion_request(
            tenant_id=tenant.id,
            request_type='full_deletion',
            user_id=user.id,
            reason='User requested account deletion'
        )
        
        assert deletion_request.id is not None
        assert deletion_request.request_id is not None
        assert deletion_request.request_type == 'full_deletion'
        assert deletion_request.user_id == user.id
        assert deletion_request.status == 'pending'
        assert deletion_request.verification_token is not None
    
    def test_create_export_request(self, gdpr_service, tenant, user):
        """Test creating a data export request."""
        export_request = gdpr_service.create_export_request(
            tenant_id=tenant.id,
            user_id=user.id,
            export_format='json',
            data_types=['messages', 'contacts']
        )
        
        assert export_request.id is not None
        assert export_request.request_id is not None
        assert export_request.user_id == user.id
        assert export_request.export_format == 'json'
        assert export_request.data_types == ['messages', 'contacts']
        assert export_request.status == 'pending'
    
    @patch('app.services.gdpr_request_service.os.path.exists')
    @patch('app.services.gdpr_request_service.os.path.getsize')
    def test_process_export_request(self, mock_getsize, mock_exists, gdpr_service, tenant, user):
        """Test processing a data export request."""
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        
        # Create export request
        export_request = gdpr_service.create_export_request(
            tenant_id=tenant.id,
            user_id=user.id,
            export_format='json'
        )
        
        # Process the request
        with patch.object(gdpr_service, '_create_export_file') as mock_create_file:
            mock_create_file.return_value = '/tmp/test_export.json'
            
            result = gdpr_service.process_export_request(export_request)
            
            assert result['status'] == 'completed'
            assert result['file_path'] == '/tmp/test_export.json'
            assert result['file_size'] == 1024


class TestDataRetentionWorkers:
    """Test data retention background workers."""
    
    @patch('app.workers.data_retention.DataRetentionService')
    def test_cleanup_expired_data_worker(self, mock_service_class, tenant):
        """Test cleanup expired data worker."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.cleanup_expired_data.return_value = {
            'total_deleted': 5,
            'total_anonymized': 2,
            'errors': []
        }
        
        # Test worker function (without actual Celery task execution)
        from app.workers.data_retention import cleanup_expired_data
        
        # Mock the task execution
        with patch.object(cleanup_expired_data, 'apply_async') as mock_apply:
            mock_apply.return_value.id = 'test-task-id'
            
            # This would normally be called by Celery
            result = cleanup_expired_data(
                tenant_id=tenant.id,
                dry_run=False,
                batch_size=100
            )
            
            # Verify the mock was called correctly
            mock_service.cleanup_expired_data.assert_called_once()
    
    @patch('app.workers.data_retention.ConsentService')
    def test_check_expired_consents_worker(self, mock_service_class, tenant):
        """Test check expired consents worker."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.check_expired_consents.return_value = {
            'expired_count': 3,
            'tenant_id': tenant.id
        }
        
        from app.workers.data_retention import check_expired_consents
        
        with patch.object(check_expired_consents, 'apply_async') as mock_apply:
            mock_apply.return_value.id = 'test-task-id'
            
            result = check_expired_consents(tenant_id=tenant.id)
            
            mock_service.check_expired_consents.assert_called_once_with(tenant.id)


class TestDataRetentionIntegration:
    """Integration tests for data retention functionality."""
    
    def test_end_to_end_message_retention(self, app, tenant, retention_service):
        """Test end-to-end message retention process."""
        # Create retention policy
        policy = retention_service.create_retention_policy(
            tenant_id=tenant.id,
            name="Message Retention",
            data_type="messages",
            table_name="inbox_messages",
            retention_days=30,
            auto_delete=True
        )
        
        # Create old and new messages
        old_date = datetime.utcnow() - timedelta(days=35)
        old_message = InboxMessage.create(
            tenant_id=tenant.id,
            channel_id=1,
            sender_id="old_sender",
            content="Old message",
            created_at=old_date
        )
        
        new_message = InboxMessage.create(
            tenant_id=tenant.id,
            channel_id=1,
            sender_id="new_sender",
            content="New message"
        )
        
        # Find expired data
        expired_data = retention_service.find_expired_data(tenant.id)
        assert expired_data['total_expired_records'] > 0
        
        # Cleanup expired data
        cleanup_report = retention_service.cleanup_expired_data(
            tenant_id=tenant.id,
            dry_run=False
        )
        
        assert cleanup_report['total_deleted'] > 0
        
        # Verify old message is deleted, new message remains
        old_msg_updated = InboxMessage.query.get(old_message.id)
        new_msg_updated = InboxMessage.query.get(new_message.id)
        
        assert old_msg_updated.is_deleted is True
        assert new_msg_updated.is_deleted is False
    
    def test_consent_lifecycle(self, app, tenant, user, consent_service):
        """Test complete consent lifecycle."""
        # Grant consent
        consent_record = consent_service.grant_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            purpose="Marketing communications",
            user_id=user.id,
            source="web"
        )
        
        # Verify consent is valid
        assert consent_service.has_valid_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            user_id=user.id
        ) is True
        
        # Withdraw consent
        success = consent_service.withdraw_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            user_id=user.id,
            reason="User request"
        )
        
        assert success is True
        
        # Verify consent is no longer valid
        assert consent_service.has_valid_consent(
            tenant_id=tenant.id,
            consent_type="marketing",
            user_id=user.id
        ) is False
    
    def test_pii_detection_and_logging(self, app, tenant, pii_detector):
        """Test PII detection with logging."""
        text_with_pii = "Contact John Doe at john.doe@example.com or call (555) 123-4567"
        
        # Detect PII
        detected_pii = pii_detector.detect_pii_in_text(text_with_pii)
        
        assert len(detected_pii) >= 2  # Should detect email and phone
        
        # Log PII detection
        for pii_item in detected_pii:
            log_entry = PIIDetectionLog.log_detection(
                tenant_id=tenant.id,
                source_table='test_table',
                source_id=1,
                field_name='content',
                pii_type=pii_item['type'],
                confidence=pii_item['confidence'],
                action_taken='detected',
                original_value=pii_item['value']
            )
            
            assert log_entry.id is not None
            assert log_entry.tenant_id == tenant.id
            assert log_entry.pii_type == pii_item['type']