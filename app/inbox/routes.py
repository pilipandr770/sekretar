"""Inbox management API endpoints."""
from flask import request, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from sqlalchemy import and_, or_, desc, asc
from sqlalchemy.orm import joinedload
from app.inbox import inbox_bp
from app.models import InboxMessage, Thread, Channel, User, Attachment
from app.utils.decorators import (
    require_tenant, require_json, validate_pagination, 
    require_permission, log_api_call, audit_log
)
from app.utils.response import (
    success_response, error_response, not_found_response,
    validation_error_response, paginated_response
)
from app.utils.tenant_middleware import TenantAwareQuery
from app.utils.validators import validate_required_fields
from app import db
import structlog

logger = structlog.get_logger()


@inbox_bp.route('/messages', methods=['GET'])
@jwt_required()
@require_tenant()
@validate_pagination()
@log_api_call('list_messages')
def list_messages():
    """List messages with filtering and pagination."""
    try:
        # Get pagination parameters
        page = g.page
        per_page = g.per_page
        
        # Get filter parameters
        channel_id = request.args.get('channel_id', type=int)
        thread_id = request.args.get('thread_id', type=int)
        direction = request.args.get('direction')  # inbound, outbound
        status = request.args.get('status')
        is_read = request.args.get('is_read', type=bool)
        ai_processed = request.args.get('ai_processed', type=bool)
        sender_id = request.args.get('sender_id')
        
        # Date range filters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Search parameters
        search = request.args.get('search')
        
        # Sort parameters
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build base query with tenant filtering
        query = InboxMessage.query.filter_by(tenant_id=g.tenant_id)
        
        # Apply filters
        if channel_id:
            query = query.filter(InboxMessage.channel_id == channel_id)
        
        if thread_id:
            query = query.filter(InboxMessage.thread_id == thread_id)
        
        if direction:
            query = query.filter(InboxMessage.direction == direction)
        
        if status:
            query = query.filter(InboxMessage.status == status)
        
        if is_read is not None:
            query = query.filter(InboxMessage.is_read == is_read)
        
        if ai_processed is not None:
            query = query.filter(InboxMessage.ai_processed == ai_processed)
        
        if sender_id:
            query = query.filter(InboxMessage.sender_id == sender_id)
        
        # Date range filtering
        if date_from:
            query = query.filter(InboxMessage.created_at >= date_from)
        
        if date_to:
            query = query.filter(InboxMessage.created_at <= date_to)
        
        # Search functionality
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    InboxMessage.content.ilike(search_term),
                    InboxMessage.sender_name.ilike(search_term),
                    InboxMessage.sender_email.ilike(search_term),
                    InboxMessage.ai_response.ilike(search_term)
                )
            )
        
        # Apply sorting
        if sort_by == 'created_at':
            sort_column = InboxMessage.created_at
        elif sort_by == 'sent_at':
            sort_column = InboxMessage.sent_at
        elif sort_by == 'sender_name':
            sort_column = InboxMessage.sender_name
        else:
            sort_column = InboxMessage.created_at
        
        if sort_order == 'desc':
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        # Include related data
        query = query.options(
            joinedload(InboxMessage.channel),
            joinedload(InboxMessage.thread),
            joinedload(InboxMessage.attachments)
        )
        
        # Get total count for pagination
        total = query.count()
        
        # Apply pagination
        messages = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Convert to dictionaries
        message_data = []
        for message in messages:
            data = message.to_dict()
            
            # Add attachment information
            if message.attachments:
                data['attachments'] = [att.to_dict() for att in message.attachments]
            
            message_data.append(data)
        
        return paginated_response(
            items=message_data,
            page=page,
            per_page=per_page,
            total=total,
            message=_('Messages retrieved successfully')
        )
        
    except Exception as e:
        logger.error("Failed to list messages", error=str(e), exc_info=True)
        return error_response(
            error_code='MESSAGE_LIST_FAILED',
            message=_('Failed to retrieve messages'),
            status_code=500
        )


@inbox_bp.route('/messages/<int:message_id>', methods=['GET'])
@jwt_required()
@require_tenant()
@log_api_call('get_message')
def get_message(message_id):
    """Get a specific message by ID."""
    try:
        message = TenantAwareQuery.get_by_id_or_404(InboxMessage, message_id)
        
        # Load related data
        db.session.refresh(message)
        
        data = message.to_dict()
        
        # Add attachment information
        if message.attachments:
            data['attachments'] = [att.to_dict() for att in message.attachments]
        
        return success_response(
            message=_('Message retrieved successfully'),
            data=data
        )
        
    except Exception as e:
        logger.error("Failed to get message", message_id=message_id, error=str(e))
        return not_found_response('Message')


