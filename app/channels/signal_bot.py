"""Signal integration for AI Secretary using signal-cli."""
import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

from flask import current_app

from app.models import Channel, InboxMessage, Thread, Attachment, Tenant
from app.secretary.agents.orchestrator import AgentOrchestrator
from app.secretary.agents.base_agent import AgentContext
from app.utils.database import db


class SignalBotHandler:
    """Signal Bot handler for processing messages using signal-cli."""
    
    def __init__(self, phone_number: str, signal_cli_path: str = None):
        self.phone_number = phone_number
        self.signal_cli_path = signal_cli_path or "signal-cli"
        self.orchestrator = AgentOrchestrator()
        self.logger = logging.getLogger("signal.bot")
        
        # Configuration
        self.max_message_length = 2000  # Signal's practical limit
        self.supported_file_types = {
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'video/mp4', 'video/quicktime', 'video/x-msvideo',
            'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp4',
            'application/pdf', 'text/plain', 'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        
        # State management
        self.is_running = False
        self.polling_interval = 2  # seconds
        self.last_message_timestamp = 0
        
    async def initialize(self):
        """Initialize Signal bot and verify setup."""
        try:
            # Check if signal-cli is available
            if not await self._check_signal_cli():
                raise RuntimeError("signal-cli not found or not working")
            
            # Check if phone number is registered
            if not await self._is_registered():
                self.logger.error(f"Phone number {self.phone_number} is not registered with Signal")
                return False
            
            # Test basic functionality
            if not await self._test_connection():
                self.logger.error("Failed to establish Signal connection")
                return False
            
            self.logger.info(f"Signal bot initialized successfully for {self.phone_number}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Signal bot: {str(e)}")
            return False
    
    async def start_polling(self):
        """Start polling for incoming messages."""
        if self.is_running:
            self.logger.warning("Signal bot is already running")
            return
        
        self.is_running = True
        self.logger.info("Starting Signal message polling...")
        
        try:
            while self.is_running:
                await self._poll_messages()
                await asyncio.sleep(self.polling_interval)
        except Exception as e:
            self.logger.error(f"Error in polling loop: {str(e)}")
        finally:
            self.is_running = False
            self.logger.info("Signal message polling stopped")
    
    async def stop_polling(self):
        """Stop polling for messages."""
        self.is_running = False
        self.logger.info("Stopping Signal message polling...")
    
    async def send_message(self, recipient: str, message: str, attachments: List[str] = None) -> bool:
        """Send a message via Signal."""
        try:
            cmd = [
                self.signal_cli_path,
                "-a", self.phone_number,
                "send",
                "-m", message,
                recipient
            ]
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    if os.path.exists(attachment):
                        cmd.extend(["-a", attachment])
            
            # Execute command
            result = await self._run_signal_command(cmd)
            
            if result.returncode == 0:
                self.logger.info(f"Message sent to {recipient}")
                return True
            else:
                self.logger.error(f"Failed to send message to {recipient}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending message to {recipient}: {str(e)}")
            return False
    
    async def send_group_message(self, group_id: str, message: str, attachments: List[str] = None) -> bool:
        """Send a message to a Signal group."""
        try:
            cmd = [
                self.signal_cli_path,
                "-a", self.phone_number,
                "send",
                "-m", message,
                "-g", group_id
            ]
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    if os.path.exists(attachment):
                        cmd.extend(["-a", attachment])
            
            # Execute command
            result = await self._run_signal_command(cmd)
            
            if result.returncode == 0:
                self.logger.info(f"Message sent to group {group_id}")
                return True
            else:
                self.logger.error(f"Failed to send message to group {group_id}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending group message to {group_id}: {str(e)}")
            return False
    
    async def _poll_messages(self):
        """Poll for new messages."""
        try:
            cmd = [
                self.signal_cli_path,
                "-a", self.phone_number,
                "receive",
                "--json",
                "--ignore-attachments"  # We'll handle attachments separately
            ]
            
            result = await self._run_signal_command(cmd, timeout=10)
            
            if result.returncode == 0 and result.stdout:
                # Parse JSON messages
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            message_data = json.loads(line)
                            await self._process_received_message(message_data)
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"Failed to parse message JSON: {e}")
            
        except Exception as e:
            self.logger.error(f"Error polling messages: {str(e)}")
    
    async def _process_received_message(self, message_data: Dict[str, Any]):
        """Process a received Signal message."""
        try:
            envelope = message_data.get('envelope', {})
            
            # Skip if no data message
            if 'dataMessage' not in envelope:
                return
            
            data_message = envelope['dataMessage']
            source = envelope.get('source', envelope.get('sourceNumber', ''))
            timestamp = envelope.get('timestamp', int(time.time() * 1000))
            
            # Skip old messages
            if timestamp <= self.last_message_timestamp:
                return
            
            self.last_message_timestamp = timestamp
            
            # Extract message content
            message_text = data_message.get('message', '')
            group_info = data_message.get('groupInfo')
            attachments = data_message.get('attachments', [])
            
            # Determine if it's a group message
            is_group = group_info is not None
            group_id = group_info.get('groupId') if is_group else None
            
            # Create context for processing
            context = await self._create_agent_context(source, group_id, is_group)
            
            # Store incoming message
            await self._store_message(
                source, group_id, message_text, attachments, 
                timestamp, direction="inbound", is_group=is_group
            )
            
            # Process through AI if there's text content
            if message_text.strip():
                response = await self.orchestrator.process_message(message_text, context)
                
                # Send AI response
                if response and response.content:
                    await self._send_ai_response(source, group_id, response, is_group)
            
            # Handle attachments
            if attachments:
                await self._process_attachments(source, group_id, attachments, context, is_group)
                
        except Exception as e:
            self.logger.error(f"Error processing received message: {str(e)}")
    
    async def _process_attachments(self, source: str, group_id: str, attachments: List[Dict], 
                                 context: AgentContext, is_group: bool):
        """Process message attachments."""
        try:
            for attachment in attachments:
                content_type = attachment.get('contentType', '')
                filename = attachment.get('filename', 'attachment')
                
                # Download attachment if supported
                if content_type in self.supported_file_types:
                    # Create a message about the attachment
                    attachment_message = f"[Attachment received: {filename} ({content_type})]"
                    
                    # Process through AI
                    response = await self.orchestrator.process_message(attachment_message, context)
                    
                    if response and response.content:
                        await self._send_ai_response(source, group_id, response, is_group)
                else:
                    # Unsupported file type
                    unsupported_message = f"I received a file ({filename}), but I can't process this file type yet."
                    if is_group:
                        await self.send_group_message(group_id, unsupported_message)
                    else:
                        await self.send_message(source, unsupported_message)
                        
        except Exception as e:
            self.logger.error(f"Error processing attachments: {str(e)}")
    
    async def _send_ai_response(self, recipient: str, group_id: str, response, is_group: bool):
        """Send AI response via Signal."""
        try:
            if not response or not response.content:
                error_message = "I'm sorry, I couldn't generate a response."
                if is_group:
                    await self.send_group_message(group_id, error_message)
                else:
                    await self.send_message(recipient, error_message)
                return
            
            # Split long messages
            messages = self._split_long_message(response.content)
            
            for message in messages:
                # Add handoff indicator if needed
                if response.requires_handoff:
                    message += "\n\n🤝 A human agent will contact you shortly for further assistance."
                
                # Send message
                success = False
                if is_group:
                    success = await self.send_group_message(group_id, message)
                else:
                    success = await self.send_message(recipient, message)
                
                if success:
                    # Store outbound message
                    await self._store_message(
                        recipient, group_id, message, [], 
                        int(time.time() * 1000), direction="outbound", is_group=is_group
                    )
                else:
                    self.logger.error("Failed to send AI response")
                    break
            
        except Exception as e:
            self.logger.error(f"Error sending AI response: {str(e)}")
    
    async def _create_agent_context(self, source: str, group_id: str, is_group: bool) -> AgentContext:
        """Create agent context from Signal message."""
        # Get or create channel and thread
        channel = await self._get_or_create_channel(source, group_id, is_group)
        thread = await self._get_or_create_thread(channel, source)
        
        return AgentContext(
            tenant_id=channel.tenant_id,
            user_id=source,
            channel_type="signal",
            conversation_id=str(thread.id),
            customer_id=source,
            language="en",  # TODO: Detect language
            metadata={
                "signal_source": source,
                "signal_group_id": group_id,
                "is_group_message": is_group,
                "channel_id": group_id if is_group else source
            }
        )
    
    def _split_long_message(self, text: str) -> List[str]:
        """Split long messages to fit Signal's limits."""
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
                    
                    if current_message and len(current_message + sentence_with_period) > self.max_message_length:
                        messages.append(current_message.strip())
                        current_message = ""
                    
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
    
    async def _check_signal_cli(self) -> bool:
        """Check if signal-cli is available and working."""
        try:
            result = await self._run_signal_command([self.signal_cli_path, "--version"])
            return result.returncode == 0
        except Exception:
            return False
    
    async def _is_registered(self) -> bool:
        """Check if the phone number is registered with Signal."""
        try:
            cmd = [self.signal_cli_path, "-a", self.phone_number, "listIdentities"]
            result = await self._run_signal_command(cmd)
            return result.returncode == 0
        except Exception:
            return False
    
    async def _test_connection(self) -> bool:
        """Test Signal connection by trying to receive messages."""
        try:
            cmd = [self.signal_cli_path, "-a", self.phone_number, "receive", "--timeout", "1"]
            result = await self._run_signal_command(cmd)
            # Return code 0 or 1 are both acceptable (1 means timeout, which is expected)
            return result.returncode in [0, 1]
        except Exception:
            return False
    
    async def _run_signal_command(self, cmd: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a signal-cli command asynchronously."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
            
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout.decode('utf-8') if stdout else '',
                stderr=stderr.decode('utf-8') if stderr else ''
            )
            
        except asyncio.TimeoutError:
            self.logger.error(f"Signal command timed out: {' '.join(cmd)}")
            raise
        except Exception as e:
            self.logger.error(f"Error running signal command: {str(e)}")
            raise
    
    async def _get_or_create_channel(self, source: str, group_id: str, is_group: bool) -> Channel:
        """Get or create Signal channel."""
        # For now, return a mock channel - this should integrate with the actual channel system
        channel_id = group_id if is_group else source
        channel_name = f"Signal {'Group' if is_group else 'Chat'} {channel_id}"
        
        return Channel(
            id=1,
            tenant_id="default",
            name=channel_name,
            type="signal",
            config={
                "phone_number": self.phone_number,
                "channel_id": channel_id,
                "is_group": is_group,
                "group_id": group_id
            }
        )
    
    async def _get_or_create_thread(self, channel: Channel, source: str) -> Thread:
        """Get or create thread for the conversation."""
        # For now, return a mock thread - this should integrate with the actual thread system
        return Thread(
            id=1,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            customer_id=source,
            subject=f"Signal conversation with {source}",
            status="active"
        )
    
    async def _store_message(self, source: str, group_id: str, content: str, 
                           attachments: List[Dict], timestamp: int, 
                           direction: str, is_group: bool):
        """Store message in the database."""
        try:
            # This is a simplified version - in production, you'd properly integrate with the database
            message_type = "group" if is_group else "direct"
            channel_id = group_id if is_group else source
            
            self.logger.info(
                f"Storing {direction} {message_type} message from {source} "
                f"in channel {channel_id}: {content[:100]}..."
            )
            
            # Store attachments info
            if attachments:
                self.logger.info(f"Message has {len(attachments)} attachments")
                
        except Exception as e:
            self.logger.error(f"Error storing message: {str(e)}")


