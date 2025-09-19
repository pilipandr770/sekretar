"""WebSocket handlers for web widget real-time communication."""
from flask import request, g
from flask_socketio import emit, join_room, leave_room, disconnect
from flask_jwt_extended import decode_token, get_jwt_identity
from sqlalchemy.orm import joinedload
from app import db
from app.utils.websocket_manager import get_socketio, emit_with_fallback
from app.models import InboxMessage, Thread, Channel, User, Tenant
from app.utils.tenant_middleware import TenantAwareQuery
# from app.services.orchestration_service import OrchestrationService
import structlog
import json
from datetime import datetime

logger = structlog.get_logger()

# Get socketio instance - will be None if WebSocket unavailable
socketio = get_socketio()


class WebSocketAuth:
    """WebSocket authentication helper."""
    
    @staticmethod
    def authenticate_socket(auth_data):
        """Authenticate WebSocket connection."""
        try:
            if not auth_data or 'token' not in auth_data:
                return None, None
            
            # Decode JWT token
            token_data = decode_token(auth_data['token'])
            user_id = token_data['sub']
            tenant_id = token_data.get('tenant_id')
            
            if not user_id or not tenant_id:
                return None, None
            
            # Verify user exists and is active
            user = User.query.filter_by(id=user_id, tenant_id=tenant_id, is_active=True).first()
            if not user:
                return None, None
            
            return user, tenant_id
            
        except Exception as e:
            logger.error("WebSocket authentication failed", error=str(e))
            return None, None


