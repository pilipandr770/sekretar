"""Tests for notification worker functionality."""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from app.models import (
    Notification, NotificationTemplate, NotificationPreference, NotificationEvent,
    NotificationType, NotificationPriority, NotificationStatus, User, Tenant, Channel
)
from app.workers.notifications import (
    NotificationWorker, send_notification, send_bulk_notifications,
    process_notification_preferences, cleanup_old_notifications,
    send_kyb_alert, send_invoice_notification, send_system_notification
)
from app.services.notification_service import NotificationService
from app.services.notification_templates import NotificationTemplateManager


class TestNotificationWorker:
    """Test notification worker functionality."""
    
    @pytest.fixture
    def notification_worker(self):
        """Create notification worker instance."""
        return NotificationWorker()
    
    @pytest.fixture
    def sample_tenant(self, db_session):
        """Create sample tenant."""
        tenant = Tenant(
            id="test-tenant-id",
            name="Test Company",
            domain="test.com"
        )
        db_session.add(tenant)
        db_session.commit()
        return tenant
    
    @pytest.fixture
    def sample_user(self, db_session, sample_tenant):
        """Create sample user."""
        user = User(
            id="test-user-id",
            tenant_id=sample_tenant.id,
            email="test@test.com",
            role="admin"
        )
        db_session.add(user)
        db_session.commit()
        return user
    
    @pytest.fixture
    def sample_notification(self, db_session, sample_tenant, sample_user):
        """Create sample notification."""
        notification = Notification(
            tenant_id=sample_tenant.id,
            user_id=sample_user.id,
            recipient="test@test.com",
            type=NotificationType.EMAIL.value,
            priority=NotificationPriority.NORMAL.value,
            subject="Test Notification",
            body="This is a test notification",
            status=NotificationStatus.PENDING.value
        )
        db_session.add(notification)
        db_session.commit()
        return notification
    
    @pytest.fixture
    def sample_template(self, db_session, sample_tenant):
        """Create sample notification template."""
        template = NotificationTemplate(
            tenant_id=sample_tenant.id,
            name="test_template",
            type=NotificationType.EMAIL.value,
            subject_template="Test: {{ title }}",
            body_template="Hello {{ name }}, {{ message }}",
            html_template="<p>Hello {{ name }}, {{ message }}</p>",
            variables=["title", "name", "message"]
        )
        db_session.add(template)
        db_session.commit()
        return template
    
    @pytest.fixture
    def sample_preference(self, db_session, sample_tenant, sample_user):
        """Create sample notification preference."""
        preference = NotificationPreference(
            tenant_id=sample_tenant.id,
            user_id=sample_user.id,
            notification_type=NotificationType.EMAIL.value,
            event_type="test_event",
            is_enabled=True,
            delivery_address="test@test.com"
        )
        db_session.add(preference)
        db_session.commit()
        return preference
    
    @pytest.fixture
    def telegram_channel(self, db_session, sample_tenant):
        """Create sample Telegram channel."""
        channel = Channel(
            tenant_id=sample_tenant.id,
            name="Test Telegram",
            type="telegram",
            config={
                "bot_token": "test_bot_token",
                "webhook_url": "https://test.com/webhook"
            },
            is_active=True
        )
        db_session.add(channel)
        db_session.commit()
        return channel
    
    @pytest.fixture
    def signal_channel(self, db_session, sample_tenant):
        """Create sample Signal channel."""
        channel = Channel(
            tenant_id=sample_tenant.id,
            name="Test Signal",
            type="signal",
            config={
                "phone_number": "+1234567890",
                "signal_cli_path": "/usr/bin/signal-cli"
            },
            is_active=True
        )
        db_session.add(channel)
        db_session.commit()
        return channel