# Signal CLI management functions
class SignalCLIManager:
    """Manager for Signal CLI operations and setup."""
    
    def __init__(self, signal_cli_path: str = None):
        self.signal_cli_path = signal_cli_path or "signal-cli"
        self.logger = logging.getLogger("signal.cli.manager")
    
    async def register_phone_number(self, phone_number: str, captcha: str = None) -> bool:
        """Register a phone number with Signal."""
        try:
            cmd = [self.signal_cli_path, "-a", phone_number, "register"]
            
            if captcha:
                cmd.extend(["--captcha", captcha])
            
            result = await self._run_command(cmd)
            
            if result.returncode == 0:
                self.logger.info(f"Registration initiated for {phone_number}")
                return True
            else:
                self.logger.error(f"Registration failed for {phone_number}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error registering phone number: {str(e)}")
            return False
    
    async def verify_phone_number(self, phone_number: str, verification_code: str) -> bool:
        """Verify a phone number with the received SMS code."""
        try:
            cmd = [
                self.signal_cli_path, "-a", phone_number, 
                "verify", verification_code
            ]
            
            result = await self._run_command(cmd)
            
            if result.returncode == 0:
                self.logger.info(f"Phone number {phone_number} verified successfully")
                return True
            else:
                self.logger.error(f"Verification failed for {phone_number}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error verifying phone number: {str(e)}")
            return False
    
    async def link_device(self, phone_number: str) -> Optional[str]:
        """Link a device and return the linking URI."""
        try:
            cmd = [self.signal_cli_path, "-a", phone_number, "link"]
            
            result = await self._run_command(cmd)
            
            if result.returncode == 0:
                # Extract linking URI from output
                for line in result.stdout.split('\n'):
                    if 'tsdevice:/?uuid=' in line or 'sgnl://linkdevice?uuid=' in line:
                        return line.strip()
                
                self.logger.warning("Device linking initiated but no URI found in output")
                return result.stdout.strip()
            else:
                self.logger.error(f"Device linking failed: {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error linking device: {str(e)}")
            return None
    
    async def list_accounts(self) -> List[str]:
        """List all registered Signal accounts."""
        try:
            cmd = [self.signal_cli_path, "listAccounts"]
            
            result = await self._run_command(cmd)
            
            if result.returncode == 0:
                accounts = []
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and line.startswith('+'):
                        accounts.append(line)
                return accounts
            else:
                self.logger.error(f"Failed to list accounts: {result.stderr}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error listing accounts: {str(e)}")
            return []
    
    async def _run_command(self, cmd: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
        """Run a signal-cli command."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
            
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout.decode('utf-8') if stdout else '',
                stderr=stderr.decode('utf-8') if stderr else ''
            )
            
        except asyncio.TimeoutError:
            self.logger.error(f"Command timed out: {' '.join(cmd)}")
            raise
        except Exception as e:
            self.logger.error(f"Error running command: {str(e)}")
            raise


# Global instances
signal_bot_handler = None
signal_cli_manager = None


def get_signal_bot_handler(phone_number: str = None, signal_cli_path: str = None) -> SignalBotHandler:
    """Get or create Signal bot handler instance."""
    global signal_bot_handler
    
    if signal_bot_handler is None:
        if not phone_number:
            phone_number = current_app.config.get('SIGNAL_PHONE_NUMBER')
        if not signal_cli_path:
            signal_cli_path = current_app.config.get('SIGNAL_CLI_PATH')
            
        if not phone_number:
            raise ValueError("Signal phone number is required")
            
        signal_bot_handler = SignalBotHandler(phone_number, signal_cli_path)
    
    return signal_bot_handler


def get_signal_cli_manager(signal_cli_path: str = None) -> SignalCLIManager:
    """Get or create Signal CLI manager instance."""
    global signal_cli_manager
    
    if signal_cli_manager is None:
        if not signal_cli_path:
            signal_cli_path = current_app.config.get('SIGNAL_CLI_PATH')
            
        signal_cli_manager = SignalCLIManager(signal_cli_path)
    
    return signal_cli_manager