def handle_connect(auth):
    """Handle WebSocket connection."""
    try:
        # Check if auth data is provided
        if not auth or 'token' not in auth:
            logger.debug("WebSocket connection attempt without authentication token")
            disconnect()
            return False
        
        # Authenticate user
        user, tenant_id = WebSocketAuth.authenticate_socket(auth)
        if not user:
            logger.debug("WebSocket authentication failed", auth_provided=bool(auth))
            disconnect()
            return False
        
        # Store user info in session
        request.sid_user_id = user.id
        request.sid_tenant_id = tenant_id
        
        # Join tenant room for broadcasts
        join_room(f"tenant_{tenant_id}")
        
        logger.info(
            "WebSocket connection established",
            user_id=user.id,
            tenant_id=tenant_id,
            session_id=request.sid
        )
        
        # Send connection confirmation
        emit('connected', {
            'status': 'connected',
            'user_id': user.id,
            'tenant_id': tenant_id,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return True
        
    except Exception as e:
        logger.error("WebSocket connection error", error=str(e))
        disconnect()
        return False


def handle_disconnect():
    """Handle WebSocket disconnection."""
    try:
        user_id = getattr(request, 'sid_user_id', None)
        tenant_id = getattr(request, 'sid_tenant_id', None)
        
        if tenant_id:
            leave_room(f"tenant_{tenant_id}")
        
        logger.info(
            "WebSocket connection closed",
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=request.sid
        )
        
    except Exception as e:
        logger.error("WebSocket disconnection error", error=str(e))


def handle_join_thread(data):
    """Join a specific thread room for real-time updates."""
    try:
        user_id = getattr(request, 'sid_user_id', None)
        tenant_id = getattr(request, 'sid_tenant_id', None)
        
        if not user_id or not tenant_id:
            emit('error', {'message': 'Not authenticated'})
            return
        
        thread_id = data.get('thread_id')
        if not thread_id:
            emit('error', {'message': 'Thread ID is required'})
            return
        
        # Verify thread exists and belongs to tenant
        thread = Thread.query.filter_by(
            id=thread_id,
            tenant_id=tenant_id
        ).first()
        
        if not thread:
            emit('error', {'message': 'Thread not found'})
            return
        
        # Join thread room
        room_name = f"thread_{thread_id}"
        join_room(room_name)
        
        logger.info(
            "User joined thread room",
            user_id=user_id,
            tenant_id=tenant_id,
            thread_id=thread_id
        )
        
        emit('thread_joined', {
            'thread_id': thread_id,
            'room': room_name,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("Failed to join thread", error=str(e))
        emit('error', {'message': 'Failed to join thread'})


def handle_leave_thread(data):
    """Leave a specific thread room."""
    try:
        user_id = getattr(request, 'sid_user_id', None)
        tenant_id = getattr(request, 'sid_tenant_id', None)
        
        if not user_id or not tenant_id:
            emit('error', {'message': 'Not authenticated'})
            return
        
        thread_id = data.get('thread_id')
        if not thread_id:
            emit('error', {'message': 'Thread ID is required'})
            return
        
        # Leave thread room
        room_name = f"thread_{thread_id}"
        leave_room(room_name)
        
        logger.info(
            "User left thread room",
            user_id=user_id,
            tenant_id=tenant_id,
            thread_id=thread_id
        )
        
        emit('thread_left', {
            'thread_id': thread_id,
            'room': room_name,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("Failed to leave thread", error=str(e))
        emit('error', {'message': 'Failed to leave thread'})


def handle_send_message(data):
    """Handle real-time message sending."""
    try:
        user_id = getattr(request, 'sid_user_id', None)
        tenant_id = getattr(request, 'sid_tenant_id', None)
        
        if not user_id or not tenant_id:
            emit('error', {'message': 'Not authenticated'})
            return
        
        # Validate required fields
        required_fields = ['thread_id', 'content']
        for field in required_fields:
            if field not in data:
                emit('error', {'message': f'{field} is required'})
                return
        
        thread_id = data['thread_id']
        content = data['content'].strip()
        
        if not content:
            emit('error', {'message': 'Message content cannot be empty'})
            return
        
        # Verify thread exists and belongs to tenant
        thread = Thread.query.filter_by(
            id=thread_id,
            tenant_id=tenant_id
        ).options(joinedload(Thread.channel)).first()
        
        if not thread:
            emit('error', {'message': 'Thread not found'})
            return
        
        # Create outbound message
        message = InboxMessage.create_outbound(
            tenant_id=tenant_id,
            channel_id=thread.channel_id,
            thread_id=thread_id,
            content=content,
            sender_id=f"user_{user_id}",
            content_type=data.get('content_type', 'text'),
            message_type='message'
        )
        
        # Set additional metadata
        message.set_metadata('source', 'web_widget')
        message.set_metadata('user_agent', request.headers.get('User-Agent', ''))
        
        # Mark as sent
        message.mark_as_sent()
        message.save()
        
        # Update channel statistics
        if thread.channel:
            thread.channel.increment_sent()
            thread.channel.save()
        
        logger.info(
            "Message sent via WebSocket",
            message_id=message.id,
            thread_id=thread_id,
            user_id=user_id,
            tenant_id=tenant_id
        )
        
        # Prepare message data for broadcast
        message_data = message.to_dict()
        message_data['user_name'] = User.query.get(user_id).full_name
        
        # Broadcast to thread room
        socketio.emit('new_message', message_data, room=f"thread_{thread_id}")
        
        # Send confirmation to sender
        emit('message_sent', {
            'message_id': message.id,
            'thread_id': thread_id,
            'timestamp': message.sent_at,
            'status': 'sent'
        })
        
        # Trigger AI response if thread has AI enabled
        if thread.ai_enabled and not thread.assigned_to_id:
            try:
                # TODO: Implement AI response generation
                # For now, create a simple mock response
                ai_response = {
                    'content': 'Thank you for your message. An AI assistant will respond shortly.',
                    'agent_type': 'support',
                    'confidence': 'medium'
                }
                
                if ai_response:
                    # Create AI response message
                    ai_message = InboxMessage.create_outbound(
                        tenant_id=tenant_id,
                        channel_id=thread.channel_id,
                        thread_id=thread_id,
                        content=ai_response['content'],
                        sender_id='ai_assistant',
                        content_type='text',
                        message_type='message'
                    )
                    
                    ai_message.set_metadata('source', 'ai_assistant')
                    ai_message.set_metadata('agent_type', ai_response.get('agent_type', 'unknown'))
                    ai_message.set_metadata('confidence', ai_response.get('confidence', 'medium'))
                    ai_message.mark_as_sent()
                    ai_message.save()
                    
                    # Broadcast AI response
                    ai_message_data = ai_message.to_dict()
                    ai_message_data['user_name'] = 'AI Assistant'
                    ai_message_data['is_ai_response'] = True
                    
                    socketio.emit('new_message', ai_message_data, room=f"thread_{thread_id}")
                    
                    logger.info(
                        "AI response sent via WebSocket",
                        message_id=ai_message.id,
                        thread_id=thread_id,
                        agent_type=ai_response.get('agent_type')
                    )
                    
            except Exception as ai_error:
                logger.error("Failed to generate AI response", error=str(ai_error))
        
    except Exception as e:
        logger.error("Failed to send message via WebSocket", error=str(e))
        emit('error', {'message': 'Failed to send message'})


def handle_typing_start(data):
    """Handle typing indicator start."""
    try:
        user_id = getattr(request, 'sid_user_id', None)
        tenant_id = getattr(request, 'sid_tenant_id', None)
        
        if not user_id or not tenant_id:
            return
        
        thread_id = data.get('thread_id')
        if not thread_id:
            return
        
        # Get user name
        user = User.query.get(user_id)
        if not user:
            return
        
        # Broadcast typing indicator to thread room (excluding sender)
        socketio.emit('user_typing', {
            'user_id': user_id,
            'user_name': user.full_name,
            'thread_id': thread_id,
            'typing': True,
            'timestamp': datetime.utcnow().isoformat()
        }, room=f"thread_{thread_id}", include_self=False)
        
    except Exception as e:
        logger.error("Failed to handle typing start", error=str(e))


def handle_typing_stop(data):
    """Handle typing indicator stop."""
    try:
        user_id = getattr(request, 'sid_user_id', None)
        tenant_id = getattr(request, 'sid_tenant_id', None)
        
        if not user_id or not tenant_id:
            return
        
        thread_id = data.get('thread_id')
        if not thread_id:
            return
        
        # Get user name
        user = User.query.get(user_id)
        if not user:
            return
        
        # Broadcast typing stop to thread room (excluding sender)
        socketio.emit('user_typing', {
            'user_id': user_id,
            'user_name': user.full_name,
            'thread_id': thread_id,
            'typing': False,
            'timestamp': datetime.utcnow().isoformat()
        }, room=f"thread_{thread_id}", include_self=False)
        
    except Exception as e:
        logger.error("Failed to handle typing stop", error=str(e))


def handle_mark_read(data):
    """Handle marking messages as read."""
    try:
        user_id = getattr(request, 'sid_user_id', None)
        tenant_id = getattr(request, 'sid_tenant_id', None)
        
        if not user_id or not tenant_id:
            emit('error', {'message': 'Not authenticated'})
            return
        
        message_ids = data.get('message_ids', [])
        if not message_ids:
            emit('error', {'message': 'Message IDs are required'})
            return
        
        # Mark messages as read
        messages = InboxMessage.query.filter(
            InboxMessage.id.in_(message_ids),
            InboxMessage.tenant_id == tenant_id,
            InboxMessage.direction == 'inbound',
            InboxMessage.is_read == False
        ).all()
        
        marked_count = 0
        for message in messages:
            message.mark_as_read()
            marked_count += 1
        
        if marked_count > 0:
            db.session.commit()
            
            logger.info(
                "Messages marked as read via WebSocket",
                user_id=user_id,
                tenant_id=tenant_id,
                marked_count=marked_count
            )
        
        emit('messages_marked_read', {
            'message_ids': [msg.id for msg in messages],
            'marked_count': marked_count,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("Failed to mark messages as read", error=str(e))
        emit('error', {'message': 'Failed to mark messages as read'})


def handle_get_thread_messages(data):
    """Get messages for a thread via WebSocket."""
    try:
        user_id = getattr(request, 'sid_user_id', None)
        tenant_id = getattr(request, 'sid_tenant_id', None)
        
        if not user_id or not tenant_id:
            emit('error', {'message': 'Not authenticated'})
            return
        
        thread_id = data.get('thread_id')
        if not thread_id:
            emit('error', {'message': 'Thread ID is required'})
            return
        
        limit = data.get('limit', 50)
        offset = data.get('offset', 0)
        
        # Verify thread belongs to tenant
        thread = Thread.query.filter_by(
            id=thread_id,
            tenant_id=tenant_id
        ).first()
        
        if not thread:
            emit('error', {'message': 'Thread not found'})
            return
        
        # Get messages
        messages = InboxMessage.query.filter_by(
            thread_id=thread_id,
            tenant_id=tenant_id
        ).options(
            joinedload(InboxMessage.attachments)
        ).order_by(
            InboxMessage.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        # Convert to dictionaries
        message_data = []
        for message in messages:
            data = message.to_dict()
            
            # Add user name for outbound messages
            if message.direction == 'outbound' and message.sender_id.startswith('user_'):
                try:
                    sender_user_id = int(message.sender_id.replace('user_', ''))
                    sender = User.query.get(sender_user_id)
                    if sender:
                        data['user_name'] = sender.full_name
                except:
                    pass
            elif message.sender_id == 'ai_assistant':
                data['user_name'] = 'AI Assistant'
                data['is_ai_response'] = True
            
            # Add attachment information
            if message.attachments:
                data['attachments'] = [att.to_dict() for att in message.attachments]
            
            message_data.append(data)
        
        emit('thread_messages', {
            'thread_id': thread_id,
            'messages': message_data,
            'limit': limit,
            'offset': offset,
            'count': len(message_data),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("Failed to get thread messages", error=str(e))
        emit('error', {'message': 'Failed to get thread messages'})


def broadcast_message_update(message_id, tenant_id, event_type='message_updated'):
    """Broadcast message updates to relevant rooms."""
    try:
        message = InboxMessage.query.filter_by(
            id=message_id,
            tenant_id=tenant_id
        ).options(joinedload(InboxMessage.thread)).first()
        
        if not message:
            return
        
        message_data = message.to_dict()
        
        # Broadcast to thread room
        socketio.emit(event_type, message_data, room=f"thread_{message.thread_id}")
        
        # Broadcast to tenant room for inbox updates
        socketio.emit('inbox_update', {
            'type': event_type,
            'message': message_data,
            'thread_id': message.thread_id
        }, room=f"tenant_{tenant_id}")
        
    except Exception as e:
        logger.error("Failed to broadcast message update", error=str(e))


def broadcast_thread_update(thread_id, tenant_id, event_type='thread_updated'):
    """Broadcast thread updates to relevant rooms."""
    try:
        thread = Thread.query.filter_by(
            id=thread_id,
            tenant_id=tenant_id
        ).options(
            joinedload(Thread.channel),
            joinedload(Thread.assigned_to)
        ).first()
        
        if not thread:
            return
        
        thread_data = thread.to_dict()
        
        # Broadcast to thread room
        socketio.emit(event_type, thread_data, room=f"thread_{thread_id}")
        
        # Broadcast to tenant room for inbox updates
        socketio.emit('inbox_update', {
            'type': event_type,
            'thread': thread_data
        }, room=f"tenant_{tenant_id}")
        
    except Exception as e:
        logger.error("Failed to broadcast thread update", error=str(e))