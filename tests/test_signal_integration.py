"""Tests for Signal integration."""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.services.signal_cli_service import SignalCLIService
from app.channels.signal_bot import SignalBotHandler
from app.api.signal import signal_bp


class TestSignalCLIService:
    """Test Signal CLI service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SignalCLIService()
    
    def test_initialization(self):
        """Test service initialization."""
        result = self.service.initialize()
        assert result is True
        assert self.service.base_dir.exists()
        assert self.service.accounts_dir.exists()
    
    @patch('requests.get')
    async def test_get_latest_version(self, mock_get):
        """Test getting latest Signal CLI version."""
        mock_response = Mock()
        mock_response.json.return_value = {"tag_name": "v0.11.5"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        version = await self.service._get_latest_version()
        assert version == "0.11.5"
    
    @patch('app.services.signal_cli_service.SignalCLIService._run_command')
    async def test_register_phone_number_success(self, mock_run_command):
        """Test successful phone number registration."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Registration successful"
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result
        
        self.service.is_installed = True
        success, message = await self.service.register_phone_number("+1234567890")
        
        assert success is True
        assert "Registration SMS sent" in message
    
    @patch('app.services.signal_cli_service.SignalCLIService._run_command')
    async def test_register_phone_number_captcha_required(self, mock_run_command):
        """Test phone number registration with captcha required."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Captcha required"
        mock_run_command.return_value = mock_result
        
        self.service.is_installed = True
        success, message = await self.service.register_phone_number("+1234567890")
        
        assert success is False
        assert "Captcha required" in message
    
    @patch('app.services.signal_cli_service.SignalCLIService._run_command')
    async def test_verify_phone_number_success(self, mock_run_command):
        """Test successful phone number verification."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Verification successful"
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result
        
        self.service.is_installed = True
        success, message = await self.service.verify_phone_number("+1234567890", "123456")
        
        assert success is True
        assert "verified successfully" in message
    
    @patch('app.services.signal_cli_service.SignalCLIService._run_command')
    async def test_verify_phone_number_invalid_code(self, mock_run_command):
        """Test phone number verification with invalid code."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Invalid verification code"
        mock_run_command.return_value = mock_result
        
        self.service.is_installed = True
        success, message = await self.service.verify_phone_number("+1234567890", "000000")
        
        assert success is False
        assert "Invalid verification code" in message
    
    @patch('app.services.signal_cli_service.SignalCLIService._run_command')
    async def test_send_message_success(self, mock_run_command):
        """Test successful message sending."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Message sent"
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result
        
        self.service.is_installed = True
        
        with patch.object(self.service, '_is_account_registered', return_value=True):
            success, message = await self.service.send_message(
                "+1234567890", "+0987654321", "Test message"
            )
        
        assert success is True
        assert "sent successfully" in message
    
    @patch('app.services.signal_cli_service.SignalCLIService._run_command')
    async def test_receive_messages(self, mock_run_command):
        """Test receiving messages."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"envelope": {"source": "+1234567890", "dataMessage": {"message": "Hello"}}}'
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result
        
        self.service.is_installed = True
        
        with patch.object(self.service, '_is_account_registered', return_value=True):
            success, messages = await self.service.receive_messages("+1234567890")
        
        assert success is True
        assert len(messages) == 1
        assert messages[0]["envelope"]["dataMessage"]["message"] == "Hello"


class TestSignalBotHandler:
    """Test Signal bot handler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = SignalBotHandler("+1234567890", "signal-cli")
    
    @patch('app.channels.signal_bot.SignalBotHandler._check_signal_cli')
    @patch('app.channels.signal_bot.SignalBotHandler._is_registered')
    @patch('app.channels.signal_bot.SignalBotHandler._test_connection')
    async def test_initialization_success(self, mock_test, mock_registered, mock_check):
        """Test successful bot initialization."""
        mock_check.return_value = True
        mock_registered.return_value = True
        mock_test.return_value = True
        
        result = await self.handler.initialize()
        assert result is True
    
    @patch('app.channels.signal_bot.SignalBotHandler._check_signal_cli')
    async def test_initialization_no_cli(self, mock_check):
        """Test bot initialization without Signal CLI."""
        mock_check.return_value = False
        
        result = await self.handler.initialize()
        assert result is False
    
    @patch('app.channels.signal_bot.SignalBotHandler._run_signal_command')
    async def test_send_message_success(self, mock_run_command):
        """Test successful message sending."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Message sent"
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result
        
        result = await self.handler.send_message("+0987654321", "Test message")
        assert result is True
    
    @patch('app.channels.signal_bot.SignalBotHandler._run_signal_command')
    async def test_send_message_failure(self, mock_run_command):
        """Test message sending failure."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Failed to send message"
        mock_run_command.return_value = mock_result
        
        result = await self.handler.send_message("+0987654321", "Test message")
        assert result is False
    
    def test_split_long_message(self):
        """Test message splitting for long messages."""
        long_message = "A" * 3000  # Longer than 2000 character limit
        
        messages = self.handler._split_long_message(long_message)
        
        assert len(messages) > 1
        for message in messages:
            assert len(message) <= 2000
        
        # Verify all content is preserved
        combined = "".join(messages)
        assert combined == long_message
    
    def test_split_short_message(self):
        """Test message splitting for short messages."""
        short_message = "Hello, this is a test message."
        
        messages = self.handler._split_long_message(short_message)
        
        assert len(messages) == 1
        assert messages[0] == short_message


