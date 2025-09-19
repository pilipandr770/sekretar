"""Web widget API endpoints."""
from flask import request, g, jsonify
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from sqlalchemy.orm import joinedload
from app.channels import channels_bp
from app.models import Channel, Thread, InboxMessage, User
from app.utils.decorators import (
    require_tenant, require_json, validate_pagination,
    require_permission, log_api_call, audit_log
)
from app.utils.response import (
    success_response, error_response, not_found_response,
    validation_error_response
)
from app.utils.tenant_middleware import TenantAwareQuery
from app.utils.validators import validate_required_fields
from app import db
import structlog
from datetime import datetime

logger = structlog.get_logger()


@channels_bp.route('/widget/init', methods=['POST'])
@jwt_required()
@require_tenant()
@require_json(['customer_id'])
@log_api_call('widget_init')
def initialize_widget():
    """Initialize web widget session and create/get thread."""
    try:
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['customer_id'])
        
        customer_id = data['customer_id']
        customer_name = data.get('customer_name', 'Web Visitor')
        customer_email = data.get('customer_email')
        
        # Get or create web widget channel
        channel = Channel.query.filter_by(
            tenant_id=g.tenant_id,
            type='web_widget',
            is_active=True
        ).first()
        
        if not channel:
            # Create web widget channel
            channel = Channel.create(
                tenant_id=g.tenant_id,
                name='Web Widget',
                type='web_widget',
                config={
                    'auto_created': True,
                    'created_by': 'widget_api'
                },
                is_active=True,
                is_connected=True
            )
            channel.save()
        
        # Check for existing thread for this customer
        existing_thread = Thread.query.filter_by(
            tenant_id=g.tenant_id,
            channel_id=channel.id,
            customer_id=customer_id,
            status='open'
        ).first()
        
        if existing_thread:
            thread = existing_thread
            logger.info(
                "Using existing thread for widget",
                thread_id=thread.id,
                customer_id=customer_id,
                tenant_id=g.tenant_id
            )
        else:
            # Create new thread
            thread = Thread.create(
                tenant_id=g.tenant_id,
                channel_id=channel.id,
                customer_id=customer_id,
                customer_name=customer_name,
                customer_email=customer_email,
                subject=f"Web chat with {customer_name}",
                status='open',
                priority='normal',
                ai_enabled=True,
                metadata={
                    'source': 'web_widget',
                    'user_agent': request.headers.get('User-Agent', ''),
                    'ip_address': request.remote_addr,
                    'created_at': datetime.utcnow().isoformat()
                }
            )
            thread.save()
            
            logger.info(
                "Created new thread for widget",
                thread_id=thread.id,
                customer_id=customer_id,
                tenant_id=g.tenant_id
            )
        
        # Update thread metadata with latest session info
        thread.set_metadata('last_seen', datetime.utcnow().isoformat())
        thread.set_metadata('session_count', thread.get_metadata('session_count', 0) + 1)
        thread.save()
        
        # Get recent messages for the thread
        recent_messages = InboxMessage.query.filter_by(
            thread_id=thread.id,
            tenant_id=g.tenant_id
        ).options(
            joinedload(InboxMessage.attachments)
        ).order_by(
            InboxMessage.created_at.desc()
        ).limit(50).all()
        
        # Convert messages to dictionaries
        message_data = []
        for message in reversed(recent_messages):  # Reverse to get chronological order
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
        
        return success_response(
            message=_('Widget initialized successfully'),
            data={
                'thread': thread.to_dict(),
                'channel': channel.to_dict(),
                'messages': message_data,
                'session_info': {
                    'customer_id': customer_id,
                    'customer_name': customer_name,
                    'customer_email': customer_email,
                    'session_count': thread.get_metadata('session_count', 1),
                    'last_seen': thread.get_metadata('last_seen')
                }
            }
        )
        
    except Exception as e:
        logger.error("Failed to initialize widget", error=str(e), exc_info=True)
        return error_response(
            error_code='WIDGET_INIT_FAILED',
            message=_('Failed to initialize widget'),
            status_code=500
        )


@channels_bp.route('/widget/thread/<int:thread_id>/messages', methods=['GET'])
@jwt_required()
@require_tenant()
@validate_pagination()
@log_api_call('widget_get_messages')
def get_widget_messages(thread_id):
    """Get messages for a widget thread."""
    try:
        # Verify thread exists and belongs to tenant
        thread = TenantAwareQuery.get_by_id_or_404(Thread, thread_id)
        
        # Ensure it's a web widget thread
        if thread.channel.type != 'web_widget':
            return error_response(
                error_code='INVALID_THREAD_TYPE',
                message=_('Thread is not a web widget thread'),
                status_code=400
            )
        
        # Get pagination parameters
        page = g.page
        per_page = g.per_page
        
        # Get messages
        query = InboxMessage.query.filter_by(
            thread_id=thread_id,
            tenant_id=g.tenant_id
        ).options(
            joinedload(InboxMessage.attachments)
        ).order_by(InboxMessage.created_at.desc())
        
        total = query.count()
        messages = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Convert to dictionaries
        message_data = []
        for message in reversed(messages):  # Reverse to get chronological order
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
        
        return success_response(
            message=_('Messages retrieved successfully'),
            data={
                'messages': message_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                },
                'thread': thread.to_dict()
            }
        )
        
    except Exception as e:
        logger.error("Failed to get widget messages", thread_id=thread_id, error=str(e))
        return error_response(
            error_code='WIDGET_MESSAGES_FAILED',
            message=_('Failed to retrieve messages'),
            status_code=500
        )


