"""Simplified unit tests for inbox management API endpoints."""
import pytest
import json
import tempfile
import os
from datetime import datetime
from app import create_app, db
from app.models import InboxMessage, Thread, Channel, User, Tenant
from flask_jwt_extended import create_access_token


class TestInboxAPISimple:
    """Simplified test cases for inbox management API endpoints."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test environment for each test."""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Create test app
        self.app = create_app('testing')
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        self.app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['HEALTH_CHECK_DATABASE_ENABLED'] = False
        self.app.config['HEALTH_CHECK_REDIS_ENABLED'] = False
        self.app.config['TENANT_MIDDLEWARE_ENABLED'] = False
        
        self.client = self.app.test_client()
        
        with self.app.app_context():
            # Create all tables
            db.create_all()
            
            # Create test data
            self.tenant = Tenant.create(
                name="Test Tenant",
                domain="test.example.com",
                slug="test-tenant"
            )
            
            self.user = User.create(
                email="test@example.com",
                password="test_password",
                tenant_id=self.tenant.id,
                role="manager",
                first_name="Test",
                last_name="User"
            )
            
            self.channel = Channel.create(
                tenant_id=self.tenant.id,
                name="Test Channel",
                type="telegram",
                config={"bot_token": "test_token"}
            )
            
            self.thread = Thread.create(
                tenant_id=self.tenant.id,
                channel_id=self.channel.id,
                customer_id="test_customer_123",
                customer_name="Test Customer",
                customer_email="customer@example.com",
                subject="Test Conversation"
            )
            
            self.inbound_message = InboxMessage.create_inbound(
                tenant_id=self.tenant.id,
                channel_id=self.channel.id,
                thread_id=self.thread.id,
                sender_id="test_customer_123",
                content="Hello, I need help with my order",
                sender_name="Test Customer",
                sender_email="customer@example.com"
            )
            
            self.outbound_message = InboxMessage.create_outbound(
                tenant_id=self.tenant.id,
                channel_id=self.channel.id,
                thread_id=self.thread.id,
                content="Hi! I'd be happy to help you with your order.",
                sender_id=f"user_{self.user.id}"
            )
            
            db.session.commit()
            
            # Create auth headers
            # The JWT system expects the identity to be the user object for claims generation
            # but stores the user ID as the subject
            access_token = create_access_token(identity=self.user)
            
            self.auth_headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
    
    def teardown_method(self):
        """Clean up after each test."""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_list_messages_success(self):
        """Test successful message listing."""
        with self.app.app_context():
            response = self.client.get('/api/v1/inbox/messages', headers=self.auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert 'data' in data
            assert 'items' in data['data']
            assert 'pagination' in data['data']
            
            # Should have both messages
            assert len(data['data']['items']) == 2
            
            # Check message structure
            message = data['data']['items'][0]
            assert 'id' in message
            assert 'content' in message
            assert 'direction' in message
            assert 'channel_name' in message
            assert 'thread_id' in message
    
    def test_list_messages_with_filters(self):
        """Test message listing with filters."""
        with self.app.app_context():
            # Filter by direction
            response = self.client.get(
                '/api/v1/inbox/messages?direction=inbound',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Should only have inbound message
            assert len(data['data']['items']) == 1
            assert data['data']['items'][0]['direction'] == 'inbound'
    
    def test_get_message_success(self):
        """Test successful message retrieval."""
        with self.app.app_context():
            response = self.client.get(
                f'/api/v1/inbox/messages/{self.inbound_message.id}',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert data['data']['id'] == self.inbound_message.id
            assert data['data']['content'] == self.inbound_message.content
            assert data['data']['direction'] == 'inbound'
    
    def test_get_message_not_found(self):
        """Test message retrieval with non-existent ID."""
        with self.app.app_context():
            response = self.client.get('/api/v1/inbox/messages/99999', headers=self.auth_headers)
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['success'] is False
    
    def test_send_message_success(self):
        """Test successful message sending."""
        with self.app.app_context():
            message_data = {
                'channel_id': self.channel.id,
                'thread_id': self.thread.id,
                'content': 'This is a test response message',
                'content_type': 'text'
            }
            
            response = self.client.post(
                '/api/v1/inbox/messages',
                headers=self.auth_headers,
                data=json.dumps(message_data)
            )
            
            assert response.status_code == 201
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert data['data']['content'] == message_data['content']
            assert data['data']['direction'] == 'outbound'
            assert data['data']['status'] == 'sent'
    
    def test_send_message_validation_error(self):
        """Test message sending with missing required fields."""
        with self.app.app_context():
            message_data = {
                'channel_id': self.channel.id,
                # Missing thread_id and content
            }
            
            response = self.client.post(
                '/api/v1/inbox/messages',
                headers=self.auth_headers,
                data=json.dumps(message_data)
            )
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['success'] is False
    
    def test_mark_message_read_success(self):
        """Test successful message read marking."""
        with self.app.app_context():
            # Ensure message is initially unread
            assert not self.inbound_message.is_read
            
            response = self.client.post(
                f'/api/v1/inbox/messages/{self.inbound_message.id}/read',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert data['data']['is_read'] is True
            assert 'read_at' in data['data']
            
            # Verify in database
            db.session.refresh(self.inbound_message)
            assert self.inbound_message.is_read is True
    
    def test_list_threads_success(self):
        """Test successful thread listing."""
        with self.app.app_context():
            response = self.client.get('/api/v1/inbox/threads', headers=self.auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert 'data' in data
            assert 'items' in data['data']
            assert len(data['data']['items']) == 1
            
            # Check thread structure
            thread = data['data']['items'][0]
            assert 'id' in thread
            assert 'customer_id' in thread
            assert 'customer_name' in thread
            assert 'status' in thread
            assert 'channel_name' in thread
    
    def test_get_thread_success(self):
        """Test successful thread retrieval."""
        with self.app.app_context():
            response = self.client.get(
                f'/api/v1/inbox/threads/{self.thread.id}',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert data['data']['id'] == self.thread.id
            assert data['data']['customer_name'] == self.thread.customer_name
            assert 'recent_messages' in data['data']
            assert len(data['data']['recent_messages']) == 2  # Both messages
    
    def test_assign_thread_success(self):
        """Test successful thread assignment."""
        with self.app.app_context():
            # Create another user to assign to
            assignee = User.create(
                tenant_id=self.tenant.id,
                email="assignee@example.com",
                password_hash="hashed_password",
                role="support",
                first_name="Support",
                last_name="Agent"
            )
            db.session.commit()
            
            assignment_data = {
                'user_id': assignee.id
            }
            
            response = self.client.post(
                f'/api/v1/inbox/threads/{self.thread.id}/assign',
                headers=self.auth_headers,
                data=json.dumps(assignment_data)
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert data['data']['assigned_to_id'] == assignee.id
            assert data['data']['assigned_to_name'] == assignee.full_name
            assert data['data']['ai_enabled'] is False  # Should be disabled when assigned
            
            # Verify in database
            db.session.refresh(self.thread)
            assert self.thread.assigned_to_id == assignee.id
            assert self.thread.ai_enabled is False
    
    def test_update_thread_status_success(self):
        """Test successful thread status update."""
        with self.app.app_context():
            status_data = {
                'status': 'closed'
            }
            
            response = self.client.put(
                f'/api/v1/inbox/threads/{self.thread.id}/status',
                headers=self.auth_headers,
                data=json.dumps(status_data)
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert data['data']['status'] == 'closed'
            
            # Verify in database
            db.session.refresh(self.thread)
            assert self.thread.status == 'closed'
    
    def test_search_messages_success(self):
        """Test successful message search."""
        with self.app.app_context():
            response = self.client.get(
                '/api/v1/inbox/search?q=order&type=messages',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert 'data' in data
            assert 'items' in data['data']
            assert 'messages' in data['data']['items']
            
            # Should find messages containing "order"
            messages = data['data']['items']['messages']
            assert len(messages) >= 1
    
    def test_get_inbox_stats_success(self):
        """Test successful inbox statistics retrieval."""
        with self.app.app_context():
            response = self.client.get('/api/v1/inbox/stats', headers=self.auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert 'data' in data
            
            stats = data['data']
            assert 'messages' in stats
            assert 'threads' in stats
            assert 'channels' in stats
            assert 'summary' in stats
            
            # Check message stats
            assert stats['messages']['total'] == 2
            assert stats['messages']['inbound'] == 1
            assert stats['messages']['outbound'] == 1
            
            # Check thread stats
            assert stats['threads']['total'] == 1
            assert stats['threads']['open'] == 1
            
            # Check channel stats
            assert len(stats['channels']) == 1
            assert stats['channels'][0]['channel_name'] == self.channel.name
    
    def test_unauthorized_access(self):
        """Test unauthorized access to inbox endpoints."""
        with self.app.app_context():
            # Test without authentication headers
            response = self.client.get('/api/v1/inbox/messages')
            assert response.status_code == 401
            
            response = self.client.get('/api/v1/inbox/threads')
            assert response.status_code == 401
            
            response = self.client.post('/api/v1/inbox/messages')
            assert response.status_code == 401