"""API endpoints for notification management."""
from datetime import datetime
from typing import Dict, Any, List
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models import (
    Notification, NotificationTemplate, NotificationPreference,
    NotificationType, NotificationPriority, NotificationStatus
)
from app.services.notification_service import NotificationService
from app.services.notification_templates import NotificationTemplateManager
from app.utils.auth import require_permission
from app.utils.validation import validate_json
from app.utils.database import db

notifications_bp = Blueprint('notifications', __name__, url_prefix='/api/v1/notifications')
notification_service = NotificationService()


@notifications_bp.route('/', methods=['POST'])
@jwt_required()
@require_permission('notifications:create')
def create_notification():
    """Create a new notification."""
    try:
        current_user = get_jwt_identity()
        
        # Validate JSON request
        validate_json(request, ['recipient', 'type', 'body'])
        data = request.get_json()
        
        notification = notification_service.create_notification(
            tenant_id=current_user['tenant_id'],
            recipient=data['recipient'],
            notification_type=data['type'],
            subject=data.get('subject'),
            body=data['body'],
            html_body=data.get('html_body'),
            user_id=data.get('user_id'),
            template_id=data.get('template_id'),
            priority=data.get('priority', 'normal'),
            scheduled_at=datetime.fromisoformat(data['scheduled_at']) if data.get('scheduled_at') else None,
            variables=data.get('variables', {}),
            max_retries=data.get('max_retries', 3)
        )
        
        # Queue for sending if not scheduled
        if not notification.scheduled_at:
            task_id = notification_service.send_notification_async(notification.id)
        else:
            task_id = None
        
        return jsonify({
            'id': notification.id,
            'status': notification.status,
            'task_id': task_id,
            'created_at': notification.created_at.isoformat()
        }), 201
    
    except Exception as e:
        current_app.logger.error(f"Error creating notification: {str(e)}")
        return jsonify({'error': 'Failed to create notification'}), 500


@notifications_bp.route('/<notification_id>', methods=['GET'])
@jwt_required()
@require_permission('notifications:read')
def get_notification(notification_id: str):
    """Get notification status and details."""
    try:
        current_user = get_jwt_identity()
        
        # Verify notification belongs to tenant
        notification = Notification.query.filter_by(
            id=notification_id,
            tenant_id=current_user['tenant_id']
        ).first()
        
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404
        
        status = notification_service.get_notification_status(notification_id)
        return jsonify(status)
    
    except Exception as e:
        current_app.logger.error(f"Error getting notification: {str(e)}")
        return jsonify({'error': 'Failed to get notification'}), 500


@notifications_bp.route('/', methods=['GET'])
@jwt_required()
@require_permission('notifications:read')
def list_notifications():
    """List notifications for the tenant."""
    try:
        current_user = get_jwt_identity()
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        status = request.args.get('status')
        notification_type = request.args.get('type')
        user_id = request.args.get('user_id')
        
        # Build query
        query = Notification.query.filter_by(tenant_id=current_user['tenant_id'])
        
        if status:
            query = query.filter_by(status=status)
        if notification_type:
            query = query.filter_by(type=notification_type)
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        # Order by creation date (newest first)
        query = query.order_by(Notification.created_at.desc())
        
        # Paginate
        notifications = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'notifications': [
                {
                    'id': n.id,
                    'type': n.type,
                    'recipient': n.recipient,
                    'subject': n.subject,
                    'status': n.status,
                    'priority': n.priority,
                    'created_at': n.created_at.isoformat() if n.created_at else None,
                    'sent_at': n.sent_at.isoformat() if n.sent_at else None,
                    'retry_count': n.retry_count,
                    'error_message': n.error_message
                }
                for n in notifications.items
            ],
            'pagination': {
                'page': notifications.page,
                'pages': notifications.pages,
                'per_page': notifications.per_page,
                'total': notifications.total,
                'has_next': notifications.has_next,
                'has_prev': notifications.has_prev
            }
        })
    
    except Exception as e:
        current_app.logger.error(f"Error listing notifications: {str(e)}")
        return jsonify({'error': 'Failed to list notifications'}), 500


