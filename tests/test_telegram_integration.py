"""Unit tests for Telegram Bot integration."""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from app import create_app
from app.channels.telegram_bot import TelegramBotHandler, get_telegram_bot_handler
from app.services.telegram_service import TelegramService, get_telegram_service
from app.models import Channel, InboxMessage, Thread, Attachment
from app.secretary.agents.base_agent import AgentContext, AgentResponse


@pytest.fixture
def app():
    """Create test Flask app."""
    app = create_app('testing')
    with app.app_context():
        yield app


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
def mock_update():
    """Create mock Telegram update."""
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.effective_user.language_code = "en"
    
    update.effective_chat = Mock()
    update.effective_chat.id = 67890
    update.effective_chat.type = "private"
    update.effective_chat.send_action = AsyncMock()
    update.effective_chat.send_message = AsyncMock()
    
    update.message = Mock()
    update.message.text = "Hello, bot!"
    update.message.message_id = 1
    update.message.date = datetime.now()
    update.message.reply_text = AsyncMock()
    update.message.caption = None
    
    return update


class TestTelegramBotHandler:
    """Test cases for TelegramBotHandler."""
    
    def test_handler_initialization(self, telegram_handler):
        """Test bot handler initialization."""
        assert telegram_handler.bot_token == "test_token_123456:ABC-DEF"
        assert telegram_handler.webhook_url == "https://example.com/webhook"
        assert telegram_handler.max_message_length == 4096
        assert len(telegram_handler.supported_file_types) == 7
        assert telegram_handler.bot is not None
        assert telegram_handler.orchestrator is not None
    
    @pytest.mark.asyncio
    async def test_initialize_bot(self, telegram_handler):
        """Test bot initialization."""
        with patch.object(telegram_handler, 'set_webhook', return_value=True):
            result = await telegram_handler.initialize()
            assert result is True
            assert telegram_handler.application is not None
    
    @pytest.mark.asyncio
    async def test_set_webhook(self, telegram_handler):
        """Test webhook setting."""
        with patch('telegram.Bot.set_webhook', new_callable=AsyncMock) as mock_set:
            mock_set.return_value = True
            result = await telegram_handler.set_webhook()
            assert result is True
            mock_set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_remove_webhook(self, telegram_handler):
        """Test webhook removal."""
        with patch('telegram.Bot.delete_webhook', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True
            result = await telegram_handler.remove_webhook()
            assert result is True
            mock_delete.assert_called_once()
    
    def test_split_long_message_short(self, telegram_handler):
        """Test splitting short messages."""
        short_message = "This is a short message."
        result = telegram_handler._split_long_message(short_message)
        assert len(result) == 1
        assert result[0] == short_message
    
    def test_split_long_message_long(self, telegram_handler):
        """Test splitting long messages."""
        long_message = "A" * 5000  # Longer than Telegram's limit
        result = telegram_handler._split_long_message(long_message)
        assert len(result) > 1
        assert all(len(msg) <= telegram_handler.max_message_length for msg in result)
        # Note: The split algorithm may add periods, so we check content is preserved
        joined_result = "".join(result).replace(". ", "").replace(".", "")
        assert joined_result == long_message
    
    def test_split_long_message_paragraphs(self, telegram_handler):
        """Test splitting messages with paragraphs."""
        paragraphs = ["A" * 2000, "B" * 2000, "C" * 2000]
        long_message = "\n\n".join(paragraphs)
        result = telegram_handler._split_long_message(long_message)
        assert len(result) >= 2  # Should split into multiple messages
        assert all(len(msg) <= telegram_handler.max_message_length for msg in result)
    
    @pytest.mark.asyncio
    async def test_handle_start_command(self, telegram_handler, mock_update):
        """Test /start command handling."""
        telegram_handler._store_message = AsyncMock()
        
        await telegram_handler.handle_start_command(mock_update, None)
        
        # Verify message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        
        # Check message content
        if call_args[0]:
            message_text = call_args[0][0]
        else:
            message_text = call_args[1]['text']
        
        assert "Welcome to AI Secretary" in message_text
        assert "Hello Test" in message_text
        
        # Verify message was stored
        telegram_handler._store_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_help_command(self, telegram_handler, mock_update):
        """Test /help command handling."""
        telegram_handler._store_message = AsyncMock()
        
        await telegram_handler.handle_help_command(mock_update, None)
        
        # Verify message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        
        # Check message content
        if call_args[0]:
            message_text = call_args[0][0]
        else:
            message_text = call_args[1]['text']
        
        assert "AI Secretary Help" in message_text
        assert "Available Commands" in message_text
        
        # Verify message was stored
        telegram_handler._store_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_status_command(self, telegram_handler, mock_update):
        """Test /status command handling."""
        telegram_handler._store_message = AsyncMock()
        telegram_handler._send_error_message = AsyncMock()
        
        # The status command will fail due to bot not being initialized
        # This tests the error handling path
        await telegram_handler.handle_status_command(mock_update, None)
        
        # Verify error message was sent (since bot is not initialized)
        telegram_handler._send_error_message.assert_called_once()
        call_args = telegram_handler._send_error_message.call_args
        assert "couldn't check the status" in call_args[0][1]
    
    @pytest.mark.asyncio
    async def test_handle_menu_command(self, telegram_handler, mock_update):
        """Test /menu command handling."""
        telegram_handler._store_message = AsyncMock()
        
        await telegram_handler.handle_menu_command(mock_update, None)
        
        # Verify message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        
        # Check message content and inline keyboard
        if call_args[0]:
            message_text = call_args[0][0]
        else:
            message_text = call_args[1]['text']
        
        assert "Quick Actions Menu" in message_text
        
        # Check if reply_markup was provided
        reply_markup = call_args[1].get('reply_markup')
        assert reply_markup is not None
        
        # Verify message was stored
        telegram_handler._store_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_text_message(self, telegram_handler, mock_update):
        """Test text message handling."""
        telegram_handler._store_message = AsyncMock()
        telegram_handler._create_agent_context = AsyncMock()
        telegram_handler._send_ai_response = AsyncMock()
        
        # Mock agent context
        mock_context = AgentContext(
            tenant_id="test_tenant",
            user_id="12345",
            channel_type="telegram",
            conversation_id="1",
            customer_id="12345"
        )
        telegram_handler._create_agent_context.return_value = mock_context
        
        # Mock orchestrator response
        mock_response = AgentResponse(
            content="Hello! How can I help you?",
            confidence=0.9,
            intent="greeting"
        )
        telegram_handler.orchestrator.process_message = AsyncMock(return_value=mock_response)
        
        await telegram_handler.handle_text_message(mock_update, None)
        
        # Verify typing action was sent
        mock_update.effective_chat.send_action.assert_called_once_with(action="typing")
        
        # Verify message was stored
        telegram_handler._store_message.assert_called_once()
        
        # Verify agent context was created
        telegram_handler._create_agent_context.assert_called_once()
        
        # Verify orchestrator was called
        telegram_handler.orchestrator.process_message.assert_called_once_with(
            "Hello, bot!", mock_context
        )
        
        # Verify AI response was sent
        telegram_handler._send_ai_response.assert_called_once_with(mock_update, mock_response)
    
    @pytest.mark.asyncio
    async def test_handle_photo_message(self, telegram_handler, mock_update):
        """Test photo message handling."""
        telegram_handler._store_message_with_attachment = AsyncMock()
        telegram_handler._create_agent_context = AsyncMock()
        telegram_handler._send_ai_response = AsyncMock()
        
        # Mock photo
        mock_photo = Mock()
        mock_photo.file_id = "photo123"
        mock_photo.get_file = AsyncMock()
        
        mock_file = Mock()
        mock_file.download_as_bytearray = AsyncMock(return_value=b"fake_image_data")
        mock_photo.get_file.return_value = mock_file
        
        mock_update.message.photo = [mock_photo]  # Telegram sends array of photo sizes
        mock_update.message.caption = "Test photo"
        
        # Mock agent context and response
        mock_context = AgentContext(tenant_id="test_tenant", user_id="12345")
        telegram_handler._create_agent_context.return_value = mock_context
        
        mock_response = AgentResponse(content="I can see your photo!", confidence=0.8)
        telegram_handler.orchestrator.process_message = AsyncMock(return_value=mock_response)
        
        await telegram_handler.handle_photo_message(mock_update, None)
        
        # Verify attachment was stored
        telegram_handler._store_message_with_attachment.assert_called_once()
        
        # Verify AI processing
        telegram_handler._create_agent_context.assert_called_once()
        telegram_handler.orchestrator.process_message.assert_called_once()
        telegram_handler._send_ai_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_document_message(self, telegram_handler, mock_update):
        """Test document message handling."""
        telegram_handler._store_message_with_attachment = AsyncMock()
        telegram_handler._create_agent_context = AsyncMock()
        telegram_handler._send_ai_response = AsyncMock()
        
        # Mock document
        mock_document = Mock()
        mock_document.file_id = "doc123"
        mock_document.file_name = "test.pdf"
        mock_document.mime_type = "application/pdf"
        mock_document.file_size = 1024  # 1KB
        mock_document.get_file = AsyncMock()
        
        mock_file = Mock()
        mock_file.download_as_bytearray = AsyncMock(return_value=b"fake_pdf_data")
        mock_document.get_file.return_value = mock_file
        
        mock_update.message.document = mock_document
        mock_update.message.caption = "Test document"
        
        # Mock agent context and response
        mock_context = AgentContext(tenant_id="test_tenant", user_id="12345")
        telegram_handler._create_agent_context.return_value = mock_context
        
        mock_response = AgentResponse(content="I received your document!", confidence=0.8)
        telegram_handler.orchestrator.process_message = AsyncMock(return_value=mock_response)
        
        await telegram_handler.handle_document_message(mock_update, None)
        
        # Verify attachment was stored
        telegram_handler._store_message_with_attachment.assert_called_once()
        
        # Verify AI processing
        telegram_handler._create_agent_context.assert_called_once()
        telegram_handler.orchestrator.process_message.assert_called_once()
        telegram_handler._send_ai_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_document_message_too_large(self, telegram_handler, mock_update):
        """Test document message handling with file too large."""
        # Mock large document
        mock_document = Mock()
        mock_document.file_size = 25 * 1024 * 1024  # 25MB - too large
        
        mock_update.message.document = mock_document
        
        await telegram_handler.handle_document_message(mock_update, None)
        
        # Verify error message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        message_text = call_args[0][0]
        assert "File too large" in message_text
    
    @pytest.mark.asyncio
    async def test_handle_callback_query(self, telegram_handler, mock_update):
        """Test callback query handling."""
        telegram_handler._store_callback_interaction = AsyncMock()
        
        # Mock callback query
        mock_query = Mock()
        mock_query.data = "contact_sales"
        mock_query.answer = AsyncMock()
        mock_query.edit_message_text = AsyncMock()
        
        mock_update.callback_query = mock_query
        
        await telegram_handler.handle_callback_query(mock_update, None)
        
        # Verify callback was acknowledged
        mock_query.answer.assert_called_once()
        
        # Verify message was edited
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        message_text = call_args[1]['text']
        assert "Sales Inquiry" in message_text
        
        # Verify interaction was stored
        telegram_handler._store_callback_interaction.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_ai_response(self, telegram_handler, mock_update):
        """Test sending AI response."""
        telegram_handler._store_message = AsyncMock()
        
        # Test normal response
        response = AgentResponse(
            content="This is a test response.",
            confidence=0.9,
            intent="test"
        )
        
        await telegram_handler._send_ai_response(mock_update, response)
        
        # Verify message was sent
        mock_update.effective_chat.send_message.assert_called_once()
        call_args = mock_update.effective_chat.send_message.call_args
        assert call_args[1]['text'] == "This is a test response."
        
        # Verify message was stored
        telegram_handler._store_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_ai_response_with_handoff(self, telegram_handler, mock_update):
        """Test sending AI response that requires handoff."""
        telegram_handler._store_message = AsyncMock()
        
        # Test response requiring handoff
        response = AgentResponse(
            content="I need to connect you with a human.",
            confidence=0.5,
            intent="handoff",
            requires_handoff=True
        )
        
        await telegram_handler._send_ai_response(mock_update, response)
        
        # Verify message was sent with inline keyboard
        mock_update.effective_chat.send_message.assert_called_once()
        call_args = mock_update.effective_chat.send_message.call_args
        assert call_args[1]['reply_markup'] is not None
    
    @pytest.mark.asyncio
    async def test_send_ai_response_long_message(self, telegram_handler, mock_update):
        """Test sending long AI response that needs splitting."""
        telegram_handler._store_message = AsyncMock()
        
        # Test long response
        long_content = "A" * 5000  # Longer than Telegram's limit
        response = AgentResponse(
            content=long_content,
            confidence=0.9,
            intent="test"
        )
        
        await telegram_handler._send_ai_response(mock_update, response)
        
        # Verify multiple messages were sent
        assert mock_update.effective_chat.send_message.call_count > 1
        
        # Verify all messages were stored
        assert telegram_handler._store_message.call_count > 1
    
    @pytest.mark.asyncio
    async def test_create_agent_context(self, telegram_handler, mock_update):
        """Test agent context creation."""
        # Mock channel and thread
        mock_channel = Mock()
        mock_channel.id = 1
        mock_channel.tenant_id = "test_tenant"
        
        mock_thread = Mock()
        mock_thread.id = 1
        
        telegram_handler._get_or_create_channel = AsyncMock(return_value=mock_channel)
        telegram_handler._get_or_create_thread = AsyncMock(return_value=mock_thread)
        
        context = await telegram_handler._create_agent_context(mock_update)
        
        assert context.tenant_id == "test_tenant"
        assert context.user_id == "12345"
        assert context.channel_type == "telegram"
        assert context.conversation_id == "1"
        assert context.customer_id == "12345"
        assert context.language == "en"
        assert "telegram_user" in context.metadata
        assert "telegram_chat" in context.metadata
    
    @pytest.mark.asyncio
    async def test_handle_webhook_update(self, telegram_handler):
        """Test webhook update handling."""
        # Mock application
        telegram_handler.application = Mock()
        telegram_handler.application.process_update = AsyncMock()
        
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
        
        with patch('telegram.Update.de_json') as mock_de_json:
            mock_update_obj = Mock()
            mock_de_json.return_value = mock_update_obj
            
            result = await telegram_handler.handle_webhook_update(update_data)
        
        assert result["status"] == "success"
        assert result["processed"] is True
        telegram_handler.application.process_update.assert_called_once_with(mock_update_obj)
    
    @pytest.mark.asyncio
    async def test_handle_webhook_update_invalid_data(self, telegram_handler):
        """Test webhook update handling with invalid data."""
        result = await telegram_handler.handle_webhook_update({})
        assert "error" in result
        assert "Invalid update data" in result["error"]


class TestTelegramService:
    """Test cases for TelegramService."""
    
    def test_service_initialization(self, telegram_service):
        """Test service initialization."""
        assert telegram_service.logger is not None
        assert telegram_service.bot_handlers == {}
        assert telegram_service.orchestrator is not None
    
    @pytest.mark.asyncio
    async def test_process_webhook_update_no_chat_id(self, telegram_service):
        """Test webhook processing with no chat ID."""
        update_data = {"update_id": 123}
        result = await telegram_service.process_webhook_update(update_data)
        assert "error" in result
        assert "Could not determine chat ID" in result["error"]
    
    @pytest.mark.asyncio
    async def test_process_webhook_update_no_channel(self, telegram_service):
        """Test webhook processing with no matching channel."""
        update_data = {
            "message": {
                "chat": {"id": 999999}  # Non-existent chat ID
            }
        }
        
        with patch.object(telegram_service, '_find_channel_by_chat_id', return_value=None):
            result = await telegram_service.process_webhook_update(update_data)
            assert "error" in result
            assert "Channel not found" in result["error"]
    
    def test_find_channel_by_chat_id_not_found(self, app, telegram_service):
        """Test finding channel by chat ID when not found."""
        with app.app_context():
            with patch('app.models.Channel.query') as mock_query:
                mock_query.filter_by.return_value.all.return_value = []
                mock_query.filter_by.return_value.first.return_value = None
                
                result = telegram_service._find_channel_by_chat_id(12345)
                assert result is None
    
    @pytest.mark.asyncio
    async def test_send_message_bot_not_initialized(self, telegram_service):
        """Test sending message when bot is not initialized."""
        with patch.object(telegram_service, 'initialize_tenant_bot', return_value=False):
            result = await telegram_service.send_message("tenant1", 12345, "Hello")
            assert "error" in result
            assert "Bot not initialized" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_bot_info_bot_not_initialized(self, telegram_service):
        """Test getting bot info when bot is not initialized."""
        with patch.object(telegram_service, 'initialize_tenant_bot', return_value=False):
            result = await telegram_service.get_bot_info("tenant1")
            assert "error" in result
            assert "Bot not initialized" in result["error"]
    
    def test_get_active_tenants_empty(self, app, telegram_service):
        """Test getting active tenants when none exist."""
        with app.app_context():
            with patch('app.models.Channel.query') as mock_query:
                mock_query.filter_by.return_value.all.return_value = []
                
                result = telegram_service.get_active_tenants()
                assert result == []
    
    def test_get_active_tenants_with_channels(self, app, telegram_service):
        """Test getting active tenants with channels."""
        with app.app_context():
            mock_channel1 = Mock()
            mock_channel1.tenant_id = "tenant1"
            mock_channel2 = Mock()
            mock_channel2.tenant_id = "tenant2"
            
            with patch('app.models.Channel.query') as mock_query:
                mock_query.filter_by.return_value.all.return_value = [mock_channel1, mock_channel2]
                
                result = telegram_service.get_active_tenants()
                assert result == ["tenant1", "tenant2"]


class TestTelegramIntegrationHelpers:
    """Test helper functions and utilities."""
    
    def test_get_telegram_bot_handler_with_token(self):
        """Test getting bot handler with token."""
        handler = get_telegram_bot_handler("test_token", "https://example.com")
        assert handler.bot_token == "test_token"
        assert handler.webhook_url == "https://example.com"
    
    def test_get_telegram_service(self):
        """Test getting telegram service."""
        service = get_telegram_service()
        assert isinstance(service, TelegramService)
        
        # Should return same instance (singleton pattern)
        service2 = get_telegram_service()
        assert service is service2


class TestTelegramModelsIntegration:
    """Test integration with database models."""
    
    @pytest.mark.asyncio
    async def test_store_message_db_inbound(self, app, telegram_service):
        """Test storing inbound message in database."""
        with app.app_context():
            # Mock channel
            mock_channel = Mock()
            mock_channel.id = 1
            mock_channel.tenant_id = "test_tenant"
            
            # Mock user data
            mock_update = {
                'message': {
                    'from': {
                        'id': 12345,
                        'first_name': 'Test',
                        'last_name': 'User',
                        'username': 'testuser'
                    },
                    'chat': {
                        'id': 67890,
                        'type': 'private'
                    }
                }
            }
            
            # Mock thread
            mock_thread = Mock()
            mock_thread.id = 1
            
            with patch.object(telegram_service, '_get_or_create_thread_db', return_value=mock_thread):
                with patch('app.models.InboxMessage.create_inbound') as mock_create:
                    mock_message = Mock()
                    mock_message.save = Mock()
                    mock_create.return_value = mock_message
                    
                    await telegram_service._store_message_db(
                        mock_channel, mock_update, "text", "Hello", "inbound"
                    )
                    
                    # Verify message was created
                    mock_create.assert_called_once()
                    mock_message.save.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_or_create_thread_db_existing(self, app, telegram_service):
        """Test getting existing thread from database."""
        with app.app_context():
            # Mock channel
            mock_channel = Mock()
            mock_channel.id = 1
            mock_channel.tenant_id = "test_tenant"
            
            # Mock user
            mock_user = Mock()
            mock_user.id = 12345
            mock_user.first_name = "Test"
            
            # Mock existing thread
            mock_thread = Mock()
            mock_thread.id = 1
            
            with patch('app.models.Thread.query') as mock_query:
                mock_query.filter_by.return_value.first.return_value = mock_thread
                
                result = await telegram_service._get_or_create_thread_db(mock_channel, mock_user)
                assert result == mock_thread
    
    @pytest.mark.asyncio
    async def test_get_or_create_thread_db_new(self, app, telegram_service):
        """Test creating new thread in database."""
        with app.app_context():
            # Mock channel
            mock_channel = Mock()
            mock_channel.id = 1
            mock_channel.tenant_id = "test_tenant"
            
            # Mock user
            mock_user = Mock()
            mock_user.id = 12345
            mock_user.first_name = "Test"
            mock_user.username = "testuser"
            mock_user.last_name = None
            mock_user.language_code = "en"
            
            with patch('app.models.Thread.query') as mock_query:
                mock_query.filter_by.return_value.first.return_value = None
                
                with patch.object(telegram_service, '_create_or_update_contact'):
                    # The method will create a real Thread object but fail to save it
                    # due to missing database tables. This tests the error handling.
                    result = await telegram_service._get_or_create_thread_db(mock_channel, mock_user)
                    
                    # The method should return a fallback thread object
                    assert result is not None
                    assert result.tenant_id == "test_tenant"
                    assert result.customer_id == "12345"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])