"""
Advanced alerting service for AI Secretary.
Handles alert generation, routing, and delivery across multiple channels.
"""

import time
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from flask import current_app
import structlog

logger = structlog.get_logger()


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


@dataclass
class Alert:
    """Alert data structure."""
    id: str
    name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    description: str
    source: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    starts_at: datetime
    ends_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        data = asdict(self)
        data['severity'] = self.severity.value
        data['status'] = self.status.value
        data['starts_at'] = self.starts_at.isoformat()
        if self.ends_at:
            data['ends_at'] = self.ends_at.isoformat()
        if self.acknowledged_at:
            data['acknowledged_at'] = self.acknowledged_at.isoformat()
        return data


class AlertRule:
    """Alert rule definition."""
    
    def __init__(
        self,
        name: str,
        condition: Callable[[], bool],
        severity: AlertSeverity,
        message: str,
        description: str,
        labels: Dict[str, str] = None,
        annotations: Dict[str, str] = None,
        cooldown_minutes: int = 5
    ):
        self.name = name
        self.condition = condition
        self.severity = severity
        self.message = message
        self.description = description
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.cooldown_minutes = cooldown_minutes
        self.last_triggered = None
    
    def should_trigger(self) -> bool:
        """Check if rule should trigger."""
        # Check cooldown period
        if self.last_triggered:
            cooldown_end = self.last_triggered + timedelta(minutes=self.cooldown_minutes)
            if datetime.utcnow() < cooldown_end:
                return False
        
        # Evaluate condition
        try:
            return self.condition()
        except Exception as e:
            logger.error("Alert rule condition failed", rule=self.name, error=str(e))
            return False
    
    def create_alert(self) -> Alert:
        """Create alert from rule."""
        alert_id = f"{self.name}_{int(time.time())}"
        
        alert = Alert(
            id=alert_id,
            name=self.name,
            severity=self.severity,
            status=AlertStatus.ACTIVE,
            message=self.message,
            description=self.description,
            source="alert_rule",
            labels=self.labels.copy(),
            annotations=self.annotations.copy(),
            starts_at=datetime.utcnow()
        )
        
        self.last_triggered = datetime.utcnow()
        return alert


class NotificationChannel:
    """Base class for notification channels."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert notification. Override in subclasses."""
        raise NotImplementedError
    
    def should_send(self, alert: Alert) -> bool:
        """Check if alert should be sent to this channel."""
        # Check severity filter
        min_severity = self.config.get('min_severity', 'low')
        severity_levels = ['low', 'medium', 'high', 'critical']
        
        if severity_levels.index(alert.severity.value) < severity_levels.index(min_severity):
            return False
        
        # Check label filters
        label_filters = self.config.get('label_filters', {})
        for key, value in label_filters.items():
            if alert.labels.get(key) != value:
                return False
        
        return True


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel."""
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            smtp_config = self.config.get('smtp', {})
            recipients = self.config.get('recipients', [])
            
            if not recipients:
                logger.warning("No email recipients configured", channel=self.name)
                return False
            
            # Create email message
            msg = MimeMultipart()
            msg['From'] = smtp_config.get('from_email', 'alerts@ai-secretary.com')
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.name}"
            
            # Email body
            body = f"""