class TestEmailNotifications:
    """Test email notification functionality."""
    
    @pytest.fixture
    def notification_worker(self):
        """Create notification worker instance."""
        return NotificationWorker()
    
    @pytest.fixture
    def sample_notification(self):
        """Create sample notification mock."""
        notification = Mock()
        notification.id = "test-notification-id"
        notification.recipient = "test@test.com"
        notification.type = NotificationType.EMAIL.value
        notification.priority = NotificationPriority.NORMAL.value
        notification.subject = "Test Notification"
        notification.body = "This is a test notification"
        notification.html_body = None
        notification.status = NotificationStatus.PENDING.value
        notification.retry_count = 0
        notification.max_retries = 3
        notification.mark_sent = Mock()
        notification.mark_failed = Mock()
        notification.is_retryable = Mock(return_value=True)
        return notification
    
    @patch('smtplib.SMTP')
    def test_send_email_notification_success(self, mock_smtp, app, notification_worker, sample_notification):
        """Test successful email sending."""
        with app.app_context():
            # Mock SMTP
            mock_server = Mock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            # Mock Flask config
            with patch('flask.current_app.config') as mock_config:
                mock_config.get.side_effect = lambda key, default=None: {
                    'SMTP_SERVER': 'smtp.test.com',
                    'SMTP_PORT': 587,
                    'SMTP_USERNAME': 'test@test.com',
                    'SMTP_PASSWORD': 'password'
                }.get(key, default)
                
                success, error = notification_worker._send_email(sample_notification)
                
                assert success is True
                assert error is None
                mock_server.starttls.assert_called_once()
                mock_server.login.assert_called_once_with('test@test.com', 'password')
                mock_server.send_message.assert_called_once()
    
    @patch('smtplib.SMTP')
    def test_send_email_notification_failure(self, mock_smtp, app, notification_worker, sample_notification):
        """Test email sending failure."""
        with app.app_context():
            # Mock SMTP to raise exception
            mock_smtp.side_effect = Exception("SMTP Error")
            
            with patch('flask.current_app.config') as mock_config:
                mock_config.get.side_effect = lambda key, default=None: {
                    'SMTP_SERVER': 'smtp.test.com',
                    'SMTP_PORT': 587,
                    'SMTP_USERNAME': 'test@test.com',
                    'SMTP_PASSWORD': 'password'
                }.get(key, default)
                
                success, error = notification_worker._send_email(sample_notification)
                
                assert success is False
                assert "SMTP Error" in error
    
    def test_send_email_no_credentials(self, app, notification_worker, sample_notification):
        """Test email sending without SMTP credentials."""
        with app.app_context():
            with patch('flask.current_app.config') as mock_config:
                mock_config.get.return_value = None
                
                success, error = notification_worker._send_email(sample_notification)
                
                assert success is False
                assert "SMTP credentials not configured" in error


