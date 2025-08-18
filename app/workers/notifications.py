"""Notification worker for multi-channel notification delivery."""
import asyncio
import logging
import smtplib
import subprocess
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template, Environment, BaseLoader

from celery import current_task
from flask import current_app
from app.models import (
    Notification, NotificationTemplate, NotificationPreference, NotificationEvent,
    NotificationType, NotificationPriority, NotificationStatus, User, Tenant, Channel
)
from app.utils.database import db
from app.workers.base import MonitoredWorker, create_task_decorator

logger = logging.getLogger(__name__)

# Create task decorator for notification queue
notification_task = create_task_decorator('notifications', max_retries=3, default_retry_delay=60)


class NotificationWorker(MonitoredWorker):
    """Worker for processing notification delivery."""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("notification.worker")
        self.jinja_env = Environment(loader=BaseLoader())
    def send_notification_impl(self, notification_id: str):
        """Send a notification via the appropriate channel."""
        try:
            notification = Notification.query.get(notification_id)
            if not notification:
                self.logger.error(f"Notification {notification_id} not found")
                return {"status": "error", "message": "Notification not found"}
            
            if notification.status != NotificationStatus.PENDING.value:
                self.logger.warning(f"Notification {notification_id} already processed: {notification.status}")
                return {"status": "skipped", "message": f"Already {notification.status}"}
            
            # Mark as processing
            notification.status = NotificationStatus.RETRYING.value if notification.retry_count > 0 else NotificationStatus.PENDING.value
            db.session.commit()
            
            # Send based on type
            success = False
            error_message = None
            
            if notification.type == NotificationType.EMAIL.value:
                success, error_message = self._send_email(notification)
            elif notification.type == NotificationType.TELEGRAM.value:
                success, error_message = self._send_telegram(notification)
            elif notification.type == NotificationType.SIGNAL.value:
                success, error_message = self._send_signal(notification)
            else:
                error_message = f"Unsupported notification type: {notification.type}"
            
            if success:
                notification.mark_sent()
                self._log_event(notification, "sent", {"sent_at": datetime.utcnow().isoformat()})
                db.session.commit()
                self.logger.info(f"Notification {notification_id} sent successfully")
                return {"status": "sent", "notification_id": notification_id}
            else:
                notification.mark_failed(error_message or "Unknown error")
                self._log_event(notification, "failed", {"error": error_message})
                db.session.commit()
                
                # Retry if possible
                if notification.is_retryable():
                    self.logger.warning(f"Notification {notification_id} failed, retrying: {error_message}")
                    # Note: retry logic would need to be handled by the task decorator
                    return {"status": "retry", "error": error_message}
                else:
                    self.logger.error(f"Notification {notification_id} failed permanently: {error_message}")
                    return {"status": "failed", "error": error_message}
        
        except Exception as e:
            self.logger.error(f"Error processing notification {notification_id}: {str(e)}")
            if 'notification' in locals() and notification:
                notification.mark_failed(str(e))
                db.session.commit()
            raise
    
    def send_bulk_notifications_impl(self, notification_ids: List[str]):
        """Send multiple notifications in batch."""
        results = []
        for notification_id in notification_ids:
            try:
                # Call the implementation directly since we're already in a task
                result = self.send_notification_impl(notification_id)
                results.append({"notification_id": notification_id, "result": result})
            except Exception as e:
                self.logger.error(f"Failed to process notification {notification_id}: {str(e)}")
                results.append({"notification_id": notification_id, "error": str(e)})
        
        return {"queued": len(results), "results": results}
    
    def process_notification_preferences_impl(self, user_id: str, event_type: str, data: Dict[str, Any]):
        """Process notification based on user preferences."""
        try:
            user = User.query.get(user_id)
            if not user:
                self.logger.error(f"User {user_id} not found")
                return {"status": "error", "message": "User not found"}
            
            # Get user preferences for this event type
            preferences = NotificationPreference.query.filter_by(
                user_id=user_id,
                event_type=event_type,
                is_enabled=True
            ).all()
            
            if not preferences:
                self.logger.info(f"No enabled preferences for user {user_id}, event {event_type}")
                return {"status": "skipped", "message": "No enabled preferences"}
            
            notifications_created = []
            
            for preference in preferences:
                # Create notification
                notification = self._create_notification_from_preference(preference, data)
                if notification:
                    notifications_created.append(notification.id)
                    # Send directly since we're already in a task
                    self.send_notification_impl(notification.id)
            
            return {
                "status": "processed",
                "notifications_created": len(notifications_created),
                "notification_ids": notifications_created
            }
        
        except Exception as e:
            self.logger.error(f"Error processing preferences for user {user_id}: {str(e)}")
            raise
    
    def cleanup_old_notifications_impl(self, days_old: int = 30):
        """Clean up old notification records."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Delete old notifications and events
            old_notifications = Notification.query.filter(
                Notification.created_at < cutoff_date,
                Notification.status.in_([NotificationStatus.SENT.value, NotificationStatus.DELIVERED.value, NotificationStatus.FAILED.value])
            ).all()
            
            deleted_count = 0
            for notification in old_notifications:
                # Delete associated events
                NotificationEvent.query.filter_by(notification_id=notification.id).delete()
                db.session.delete(notification)
                deleted_count += 1
            
            db.session.commit()
            
            self.logger.info(f"Cleaned up {deleted_count} old notifications")
            return {"status": "completed", "deleted_count": deleted_count}
        
        except Exception as e:
            self.logger.error(f"Error cleaning up notifications: {str(e)}")
            raise
    
    def _send_email(self, notification: Notification) -> tuple[bool, Optional[str]]:
        """Send email notification."""
        try:
            # Get SMTP configuration
            smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = current_app.config.get('SMTP_PORT', 587)
            smtp_username = current_app.config.get('SMTP_USERNAME')
            smtp_password = current_app.config.get('SMTP_PASSWORD')
            
            if not smtp_username or not smtp_password:
                return False, "SMTP credentials not configured"
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = notification.subject or "Notification"
            msg['From'] = smtp_username
            msg['To'] = notification.recipient
            
            # Set priority
            if notification.priority == NotificationPriority.HIGH.value:
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
            elif notification.priority == NotificationPriority.URGENT.value:
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
                msg['Importance'] = 'high'
            
            # Attach content
            msg.attach(MIMEText(notification.body, 'plain'))
            if notification.html_body:
                msg.attach(MIMEText(notification.html_body, 'html'))
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            return True, None
        
        except Exception as e:
            return False, str(e)
    
    def _send_telegram(self, notification: Notification) -> tuple[bool, Optional[str]]:
        """Send Telegram notification."""
        try:
            # Get tenant's Telegram channel
            user = User.query.get(notification.user_id) if notification.user_id else None
            if not user:
                return False, "User not found for Telegram notification"
            
            channel = Channel.query.filter_by(
                tenant_id=user.tenant_id,
                type='telegram',
                is_active=True
            ).first()
            
            if not channel:
                return False, "No active Telegram channel found"
            
            bot_token = channel.config.get('bot_token')
            if not bot_token:
                return False, "Telegram bot token not configured"
            
            # Use recipient as chat_id (should be Telegram chat ID)
            chat_id = notification.recipient
            
            # Prepare message
            message_text = notification.body
            if notification.subject:
                message_text = f"*{notification.subject}*\n\n{message_text}"
            
            # Send via Telegram Bot API
            import requests
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message_text,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get('ok'):
                # Store message ID for tracking
                notification.external_id = str(result['result']['message_id'])
                return True, None
            else:
                return False, result.get('description', 'Unknown Telegram API error')
        
        except Exception as e:
            return False, str(e)
    
    def _send_signal(self, notification: Notification) -> tuple[bool, Optional[str]]:
        """Send Signal notification."""
        try:
            # Get tenant's Signal channel
            user = User.query.get(notification.user_id) if notification.user_id else None
            if not user:
                return False, "User not found for Signal notification"
            
            channel = Channel.query.filter_by(
                tenant_id=user.tenant_id,
                type='signal',
                is_active=True
            ).first()
            
            if not channel:
                return False, "No active Signal channel found"
            
            signal_cli_path = channel.config.get('signal_cli_path', 'signal-cli')
            phone_number = channel.config.get('phone_number')
            
            if not phone_number:
                return False, "Signal phone number not configured"
            
            # Prepare message
            message_text = notification.body
            if notification.subject:
                message_text = f"{notification.subject}\n\n{message_text}"
            
            # Send via signal-cli
            cmd = [
                signal_cli_path,
                '-u', phone_number,
                'send',
                '-m', message_text,
                notification.recipient
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return True, None
            else:
                return False, f"signal-cli error: {result.stderr}"
        
        except Exception as e:
            return False, str(e)
    
    def _create_notification_from_preference(self, preference: NotificationPreference, data: Dict[str, Any]) -> Optional[Notification]:
        """Create notification from user preference and event data."""
        try:
            # Get template for this event type and notification type
            template = NotificationTemplate.query.filter_by(
                tenant_id=preference.tenant_id,
                name=f"{preference.event_type}_{preference.notification_type}",
                type=preference.notification_type,
                is_active=True
            ).first()
            
            if not template:
                # Try generic template
                template = NotificationTemplate.query.filter_by(
                    tenant_id=preference.tenant_id,
                    name=f"generic_{preference.notification_type}",
                    type=preference.notification_type,
                    is_active=True
                ).first()
            
            # Render content
            subject = None
            body = data.get('message', 'Notification')
            html_body = None
            
            if template:
                # Render templates
                if template.subject_template:
                    subject_tmpl = self.jinja_env.from_string(template.subject_template)
                    subject = subject_tmpl.render(**data)
                
                body_tmpl = self.jinja_env.from_string(template.body_template)
                body = body_tmpl.render(**data)
                
                if template.html_template:
                    html_tmpl = self.jinja_env.from_string(template.html_template)
                    html_body = html_tmpl.render(**data)
            
            # Create notification
            notification = Notification(
                tenant_id=preference.tenant_id,
                template_id=template.id if template else None,
                user_id=preference.user_id,
                recipient=preference.delivery_address,
                type=preference.notification_type,
                priority=data.get('priority', NotificationPriority.NORMAL.value),
                subject=subject,
                body=body,
                html_body=html_body,
                variables=data,
                scheduled_at=data.get('scheduled_at'),
                max_retries=data.get('max_retries', 3)
            )
            
            db.session.add(notification)
            db.session.commit()
            
            return notification
        
        except Exception as e:
            self.logger.error(f"Error creating notification from preference: {str(e)}")
            return None
    
    def _log_event(self, notification: Notification, event_type: str, data: Dict[str, Any]):
        """Log notification event."""
        try:
            event = NotificationEvent(
                notification_id=notification.id,
                event_type=event_type,
                data=data
            )
            db.session.add(event)
        except Exception as e:
            self.logger.error(f"Error logging notification event: {str(e)}")


# Create worker instance
notification_worker = NotificationWorker()


# Task functions using decorators
@notification_task
def send_notification(notification_id: str):
    """Send a notification via the appropriate channel."""
    return notification_worker.send_notification_impl(notification_id)


@notification_task
def send_bulk_notifications(notification_ids: List[str]):
    """Send multiple notifications in batch."""
    return notification_worker.send_bulk_notifications_impl(notification_ids)


@notification_task
def process_notification_preferences(user_id: str, event_type: str, data: Dict[str, Any]):
    """Process notification based on user preferences."""
    return notification_worker.process_notification_preferences_impl(user_id, event_type, data)


@notification_task
def cleanup_old_notifications(days_old: int = 30):
    """Clean up old notification records."""
    return notification_worker.cleanup_old_notifications_impl(days_old)


# Convenience functions for common notification types
@notification_task
def send_kyb_alert(tenant_id: str, user_id: str, alert_data: Dict[str, Any]):
    """Send KYB alert notification."""
    return process_notification_preferences.delay(
        user_id=user_id,
        event_type='kyb_alert',
        data={
            **alert_data,
            'priority': NotificationPriority.HIGH.value
        }
    )


@notification_task
def send_invoice_notification(tenant_id: str, user_id: str, invoice_data: Dict[str, Any]):
    """Send invoice-related notification."""
    return process_notification_preferences.delay(
        user_id=user_id,
        event_type='invoice_update',
        data=invoice_data
    )


@notification_task
def send_system_notification(tenant_id: str, user_id: str, message: str, priority: str = 'normal'):
    """Send generic system notification."""
    return process_notification_preferences.delay(
        user_id=user_id,
        event_type='system_notification',
        data={
            'message': message,
            'priority': priority,
            'timestamp': datetime.utcnow().isoformat()
        }
    )


# Periodic tasks
@notification_task
def daily_notification_cleanup():
    """Daily cleanup of old notifications."""
    return cleanup_old_notifications.delay(days_old=30)


@notification_task
def process_scheduled_notifications():
    """Process notifications scheduled for sending."""
    try:
        # Get notifications scheduled for now or earlier
        now = datetime.utcnow()
        scheduled_notifications = Notification.query.filter(
            Notification.scheduled_at <= now,
            Notification.status == NotificationStatus.PENDING.value
        ).all()
        
        queued_count = 0
        for notification in scheduled_notifications:
            send_notification.delay(notification.id)
            queued_count += 1
        
        logger.info(f"Queued {queued_count} scheduled notifications")
        return {"status": "completed", "queued_count": queued_count}
    
    except Exception as e:
        logger.error(f"Error processing scheduled notifications: {str(e)}")
        raise