@notifications_bp.route('/bulk', methods=['POST'])
@jwt_required()
@require_permission('notifications:create')
def create_bulk_notifications():
    """Create multiple notifications in bulk."""
    try:
        current_user = get_jwt_identity()
        
        # Validate JSON request
        validate_json(request, ['notifications'])
        data = request.get_json()
        
        notifications = []
        notification_ids = []
        
        for notif_data in data['notifications']:
            notification = notification_service.create_notification(
                tenant_id=current_user['tenant_id'],
                recipient=notif_data['recipient'],
                notification_type=notif_data['type'],
                subject=notif_data.get('subject'),
                body=notif_data['body'],
                html_body=notif_data.get('html_body'),
                user_id=notif_data.get('user_id'),
                template_id=notif_data.get('template_id'),
                priority=notif_data.get('priority', 'normal'),
                scheduled_at=datetime.fromisoformat(notif_data['scheduled_at']) if notif_data.get('scheduled_at') else None,
                variables=notif_data.get('variables', {}),
                max_retries=notif_data.get('max_retries', 3)
            )
            
            notifications.append({
                'id': notification.id,
                'status': notification.status,
                'created_at': notification.created_at.isoformat()
            })
            
            # Only queue unscheduled notifications
            if not notification.scheduled_at:
                notification_ids.append(notification.id)
        
        # Queue for bulk sending
        task_id = None
        if notification_ids:
            task_id = notification_service.send_bulk_notifications(notification_ids)
        
        return jsonify({
            'notifications': notifications,
            'bulk_task_id': task_id,
            'queued_count': len(notification_ids)
        }), 201
    
    except Exception as e:
        current_app.logger.error(f"Error creating bulk notifications: {str(e)}")
        return jsonify({'error': 'Failed to create bulk notifications'}), 500


@notifications_bp.route('/send-to-user', methods=['POST'])
@jwt_required()
@require_permission('notifications:create')
def send_to_user_preferences():
    """Send notification based on user preferences."""
    try:
        current_user = get_jwt_identity()
        
        # Validate JSON request
        validate_json(request, ['user_id', 'event_type', 'data'])
        data = request.get_json()
        
        task_ids = notification_service.send_to_user_preferences(
            user_id=data['user_id'],
            event_type=data['event_type'],
            data=data['data'],
            priority=data.get('priority', 'normal')
        )
        
        return jsonify({
            'task_ids': task_ids,
            'queued_count': len(task_ids)
        })
    
    except Exception as e:
        current_app.logger.error(f"Error sending to user preferences: {str(e)}")
        return jsonify({'error': 'Failed to send notifications'}), 500


# Notification Preferences endpoints
@notifications_bp.route('/preferences', methods=['GET'])
@jwt_required()
@require_permission('notifications:read')
def get_user_preferences():
    """Get current user's notification preferences."""
    try:
        current_user = get_jwt_identity()
        user_id = request.args.get('user_id', current_user['user_id'])
        
        preferences = notification_service.get_user_preferences(user_id)
        return jsonify({'preferences': preferences})
    
    except Exception as e:
        current_app.logger.error(f"Error getting preferences: {str(e)}")
        return jsonify({'error': 'Failed to get preferences'}), 500


@notifications_bp.route('/preferences', methods=['POST'])
@jwt_required()
@require_permission('notifications:manage')
def set_user_preference():
    """Set user notification preference."""
    try:
        current_user = get_jwt_identity()
        
        # Validate JSON request
        validate_json(request, ['event_type', 'notification_type', 'delivery_address'])
        data = request.get_json()
        
        user_id = data.get('user_id', current_user['user_id'])
        
        preference = notification_service.set_user_preference(
            user_id=user_id,
            tenant_id=current_user['tenant_id'],
            event_type=data['event_type'],
            notification_type=data['notification_type'],
            delivery_address=data['delivery_address'],
            is_enabled=data.get('is_enabled', True),
            settings=data.get('settings', {})
        )
        
        return jsonify({
            'id': preference.id,
            'event_type': preference.event_type,
            'notification_type': preference.notification_type,
            'delivery_address': preference.delivery_address,
            'is_enabled': preference.is_enabled,
            'settings': preference.settings
        })
    
    except Exception as e:
        current_app.logger.error(f"Error setting preference: {str(e)}")
        return jsonify({'error': 'Failed to set preference'}), 500


