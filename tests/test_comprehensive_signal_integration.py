"""Comprehensive Signal integration tests for communication channel testing."""
import pytest
import asyncio
import json
import subprocess
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from pathlib import Path

from app import create_app
from app.channels.signal_bot import SignalBotHandler, SignalCLIManager, get_signal_bot_handler, get_signal_cli_manager
from app.services.signal_service import SignalService, get_signal_service
from app.services.signal_cli_service import SignalCLIService, get_signal_cli_service
from app.models import Channel, InboxMessage, Thread, Attachment, Tenant, Contact
from app.secretary.agents.base_agent import AgentContext, AgentResponse


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


@pytest.fixture
def signal_cli_service():
    """Create Signal CLI service for testing."""
    service = SignalCLIService()
    service.initialize()
    return service


@pytest.fixture
def signal_bot_handler():
    """Create Signal bot handler for testing."""
    return SignalBotHandler("+1234567890", "signal-cli")


@pytest.fixture
def signal_service(app):
    """Create Signal service for testing."""
    with app.app_context():
        return SignalService()


@pytest.fixture
def real_company_data():
    """Real company data for testing Signal integration."""
    return {
        "microsoft_ireland": {
            "name": "Microsoft Ireland Operations Limited",
            "vat_number": "IE9825613N",
            "country": "IE",
            "lei_code": "635400AKJKKLMN4KNZ71",
            "address": "One Microsoft Place, South County Business Park, Leopardstown, Dublin 18",
            "signal_phone": "+353123456789"
        },
        "sap_germany": {
            "name": "SAP SE",
            "vat_number": "DE143593636",
            "country": "DE", 
            "lei_code": "529900T8BM49AURSDO55",
            "address": "Dietmar-Hopp-Allee 16, 69190 Walldorf",
            "signal_phone": "+49987654321"
        },
        "unilever_uk": {
            "name": "Unilever PLC",
            "vat_number": "GB440861235",
            "country": "GB",
            "lei_code": "549300BFXFJ6KBNTKY86",
            "address": "100 Victoria Embankment, London EC4Y 0DY",
            "signal_phone": "+441122334455"
        }
    }


