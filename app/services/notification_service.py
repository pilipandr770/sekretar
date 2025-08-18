"""Enhanced notification service for multi-channel notifications."""
import asyncio
import logging
import smtplib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template, Environment, BaseLoader

from flask import current_app
from app.models import (
    Notification, NotificationTemplate, NotificationPreference, NotificationEvent,
    NotificationType, NotificationPriority, NotificationStatus, User, Tenant
)
from app.utils.database import db


class NotificationService:
    """Enhanced service for multi-channel notifications with worker integration."""
    
    def __init__(self):
        self.logger = logging.getLogger("notification.service")
        self.jinja_env = Environment(loader=BaseLoader())
    
    def create_notification(
        self,
        tenant_id: str,
        recipient: str,
        notification_type: Union[str, NotificationType],
        subject: Optional[str] = None,
        body: str = "",
        html_body: Optional[str] = None,
        user_id: Optional[str] = None,
        template_id: Optional[str] = None,
        priority: Union[str, NotificationPriority] = NotificationPriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        variables: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> Notification:
        """Create a new notification record."""
        try:
            # Convert enums to strings if needed
            if isinstance(notification_type, NotificationType):
                notification_type = notification_type.value
            if isinstance(priority, NotificationPriority):
                priority = priority.value
            
            notification = Notification(
                tenant_id=tenant_id,
                template_id=template_id,
                user_id=user_id,
                recipient=recipient,
                type=notification_type,
                priority=priority,
                subject=subject,
                body=body,
                html_body=html_body,
                variables=variables or {},
                scheduled_at=scheduled_at,
                max_retries=max_retries
            )
            
            db.session.add(notification)
            db.session.commit()
            
            self.logger.info(f"Created notification {notification.id} for {recipient}")
            return notification
        
        except Exception as e:
            self.logger.error(f"Error creating notification: {str(e)}")
            raise
    
    def send_notification_async(self, notification_id: str) -> str:
        """Queue notification for asynchronous sending."""
        try:
            from app.workers.notifications import send_notification
            task = send_notification.delay(notification_id)
            self.logger.info(f"Queued notification {notification_id} for sending, task: {task.id}")
            return task.id
        except Exception as e:
            self.logger.error(f"Error queuing notification {notification_id}: {str(e)}")
            raise
    
    def send_to_user_preferences(
        self,
        user_id: str,
        event_type: str,
        data: Dict[str, Any],
        priority: Union[str, NotificationPriority] = NotificationPriority.NORMAL
    ) -> List[str]:
        """Send notifications based on user preferences."""
        try:
            from app.workers.notifications import process_notification_preferences
            
            if isinstance(priority, NotificationPriority):
                priority = priority.value
            
            data['priority'] = priority
            
            task = process_notification_preferences.delay(user_id, event_type, data)
            self.logger.info(f"Queued preference-based notifications for user {user_id}, event {event_type}")
            return [task.id]
        
        except Exception as e:
            self.logger.error(f"Error sending preference-based notifications: {str(e)}")
            raise
    
    def send_bulk_notifications(self, notification_ids: List[str]) -> str:
        """Send multiple notifications in bulk."""
        try:
            from app.workers.notifications import send_bulk_notifications
            task = send_bulk_notifications.delay(notification_ids)
            self.logger.info(f"Queued {len(notification_ids)} notifications for bulk sending")
            return task.id
        except Exception as e:
            self.logger.error(f"Error queuing bulk notifications: {str(e)}")
            raise
    
    def create_template(
        self,
        tenant_id: str,
        name: str,
        notification_type: Union[str, NotificationType],
        body_template: str,
        subject_template: Optional[str] = None,
        html_template: Optional[str] = None,
        variables: Optional[List[str]] = None
    ) -> NotificationTemplate:
        """Create a notification template."""
        try:
            if isinstance(notification_type, NotificationType):
                notification_type = notification_type.value
            
            template = NotificationTemplate(
                tenant_id=tenant_id,
                name=name,
                type=notification_type,
                subject_template=subject_template,
                body_template=body_template,
                html_template=html_template,
                variables=variables or []
            )
            
            db.session.add(template)
            db.session.commit()
            
            self.logger.info(f"Created notification template {template.id}: {name}")
            return template
        
        except Exception as e:
            self.logger.error(f"Error creating notification template: {str(e)}")
            raise
    
    def set_user_preference(
        self,
        user_id: str,
        tenant_id: str,
        event_type: str,
        notification_type: Union[str, NotificationType],
        delivery_address: str,
        is_enabled: bool = True,
        settings: Optional[Dict[str, Any]] = None
    ) -> NotificationPreference:
        """Set user notification preference."""
        try:
            if isinstance(notification_type, NotificationType):
                notification_type = notification_type.value
            
            # Check if preference already exists
            preference = NotificationPreference.query.filter_by(
                user_id=user_id,
                event_type=event_type,
                notification_type=notification_type
            ).first()
            
            if preference:
                # Update existing
                preference.delivery_address = delivery_address
                preference.is_enabled = is_enabled
                preference.settings = settings or {}
            else:
                # Create new
                preference = NotificationPreference(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    notification_type=notification_type,
                    event_type=event_type,
                    is_enabled=is_enabled,
                    delivery_address=delivery_address,
                    settings=settings or {}
                )
                db.session.add(preference)
            
            db.session.commit()
            
            self.logger.info(f"Set notification preference for user {user_id}: {event_type} -> {notification_type}")
            return preference
        
        except Exception as e:
            self.logger.error(f"Error setting notification preference: {str(e)}")
            raise
    
    def get_notification_status(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Get notification status and delivery information."""
        try:
            notification = Notification.query.get(notification_id)
            if not notification:
                return None
            
            # Get events
            events = NotificationEvent.query.filter_by(
                notification_id=notification_id
            ).order_by(NotificationEvent.timestamp.desc()).all()
            
            return {
                'id': notification.id,
                'status': notification.status,
                'type': notification.type,
                'recipient': notification.recipient,
                'subject': notification.subject,
                'priority': notification.priority,
                'created_at': notification.created_at.isoformat() if notification.created_at else None,
                'sent_at': notification.sent_at.isoformat() if notification.sent_at else None,
                'delivered_at': notification.delivered_at.isoformat() if notification.delivered_at else None,
                'failed_at': notification.failed_at.isoformat() if notification.failed_at else None,
                'retry_count': notification.retry_count,
                'error_message': notification.error_message,
                'external_id': notification.external_id,
                'events': [
                    {
                        'type': event.event_type,
                        'timestamp': event.timestamp.isoformat(),
                        'data': event.data
                    }
                    for event in events
                ]
            }
        
        except Exception as e:
            self.logger.error(f"Error getting notification status: {str(e)}")
            return None
    
    def get_user_preferences(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all notification preferences for a user."""
        try:
            preferences = NotificationPreference.query.filter_by(user_id=user_id).all()
            
            return [
                {
                    'id': pref.id,
                    'event_type': pref.event_type,
                    'notification_type': pref.notification_type,
                    'delivery_address': pref.delivery_address,
                    'is_enabled': pref.is_enabled,
                    'settings': pref.settings
                }
                for pref in preferences
            ]
        
        except Exception as e:
            self.logger.error(f"Error getting user preferences: {str(e)}")
            return []
    
    # Legacy methods for backward compatibility
    @staticmethod
    def send_change_notification(change_data: Dict) -> bool:
        """Send notification about counterparty changes."""
        try:
            from app.models import Counterparty, Tenant
            
            # Get counterparty and tenant info
            counterparty = Counterparty.query.get(change_data['counterparty_id'])
            if not counterparty:
                return False
            
            tenant = Tenant.query.get(counterparty.tenant_id)
            if not tenant:
                return False
            
            # Prepare notification data
            notification_data = {
                'company_name': tenant.name,
                'counterparty_name': counterparty.name,
                'field_changed': change_data['field_name'],
                'old_value': change_data['old_value'],
                'new_value': change_data['new_value'],
                'detected_at': change_data['detected_at'],
                'change_source': change_data.get('change_source', 'Unknown')
            }
            
            # Send email notification using new service
            service = NotificationService()
            notification = service.create_notification(
                tenant_id=tenant.id,
                recipient=change_data.get('recipient_email', 'admin@example.com'),
                notification_type=NotificationType.EMAIL,
                subject=f"KYB Alert: Changes detected for {counterparty.name}",
                body=f"Changes detected for {counterparty.name}",
                variables=notification_data
            )
            
            if notification:
                service.send_notification_async(notification.id)
                return True
            
            return False
            
        except Exception as e:
            current_app.logger.error(f"Change notification error: {str(e)}")
            return False
    
    @staticmethod
    def send_sanctions_alert(counterparty_id: str, match_data: Dict) -> bool:
        """Send high-priority sanctions alert."""
        try:
            from app.models import Counterparty, Tenant
            
            counterparty = Counterparty.query.get(counterparty_id)
            if not counterparty:
                return False
                
            tenant = Tenant.query.get(counterparty.tenant_id)
            if not tenant:
                return False
            
            # Prepare alert data
            alert_data = {
                'company_name': tenant.name,
                'counterparty_name': counterparty.name,
                'sanctions_list': match_data['list'],
                'match_type': match_data['type'],
                'match_score': match_data['score'],
                'matched_keyword': match_data.get('matched_keyword', ''),
                'detected_at': match_data['detected_at']
            }
            
            # Send high-priority notification using new service
            service = NotificationService()
            notification = service.create_notification(
                tenant_id=tenant.id,
                recipient=match_data.get('recipient_email', 'admin@example.com'),
                notification_type=NotificationType.EMAIL,
                subject=f"🚨 URGENT: Sanctions match found for {counterparty.name}",
                body=f"Sanctions match found for {counterparty.name}",
                priority=NotificationPriority.URGENT,
                variables=alert_data
            )
            
            if notification:
                service.send_notification_async(notification.id)
                return True
            
            return False
            
        except Exception as e:
            current_app.logger.error(f"Sanctions alert error: {str(e)}")
            return False
    
    @staticmethod
    def send_kyb_summary(tenant_id: str, summary_data: Dict) -> bool:
        """Send daily/weekly KYB summary."""
        try:
            from app.models import Tenant
            
            tenant = Tenant.query.get(tenant_id)
            if not tenant:
                return False
            
            # Send summary notification using new service
            service = NotificationService()
            notification = service.create_notification(
                tenant_id=tenant.id,
                recipient=summary_data.get('recipient_email', 'admin@example.com'),
                notification_type=NotificationType.EMAIL,
                subject=f"KYB Summary for {tenant.name}",
                body=f"KYB Summary for {tenant.name}",
                variables=summary_data
            )
            
            if notification:
                service.send_notification_async(notification.id)
                return True
            
            return False
            
        except Exception as e:
            current_app.logger.error(f"KYB summary error: {str(e)}")
            return False
    
    @staticmethod
    def _send_email_notification(to_email: str, subject: str, template_type: str, 
                               data: Dict, priority: str = 'normal') -> bool:
        """Send email notification using SMTP."""
        try:
            # Get SMTP configuration
            smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = current_app.config.get('SMTP_PORT', 587)
            smtp_username = current_app.config.get('SMTP_USERNAME')
            smtp_password = current_app.config.get('SMTP_PASSWORD')
            
            if not smtp_username or not smtp_password:
                current_app.logger.warning("SMTP credentials not configured")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = smtp_username
            msg['To'] = to_email
            
            if priority == 'high':
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
            
            # Generate email content
            html_content = NotificationService._generate_email_content(template_type, data)
            text_content = NotificationService._generate_text_content(template_type, data)
            
            # Attach parts
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            current_app.logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Email sending error: {str(e)}")
            return False
    
    @staticmethod
    def _generate_email_content(template_type: str, data: Dict) -> str:
        """Generate HTML email content."""
        templates = {
            'change_notification': """
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #f39c12;">🔍 KYB Change Detected</h2>
                <p>Dear {{ company_name }} team,</p>
                <p>We detected a change in the information for counterparty <strong>{{ counterparty_name }}</strong>:</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #f39c12; margin: 20px 0;">
                    <p><strong>Field Changed:</strong> {{ field_changed }}</p>
                    <p><strong>Old Value:</strong> {{ old_value }}</p>
                    <p><strong>New Value:</strong> {{ new_value }}</p>
                    <p><strong>Source:</strong> {{ change_source }}</p>
                    <p><strong>Detected:</strong> {{ detected_at }}</p>
                </div>
                
                <p>Please review this change and take appropriate action if necessary.</p>
                <p>Best regards,<br>AI Secretary KYB System</p>
            </body>
            </html>
            """,
            
            'sanctions_alert': """
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #e74c3c;">🚨 URGENT: Sanctions Match Found</h2>
                <p>Dear {{ company_name }} team,</p>
                <p><strong style="color: #e74c3c;">IMMEDIATE ACTION REQUIRED</strong></p>
                <p>A potential sanctions match has been found for counterparty <strong>{{ counterparty_name }}</strong>:</p>
                
                <div style="background-color: #fdf2f2; padding: 15px; border-left: 4px solid #e74c3c; margin: 20px 0;">
                    <p><strong>Sanctions List:</strong> {{ sanctions_list }}</p>
                    <p><strong>Match Type:</strong> {{ match_type }}</p>
                    <p><strong>Confidence Score:</strong> {{ match_score }}%</p>
                    <p><strong>Matched Keyword:</strong> {{ matched_keyword }}</p>
                    <p><strong>Detected:</strong> {{ detected_at }}</p>
                </div>
                
                <p><strong>Recommended Actions:</strong></p>
                <ul>
                    <li>Immediately review the counterparty relationship</li>
                    <li>Consult with legal/compliance team</li>
                    <li>Consider suspending transactions</li>
                    <li>Document all actions taken</li>
                </ul>
                
                <p>Best regards,<br>AI Secretary KYB System</p>
            </body>
            </html>
            """,
            
            'kyb_summary': """
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #3498db;">📊 KYB Summary Report</h2>
                <p>Dear {{ company_name }} team,</p>
                <p>Here's your KYB monitoring summary:</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; margin: 20px 0;">
                    <h3>Statistics</h3>
                    <p><strong>Total Counterparties:</strong> {{ total_counterparties }}</p>
                    <p><strong>High Risk:</strong> {{ high_risk_counterparties }}</p>
                    <p><strong>Recent Changes:</strong> {{ recent_changes }}</p>
                    <p><strong>Recent Checks:</strong> {{ recent_checks }}</p>
                </div>
                
                <p>For detailed information, please visit your KYB Dashboard.</p>
                <p>Best regards,<br>AI Secretary KYB System</p>
            </body>
            </html>
            """
        }
        
        template = templates.get(template_type, "<p>{{ message }}</p>")
        
        # Simple template rendering (in production, use Jinja2)
        content = template
        for key, value in data.items():
            content = content.replace(f"{{{{ {key} }}}}", str(value))
        
        return content
    
    @staticmethod
    def _generate_text_content(template_type: str, data: Dict) -> str:
        """Generate plain text email content."""
        if template_type == 'change_notification':
            return f"""
KYB Change Detected

Dear {data.get('company_name', 'Team')},

We detected a change for counterparty {data.get('counterparty_name', 'Unknown')}:

Field Changed: {data.get('field_changed', 'Unknown')}
Old Value: {data.get('old_value', 'N/A')}
New Value: {data.get('new_value', 'N/A')}
Source: {data.get('change_source', 'Unknown')}
Detected: {data.get('detected_at', 'Unknown')}

Please review this change and take appropriate action if necessary.

Best regards,
AI Secretary KYB System
            """
        elif template_type == 'sanctions_alert':
            return f"""
URGENT: Sanctions Match Found

Dear {data.get('company_name', 'Team')},

IMMEDIATE ACTION REQUIRED

A potential sanctions match has been found for counterparty {data.get('counterparty_name', 'Unknown')}:

Sanctions List: {data.get('sanctions_list', 'Unknown')}
Match Type: {data.get('match_type', 'Unknown')}
Confidence Score: {data.get('match_score', 0)}%
Matched Keyword: {data.get('matched_keyword', 'N/A')}
Detected: {data.get('detected_at', 'Unknown')}

Recommended Actions:
- Immediately review the counterparty relationship
- Consult with legal/compliance team
- Consider suspending transactions
- Document all actions taken

Best regards,
AI Secretary KYB System
            """
        else:
            return f"KYB Notification: {data.get('message', 'No details available')}"