# Template management endpoints
@notifications_bp.route('/templates', methods=['GET'])
@jwt_required()
@require_permission('notifications:read')
def list_templates():
    """List notification templates."""
    try:
        current_user = get_jwt_identity()
        notification_type = request.args.get('type')
        
        templates = NotificationTemplateManager.list_templates(
            current_user['tenant_id'],
            notification_type
        )
        
        return jsonify({
            'templates': [
                {
                    'id': t.id,
                    'name': t.name,
                    'type': t.type,
                    'subject_template': t.subject_template,
                    'body_template': t.body_template,
                    'html_template': t.html_template,
                    'variables': t.variables,
                    'is_active': t.is_active,
                    'created_at': t.created_at.isoformat() if t.created_at else None
                }
                for t in templates
            ]
        })
    
    except Exception as e:
        current_app.logger.error(f"Error listing templates: {str(e)}")
        return jsonify({'error': 'Failed to list templates'}), 500


@notifications_bp.route('/templates/create-defaults', methods=['POST'])
@jwt_required()
@require_permission('notifications:manage')
def create_default_templates():
    """Create default notification templates for the tenant."""
    try:
        current_user = get_jwt_identity()
        
        templates = NotificationTemplateManager.create_default_templates(
            current_user['tenant_id']
        )
        
        return jsonify({
            'created_count': len(templates),
            'templates': [
                {
                    'id': t.id,
                    'name': t.name,
                    'type': t.type
                }
                for t in templates
            ]
        })
    
    except Exception as e:
        current_app.logger.error(f"Error creating default templates: {str(e)}")
        return jsonify({'error': 'Failed to create default templates'}), 500


@notifications_bp.route('/templates/<template_id>', methods=['PUT'])
@jwt_required()
@require_permission('notifications:manage')
def update_template(template_id: str):
    """Update a notification template."""
    try:
        current_user = get_jwt_identity()
        data = request.get_json()
        
        # Verify template belongs to tenant
        template = NotificationTemplate.query.filter_by(
            id=template_id,
            tenant_id=current_user['tenant_id']
        ).first()
        
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        
        updated_template = NotificationTemplateManager.update_template(
            template_id,
            subject_template=data.get('subject_template'),
            body_template=data.get('body_template'),
            html_template=data.get('html_template'),
            variables=data.get('variables')
        )
        
        return jsonify({
            'id': updated_template.id,
            'name': updated_template.name,
            'type': updated_template.type,
            'subject_template': updated_template.subject_template,
            'body_template': updated_template.body_template,
            'html_template': updated_template.html_template,
            'variables': updated_template.variables,
            'updated_at': updated_template.updated_at.isoformat() if updated_template.updated_at else None
        })
    
    except Exception as e:
        current_app.logger.error(f"Error updating template: {str(e)}")
        return jsonify({'error': 'Failed to update template'}), 500


# Statistics and monitoring endpoints
@notifications_bp.route('/stats', methods=['GET'])
@jwt_required()
@require_permission('notifications:read')
def get_notification_stats():
    """Get notification statistics for the tenant."""
    try:
        current_user = get_jwt_identity()
        
        # Get counts by status
        stats = {}
        for status in NotificationStatus:
            count = Notification.query.filter_by(
                tenant_id=current_user['tenant_id'],
                status=status.value
            ).count()
            stats[status.value] = count
        
        # Get counts by type
        type_stats = {}
        for notif_type in NotificationType:
            count = Notification.query.filter_by(
                tenant_id=current_user['tenant_id'],
                type=notif_type.value
            ).count()
            type_stats[notif_type.value] = count
        
        # Get recent activity (last 24 hours)
        from datetime import timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_count = Notification.query.filter(
            Notification.tenant_id == current_user['tenant_id'],
            Notification.created_at >= yesterday
        ).count()
        
        return jsonify({
            'status_counts': stats,
            'type_counts': type_stats,
            'recent_24h': recent_count,
            'total': sum(stats.values())
        })
    
    except Exception as e:
        current_app.logger.error(f"Error getting notification stats: {str(e)}")
        return jsonify({'error': 'Failed to get statistics'}), 500