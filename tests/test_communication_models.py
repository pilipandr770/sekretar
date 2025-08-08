"""Test communication and inbox models."""
import pytest
from datetime import datetime
from app.models.tenant import Tenant
from app.models.user import User
from app.models.channel import Channel
from app.models.thread import Thread
from app.models.inbox_message import InboxMessage, Attachment
from app import db


class TestChannel:
    """Test Channel model."""
    
    def test_create_channel(self, app):
        """Test channel creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(
                tenant_id=tenant.id,
                name="Test Channel",
                type="telegram",
                config={"bot_token": "test_token"}
            )
            channel.save()
            
            assert channel.id is not None
            assert channel.name == "Test Channel"
            assert channel.type == "telegram"
            assert channel.get_config("bot_token") == "test_token"
            assert channel.is_active is True
            assert channel.is_connected is False
    
    def test_channel_config_management(self, app):
        """Test channel configuration management."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            # Test setting config
            channel.set_config("bot_token", "new_token")
            channel.set_config("webhook_url", "https://example.com/webhook")
            channel.save()
            
            assert channel.get_config("bot_token") == "new_token"
            assert channel.get_config("webhook_url") == "https://example.com/webhook"
            assert channel.get_config("nonexistent") is None
            assert channel.get_config("nonexistent", "default") == "default"
            
            # Test updating config
            channel.update_config({
                "bot_token": "updated_token",
                "new_setting": "value"
            })
            channel.save()
            
            assert channel.get_config("bot_token") == "updated_token"
            assert channel.get_config("new_setting") == "value"
    
    def test_channel_connection_status(self, app):
        """Test channel connection status management."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            # Test marking as connected
            channel.mark_connected()
            channel.save()
            
            assert channel.is_connected is True
            assert channel.connection_status == "connected"
            assert channel.last_connected_at is not None
            assert channel.last_error is None
            
            # Test marking as disconnected with error
            channel.mark_disconnected("Connection failed")
            channel.save()
            
            assert channel.is_connected is False
            assert channel.connection_status == "error"
            assert channel.last_error == "Connection failed"
    
    def test_channel_statistics(self, app):
        """Test channel message statistics."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            # Test incrementing counters
            channel.increment_received()
            channel.increment_received()
            channel.increment_sent()
            channel.save()
            
            assert channel.messages_received == 2
            assert channel.messages_sent == 1
            
            # Test computed fields in to_dict
            data = channel.to_dict()
            assert data['total_messages'] == 3
    
    def test_create_specific_channels(self, app):
        """Test creating specific channel types."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Test Telegram channel
            telegram = Channel.create_telegram_channel(
                tenant_id=tenant.id,
                name="Telegram Bot",
                bot_token="test_token",
                webhook_url="https://example.com/webhook"
            )
            
            assert telegram.type == "telegram"
            assert telegram.get_config("bot_token") == "test_token"
            assert telegram.get_config("webhook_url") == "https://example.com/webhook"
            
            # Test Signal channel
            signal = Channel.create_signal_channel(
                tenant_id=tenant.id,
                name="Signal Bot",
                phone_number="+1234567890"
            )
            
            assert signal.type == "signal"
            assert signal.get_config("phone_number") == "+1234567890"
            
            # Test Widget channel
            widget = Channel.create_widget_channel(
                tenant_id=tenant.id,
                name="Web Widget",
                theme="dark",
                position="bottom-left"
            )
            
            assert widget.type == "widget"
            assert widget.get_config("theme") == "dark"
            assert widget.get_config("position") == "bottom-left"


class TestThread:
    """Test Thread model."""
    
    def test_create_thread(self, app):
        """Test thread creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            thread = Thread(
                tenant_id=tenant.id,
                channel_id=channel.id,
                customer_id="customer123",
                customer_name="John Doe",
                subject="Test conversation"
            )
            thread.save()
            
            assert thread.id is not None
            assert thread.customer_id == "customer123"
            assert thread.customer_name == "John Doe"
            assert thread.status == "open"
            assert thread.ai_enabled is True
            assert thread.message_count == 0
    
    def test_thread_metadata_and_tags(self, app):
        """Test thread metadata and tags management."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            thread = Thread(
                tenant_id=tenant.id,
                channel_id=channel.id,
                customer_id="customer123"
            )
            thread.save()
            
            # Test metadata
            thread.set_metadata("source", "website")
            thread.set_metadata("priority", "high")
            thread.save()
            
            assert thread.get_metadata("source") == "website"
            assert thread.get_metadata("priority") == "high"
            assert thread.get_metadata("nonexistent") is None
            
            # Test tags
            thread.add_tag("urgent")
            thread.add_tag("billing")
            thread.add_tag("urgent")  # Should not duplicate
            thread.save()
            
            assert thread.has_tag("urgent")
            assert thread.has_tag("billing")
            assert len(thread.tags) == 2
            
            thread.remove_tag("urgent")
            thread.save()
            
            assert not thread.has_tag("urgent")
            assert thread.has_tag("billing")
    
    def test_thread_assignment(self, app):
        """Test thread assignment to users."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="agent@test.com",
                password="password",
                tenant_id=tenant.id,
                role="support"
            )
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            thread = Thread(
                tenant_id=tenant.id,
                channel_id=channel.id,
                customer_id="customer123"
            )
            thread.save()
            
            # Test assignment
            thread.assign_to_user(user.id)
            thread.save()
            
            assert thread.assigned_to_id == user.id
            assert thread.ai_enabled is False  # Should disable AI when assigned
            
            # Test unassignment
            thread.unassign()
            thread.save()
            
            assert thread.assigned_to_id is None
            assert thread.ai_enabled is True  # Should re-enable AI
    
    def test_thread_status_management(self, app):
        """Test thread status management."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            thread = Thread(
                tenant_id=tenant.id,
                channel_id=channel.id,
                customer_id="customer123"
            )
            thread.save()
            
            # Test closing
            thread.close()
            thread.save()
            assert thread.status == "closed"
            
            # Test reopening
            thread.reopen()
            thread.save()
            assert thread.status == "open"
            
            # Test archiving
            thread.archive()
            thread.save()
            assert thread.status == "archived"
            
            # Test marking as spam
            thread.mark_as_spam()
            thread.save()
            assert thread.status == "spam"
            assert thread.ai_enabled is False
    
    def test_find_or_create_thread(self, app):
        """Test finding or creating threads."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            # Test creating new thread
            thread1, created1 = Thread.find_or_create(
                tenant_id=tenant.id,
                channel_id=channel.id,
                customer_id="customer123"
            )
            
            assert created1 is True
            assert thread1.customer_id == "customer123"
            
            # Test finding existing thread
            thread2, created2 = Thread.find_or_create(
                tenant_id=tenant.id,
                channel_id=channel.id,
                customer_id="customer123"
            )
            
            assert created2 is False
            assert thread2.id == thread1.id