@channels_bp.route('/widget/thread/<int:thread_id>/send', methods=['POST'])
@jwt_required()
@require_tenant()
@require_json(['content'])
@log_api_call('widget_send_message')
@audit_log('widget_send_message', 'inbox_message')
def send_widget_message(thread_id):
    """Send a message through the web widget."""
    try:
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['content'])
        
        content = data['content'].strip()
        if not content:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Message content cannot be empty'),
                status_code=400
            )
        
        # Verify thread exists and belongs to tenant
        thread = TenantAwareQuery.get_by_id_or_404(Thread, thread_id)
        
        # Ensure it's a web widget thread
        if thread.channel.type != 'web_widget':
            return error_response(
                error_code='INVALID_THREAD_TYPE',
                message=_('Thread is not a web widget thread'),
                status_code=400
            )
        
        # Create inbound message (from customer)
        message = InboxMessage.create_inbound(
            tenant_id=g.tenant_id,
            channel_id=thread.channel_id,
            thread_id=thread_id,
            sender_id=thread.customer_id,
            content=content,
            sender_name=thread.customer_name,
            sender_email=thread.customer_email,
            content_type=data.get('content_type', 'text'),
            message_type='message'
        )
        
        # Set widget-specific metadata
        message.set_metadata('source', 'web_widget')
        message.set_metadata('user_agent', request.headers.get('User-Agent', ''))
        message.set_metadata('ip_address', request.remote_addr)
        message.set_metadata('timestamp', datetime.utcnow().isoformat())
        
        message.save()
        
        # Update channel statistics
        thread.channel.increment_received()
        thread.channel.save()
        
        # Update thread last activity
        thread.set_metadata('last_activity', datetime.utcnow().isoformat())
        thread.save()
        
        logger.info(
            "Message sent via widget",
            message_id=message.id,
            thread_id=thread_id,
            customer_id=thread.customer_id,
            tenant_id=g.tenant_id
        )
        
        # Broadcast message via WebSocket (if connected)
        try:
            from app.channels.websocket_handlers import broadcast_message_update
            broadcast_message_update(message.id, g.tenant_id, 'new_message')
        except Exception as ws_error:
            logger.warning("Failed to broadcast message via WebSocket", error=str(ws_error))
        
        return success_response(
            message=_('Message sent successfully'),
            data=message.to_dict(),
            status_code=201
        )
        
    except Exception as e:
        logger.error("Failed to send widget message", thread_id=thread_id, error=str(e), exc_info=True)
        return error_response(
            error_code='WIDGET_SEND_FAILED',
            message=_('Failed to send message'),
            status_code=500
        )


