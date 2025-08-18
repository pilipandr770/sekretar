"""Telegram Bot integration for AI Secretary."""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

import telegram
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode
from flask import current_app, request, jsonify

from app.models import Channel, InboxMessage, Thread, Attachment, Tenant
from app.secretary.agents.orchestrator import AgentOrchestrator
from app.secretary.agents.base_agent import AgentContext
from app.utils.database import db


class TelegramBotHandler:
    """Telegram Bot handler for processing messages and managing bot interactions."""
    
    def __init__(self, bot_token: str, webhook_url: str = None):
        self.bot_token = bot_token
        self.webhook_url = webhook_url
        self.bot = Bot(token=bot_token)
        self.application = None
        self.orchestrator = AgentOrchestrator()
        self.logger = logging.getLogger("telegram.bot")
        
        # Bot configuration
        self.max_message_length = 4096  # Telegram's limit
        self.supported_file_types = {
            'photo', 'document', 'audio', 'video', 'voice', 'video_note', 'sticker'
        }
        
    async def initialize(self):
        """Initialize the Telegram bot application."""
        try:
            self.application = Application.builder().token(self.bot_token).build()
            
            # Add handlers
            self.application.add_handler(CommandHandler("start", self.handle_start_command))
            self.application.add_handler(CommandHandler("help", self.handle_help_command))
            self.application.add_handler(CommandHandler("status", self.handle_status_command))
            self.application.add_handler(CommandHandler("menu", self.handle_menu_command))
            
            # Message handlers
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
            self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo_message))
            self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document_message))
            self.application.add_handler(MessageHandler(filters.AUDIO, self.handle_audio_message))
            self.application.add_handler(MessageHandler(filters.VIDEO, self.handle_video_message))
            self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice_message))
            
            # Callback query handler for inline keyboards
            self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))
            
            # Set webhook if URL provided
            if self.webhook_url:
                await self.set_webhook()
                
            self.logger.info("Telegram bot initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {str(e)}")
            return False
    
    async def set_webhook(self):
        """Set webhook for receiving updates."""
        try:
            webhook_url = urljoin(self.webhook_url, f"/api/v1/channels/telegram/webhook")
            await self.bot.set_webhook(url=webhook_url)
            self.logger.info(f"Webhook set to: {webhook_url}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set webhook: {str(e)}")
            return False
    
    async def remove_webhook(self):
        """Remove webhook."""
        try:
            await self.bot.delete_webhook()
            self.logger.info("Webhook removed")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove webhook: {str(e)}")
            return False
    
    async def handle_webhook_update(self, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming webhook update."""
        try:
            update = Update.de_json(update_data, self.bot)
            if not update:
                return {"error": "Invalid update data"}
            
            # Process the update
            await self.application.process_update(update)
            
            return {"status": "success", "processed": True}
            
        except Exception as e:
            self.logger.error(f"Error processing webhook update: {str(e)}")
            return {"error": str(e)}
    
    async def handle_start_command(self, update: Update, context):
        """Handle /start command."""
        try:
            user = update.effective_user
            chat = update.effective_chat
            
            welcome_message = (
                f"👋 Hello {user.first_name}!\n\n"
                "Welcome to AI Secretary! I'm here to help you with:\n"
                "• 💬 General inquiries and support\n"
                "• 🛒 Sales and product information\n"
                "• 💳 Billing and subscription questions\n"
                "• 📅 Appointment scheduling\n\n"
                "Just send me a message and I'll assist you right away!\n\n"
                "Use /help to see available commands or /menu for quick actions."
            )
            
            # Create inline keyboard with quick actions
            keyboard = [
                [InlineKeyboardButton("📞 Contact Sales", callback_data="contact_sales")],
                [InlineKeyboardButton("🆘 Get Support", callback_data="get_support")],
                [InlineKeyboardButton("📅 Book Meeting", callback_data="book_meeting")],
                [InlineKeyboardButton("ℹ️ Help", callback_data="show_help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            
            # Store this interaction
            await self._store_message(update, "start_command", welcome_message, direction="outbound")
            
        except Exception as e:
            self.logger.error(f"Error handling start command: {str(e)}")
            await self._send_error_message(update, "Sorry, I encountered an error. Please try again.")
    
    async def handle_help_command(self, update: Update, context):
        """Handle /help command."""
        try:
            help_message = (
                "🤖 <b>AI Secretary Help</b>\n\n"
                "<b>Available Commands:</b>\n"
                "• /start - Welcome message and quick actions\n"
                "• /help - Show this help message\n"
                "• /status - Check bot status\n"
                "• /menu - Show quick action menu\n\n"
                "<b>What I can help with:</b>\n"
                "• Answer questions about our products and services\n"
                "• Help with technical support issues\n"
                "• Assist with billing and subscription questions\n"
                "• Schedule appointments and meetings\n"
                "• Process general inquiries\n\n"
                "<b>File Support:</b>\n"
                "• Send images, documents, audio, and video files\n"
                "• I can analyze and help with file content\n\n"
                "Just send me a message and I'll do my best to help! 😊"
            )
            
            await update.message.reply_text(help_message, parse_mode=ParseMode.HTML)
            await self._store_message(update, "help_command", help_message, direction="outbound")
            
        except Exception as e:
            self.logger.error(f"Error handling help command: {str(e)}")
            await self._send_error_message(update, "Sorry, I couldn't show the help message.")
    
    async def handle_status_command(self, update: Update, context):
        """Handle /status command."""
        try:
            status_message = (
                "🟢 <b>Bot Status: Online</b>\n\n"
                f"• Bot ID: @{self.bot.username}\n"
                f"• Server Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                "• AI Agents: Active\n"
                "• Response Time: Fast\n\n"
                "All systems operational! 🚀"
            )
            
            await update.message.reply_text(status_message, parse_mode=ParseMode.HTML)
            await self._store_message(update, "status_command", status_message, direction="outbound")
            
        except Exception as e:
            self.logger.error(f"Error handling status command: {str(e)}")
            await self._send_error_message(update, "Sorry, I couldn't check the status.")
    
    async def handle_menu_command(self, update: Update, context):
        """Handle /menu command."""
        try:
            menu_message = "🎯 <b>Quick Actions Menu</b>\n\nChoose an option below:"
            
            keyboard = [
                [InlineKeyboardButton("💬 General Inquiry", callback_data="general_inquiry")],
                [InlineKeyboardButton("🛒 Sales Question", callback_data="sales_question")],
                [InlineKeyboardButton("🆘 Technical Support", callback_data="tech_support")],
                [InlineKeyboardButton("💳 Billing Help", callback_data="billing_help")],
                [InlineKeyboardButton("📅 Schedule Meeting", callback_data="schedule_meeting")],
                [InlineKeyboardButton("👤 Speak to Human", callback_data="human_handoff")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                menu_message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            
            await self._store_message(update, "menu_command", menu_message, direction="outbound")
            
        except Exception as e:
            self.logger.error(f"Error handling menu command: {str(e)}")
            await self._send_error_message(update, "Sorry, I couldn't show the menu.")
    
    async def handle_text_message(self, update: Update, context):
        """Handle regular text messages."""
        try:
            user = update.effective_user
            message_text = update.message.text
            
            # Store incoming message
            await self._store_message(update, "text", message_text, direction="inbound")
            
            # Show typing indicator
            await update.effective_chat.send_action(action="typing")
            
            # Process message through AI orchestrator
            agent_context = await self._create_agent_context(update)
            response = await self.orchestrator.process_message(message_text, agent_context)
            
            # Send AI response
            await self._send_ai_response(update, response)
            
        except Exception as e:
            self.logger.error(f"Error handling text message: {str(e)}")
            await self._send_error_message(update, "Sorry, I encountered an error processing your message.")
    
    async def handle_photo_message(self, update: Update, context):
        """Handle photo messages."""
        try:
            photo = update.message.photo[-1]  # Get highest resolution
            caption = update.message.caption or ""
            
            # Download photo
            file_info = await photo.get_file()
            file_data = await file_info.download_as_bytearray()
            
            # Store message with attachment
            await self._store_message_with_attachment(
                update, "photo", caption, file_data, 
                filename=f"photo_{photo.file_id}.jpg",
                mime_type="image/jpeg"
            )
            
            # Process through AI
            message_text = f"[Photo uploaded] {caption}".strip()
            agent_context = await self._create_agent_context(update)
            response = await self.orchestrator.process_message(message_text, agent_context)
            
            await self._send_ai_response(update, response)
            
        except Exception as e:
            self.logger.error(f"Error handling photo message: {str(e)}")
            await self._send_error_message(update, "Sorry, I couldn't process your photo.")
    
    async def handle_document_message(self, update: Update, context):
        """Handle document messages."""
        try:
            document = update.message.document
            caption = update.message.caption or ""
            
            # Check file size (limit to 20MB)
            if document.file_size > 20 * 1024 * 1024:
                await update.message.reply_text(
                    "📄 File too large! Please send files smaller than 20MB."
                )
                return
            
            # Download document
            file_info = await document.get_file()
            file_data = await file_info.download_as_bytearray()
            
            # Store message with attachment
            await self._store_message_with_attachment(
                update, "document", caption, file_data,
                filename=document.file_name,
                mime_type=document.mime_type
            )
            
            # Process through AI
            message_text = f"[Document uploaded: {document.file_name}] {caption}".strip()
            agent_context = await self._create_agent_context(update)
            response = await self.orchestrator.process_message(message_text, agent_context)
            
            await self._send_ai_response(update, response)
            
        except Exception as e:
            self.logger.error(f"Error handling document message: {str(e)}")
            await self._send_error_message(update, "Sorry, I couldn't process your document.")
    
    async def handle_audio_message(self, update: Update, context):
        """Handle audio messages."""
        try:
            audio = update.message.audio
            caption = update.message.caption or ""
            
            # Store message (don't download large audio files by default)
            await self._store_message(
                update, "audio", 
                f"[Audio file: {audio.file_name or 'audio.mp3'}] {caption}".strip(),
                direction="inbound"
            )
            
            # Process through AI
            message_text = f"[Audio message received] {caption}".strip()
            agent_context = await self._create_agent_context(update)
            response = await self.orchestrator.process_message(message_text, agent_context)
            
            await self._send_ai_response(update, response)
            
        except Exception as e:
            self.logger.error(f"Error handling audio message: {str(e)}")
            await self._send_error_message(update, "Sorry, I couldn't process your audio message.")
    
    async def handle_video_message(self, update: Update, context):
        """Handle video messages."""
        try:
            video = update.message.video
            caption = update.message.caption or ""
            
            # Store message (don't download large video files by default)
            await self._store_message(
                update, "video",
                f"[Video file: {video.file_name or 'video.mp4'}] {caption}".strip(),
                direction="inbound"
            )
            
            # Process through AI
            message_text = f"[Video message received] {caption}".strip()
            agent_context = await self._create_agent_context(update)
            response = await self.orchestrator.process_message(message_text, agent_context)
            
            await self._send_ai_response(update, response)
            
        except Exception as e:
            self.logger.error(f"Error handling video message: {str(e)}")
            await self._send_error_message(update, "Sorry, I couldn't process your video message.")
    
    async def handle_voice_message(self, update: Update, context):
        """Handle voice messages."""
        try:
            voice = update.message.voice
            
            # Store message
            await self._store_message(
                update, "voice", "[Voice message received]", direction="inbound"
            )
            
            # Process through AI
            agent_context = await self._create_agent_context(update)
            response = await self.orchestrator.process_message(
                "[Voice message received - audio transcription not yet implemented]", 
                agent_context
            )
            
            await self._send_ai_response(update, response)
            
        except Exception as e:
            self.logger.error(f"Error handling voice message: {str(e)}")
            await self._send_error_message(update, "Sorry, I couldn't process your voice message.")
    
    async def handle_callback_query(self, update: Update, context):
        """Handle inline keyboard button presses."""
        try:
            query = update.callback_query
            await query.answer()  # Acknowledge the callback
            
            callback_data = query.data
            user = update.effective_user
            
            # Handle different callback actions
            response_text = ""
            
            if callback_data == "contact_sales":
                response_text = (
                    "🛒 <b>Sales Inquiry</b>\n\n"
                    "I'd be happy to help you with sales questions! "
                    "Please tell me what you're interested in learning about our products or services."
                )
            elif callback_data == "get_support":
                response_text = (
                    "🆘 <b>Technical Support</b>\n\n"
                    "I'm here to help with any technical issues! "
                    "Please describe the problem you're experiencing and I'll do my best to assist you."
                )
            elif callback_data == "book_meeting":
                response_text = (
                    "📅 <b>Meeting Scheduling</b>\n\n"
                    "I can help you schedule a meeting! "
                    "Please let me know your preferred date, time, and the purpose of the meeting."
                )
            elif callback_data == "show_help":
                response_text = (
                    "ℹ️ <b>Help & Information</b>\n\n"
                    "I'm an AI assistant that can help you with various tasks. "
                    "Just send me a message describing what you need help with!"
                )
            elif callback_data in ["general_inquiry", "sales_question", "tech_support", "billing_help", "schedule_meeting"]:
                intent_map = {
                    "general_inquiry": "I'm ready to help with your general inquiry!",
                    "sales_question": "I'm ready to answer your sales questions!",
                    "tech_support": "I'm ready to provide technical support!",
                    "billing_help": "I'm ready to help with billing questions!",
                    "schedule_meeting": "I'm ready to help schedule your meeting!"
                }
                response_text = f"✅ {intent_map[callback_data]} Please tell me more about what you need."
            elif callback_data == "human_handoff":
                response_text = (
                    "👤 <b>Human Agent Request</b>\n\n"
                    "I understand you'd like to speak with a human agent. "
                    "Let me connect you with someone who can provide personalized assistance. "
                    "Please briefly describe your inquiry so I can route you to the right person."
                )
            
            # Send response
            if response_text:
                await query.edit_message_text(
                    text=response_text,
                    parse_mode=ParseMode.HTML
                )
                
                # Store the interaction
                await self._store_callback_interaction(update, callback_data, response_text)
            
        except Exception as e:
            self.logger.error(f"Error handling callback query: {str(e)}")
            await query.edit_message_text("Sorry, I encountered an error. Please try again.")
    
    async def _create_agent_context(self, update: Update) -> AgentContext:
        """Create agent context from Telegram update."""
        user = update.effective_user
        chat = update.effective_chat
        
        # Get or create channel and thread
        channel = await self._get_or_create_channel(chat)
        thread = await self._get_or_create_thread(channel, user)
        
        return AgentContext(
            tenant_id=channel.tenant_id,
            user_id=str(user.id),
            channel_type="telegram",
            conversation_id=str(thread.id),
            customer_id=str(user.id),
            language="en",  # TODO: Detect language
            metadata={
                "telegram_user": {
                    "id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "language_code": user.language_code
                },
                "telegram_chat": {
                    "id": chat.id,
                    "type": chat.type,
                    "title": getattr(chat, 'title', None)
                },
                "channel_id": str(chat.id)  # Move channel_id to metadata
            }
        )
    
    async def _send_ai_response(self, update: Update, response):
        """Send AI response to Telegram."""
        try:
            if not response or not response.content:
                await self._send_error_message(update, "I'm sorry, I couldn't generate a response.")
                return
            
            # Split long messages
            messages = self._split_long_message(response.content)
            
            for message in messages:
                # Add inline keyboard if handoff is required
                reply_markup = None
                if response.requires_handoff:
                    keyboard = [[InlineKeyboardButton("👤 Connect to Human", callback_data="human_handoff")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                
                sent_message = await update.effective_chat.send_message(
                    text=message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
                
                # Store outbound message
                await self._store_message(update, "ai_response", message, direction="outbound")
            
        except Exception as e:
            self.logger.error(f"Error sending AI response: {str(e)}")
            await self._send_error_message(update, "Sorry, I encountered an error sending my response.")
    
    async def _send_error_message(self, update: Update, error_text: str):
        """Send error message to user."""
        try:
            await update.effective_chat.send_message(
                text=f"❌ {error_text}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            self.logger.error(f"Error sending error message: {str(e)}")
    
    def _split_long_message(self, text: str) -> List[str]:
        """Split long messages to fit Telegram's limits."""
        if len(text) <= self.max_message_length:
            return [text]
        
        messages = []
        current_message = ""
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            # Check if adding this paragraph would exceed the limit
            if current_message and len(current_message + '\n\n' + paragraph) > self.max_message_length:
                # Save current message and start new one
                messages.append(current_message.strip())
                current_message = ""
            
            # If single paragraph is too long, split by sentences
            if len(paragraph) > self.max_message_length:
                sentences = paragraph.split('. ')
                for sentence in sentences:
                    sentence_with_period = sentence + '. ' if not sentence.endswith('.') else sentence + ' '
                    
                    # Check if adding this sentence would exceed the limit
                    if current_message and len(current_message + sentence_with_period) > self.max_message_length:
                        messages.append(current_message.strip())
                        current_message = ""
                    
                    # If single sentence is still too long, split by characters
                    if len(sentence_with_period) > self.max_message_length:
                        # Split very long sentences by chunks
                        for i in range(0, len(sentence_with_period), self.max_message_length):
                            chunk = sentence_with_period[i:i + self.max_message_length]
                            if current_message and len(current_message + chunk) > self.max_message_length:
                                messages.append(current_message.strip())
                                current_message = chunk
                            else:
                                current_message += chunk
                    else:
                        current_message += sentence_with_period
            else:
                # Add paragraph to current message
                if current_message:
                    current_message += '\n\n' + paragraph
                else:
                    current_message = paragraph
        
        # Add any remaining content
        if current_message:
            messages.append(current_message.strip())
        
        # Ensure we have at least one message
        if not messages:
            messages = [text[:self.max_message_length]]
        
        return messages
    
    async def _get_or_create_channel(self, chat) -> Channel:
        """Get or create Telegram channel for the chat."""
        # For now, return a mock channel - this should integrate with the actual channel system
        # In a real implementation, you'd look up the channel by chat ID and tenant
        return Channel(
            id=1,
            tenant_id="default",
            name=f"Telegram Chat {chat.id}",
            type="telegram",
            config={"chat_id": chat.id}
        )
    
    async def _get_or_create_thread(self, channel: Channel, user) -> Thread:
        """Get or create thread for the user."""
        # For now, return a mock thread - this should integrate with the actual thread system
        return Thread(
            id=1,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            customer_id=str(user.id),
            subject=f"Conversation with {user.first_name or user.username}",
            status="active"
        )
    
    async def _store_message(self, update: Update, content_type: str, content: str, direction: str):
        """Store message in the database."""
        try:
            # This is a simplified version - in production, you'd properly integrate with the database
            self.logger.info(f"Storing {direction} message: {content_type} - {content[:100]}...")
        except Exception as e:
            self.logger.error(f"Error storing message: {str(e)}")
    
    async def _store_message_with_attachment(self, update: Update, content_type: str, 
                                           content: str, file_data: bytes, 
                                           filename: str, mime_type: str):
        """Store message with attachment."""
        try:
            # Store the file and create attachment record
            self.logger.info(f"Storing message with attachment: {filename} ({len(file_data)} bytes)")
            # In production, save file to storage and create Attachment record
        except Exception as e:
            self.logger.error(f"Error storing message with attachment: {str(e)}")
    
    async def _store_callback_interaction(self, update: Update, callback_data: str, response_text: str):
        """Store callback query interaction."""
        try:
            self.logger.info(f"Storing callback interaction: {callback_data}")
        except Exception as e:
            self.logger.error(f"Error storing callback interaction: {str(e)}")


# Global bot handler instance
telegram_bot_handler = None


def get_telegram_bot_handler(bot_token: str = None, webhook_url: str = None) -> TelegramBotHandler:
    """Get or create Telegram bot handler instance."""
    global telegram_bot_handler
    
    if telegram_bot_handler is None:
        if not bot_token:
            bot_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
        if not webhook_url:
            webhook_url = current_app.config.get('TELEGRAM_WEBHOOK_URL')
            
        if not bot_token:
            raise ValueError("Telegram bot token is required")
            
        telegram_bot_handler = TelegramBotHandler(bot_token, webhook_url)
    
    return telegram_bot_handler


async def initialize_telegram_bot() -> bool:
    """Initialize the Telegram bot."""
    try:
        handler = get_telegram_bot_handler()
        return await handler.initialize()
    except Exception as e:
        logging.getLogger("telegram.bot").error(f"Failed to initialize Telegram bot: {str(e)}")
        return False