class TestInboxMessage:
    """Test InboxMessage model."""
    
    def test_create_message(self, app):
        """Test message creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            thread = Thread(
                tenant_id=tenant.id,
                channel_id=channel.id,
                customer_id="customer123"
            )
            thread.save()
            
            message = InboxMessage(
                tenant_id=tenant.id,
                channel_id=channel.id,
                thread_id=thread.id,
                sender_id="customer123",
                content="Hello, I need help!",
                direction="inbound"
            )
            message.save()
            
            assert message.id is not None
            assert message.content == "Hello, I need help!"
            assert message.direction == "inbound"
            assert message.is_from_customer() is True
            assert message.is_from_agent() is False
            assert message.ai_processed is False
    
    def test_create_inbound_outbound_messages(self, app):
        """Test creating inbound and outbound messages."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            thread = Thread(
                tenant_id=tenant.id,
                channel_id=channel.id,
                customer_id="customer123"
            )
            thread.save()
            
            # Test inbound message
            inbound = InboxMessage.create_inbound(
                tenant_id=tenant.id,
                channel_id=channel.id,
                thread_id=thread.id,
                sender_id="customer123",
                content="Hello!"
            )
            
            assert inbound.direction == "inbound"
            assert inbound.sent_at is not None
            
            # Check that thread and channel stats were updated
            db.session.refresh(thread)
            db.session.refresh(channel)
            assert thread.message_count == 1
            assert channel.messages_received == 1
            
            # Test outbound message
            outbound = InboxMessage.create_outbound(
                tenant_id=tenant.id,
                channel_id=channel.id,
                thread_id=thread.id,
                content="Hi! How can I help you?"
            )
            
            assert outbound.direction == "outbound"
            assert outbound.status == "processing"
            
            # Check that thread stats were updated
            db.session.refresh(thread)
            assert thread.message_count == 2
    
    def test_message_status_management(self, app):
        """Test message status management."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            thread = Thread(
                tenant_id=tenant.id,
                channel_id=channel.id,
                customer_id="customer123"
            )
            thread.save()
            
            message = InboxMessage(
                tenant_id=tenant.id,
                channel_id=channel.id,
                thread_id=thread.id,
                sender_id="customer123",
                content="Test message",
                direction="outbound"
            )
            message.save()
            
            # Test marking as read
            message.mark_as_read()
            message.save()
            
            assert message.is_read is True
            assert message.read_at is not None
            
            # Test marking as sent
            message.mark_as_sent()
            message.save()
            
            assert message.status == "sent"
            assert message.delivered_at is not None
            
            # Test marking as failed
            message.mark_as_failed("Network error")
            message.save()
            
            assert message.status == "failed"
            assert message.get_metadata("error") == "Network error"
    
    def test_ai_processing(self, app):
        """Test AI processing functionality."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            thread = Thread(
                tenant_id=tenant.id,
                channel_id=channel.id,
                customer_id="customer123"
            )
            thread.save()
            
            message = InboxMessage(
                tenant_id=tenant.id,
                channel_id=channel.id,
                thread_id=thread.id,
                sender_id="customer123",
                content="I'm having trouble with my order",
                direction="inbound"
            )
            message.save()
            
            # Test setting AI response
            message.set_ai_response(
                response="I understand you're having trouble with your order. Let me help you with that.",
                confidence="high",
                intent="support_request",
                sentiment="neutral"
            )
            message.save()
            
            assert message.ai_processed is True
            assert message.ai_response is not None
            assert message.ai_confidence == "high"
            assert message.ai_intent == "support_request"
            assert message.ai_sentiment == "neutral"