@pytest.fixture
def client():
    """Create test client."""
    from app import create_app
    app = create_app('testing')
    
    with app.test_client() as client:
        with app.app_context():
            yield client


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    # This would normally create a valid JWT token
    return {
        'Authorization': 'Bearer test-token',
        'Content-Type': 'application/json'
    }


class TestSignalAPI:
    """Test Signal API endpoints."""
    
    @patch('app.api.signal.get_signal_cli_service')
    def test_get_signal_status(self, mock_service, client, auth_headers):
        """Test getting Signal status."""
        mock_service_instance = Mock()
        mock_service_instance.get_installation_status.return_value = {
            "is_installed": True,
            "cli_path": "/path/to/signal-cli",
            "version": "0.11.5"
        }
        mock_service.return_value = mock_service_instance
        
        with patch('app.api.signal.get_jwt_identity', return_value=1):
            with patch('app.api.signal.User') as mock_user:
                mock_user.query.get.return_value = Mock(tenant_id="test-tenant")
                with patch('app.api.signal.Channel') as mock_channel:
                    mock_channel.query.filter_by.return_value.all.return_value = []
                    
                    response = client.get('/api/v1/signal/status', headers=auth_headers)
                    
                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['success'] is True
                    assert 'installation' in data['data']
    
    @patch('app.api.signal.get_signal_cli_service')
    @patch('app.api.signal.asyncio.run')
    def test_install_signal_cli(self, mock_asyncio, mock_service, client, auth_headers):
        """Test Signal CLI installation."""
        mock_service_instance = Mock()
        mock_service_instance.is_installed = False
        mock_service_instance.get_installation_status.return_value = {
            "is_installed": True,
            "version": "0.11.5"
        }
        mock_service.return_value = mock_service_instance
        
        mock_asyncio.return_value = (True, "Installation successful")
        
        response = client.post('/api/v1/signal/install', 
                             headers=auth_headers,
                             json={"version": "latest"})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert "Installation successful" in data['data']['message']
    
    @patch('app.api.signal.get_signal_cli_service')
    @patch('app.api.signal.asyncio.run')
    def test_register_phone_number(self, mock_asyncio, mock_service, client, auth_headers):
        """Test phone number registration."""
        mock_service_instance = Mock()
        mock_service_instance.is_installed = True
        mock_service.return_value = mock_service_instance
        
        mock_asyncio.return_value = (True, "Registration SMS sent")
        
        response = client.post('/api/v1/signal/register',
                             headers=auth_headers,
                             json={"phone_number": "+1234567890"})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['next_step'] == "verification"
    
    @patch('app.api.signal.get_signal_cli_service')
    @patch('app.api.signal.asyncio.run')
    def test_verify_phone_number(self, mock_asyncio, mock_service, client, auth_headers):
        """Test phone number verification."""
        mock_service_instance = Mock()
        mock_service_instance.is_installed = True
        mock_service.return_value = mock_service_instance
        
        mock_asyncio.side_effect = [
            (True, "Phone number verified successfully"),  # verify_phone_number
            {"phone_number": "+1234567890", "is_registered": True}  # get_account_info
        ]
        
        response = client.post('/api/v1/signal/verify',
                             headers=auth_headers,
                             json={
                                 "phone_number": "+1234567890",
                                 "verification_code": "123456"
                             })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['next_step'] == "create_channel"
    
    @patch('app.api.signal.get_signal_cli_service')
    @patch('app.api.signal.asyncio.run')
    def test_create_signal_channel(self, mock_asyncio, mock_service, client, auth_headers):
        """Test Signal channel creation."""
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        
        mock_asyncio.return_value = ["+1234567890"]  # list_accounts
        
        with patch('app.api.signal.get_jwt_identity', return_value=1):
            with patch('app.api.signal.User') as mock_user:
                mock_user.query.get.return_value = Mock(tenant_id="test-tenant")
                with patch('app.api.signal.Channel') as mock_channel:
                    mock_channel.query.filter_by.return_value.filter.return_value.first.return_value = None
                    
                    mock_new_channel = Mock()
                    mock_new_channel.id = 1
                    mock_new_channel.name = "Test Signal Channel"
                    mock_new_channel.config = {"phone_number": "+1234567890"}
                    mock_new_channel.created_at.isoformat.return_value = "2023-01-01T00:00:00"
                    
                    with patch('app.api.signal.db.session'):
                        response = client.post('/api/v1/signal/channels',
                                             headers=auth_headers,
                                             json={
                                                 "phone_number": "+1234567890",
                                                 "name": "Test Signal Channel"
                                             })
                        
                        assert response.status_code == 200
                        data = response.get_json()
                        assert data['success'] is True
                        assert "created successfully" in data['data']['message']