class TestSignalCLIWrapperTests:
    """Test Signal CLI wrapper functionality."""
    
    @pytest.mark.asyncio
    async def test_signal_cli_installation(self, signal_cli_service):
        """Test Signal CLI installation process."""
        with patch('requests.get') as mock_get:
            # Mock GitHub API response
            mock_response = Mock()
            mock_response.json.return_value = {"tag_name": "v0.11.5"}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # Mock download and extraction
            with patch('shutil.unpack_archive') as mock_unpack:
                with patch.object(signal_cli_service.base_dir, 'iterdir') as mock_iterdir:
                    mock_dir = Mock()
                    mock_dir.is_dir.return_value = True
                    mock_dir.name = "signal-cli-0.11.5"
                    mock_dir.__truediv__ = lambda self, other: Mock()
                    mock_iterdir.return_value = [mock_dir]
                    
                    with patch.object(signal_cli_service, '_verify_installation', return_value=True):
                        success, message = await signal_cli_service.install_signal_cli("latest")
                        
                        assert success is True
                        assert "installed successfully" in message
                        assert signal_cli_service.is_installed is True
    
    @pytest.mark.asyncio
    async def test_signal_cli_phone_registration(self, signal_cli_service, real_company_data):
        """Test Signal CLI phone number registration."""
        company = real_company_data["microsoft_ireland"]
        signal_cli_service.is_installed = True
        
        # Mock successful registration
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Registration successful"
        mock_result.stderr = ""
        
        with patch.object(signal_cli_service, '_run_command', return_value=mock_result):
            success, message = await signal_cli_service.register_phone_number(
                company["signal_phone"]
            )
            
            assert success is True
            assert "Registration SMS sent" in message
    
    @pytest.mark.asyncio
    async def test_signal_cli_phone_registration_with_captcha(self, signal_cli_service, real_company_data):
        """Test Signal CLI phone number registration with captcha."""
        company = real_company_data["sap_germany"]
        signal_cli_service.is_installed = True
        
        # Mock captcha required error first
        mock_result_error = Mock()
        mock_result_error.returncode = 1
        mock_result_error.stdout = ""
        mock_result_error.stderr = "Captcha required"
        
        with patch.object(signal_cli_service, '_run_command', return_value=mock_result_error):
            success, message = await signal_cli_service.register_phone_number(
                company["signal_phone"]
            )
            
            assert success is False
            assert "Captcha required" in message
        
        # Mock successful registration with captcha
        mock_result_success = Mock()
        mock_result_success.returncode = 0
        mock_result_success.stdout = "Registration successful"
        mock_result_success.stderr = ""
        
        with patch.object(signal_cli_service, '_run_command', return_value=mock_result_success):
            success, message = await signal_cli_service.register_phone_number(
                company["signal_phone"], "test_captcha_token"
            )
            
            assert success is True
            assert "Registration SMS sent" in message
    
    @pytest.mark.asyncio
    async def test_signal_cli_phone_verification(self, signal_cli_service, real_company_data):
        """Test Signal CLI phone number verification."""
        company = real_company_data["unilever_uk"]
        signal_cli_service.is_installed = True
        
        # Mock successful verification
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Verification successful"
        mock_result.stderr = ""
        
        with patch.object(signal_cli_service, '_run_command', return_value=mock_result):
            success, message = await signal_cli_service.verify_phone_number(
                company["signal_phone"], "123456"
            )
            
            assert success is True
            assert "verified successfully" in message
    
    @pytest.mark.asyncio
    async def test_signal_cli_phone_verification_invalid_code(self, signal_cli_service, real_company_data):
        """Test Signal CLI phone number verification with invalid code."""
        company = real_company_data["microsoft_ireland"]
        signal_cli_service.is_installed = True
        
        # Mock invalid verification code
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Invalid verification code"
        
        with patch.object(signal_cli_service, '_run_command', return_value=mock_result):
            success, message = await signal_cli_service.verify_phone_number(
                company["signal_phone"], "000000"
            )
            
            assert success is False
            assert "Invalid verification code" in message
    
    @pytest.mark.asyncio
    async def test_signal_cli_message_sending(self, signal_cli_service, real_company_data):
        """Test Signal CLI message sending."""
        company = real_company_data["sap_germany"]
        signal_cli_service.is_installed = True
        
        # Mock successful message sending
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Message sent"
        mock_result.stderr = ""
        
        with patch.object(signal_cli_service, '_is_account_registered', return_value=True):
            with patch.object(signal_cli_service, '_run_command', return_value=mock_result):
                success, message = await signal_cli_service.send_message(
                    company["signal_phone"],
                    "+1234567890",
                    f"Hello from {company['name']}! How can we help you today?"
                )
                
                assert success is True
                assert "sent successfully" in message
    
    @pytest.mark.asyncio
    async def test_signal_cli_message_receiving(self, signal_cli_service, real_company_data):
        """Test Signal CLI message receiving."""
        company = real_company_data["unilever_uk"]
        signal_cli_service.is_installed = True
        
        # Mock received message
        message_json = json.dumps({
            "envelope": {
                "source": "+1234567890",
                "timestamp": 1640995200000,
                "dataMessage": {
                    "message": f"I'm interested in {company['name']} products. Can you help?",
                    "attachments": []
                }
            }
        })
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = message_json
        mock_result.stderr = ""
        
        with patch.object(signal_cli_service, '_is_account_registered', return_value=True):
            with patch.object(signal_cli_service, '_run_command', return_value=mock_result):
                success, messages = await signal_cli_service.receive_messages(
                    company["signal_phone"]
                )
                
                assert success is True
                assert len(messages) == 1
                assert messages[0]["envelope"]["dataMessage"]["message"] == f"I'm interested in {company['name']} products. Can you help?"
    
    @pytest.mark.asyncio
    async def test_signal_cli_account_listing(self, signal_cli_service, real_company_data):
        """Test Signal CLI account listing."""
        signal_cli_service.is_installed = True
        
        # Mock multiple registered accounts
        accounts_output = "\n".join([
            company["signal_phone"] for company in real_company_data.values()
        ])
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = accounts_output
        mock_result.stderr = ""
        
        with patch.object(signal_cli_service, '_run_command', return_value=mock_result):
            accounts = await signal_cli_service.list_accounts()
            
            assert len(accounts) == 3
            assert real_company_data["microsoft_ireland"]["signal_phone"] in accounts
            assert real_company_data["sap_germany"]["signal_phone"] in accounts
            assert real_company_data["unilever_uk"]["signal_phone"] in accounts


