"""Tests for WebSocket real-time features."""
import pytest
import json
from unittest.mock import Mock, patch
from flask import Flask
from flask_socketio import SocketIOTestClient
from app import create_app, socketio
from app.models.tenant import Tenant
from app.models.user import User
from app.main.websocket_handlers import (
    active_connections, broadcast_new_message, broadcast_notification,
    is_user_online, get_active_users_count
)


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app('testing')
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create SocketIO test client."""
    return socketio.test_client(app)


@pytest.fixture
def mock_user():
    """Create mock user for testing."""
    user = Mock(spec=User)
    user.id = 1
    user.tenant_id = 1
    user.email = 'test@example.com'
    user.is_active = True
    return user


@pytest.fixture
def mock_token():
    """Create mock JWT token."""
    return 'mock.jwt.token'


class TestWebSocketConnection:
    """Test WebSocket connection handling."""
    
    @patch('app.main.websocket_handlers.decode_token')
    @patch('app.main.websocket_handlers.User')
    def test_successful_connection(self, mock_user_model, mock_decode_token, client, mock_user, mock_token):
        """Test successful WebSocket connection."""
        # Setup mocks
        mock_decode_token.return_value = {'sub': 1}
        mock_user_model.query.get.return_value = mock_user
        
        # Connect with valid token
        client.connect(auth={'token': mock_token})
        
        # Check connection was successful
        assert client.is_connected()
        
        # Check received connected event
        received = client.get_received()
        assert len(received) > 0
        assert received[0]['name'] == 'connected'
        assert received[0]['args'][0]['status'] == 'connected'
    
    def test_connection_without_token(self, client):
        """Test WebSocket connection without token fails."""
        # Try to connect without token
        client.connect()
        
        # Should not be connected
        assert not client.is_connected()
    
    @patch('app.main.websocket_handlers.decode_token')
    def test_connection_with_invalid_token(self, mock_decode_token, client, mock_token):
        """Test WebSocket connection with invalid token fails."""
        # Setup mock to raise exception
        mock_decode_token.side_effect = Exception('Invalid token')
        
        # Try to connect with invalid token
        client.connect(auth={'token': mock_token})
        
        # Should not be connected
        assert not client.is_connected()
    
    @patch('app.main.websocket_handlers.decode_token')
    @patch('app.main.websocket_handlers.User')
    def test_connection_with_inactive_user(self, mock_user_model, mock_decode_token, client, mock_user, mock_token):
        """Test WebSocket connection with inactive user fails."""
        # Setup mocks
        mock_decode_token.return_value = {'sub': 1}
        mock_user.is_active = False
        mock_user_model.query.get.return_value = mock_user
        
        # Try to connect with inactive user
        client.connect(auth={'token': mock_token})
        
        # Should not be connected
        assert not client.is_connected()


class TestWebSocketEvents:
    """Test WebSocket event handling."""
    
    @patch('app.main.websocket_handlers.decode_token')
    @patch('app.main.websocket_handlers.User')
    def test_join_conversation(self, mock_user_model, mock_decode_token, client, mock_user, mock_token):
        """Test joining a conversation room."""
        # Setup mocks
        mock_decode_token.return_value = {'sub': 1}
        mock_user_model.query.get.return_value = mock_user
        
        # Connect
        client.connect(auth={'token': mock_token})
        
        # Join conversation
        client.emit('join_conversation', {'conversation_id': 'conv123'})
        
        # Check received joined_conversation event
        received = client.get_received()
        join_event = next((r for r in received if r['name'] == 'joined_conversation'), None)
        assert join_event is not None
        assert join_event['args'][0]['conversation_id'] == 'conv123'
        assert join_event['args'][0]['status'] == 'joined'
    
    @patch('app.main.websocket_handlers.decode_token')
    @patch('app.main.websocket_handlers.User')
    def test_join_conversation_without_id(self, mock_user_model, mock_decode_token, client, mock_user, mock_token):
        """Test joining conversation without conversation ID."""
        # Setup mocks
        mock_decode_token.return_value = {'sub': 1}
        mock_user_model.query.get.return_value = mock_user
        
        # Connect
        client.connect(auth={'token': mock_token})
        
        # Try to join conversation without ID
        client.emit('join_conversation', {})
        
        # Check received error event
        received = client.get_received()
        error_event = next((r for r in received if r['name'] == 'error'), None)
        assert error_event is not None
        assert 'Conversation ID required' in error_event['args'][0]['message']
    
    @patch('app.main.websocket_handlers.decode_token')
    @patch('app.main.websocket_handlers.User')
    def test_typing_indicators(self, mock_user_model, mock_decode_token, client, mock_user, mock_token):
        """Test typing indicator events."""
        # Setup mocks
        mock_decode_token.return_value = {'sub': 1}
        mock_user_model.query.get.return_value = mock_user
        
        # Connect
        client.connect(auth={'token': mock_token})
        
        # Start typing
        client.emit('typing_start', {'conversation_id': 'conv123'})
        
        # Stop typing
        client.emit('typing_stop', {'conversation_id': 'conv123'})
        
        # Events should be processed without errors
        assert client.is_connected()
    
    @patch('app.main.websocket_handlers.decode_token')
    @patch('app.main.websocket_handlers.User')
    def test_ping_pong(self, mock_user_model, mock_decode_token, client, mock_user, mock_token):
        """Test ping/pong keepalive."""
        # Setup mocks
        mock_decode_token.return_value = {'sub': 1}
        mock_user_model.query.get.return_value = mock_user
        
        # Connect
        client.connect(auth={'token': mock_token})
        
        # Send ping
        client.emit('ping')
        
        # Check received pong
        received = client.get_received()
        pong_event = next((r for r in received if r['name'] == 'pong'), None)
        assert pong_event is not None


class TestBroadcastFunctions:
    """Test broadcast utility functions."""
    
    @patch('app.main.websocket_handlers.socketio')
    def test_broadcast_new_message(self, mock_socketio):
        """Test broadcasting new message."""
        tenant_id = 1
        conversation_id = 'conv123'
        message_data = {'id': 'msg123', 'content': 'Hello'}
        
        broadcast_new_message(tenant_id, conversation_id, message_data)
        
        # Check socketio.emit was called correctly
        mock_socketio.emit.assert_called_once_with(
            'new_message',
            {
                'conversation_id': conversation_id,
                'message': message_data
            },
            room=f'conversation_{conversation_id}_{tenant_id}'
        )
    
    @patch('app.main.websocket_handlers.socketio')
    def test_broadcast_notification(self, mock_socketio):
        """Test broadcasting notification to user."""
        user_id = 1
        notification_data = {'title': 'Test', 'message': 'Test notification'}
        
        broadcast_notification(user_id, notification_data)
        
        # Check socketio.emit was called correctly
        mock_socketio.emit.assert_called_once_with(
            'notification',
            notification_data,
            room=f'user_{user_id}'
        )


class TestConnectionTracking:
    """Test connection tracking utilities."""
    
    def test_is_user_online_when_offline(self):
        """Test is_user_online returns False when user is offline."""
        # Clear active connections
        active_connections.clear()
        
        result = is_user_online(1)
        assert result is False
    
    def test_is_user_online_when_online(self):
        """Test is_user_online returns True when user is online."""
        # Add user to active connections
        active_connections['session123'] = {
            'user_id': 1,
            'tenant_id': 1,
            'user_email': 'test@example.com'
        }
        
        result = is_user_online(1)
        assert result is True
        
        # Cleanup
        active_connections.clear()
    
    def test_get_active_users_count(self):
        """Test getting active users count for tenant."""
        # Clear active connections
        active_connections.clear()
        
        # Add users from different tenants
        active_connections['session1'] = {
            'user_id': 1,
            'tenant_id': 1,
            'user_email': 'user1@example.com'
        }
        active_connections['session2'] = {
            'user_id': 2,
            'tenant_id': 1,
            'user_email': 'user2@example.com'
        }
        active_connections['session3'] = {
            'user_id': 3,
            'tenant_id': 2,
            'user_email': 'user3@example.com'
        }
        
        # Check count for tenant 1
        count = get_active_users_count(1)
        assert count == 2
        
        # Check count for tenant 2
        count = get_active_users_count(2)
        assert count == 1
        
        # Check count for non-existent tenant
        count = get_active_users_count(999)
        assert count == 0
        
        # Cleanup
        active_connections.clear()


class TestWebSocketClientJS:
    """Test WebSocket client JavaScript functionality."""
    
    def test_websocket_client_file_exists(self):
        """Test that WebSocket client JavaScript file exists."""
        import os
        from pathlib import Path
        
        base_dir = Path(__file__).parent.parent
        js_file = base_dir / 'app' / 'static' / 'js' / 'websocket-client.js'
        
        assert js_file.exists(), "WebSocket client JavaScript file should exist"
    
    def test_websocket_client_has_required_methods(self):
        """Test that WebSocket client has required methods."""
        import os
        from pathlib import Path
        
        base_dir = Path(__file__).parent.parent
        js_file = base_dir / 'app' / 'static' / 'js' / 'websocket-client.js'
        
        content = js_file.read_text(encoding='utf-8')
        
        # Check for required methods
        required_methods = [
            'connect()',
            'joinConversation(',
            'leaveConversation(',
            'startTyping(',
            'stopTyping(',
            'handleNewMessage(',
            'handleTypingIndicator(',
            'showNotification('
        ]
        
        for method in required_methods:
            assert method in content, f"WebSocket client should have {method} method"
    
    def test_websocket_client_has_event_handlers(self):
        """Test that WebSocket client has event handlers."""
        import os
        from pathlib import Path
        
        base_dir = Path(__file__).parent.parent
        js_file = base_dir / 'app' / 'static' / 'js' / 'websocket-client.js'
        
        content = js_file.read_text(encoding='utf-8')
        
        # Check for required event handlers
        required_events = [
            'new_message',
            'message_updated',
            'conversation_updated',
            'user_typing',
            'notification',
            'system_alert'
        ]
        
        for event in required_events:
            assert f"'{event}'" in content or f'"{event}"' in content, f"WebSocket client should handle {event} event"


class TestRealTimeTemplateIntegration:
    """Test real-time features integration in templates."""
    
    def test_inbox_template_has_realtime_features(self):
        """Test that inbox template includes real-time features."""
        from pathlib import Path
        
        base_dir = Path(__file__).parent.parent
        template_file = base_dir / 'app' / 'templates' / 'main' / 'inbox.html'
        
        content = template_file.read_text(encoding='utf-8')
        
        # Check for real-time feature functions
        realtime_functions = [
            'setupRealTimeFeatures',
            'handleRealTimeNewMessage',
            'handleTypingIndicator',
            'showTypingIndicator',
            'addMessageToView'
        ]
        
        for function in realtime_functions:
            assert function in content, f"Inbox template should have {function} function"
    
    def test_dashboard_template_has_realtime_features(self):
        """Test that dashboard template includes real-time features."""
        from pathlib import Path
        
        base_dir = Path(__file__).parent.parent
        template_file = base_dir / 'app' / 'templates' / 'main' / 'dashboard.html'
        
        content = template_file.read_text(encoding='utf-8')
        
        # Check for real-time feature functions
        realtime_functions = [
            'setupRealTimeFeatures',
            'showNotificationBadge',
            'showDashboardNotification',
            'showSystemAlert'
        ]
        
        for function in realtime_functions:
            assert function in content, f"Dashboard template should have {function} function"
    
    def test_base_template_includes_socketio(self):
        """Test that base template includes Socket.IO."""
        from pathlib import Path
        
        base_dir = Path(__file__).parent.parent
        template_file = base_dir / 'app' / 'templates' / 'base.html'
        
        content = template_file.read_text(encoding='utf-8')
        
        # Check for Socket.IO inclusion
        assert 'socket.io' in content, "Base template should include Socket.IO"
        assert 'websocket-client.js' in content, "Base template should include WebSocket client"
    
    def test_css_has_realtime_styles(self):
        """Test that CSS includes real-time feature styles."""
        from pathlib import Path
        
        base_dir = Path(__file__).parent.parent
        css_file = base_dir / 'app' / 'static' / 'css' / 'app.css'
        
        content = css_file.read_text(encoding='utf-8')
        
        # Check for real-time styles
        realtime_styles = [
            'typing-indicator',
            'typing-animation',
            'typing-dot',
            'ws-status',
            'notification-badge',
            'online-indicator'
        ]
        
        for style in realtime_styles:
            assert style in content, f"CSS should include {style} style"


class TestNotificationFeatures:
    """Test notification features."""
    
    def test_notification_permission_handling(self):
        """Test that notification permission is handled in JavaScript."""
        from pathlib import Path
        
        base_dir = Path(__file__).parent.parent
        js_file = base_dir / 'app' / 'static' / 'js' / 'websocket-client.js'
        
        content = js_file.read_text(encoding='utf-8')
        
        # Check for notification permission handling
        assert 'Notification.permission' in content
        assert 'requestPermission' in content
        assert 'new Notification' in content
    
    def test_toast_notification_functionality(self):
        """Test that toast notifications are implemented."""
        from pathlib import Path
        
        base_dir = Path(__file__).parent.parent
        template_file = base_dir / 'app' / 'templates' / 'main' / 'inbox.html'
        
        content = template_file.read_text(encoding='utf-8')
        
        # Check for toast notification functions
        assert 'showToastNotification' in content
        assert 'toast-container' in content
        assert 'bootstrap.Toast' in content


class TestTypingIndicators:
    """Test typing indicator features."""
    
    def test_typing_indicator_css_animation(self):
        """Test that typing indicator has CSS animation."""
        from pathlib import Path
        
        base_dir = Path(__file__).parent.parent
        css_file = base_dir / 'app' / 'static' / 'css' / 'app.css'
        
        content = css_file.read_text(encoding='utf-8')
        
        # Check for typing animation
        assert '@keyframes typingPulse' in content
        assert 'animation: typingPulse' in content
        assert 'typing-dot' in content
    
    def test_typing_indicator_javascript(self):
        """Test that typing indicators are handled in JavaScript."""
        from pathlib import Path
        
        base_dir = Path(__file__).parent.parent
        template_file = base_dir / 'app' / 'templates' / 'main' / 'inbox.html'
        
        content = template_file.read_text(encoding='utf-8')
        
        # Check for typing indicator handling
        assert 'startTyping' in content
        assert 'stopTyping' in content
        assert 'showTypingIndicator' in content
        assert 'typing-indicator' in content