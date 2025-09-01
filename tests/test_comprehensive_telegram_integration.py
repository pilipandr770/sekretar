"""Comprehensive Telegram integration tests for communication channel testing."""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from app import create_app
from app.channels.telegram_bot import TelegramBotHandler, get_telegram_bot_handler
from app.services.telegram_service import TelegramService, get_telegram_service
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
def telegram_handler():
    """Create Telegram bot handler for testing."""
    return TelegramBotHandler("test_token_123456:ABC-DEF", "https://example.com/webhook")


@pytest.fixture
def telegram_service(app):
    """Create Telegram service for testing."""
    with app.app_context():
        return TelegramService()


@pytest.fixture
def mock_telegram_update():
    """Create comprehensive mock Telegram update."""
    update = Mock()
    
    # User data
    update.effective_user = Mock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.effective_user.language_code = "en"
    
    # Chat data
    update.effective_chat = Mock()
    update.effective_chat.id = 67890
    update.effective_chat.type = "private"
    update.effective_chat.send_action = AsyncMock()
    update.effective_chat.send_message = AsyncMock()
    
    # Message data
    update.message = Mock()
    update.message.text = "Hello, bot!"
    update.message.message_id = 1
    update.message.date = datetime.now()
    update.message.reply_text = AsyncMock()
    update.message.caption = None
    
    return update


@pytest.fixture
def real_company_data():
    """Real company data for testing."""
    return {
        "microsoft_ireland": {
            "name": "Microsoft Ireland Operations Limited",
            "vat_number": "IE9825613N",
            "country": "IE",
            "lei_code": "635400AKJKKLMN4KNZ71",
            "address": "One Microsoft Place, South County Business Park, Leopardstown, Dublin 18",
            "telegram_chat_id": 12345
        },
        "sap_germany": {
            "name": "SAP SE",
            "vat_number": "DE143593636",
            "country": "DE", 
            "lei_code": "529900T8BM49AURSDO55",
            "address": "Dietmar-Hopp-Allee 16, 69190 Walldorf",
            "telegram_chat_id": 67890
        }
    }