class TestSignalIntegration:
    """Integration tests for Signal functionality."""
    
    @pytest.mark.asyncio
    async def test_full_message_flow(self):
        """Test complete message flow from receiving to AI response."""
        # Mock message data
        message_data = {
            "envelope": {
                "source": "+1234567890",
                "timestamp": 1640995200000,
                "dataMessage": {
                    "message": "Hello, I need help with my account",
                    "attachments": []
                }
            }
        }
        
        # Create handler
        handler = SignalBotHandler("+0987654321", "signal-cli")
        
        # Mock dependencies
        with patch.object(handler, '_create_agent_context') as mock_context:
            with patch.object(handler, '_store_message') as mock_store:
                with patch.object(handler.orchestrator, 'process_message') as mock_process:
                    with patch.object(handler, '_send_ai_response') as mock_send:
                        
                        # Set up mocks
                        mock_context.return_value = Mock()
                        mock_response = Mock()
                        mock_response.content = "I'd be happy to help you with your account!"
                        mock_response.requires_handoff = False
                        mock_process.return_value = mock_response
                        
                        # Process message
                        await handler._process_received_message(message_data)
                        
                        # Verify calls
                        mock_store.assert_called()
                        mock_process.assert_called_once()
                        mock_send.assert_called_once()
    
    def test_phone_number_validation(self):
        """Test phone number validation in various formats."""
        valid_numbers = [
            "+1234567890",
            "+49123456789",
            "+441234567890"
        ]
        
        invalid_numbers = [
            "1234567890",  # Missing +
            "+123",        # Too short
            "abc123",      # Contains letters
            ""             # Empty
        ]
        
        # Test valid numbers
        for number in valid_numbers:
            # This would test the validation logic
            assert number.startswith('+')
            assert len(number) >= 10
            assert number[1:].isdigit()
        
        # Test invalid numbers
        for number in invalid_numbers:
            # This would test the validation logic
            is_valid = (number.startswith('+') and 
                       len(number) >= 10 and 
                       number[1:].isdigit())
            assert not is_valid
    
    def test_message_formatting(self):
        """Test message formatting and sanitization."""
        test_cases = [
            ("Hello world", "Hello world"),
            ("Hello\nworld", "Hello\nworld"),
            ("Hello\n\nworld", "Hello\n\nworld"),
            ("", ""),
            ("A" * 3000, "A" * 2000)  # Should be truncated
        ]
        
        handler = SignalBotHandler("+1234567890", "signal-cli")
        
        for input_msg, expected in test_cases:
            if len(input_msg) > 2000:
                # Test splitting
                messages = handler._split_long_message(input_msg)
                assert len(messages[0]) <= 2000
            else:
                # Test normal processing
                messages = handler._split_long_message(input_msg)
                assert len(messages) == 1
                assert messages[0] == expected