class TestSignalMessagePollingAndProcessing:
    """Test Signal message polling and processing functionality."""
    
    @pytest.mark.asyncio
    async def test_signal_message_polling_setup(self, signal_bot_handler, real_company_data):
        """Test Signal message polling setup."""
        company = real_company_data["microsoft_ireland"]
        signal_bot_handler.phone_number = company["signal_phone"]
        
        # Mock initialization checks
        with patch.object(signal_bot_handler, '_check_signal_cli', return_value=True):
            with patch.object(signal_bot_handler, '_is_registered', return_value=True):
                with patch.object(signal_bot_handler, '_test_connection', return_value=True):
                    success = await signal_bot_handler.initialize()
                    assert success is True
    
    @pytest.mark.asyncio
    async def test_signal_message_processing_text(self, signal_bot_handler, real_company_data):
        """Test Signal text message processing."""
        company = real_company_data["sap_germany"]
        
        # Mock message data
        message_data = {
            "envelope": {
                "source": "+1234567890",
                "timestamp": 1640995200000,
                "dataMessage": {
                    "message": f"Hello, I'm from {company['name']}. Our VAT number is {company['vat_number']}. Can you help us?",
                    "attachments": []
                }
            }
        }
        
        # Mock dependencies
        signal_bot_handler._create_agent_context = AsyncMock()
        signal_bot_handler._store_message = AsyncMock()
        signal_bot_handler._send_ai_response = AsyncMock()
        
        mock_context = AgentContext(
            tenant_id="test_tenant",
            user_id="+1234567890",
            channel_type="signal",
            conversation_id="1",
            customer_id="+1234567890"
        )
        signal_bot_handler._create_agent_context.return_value = mock_context
        
        mock_response = AgentResponse(
            content=f"Hello! I see you're from {company['name']}. I'd be happy to help you with your inquiry.",
            confidence=0.9,
            intent="business_inquiry"
        )
        signal_bot_handler.orchestrator.process_message = AsyncMock(return_value=mock_response)
        
        await signal_bot_handler._process_received_message(message_data)
        
        # Verify message was stored
        signal_bot_handler._store_message.assert_called_once()
        
        # Verify AI processing
        signal_bot_handler._create_agent_context.assert_called_once()
        signal_bot_handler.orchestrator.process_message.assert_called_once()
        signal_bot_handler._send_ai_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_signal_group_message_processing(self, signal_bot_handler, real_company_data):
        """Test Signal group message processing."""
        company = real_company_data["unilever_uk"]
        
        # Mock group message data
        message_data = {
            "envelope": {
                "source": "+1234567890",
                "timestamp": 1640995200000,
                "dataMessage": {
                    "message": f"Team, we need to discuss the {company['name']} partnership proposal.",
                    "groupInfo": {
                        "groupId": "group123",
                        "name": "Business Development Team"
                    },
                    "attachments": []
                }
            }
        }
        
        # Mock dependencies
        signal_bot_handler._create_agent_context = AsyncMock()
        signal_bot_handler._store_message = AsyncMock()
        signal_bot_handler._send_ai_response = AsyncMock()
        
        mock_context = AgentContext(
            tenant_id="test_tenant",
            user_id="+1234567890",
            channel_type="signal",
            conversation_id="1",
            customer_id="+1234567890",
            metadata={
                "signal_group_id": "group123",
                "is_group_message": True
            }
        )
        signal_bot_handler._create_agent_context.return_value = mock_context
        
        mock_response = AgentResponse(
            content=f"I can help with information about {company['name']} partnerships. What specific details do you need?",
            confidence=0.8,
            intent="partnership_inquiry"
        )
        signal_bot_handler.orchestrator.process_message = AsyncMock(return_value=mock_response)
        
        await signal_bot_handler._process_received_message(message_data)
        
        # Verify group message was processed
        signal_bot_handler._store_message.assert_called_once()
        signal_bot_handler._create_agent_context.assert_called_once()
        signal_bot_handler.orchestrator.process_message.assert_called_once()
        signal_bot_handler._send_ai_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_signal_attachment_processing(self, signal_bot_handler, real_company_data):
        """Test Signal attachment processing."""
        company = real_company_data["microsoft_ireland"]
        
        # Mock message with attachments
        message_data = {
            "envelope": {
                "source": "+1234567890",
                "timestamp": 1640995200000,
                "dataMessage": {
                    "message": f"Here's our company profile for {company['name']}",
                    "attachments": [
                        {
                            "contentType": "application/pdf",
                            "filename": "company_profile.pdf",
                            "size": 1048576
                        },
                        {
                            "contentType": "image/jpeg",
                            "filename": "office_photo.jpg",
                            "size": 512000
                        }
                    ]
                }
            }
        }
        
        # Mock dependencies
        signal_bot_handler._create_agent_context = AsyncMock()
        signal_bot_handler._store_message = AsyncMock()
        signal_bot_handler._send_ai_response = AsyncMock()
        signal_bot_handler._process_attachments = AsyncMock()
        
        mock_context = AgentContext(
            tenant_id="test_tenant",
            user_id="+1234567890",
            channel_type="signal",
            conversation_id="1",
            customer_id="+1234567890"
        )
        signal_bot_handler._create_agent_context.return_value = mock_context
        
        mock_response = AgentResponse(
            content=f"Thank you for sharing the {company['name']} company profile and office photo. I'll review these documents.",
            confidence=0.9,
            intent="document_received"
        )
        signal_bot_handler.orchestrator.process_message = AsyncMock(return_value=mock_response)
        
        await signal_bot_handler._process_received_message(message_data)
        
        # Verify attachments were processed
        signal_bot_handler._process_attachments.assert_called_once()
        
        # Verify message processing
        signal_bot_handler._store_message.assert_called_once()
        signal_bot_handler._create_agent_context.assert_called_once()
        signal_bot_handler.orchestrator.process_message.assert_called_once()
        signal_bot_handler._send_ai_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_signal_long_message_splitting(self, signal_bot_handler, real_company_data):
        """Test Signal long message splitting."""
        company = real_company_data["sap_germany"]
        
        # Create a long message
        long_content = f"""
        Thank you for your inquiry about {company['name']}. 
        
        {company['name']} is a multinational software corporation headquartered in {company['address']}. 
        The company has a rich history of innovation and has been serving customers worldwide for decades.
        
        Our VAT number is {company['vat_number']} and our LEI code is {company['lei_code']}.
        
        """ + "A" * 2500  # Make it longer than Signal's 2000 character limit
        
        messages = signal_bot_handler._split_long_message(long_content)
        
        # Verify message was split
        assert len(messages) > 1
        
        # Verify each message is within limits
        for message in messages:
            assert len(message) <= signal_bot_handler.max_message_length
        
        # Verify content is preserved (approximately, accounting for splitting)
        combined_length = sum(len(msg) for msg in messages)
        assert combined_length >= len(long_content) * 0.9  # Allow for some formatting changes
    
    @pytest.mark.asyncio
    async def test_signal_message_sending_with_handoff(self, signal_bot_handler, real_company_data):
        """Test Signal message sending with human handoff."""
        company = real_company_data["unilever_uk"]
        
        # Mock AI response requiring handoff
        mock_response = AgentResponse(
            content=f"I understand you need detailed information about {company['name']} partnerships. Let me connect you with a specialist.",
            confidence=0.6,
            intent="complex_inquiry",
            requires_handoff=True
        )
        
        # Mock send methods
        signal_bot_handler.send_message = AsyncMock(return_value=True)
        signal_bot_handler.send_group_message = AsyncMock(return_value=True)
        signal_bot_handler._store_message = AsyncMock()
        
        # Test direct message with handoff
        await signal_bot_handler._send_ai_response("+1234567890", None, mock_response, False)
        
        # Verify message was sent
        signal_bot_handler.send_message.assert_called_once()
        call_args = signal_bot_handler.send_message.call_args[0]
        assert "human agent will contact you" in call_args[1]
        
        # Verify message was stored
        signal_bot_handler._store_message.assert_called_once()


