"""Signal service for managing Signal integration and message processing."""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from flask import current_app
from app.channels.signal_bot import SignalBotHandler, SignalCLIManager, get_signal_bot_handler, get_signal_cli_manager
from app.models import Channel, InboxMessage, Thread, Tenant, User
from app.utils.database import db
import structlog

logger = structlog.get_logger()


class SignalService:
    """Service for managing Signal integration."""
    
    def __init__(self):
        self.bot_handler = None
        self.cli_manager = None
        self.is_initialized = False
        self.polling_task = None
        
    def initialize(self, phone_number: str = None, signal_cli_path: str = None):
        """Initialize Signal service."""
        try:
            self.bot_handler = get_signal_bot_handler(phone_number, signal_cli_path)
            self.cli_manager = get_signal_cli_manager(signal_cli_path)
            self.is_initialized = True
            
            logger.info("Signal service initialized", phone_number=phone_number)
            return True
            
        except Exception as e:
            logger.error("Failed to initialize Signal service", error=str(e))
            return False
    
    async def start_bot(self) -> bool:
        """Start the Signal bot."""
        if not self.is_initialized:
            logger.error("Signal service not initialized")
            return False
        
        try:
            # Initialize bot handler
            if not await self.bot_handler.initialize():
                logger.error("Failed to initialize Signal bot handler")
                return False
            
            # Start polling in background
            self.polling_task = asyncio.create_task(self.bot_handler.start_polling())
            
            logger.info("Signal bot started successfully")
            return True
            
        except Exception as e:
            logger.error("Failed to start Signal bot", error=str(e))
            return False
    
    async def stop_bot(self):
        """Stop the Signal bot."""
        try:
            if self.bot_handler:
                await self.bot_handler.stop_polling()
            
            if self.polling_task:
                self.polling_task.cancel()
                try:
                    await self.polling_task
                except asyncio.CancelledError:
                    pass
                self.polling_task = None
            
            logger.info("Signal bot stopped")
            
        except Exception as e:
            logger.error("Error stopping Signal bot", error=str(e))
    
    async def send_message(self, tenant_id: str, recipient: str, message: str, 
                          attachments: List[str] = None) -> bool:
        """Send a message via Signal."""
        if not self.is_initialized or not self.bot_handler:
            logger.error("Signal service not initialized")
            return False
        
        try:
            # Get tenant's Signal configuration
            channel = self._get_signal_channel(tenant_id)
            if not channel:
                logger.error("No Signal channel configured for tenant", tenant_id=tenant_id)
                return False
            
            # Send message
            success = await self.bot_handler.send_message(recipient, message, attachments)
            
            if success:
                # Store outbound message
                await self._store_outbound_message(
                    tenant_id, channel.id, recipient, message, attachments
                )
                
                logger.info("Signal message sent", 
                           tenant_id=tenant_id, recipient=recipient)
            
            return success
            
        except Exception as e:
            logger.error("Failed to send Signal message", 
                        tenant_id=tenant_id, recipient=recipient, error=str(e))
            return False
    
    async def send_group_message(self, tenant_id: str, group_id: str, message: str,
                                attachments: List[str] = None) -> bool:
        """Send a message to a Signal group."""
        if not self.is_initialized or not self.bot_handler:
            logger.error("Signal service not initialized")
            return False
        
        try:
            # Get tenant's Signal configuration
            channel = self._get_signal_channel(tenant_id)
            if not channel:
                logger.error("No Signal channel configured for tenant", tenant_id=tenant_id)
                return False
            
            # Send group message
            success = await self.bot_handler.send_group_message(group_id, message, attachments)
            
            if success:
                # Store outbound message
                await self._store_outbound_message(
                    tenant_id, channel.id, group_id, message, attachments, is_group=True
                )
                
                logger.info("Signal group message sent", 
                           tenant_id=tenant_id, group_id=group_id)
            
            return success
            
        except Exception as e:
            logger.error("Failed to send Signal group message", 
                        tenant_id=tenant_id, group_id=group_id, error=str(e))
            return False
    
    async def register_phone_number(self, phone_number: str, captcha: str = None) -> bool:
        """Register a phone number with Signal."""
        if not self.cli_manager:
            logger.error("Signal CLI manager not initialized")
            return False
        
        try:
            success = await self.cli_manager.register_phone_number(phone_number, captcha)
            
            if success:
                logger.info("Signal phone number registration initiated", 
                           phone_number=phone_number)
            else:
                logger.error("Signal phone number registration failed", 
                            phone_number=phone_number)
            
            return success
            
        except Exception as e:
            logger.error("Error registering Signal phone number", 
                        phone_number=phone_number, error=str(e))
            return False
    
    async def verify_phone_number(self, phone_number: str, verification_code: str) -> bool:
        """Verify a phone number with SMS code."""
        if not self.cli_manager:
            logger.error("Signal CLI manager not initialized")
            return False
        
        try:
            success = await self.cli_manager.verify_phone_number(phone_number, verification_code)
            
            if success:
                logger.info("Signal phone number verified successfully", 
                           phone_number=phone_number)
            else:
                logger.error("Signal phone number verification failed", 
                            phone_number=phone_number)
            
            return success
            
        except Exception as e:
            logger.error("Error verifying Signal phone number", 
                        phone_number=phone_number, error=str(e))
            return False
    
    async def link_device(self, phone_number: str) -> Optional[str]:
        """Link a device and return linking URI."""
        if not self.cli_manager:
            logger.error("Signal CLI manager not initialized")
            return None
        
        try:
            linking_uri = await self.cli_manager.link_device(phone_number)
            
            if linking_uri:
                logger.info("Signal device linking initiated", 
                           phone_number=phone_number)
            else:
                logger.error("Signal device linking failed", 
                            phone_number=phone_number)
            
            return linking_uri
            
        except Exception as e:
            logger.error("Error linking Signal device", 
                        phone_number=phone_number, error=str(e))
            return None
    
    async def get_registered_accounts(self) -> List[str]:
        """Get list of registered Signal accounts."""
        if not self.cli_manager:
            logger.error("Signal CLI manager not initialized")
            return []
        
        try:
            accounts = await self.cli_manager.list_accounts()
            logger.info("Retrieved Signal accounts", count=len(accounts))
            return accounts
            
        except Exception as e:
            logger.error("Error getting Signal accounts", error=str(e))
            return []
    
    def create_channel(self, tenant_id: str, phone_number: str, name: str = None) -> Channel:
        """Create a Signal channel for a tenant."""
        try:
            channel = Channel(
                tenant_id=tenant_id,
                name=name or f"Signal ({phone_number})",
                type="signal",
                config={
                    "phone_number": phone_number,
                    "enabled": True,
                    "auto_response": True,
                    "polling_interval": 2
                },
                is_active=True
            )
            
            db.session.add(channel)
            db.session.commit()
            
            logger.info("Signal channel created", 
                       tenant_id=tenant_id, channel_id=channel.id, phone_number=phone_number)
            
            return channel
            
        except Exception as e:
            logger.error("Failed to create Signal channel", 
                        tenant_id=tenant_id, phone_number=phone_number, error=str(e))
            db.session.rollback()
            raise
    
    def update_channel_config(self, channel_id: int, config: Dict[str, Any]) -> bool:
        """Update Signal channel configuration."""
        try:
            channel = Channel.query.filter_by(id=channel_id, type="signal").first()
            if not channel:
                logger.error("Signal channel not found", channel_id=channel_id)
                return False
            
            # Update configuration
            current_config = channel.config or {}
            current_config.update(config)
            channel.config = current_config
            
            db.session.commit()
            
            logger.info("Signal channel configuration updated", 
                       channel_id=channel_id, config=config)
            
            return True
            
        except Exception as e:
            logger.error("Failed to update Signal channel configuration", 
                        channel_id=channel_id, error=str(e))
            db.session.rollback()
            return False
    
    def get_channel_status(self, channel_id: int) -> Dict[str, Any]:
        """Get Signal channel status."""
        try:
            channel = Channel.query.filter_by(id=channel_id, type="signal").first()
            if not channel:
                return {"error": "Channel not found"}
            
            # Check if bot is running
            bot_status = "running" if (self.is_initialized and self.polling_task and not self.polling_task.done()) else "stopped"
            
            # Get recent message statistics
            recent_messages = InboxMessage.query.filter_by(
                channel_id=channel_id
            ).filter(
                InboxMessage.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).count()
            
            return {
                "channel_id": channel_id,
                "channel_name": channel.name,
                "phone_number": channel.config.get("phone_number"),
                "is_active": channel.is_active,
                "bot_status": bot_status,
                "recent_messages_24h": recent_messages,
                "configuration": channel.config
            }
            
        except Exception as e:
            logger.error("Failed to get Signal channel status", 
                        channel_id=channel_id, error=str(e))
            return {"error": str(e)}
    
    def _get_signal_channel(self, tenant_id: str) -> Optional[Channel]:
        """Get Signal channel for tenant."""
        try:
            return Channel.query.filter_by(
                tenant_id=tenant_id,
                type="signal",
                is_active=True
            ).first()
        except Exception as e:
            logger.error("Failed to get Signal channel", 
                        tenant_id=tenant_id, error=str(e))
            return None
    
    async def _store_outbound_message(self, tenant_id: str, channel_id: int, 
                                    recipient: str, content: str, 
                                    attachments: List[str] = None, is_group: bool = False):
        """Store outbound message in database."""
        try:
            # Get or create thread
            thread = Thread.query.filter_by(
                tenant_id=tenant_id,
                channel_id=channel_id,
                customer_id=recipient
            ).first()
            
            if not thread:
                thread = Thread(
                    tenant_id=tenant_id,
                    channel_id=channel_id,
                    customer_id=recipient,
                    subject=f"Signal {'Group' if is_group else 'Chat'} with {recipient}",
                    status="active"
                )
                db.session.add(thread)
                db.session.flush()
            
            # Create message
            message = InboxMessage(
                tenant_id=tenant_id,
                channel_id=channel_id,
                thread_id=thread.id,
                sender_id=None,  # System/bot message
                content=content,
                message_type="text",
                direction="outbound",
                status="sent",
                metadata={
                    "signal_recipient": recipient,
                    "is_group": is_group,
                    "attachments_count": len(attachments) if attachments else 0
                }
            )
            
            db.session.add(message)
            db.session.commit()
            
            logger.info("Outbound Signal message stored", 
                       tenant_id=tenant_id, message_id=message.id)
            
        except Exception as e:
            logger.error("Failed to store outbound Signal message", 
                        tenant_id=tenant_id, recipient=recipient, error=str(e))
            db.session.rollback()


# Global service instance
signal_service = SignalService()


def init_signal_service(app):
    """Initialize Signal service with Flask app."""
    try:
        phone_number = app.config.get('SIGNAL_PHONE_NUMBER')
        signal_cli_path = app.config.get('SIGNAL_CLI_PATH')
        
        if phone_number:
            success = signal_service.initialize(phone_number, signal_cli_path)
            if success:
                logger.info("Signal service initialized successfully")
            else:
                logger.warning("Signal service initialization failed")
        else:
            logger.info("Signal phone number not configured, skipping initialization")
        
        return signal_service
        
    except Exception as e:
        logger.error("Failed to initialize Signal service", error=str(e))
        return None


def get_signal_service() -> SignalService:
    """Get Signal service instance."""
    return signal_service