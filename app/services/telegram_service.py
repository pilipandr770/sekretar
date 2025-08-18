"""Telegram service for managing bot instances and database integration."""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

from app.models import Channel, InboxMessage, Thread, Attachment, Tenant, Contact
from app.channels.telegram_bot import TelegramBotHandler, get_telegram_bot_handler
from app.secretary.agents.orchestrator import AgentOrchestrator
from app.secretary.agents.base_agent import AgentContext, AgentResponse
from app.utils.database import db
from flask import current_app


class TelegramService:
    """Service for managing Telegram bot operations and database integration."""
    
    def __init__(self):
        self.logger = logging.getLogger("telegram.service")
        self.bot_handlers: Dict[str, TelegramBotHandler] = {}
        self.orchestrator = AgentOrchestrator()
    
    async def initialize_tenant_bot(self, tenant_id: str) -> bool:
        """Initialize Telegram bot for a specific tenant."""
        try:
            # Get tenant's Telegram channel
            channel = Channel.query.filter_by(
                tenant_id=tenant_id,
                type='telegram',
                is_active=True
            ).first()
            
            if not channel:
                self.logger.warning(f"No active Telegram channel found for tenant {tenant_id}")
                return False
            
            bot_token = channel.get_config('bot_token')
            webhook_url = channel.get_config('webhook_url')
            
            if not bot_token:
                self.logger.error(f"No bot token configured for tenant {tenant_id}")
                return False
            
            # Create and initialize bot handler
            handler = TelegramBotHandler(bot_token, webhook_url)
            success = await handler.initialize()
            
            if success:
                self.bot_handlers[tenant_id] = handler
                channel.mark_connected()
                self.logger.info(f"Telegram bot initialized for tenant {tenant_id}")
            else:
                channel.mark_disconnected("Failed to initialize bot")
                self.logger.error(f"Failed to initialize Telegram bot for tenant {tenant_id}")
            
            channel.save()
            return success
            
        except Exception as e:
            self.logger.error(f"Error initializing Telegram bot for tenant {tenant_id}: {str(e)}")
            return False
    
    async def process_webhook_update(self, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming webhook update and route to appropriate tenant."""
        try:
            # Extract chat ID to determine tenant
            chat_id = None
            if 'message' in update_data:
                chat_id = update_data['message']['chat']['id']
            elif 'callback_query' in update_data:
                chat_id = update_data['callback_query']['message']['chat']['id']
            
            if not chat_id:
                return {"error": "Could not determine chat ID from update"}
            
            # Find channel by chat configuration
            channel = self._find_channel_by_chat_id(chat_id)
            if not channel:
                self.logger.warning(f"No channel found for chat ID {chat_id}")
                return {"error": "Channel not found"}
            
            # Get or create bot handler for this tenant
            if channel.tenant_id not in self.bot_handlers:
                success = await self.initialize_tenant_bot(channel.tenant_id)
                if not success:
                    return {"error": "Failed to initialize bot"}
            
            handler = self.bot_handlers[channel.tenant_id]
            
            # Process the update with enhanced database integration
            result = await self._process_update_with_db_integration(
                handler, update_data, channel
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing webhook update: {str(e)}")
            return {"error": str(e)}
    
    async def _process_update_with_db_integration(self, handler: TelegramBotHandler, 
                                                update_data: Dict[str, Any], 
                                                channel: Channel) -> Dict[str, Any]:
        """Process update with proper database integration."""
        try:
            # Override handler methods to use actual database operations
            original_store_message = handler._store_message
            original_get_or_create_channel = handler._get_or_create_channel
            original_get_or_create_thread = handler._get_or_create_thread
            
            # Replace with database-integrated methods
            handler._store_message = lambda *args, **kwargs: self._store_message_db(
                channel, *args, **kwargs
            )
            handler._get_or_create_channel = lambda chat: asyncio.create_task(
                asyncio.coroutine(lambda: channel)()
            )
            handler._get_or_create_thread = lambda ch, user: self._get_or_create_thread_db(
                channel, user
            )
            
            # Process the update
            result = await handler.handle_webhook_update(update_data)
            
            # Restore original methods
            handler._store_message = original_store_message
            handler._get_or_create_channel = original_get_or_create_channel
            handler._get_or_create_thread = original_get_or_create_thread
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in database-integrated processing: {str(e)}")
            return {"error": str(e)}
    
    def _find_channel_by_chat_id(self, chat_id: int) -> Optional[Channel]:
        """Find channel by Telegram chat ID."""
        try:
            # Look for channels with this chat_id in their config
            channels = Channel.query.filter_by(type='telegram', is_active=True).all()
            
            for channel in channels:
                config_chat_id = channel.get_config('chat_id')
                if config_chat_id == chat_id:
                    return channel
            
            # If not found, create a default mapping (for development)
            # In production, you'd want stricter channel management
            return Channel.query.filter_by(type='telegram', is_active=True).first()
            
        except Exception as e:
            self.logger.error(f"Error finding channel by chat ID {chat_id}: {str(e)}")
            return None
    
    async def _store_message_db(self, channel: Channel, update, content_type: str, 
                              content: str, direction: str):
        """Store message in database."""
        try:
            # Extract user and chat info from update
            if hasattr(update, 'effective_user') and hasattr(update, 'effective_chat'):
                user = update.effective_user
                chat = update.effective_chat
            else:
                # Handle raw update data
                if 'message' in update:
                    user_data = update['message']['from']
                    chat_data = update['message']['chat']
                else:
                    return
                
                user = type('User', (), user_data)
                chat = type('Chat', (), chat_data)
            
            # Get or create thread
            thread = await self._get_or_create_thread_db(channel, user)
            
            # Create message
            if direction == 'inbound':
                message = InboxMessage.create_inbound(
                    tenant_id=channel.tenant_id,
                    channel_id=channel.id,
                    thread_id=thread.id,
                    sender_id=str(user.id),
                    content=content,
                    content_type=content_type,
                    sender_name=getattr(user, 'first_name', '') + ' ' + getattr(user, 'last_name', ''),
                    extra_data={
                        'telegram_user_id': user.id,
                        'telegram_username': getattr(user, 'username', None),
                        'telegram_chat_id': chat.id,
                        'telegram_chat_type': getattr(chat, 'type', 'private')
                    }
                )
            else:
                message = InboxMessage.create_outbound(
                    tenant_id=channel.tenant_id,
                    channel_id=channel.id,
                    thread_id=thread.id,
                    content=content,
                    content_type=content_type,
                    extra_data={
                        'telegram_chat_id': chat.id,
                        'telegram_chat_type': getattr(chat, 'type', 'private')
                    }
                )
            
            message.save()
            self.logger.info(f"Stored {direction} message: {content[:100]}...")
            
        except Exception as e:
            self.logger.error(f"Error storing message in database: {str(e)}")
    
    async def _get_or_create_thread_db(self, channel: Channel, user) -> Thread:
        """Get or create thread in database."""
        try:
            user_id = str(user.id)
            
            # Look for existing thread
            thread = Thread.query.filter_by(
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                customer_id=user_id,
                status='active'
            ).first()
            
            if thread:
                return thread
            
            # Create new thread
            thread = Thread(
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                customer_id=user_id,
                subject=f"Telegram conversation with {getattr(user, 'first_name', 'User')}",
                status='active',
                extra_data={
                    'telegram_user_id': user.id,
                    'telegram_username': getattr(user, 'username', None),
                    'telegram_first_name': getattr(user, 'first_name', None),
                    'telegram_last_name': getattr(user, 'last_name', None),
                    'telegram_language_code': getattr(user, 'language_code', 'en')
                }
            )
            thread.save()
            
            # Create or update contact
            await self._create_or_update_contact(channel.tenant_id, user, thread)
            
            self.logger.info(f"Created new thread {thread.id} for user {user_id}")
            return thread
            
        except Exception as e:
            self.logger.error(f"Error getting/creating thread: {str(e)}")
            # Return a mock thread to prevent crashes
            return Thread(
                id=1,
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                customer_id=str(user.id),
                subject="Error thread",
                status='active'
            )
    
    async def _create_or_update_contact(self, tenant_id: str, user, thread: Thread):
        """Create or update contact from Telegram user."""
        try:
            # Look for existing contact
            contact = Contact.query.filter_by(
                tenant_id=tenant_id,
                external_id=str(user.id)
            ).first()
            
            if not contact:
                # Create new contact
                contact = Contact(
                    tenant_id=tenant_id,
                    external_id=str(user.id),
                    name=f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip(),
                    source='telegram',
                    extra_data={
                        'telegram_user_id': user.id,
                        'telegram_username': getattr(user, 'username', None),
                        'telegram_first_name': getattr(user, 'first_name', None),
                        'telegram_last_name': getattr(user, 'last_name', None),
                        'telegram_language_code': getattr(user, 'language_code', 'en'),
                        'first_contact_thread_id': thread.id
                    }
                )
                contact.save()
                self.logger.info(f"Created contact for Telegram user {user.id}")
            else:
                # Update existing contact
                contact.extra_data.update({
                    'telegram_first_name': getattr(user, 'first_name', None),
                    'telegram_last_name': getattr(user, 'last_name', None),
                    'telegram_language_code': getattr(user, 'language_code', 'en'),
                    'last_contact_thread_id': thread.id
                })
                contact.save()
                
        except Exception as e:
            self.logger.error(f"Error creating/updating contact: {str(e)}")
    
    async def send_message(self, tenant_id: str, chat_id: int, message: str, 
                         parse_mode: str = 'HTML') -> Dict[str, Any]:
        """Send message via Telegram bot."""
        try:
            # Get bot handler
            if tenant_id not in self.bot_handlers:
                success = await self.initialize_tenant_bot(tenant_id)
                if not success:
                    return {"error": "Bot not initialized"}
            
            handler = self.bot_handlers[tenant_id]
            
            # Send message
            sent_message = await handler.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode
            )
            
            # Update channel statistics
            channel = Channel.query.filter_by(
                tenant_id=tenant_id,
                type='telegram'
            ).first()
            
            if channel:
                channel.increment_sent()
                channel.save()
            
            return {
                "success": True,
                "message_id": sent_message.message_id,
                "chat_id": sent_message.chat_id,
                "date": sent_message.date.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error sending message: {str(e)}")
            return {"error": str(e)}
    
    async def get_bot_info(self, tenant_id: str) -> Dict[str, Any]:
        """Get bot information for a tenant."""
        try:
            if tenant_id not in self.bot_handlers:
                success = await self.initialize_tenant_bot(tenant_id)
                if not success:
                    return {"error": "Bot not initialized"}
            
            handler = self.bot_handlers[tenant_id]
            bot_info = await handler.bot.get_me()
            
            return {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
                "can_join_groups": bot_info.can_join_groups,
                "can_read_all_group_messages": bot_info.can_read_all_group_messages,
                "supports_inline_queries": bot_info.supports_inline_queries
            }
            
        except Exception as e:
            self.logger.error(f"Error getting bot info: {str(e)}")
            return {"error": str(e)}
    
    async def set_webhook(self, tenant_id: str, webhook_url: str = None) -> bool:
        """Set webhook for tenant's bot."""
        try:
            if tenant_id not in self.bot_handlers:
                success = await self.initialize_tenant_bot(tenant_id)
                if not success:
                    return False
            
            handler = self.bot_handlers[tenant_id]
            
            if webhook_url:
                handler.webhook_url = webhook_url
            
            success = await handler.set_webhook()
            
            if success:
                # Update channel config
                channel = Channel.query.filter_by(
                    tenant_id=tenant_id,
                    type='telegram'
                ).first()
                
                if channel:
                    channel.set_config('webhook_url', webhook_url or handler.webhook_url)
                    channel.save()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error setting webhook: {str(e)}")
            return False
    
    async def remove_webhook(self, tenant_id: str) -> bool:
        """Remove webhook for tenant's bot."""
        try:
            if tenant_id not in self.bot_handlers:
                return False
            
            handler = self.bot_handlers[tenant_id]
            success = await handler.remove_webhook()
            
            if success:
                # Update channel config
                channel = Channel.query.filter_by(
                    tenant_id=tenant_id,
                    type='telegram'
                ).first()
                
                if channel:
                    channel.set_config('webhook_url', None)
                    channel.save()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error removing webhook: {str(e)}")
            return False
    
    def get_active_tenants(self) -> List[str]:
        """Get list of tenants with active Telegram channels."""
        try:
            channels = Channel.query.filter_by(
                type='telegram',
                is_active=True
            ).all()
            
            return [channel.tenant_id for channel in channels]
            
        except Exception as e:
            self.logger.error(f"Error getting active tenants: {str(e)}")
            return []
    
    async def initialize_all_tenant_bots(self) -> Dict[str, bool]:
        """Initialize bots for all active tenants."""
        results = {}
        active_tenants = self.get_active_tenants()
        
        for tenant_id in active_tenants:
            try:
                success = await self.initialize_tenant_bot(tenant_id)
                results[tenant_id] = success
            except Exception as e:
                self.logger.error(f"Error initializing bot for tenant {tenant_id}: {str(e)}")
                results[tenant_id] = False
        
        return results


# Global service instance
telegram_service = TelegramService()


def get_telegram_service() -> TelegramService:
    """Get the global Telegram service instance."""
    return telegram_service