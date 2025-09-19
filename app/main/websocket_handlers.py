"""WebSocket handlers for real-time features."""
import json
from flask import request
from flask_socketio import emit, join_room, leave_room, disconnect
from flask_jwt_extended import decode_token, get_jwt_identity
from app.utils.websocket_manager import get_socketio, emit_with_fallback
from app.models.user import User
from app.models.tenant import Tenant
import structlog

logger = structlog.get_logger(__name__)


# Store active connections
active_connections = {}

# Get socketio instance - will be None if WebSocket unavailable
socketio = get_socketio()


# Handler functions (will be registered conditionally)
def handle_connect(auth):
    """Handle client connection."""
    try:
        # Authenticate user via token
        token = auth.get('token') if auth else None
        if not token:
            logger.warning("WebSocket connection attempted without token")
            disconnect()
            return False
        
        # Decode JWT token
        try:
            decoded_token = decode_token(token)
            user_id = decoded_token['sub']
        except Exception as e:
            logger.warning("Invalid WebSocket token", error=str(e))
            disconnect()
            return False
        
        # Get user and tenant info
        user = User.query.get(user_id)
        if not user or not user.is_active:
            logger.warning("WebSocket connection for inactive user", user_id=user_id)
            disconnect()
            return False
        
        # Store connection info
        session_id = request.sid
        active_connections[session_id] = {
            'user_id': user.id,
            'tenant_id': user.tenant_id,
            'user_email': user.email,
            'connected_at': None  # Will be set by datetime when needed
        }
        
        # Join tenant room for tenant-specific broadcasts
        join_room(f"tenant_{user.tenant_id}")
        
        # Join user-specific room
        join_room(f"user_{user.id}")
        
        logger.info("WebSocket client connected", 
                   user_id=user.id, 
                   tenant_id=user.tenant_id,
                   session_id=session_id)
        
        # Send connection confirmation
        emit('connected', {
            'status': 'connected',
            'user_id': user.id,
            'tenant_id': user.tenant_id
        })
        
        return True
        
    except Exception as e:
        logger.error("WebSocket connection error", error=str(e))
        disconnect()
        return False


def handle_disconnect():
    """Handle client disconnection."""
    session_id = request.sid
    
    if session_id in active_connections:
        connection_info = active_connections[session_id]
        user_id = connection_info['user_id']
        tenant_id = connection_info['tenant_id']
        
        # Leave rooms
        leave_room(f"tenant_{tenant_id}")
        leave_room(f"user_{user_id}")
        
        # Remove from active connections
        del active_connections[session_id]
        
        logger.info("WebSocket client disconnected", 
                   user_id=user_id, 
                   tenant_id=tenant_id,
                   session_id=session_id)


def handle_join_conversation(data):
    """Handle joining a conversation room."""
    session_id = request.sid
    
    if session_id not in active_connections:
        emit('error', {'message': 'Not authenticated'})
        return
    
    conversation_id = data.get('conversation_id')
    if not conversation_id:
        emit('error', {'message': 'Conversation ID required'})
        return
    
    connection_info = active_connections[session_id]
    tenant_id = connection_info['tenant_id']
    
    # Join conversation room
    room_name = f"conversation_{conversation_id}_{tenant_id}"
    join_room(room_name)
    
    logger.info("User joined conversation", 
               user_id=connection_info['user_id'],
               conversation_id=conversation_id,
               room=room_name)
    
    emit('joined_conversation', {
        'conversation_id': conversation_id,
        'status': 'joined'
    })


def handle_leave_conversation(data):
    """Handle leaving a conversation room."""
    session_id = request.sid
    
    if session_id not in active_connections:
        return
    
    conversation_id = data.get('conversation_id')
    if not conversation_id:
        return
    
    connection_info = active_connections[session_id]
    tenant_id = connection_info['tenant_id']
    
    # Leave conversation room
    room_name = f"conversation_{conversation_id}_{tenant_id}"
    leave_room(room_name)
    
    logger.info("User left conversation", 
               user_id=connection_info['user_id'],
               conversation_id=conversation_id,
               room=room_name)


def handle_typing_start(data):
    """Handle typing indicator start."""
    session_id = request.sid
    
    if session_id not in active_connections:
        return
    
    conversation_id = data.get('conversation_id')
    if not conversation_id:
        return
    
    connection_info = active_connections[session_id]
    tenant_id = connection_info['tenant_id']
    user_id = connection_info['user_id']
    
    # Broadcast typing indicator to conversation room (excluding sender)
    room_name = f"conversation_{conversation_id}_{tenant_id}"
    emit('user_typing', {
        'conversation_id': conversation_id,
        'user_id': user_id,
        'user_email': connection_info['user_email'],
        'typing': True
    }, room=room_name, include_self=False)