Alert: {alert.name}
Severity: {alert.severity.value.upper()}
Status: {alert.status.value}
Time: {alert.starts_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

Message: {alert.message}
Description: {alert.description}

Labels:
{json.dumps(alert.labels, indent=2)}

Annotations:
{json.dumps(alert.annotations, indent=2)}
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(smtp_config.get('host', 'localhost'), smtp_config.get('port', 587))
            if smtp_config.get('use_tls', True):
                server.starttls()
            
            if smtp_config.get('username') and smtp_config.get('password'):
                server.login(smtp_config['username'], smtp_config['password'])
            
            server.send_message(msg)
            server.quit()
            
            logger.info("Alert sent via email", alert_id=alert.id, recipients=recipients)
            return True
            
        except Exception as e:
            logger.error("Failed to send email alert", alert_id=alert.id, error=str(e))
            return False


class SlackNotificationChannel(NotificationChannel):
    """Slack notification channel."""
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via Slack webhook."""
        try:
            webhook_url = self.config.get('webhook_url')
            if not webhook_url:
                logger.warning("No Slack webhook URL configured", channel=self.name)
                return False
            
            # Determine color based on severity
            color_map = {
                AlertSeverity.LOW: "#36a64f",      # Green
                AlertSeverity.MEDIUM: "#ff9500",   # Orange
                AlertSeverity.HIGH: "#ff0000",     # Red
                AlertSeverity.CRITICAL: "#8B0000"  # Dark Red
            }
            
            # Create Slack message
            payload = {
                "username": "AI Secretary Alerts",
                "icon_emoji": ":warning:",
                "attachments": [
                    {
                        "color": color_map.get(alert.severity, "#ff0000"),
                        "title": f"{alert.severity.value.upper()}: {alert.name}",
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "Description",
                                "value": alert.description,
                                "short": False
                            },
                            {
                                "title": "Time",
                                "value": alert.starts_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
                                "short": True
                            },
                            {
                                "title": "Status",
                                "value": alert.status.value,
                                "short": True
                            }
                        ],
                        "footer": "AI Secretary Monitoring",
                        "ts": int(alert.starts_at.timestamp())
                    }
                ]
            }
            
            # Add labels as fields if present
            if alert.labels:
                for key, value in alert.labels.items():
                    payload["attachments"][0]["fields"].append({
                        "title": key,
                        "value": value,
                        "short": True
                    })
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Alert sent via Slack", alert_id=alert.id)
            return True
            
        except Exception as e:
            logger.error("Failed to send Slack alert", alert_id=alert.id, error=str(e))
            return False


class WebhookNotificationChannel(NotificationChannel):
    """Generic webhook notification channel."""
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via webhook."""
        try:
            webhook_url = self.config.get('url')
            if not webhook_url:
                logger.warning("No webhook URL configured", channel=self.name)
                return False
            
            headers = self.config.get('headers', {})
            headers.setdefault('Content-Type', 'application/json')
            
            payload = {
                "alert": alert.to_dict(),
                "timestamp": datetime.utcnow().isoformat(),
                "source": "ai-secretary-alerting"
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=self.config.get('timeout', 10)
            )
            response.raise_for_status()
            
            logger.info("Alert sent via webhook", alert_id=alert.id, url=webhook_url)
            return True
            
        except Exception as e:
            logger.error("Failed to send webhook alert", alert_id=alert.id, error=str(e))
            return False


class AlertingService:
    """Main alerting service."""
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.channels: Dict[str, NotificationChannel] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.suppression_rules: List[Dict[str, Any]] = []
        self._running = False
        self._check_interval = 60  # seconds
    
    def add_rule(self, rule: AlertRule):
        """Add alert rule."""
        self.rules.append(rule)
        logger.info("Alert rule added", rule_name=rule.name)
    
    def add_channel(self, channel: NotificationChannel):
        """Add notification channel."""
        self.channels[channel.name] = channel
        logger.info("Notification channel added", channel_name=channel.name)
    
    def add_suppression_rule(self, rule: Dict[str, Any]):
        """Add alert suppression rule."""
        self.suppression_rules.append(rule)
        logger.info("Suppression rule added", rule=rule)
    
    async def check_rules(self):
        """Check all alert rules and trigger alerts."""
        for rule in self.rules:
            try:
                if rule.should_trigger():
                    alert = rule.create_alert()
                    await self.fire_alert(alert)
            except Exception as e:
                logger.error("Error checking alert rule", rule=rule.name, error=str(e))
    
    async def fire_alert(self, alert: Alert):
        """Fire an alert and send notifications."""
        # Check if alert is suppressed
        if self._is_suppressed(alert):
            logger.info("Alert suppressed", alert_id=alert.id)
            return
        
        # Store alert
        self.active_alerts[alert.id] = alert
        self.alert_history.append(alert)
        
        logger.warning("Alert fired", alert_id=alert.id, name=alert.name, severity=alert.severity.value)
        
        # Send notifications
        for channel_name, channel in self.channels.items():
            if channel.enabled and channel.should_send(alert):
                try:
                    success = await channel.send_alert(alert)
                    if success:
                        logger.info("Alert notification sent", alert_id=alert.id, channel=channel_name)
                    else:
                        logger.warning("Alert notification failed", alert_id=alert.id, channel=channel_name)
                except Exception as e:
                    logger.error("Error sending alert notification", 
                               alert_id=alert.id, channel=channel_name, error=str(e))
    
    def resolve_alert(self, alert_id: str, resolved_by: str = None):
        """Resolve an active alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.ends_at = datetime.utcnow()
            
            del self.active_alerts[alert_id]
            
            logger.info("Alert resolved", alert_id=alert_id, resolved_by=resolved_by)
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        """Acknowledge an active alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = acknowledged_by
            
            logger.info("Alert acknowledged", alert_id=alert_id, acknowledged_by=acknowledged_by)
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history."""
        return list(self.alert_history)[-limit:]
    
    def _is_suppressed(self, alert: Alert) -> bool:
        """Check if alert is suppressed by suppression rules."""
        for rule in self.suppression_rules:
            # Check if all rule conditions match
            matches = True
            
            for key, value in rule.get('labels', {}).items():
                if alert.labels.get(key) != value:
                    matches = False
                    break
            
            if matches and rule.get('severity') and alert.severity.value != rule['severity']:
                matches = False
            
            if matches:
                return True
        
        return False
    
    async def start_monitoring(self):
        """Start the alerting monitoring loop."""
        self._running = True
        logger.info("Alerting service started")
        
        while self._running:
            try:
                await self.check_rules()
                await asyncio.sleep(self._check_interval)
            except Exception as e:
                logger.error("Error in alerting monitoring loop", error=str(e))
                await asyncio.sleep(self._check_interval)
    
    def stop_monitoring(self):
        """Stop the alerting monitoring loop."""
        self._running = False
        logger.info("Alerting service stopped")


# Global alerting service instance
alerting_service = AlertingService()


def init_alerting(app):
    """Initialize alerting service with Flask app."""
    try:
        # Configure notification channels from app config
        email_config = app.config.get('ALERTING_EMAIL', {})
        if email_config.get('enabled', False):
            email_channel = EmailNotificationChannel('email', email_config)
            alerting_service.add_channel(email_channel)
        
        slack_config = app.config.get('ALERTING_SLACK', {})
        if slack_config.get('enabled', False):
            slack_channel = SlackNotificationChannel('slack', slack_config)
            alerting_service.add_channel(slack_channel)
        
        webhook_config = app.config.get('ALERTING_WEBHOOK', {})
        if webhook_config.get('enabled', False):
            webhook_channel = WebhookNotificationChannel('webhook', webhook_config)
            alerting_service.add_channel(webhook_channel)
        
        # Set up default alert rules
        setup_default_alert_rules()
        
        logger.info("Alerting service initialized")
        return alerting_service
        
    except Exception as e:
        logger.error("Failed to initialize alerting service", error=str(e))
        return None


def setup_default_alert_rules():
    """Set up default alert rules."""
    from app.services.monitoring_service import monitoring_service
    import psutil
    
    # High CPU usage alert
    def check_high_cpu():
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            return cpu_usage > 85
        except:
            return False
    
    cpu_rule = AlertRule(
        name="high_cpu_usage",
        condition=check_high_cpu,
        severity=AlertSeverity.HIGH,
        message="High CPU usage detected",
        description="CPU usage is above 85%",
        labels={"component": "system", "resource": "cpu"},
        cooldown_minutes=10
    )
    alerting_service.add_rule(cpu_rule)
    
    # High memory usage alert
    def check_high_memory():
        try:
            memory_usage = psutil.virtual_memory().percent
            return memory_usage > 90
        except:
            return False
    
    memory_rule = AlertRule(
        name="high_memory_usage",
        condition=check_high_memory,
        severity=AlertSeverity.CRITICAL,
        message="High memory usage detected",
        description="Memory usage is above 90%",
        labels={"component": "system", "resource": "memory"},
        cooldown_minutes=5
    )
    alerting_service.add_rule(memory_rule)
    
    # Disk space alert
    def check_disk_space():
        try:
            disk_usage = psutil.disk_usage('/').percent
            return disk_usage > 95
        except:
            return False
    
    disk_rule = AlertRule(
        name="low_disk_space",
        condition=check_disk_space,
        severity=AlertSeverity.CRITICAL,
        message="Low disk space detected",
        description="Disk usage is above 95%",
        labels={"component": "system", "resource": "disk"},
        cooldown_minutes=30
    )
    alerting_service.add_rule(disk_rule)
    
    logger.info("Default alert rules configured")