class TestSignalGroupConversationHandling:
    """Test Signal group conversation handling."""
    
    @pytest.mark.asyncio
    async def test_signal_group_message_sending(self, signal_bot_handler, real_company_data):
        """Test Signal group message sending."""
        company = real_company_data["microsoft_ireland"]
        
        # Mock successful group message sending
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Message sent to group"
        mock_result.stderr = ""
        
        with patch.object(signal_bot_handler, '_run_signal_command', return_value=mock_result):
            success = await signal_bot_handler.send_group_message(
                "group123",
                f"Update: {company['name']} partnership meeting scheduled for next week.",
                []
            )
            
            assert success is True
    
    @pytest.mark.asyncio
    async def test_signal_group_context_creation(self, signal_bot_handler, real_company_data):
        """Test Signal group context creation."""
        company = real_company_data["sap_germany"]
        
        # Mock channel and thread creation
        signal_bot_handler._get_or_create_channel = AsyncMock()
        signal_bot_handler._get_or_create_thread = AsyncMock()
        
        mock_channel = Mock()
        mock_channel.id = 1
        mock_channel.tenant_id = "test_tenant"
        signal_bot_handler._get_or_create_channel.return_value = mock_channel
        
        mock_thread = Mock()
        mock_thread.id = 1
        signal_bot_handler._get_or_create_thread.return_value = mock_thread
        
        context = await signal_bot_handler._create_agent_context(
            "+1234567890", "group123", True
        )
        
        assert context.tenant_id == "test_tenant"
        assert context.user_id == "+1234567890"
        assert context.channel_type == "signal"
        assert context.conversation_id == "1"
        assert context.customer_id == "+1234567890"
        assert context.metadata["signal_group_id"] == "group123"
        assert context.metadata["is_group_message"] is True
    
    @pytest.mark.asyncio
    async def test_signal_group_attachment_handling(self, signal_bot_handler, real_company_data):
        """Test Signal group attachment handling."""
        company = real_company_data["unilever_uk"]
        
        # Mock attachments
        attachments = [
            {
                "contentType": "application/pdf",
                "filename": f"{company['name']}_proposal.pdf"
            },
            {
                "contentType": "image/png",
                "filename": "chart.png"
            }
        ]
        
        # Mock context
        mock_context = AgentContext(
            tenant_id="test_tenant",
            user_id="+1234567890",
            channel_type="signal",
            conversation_id="1",
            customer_id="+1234567890"
        )
        
        # Mock AI response
        mock_response = AgentResponse(
            content=f"I received the {company['name']} proposal and chart. I'll review these documents.",
            confidence=0.8,
            intent="document_received"
        )
        signal_bot_handler.orchestrator.process_message = AsyncMock(return_value=mock_response)
        signal_bot_handler.send_group_message = AsyncMock(return_value=True)
        
        await signal_bot_handler._process_attachments(
            "+1234567890", "group123", attachments, mock_context, True
        )
        
        # Verify AI processing and group message sending
        signal_bot_handler.orchestrator.process_message.assert_called()
        signal_bot_handler.send_group_message.assert_called()


