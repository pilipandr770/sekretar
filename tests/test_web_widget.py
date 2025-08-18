"""Tests for web widget functionality."""
import pytest
import json
from unittest.mock import patch, MagicMock
from flask import url_for
from app.models import Channel, Thread, InboxMessage, User
from app import db


class TestWebWidgetAPI:
    """Test web widget API endpoints."""
    
    def test_widget_init_creates_channel_and_thread(self, client, auth_headers, tenant):
        """Test widget initialization creates channel and thread."""
        data = {
            'customer_id': 'customer_123',
            'customer_name': 'John Doe',
            'customer_email': 'john@example.com'
        }
        
        response = client.post(
            '/api/v1/channels/widget/init',
            json=data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        result = response.get_json()
        
        assert result['success'] is True
        assert 'thread' in result['data']
        assert 'channel' in result['data']
        assert 'messages' in result['data']
        assert 'session_info' in result['data']
        
        # Verify channel was created
        channel = Channel.query.filter_by(
            tenant_id=tenant.id,
            type='web_widget'
        ).first()
        assert channel is not None
        assert channel.is_active is True
        assert channel.is_connected is True
        
        # Verify thread was created
        thread = Thread.query.filter_by(
            tenant_id=tenant.id,
            channel_id=channel.id,
            customer_id='customer_123'
        ).first()
        assert thread is not None
        assert thread.status == 'open'
        assert thread.ai_enabled is True
        assert thread.customer_name == 'John Doe'
        assert thread.customer_email == 'john@example.com'
    
    def test_widget_init_reuses_existing_thread(self, client, auth_headers, tenant):
        """Test widget initialization reuses existing open thread."""
        # Create existing channel and thread
        channel = Channel.create(
            tenant_id=tenant.id,
            name='Web Widget',
            type='web_widget',
            is_active=True,
            is_connected=True
        )
        channel.save()
        
        existing_thread = Thread.create(
            tenant_id=tenant.id,
            channel_id=channel.id,
            customer_id='customer_123',
            customer_name='John Doe',
            status='open'
        )
        existing_thread.save()
        
        data = {
            'customer_id': 'customer_123',
            'customer_name': 'John Doe Updated'
        }
        
        response = client.post(
            '/api/v1/channels/widget/init',
            json=data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        result = response.get_json()
        
        # Should return existing thread
        assert result['data']['thread']['id'] == existing_thread.id
        
        # Should not create new thread
        thread_count = Thread.query.filter_by(
            tenant_id=tenant.id,
            customer_id='customer_123'
        ).count()
        assert thread_count == 1
    
    def test_widget_init_requires_customer_id(self, client, auth_headers):
        """Test widget initialization requires customer_id."""
        data = {
            'customer_name': 'John Doe'
        }
        
        response = client.post(
            '/api/v1/channels/widget/init',
            json=data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        result = response.get_json()
        assert 'customer_id' in result['error']['message']
    
    def test_send_widget_message(self, client, auth_headers, tenant):
        """Test sending message through widget."""
        # Create channel and thread
        channel = Channel.create(
            tenant_id=tenant.id,
            name='Web Widget',
            type='web_widget',
            is_active=True
        )
        channel.save()
        
        thread = Thread.create(
            tenant_id=tenant.id,
            channel_id=channel.id,
            customer_id='customer_123',
            customer_name='John Doe',
            status='open'
        )
        thread.save()
        
        data = {
            'content': 'Hello, I need help with my order',
            'content_type': 'text'
        }
        
        with patch('app.channels.websocket_handlers.broadcast_message_update'):
            response = client.post(
                f'/api/v1/channels/widget/thread/{thread.id}/send',
                json=data,
                headers=auth_headers
            )
        
        assert response.status_code == 201
        result = response.get_json()
        
        assert result['success'] is True
        assert 'id' in result['data']
        
        # Verify message was created
        message = InboxMessage.query.filter_by(
            thread_id=thread.id,
            content='Hello, I need help with my order'
        ).first()
        assert message is not None
        assert message.direction == 'inbound'
        assert message.sender_id == 'customer_123'
        assert message.get_metadata('source') == 'web_widget'
    
    def test_send_widget_message_empty_content(self, client, auth_headers, tenant):
        """Test sending empty message fails."""
        # Create channel and thread
        channel = Channel.create(
            tenant_id=tenant.id,
            name='Web Widget',
            type='web_widget',
            is_active=True
        )
        channel.save()
        
        thread = Thread.create(
            tenant_id=tenant.id,
            channel_id=channel.id,
            customer_id='customer_123',
            status='open'
        )
        thread.save()
        
        data = {
            'content': '   ',  # Empty/whitespace content
        }
        
        response = client.post(
            f'/api/v1/channels/widget/thread/{thread.id}/send',
            json=data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        result = response.get_json()
        assert 'empty' in result['error']['message'].lower()
    
    def test_send_widget_message_wrong_thread_type(self, client, auth_headers, tenant):
        """Test sending message to non-widget thread fails."""
        # Create non-widget channel and thread
        channel = Channel.create(
            tenant_id=tenant.id,
            name='Telegram',
            type='telegram',
            is_active=True
        )
        channel.save()
        
        thread = Thread.create(
            tenant_id=tenant.id,
            channel_id=channel.id,
            customer_id='customer_123',
            status='open'
        )
        thread.save()
        
        data = {
            'content': 'Hello'
        }
        
        response = client.post(
            f'/api/v1/channels/widget/thread/{thread.id}/send',
            json=data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        result = response.get_json()
        assert 'not a web widget thread' in result['error']['message']
    
    def test_get_widget_messages(self, client, auth_headers, tenant):
        """Test getting messages for widget thread."""
        # Create channel and thread
        channel = Channel.create(
            tenant_id=tenant.id,
            name='Web Widget',
            type='web_widget',
            is_active=True
        )
        channel.save()
        
        thread = Thread.create(
            tenant_id=tenant.id,
            channel_id=channel.id,
            customer_id='customer_123',
            status='open'
        )
        thread.save()
        
        # Create test messages
        message1 = InboxMessage.create_inbound(
            tenant_id=tenant.id,
            channel_id=channel.id,
            thread_id=thread.id,
            sender_id='customer_123',
            content='First message'
        )
        message1.save()
        
        message2 = InboxMessage.create_outbound(
            tenant_id=tenant.id,
            channel_id=channel.id,
            thread_id=thread.id,
            content='AI response',
            sender_id='ai_assistant'
        )
        message2.save()
        
        response = client.get(
            f'/api/v1/channels/widget/thread/{thread.id}/messages',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        result = response.get_json()
        
        assert result['success'] is True
        assert len(result['data']['messages']) == 2
        assert 'pagination' in result['data']
        assert 'thread' in result['data']
        
        # Messages should be in chronological order
        messages = result['data']['messages']
        assert messages[0]['content'] == 'First message'
        assert messages[1]['content'] == 'AI response'
        assert messages[1]['is_ai_response'] is True
    
    def test_widget_typing_indicator(self, client, auth_headers, tenant):
        """Test widget typing indicator."""
        # Create channel and thread
        channel = Channel.create(
            tenant_id=tenant.id,
            name='Web Widget',
            type='web_widget',
            is_active=True
        )
        channel.save()
        
        thread = Thread.create(
            tenant_id=tenant.id,
            channel_id=channel.id,
            customer_id='customer_123',
            status='open'
        )
        thread.save()
        
        data = {
            'typing': True
        }
        
        with patch('app.socketio.emit') as mock_emit:
            response = client.post(
                f'/api/v1/channels/widget/thread/{thread.id}/typing',
                json=data,
                headers=auth_headers
            )
        
        assert response.status_code == 200
        result = response.get_json()
        
        assert result['success'] is True
        assert result['data']['typing'] is True
        assert result['data']['thread_id'] == thread.id
        
        # Verify WebSocket emission was called
        mock_emit.assert_called_once()
        call_args = mock_emit.call_args
        assert call_args[0][0] == 'user_typing'
        assert call_args[1]['room'] == f'thread_{thread.id}'
    
    def test_get_widget_config_default(self, client, auth_headers, tenant):
        """Test getting default widget configuration."""
        response = client.get(
            '/api/v1/channels/widget/config',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        result = response.get_json()
        
        assert result['success'] is True
        config = result['data']
        
        # Check default values
        assert config['title'] == 'AI Secretary'
        assert config['theme'] == 'light'
        assert config['position'] == 'bottom-right'
        assert config['auto_open'] is False
        assert config['show_typing_indicator'] is True
        assert config['max_message_length'] == 2000
    
    def test_update_widget_config(self, client, auth_headers, tenant):
        """Test updating widget configuration."""
        data = {
            'title': 'Custom Support Chat',
            'theme': 'dark',
            'position': 'bottom-left',
            'auto_open': True,
            'enable_sound': False
        }
        
        response = client.put(
            '/api/v1/channels/widget/config',
            json=data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        result = response.get_json()
        
        assert result['success'] is True
        
        # Verify channel was created/updated
        channel = Channel.query.filter_by(
            tenant_id=tenant.id,
            type='web_widget'
        ).first()
        assert channel is not None
        assert channel.config['widget']['title'] == 'Custom Support Chat'
        assert channel.config['widget']['theme'] == 'dark'
        assert channel.config['widget']['position'] == 'bottom-left'
        assert channel.config['widget']['auto_open'] is True
        assert channel.config['widget']['enable_sound'] is False
    
    def test_get_widget_stats(self, client, auth_headers, tenant):
        """Test getting widget statistics."""
        # Create channel with some data
        channel = Channel.create(
            tenant_id=tenant.id,
            name='Web Widget',
            type='web_widget',
            is_active=True,
            is_connected=True
        )
        channel.save()
        
        # Create thread and messages
        thread = Thread.create(
            tenant_id=tenant.id,
            channel_id=channel.id,
            customer_id='customer_123',
            status='open'
        )
        thread.save()
        
        message = InboxMessage.create_inbound(
            tenant_id=tenant.id,
            channel_id=channel.id,
            thread_id=thread.id,
            sender_id='customer_123',
            content='Test message'
        )
        message.save()
        
        response = client.get(
            '/api/v1/channels/widget/stats',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        result = response.get_json()
        
        assert result['success'] is True
        stats = result['data']
        
        assert stats['enabled'] is True
        assert stats['total_threads'] == 1
        assert stats['total_messages'] == 1
        assert stats['active_threads'] == 1
        assert 'channel_info' in stats


class TestWebSocketHandlers:
    """Test WebSocket handlers for web widget."""
    
    def test_websocket_authentication(self, app, tenant):
        """Test WebSocket authentication."""
        from app.channels.websocket_handlers import WebSocketAuth
        
        # Test valid token
        auth_data = {
            'token': 'valid_jwt_token'
        }
        
        with patch('app.channels.websocket_handlers.decode_token') as mock_decode:
            with patch('app.models.User.query') as mock_user_query:
                mock_decode.return_value = {
                    'sub': 1,
                    'tenant_id': tenant.id
                }
                
                mock_user = MagicMock()
                mock_user.id = 1
                mock_user.tenant_id = tenant.id
                mock_user.is_active = True
                mock_user_query.filter_by.return_value.first.return_value = mock_user
                
                user, tenant_id = WebSocketAuth.authenticate_socket(auth_data)
                
                assert user == mock_user
                assert tenant_id == tenant.id
    
    def test_websocket_authentication_invalid_token(self):
        """Test WebSocket authentication with invalid token."""
        from app.channels.websocket_handlers import WebSocketAuth
        
        # Test invalid token
        auth_data = {
            'token': 'invalid_token'
        }
        
        with patch('app.channels.websocket_handlers.decode_token') as mock_decode:
            mock_decode.side_effect = Exception('Invalid token')
            
            user, tenant_id = WebSocketAuth.authenticate_socket(auth_data)
            
            assert user is None
            assert tenant_id is None
    
    def test_websocket_authentication_no_token(self):
        """Test WebSocket authentication without token."""
        from app.channels.websocket_handlers import WebSocketAuth
        
        # Test no token
        auth_data = {}
        
        user, tenant_id = WebSocketAuth.authenticate_socket(auth_data)
        
        assert user is None
        assert tenant_id is None


class TestWebWidgetJavaScript:
    """Test web widget JavaScript functionality."""
    
    def test_widget_demo_page_loads(self, client):
        """Test that widget demo page loads successfully."""
        response = client.get('/widget-demo')
        
        assert response.status_code == 200
        assert b'AI Secretary Widget Demo' in response.data
        assert b'ai-secretary-widget.js' in response.data
    
    def test_widget_javascript_file_exists(self, client):
        """Test that widget JavaScript file is accessible."""
        response = client.get('/static/js/ai-secretary-widget.js')
        
        assert response.status_code == 200
        assert b'AISecretaryWidget' in response.data
        assert b'WebSocket' in response.data
    
    def test_widget_css_styles_included(self, client):
        """Test that widget includes proper CSS styles."""
        response = client.get('/static/js/ai-secretary-widget.js')
        
        assert response.status_code == 200
        # Check for key CSS classes
        assert b'ai-secretary-widget' in response.data
        assert b'widget-button' in response.data
        assert b'widget-chat' in response.data
        assert b'chat-messages' in response.data


class TestWebWidgetIntegration:
    """Integration tests for web widget functionality."""
    
    def test_complete_widget_flow(self, client, auth_headers, tenant):
        """Test complete widget flow from initialization to messaging."""
        # Step 1: Initialize widget
        init_data = {
            'customer_id': 'integration_test_customer',
            'customer_name': 'Integration Test User',
            'customer_email': 'test@example.com'
        }
        
        response = client.post(
            '/api/v1/channels/widget/init',
            json=init_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        init_result = response.get_json()
        thread_id = init_result['data']['thread']['id']
        
        # Step 2: Send message
        message_data = {
            'content': 'Hello, I need help with my account'
        }
        
        with patch('app.channels.websocket_handlers.broadcast_message_update'):
            response = client.post(
                f'/api/v1/channels/widget/thread/{thread_id}/send',
                json=message_data,
                headers=auth_headers
            )
        
        assert response.status_code == 201
        
        # Step 3: Get messages
        response = client.get(
            f'/api/v1/channels/widget/thread/{thread_id}/messages',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        messages_result = response.get_json()
        
        assert len(messages_result['data']['messages']) == 1
        assert messages_result['data']['messages'][0]['content'] == 'Hello, I need help with my account'
        
        # Step 4: Update typing indicator
        typing_data = {
            'typing': True
        }
        
        with patch('app.socketio.emit'):
            response = client.post(
                f'/api/v1/channels/widget/thread/{thread_id}/typing',
                json=typing_data,
                headers=auth_headers
            )
        
        assert response.status_code == 200
        
        # Step 5: Get widget stats
        response = client.get(
            '/api/v1/channels/widget/stats',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        stats_result = response.get_json()
        
        assert stats_result['data']['total_threads'] >= 1
        assert stats_result['data']['total_messages'] >= 1
    
    def test_widget_with_ai_response(self, client, auth_headers, tenant):
        """Test widget with AI response generation."""
        # Initialize widget
        init_data = {
            'customer_id': 'ai_test_customer',
            'customer_name': 'AI Test User'
        }
        
        response = client.post(
            '/api/v1/channels/widget/init',
            json=init_data,
            headers=auth_headers
        )
        
        thread_id = response.get_json()['data']['thread']['id']
        
        # Mock AI response
        with patch('app.services.orchestration_service.OrchestrationService.process_message') as mock_ai:
            mock_ai.return_value = {
                'content': 'Hello! How can I help you today?',
                'agent_type': 'support',
                'confidence': 'high'
            }
            
            with patch('app.channels.websocket_handlers.broadcast_message_update'):
                with patch('app.socketio.emit'):
                    # Send message that should trigger AI response
                    message_data = {
                        'content': 'I need help'
                    }
                    
                    response = client.post(
                        f'/api/v1/channels/widget/thread/{thread_id}/send',
                        json=message_data,
                        headers=auth_headers
                    )
        
        assert response.status_code == 201
        
        # Verify AI processing was called
        mock_ai.assert_called_once()
    
    def test_widget_error_handling(self, client, auth_headers):
        """Test widget error handling for invalid requests."""
        # Test sending message to non-existent thread
        response = client.post(
            '/api/v1/channels/widget/thread/99999/send',
            json={'content': 'Test message'},
            headers=auth_headers
        )
        
        assert response.status_code == 404
        
        # Test getting messages for non-existent thread
        response = client.get(
            '/api/v1/channels/widget/thread/99999/messages',
            headers=auth_headers
        )
        
        assert response.status_code == 404
        
        # Test typing indicator for non-existent thread
        response = client.post(
            '/api/v1/channels/widget/thread/99999/typing',
            json={'typing': True},
            headers=auth_headers
        )
        
        assert response.status_code == 404