def handle_typing_stop(data):
    """Handle typing indicator stop."""
    session_id = request.sid
    
    if session_id not in active_connections:
        return
    
    conversation_id = data.get('conversation_id')
    if not conversation_id:
        return
    
    connection_info = active_connections[session_id]
    tenant_id = connection_info['tenant_id']
    user_id = connection_info['user_id']
    
    # Broadcast typing stop to conversation room (excluding sender)
    room_name = f"conversation_{conversation_id}_{tenant_id}"
    emit('user_typing', {
        'conversation_id': conversation_id,
        'user_id': user_id,
        'user_email': connection_info['user_email'],
        'typing': False
    }, room=room_name, include_self=False)


def handle_ping():
    """Handle ping for connection keepalive."""
    emit('pong')


# Utility functions for broadcasting events

def broadcast_new_message(tenant_id, conversation_id, message_data):
    """Broadcast new message to conversation participants."""
    room_name = f"conversation_{conversation_id}_{tenant_id}"
    
    def fallback(event, data, room):
        logger.debug(f"WebSocket unavailable, message broadcast skipped for {room}")
    
    emit_with_fallback('new_message', {
        'conversation_id': conversation_id,
        'message': message_data
    }, room=room_name, fallback_callback=fallback)
    
    logger.info("Broadcasted new message", 
               tenant_id=tenant_id,
               conversation_id=conversation_id,
               room=room_name)


def broadcast_message_update(tenant_id, conversation_id, message_data):
    """Broadcast message update to conversation participants."""
    room_name = f"conversation_{conversation_id}_{tenant_id}"
    emit_with_fallback('message_updated', {
        'conversation_id': conversation_id,
        'message': message_data
    }, room=room_name)


def broadcast_conversation_update(tenant_id, conversation_data):
    """Broadcast conversation update to tenant users."""
    room_name = f"tenant_{tenant_id}"
    emit_with_fallback('conversation_updated', {
        'conversation': conversation_data
    }, room=room_name)


def broadcast_notification(user_id, notification_data):
    """Broadcast notification to specific user."""
    room_name = f"user_{user_id}"
    
    def fallback(event, data, room):
        # Could implement push notification fallback here
        logger.debug(f"WebSocket unavailable, notification fallback for user {user_id}")
    
    emit_with_fallback('notification', notification_data, room=room_name, fallback_callback=fallback)
    
    logger.info("Broadcasted notification", 
               user_id=user_id,
               notification_type=notification_data.get('type'))


def broadcast_tenant_notification(tenant_id, notification_data):
    """Broadcast notification to all tenant users."""
    room_name = f"tenant_{tenant_id}"
    emit_with_fallback('tenant_notification', notification_data, room=room_name)


def broadcast_lead_update(tenant_id, lead_data):
    """Broadcast lead update to tenant users."""
    room_name = f"tenant_{tenant_id}"
    emit_with_fallback('lead_updated', {
        'lead': lead_data
    }, room=room_name)


def broadcast_appointment_update(tenant_id, appointment_data):
    """Broadcast appointment update to tenant users."""
    room_name = f"tenant_{tenant_id}"
    emit_with_fallback('appointment_updated', {
        'appointment': appointment_data
    }, room=room_name)


def broadcast_system_alert(tenant_id, alert_data):
    """Broadcast system alert to tenant users."""
    room_name = f"tenant_{tenant_id}"
    emit_with_fallback('system_alert', alert_data, room=room_name)


def get_active_users_count(tenant_id):
    """Get count of active users for a tenant."""
    count = 0
    for connection in active_connections.values():
        if connection['tenant_id'] == tenant_id:
            count += 1
    return count


def get_active_users_in_conversation(tenant_id, conversation_id):
    """Get list of active users in a conversation."""
    # This would require tracking which users are in which conversations
    # For now, return empty list as this requires more complex state management
    return []


def is_user_online(user_id):
    """Check if a user is currently online."""
    for connection in active_connections.values():
        if connection['user_id'] == user_id:
            return True
    return False


def register_websocket_handlers():
    """Register WebSocket handlers with the manager."""
    # Only register if WebSocket is available
    socketio = get_socketio()
    if not socketio:
        logger.info("WebSocket unavailable, skipping handler registration")
        return
    
    # Register handlers directly with socketio
    socketio.on('connect')(handle_connect)
    socketio.on('disconnect')(handle_disconnect)
    socketio.on('join_conversation')(handle_join_conversation)
    socketio.on('leave_conversation')(handle_leave_conversation)
    socketio.on('typing_start')(handle_typing_start)
    socketio.on('typing_stop')(handle_typing_stop)
    socketio.on('ping')(handle_ping)
    
    logger.info("WebSocket handlers registered")