class TestTelegramNotifications:
    """Test Telegram notification functionality."""
    
    @pytest.fixture
    def notification_worker(self):
        """Create notification worker instance."""
        return NotificationWorker()
    
    @patch('requests.post')
    def test_send_telegram_notification_success(self, mock_post, notification_worker, sample_notification, 
                                              sample_user, telegram_channel):
        """Test successful Telegram sending."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'ok': True,
            'result': {'message_id': 123}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Set recipient as chat ID
        sample_notification.recipient = "123456789"
        
        success, error = notification_worker._send_telegram(sample_notification)
        
        assert success is True
        assert error is None
        assert sample_notification.external_id == "123"
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "sendMessage" in call_args[0][0]
        assert call_args[1]['json']['chat_id'] == "123456789"
        assert call_args[1]['json']['text'] == "*Test Notification*\n\nThis is a test notification"
    
    @patch('requests.post')
    def test_send_telegram_notification_api_error(self, mock_post, notification_worker, sample_notification,
                                                 sample_user, telegram_channel):
        """Test Telegram API error."""
        # Mock error response
        mock_response = Mock()
        mock_response.json.return_value = {
            'ok': False,
            'description': 'Chat not found'
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        sample_notification.recipient = "123456789"
        
        success, error = notification_worker._send_telegram(sample_notification)
        
        assert success is False
        assert "Chat not found" in error
    
    def test_send_telegram_no_channel(self, notification_worker, sample_notification, sample_user):
        """Test Telegram sending without channel."""
        success, error = notification_worker._send_telegram(sample_notification)
        
        assert success is False
        assert "No active Telegram channel found" in error


class TestSignalNotifications:
    """Test Signal notification functionality."""
    
    @pytest.fixture
    def notification_worker(self):
        """Create notification worker instance."""
        return NotificationWorker()
    
    @patch('subprocess.run')
    def test_send_signal_notification_success(self, mock_run, notification_worker, sample_notification,
                                            sample_user, signal_channel):
        """Test successful Signal sending."""
        # Mock successful subprocess
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        sample_notification.recipient = "+1234567890"
        
        success, error = notification_worker._send_signal(sample_notification)
        
        assert success is True
        assert error is None
        
        # Verify signal-cli call
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "/usr/bin/signal-cli" in call_args
        assert "+1234567890" in call_args
        assert "send" in call_args
    
    @patch('subprocess.run')
    def test_send_signal_notification_failure(self, mock_run, notification_worker, sample_notification,
                                            sample_user, signal_channel):
        """Test Signal sending failure."""
        # Mock failed subprocess
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Signal error"
        mock_run.return_value = mock_result
        
        sample_notification.recipient = "+1234567890"
        
        success, error = notification_worker._send_signal(sample_notification)
        
        assert success is False
        assert "signal-cli error: Signal error" in error
    
    def test_send_signal_no_channel(self, notification_worker, sample_notification, sample_user):
        """Test Signal sending without channel."""
        success, error = notification_worker._send_signal(sample_notification)
        
        assert success is False
        assert "No active Signal channel found" in error


class TestNotificationPreferences:
    """Test notification preference processing."""
    
    @pytest.fixture
    def notification_worker(self):
        """Create notification worker instance."""
        return NotificationWorker()
    
    def test_create_notification_from_preference(self, notification_worker, sample_preference, sample_template):
        """Test creating notification from preference."""
        data = {
            'title': 'Test Alert',
            'name': 'John Doe',
            'message': 'This is a test message'
        }
        
        notification = notification_worker._create_notification_from_preference(sample_preference, data)
        
        assert notification is not None
        assert notification.recipient == sample_preference.delivery_address
        assert notification.type == sample_preference.notification_type
        assert "Test Alert" in notification.subject
        assert "John Doe" in notification.body
        assert "This is a test message" in notification.body
    
    def test_create_notification_no_template(self, notification_worker, sample_preference):
        """Test creating notification without template."""
        data = {
            'message': 'This is a test message'
        }
        
        notification = notification_worker._create_notification_from_preference(sample_preference, data)
        
        assert notification is not None
        assert notification.body == 'This is a test message'
        assert notification.subject is None


class TestNotificationService:
    """Test notification service functionality."""
    
    def test_create_notification(self, sample_tenant, sample_user):
        """Test creating notification via service."""
        service = NotificationService()
        
        notification = service.create_notification(
            tenant_id=sample_tenant.id,
            recipient="test@test.com",
            notification_type=NotificationType.EMAIL,
            subject="Test Subject",
            body="Test Body",
            user_id=sample_user.id,
            priority=NotificationPriority.HIGH
        )
        
        assert notification.tenant_id == sample_tenant.id
        assert notification.recipient == "test@test.com"
        assert notification.type == NotificationType.EMAIL.value
        assert notification.subject == "Test Subject"
        assert notification.body == "Test Body"
        assert notification.priority == NotificationPriority.HIGH.value
    
    @patch('app.workers.notifications.send_notification.delay')
    def test_send_notification_async(self, mock_delay, sample_notification):
        """Test async notification sending."""
        mock_task = Mock()
        mock_task.id = "task-123"
        mock_delay.return_value = mock_task
        
        service = NotificationService()
        task_id = service.send_notification_async(sample_notification.id)
        
        assert task_id == "task-123"
        mock_delay.assert_called_once_with(sample_notification.id)
    
    def test_set_user_preference(self, sample_tenant, sample_user):
        """Test setting user notification preference."""
        service = NotificationService()
        
        preference = service.set_user_preference(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            event_type="test_event",
            notification_type=NotificationType.EMAIL,
            delivery_address="test@test.com",
            is_enabled=True
        )
        
        assert preference.user_id == sample_user.id
        assert preference.event_type == "test_event"
        assert preference.notification_type == NotificationType.EMAIL.value
        assert preference.delivery_address == "test@test.com"
        assert preference.is_enabled is True
    
    def test_get_notification_status(self, sample_notification):
        """Test getting notification status."""
        service = NotificationService()
        
        # Add some events
        event = NotificationEvent(
            notification_id=sample_notification.id,
            event_type="sent",
            data={"test": "data"}
        )
        from app.utils.database import db
        db.session.add(event)
        db.session.commit()
        
        status = service.get_notification_status(sample_notification.id)
        
        assert status is not None
        assert status['id'] == sample_notification.id
        assert status['status'] == NotificationStatus.PENDING.value
        assert status['type'] == NotificationType.EMAIL.value
        assert len(status['events']) == 1
        assert status['events'][0]['type'] == "sent"


class TestNotificationTemplates:
    """Test notification template functionality."""
    
    def test_create_default_templates(self, sample_tenant):
        """Test creating default templates."""
        templates = NotificationTemplateManager.create_default_templates(sample_tenant.id)
        
        assert len(templates) > 0
        
        # Check specific templates exist
        kyb_template = NotificationTemplateManager.get_template(sample_tenant.id, 'kyb_alert_email')
        assert kyb_template is not None
        assert kyb_template.type == NotificationType.EMAIL.value
        assert 'KYB Alert' in kyb_template.subject_template
    
    def test_get_template(self, sample_template):
        """Test getting template by name."""
        template = NotificationTemplateManager.get_template(
            sample_template.tenant_id,
            sample_template.name
        )
        
        assert template is not None
        assert template.id == sample_template.id
    
    def test_list_templates(self, sample_template):
        """Test listing templates."""
        templates = NotificationTemplateManager.list_templates(sample_template.tenant_id)
        
        assert len(templates) >= 1
        assert sample_template.id in [t.id for t in templates]
    
    def test_update_template(self, sample_template):
        """Test updating template."""
        updated = NotificationTemplateManager.update_template(
            sample_template.id,
            subject_template="Updated: {{ title }}",
            body_template="Updated body: {{ message }}"
        )
        
        assert updated.subject_template == "Updated: {{ title }}"
        assert updated.body_template == "Updated body: {{ message }}"
    
    def test_delete_template(self, sample_template):
        """Test deleting template."""
        success = NotificationTemplateManager.delete_template(sample_template.id)
        
        assert success is True
        
        # Verify soft delete
        from app.utils.database import db
        db.session.refresh(sample_template)
        assert sample_template.is_active is False


class TestWorkerTasks:
    """Test worker task functions."""
    
    @patch('app.workers.notifications.NotificationWorker.send_notification')
    def test_send_notification_task(self, mock_send, sample_notification):
        """Test send notification task."""
        mock_send.return_value = {"status": "sent"}
        
        # This would normally be called via Celery
        result = mock_send(sample_notification.id)
        
        assert result["status"] == "sent"
        mock_send.assert_called_once_with(sample_notification.id)
    
    @patch('app.workers.notifications.send_notification.delay')
    def test_send_bulk_notifications_task(self, mock_delay):
        """Test bulk notification sending."""
        mock_task = Mock()
        mock_task.id = "task-123"
        mock_delay.return_value = mock_task
        
        notification_ids = ["id1", "id2", "id3"]
        
        # This would normally be called via Celery
        from app.workers.notifications import notification_worker
        result = notification_worker.send_bulk_notifications(notification_ids)
        
        assert result["queued"] == 3
        assert len(result["results"]) == 3
    
    def test_cleanup_old_notifications(self, db_session, sample_tenant):
        """Test cleanup of old notifications."""
        # Create old notifications
        old_date = datetime.utcnow() - timedelta(days=35)
        
        old_notification = Notification(
            tenant_id=sample_tenant.id,
            recipient="old@test.com",
            type=NotificationType.EMAIL.value,
            body="Old notification",
            status=NotificationStatus.SENT.value,
            created_at=old_date
        )
        db_session.add(old_notification)
        db_session.commit()
        
        from app.workers.notifications import notification_worker
        result = notification_worker.cleanup_old_notifications(30)
        
        assert result["status"] == "completed"
        assert result["deleted_count"] >= 1


class TestIntegration:
    """Integration tests for notification system."""
    
    @patch('smtplib.SMTP')
    @patch('app.workers.notifications.send_notification.delay')
    def test_end_to_end_email_notification(self, mock_delay, mock_smtp, sample_tenant, sample_user):
        """Test complete email notification flow."""
        # Mock SMTP
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        # Mock task
        mock_task = Mock()
        mock_task.id = "task-123"
        mock_delay.return_value = mock_task
        
        # Create templates
        NotificationTemplateManager.create_default_templates(sample_tenant.id)
        
        # Create service
        service = NotificationService()
        
        # Set user preference
        service.set_user_preference(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            event_type="kyb_alert",
            notification_type=NotificationType.EMAIL,
            delivery_address="test@test.com"
        )
        
        # Send notification via preferences
        with patch('flask.current_app.config') as mock_config:
            mock_config.get.side_effect = lambda key, default=None: {
                'SMTP_SERVER': 'smtp.test.com',
                'SMTP_PORT': 587,
                'SMTP_USERNAME': 'test@test.com',
                'SMTP_PASSWORD': 'password'
            }.get(key, default)
            
            task_ids = service.send_to_user_preferences(
                user_id=sample_user.id,
                event_type="kyb_alert",
                data={
                    'company_name': 'Test Company',
                    'counterparty_name': 'Test Counterparty',
                    'alert_type': 'Sanctions Match',
                    'severity': 'High',
                    'details': 'Potential match found',
                    'detected_at': datetime.utcnow().isoformat()
                }
            )
            
            assert len(task_ids) == 1
            mock_delay.assert_called_once()