class TestTelegramWebhookProcessing:
    """Test webhook message processing with real data scenarios."""
    
    @pytest.mark.asyncio
    async def test_webhook_text_message_processing(self, client, real_company_data):
        """Test webhook processing for text messages."""
        company = real_company_data["microsoft_ireland"]
        
        update_data = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "date": 1234567890,
                "text": f"Hello, I'm from {company['name']}. Our VAT number is {company['vat_number']}.",
                "from": {
                    "id": company["telegram_chat_id"],
                    "first_name": "John",
                    "last_name": "Doe",
                    "username": "johndoe"
                },
                "chat": {
                    "id": company["telegram_chat_id"],
                    "type": "private"
                }
            }
        }
        
        with patch('app.services.telegram_service.get_telegram_service') as mock_get_service:
            mock_service = Mock()
            mock_service.process_webhook_update = AsyncMock(return_value={"status": "success"})
            mock_get_service.return_value = mock_service
            
            response = client.post(
                '/api/v1/channels/telegram/webhook',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Verify the service was called with correct data
            mock_service.process_webhook_update.assert_called_once_with(update_data)
    
    @pytest.mark.asyncio
    async def test_webhook_photo_message_processing(self, client, real_company_data):
        """Test webhook processing for photo messages."""
        company = real_company_data["sap_germany"]
        
        update_data = {
            "update_id": 124,
            "message": {
                "message_id": 2,
                "date": 1234567890,
                "photo": [
                    {
                        "file_id": "photo123",
                        "file_unique_id": "unique123",
                        "width": 1280,
                        "height": 720,
                        "file_size": 102400
                    }
                ],
                "caption": f"Here's our office in {company['address']}",
                "from": {
                    "id": company["telegram_chat_id"],
                    "first_name": "Maria",
                    "last_name": "Schmidt",
                    "username": "mariaschmidt"
                },
                "chat": {
                    "id": company["telegram_chat_id"],
                    "type": "private"
                }
            }
        }
        
        with patch('app.services.telegram_service.get_telegram_service') as mock_get_service:
            mock_service = Mock()
            mock_service.process_webhook_update = AsyncMock(return_value={"status": "success"})
            mock_get_service.return_value = mock_service
            
            response = client.post(
                '/api/v1/channels/telegram/webhook',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
    
    @pytest.mark.asyncio
    async def test_webhook_document_message_processing(self, client, real_company_data):
        """Test webhook processing for document messages."""
        company = real_company_data["microsoft_ireland"]
        
        update_data = {
            "update_id": 125,
            "message": {
                "message_id": 3,
                "date": 1234567890,
                "document": {
                    "file_id": "doc123",
                    "file_unique_id": "unique_doc123",
                    "file_name": "company_profile.pdf",
                    "mime_type": "application/pdf",
                    "file_size": 1048576
                },
                "caption": f"Company profile for {company['name']}",
                "from": {
                    "id": company["telegram_chat_id"],
                    "first_name": "Sarah",
                    "last_name": "Johnson",
                    "username": "sarahjohnson"
                },
                "chat": {
                    "id": company["telegram_chat_id"],
                    "type": "private"
                }
            }
        }
        
        with patch('app.services.telegram_service.get_telegram_service') as mock_get_service:
            mock_service = Mock()
            mock_service.process_webhook_update = AsyncMock(return_value={"status": "success"})
            mock_get_service.return_value = mock_service
            
            response = client.post(
                '/api/v1/channels/telegram/webhook',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
    
    def test_webhook_invalid_data(self, client):
        """Test webhook with invalid data."""
        response = client.post('/api/v1/channels/telegram/webhook')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'No update data provided' in data['message']
    
    def test_webhook_malformed_json(self, client):
        """Test webhook with malformed JSON."""
        response = client.post(
            '/api/v1/channels/telegram/webhook',
            data='invalid json',
            content_type='application/json'
        )
        assert response.status_code == 400


class TestTelegramBotCommands:
    """Test bot command handling with real scenarios."""
    
    @pytest.mark.asyncio
    async def test_start_command_with_company_context(self, telegram_handler, mock_telegram_update, real_company_data):
        """Test /start command with company context."""
        company = real_company_data["microsoft_ireland"]
        
        # Update user context with company info
        mock_telegram_update.effective_user.first_name = "John"
        mock_telegram_update.effective_user.last_name = "Doe"
        mock_telegram_update.effective_chat.id = company["telegram_chat_id"]
        
        telegram_handler._store_message = AsyncMock()
        
        await telegram_handler.handle_start_command(mock_telegram_update, None)
        
        # Verify welcome message was sent
        mock_telegram_update.message.reply_text.assert_called_once()
        call_args = mock_telegram_update.message.reply_text.call_args
        
        message_text = call_args[1]['text'] if 'text' in call_args[1] else call_args[0][0]
        assert "Welcome to AI Secretary" in message_text
        assert "Hello John" in message_text
        
        # Verify inline keyboard was provided
        assert 'reply_markup' in call_args[1]
        
        # Verify message was stored
        telegram_handler._store_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_help_command_comprehensive(self, telegram_handler, mock_telegram_update):
        """Test /help command with comprehensive information."""
        telegram_handler._store_message = AsyncMock()
        
        await telegram_handler.handle_help_command(mock_telegram_update, None)
        
        # Verify help message was sent
        mock_telegram_update.message.reply_text.assert_called_once()
        call_args = mock_telegram_update.message.reply_text.call_args
        
        message_text = call_args[1]['text'] if 'text' in call_args[1] else call_args[0][0]
        assert "AI Secretary Help" in message_text
        assert "Available Commands" in message_text
        assert "/start" in message_text
        assert "/help" in message_text
        assert "/status" in message_text
        assert "/menu" in message_text
        
        # Verify message was stored
        telegram_handler._store_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_menu_command_with_business_options(self, telegram_handler, mock_telegram_update):
        """Test /menu command with business-specific options."""
        telegram_handler._store_message = AsyncMock()
        
        await telegram_handler.handle_menu_command(mock_telegram_update, None)
        
        # Verify menu message was sent
        mock_telegram_update.message.reply_text.assert_called_once()
        call_args = mock_telegram_update.message.reply_text.call_args
        
        message_text = call_args[1]['text'] if 'text' in call_args[1] else call_args[0][0]
        assert "Quick Actions Menu" in message_text
        
        # Verify inline keyboard with business options
        reply_markup = call_args[1]['reply_markup']
        assert reply_markup is not None
        
        # Verify message was stored
        telegram_handler._store_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_status_command_error_handling(self, telegram_handler, mock_telegram_update):
        """Test /status command error handling."""
        telegram_handler._store_message = AsyncMock()
        telegram_handler._send_error_message = AsyncMock()
        
        # The status command will fail due to bot not being initialized
        await telegram_handler.handle_status_command(mock_telegram_update, None)
        
        # Verify error message was sent
        telegram_handler._send_error_message.assert_called_once()
        call_args = telegram_handler._send_error_message.call_args
        assert "couldn't check the status" in call_args[0][1]


class TestTelegramFileUploadProcessing:
    """Test file upload processing with various file types."""
    
    @pytest.mark.asyncio
    async def test_photo_upload_processing(self, telegram_handler, mock_telegram_update, real_company_data):
        """Test photo upload processing."""
        company = real_company_data["sap_germany"]
        
        # Mock photo
        mock_photo = Mock()
        mock_photo.file_id = "photo123"
        mock_photo.get_file = AsyncMock()
        
        mock_file = Mock()
        mock_file.download_as_bytearray = AsyncMock(return_value=b"fake_image_data")
        mock_photo.get_file.return_value = mock_file
        
        mock_telegram_update.message.photo = [mock_photo]
        mock_telegram_update.message.caption = f"Office photo from {company['name']}"
        mock_telegram_update.effective_chat.id = company["telegram_chat_id"]
        
        # Mock dependencies
        telegram_handler._store_message_with_attachment = AsyncMock()
        telegram_handler._create_agent_context = AsyncMock()
        telegram_handler._send_ai_response = AsyncMock()
        
        mock_context = AgentContext(
            tenant_id="test_tenant",
            user_id=str(company["telegram_chat_id"]),
            channel_type="telegram",
            conversation_id="1",
            customer_id=str(company["telegram_chat_id"])
        )
        telegram_handler._create_agent_context.return_value = mock_context
        
        mock_response = AgentResponse(
            content=f"I can see your office photo from {company['name']}! How can I help you today?",
            confidence=0.8,
            intent="photo_received"
        )
        telegram_handler.orchestrator.process_message = AsyncMock(return_value=mock_response)
        
        await telegram_handler.handle_photo_message(mock_telegram_update, None)
        
        # Verify photo was downloaded
        mock_photo.get_file.assert_called_once()
        mock_file.download_as_bytearray.assert_called_once()
        
        # Verify attachment was stored
        telegram_handler._store_message_with_attachment.assert_called_once()
        
        # Verify AI processing
        telegram_handler._create_agent_context.assert_called_once()
        telegram_handler.orchestrator.process_message.assert_called_once()
        telegram_handler._send_ai_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_document_upload_processing(self, telegram_handler, mock_telegram_update, real_company_data):
        """Test document upload processing."""
        company = real_company_data["microsoft_ireland"]
        
        # Mock document
        mock_document = Mock()
        mock_document.file_id = "doc123"
        mock_document.file_name = "company_registration.pdf"
        mock_document.mime_type = "application/pdf"
        mock_document.file_size = 1024 * 500  # 500KB
        mock_document.get_file = AsyncMock()
        
        mock_file = Mock()
        mock_file.download_as_bytearray = AsyncMock(return_value=b"fake_pdf_data")
        mock_document.get_file.return_value = mock_file
        
        mock_telegram_update.message.document = mock_document
        mock_telegram_update.message.caption = f"Registration document for {company['name']}"
        mock_telegram_update.effective_chat.id = company["telegram_chat_id"]
        
        # Mock dependencies
        telegram_handler._store_message_with_attachment = AsyncMock()
        telegram_handler._create_agent_context = AsyncMock()
        telegram_handler._send_ai_response = AsyncMock()
        
        mock_context = AgentContext(
            tenant_id="test_tenant",
            user_id=str(company["telegram_chat_id"]),
            channel_type="telegram",
            conversation_id="1",
            customer_id=str(company["telegram_chat_id"])
        )
        telegram_handler._create_agent_context.return_value = mock_context
        
        mock_response = AgentResponse(
            content=f"I've received your registration document for {company['name']}. I can help you with any questions about it.",
            confidence=0.9,
            intent="document_received"
        )
        telegram_handler.orchestrator.process_message = AsyncMock(return_value=mock_response)
        
        await telegram_handler.handle_document_message(mock_telegram_update, None)
        
        # Verify document was downloaded
        mock_document.get_file.assert_called_once()
        mock_file.download_as_bytearray.assert_called_once()
        
        # Verify attachment was stored
        telegram_handler._store_message_with_attachment.assert_called_once()
        
        # Verify AI processing
        telegram_handler._create_agent_context.assert_called_once()
        telegram_handler.orchestrator.process_message.assert_called_once()
        telegram_handler._send_ai_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_document_too_large_handling(self, telegram_handler, mock_telegram_update):
        """Test handling of documents that are too large."""
        # Mock large document
        mock_document = Mock()
        mock_document.file_size = 25 * 1024 * 1024  # 25MB - too large
        mock_document.file_name = "large_document.pdf"
        
        mock_telegram_update.message.document = mock_document
        
        await telegram_handler.handle_document_message(mock_telegram_update, None)
        
        # Verify error message was sent
        mock_telegram_update.message.reply_text.assert_called_once()
        call_args = mock_telegram_update.message.reply_text.call_args
        message_text = call_args[0][0]
        assert "File too large" in message_text
        assert "20MB" in message_text
    
    @pytest.mark.asyncio
    async def test_voice_message_processing(self, telegram_handler, mock_telegram_update, real_company_data):
        """Test voice message processing."""
        company = real_company_data["sap_germany"]
        
        # Mock voice message
        mock_voice = Mock()
        mock_voice.file_id = "voice123"
        mock_voice.duration = 30
        
        mock_telegram_update.message.voice = mock_voice
        mock_telegram_update.effective_chat.id = company["telegram_chat_id"]
        
        # Mock dependencies
        telegram_handler._store_message = AsyncMock()
        telegram_handler._create_agent_context = AsyncMock()
        telegram_handler._send_ai_response = AsyncMock()
        
        mock_context = AgentContext(
            tenant_id="test_tenant",
            user_id=str(company["telegram_chat_id"]),
            channel_type="telegram",
            conversation_id="1",
            customer_id=str(company["telegram_chat_id"])
        )
        telegram_handler._create_agent_context.return_value = mock_context
        
        mock_response = AgentResponse(
            content="I received your voice message. Audio transcription is not yet implemented, but I'm here to help with text messages!",
            confidence=0.7,
            intent="voice_received"
        )
        telegram_handler.orchestrator.process_message = AsyncMock(return_value=mock_response)
        
        await telegram_handler.handle_voice_message(mock_telegram_update, None)
        
        # Verify message was stored
        telegram_handler._store_message.assert_called_once()
        
        # Verify AI processing
        telegram_handler._create_agent_context.assert_called_once()
        telegram_handler.orchestrator.process_message.assert_called_once()
        telegram_handler._send_ai_response.assert_called_once()


class TestTelegramCallbackQueryHandling:
    """Test inline keyboard callback query handling."""
    
    @pytest.mark.asyncio
    async def test_contact_sales_callback(self, telegram_handler, mock_telegram_update):
        """Test contact sales callback query."""
        telegram_handler._store_callback_interaction = AsyncMock()
        
        # Mock callback query
        mock_query = Mock()
        mock_query.data = "contact_sales"
        mock_query.answer = AsyncMock()
        mock_query.edit_message_text = AsyncMock()
        
        mock_telegram_update.callback_query = mock_query
        
        await telegram_handler.handle_callback_query(mock_telegram_update, None)
        
        # Verify callback was acknowledged
        mock_query.answer.assert_called_once()
        
        # Verify message was edited with sales inquiry content
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        message_text = call_args[1]['text']
        assert "Sales Inquiry" in message_text
        assert "sales questions" in message_text
        
        # Verify interaction was stored
        telegram_handler._store_callback_interaction.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_support_callback(self, telegram_handler, mock_telegram_update):
        """Test get support callback query."""
        telegram_handler._store_callback_interaction = AsyncMock()
        
        # Mock callback query
        mock_query = Mock()
        mock_query.data = "get_support"
        mock_query.answer = AsyncMock()
        mock_query.edit_message_text = AsyncMock()
        
        mock_telegram_update.callback_query = mock_query
        
        await telegram_handler.handle_callback_query(mock_telegram_update, None)
        
        # Verify callback was acknowledged
        mock_query.answer.assert_called_once()
        
        # Verify message was edited with support content
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        message_text = call_args[1]['text']
        assert "Technical Support" in message_text
        assert "technical issues" in message_text
        
        # Verify interaction was stored
        telegram_handler._store_callback_interaction.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_book_meeting_callback(self, telegram_handler, mock_telegram_update):
        """Test book meeting callback query."""
        telegram_handler._store_callback_interaction = AsyncMock()
        
        # Mock callback query
        mock_query = Mock()
        mock_query.data = "book_meeting"
        mock_query.answer = AsyncMock()
        mock_query.edit_message_text = AsyncMock()
        
        mock_telegram_update.callback_query = mock_query
        
        await telegram_handler.handle_callback_query(mock_telegram_update, None)
        
        # Verify callback was acknowledged
        mock_query.answer.assert_called_once()
        
        # Verify message was edited with meeting scheduling content
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        message_text = call_args[1]['text']
        assert "Meeting Scheduling" in message_text
        assert "schedule a meeting" in message_text
        
        # Verify interaction was stored
        telegram_handler._store_callback_interaction.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_human_handoff_callback(self, telegram_handler, mock_telegram_update):
        """Test human handoff callback query."""
        telegram_handler._store_callback_interaction = AsyncMock()
        
        # Mock callback query
        mock_query = Mock()
        mock_query.data = "human_handoff"
        mock_query.answer = AsyncMock()
        mock_query.edit_message_text = AsyncMock()
        
        mock_telegram_update.callback_query = mock_query
        
        await telegram_handler.handle_callback_query(mock_telegram_update, None)
        
        # Verify callback was acknowledged
        mock_query.answer.assert_called_once()
        
        # Verify message was edited with handoff content
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        message_text = call_args[1]['text']
        assert "Human Agent Request" in message_text
        assert "human agent" in message_text
        
        # Verify interaction was stored
        telegram_handler._store_callback_interaction.assert_called_once()


class TestTelegramAPIEndpoints:
    """Test Telegram API endpoints with real scenarios."""
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    def test_setup_telegram_channel_success(self, mock_query, mock_jwt, client, auth_headers, real_company_data):
        """Test successful Telegram channel setup."""
        company = real_company_data["microsoft_ireland"]
        mock_jwt.return_value = "test_tenant"
        mock_query.filter_by.return_value.first.return_value = None
        
        # Mock channel creation
        mock_channel = Mock()
        mock_channel.to_dict.return_value = {
            "id": 1, 
            "name": f"{company['name']} Bot",
            "type": "telegram",
            "is_connected": True
        }
        mock_channel.mark_connected.return_value = mock_channel
        mock_channel.save.return_value = None
        
        with patch('app.models.Channel.create_telegram_channel', return_value=mock_channel):
            with patch('app.channels.telegram_bot.get_telegram_bot_handler') as mock_get_handler:
                mock_handler = Mock()
                mock_handler.initialize = AsyncMock(return_value=True)
                mock_get_handler.return_value = mock_handler
                
                response = client.post(
                    '/api/v1/channels/telegram/setup',
                    data=json.dumps({
                        'bot_token': 'test_token_123456:ABC-DEF',
                        'name': f"{company['name']} Bot",
                        'webhook_url': 'https://example.com/webhook'
                    }),
                    content_type='application/json',
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] is True
                assert 'created successfully' in data['message']
                assert data['data']['name'] == f"{company['name']} Bot"
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    @patch('app.channels.telegram_bot.get_telegram_bot_handler')
    def test_test_telegram_connection_success(self, mock_get_handler, mock_query, mock_jwt, client, auth_headers, real_company_data):
        """Test successful Telegram connection test."""
        company = real_company_data["sap_germany"]
        mock_jwt.return_value = "test_tenant"
        
        # Mock channel with token
        mock_channel = Mock()
        mock_channel.get_config.return_value = "test_token_123456:ABC-DEF"
        mock_channel.mark_connected.return_value = mock_channel
        mock_channel.save.return_value = None
        mock_query.filter_by.return_value.first.return_value = mock_channel
        
        # Mock bot handler and bot info
        mock_bot_info = Mock()
        mock_bot_info.id = 123456
        mock_bot_info.username = f"{company['name'].lower().replace(' ', '_')}_bot"
        mock_bot_info.first_name = f"{company['name']} Bot"
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
        assert data['data']['bot_info']['first_name'] == f"{company['name']} Bot"
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    @patch('app.channels.telegram_bot.get_telegram_bot_handler')
    def test_send_telegram_message_success(self, mock_get_handler, mock_query, mock_jwt, client, auth_headers, real_company_data):
        """Test successful Telegram message sending."""
        company = real_company_data["microsoft_ireland"]
        mock_jwt.return_value = "test_tenant"
        
        # Mock channel
        mock_channel = Mock()
        mock_channel.get_config.return_value = "test_token_123456:ABC-DEF"
        mock_channel.increment_sent.return_value = mock_channel
        mock_channel.save.return_value = None
        mock_query.filter_by.return_value.first.return_value = mock_channel
        
        # Mock sent message
        mock_sent_message = Mock()
        mock_sent_message.message_id = 123
        mock_sent_message.chat_id = company["telegram_chat_id"]
        mock_sent_message.date = Mock()
        mock_sent_message.date.isoformat.return_value = "2023-01-01T00:00:00"
        
        # Mock bot handler
        mock_handler = Mock()
        mock_handler.bot.send_message = AsyncMock(return_value=mock_sent_message)
        mock_get_handler.return_value = mock_handler
        
        response = client.post(
            '/api/v1/channels/telegram/send',
            data=json.dumps({
                'chat_id': company["telegram_chat_id"],
                'message': f'Hello from {company["name"]}! How can we help you today?'
            }),
            content_type='application/json',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'sent successfully' in data['message']
        assert data['data']['message_id'] == 123
        assert data['data']['chat_id'] == company["telegram_chat_id"]
    
    @patch('flask_jwt_extended.get_jwt_identity')
    @patch('app.models.Channel.query')
    def test_get_telegram_status_success(self, mock_query, mock_jwt, client, auth_headers, real_company_data):
        """Test successful Telegram status retrieval."""
        company = real_company_data["sap_germany"]
        mock_jwt.return_value = "test_tenant"
        
        # Mock channel
        mock_channel = Mock()
        mock_channel.is_connected = True
        mock_channel.get_config.return_value = "https://example.com/webhook"
        mock_channel.messages_received = 25
        mock_channel.messages_sent = 15
        mock_channel.to_dict.return_value = {
            "id": 1,
            "name": f"{company['name']} Bot",
            "is_connected": True,
            "type": "telegram"
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
        assert data['data']['statistics']['messages_received'] == 25
        assert data['data']['statistics']['messages_sent'] == 15
        assert data['data']['statistics']['total_messages'] == 40


if __name__ == "__main__":
    pytest.main([__file__, "-v"])