@inbox_bp.route('/messages', methods=['POST'])
@jwt_required()
@require_tenant()
@require_json(['channel_id', 'thread_id', 'content'])
@require_permission('inbox.send_message')
@log_api_call('send_message')
@audit_log('send_message', 'inbox_message')
def send_message():
    """Send a new message."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['channel_id', 'thread_id', 'content']
        validate_required_fields(data, required_fields)
        
        # Validate channel exists and belongs to tenant
        channel = TenantAwareQuery.get_by_id_or_404(Channel, data['channel_id'])
        
        # Validate thread exists and belongs to tenant
        thread = TenantAwareQuery.get_by_id_or_404(Thread, data['thread_id'])
        
        # Ensure thread belongs to the same channel
        if thread.channel_id != channel.id:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Thread does not belong to the specified channel'),
                status_code=400
            )
        
        # Create outbound message
        message = InboxMessage.create_outbound(
            tenant_id=g.tenant_id,
            channel_id=channel.id,
            thread_id=thread.id,
            content=data['content'],
            sender_id=f"user_{get_current_user().id}",
            content_type=data.get('content_type', 'text'),
            message_type=data.get('message_type', 'message')
        )
        
        # Set additional metadata if provided
        if 'metadata' in data:
            for key, value in data['metadata'].items():
                message.set_metadata(key, value)
        
        # Mark as sent (in real implementation, this would be done by channel handler)
        message.mark_as_sent()
        message.save()
        
        # Update channel statistics
        channel.increment_sent()
        channel.save()
        
        logger.info(
            "Message sent successfully",
            message_id=message.id,
            channel_id=channel.id,
            thread_id=thread.id,
            user_id=get_current_user().id
        )
        
        return success_response(
            message=_('Message sent successfully'),
            data=message.to_dict(),
            status_code=201
        )
        
    except Exception as e:
        logger.error("Failed to send message", error=str(e), exc_info=True)
        return error_response(
            error_code='MESSAGE_SEND_FAILED',
            message=_('Failed to send message'),
            status_code=500
        )


@inbox_bp.route('/messages/<int:message_id>/read', methods=['POST'])
@jwt_required()
@require_tenant()
@log_api_call('mark_message_read')
def mark_message_read(message_id):
    """Mark a message as read."""
    try:
        message = TenantAwareQuery.get_by_id_or_404(InboxMessage, message_id)
        
        if not message.is_read:
            message.mark_as_read()
            message.save()
            
            logger.info(
                "Message marked as read",
                message_id=message_id,
                user_id=get_current_user().id
            )
        
        return success_response(
            message=_('Message marked as read'),
            data={'is_read': True, 'read_at': message.read_at}
        )
        
    except Exception as e:
        logger.error("Failed to mark message as read", message_id=message_id, error=str(e))
        return not_found_response('Message')


@inbox_bp.route('/threads', methods=['GET'])
@jwt_required()
@require_tenant()
@validate_pagination()
@log_api_call('list_threads')
def list_threads():
    """List conversation threads with filtering and pagination."""
    try:
        # Get pagination parameters
        page = g.page
        per_page = g.per_page
        
        # Get filter parameters
        channel_id = request.args.get('channel_id', type=int)
        status = request.args.get('status')
        assigned_to_id = request.args.get('assigned_to_id', type=int)
        priority = request.args.get('priority')
        ai_enabled = request.args.get('ai_enabled', type=bool)
        
        # Search parameters
        search = request.args.get('search')
        
        # Sort parameters
        sort_by = request.args.get('sort_by', 'last_message_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build base query with tenant filtering
        query = Thread.query.filter_by(tenant_id=g.tenant_id)
        
        # Apply filters
        if channel_id:
            query = query.filter(Thread.channel_id == channel_id)
        
        if status:
            query = query.filter(Thread.status == status)
        
        if assigned_to_id:
            query = query.filter(Thread.assigned_to_id == assigned_to_id)
        
        if priority:
            query = query.filter(Thread.priority == priority)
        
        if ai_enabled is not None:
            query = query.filter(Thread.ai_enabled == ai_enabled)
        
        # Search functionality
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Thread.subject.ilike(search_term),
                    Thread.customer_name.ilike(search_term),
                    Thread.customer_email.ilike(search_term),
                    Thread.customer_id.ilike(search_term)
                )
            )
        
        # Apply sorting
        if sort_by == 'last_message_at':
            sort_column = Thread.last_message_at
        elif sort_by == 'created_at':
            sort_column = Thread.created_at
        elif sort_by == 'customer_name':
            sort_column = Thread.customer_name
        elif sort_by == 'message_count':
            sort_column = Thread.message_count
        else:
            sort_column = Thread.last_message_at
        
        if sort_order == 'desc':
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        # Include related data
        query = query.options(
            joinedload(Thread.channel),
            joinedload(Thread.assigned_to),
            joinedload(Thread.lead)
        )
        
        # Get total count for pagination
        total = query.count()
        
        # Apply pagination
        threads = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Convert to dictionaries
        thread_data = []
        for thread in threads:
            data = thread.to_dict()
            thread_data.append(data)
        
        return paginated_response(
            items=thread_data,
            page=page,
            per_page=per_page,
            total=total,
            message=_('Threads retrieved successfully')
        )
        
    except Exception as e:
        logger.error("Failed to list threads", error=str(e), exc_info=True)
        return error_response(
            error_code='THREAD_LIST_FAILED',
            message=_('Failed to retrieve threads'),
            status_code=500
        )


@inbox_bp.route('/threads/<int:thread_id>', methods=['GET'])
@jwt_required()
@require_tenant()
@log_api_call('get_thread')
def get_thread(thread_id):
    """Get a specific thread by ID."""
    try:
        thread = TenantAwareQuery.get_by_id_or_404(Thread, thread_id)
        
        # Load related data
        db.session.refresh(thread)
        
        data = thread.to_dict()
        
        # Get recent messages for the thread
        recent_messages = InboxMessage.get_thread_messages(
            thread_id=thread_id,
            limit=request.args.get('message_limit', 50, type=int)
        )
        
        data['recent_messages'] = [msg.to_dict() for msg in recent_messages]
        
        return success_response(
            message=_('Thread retrieved successfully'),
            data=data
        )
        
    except Exception as e:
        logger.error("Failed to get thread", thread_id=thread_id, error=str(e))
        return not_found_response('Thread')


@inbox_bp.route('/threads/<int:thread_id>/assign', methods=['POST'])
@jwt_required()
@require_tenant()
@require_json(['user_id'])
@require_permission('inbox.assign_thread')
@log_api_call('assign_thread')
@audit_log('assign_thread', 'thread')
def assign_thread(thread_id):
    """Assign a thread to a user (manual handoff)."""
    try:
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['user_id'])
        
        thread = TenantAwareQuery.get_by_id_or_404(Thread, thread_id)
        
        # Validate user exists and belongs to tenant
        user = TenantAwareQuery.get_by_id_or_404(User, data['user_id'])
        
        # Assign thread to user
        thread.assign_to_user(user.id)
        thread.save()
        
        logger.info(
            "Thread assigned to user",
            thread_id=thread_id,
            assigned_to_id=user.id,
            assigned_by_id=get_current_user().id
        )
        
        return success_response(
            message=_('Thread assigned successfully'),
            data={
                'thread_id': thread.id,
                'assigned_to_id': user.id,
                'assigned_to_name': user.full_name,
                'ai_enabled': thread.ai_enabled
            }
        )
        
    except Exception as e:
        logger.error("Failed to assign thread", thread_id=thread_id, error=str(e), exc_info=True)
        return error_response(
            error_code='THREAD_ASSIGNMENT_FAILED',
            message=_('Failed to assign thread'),
            status_code=500
        )


@inbox_bp.route('/threads/<int:thread_id>/unassign', methods=['POST'])
@jwt_required()
@require_tenant()
@require_permission('inbox.assign_thread')
@log_api_call('unassign_thread')
@audit_log('unassign_thread', 'thread')
def unassign_thread(thread_id):
    """Unassign a thread from a user (return to AI)."""
    try:
        thread = TenantAwareQuery.get_by_id_or_404(Thread, thread_id)
        
        old_assigned_to_id = thread.assigned_to_id
        
        # Unassign thread
        thread.unassign()
        thread.save()
        
        logger.info(
            "Thread unassigned",
            thread_id=thread_id,
            previously_assigned_to_id=old_assigned_to_id,
            unassigned_by_id=get_current_user().id
        )
        
        return success_response(
            message=_('Thread unassigned successfully'),
            data={
                'thread_id': thread.id,
                'assigned_to_id': None,
                'ai_enabled': thread.ai_enabled
            }
        )
        
    except Exception as e:
        logger.error("Failed to unassign thread", thread_id=thread_id, error=str(e), exc_info=True)
        return error_response(
            error_code='THREAD_UNASSIGNMENT_FAILED',
            message=_('Failed to unassign thread'),
            status_code=500
        )


@inbox_bp.route('/threads/<int:thread_id>/status', methods=['PUT'])
@jwt_required()
@require_tenant()
@require_json(['status'])
@require_permission('inbox.manage_thread')
@log_api_call('update_thread_status')
@audit_log('update_thread_status', 'thread')
def update_thread_status(thread_id):
    """Update thread status."""
    try:
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['status'])
        
        thread = TenantAwareQuery.get_by_id_or_404(Thread, thread_id)
        
        # Validate status value
        valid_statuses = ['open', 'closed', 'archived', 'spam']
        if data['status'] not in valid_statuses:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Invalid status. Valid options: %(statuses)s', 
                         statuses=', '.join(valid_statuses)),
                status_code=400
            )
        
        old_status = thread.status
        
        # Update status using appropriate method
        if data['status'] == 'closed':
            thread.close()
        elif data['status'] == 'open':
            thread.reopen()
        elif data['status'] == 'archived':
            thread.archive()
        elif data['status'] == 'spam':
            thread.mark_as_spam()
        
        thread.save()
        
        logger.info(
            "Thread status updated",
            thread_id=thread_id,
            old_status=old_status,
            new_status=data['status'],
            updated_by_id=get_current_user().id
        )
        
        return success_response(
            message=_('Thread status updated successfully'),
            data={
                'thread_id': thread.id,
                'status': thread.status,
                'ai_enabled': thread.ai_enabled
            }
        )
        
    except Exception as e:
        logger.error("Failed to update thread status", thread_id=thread_id, error=str(e), exc_info=True)
        return error_response(
            error_code='THREAD_STATUS_UPDATE_FAILED',
            message=_('Failed to update thread status'),
            status_code=500
        )


@inbox_bp.route('/search', methods=['GET'])
@jwt_required()
@require_tenant()
@validate_pagination()
@log_api_call('search_messages')
def search_messages():
    """Search messages and threads with advanced filtering."""
    try:
        # Get search parameters
        query_text = request.args.get('q', '').strip()
        if not query_text:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Search query is required'),
                status_code=400
            )
        
        # Get pagination parameters
        page = g.page
        per_page = g.per_page
        
        # Get filter parameters
        search_type = request.args.get('type', 'all')  # messages, threads, all
        channel_id = request.args.get('channel_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        results = {'messages': [], 'threads': []}
        total_count = 0
        
        search_term = f"%{query_text}%"
        
        # Search messages
        if search_type in ['messages', 'all']:
            message_query = InboxMessage.query.filter_by(tenant_id=g.tenant_id)
            
            # Apply search filters
            message_query = message_query.filter(
                or_(
                    InboxMessage.content.ilike(search_term),
                    InboxMessage.sender_name.ilike(search_term),
                    InboxMessage.sender_email.ilike(search_term),
                    InboxMessage.ai_response.ilike(search_term)
                )
            )
            
            # Apply additional filters
            if channel_id:
                message_query = message_query.filter(InboxMessage.channel_id == channel_id)
            
            if date_from:
                message_query = message_query.filter(InboxMessage.created_at >= date_from)
            
            if date_to:
                message_query = message_query.filter(InboxMessage.created_at <= date_to)
            
            # Include related data
            message_query = message_query.options(
                joinedload(InboxMessage.channel),
                joinedload(InboxMessage.thread)
            )
            
            message_query = message_query.order_by(desc(InboxMessage.created_at))
            
            if search_type == 'messages':
                # Paginate messages only
                total_count = message_query.count()
                messages = message_query.offset((page - 1) * per_page).limit(per_page).all()
                results['messages'] = [msg.to_dict() for msg in messages]
            else:
                # Get limited results for combined search
                messages = message_query.limit(per_page // 2).all()
                results['messages'] = [msg.to_dict() for msg in messages]
        
        # Search threads
        if search_type in ['threads', 'all']:
            thread_query = Thread.query.filter_by(tenant_id=g.tenant_id)
            
            # Apply search filters
            thread_query = thread_query.filter(
                or_(
                    Thread.subject.ilike(search_term),
                    Thread.customer_name.ilike(search_term),
                    Thread.customer_email.ilike(search_term),
                    Thread.customer_id.ilike(search_term)
                )
            )
            
            # Apply additional filters
            if channel_id:
                thread_query = thread_query.filter(Thread.channel_id == channel_id)
            
            if date_from:
                thread_query = thread_query.filter(Thread.created_at >= date_from)
            
            if date_to:
                thread_query = thread_query.filter(Thread.created_at <= date_to)
            
            # Include related data
            thread_query = thread_query.options(
                joinedload(Thread.channel),
                joinedload(Thread.assigned_to)
            )
            
            thread_query = thread_query.order_by(desc(Thread.last_message_at))
            
            if search_type == 'threads':
                # Paginate threads only
                total_count = thread_query.count()
                threads = thread_query.offset((page - 1) * per_page).limit(per_page).all()
                results['threads'] = [thread.to_dict() for thread in threads]
            else:
                # Get limited results for combined search
                threads = thread_query.limit(per_page // 2).all()
                results['threads'] = [thread.to_dict() for thread in threads]
        
        # For combined search, calculate total differently
        if search_type == 'all':
            total_count = len(results['messages']) + len(results['threads'])
        
        return paginated_response(
            items=results,
            page=page,
            per_page=per_page,
            total=total_count,
            message=_('Search completed successfully'),
            search_query=query_text,
            search_type=search_type
        )
        
    except Exception as e:
        logger.error("Failed to search messages", error=str(e), exc_info=True)
        return error_response(
            error_code='SEARCH_FAILED',
            message=_('Search failed'),
            status_code=500
        )


@inbox_bp.route('/stats', methods=['GET'])
@jwt_required()
@require_tenant()
@log_api_call('get_inbox_stats')
def get_inbox_stats():
    """Get inbox statistics and metrics."""
    try:
        # Get date range for stats
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Base queries with tenant filtering
        message_query = InboxMessage.query.filter_by(tenant_id=g.tenant_id)
        thread_query = Thread.query.filter_by(tenant_id=g.tenant_id)
        
        # Apply date filters if provided
        if date_from:
            message_query = message_query.filter(InboxMessage.created_at >= date_from)
            thread_query = thread_query.filter(Thread.created_at >= date_from)
        
        if date_to:
            message_query = message_query.filter(InboxMessage.created_at <= date_to)
            thread_query = thread_query.filter(Thread.created_at <= date_to)
        
        # Message statistics
        total_messages = message_query.count()
        inbound_messages = message_query.filter(InboxMessage.direction == 'inbound').count()
        outbound_messages = message_query.filter(InboxMessage.direction == 'outbound').count()
        unread_messages = message_query.filter(
            InboxMessage.direction == 'inbound',
            InboxMessage.is_read == False
        ).count()
        
        # AI processing statistics
        ai_processed_messages = message_query.filter(InboxMessage.ai_processed == True).count()
        pending_ai_messages = message_query.filter(
            InboxMessage.direction == 'inbound',
            InboxMessage.ai_processed == False
        ).count()
        
        # Thread statistics
        total_threads = thread_query.count()
        open_threads = thread_query.filter(Thread.status == 'open').count()
        closed_threads = thread_query.filter(Thread.status == 'closed').count()
        assigned_threads = thread_query.filter(Thread.assigned_to_id.isnot(None)).count()
        unassigned_threads = thread_query.filter(
            Thread.assigned_to_id.is_(None),
            Thread.status == 'open'
        ).count()
        
        # Channel statistics
        channel_stats = []
        channels = Channel.query.filter_by(tenant_id=g.tenant_id, is_active=True).all()
        
        for channel in channels:
            channel_message_count = message_query.filter(InboxMessage.channel_id == channel.id).count()
            channel_thread_count = thread_query.filter(Thread.channel_id == channel.id).count()
            
            channel_stats.append({
                'channel_id': channel.id,
                'channel_name': channel.name,
                'channel_type': channel.type,
                'message_count': channel_message_count,
                'thread_count': channel_thread_count,
                'is_connected': channel.is_connected
            })
        
        stats = {
            'messages': {
                'total': total_messages,
                'inbound': inbound_messages,
                'outbound': outbound_messages,
                'unread': unread_messages,
                'ai_processed': ai_processed_messages,
                'pending_ai': pending_ai_messages
            },
            'threads': {
                'total': total_threads,
                'open': open_threads,
                'closed': closed_threads,
                'assigned': assigned_threads,
                'unassigned': unassigned_threads
            },
            'channels': channel_stats,
            'summary': {
                'needs_attention': unread_messages + unassigned_threads,
                'ai_processing_rate': (ai_processed_messages / max(inbound_messages, 1)) * 100,
                'response_coverage': (outbound_messages / max(inbound_messages, 1)) * 100
            }
        }
        
        return success_response(
            message=_('Inbox statistics retrieved successfully'),
            data=stats
        )
        
    except Exception as e:
        logger.error("Failed to get inbox stats", error=str(e), exc_info=True)
        return error_response(
            error_code='STATS_RETRIEVAL_FAILED',
            message=_('Failed to retrieve inbox statistics'),
            status_code=500
        )