"""Unit tests for inbox management API endpoints."""
import pytest
import json
from datetime import datetime, timedelta
from flask import url_for
from app.models import InboxMessage, Thread, Channel, User, Tenant
from app import db


class TestInboxAPI:
    """Test cases for inbox management API endpoints."""
    
    @pytest.fixture(autouse=True)
    def setup_test_data(self, app, client, auth_headers):
        """Set up test data for each test."""
        with app.app_context():
            # Create test tenant
            self.tenant = Tenant.create(
                name="Test Tenant",
                domain="test.example.com"
            )
            
            # Create test user
            self.user = User.create(
                tenant_id=self.tenant.id,
                email="test@example.com",
                password_hash="hashed_password",
                role="manager",
                first_name="Test",
                last_name="User"
            )
            
            # Create test channel
            self.channel = Channel.create(
                tenant_id=self.tenant.id,
                name="Test Channel",
                type="telegram",
                config={"bot_token": "test_token"}
            )
            
            # Create test thread
            self.thread = Thread.create(
                tenant_id=self.tenant.id,
                channel_id=self.channel.id,
                customer_id="test_customer_123",
                customer_name="Test Customer",
                customer_email="customer@example.com",
                subject="Test Conversation"
            )
            
            # Create test messages
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
    
    def test_list_messages_success(self, client, auth_headers):
        """Test successful message listing."""
        response = client.get('/api/v1/inbox/messages', headers=auth_headers)
        
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
    
    def test_list_messages_with_filters(self, client, auth_headers):
        """Test message listing with filters."""
        # Filter by direction
        response = client.get(
            '/api/v1/inbox/messages?direction=inbound',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should only have inbound message
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['direction'] == 'inbound'
    
    def test_list_messages_with_search(self, client, auth_headers):
        """Test message listing with search."""
        response = client.get(
            '/api/v1/inbox/messages?search=order',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should find the message containing "order"
        assert len(data['data']['items']) >= 1
        found_message = any('order' in item['content'].lower() for item in data['data']['items'])
        assert found_message
    
    def test_list_messages_pagination(self, client, auth_headers):
        """Test message listing pagination."""
        response = client.get(
            '/api/v1/inbox/messages?page=1&per_page=1',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert len(data['data']['items']) == 1
        assert data['data']['pagination']['page'] == 1
        assert data['data']['pagination']['per_page'] == 1
        assert data['data']['pagination']['total'] == 2
    
    def test_get_message_success(self, client, auth_headers):
        """Test successful message retrieval."""
        response = client.get(
            f'/api/v1/inbox/messages/{self.inbound_message.id}',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['data']['id'] == self.inbound_message.id
        assert data['data']['content'] == self.inbound_message.content
        assert data['data']['direction'] == 'inbound'
    
    def test_get_message_not_found(self, client, auth_headers):
        """Test message retrieval with non-existent ID."""
        response = client.get('/api/v1/inbox/messages/99999', headers=auth_headers)
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_send_message_success(self, client, auth_headers):
        """Test successful message sending."""
        message_data = {
            'channel_id': self.channel.id,
            'thread_id': self.thread.id,
            'content': 'This is a test response message',
            'content_type': 'text'
        }
        
        response = client.post(
            '/api/v1/inbox/messages',
            headers=auth_headers,
            data=json.dumps(message_data),
            content_type='application/json'
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['data']['content'] == message_data['content']
        assert data['data']['direction'] == 'outbound'
        assert data['data']['status'] == 'sent'
    
    def test_send_message_validation_error(self, client, auth_headers):
        """Test message sending with missing required fields."""
        message_data = {
            'channel_id': self.channel.id,
            # Missing thread_id and content
        }
        
        response = client.post(
            '/api/v1/inbox/messages',
            headers=auth_headers,
            data=json.dumps(message_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_send_message_invalid_thread(self, client, auth_headers):
        """Test message sending with invalid thread ID."""
        message_data = {
            'channel_id': self.channel.id,
            'thread_id': 99999,  # Non-existent thread
            'content': 'This should fail'
        }
        
        response = client.post(
            '/api/v1/inbox/messages',
            headers=auth_headers,
            data=json.dumps(message_data),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_mark_message_read_success(self, client, auth_headers):
        """Test successful message read marking."""
        # Ensure message is initially unread
        assert not self.inbound_message.is_read
        
        response = client.post(
            f'/api/v1/inbox/messages/{self.inbound_message.id}/read',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['data']['is_read'] is True
        assert 'read_at' in data['data']
        
        # Verify in database
        db.session.refresh(self.inbound_message)
        assert self.inbound_message.is_read is True
    
    def test_list_threads_success(self, client, auth_headers):
        """Test successful thread listing."""
        response = client.get('/api/v1/inbox/threads', headers=auth_headers)
        
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
    
    def test_list_threads_with_filters(self, client, auth_headers):
        """Test thread listing with filters."""
        # Create a closed thread
        closed_thread = Thread.create(
            tenant_id=self.tenant.id,
            channel_id=self.channel.id,
            customer_id="closed_customer",
            customer_name="Closed Customer",
            status="closed"
        )
        db.session.commit()
        
        # Filter by status
        response = client.get(
            '/api/v1/inbox/threads?status=open',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should only have open thread
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['status'] == 'open'
    
    def test_get_thread_success(self, client, auth_headers):
        """Test successful thread retrieval."""
        response = client.get(
            f'/api/v1/inbox/threads/{self.thread.id}',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['data']['id'] == self.thread.id
        assert data['data']['customer_name'] == self.thread.customer_name
        assert 'recent_messages' in data['data']
        assert len(data['data']['recent_messages']) == 2  # Both messages
    
    def test_assign_thread_success(self, client, auth_headers):
        """Test successful thread assignment."""
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
        
        response = client.post(
            f'/api/v1/inbox/threads/{self.thread.id}/assign',
            headers=auth_headers,
            data=json.dumps(assignment_data),
            content_type='application/json'
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
    
    def test_assign_thread_invalid_user(self, client, auth_headers):
        """Test thread assignment with invalid user ID."""
        assignment_data = {
            'user_id': 99999  # Non-existent user
        }
        
        response = client.post(
            f'/api/v1/inbox/threads/{self.thread.id}/assign',
            headers=auth_headers,
            data=json.dumps(assignment_data),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_unassign_thread_success(self, client, auth_headers):
        """Test successful thread unassignment."""
        # First assign the thread
        assignee = User.create(
            tenant_id=self.tenant.id,
            email="assignee2@example.com",
            password_hash="hashed_password",
            role="support",
            first_name="Support",
            last_name="Agent2"
        )
        self.thread.assign_to_user(assignee.id)
        db.session.commit()
        
        response = client.post(
            f'/api/v1/inbox/threads/{self.thread.id}/unassign',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['data']['assigned_to_id'] is None
        assert data['data']['ai_enabled'] is True  # Should be re-enabled
        
        # Verify in database
        db.session.refresh(self.thread)
        assert self.thread.assigned_to_id is None
        assert self.thread.ai_enabled is True
    
    def test_update_thread_status_success(self, client, auth_headers):
        """Test successful thread status update."""
        status_data = {
            'status': 'closed'
        }
        
        response = client.put(
            f'/api/v1/inbox/threads/{self.thread.id}/status',
            headers=auth_headers,
            data=json.dumps(status_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['data']['status'] == 'closed'
        
        # Verify in database
        db.session.refresh(self.thread)
        assert self.thread.status == 'closed'
    
    def test_update_thread_status_invalid(self, client, auth_headers):
        """Test thread status update with invalid status."""
        status_data = {
            'status': 'invalid_status'
        }
        
        response = client.put(
            f'/api/v1/inbox/threads/{self.thread.id}/status',
            headers=auth_headers,
            data=json.dumps(status_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_search_messages_success(self, client, auth_headers):
        """Test successful message search."""
        response = client.get(
            '/api/v1/inbox/search?q=order&type=messages',
            headers=auth_headers
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
    
    def test_search_threads_success(self, client, auth_headers):
        """Test successful thread search."""
        response = client.get(
            '/api/v1/inbox/search?q=Test&type=threads',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'threads' in data['data']['items']
        
        # Should find threads with "Test" in customer name
        threads = data['data']['items']['threads']
        assert len(threads) >= 1
    
    def test_search_combined_success(self, client, auth_headers):
        """Test successful combined search."""
        response = client.get(
            '/api/v1/inbox/search?q=Test&type=all',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'messages' in data['data']['items']
        assert 'threads' in data['data']['items']
    
    def test_search_no_query(self, client, auth_headers):
        """Test search without query parameter."""
        response = client.get('/api/v1/inbox/search', headers=auth_headers)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_get_inbox_stats_success(self, client, auth_headers):
        """Test successful inbox statistics retrieval."""
        response = client.get('/api/v1/inbox/stats', headers=auth_headers)
        
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
    
    def test_unauthorized_access(self, client):
        """Test unauthorized access to inbox endpoints."""
        # Test without authentication headers
        response = client.get('/api/v1/inbox/messages')
        assert response.status_code == 401
        
        response = client.get('/api/v1/inbox/threads')
        assert response.status_code == 401
        
        response = client.post('/api/v1/inbox/messages')
        assert response.status_code == 401
    
    def test_tenant_isolation(self, app, client, auth_headers):
        """Test that users can only access their tenant's data."""
        with app.app_context():
            # Create another tenant with data
            other_tenant = Tenant.create(
                name="Other Tenant",
                domain="other.example.com"
            )
            
            other_channel = Channel.create(
                tenant_id=other_tenant.id,
                name="Other Channel",
                type="telegram",
                config={"bot_token": "other_token"}
            )
            
            other_thread = Thread.create(
                tenant_id=other_tenant.id,
                channel_id=other_channel.id,
                customer_id="other_customer",
                customer_name="Other Customer"
            )
            
            other_message = InboxMessage.create_inbound(
                tenant_id=other_tenant.id,
                channel_id=other_channel.id,
                thread_id=other_thread.id,
                sender_id="other_customer",
                content="Other tenant message"
            )
            
            db.session.commit()
            
            # Try to access other tenant's data
            response = client.get(
                f'/api/v1/inbox/messages/{other_message.id}',
                headers=auth_headers
            )
            assert response.status_code == 404  # Should not find it
            
            response = client.get(
                f'/api/v1/inbox/threads/{other_thread.id}',
                headers=auth_headers
            )
            assert response.status_code == 404  # Should not find it
            
            # List should not include other tenant's data
            response = client.get('/api/v1/inbox/messages', headers=auth_headers)
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Should only see own tenant's messages (2 messages)
            assert len(data['data']['items']) == 2
            message_ids = [item['id'] for item in data['data']['items']]
            assert other_message.id not in message_ids