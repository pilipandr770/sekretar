"""Unit tests for Telegram channel routes."""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch

from app import create_app
from app.models import Channel


@pytest.fixture
def app():
    """Create test Flask app."""
    app = create_app('testing')
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def auth_headers():
    """Create mock auth headers."""
    return {'Authorization': 'Bearer test_token'}


class TestTelegramRoutes:
    """Test cases for Telegram channel routes."""
    
    def test_telegram_webhook_no_data(self, client):
        """Test webhook with no data."""
        response = client.post('/api/v1/channels/telegram/webhook')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'No update data provided' in data['message']
    
    def test_telegram_webhook_invalid_json(self, client):
        """Test webhook with invalid JSON."""
        response = client.post(
            '/api/v1/channels/telegram/webhook',
            data='invalid json',
            content_type='application/json'
        )
        assert response.status_code == 400
    
    @patch('app.services.telegram_service.get_telegram_service')
    def test_telegram_webhook_success(self, mock_get_service, client):
        """Test successful webhook processing."""
        # Mock service
        mock_service = Mock()
        mock_service.process_webhook_update = AsyncMock(return_value={"status": "success"})
        mock_get_service.return_value = mock_service
        
        update_data = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "date": 1234567890,
                "text": "Hello, bot!",
                "from": {
                    "id": 12345,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "chat": {
                    "id": 67890,
                    "type": "private"
                }
            }
        }
        
        response = client.post(
            '/api/v1/channels/telegram/webhook',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'Webhook processed successfully' in data['message']
    
    @patch('app.services.telegram_service.get_telegram_service')
    def test_telegram_webhook_processing_error(self, mock_get_service, client):
        """Test webhook processing error."""
        # Mock service with error
        mock_service = Mock()
        mock_service.process_webhook_update = AsyncMock(return_value={"error": "Processing failed"})
        mock_get_service.return_value = mock_service
        
        update_data = {"update_id": 123}
        
        response = client.post(
            '/api/v1/channels/telegram/webhook',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Processing failed' in data['message']
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    def test_setup_telegram_channel_missing_token(self, mock_query, mock_jwt, client, auth_headers):
        """Test setup without bot token."""
        mock_jwt.return_value = "test_tenant"
        
        response = client.post(
            '/api/v1/channels/telegram/setup',
            data=json.dumps({}),
            content_type='application/json',
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Bot token is required' in data['message']
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    def test_setup_telegram_channel_already_exists(self, mock_query, mock_jwt, client, auth_headers):
        """Test setup when channel already exists."""
        mock_jwt.return_value = "test_tenant"
        
        # Mock existing channel
        mock_channel = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_channel
        
        response = client.post(
            '/api/v1/channels/telegram/setup',
            data=json.dumps({'bot_token': 'test_token'}),
            content_type='application/json',
            headers=auth_headers
        )
        
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'already exists' in data['message']
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    @patch('app.models.Channel.create_telegram_channel')
    @patch('app.channels.telegram_bot.get_telegram_bot_handler')
    def test_setup_telegram_channel_success(self, mock_get_handler, mock_create, mock_query, mock_jwt, client, auth_headers):
        """Test successful channel setup."""
        mock_jwt.return_value = "test_tenant"
        mock_query.filter_by.return_value.first.return_value = None
        
        # Mock channel creation
        mock_channel = Mock()
        mock_channel.to_dict.return_value = {"id": 1, "name": "Test Bot"}
        mock_channel.mark_connected.return_value = mock_channel
        mock_channel.save.return_value = None
        mock_create.return_value = mock_channel
        
        # Mock bot handler
        mock_handler = Mock()
        mock_handler.initialize = AsyncMock(return_value=True)
        mock_get_handler.return_value = mock_handler
        
        response = client.post(
            '/api/v1/channels/telegram/setup',
            data=json.dumps({
                'bot_token': 'test_token',
                'name': 'Test Bot'
            }),
            content_type='application/json',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'created successfully' in data['message']
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    def test_test_telegram_connection_no_channel(self, mock_query, mock_jwt, client, auth_headers):
        """Test connection test with no channel."""
        mock_jwt.return_value = "test_tenant"
        mock_query.filter_by.return_value.first.return_value = None
        
        response = client.post(
            '/api/v1/channels/telegram/test',
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'not found' in data['message']
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    def test_test_telegram_connection_no_token(self, mock_query, mock_jwt, client, auth_headers):
        """Test connection test with no bot token."""
        mock_jwt.return_value = "test_tenant"
        
        # Mock channel without token
        mock_channel = Mock()
        mock_channel.get_config.return_value = None
        mock_query.filter_by.return_value.first.return_value = mock_channel
        
        response = client.post(
            '/api/v1/channels/telegram/test',
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'not configured' in data['message']
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    @patch('app.channels.telegram_bot.get_telegram_bot_handler')
    def test_test_telegram_connection_success(self, mock_get_handler, mock_query, mock_jwt, client, auth_headers):
        """Test successful connection test."""
        mock_jwt.return_value = "test_tenant"
        
        # Mock channel with token
        mock_channel = Mock()
        mock_channel.get_config.return_value = "test_token"
        mock_channel.mark_connected.return_value = mock_channel
        mock_channel.save.return_value = None
        mock_query.filter_by.return_value.first.return_value = mock_channel
        
        # Mock bot handler and bot info
        mock_bot_info = Mock()
        mock_bot_info.id = 123456
        mock_bot_info.username = "test_bot"
        mock_bot_info.first_name = "Test Bot"
        mock_bot_info.can_join_groups = True
        mock_bot_info.can_read_all_group_messages = False
        mock_bot_info.supports_inline_queries = True
        
        mock_handler = Mock()
        mock_handler.bot.get_me = AsyncMock(return_value=mock_bot_info)
        mock_get_handler.return_value = mock_handler
        
        response = client.post(
            '/api/v1/channels/telegram/test',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'test successful' in data['message']
        assert 'bot_info' in data['data']
        assert data['data']['bot_info']['username'] == "test_bot"
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    def test_send_telegram_message_missing_data(self, mock_query, mock_jwt, client, auth_headers):
        """Test sending message with missing data."""
        mock_jwt.return_value = "test_tenant"
        
        response = client.post(
            '/api/v1/channels/telegram/send',
            data=json.dumps({}),
            content_type='application/json',
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'required' in data['message']
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    @patch('app.channels.telegram_bot.get_telegram_bot_handler')
    def test_send_telegram_message_success(self, mock_get_handler, mock_query, mock_jwt, client, auth_headers):
        """Test successful message sending."""
        mock_jwt.return_value = "test_tenant"
        
        # Mock channel
        mock_channel = Mock()
        mock_channel.get_config.return_value = "test_token"
        mock_channel.increment_sent.return_value = mock_channel
        mock_channel.save.return_value = None
        mock_query.filter_by.return_value.first.return_value = mock_channel
        
        # Mock sent message
        mock_sent_message = Mock()
        mock_sent_message.message_id = 123
        mock_sent_message.chat_id = 67890
        mock_sent_message.date = Mock()
        mock_sent_message.date.isoformat.return_value = "2023-01-01T00:00:00"
        
        # Mock bot handler
        mock_handler = Mock()
        mock_handler.bot.send_message = AsyncMock(return_value=mock_sent_message)
        mock_get_handler.return_value = mock_handler
        
        response = client.post(
            '/api/v1/channels/telegram/send',
            data=json.dumps({
                'chat_id': 67890,
                'message': 'Hello, world!'
            }),
            content_type='application/json',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'sent successfully' in data['message']
        assert data['data']['message_id'] == 123
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    def test_get_telegram_status_no_channel(self, mock_query, mock_jwt, client, auth_headers):
        """Test getting status with no channel."""
        mock_jwt.return_value = "test_tenant"
        mock_query.filter_by.return_value.first.return_value = None
        
        response = client.get(
            '/api/v1/channels/telegram/status',
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'not found' in data['message']
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    def test_get_telegram_status_success(self, mock_query, mock_jwt, client, auth_headers):
        """Test successful status retrieval."""
        mock_jwt.return_value = "test_tenant"
        
        # Mock channel
        mock_channel = Mock()
        mock_channel.is_connected = True
        mock_channel.get_config.return_value = "https://example.com/webhook"
        mock_channel.messages_received = 10
        mock_channel.messages_sent = 5
        mock_channel.to_dict.return_value = {
            "id": 1,
            "name": "Test Bot",
            "is_connected": True
        }
        mock_query.filter_by.return_value.first.return_value = mock_channel
        
        response = client.get(
            '/api/v1/channels/telegram/status',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'retrieved successfully' in data['message']
        assert 'channel' in data['data']
        assert 'statistics' in data['data']
        assert data['data']['statistics']['messages_received'] == 10
        assert data['data']['statistics']['messages_sent'] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])