@channels_bp.route('/widget/thread/<int:thread_id>/typing', methods=['POST'])
@jwt_required()
@require_tenant()
@require_json(['typing'])
@log_api_call('widget_typing')
def handle_widget_typing(thread_id):
    """Handle typing indicator for web widget."""
    try:
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['typing'])
        
        is_typing = data['typing']
        
        # Verify thread exists and belongs to tenant
        thread = TenantAwareQuery.get_by_id_or_404(Thread, thread_id)
        
        # Ensure it's a web widget thread
        if thread.channel.type != 'web_widget':
            return error_response(
                error_code='INVALID_THREAD_TYPE',
                message=_('Thread is not a web widget thread'),
                status_code=400
            )
        
        # Broadcast typing indicator via WebSocket
        try:
            from app.utils.websocket_manager import emit_with_fallback
            emit_with_fallback('user_typing', {
                'user_id': thread.customer_id,
                'user_name': thread.customer_name or 'Customer',
                'thread_id': thread_id,
                'typing': is_typing,
                'timestamp': datetime.utcnow().isoformat()
            }, room=f"thread_{thread_id}")
            
        except Exception as ws_error:
            logger.warning("Failed to broadcast typing indicator", error=str(ws_error))
        
        return success_response(
            message=_('Typing indicator updated'),
            data={
                'thread_id': thread_id,
                'typing': is_typing,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error("Failed to handle widget typing", thread_id=thread_id, error=str(e))
        return error_response(
            error_code='WIDGET_TYPING_FAILED',
            message=_('Failed to update typing indicator'),
            status_code=500
        )


@channels_bp.route('/widget/config', methods=['GET'])
@jwt_required()
@require_tenant()
@log_api_call('widget_get_config')
def get_widget_config():
    """Get widget configuration for tenant."""
    try:
        # Get web widget channel
        channel = Channel.query.filter_by(
            tenant_id=g.tenant_id,
            type='web_widget',
            is_active=True
        ).first()
        
        # Default configuration
        config = {
            'enabled': bool(channel and channel.is_connected),
            'title': 'AI Secretary',
            'subtitle': 'How can I help you today?',
            'theme': 'light',
            'position': 'bottom-right',
            'auto_open': False,
            'show_typing_indicator': True,
            'show_timestamps': True,
            'enable_sound': True,
            'max_message_length': 2000,
            'rate_limit': {
                'messages_per_minute': 10,
                'messages_per_hour': 100
            }
        }
        
        # Override with channel-specific config if available
        if channel and channel.config:
            widget_config = channel.config.get('widget', {})
            config.update(widget_config)
        
        return success_response(
            message=_('Widget configuration retrieved'),
            data=config
        )
        
    except Exception as e:
        logger.error("Failed to get widget config", error=str(e))
        return error_response(
            error_code='WIDGET_CONFIG_FAILED',
            message=_('Failed to retrieve widget configuration'),
            status_code=500
        )


@channels_bp.route('/widget/config', methods=['PUT'])
@jwt_required()
@require_tenant()
@require_json()
@require_permission('channels.manage')
@log_api_call('widget_update_config')
@audit_log('widget_update_config', 'channel')
def update_widget_config():
    """Update widget configuration for tenant."""
    try:
        data = request.get_json()
        
        # Get or create web widget channel
        channel = Channel.query.filter_by(
            tenant_id=g.tenant_id,
            type='web_widget'
        ).first()
        
        if not channel:
            channel = Channel.create(
                tenant_id=g.tenant_id,
                name='Web Widget',
                type='web_widget',
                config={'widget': {}},
                is_active=True,
                is_connected=True
            )
        
        # Update widget configuration
        if not channel.config:
            channel.config = {}
        
        if 'widget' not in channel.config:
            channel.config['widget'] = {}
        
        # Allowed configuration keys
        allowed_keys = [
            'title', 'subtitle', 'theme', 'position', 'auto_open',
            'show_typing_indicator', 'show_timestamps', 'enable_sound',
            'max_message_length', 'rate_limit'
        ]
        
        for key in allowed_keys:
            if key in data:
                channel.config['widget'][key] = data[key]
        
        # Mark as modified for SQLAlchemy
        channel.config = dict(channel.config)
        channel.save()
        
        logger.info(
            "Widget configuration updated",
            channel_id=channel.id,
            tenant_id=g.tenant_id,
            updated_by=get_current_user().id
        )
        
        return success_response(
            message=_('Widget configuration updated successfully'),
            data=channel.config.get('widget', {})
        )
        
    except Exception as e:
        logger.error("Failed to update widget config", error=str(e), exc_info=True)
        return error_response(
            error_code='WIDGET_CONFIG_UPDATE_FAILED',
            message=_('Failed to update widget configuration'),
            status_code=500
        )


@channels_bp.route('/widget/stats', methods=['GET'])
@jwt_required()
@require_tenant()
@log_api_call('widget_get_stats')
def get_widget_stats():
    """Get widget usage statistics."""
    try:
        # Get web widget channel
        channel = Channel.query.filter_by(
            tenant_id=g.tenant_id,
            type='web_widget',
            is_active=True
        ).first()
        
        if not channel:
            return success_response(
                message=_('Widget statistics retrieved'),
                data={
                    'enabled': False,
                    'total_threads': 0,
                    'total_messages': 0,
                    'active_threads': 0,
                    'messages_today': 0,
                    'avg_response_time': 0
                }
            )
        
        # Get date range for stats
        from datetime import datetime, timedelta
        today = datetime.utcnow().date()
        
        # Thread statistics
        total_threads = Thread.query.filter_by(
            tenant_id=g.tenant_id,
            channel_id=channel.id
        ).count()
        
        active_threads = Thread.query.filter_by(
            tenant_id=g.tenant_id,
            channel_id=channel.id,
            status='open'
        ).count()
        
        # Message statistics
        total_messages = InboxMessage.query.filter_by(
            tenant_id=g.tenant_id,
            channel_id=channel.id
        ).count()
        
        messages_today = InboxMessage.query.filter_by(
            tenant_id=g.tenant_id,
            channel_id=channel.id
        ).filter(
            InboxMessage.created_at >= today
        ).count()
        
        # Calculate average response time (simplified)
        avg_response_time = 0  # Would need more complex calculation
        
        stats = {
            'enabled': channel.is_connected,
            'total_threads': total_threads,
            'total_messages': total_messages,
            'active_threads': active_threads,
            'messages_today': messages_today,
            'avg_response_time': avg_response_time,
            'channel_info': {
                'id': channel.id,
                'name': channel.name,
                'created_at': channel.created_at.isoformat() if channel.created_at else None,
                'last_activity': channel.last_activity_at.isoformat() if channel.last_activity_at else None
            }
        }
        
        return success_response(
            message=_('Widget statistics retrieved'),
            data=stats
        )
        
    except Exception as e:
        logger.error("Failed to get widget stats", error=str(e))
        return error_response(
            error_code='WIDGET_STATS_FAILED',
            message=_('Failed to retrieve widget statistics'),
            status_code=500
        )