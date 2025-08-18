#!/usr/bin/env python3
"""Basic test script for Telegram bot functionality."""

import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.channels.telegram_bot import TelegramBotHandler
from app.secretary.agents.base_agent import AgentContext, AgentResponse


async def test_telegram_bot_basic():
    """Test basic Telegram bot functionality."""
    print("🤖 Testing Telegram Bot Integration...")
    
    # Create Flask app context
    app = create_app('testing')
    
    with app.app_context():
        # Test 1: Bot Handler Initialization
        print("\n1. Testing bot handler initialization...")
        try:
            handler = TelegramBotHandler("test_token_123456:ABC-DEF")
            print("✅ Bot handler created successfully")
            print(f"   - Bot token: {handler.bot_token[:20]}...")
            print(f"   - Max message length: {handler.max_message_length}")
            print(f"   - Supported file types: {len(handler.supported_file_types)}")
        except Exception as e:
            print(f"❌ Failed to create bot handler: {e}")
            return False
        
        # Test 2: Message Splitting
        print("\n2. Testing message splitting...")
        try:
            short_message = "This is a short message."
            long_message = "A" * 5000  # Longer than Telegram's limit
            
            short_result = handler._split_long_message(short_message)
            long_result = handler._split_long_message(long_message)
            
            assert len(short_result) == 1, f"Expected 1 message, got {len(short_result)}"
            assert len(long_result) > 1, f"Expected multiple messages, got {len(long_result)}"
            assert all(len(msg) <= handler.max_message_length for msg in long_result), "Some messages exceed limit"
            
            print("✅ Message splitting works correctly")
            print(f"   - Short message: {len(short_result)} part(s)")
            print(f"   - Long message: {len(long_result)} part(s)")
        except Exception as e:
            print(f"❌ Message splitting failed: {e}")
            return False
        
        # Test 3: Mock Command Handling
        print("\n3. Testing command handling...")
        try:
            # Create mock update
            mock_update = Mock()
            mock_update.effective_user = Mock()
            mock_update.effective_user.id = 12345
            mock_update.effective_user.username = "testuser"
            mock_update.effective_user.first_name = "Test"
            mock_update.effective_user.last_name = "User"
            mock_update.effective_user.language_code = "en"
            
            mock_update.effective_chat = Mock()
            mock_update.effective_chat.id = 67890
            mock_update.effective_chat.type = "private"
            mock_update.effective_chat.send_action = AsyncMock()
            
            mock_update.message = Mock()
            mock_update.message.text = "/start"
            mock_update.message.message_id = 1
            mock_update.message.reply_text = AsyncMock()
            
            # Mock the store_message method
            handler._store_message = AsyncMock()
            
            # Test /start command
            await handler.handle_start_command(mock_update, None)
            
            # Verify message was sent
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            
            # Check message content
            if call_args[0]:
                message_text = call_args[0][0]
            else:
                message_text = call_args[1]['text']
            
            assert "Welcome to AI Secretary" in message_text, "Welcome message not found"
            
            print("✅ Command handling works correctly")
            print(f"   - Start command processed successfully")
            print(f"   - Message stored: {handler._store_message.called}")
        except Exception as e:
            print(f"❌ Command handling failed: {e}")
            return False
        
        # Test 4: Agent Context Creation
        print("\n4. Testing agent context creation...")
        try:
            # Mock channel and thread
            mock_channel = Mock()
            mock_channel.id = 1
            mock_channel.tenant_id = "test_tenant"
            mock_channel.name = "Test Channel"
            mock_channel.type = "telegram"
            
            mock_thread = Mock()
            mock_thread.id = 1
            mock_thread.tenant_id = "test_tenant"
            mock_thread.channel_id = 1
            mock_thread.customer_id = "12345"
            
            # Mock the methods
            handler._get_or_create_channel = AsyncMock(return_value=mock_channel)
            handler._get_or_create_thread = AsyncMock(return_value=mock_thread)
            
            # Create agent context
            context = await handler._create_agent_context(mock_update)
            
            assert context.tenant_id == "test_tenant", f"Expected test_tenant, got {context.tenant_id}"
            assert context.user_id == "12345", f"Expected 12345, got {context.user_id}"
            assert context.channel_type == "telegram", f"Expected telegram, got {context.channel_type}"
            assert context.conversation_id == "1", f"Expected 1, got {context.conversation_id}"
            assert context.customer_id == "12345", f"Expected 12345, got {context.customer_id}"
            
            print("✅ Agent context creation works correctly")
            print(f"   - Tenant ID: {context.tenant_id}")
            print(f"   - User ID: {context.user_id}")
            print(f"   - Channel type: {context.channel_type}")
            print(f"   - Conversation ID: {context.conversation_id}")
        except Exception as e:
            print(f"❌ Agent context creation failed: {e}")
            return False
        
        # Test 5: Webhook Update Processing
        print("\n5. Testing webhook update processing...")
        try:
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
            
            # Mock the application processing
            handler.application = Mock()
            handler.application.process_update = AsyncMock()
            
            # Mock the Update.de_json method to avoid Telegram object creation issues
            from unittest.mock import patch
            with patch('telegram.Update.de_json') as mock_de_json:
                mock_update_obj = Mock()
                mock_de_json.return_value = mock_update_obj
                
                result = await handler.handle_webhook_update(update_data)
            
            assert result["status"] == "success", f"Expected success, got {result.get('status')}"
            assert result["processed"] is True, f"Expected True, got {result.get('processed')}"
            
            print("✅ Webhook update processing works correctly")
            print(f"   - Status: {result['status']}")
            print(f"   - Processed: {result['processed']}")
        except Exception as e:
            print(f"❌ Webhook update processing failed: {e}")
            return False
        
        print("\n🎉 All Telegram bot tests passed successfully!")
        print("\n📋 Summary:")
        print("   ✅ Bot handler initialization")
        print("   ✅ Message splitting")
        print("   ✅ Command handling (/start)")
        print("   ✅ Agent context creation")
        print("   ✅ Webhook update processing")
        
        return True


async def main():
    """Main test function."""
    print("=" * 60)
    print("🚀 Telegram Bot Integration Test Suite")
    print("=" * 60)
    
    try:
        success = await test_telegram_bot_basic()
        
        if success:
            print("\n" + "=" * 60)
            print("✅ ALL TESTS PASSED - Telegram integration is working!")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("❌ SOME TESTS FAILED - Check the output above")
            print("=" * 60)
            return 1
            
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)