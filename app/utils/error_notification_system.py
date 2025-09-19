"""
Error Notification System

This module provides a comprehensive error notification system that integrates
with the frontend error display component and provides real-time error notifications.
"""
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from flask import current_app, request, session, g
from flask_socketio import emit
import structlog

logger = structlog.get_logger(__name__)


class ErrorNotificationSystem:
    """
    Comprehensive error notification system that provides real-time
    error notifications to users and administrators.
    """
    
    def __init__(self, app=None):
        """Initialize error notification system."""
        self.app = app
        self._notification_callbacks: List[Callable] = []
        self._error_thresholds = {
            'critical': 0,  # Always notify
            'high': 1,      # Notify after 1 occurrence
            'medium': 3,    # Notify after 3 occurrences
            'low': 5        # Notify after 5 occurrences
        }
        self._error_counts: Dict[str, int] = {}
        self._last_notifications: Dict[str, datetime] = {}
        self._notification_cooldown = timedelta(minutes=5)
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['error_notification_system'] = self
        
        # Load configuration
        self._error_thresholds.update(app.config.get('ERROR_NOTIFICATION_THRESHOLDS', {}))
        cooldown_minutes = app.config.get('ERROR_NOTIFICATION_COOLDOWN_MINUTES', 5)
        self._notification_cooldown = timedelta(minutes=cooldown_minutes)
        
        # Register error notification routes
        self._register_notification_routes()
        
        logger.info("🔔 Error notification system initialized")
    
    def _register_notification_routes(self):
        """Register error notification API routes."""
        
        @self.app.route('/api/v1/notifications/errors')
        def get_error_notifications():
            """Get current error notifications for the user."""
            try:
                from flask import jsonify
                
                # Get user notifications
                notifications = self._get_user_error_notifications()
                
                return jsonify({
                    'status': 'success',
                    'data': {
                        'notifications': notifications,
                        'count': len(notifications)
                    }
                })
                
            except Exception as e:
                logger.error(f"Failed to get error notifications: {e}")
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to retrieve error notifications'
                }), 500
        
        @self.app.route('/api/v1/notifications/errors/<notification_id>/dismiss', methods=['POST'])
        def dismiss_error_notification(notification_id: str):
            """Dismiss an error notification."""
            try:
                from flask import jsonify
                
                # Dismiss the notification
                success = self._dismiss_notification(notification_id)
                
                if success:
                    return jsonify({
                        'status': 'success',
                        'message': 'Notification dismissed'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Notification not found'
                    }), 404
                    
            except Exception as e:
                logger.error(f"Failed to dismiss error notification: {e}")
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to dismiss notification'
                }), 500
    
    def add_notification_callback(self, callback: Callable):
        """Add callback to be called when notifications are created."""
        self._notification_callbacks.append(callback)
    
    def notify_error(
        self,
        error: Exception,
        context: Dict[str, Any] = None,
        severity: str = 'medium',
        user_message: Optional[str] = None,
        admin_message: Optional[str] = None,
        resolution_steps: Optional[List[str]] = None
    ):
        """
        Notify about an error occurrence.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            severity: Error severity ('critical', 'high', 'medium', 'low')
            user_message: Custom user-friendly message
            admin_message: Custom admin message
            resolution_steps: List of resolution steps
        """
        try:
            context = context or {}
            error_key = self._generate_error_key(error, context)
            
            # Update error count
            self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
            error_count = self._error_counts[error_key]
            
            # Check if we should notify based on threshold
            threshold = self._error_thresholds.get(severity, 1)
            if error_count < threshold:
                return
            
            # Check cooldown period
            last_notification = self._last_notifications.get(error_key)
            if last_notification and datetime.now() - last_notification < self._notification_cooldown:
                return
            
            # Create error notification
            notification_data = self._create_error_notification(
                error=error,
                context=context,
                severity=severity,
                error_count=error_count,
                user_message=user_message,
                admin_message=admin_message,
                resolution_steps=resolution_steps
            )
            
            # Send notification
            self._send_notification(notification_data)
            
            # Update last notification time
            self._last_notifications[error_key] = datetime.now()
            
            # Call notification callbacks
            for callback in self._notification_callbacks:
                try:
                    callback(notification_data)
                except Exception as callback_error:
                    logger.error(f"Notification callback failed: {callback_error}")
            
            logger.info(f"Error notification sent: {error_key} (severity: {severity}, count: {error_count})")
            
        except Exception as e:
            logger.error(f"Failed to notify error: {e}")
    
    def _generate_error_key(self, error: Exception, context: Dict[str, Any]) -> str:
        """Generate unique key for error type."""
        error_type = type(error).__name__
        service_name = context.get('service_name', 'unknown')
        function_name = context.get('function', 'unknown')
        
        return f"{service_name}_{error_type}_{function_name}"
    
    def _create_error_notification(
        self,
        error: Exception,
        context: Dict[str, Any],
        severity: str,
        error_count: int,
        user_message: Optional[str] = None,
        admin_message: Optional[str] = None,
        resolution_steps: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create error notification data."""
        
        # Get multilingual error message if available
        try:
            from app.utils.multilingual_errors import create_localized_error_response
            localized_response = create_localized_error_response(
                error=error,
                context=context,
                include_technical_details=current_app.config.get('DEBUG', False)
            )
            
            title = localized_response.get('title', 'Error')
            message = user_message or localized_response.get('user_message', str(error))
            resolution_steps = resolution_steps or localized_response.get('resolution_steps', [])
            
        except Exception as e:
            logger.warning(f"Failed to get localized error message: {e}")
            title = 'Error'
            message = user_message or str(error)
            resolution_steps = resolution_steps or []
        
        # Determine notification type and priority
        notification_type = self._get_notification_type(severity)
        priority = self._get_notification_priority(severity)
        
        # Create notification data
        notification_data = {
            'id': f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(str(error)) % 10000}",
            'type': notification_type,
            'priority': priority,
            'severity': severity,
            'title': title,
            'message': message,
            'error_type': type(error).__name__,
            'error_count': error_count,
            'service_affected': context.get('service_name'),
            'resolution_steps': resolution_steps,
            'timestamp': datetime.now().isoformat(),
            'dismissible': severity not in ['critical'],
            'auto_dismiss': severity in ['low'],
            'auto_dismiss_delay': 10000 if severity == 'low' else None,
            'context': context
        }
        
        # Add technical details for admin notifications
        if admin_message or current_app.config.get('DEBUG', False):
            notification_data['technical_details'] = {
                'error_message': str(error),
                'error_type': type(error).__name__,
                'admin_message': admin_message,
                'context': context
            }
        
        return notification_data
    
    def _get_notification_type(self, severity: str) -> str:
        """Get notification type based on severity."""
        type_mapping = {
            'critical': 'error',
            'high': 'error',
            'medium': 'warning',
            'low': 'info'
        }
        return type_mapping.get(severity, 'warning')
    
    def _get_notification_priority(self, severity: str) -> str:
        """Get notification priority based on severity."""
        priority_mapping = {
            'critical': 'urgent',
            'high': 'high',
            'medium': 'medium',
            'low': 'low'
        }
        return priority_mapping.get(severity, 'medium')
    
    def _send_notification(self, notification_data: Dict[str, Any]):
        """Send notification to appropriate channels."""
        
        # 1. Send to user notification manager
        self._send_to_user_notification_manager(notification_data)
        
        # 2. Send real-time notification via WebSocket
        self._send_realtime_notification(notification_data)
        
        # 3. Store in session for page reload
        self._store_session_notification(notification_data)
        
        # 4. Send to admin channels if critical
        if notification_data['severity'] == 'critical':
            self._send_admin_notification(notification_data)
    
    def _send_to_user_notification_manager(self, notification_data: Dict[str, Any]):
        """Send notification to user notification manager."""
        try:
            if current_app and 'ERROR_HANDLERS' in current_app.config:
                error_handlers = current_app.config['ERROR_HANDLERS']
                notification_manager = error_handlers.get('user_notifications')
                
                if notification_manager:
                    # Convert to notification manager format
                    notification_manager.create_notification(
                        notification_id=notification_data['id'],
                        type=getattr(notification_manager.NotificationType, notification_data['type'].upper()),
                        priority=getattr(notification_manager.NotificationPriority, notification_data['priority'].upper()),
                        title=notification_data['title'],
                        message=notification_data['message'],
                        dismissible=notification_data['dismissible'],
                        auto_dismiss=notification_data['auto_dismiss'],
                        auto_dismiss_delay=notification_data.get('auto_dismiss_delay'),
                        service_affected=notification_data.get('service_affected'),
                        resolution_steps=notification_data.get('resolution_steps', [])
                    )
                    
        except Exception as e:
            logger.error(f"Failed to send to user notification manager: {e}")
    
    def _send_realtime_notification(self, notification_data: Dict[str, Any]):
        """Send real-time notification via WebSocket."""
        try:
            from app.utils.websocket_manager import emit_with_fallback
            
            def fallback(event, data, room):
                # Store in session as fallback
                self._store_session_notification(data)
            
            # Emit to current user's session
            emit_with_fallback('error_notification', notification_data, fallback_callback=fallback)
            
            # For critical errors, broadcast to all admin users
            if notification_data['severity'] == 'critical':
                emit_with_fallback('admin_error_notification', notification_data, room='admin', fallback_callback=fallback)
                    
        except Exception as e:
            logger.error(f"Failed to send real-time notification: {e}")
            # Fallback to session storage
            self._store_session_notification(notification_data)
    
    def _store_session_notification(self, notification_data: Dict[str, Any]):
        """Store notification in session for page reload."""
        try:
            if 'error_notifications' not in session:
                session['error_notifications'] = []
            
            # Limit stored notifications
            session['error_notifications'].append(notification_data)
            if len(session['error_notifications']) > 10:
                session['error_notifications'] = session['error_notifications'][-10:]
            
            session.modified = True
            
        except Exception as e:
            logger.error(f"Failed to store session notification: {e}")
    
    def _send_admin_notification(self, notification_data: Dict[str, Any]):
        """Send notification to admin channels."""
        try:
            # Log critical error for admin attention
            logger.critical(
                "Critical error notification",
                notification_id=notification_data['id'],
                error_type=notification_data['error_type'],
                service_affected=notification_data.get('service_affected'),
                error_count=notification_data['error_count']
            )
            
            # Could integrate with external alerting systems here
            # (e.g., Slack, email, PagerDuty, etc.)
            
        except Exception as e:
            logger.error(f"Failed to send admin notification: {e}")
    
    def _get_user_error_notifications(self) -> List[Dict[str, Any]]:
        """Get current error notifications for the user."""
        notifications = []
        
        try:
            # Get from session
            session_notifications = session.get('error_notifications', [])
            
            # Filter out expired notifications
            current_time = datetime.now()
            for notification in session_notifications:
                notification_time = datetime.fromisoformat(notification['timestamp'])
                
                # Remove notifications older than 1 hour
                if current_time - notification_time < timedelta(hours=1):
                    notifications.append(notification)
            
            # Update session with filtered notifications
            session['error_notifications'] = notifications
            session.modified = True
            
        except Exception as e:
            logger.error(f"Failed to get user error notifications: {e}")
        
        return notifications
    
    def _dismiss_notification(self, notification_id: str) -> bool:
        """Dismiss a specific notification."""
        try:
            session_notifications = session.get('error_notifications', [])
            
            # Remove notification with matching ID
            updated_notifications = [
                n for n in session_notifications 
                if n.get('id') != notification_id
            ]
            
            if len(updated_notifications) < len(session_notifications):
                session['error_notifications'] = updated_notifications
                session.modified = True
                return True
            
        except Exception as e:
            logger.error(f"Failed to dismiss notification: {e}")
        
        return False
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error notification statistics."""
        return {
            'total_errors': sum(self._error_counts.values()),
            'unique_error_types': len(self._error_counts),
            'error_counts': self._error_counts.copy(),
            'notification_thresholds': self._error_thresholds.copy(),
            'active_notifications': len(self._last_notifications),
            'cooldown_period_minutes': self._notification_cooldown.total_seconds() / 60
        }
    
    def clear_error_counts(self):
        """Clear error counts (useful for testing or reset)."""
        self._error_counts.clear()
        self._last_notifications.clear()
        logger.info("Error notification counts cleared")


# Global instance
_error_notification_system = None


def get_error_notification_system(app=None) -> ErrorNotificationSystem:
    """Get or create error notification system instance."""
    global _error_notification_system
    
    if _error_notification_system is None:
        _error_notification_system = ErrorNotificationSystem(app)
    elif app is not None and _error_notification_system.app is None:
        _error_notification_system.init_app(app)
    
    return _error_notification_system


def init_error_notification_system(app):
    """Initialize error notification system for Flask app."""
    system = get_error_notification_system(app)
    return system


def notify_error(
    error: Exception,
    context: Dict[str, Any] = None,
    severity: str = 'medium',
    user_message: Optional[str] = None,
    admin_message: Optional[str] = None,
    resolution_steps: Optional[List[str]] = None
):
    """
    Convenience function to notify about an error.
    
    Args:
        error: The exception that occurred
        context: Additional context information
        severity: Error severity ('critical', 'high', 'medium', 'low')
        user_message: Custom user-friendly message
        admin_message: Custom admin message
        resolution_steps: List of resolution steps
    """
    system = get_error_notification_system()
    system.notify_error(
        error=error,
        context=context,
        severity=severity,
        user_message=user_message,
        admin_message=admin_message,
        resolution_steps=resolution_steps
    )