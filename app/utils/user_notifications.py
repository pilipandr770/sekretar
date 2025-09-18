"""
User Notification System

This module provides user-friendly notifications for service unavailability,
configuration issues, and system status updates.
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from flask import current_app, session, request, g
import structlog

logger = structlog.get_logger(__name__)


class NotificationType(Enum):
    """Notification types."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SERVICE_DEGRADED = "service_degraded"
    SERVICE_UNAVAILABLE = "service_unavailable"
    CONFIGURATION_ISSUE = "configuration_issue"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class UserNotification:
    """User notification data structure."""
    id: str
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    dismissible: bool = True
    auto_dismiss: bool = False
    auto_dismiss_delay: int = 5000  # milliseconds
    action_url: Optional[str] = None
    action_text: Optional[str] = None
    service_affected: Optional[str] = None
    resolution_steps: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    shown_to_user: bool = False
    dismissed_by_user: bool = False


class UserNotificationManager:
    """
    Manages user-friendly notifications for service issues and system status.
    """
    
    def __init__(self, app=None):
        """Initialize user notification manager."""
        self.app = app
        self._notifications: Dict[str, UserNotification] = {}
        self._notification_templates: Dict[str, Dict[str, Any]] = {}
        
        # Configuration
        self._max_notifications = 10
        self._default_expiry_hours = 24
        self._auto_cleanup_enabled = True
        
        if app is not None:
            self.init_app(app)
        else:
            self._setup_default_templates()
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['user_notifications'] = self
        
        # Load configuration
        self._max_notifications = app.config.get('MAX_USER_NOTIFICATIONS', 10)
        self._default_expiry_hours = app.config.get('NOTIFICATION_EXPIRY_HOURS', 24)
        self._auto_cleanup_enabled = app.config.get('NOTIFICATION_AUTO_CLEANUP', True)
        
        # Setup notification templates
        self._setup_default_templates()
        
        # Register template context processor
        app.context_processor(self._inject_notifications)
        
        # Register before request handler for cleanup
        app.before_request(self._cleanup_expired_notifications)
        
        logger.info("📢 User notification manager initialized")
    
    def _setup_default_templates(self):
        """Setup default notification templates."""
        self._notification_templates = {
            'database_unavailable': {
                'type': NotificationType.ERROR,
                'priority': NotificationPriority.URGENT,
                'title': 'Database Service Unavailable',
                'message': 'The database service is currently unavailable. Some features may not work properly.',
                'dismissible': False,
                'auto_dismiss': False
            },
            'database_degraded': {
                'type': NotificationType.WARNING,
                'priority': NotificationPriority.MEDIUM,
                'title': 'Database Running in Compatibility Mode',
                'message': 'The database is running in compatibility mode. Performance may be reduced.',
                'dismissible': True,
                'auto_dismiss': False
            },
            'cache_unavailable': {
                'type': NotificationType.WARNING,
                'priority': NotificationPriority.LOW,
                'title': 'Caching Service Unavailable',
                'message': 'The caching service is unavailable. The application may respond more slowly.',
                'dismissible': True,
                'auto_dismiss': True,
                'auto_dismiss_delay': 10000
            },
            'ai_features_disabled': {
                'type': NotificationType.INFO,
                'priority': NotificationPriority.LOW,
                'title': 'AI Features Unavailable',
                'message': 'AI-powered features are currently unavailable due to service configuration.',
                'dismissible': True,
                'auto_dismiss': False
            },
            'payment_disabled': {
                'type': NotificationType.WARNING,
                'priority': NotificationPriority.MEDIUM,
                'title': 'Payment Processing Unavailable',
                'message': 'Payment processing is currently unavailable. Billing features are disabled.',
                'dismissible': True,
                'auto_dismiss': False
            },
            'oauth_disabled': {
                'type': NotificationType.INFO,
                'priority': NotificationPriority.LOW,
                'title': 'Social Login Unavailable',
                'message': 'Social login options are currently unavailable. Please use email/password login.',
                'dismissible': True,
                'auto_dismiss': False
            },
            'messaging_disabled': {
                'type': NotificationType.INFO,
                'priority': NotificationPriority.LOW,
                'title': 'Messaging Integration Unavailable',
                'message': 'Messaging integrations (Telegram, Signal) are currently unavailable.',
                'dismissible': True,
                'auto_dismiss': False
            },
            'configuration_error': {
                'type': NotificationType.ERROR,
                'priority': NotificationPriority.HIGH,
                'title': 'Configuration Issue Detected',
                'message': 'A configuration issue has been detected that may affect system functionality.',
                'dismissible': False,
                'auto_dismiss': False
            },
            'database_connection_failed': {
                'type': NotificationType.ERROR,
                'priority': NotificationPriority.URGENT,
                'title': 'Database Connection Failed',
                'message': 'Unable to connect to the database. The system is running in limited mode.',
                'dismissible': False,
                'auto_dismiss': False,
                'resolution_steps': [
                    'Check database service status',
                    'Verify database connection settings',
                    'Contact system administrator'
                ]
            },
            'weak_security_config': {
                'type': NotificationType.WARNING,
                'priority': NotificationPriority.HIGH,
                'title': 'Security Configuration Warning',
                'message': 'Weak security configuration detected. Please review and strengthen security settings.',
                'dismissible': True,
                'auto_dismiss': False,
                'resolution_steps': [
                    'Generate strong secret keys',
                    'Review security configuration',
                    'Update environment variables'
                ]
            },
            'file_permissions_issue': {
                'type': NotificationType.WARNING,
                'priority': NotificationPriority.MEDIUM,
                'title': 'File Permissions Issue',
                'message': 'File or directory permissions may prevent proper system operation.',
                'dismissible': True,
                'auto_dismiss': False,
                'resolution_steps': [
                    'Check file and directory permissions',
                    'Ensure application has write access',
                    'Create missing directories'
                ]
            },
            'service_recovered': {
                'type': NotificationType.SUCCESS,
                'priority': NotificationPriority.MEDIUM,
                'title': 'Service Restored',
                'message': 'A previously unavailable service has been restored.',
                'dismissible': True,
                'auto_dismiss': True,
                'auto_dismiss_delay': 8000
            }
        }
    
    def _inject_notifications(self):
        """Inject notifications into template context."""
        return {
            'user_notifications': self.get_active_notifications(),
            'notification_count': len(self.get_active_notifications())
        }
    
    def _cleanup_expired_notifications(self):
        """Clean up expired notifications."""
        if not self._auto_cleanup_enabled:
            return
        
        current_time = datetime.now()
        expired_ids = []
        
        for notification_id, notification in self._notifications.items():
            if notification.expires_at and current_time > notification.expires_at:
                expired_ids.append(notification_id)
        
        for notification_id in expired_ids:
            del self._notifications[notification_id]
            logger.debug(f"Cleaned up expired notification: {notification_id}")
    
    def create_notification(
        self,
        notification_id: str,
        type: NotificationType,
        priority: NotificationPriority,
        title: str,
        message: str,
        **kwargs
    ) -> UserNotification:
        """Create a new user notification."""
        # Set expiry time
        expires_at = None
        if kwargs.get('expires_in_hours'):
            expires_at = datetime.now() + timedelta(hours=kwargs['expires_in_hours'])
        elif not kwargs.get('no_expiry', False):
            expires_at = datetime.now() + timedelta(hours=self._default_expiry_hours)
        
        notification = UserNotification(
            id=notification_id,
            type=type,
            priority=priority,
            title=title,
            message=message,
            dismissible=kwargs.get('dismissible', True),
            auto_dismiss=kwargs.get('auto_dismiss', False),
            auto_dismiss_delay=kwargs.get('auto_dismiss_delay', 5000),
            action_url=kwargs.get('action_url'),
            action_text=kwargs.get('action_text'),
            service_affected=kwargs.get('service_affected'),
            resolution_steps=kwargs.get('resolution_steps', []),
            expires_at=expires_at
        )
        
        # Limit number of notifications
        if len(self._notifications) >= self._max_notifications:
            # Remove oldest notification
            oldest_id = min(self._notifications.keys(), 
                           key=lambda k: self._notifications[k].timestamp)
            del self._notifications[oldest_id]
            logger.debug(f"Removed oldest notification to make room: {oldest_id}")
        
        self._notifications[notification_id] = notification
        
        logger.info(
            "User notification created",
            notification_id=notification_id,
            type=type.value,
            priority=priority.value,
            title=title
        )
        
        return notification
    
    def create_from_template(
        self,
        notification_id: str,
        template_name: str,
        **kwargs
    ) -> Optional[UserNotification]:
        """Create notification from template."""
        template = self._notification_templates.get(template_name)
        if not template:
            logger.error(f"Notification template not found: {template_name}")
            return None
        
        # Merge template with kwargs
        notification_data = template.copy()
        notification_data.update(kwargs)
        
        return self.create_notification(
            notification_id=notification_id,
            type=notification_data['type'],
            priority=notification_data['priority'],
            title=notification_data['title'],
            message=notification_data['message'],
            **{k: v for k, v in notification_data.items() 
               if k not in ['type', 'priority', 'title', 'message']}
        )
    
    def update_notification(
        self,
        notification_id: str,
        **kwargs
    ) -> Optional[UserNotification]:
        """Update an existing notification."""
        if notification_id not in self._notifications:
            return None
        
        notification = self._notifications[notification_id]
        
        # Update fields
        for field, value in kwargs.items():
            if hasattr(notification, field):
                setattr(notification, field, value)
        
        logger.debug(f"Updated notification: {notification_id}")
        return notification
    
    def dismiss_notification(self, notification_id: str) -> bool:
        """Dismiss a notification."""
        if notification_id not in self._notifications:
            return False
        
        self._notifications[notification_id].dismissed_by_user = True
        logger.debug(f"Dismissed notification: {notification_id}")
        return True
    
    def remove_notification(self, notification_id: str) -> bool:
        """Remove a notification completely."""
        if notification_id not in self._notifications:
            return False
        
        del self._notifications[notification_id]
        logger.debug(f"Removed notification: {notification_id}")
        return True
    
    def get_notification(self, notification_id: str) -> Optional[UserNotification]:
        """Get a specific notification."""
        return self._notifications.get(notification_id)
    
    def get_active_notifications(self) -> List[UserNotification]:
        """Get all active (non-dismissed, non-expired) notifications."""
        current_time = datetime.now()
        active = []
        
        for notification in self._notifications.values():
            # Skip dismissed notifications
            if notification.dismissed_by_user:
                continue
            
            # Skip expired notifications
            if notification.expires_at and current_time > notification.expires_at:
                continue
            
            active.append(notification)
        
        # Sort by priority and timestamp
        priority_order = {
            NotificationPriority.URGENT: 0,
            NotificationPriority.HIGH: 1,
            NotificationPriority.MEDIUM: 2,
            NotificationPriority.LOW: 3
        }
        
        active.sort(key=lambda n: (priority_order[n.priority], n.timestamp))
        return active
    
    def get_notifications_by_type(self, notification_type: NotificationType) -> List[UserNotification]:
        """Get notifications by type."""
        return [n for n in self._notifications.values() if n.type == notification_type]
    
    def get_notifications_by_service(self, service_name: str) -> List[UserNotification]:
        """Get notifications for a specific service."""
        return [n for n in self._notifications.values() 
                if n.service_affected == service_name]
    
    def clear_notifications_by_type(self, notification_type: NotificationType):
        """Clear all notifications of a specific type."""
        to_remove = [n.id for n in self._notifications.values() if n.type == notification_type]
        for notification_id in to_remove:
            del self._notifications[notification_id]
        
        logger.info(f"Cleared {len(to_remove)} notifications of type: {notification_type.value}")
    
    def clear_notifications_by_service(self, service_name: str):
        """Clear all notifications for a specific service."""
        to_remove = [n.id for n in self._notifications.values() 
                    if n.service_affected == service_name]
        for notification_id in to_remove:
            del self._notifications[notification_id]
        
        logger.info(f"Cleared {len(to_remove)} notifications for service: {service_name}")
    
    def clear_all_notifications(self):
        """Clear all notifications."""
        count = len(self._notifications)
        self._notifications.clear()
        logger.info(f"Cleared all {count} notifications")
    
    def notify_service_degradation(self, service_name: str, level: str, reason: str):
        """Create notification for service degradation."""
        notification_id = f"service_degraded_{service_name}"
        
        if level == 'unavailable':
            template_name = f"{service_name}_unavailable"
            if template_name not in self._notification_templates:
                template_name = 'configuration_error'
        else:
            template_name = f"{service_name}_degraded"
            if template_name not in self._notification_templates:
                template_name = 'cache_unavailable'  # Generic degradation template
        
        self.create_from_template(
            notification_id=notification_id,
            template_name=template_name,
            service_affected=service_name,
            message=f"{service_name.title()} service is {level}: {reason}"
        )
    
    def notify_service_recovery(self, service_name: str):
        """Create notification for service recovery."""
        # Remove existing degradation notifications for this service
        self.clear_notifications_by_service(service_name)
        
        # Create recovery notification
        notification_id = f"service_recovered_{service_name}"
        self.create_from_template(
            notification_id=notification_id,
            template_name='service_recovered',
            service_affected=service_name,
            message=f"{service_name.title()} service has been restored and is now available."
        )
    
    def notify_configuration_issue(self, issue_type: str, message: str, severity: str):
        """Create notification for configuration issue."""
        notification_id = f"config_issue_{issue_type}"
        
        priority_mapping = {
            'low': NotificationPriority.LOW,
            'medium': NotificationPriority.MEDIUM,
            'high': NotificationPriority.HIGH,
            'critical': NotificationPriority.URGENT
        }
        
        self.create_notification(
            notification_id=notification_id,
            type=NotificationType.CONFIGURATION_ISSUE,
            priority=priority_mapping.get(severity, NotificationPriority.MEDIUM),
            title=f"Configuration Issue: {issue_type.replace('_', ' ').title()}",
            message=message,
            dismissible=severity not in ['critical', 'high'],
            auto_dismiss=False
        )
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification statistics."""
        active_notifications = self.get_active_notifications()
        
        stats = {
            'total_notifications': len(self._notifications),
            'active_notifications': len(active_notifications),
            'dismissed_notifications': len([n for n in self._notifications.values() 
                                          if n.dismissed_by_user]),
            'by_type': {},
            'by_priority': {},
            'by_service': {}
        }
        
        # Count by type
        for notification in active_notifications:
            type_name = notification.type.value
            stats['by_type'][type_name] = stats['by_type'].get(type_name, 0) + 1
        
        # Count by priority
        for notification in active_notifications:
            priority_name = notification.priority.value
            stats['by_priority'][priority_name] = stats['by_priority'].get(priority_name, 0) + 1
        
        # Count by service
        for notification in active_notifications:
            if notification.service_affected:
                service_name = notification.service_affected
                stats['by_service'][service_name] = stats['by_service'].get(service_name, 0) + 1
        
        return stats


# Global instance
_user_notification_manager = None


def get_user_notification_manager(app=None) -> UserNotificationManager:
    """Get or create user notification manager instance."""
    global _user_notification_manager
    
    if _user_notification_manager is None:
        _user_notification_manager = UserNotificationManager(app)
    elif app is not None and _user_notification_manager.app is None:
        _user_notification_manager.init_app(app)
    
    return _user_notification_manager


def init_user_notifications(app):
    """Initialize user notifications for Flask app."""
    manager = get_user_notification_manager(app)
    return manager