class TestAttachment:
    """Test Attachment model."""
    
    def test_create_attachment(self, app):
        """Test attachment creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            channel = Channel(tenant_id=tenant.id, name="Test", type="telegram")
            channel.save()
            
            thread = Thread(
                tenant_id=tenant.id,
                channel_id=channel.id,
                customer_id="customer123"
            )
            thread.save()
            
            message = InboxMessage(
                tenant_id=tenant.id,
                channel_id=channel.id,
                thread_id=thread.id,
                sender_id="customer123",
                content="Here's the document",
                direction="inbound"
            )
            message.save()
            
            attachment = Attachment(
                tenant_id=tenant.id,
                message_id=message.id,
                filename="document.pdf",
                original_filename="My Document.pdf",
                file_size=1024000,
                mime_type="application/pdf"
            )
            attachment.save()
            
            assert attachment.id is not None
            assert attachment.filename == "document.pdf"
            assert attachment.get_file_extension() == "pdf"
            assert attachment.is_document() is True
            assert attachment.is_image() is False
    
    def test_attachment_type_detection(self, app):
        """Test attachment type detection."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Test image
            image_attachment = Attachment(
                tenant_id=tenant.id,
                filename="photo.jpg",
                mime_type="image/jpeg"
            )
            
            assert image_attachment.is_image() is True
            assert image_attachment.is_document() is False
            assert image_attachment.is_audio() is False
            assert image_attachment.is_video() is False
            
            # Test document
            doc_attachment = Attachment(
                tenant_id=tenant.id,
                filename="report.pdf",
                mime_type="application/pdf"
            )
            
            assert doc_attachment.is_document() is True
            assert doc_attachment.is_image() is False
            
            # Test audio
            audio_attachment = Attachment(
                tenant_id=tenant.id,
                filename="voice.mp3",
                mime_type="audio/mpeg"
            )
            
            assert audio_attachment.is_audio() is True
            assert audio_attachment.is_image() is False
            
            # Test video
            video_attachment = Attachment(
                tenant_id=tenant.id,
                filename="clip.mp4",
                mime_type="video/mp4"
            )
            
            assert video_attachment.is_video() is True
            assert video_attachment.is_image() is False