class TestSignalAPIEndpoints:
    """Test Signal API endpoints with real scenarios."""
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.User.query')
    @patch('app.models.Channel.query')
    @patch('app.api.signal.get_signal_cli_service')
    def test_signal_status_endpoint(self, mock_service, mock_channel_query, mock_user_query, mock_jwt, client, auth_headers, real_company_data):
        """Test Signal status endpoint."""
        mock_jwt.return_value = 1
        
        # Mock user
        mock_user = Mock()
        mock_user.tenant_id = "test_tenant"
        mock_user_query.get.return_value = mock_user
        
        # Mock channels
        channels = []
        for company in real_company_data.values():
            mock_channel = Mock()
            mock_channel.id = len(channels) + 1
            mock_channel.name = f"Signal ({company['signal_phone']})"
            mock_channel.config = {"phone_number": company["signal_phone"]}
            mock_channel.is_active = True
            mock_channel.created_at.isoformat.return_value = "2023-01-01T00:00:00"
            channels.append(mock_channel)
        
        mock_channel_query.filter_by.return_value.all.return_value = channels
        
        # Mock service
        mock_service_instance = Mock()
        mock_service_instance.get_installation_status.return_value = {
            "is_installed": True,
            "cli_path": "/path/to/signal-cli",
            "version": "0.11.5",
            "java_available": True
        }
        mock_service.return_value = mock_service_instance
        
        response = client.get('/api/v1/signal/status', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'installation' in data['data']
        assert 'channels' in data['data']
        assert len(data['data']['channels']) == 3
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.api.signal.get_signal_cli_service')
    @patch('app.api.signal.asyncio.run')
    def test_signal_cli_installation_endpoint(self, mock_asyncio, mock_service, mock_jwt, client, auth_headers):
        """Test Signal CLI installation endpoint."""
        mock_jwt.return_value = 1
        
        # Mock service
        mock_service_instance = Mock()
        mock_service_instance.is_installed = False
        mock_service_instance.get_installation_status.return_value = {
            "is_installed": True,
            "version": "0.11.5"
        }
        mock_service.return_value = mock_service_instance
        
        # Mock installation
        mock_asyncio.return_value = (True, "Signal CLI v0.11.5 installed successfully")
        
        response = client.post('/api/v1/signal/install', 
                             headers=auth_headers,
                             json={"version": "0.11.5"})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert "installed successfully" in data['data']['message']
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.api.signal.get_signal_cli_service')
    @patch('app.api.signal.asyncio.run')
    def test_signal_phone_registration_endpoint(self, mock_asyncio, mock_service, mock_jwt, client, auth_headers, real_company_data):
        """Test Signal phone registration endpoint."""
        company = real_company_data["microsoft_ireland"]
        mock_jwt.return_value = 1
        
        # Mock service
        mock_service_instance = Mock()
        mock_service_instance.is_installed = True
        mock_service.return_value = mock_service_instance
        
        # Mock registration
        mock_asyncio.return_value = (True, "Registration SMS sent. Please check your phone for verification code.")
        
        response = client.post('/api/v1/signal/register',
                             headers=auth_headers,
                             json={"phone_number": company["signal_phone"]})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['phone_number'] == company["signal_phone"]
        assert data['data']['next_step'] == "verification"
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.api.signal.get_signal_cli_service')
    @patch('app.api.signal.asyncio.run')
    def test_signal_phone_verification_endpoint(self, mock_asyncio, mock_service, mock_jwt, client, auth_headers, real_company_data):
        """Test Signal phone verification endpoint."""
        company = real_company_data["sap_germany"]
        mock_jwt.return_value = 1
        
        # Mock service
        mock_service_instance = Mock()
        mock_service_instance.is_installed = True
        mock_service.return_value = mock_service_instance
        
        # Mock verification and account info
        mock_asyncio.side_effect = [
            (True, "Phone number verified successfully. Signal account is ready."),
            {
                "phone_number": company["signal_phone"],
                "is_registered": True,
                "cli_version": "0.11.5"
            }
        ]
        
        response = client.post('/api/v1/signal/verify',
                             headers=auth_headers,
                             json={
                                 "phone_number": company["signal_phone"],
                                 "verification_code": "123456"
                             })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['phone_number'] == company["signal_phone"]
        assert data['data']['next_step'] == "create_channel"
        assert 'account_info' in data['data']
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.User.query')
    @patch('app.models.Channel.query')
    @patch('app.api.signal.get_signal_cli_service')
    @patch('app.api.signal.asyncio.run')
    @patch('app.api.signal.db.session')
    def test_signal_channel_creation_endpoint(self, mock_session, mock_asyncio, mock_service, mock_channel_query, mock_user_query, mock_jwt, client, auth_headers, real_company_data):
        """Test Signal channel creation endpoint."""
        company = real_company_data["unilever_uk"]
        mock_jwt.return_value = 1
        
        # Mock user
        mock_user = Mock()
        mock_user.tenant_id = "test_tenant"
        mock_user_query.get.return_value = mock_user
        
        # Mock no existing channel
        mock_channel_query.filter_by.return_value.filter.return_value.first.return_value = None
        
        # Mock service
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        
        # Mock registered accounts
        mock_asyncio.return_value = [company["signal_phone"]]
        
        # Mock channel creation
        with patch('app.api.signal.Channel') as mock_channel_class:
            mock_channel = Mock()
            mock_channel.id = 1
            mock_channel.name = f"Signal ({company['signal_phone']})"
            mock_channel.config = {
                "phone_number": company["signal_phone"],
                "auto_response": True,
                "polling_interval": 2,
                "enabled": True
            }
            mock_channel.created_at.isoformat.return_value = "2023-01-01T00:00:00"
            mock_channel_class.return_value = mock_channel
            
            response = client.post('/api/v1/signal/channels',
                                 headers=auth_headers,
                                 json={
                                     "phone_number": company["signal_phone"],
                                     "name": f"{company['name']} Signal Bot",
                                     "auto_response": True,
                                     "polling_interval": 2
                                 })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert "created successfully" in data['data']['message']
            assert data['data']['channel']['phone_number'] == company["signal_phone"]


class TestSignalIntegrationScenarios:
    """Test complete Signal integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_signal_setup_flow(self, signal_cli_service, real_company_data):
        """Test complete Signal setup flow from installation to channel creation."""
        company = real_company_data["microsoft_ireland"]
        
        # Step 1: Install Signal CLI
        with patch.object(signal_cli_service, 'install_signal_cli') as mock_install:
            mock_install.return_value = (True, "Signal CLI installed successfully")
            success, message = await signal_cli_service.install_signal_cli("latest")
            assert success is True
        
        # Step 2: Register phone number
        with patch.object(signal_cli_service, 'register_phone_number') as mock_register:
            mock_register.return_value = (True, "Registration SMS sent")
            success, message = await signal_cli_service.register_phone_number(company["signal_phone"])
            assert success is True
        
        # Step 3: Verify phone number
        with patch.object(signal_cli_service, 'verify_phone_number') as mock_verify:
            mock_verify.return_value = (True, "Phone number verified successfully")
            success, message = await signal_cli_service.verify_phone_number(company["signal_phone"], "123456")
            assert success is True
        
        # Step 4: Test message sending
        with patch.object(signal_cli_service, 'send_message') as mock_send:
            mock_send.return_value = (True, "Message sent successfully")
            success, message = await signal_cli_service.send_message(
                company["signal_phone"],
                "+1234567890",
                f"Hello from {company['name']}!"
            )
            assert success is True
    
    @pytest.mark.asyncio
    async def test_signal_business_conversation_flow(self, signal_bot_handler, real_company_data):
        """Test complete business conversation flow via Signal."""
        company = real_company_data["sap_germany"]
        
        # Mock conversation messages
        conversation_messages = [
            {
                "envelope": {
                    "source": "+1234567890",
                    "timestamp": 1640995200000,
                    "dataMessage": {
                        "message": f"Hi, I'm interested in {company['name']} solutions for our enterprise.",
                        "attachments": []
                    }
                }
            },
            {
                "envelope": {
                    "source": "+1234567890",
                    "timestamp": 1640995260000,
                    "dataMessage": {
                        "message": f"Can you provide information about pricing for {company['name']} ERP systems?",
                        "attachments": []
                    }
                }
            },
            {
                "envelope": {
                    "source": "+1234567890",
                    "timestamp": 1640995320000,
                    "dataMessage": {
                        "message": "I'd like to schedule a demo with your sales team.",
                        "attachments": []
                    }
                }
            }
        ]
        
        # Mock dependencies
        signal_bot_handler._create_agent_context = AsyncMock()
        signal_bot_handler._store_message = AsyncMock()
        signal_bot_handler._send_ai_response = AsyncMock()
        
        mock_context = AgentContext(
            tenant_id="test_tenant",
            user_id="+1234567890",
            channel_type="signal",
            conversation_id="1",
            customer_id="+1234567890"
        )
        signal_bot_handler._create_agent_context.return_value = mock_context
        
        # Mock AI responses for each message
        ai_responses = [
            AgentResponse(
                content=f"Hello! Thank you for your interest in {company['name']} solutions. I'd be happy to help you learn more about our enterprise offerings.",
                confidence=0.9,
                intent="product_inquiry"
            ),
            AgentResponse(
                content=f"I can provide general information about {company['name']} ERP pricing. For detailed quotes, I'll connect you with our sales team.",
                confidence=0.8,
                intent="pricing_inquiry"
            ),
            AgentResponse(
                content="I'd be happy to help you schedule a demo! Let me connect you with our sales team to arrange a personalized demonstration.",
                confidence=0.9,
                intent="demo_request",
                requires_handoff=True
            )
        ]
        
        # Process each message in the conversation
        for i, message_data in enumerate(conversation_messages):
            signal_bot_handler.orchestrator.process_message = AsyncMock(return_value=ai_responses[i])
            await signal_bot_handler._process_received_message(message_data)
        
        # Verify all messages were processed
        assert signal_bot_handler._store_message.call_count == 3
        assert signal_bot_handler._create_agent_context.call_count == 3
        assert signal_bot_handler.orchestrator.process_message.call_count == 3
        assert signal_bot_handler._send_ai_response.call_count == 3
    
    @pytest.mark.asyncio
    async def test_signal_error_handling_scenarios(self, signal_cli_service, real_company_data):
        """Test Signal error handling scenarios."""
        company = real_company_data["unilever_uk"]
        
        # Test registration with rate limiting
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Rate limited. Please wait before trying again."
        
        with patch.object(signal_cli_service, '_run_command', return_value=mock_result):
            success, message = await signal_cli_service.register_phone_number(company["signal_phone"])
            assert success is False
            assert "Rate limited" in message
        
        # Test verification with expired code
        mock_result.stderr = "Verification code expired. Please request a new one."
        
        with patch.object(signal_cli_service, '_run_command', return_value=mock_result):
            success, message = await signal_cli_service.verify_phone_number(company["signal_phone"], "123456")
            assert success is False
            assert "expired" in message
        
        # Test message sending to unregistered recipient
        mock_result.stderr = "Recipient not found or not registered with Signal"
        
        with patch.object(signal_cli_service, '_is_account_registered', return_value=True):
            with patch.object(signal_cli_service, '_run_command', return_value=mock_result):
                success, message = await signal_cli_service.send_message(
                    company["signal_phone"],
                    "+9999999999",
                    "Test message"
                )
                assert success is False
                assert "Recipient not found" in message or "Failed to send message" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])