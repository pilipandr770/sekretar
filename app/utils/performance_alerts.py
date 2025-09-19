"""Performance alerting system."""
import logging
import smtplib
import json
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
from flask import current_app

from app.models.performance import PerformanceAlert
from app.utils.application_context_manager import with_app_context, safe_context


logger = logging.getLogger(__name__)


class AlertSeverity:
    """Alert severity levels."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class AlertManager:
    """Manages performance alerts and notifications."""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize alert manager with Flask app."""
        self.app = app
        logger.info("✅ Alert manager initialized")
    
    def send_alert(self, alert: PerformanceAlert) -> bool:
        """Send alert through configured channels."""
        if not current_app.config.get('ALERTING_ENABLED', True):
            return False
        
        success = True
        
        # Send email alert
        if self._should_send_email_alert(alert):
            success &= self._send_email_alert(alert)
        
        # Send Slack alert
        if self._should_send_slack_alert(alert):
            success &= self._send_slack_alert(alert)
        
        # Send webhook alert
        if self._should_send_webhook_alert(alert):
            success &= self._send_webhook_alert(alert)
        
        return success
    
    def _should_send_email_alert(self, alert: PerformanceAlert) -> bool:
        """Check if email alert should be sent."""
        config = current_app.config.get('ALERTING_EMAIL', {})
        if not config.get('enabled', False):
            return False
        
        min_severity = config.get('min_severity', 'high')
        return self._meets_severity_threshold(alert.severity, min_severity)
    
    def _should_send_slack_alert(self, alert: PerformanceAlert) -> bool:
        """Check if Slack alert should be sent."""
        config = current_app.config.get('ALERTING_SLACK', {})
        if not config.get('enabled', False):
            return False
        
        min_severity = config.get('min_severity', 'medium')
        return self._meets_severity_threshold(alert.severity, min_severity)
    
    def _should_send_webhook_alert(self, alert: PerformanceAlert) -> bool:
        """Check if webhook alert should be sent."""
        config = current_app.config.get('ALERTING_WEBHOOK', {})
        if not config.get('enabled', False):
            return False
        
        min_severity = config.get('min_severity', 'low')
        return self._meets_severity_threshold(alert.severity, min_severity)
    
    def _meets_severity_threshold(self, alert_severity: str, min_severity: str) -> bool:
        """Check if alert severity meets minimum threshold."""
        severity_levels = {
            AlertSeverity.LOW: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.HIGH: 3,
            AlertSeverity.CRITICAL: 4
        }
        
        alert_level = severity_levels.get(alert_severity, 1)
        min_level = severity_levels.get(min_severity, 1)
        
        return alert_level >= min_level
    
    def _send_email_alert(self, alert: PerformanceAlert) -> bool:
        """Send email alert."""
        try:
            config = current_app.config.get('ALERTING_EMAIL', {})
            smtp_config = config.get('smtp', {})
            
            if not smtp_config.get('username') or not smtp_config.get('password'):
                logger.warning("Email alerting configured but SMTP credentials missing")
                return False
            
            recipients = config.get('recipients', [])
            if not recipients:
                logger.warning("Email alerting configured but no recipients specified")
                return False
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = smtp_config.get('from_email', 'alerts@ai-secretary.com')
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"[{alert.severity.upper()}] {alert.title}"
            
            # Create email body
            body = self._create_email_body(alert)
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            server = smtplib.SMTP(smtp_config['host'], smtp_config['port'])
            if smtp_config.get('use_tls', True):
                server.starttls()
            
            server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email alert sent for {alert.title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _send_slack_alert(self, alert: PerformanceAlert) -> bool:
        """Send Slack alert."""
        try:
            config = current_app.config.get('ALERTING_SLACK', {})
            webhook_url = config.get('webhook_url')
            
            if not webhook_url:
                logger.warning("Slack alerting configured but webhook URL missing")
                return False
            
            # Create Slack message
            color = self._get_alert_color(alert.severity)
            message = {
                "attachments": [
                    {
                        "color": color,
                        "title": alert.title,
                        "text": alert.description,
                        "fields": [
                            {
                                "title": "Severity",
                                "value": alert.severity.upper(),
                                "short": True
                            },
                            {
                                "title": "Alert Type",
                                "value": alert.alert_type.replace('_', ' ').title(),
                                "short": True
                            },
                            {
                                "title": "First Occurrence",
                                "value": alert.first_occurrence.strftime('%Y-%m-%d %H:%M:%S UTC'),
                                "short": True
                            },
                            {
                                "title": "Occurrence Count",
                                "value": str(alert.occurrence_count),
                                "short": True
                            }
                        ]
                    }
                ]
            }
            
            if alert.endpoint:
                message["attachments"][0]["fields"].append({
                    "title": "Endpoint",
                    "value": alert.endpoint,
                    "short": True
                })
            
            if alert.metric_value and alert.threshold_value:
                message["attachments"][0]["fields"].append({
                    "title": "Metric Value",
                    "value": f"{alert.metric_value:.2f} (threshold: {alert.threshold_value:.2f})",
                    "short": True
                })
            
            # Send to Slack
            response = requests.post(webhook_url, json=message, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Slack alert sent for {alert.title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False
    
    def _send_webhook_alert(self, alert: PerformanceAlert) -> bool:
        """Send webhook alert."""
        try:
            config = current_app.config.get('ALERTING_WEBHOOK', {})
            webhook_url = config.get('url')
            
            if not webhook_url:
                logger.warning("Webhook alerting configured but URL missing")
                return False
            
            # Create webhook payload
            payload = {
                "alert_id": alert.id,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "title": alert.title,
                "description": alert.description,
                "endpoint": alert.endpoint,
                "service_name": alert.service_name,
                "metric_value": alert.metric_value,
                "threshold_value": alert.threshold_value,
                "status": alert.status,
                "first_occurrence": alert.first_occurrence.isoformat(),
                "last_occurrence": alert.last_occurrence.isoformat(),
                "occurrence_count": alert.occurrence_count,
                "alert_metadata": alert.alert_metadata
            }
            
            # Send webhook
            headers = config.get('headers', {})
            headers['Content-Type'] = 'application/json'
            
            timeout = config.get('timeout', 10)
            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
            
            logger.info(f"Webhook alert sent for {alert.title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False
    
    def _create_email_body(self, alert: PerformanceAlert) -> str:
        """Create HTML email body for alert."""
        color = self._get_alert_color(alert.severity)
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .alert-header {{ background-color: {color}; color: white; padding: 15px; border-radius: 5px 5px 0 0; }}
                .alert-body {{ border: 1px solid #ddd; border-top: none; padding: 20px; border-radius: 0 0 5px 5px; }}
                .alert-field {{ margin-bottom: 10px; }}
                .alert-label {{ font-weight: bold; color: #333; }}
                .alert-value {{ color: #666; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #999; }}
            </style>
        </head>
        <body>
            <div class="alert-header">
                <h2>{alert.title}</h2>
                <p>Severity: {alert.severity.upper()}</p>
            </div>
            <div class="alert-body">
                <div class="alert-field">
                    <span class="alert-label">Description:</span>
                    <span class="alert-value">{alert.description}</span>
                </div>
                <div class="alert-field">
                    <span class="alert-label">Alert Type:</span>
                    <span class="alert-value">{alert.alert_type.replace('_', ' ').title()}</span>
                </div>
                <div class="alert-field">
                    <span class="alert-label">First Occurrence:</span>
                    <span class="alert-value">{alert.first_occurrence.strftime('%Y-%m-%d %H:%M:%S UTC')}</span>
                </div>
                <div class="alert-field">
                    <span class="alert-label">Last Occurrence:</span>
                    <span class="alert-value">{alert.last_occurrence.strftime('%Y-%m-%d %H:%M:%S UTC')}</span>
                </div>
                <div class="alert-field">
                    <span class="alert-label">Occurrence Count:</span>
                    <span class="alert-value">{alert.occurrence_count}</span>
                </div>
        """
        
        if alert.endpoint:
            html += f"""
                <div class="alert-field">
                    <span class="alert-label">Endpoint:</span>
                    <span class="alert-value">{alert.endpoint}</span>
                </div>
            """
        
        if alert.service_name:
            html += f"""
                <div class="alert-field">
                    <span class="alert-label">Service:</span>
                    <span class="alert-value">{alert.service_name}</span>
                </div>
            """
        
        if alert.metric_value and alert.threshold_value:
            html += f"""
                <div class="alert-field">
                    <span class="alert-label">Metric Value:</span>
                    <span class="alert-value">{alert.metric_value:.2f} (threshold: {alert.threshold_value:.2f})</span>
                </div>
            """
        
        html += """
            </div>
            <div class="footer">
                <p>This alert was generated by AI Secretary Performance Monitoring System.</p>
                <p>Please investigate and take appropriate action.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _get_alert_color(self, severity: str) -> str:
        """Get color for alert severity."""
        colors = {
            AlertSeverity.LOW: '#36a64f',      # Green
            AlertSeverity.MEDIUM: '#ff9500',   # Orange
            AlertSeverity.HIGH: '#ff0000',     # Red
            AlertSeverity.CRITICAL: '#8b0000'  # Dark Red
        }
        return colors.get(severity, '#36a64f')
    
    def check_and_send_alerts(self):
        """Check for new alerts and send notifications."""
        try:
            # Get active alerts that haven't been sent yet
            active_alerts = PerformanceAlert.query.filter_by(status='active').all()
            
            for alert in active_alerts:
                # Check if this is a new alert or if it should be re-sent
                if self._should_send_alert_notification(alert):
                    self.send_alert(alert)
                    
        except Exception as e:
            logger.error(f"Failed to check and send alerts: {e}")
    
    def _should_send_alert_notification(self, alert: PerformanceAlert) -> bool:
        """Check if alert notification should be sent."""
        # Send notification for new alerts
        if alert.occurrence_count == 1:
            return True
        
        # Re-send critical alerts every 15 minutes
        if alert.severity == AlertSeverity.CRITICAL:
            time_since_last = datetime.utcnow() - alert.last_occurrence
            return time_since_last >= timedelta(minutes=15)
        
        # Re-send high severity alerts every hour
        if alert.severity == AlertSeverity.HIGH:
            time_since_last = datetime.utcnow() - alert.last_occurrence
            return time_since_last >= timedelta(hours=1)
        
        # Don't re-send medium/low severity alerts
        return False


class PerformanceThresholdChecker:
    """Checks performance metrics against thresholds and creates alerts."""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize threshold checker with Flask app."""
        self.app = app
        logger.info("✅ Performance threshold checker initialized")
    
    @with_app_context
    def check_error_rates(self, hours: int = 1):
        """Check error rates for endpoints with proper Flask context."""
        try:
            from sqlalchemy import func
            from app.models.performance import PerformanceMetric
            
            since = datetime.utcnow() - timedelta(hours=hours)
            threshold = current_app.config.get('ERROR_RATE_THRESHOLD', 0.05)  # 5%
            
            # Get error rates by endpoint
            results = PerformanceMetric.query.with_entities(
                PerformanceMetric.endpoint,
                func.count(PerformanceMetric.id).label('total_requests'),
                func.sum(func.case([(PerformanceMetric.status_code >= 400, 1)], else_=0)).label('error_count')
            ).filter(
                PerformanceMetric.timestamp >= since
            ).group_by(
                PerformanceMetric.endpoint
            ).having(
                func.count(PerformanceMetric.id) >= 10  # At least 10 requests
            ).all()
            
            for result in results:
                error_rate = (result.error_count or 0) / result.total_requests
                
                if error_rate >= threshold:
                    PerformanceAlert.create_or_update_alert(
                        alert_type='high_error_rate',
                        severity='high' if error_rate >= threshold * 2 else 'medium',
                        title=f'High Error Rate: {result.endpoint}',
                        description=f'Error rate for {result.endpoint} is {error_rate:.1%} ({result.error_count}/{result.total_requests})',
                        endpoint=result.endpoint,
                        metric_value=error_rate,
                        threshold_value=threshold
                    )
                    
        except Exception as e:
            logger.error(f"Failed to check error rates: {e}")
    
    @with_app_context
    def check_response_times(self, hours: int = 1):
        """Check average response times for endpoints with proper Flask context."""
        try:
            from sqlalchemy import func
            from app.models.performance import PerformanceMetric
            
            since = datetime.utcnow() - timedelta(hours=hours)
            threshold = current_app.config.get('RESPONSE_TIME_THRESHOLD', 2000)  # 2 seconds
            
            # Get average response times by endpoint
            results = PerformanceMetric.query.with_entities(
                PerformanceMetric.endpoint,
                func.count(PerformanceMetric.id).label('request_count'),
                func.avg(PerformanceMetric.response_time_ms).label('avg_response_time')
            ).filter(
                PerformanceMetric.timestamp >= since
            ).group_by(
                PerformanceMetric.endpoint
            ).having(
                func.count(PerformanceMetric.id) >= 5  # At least 5 requests
            ).all()
            
            for result in results:
                avg_time = result.avg_response_time or 0
                
                if avg_time >= threshold:
                    PerformanceAlert.create_or_update_alert(
                        alert_type='slow_endpoint',
                        severity='high' if avg_time >= threshold * 2 else 'medium',
                        title=f'Slow Endpoint: {result.endpoint}',
                        description=f'Average response time for {result.endpoint} is {avg_time:.0f}ms over {result.request_count} requests',
                        endpoint=result.endpoint,
                        metric_value=avg_time,
                        threshold_value=threshold
                    )
                    
        except Exception as e:
            logger.error(f"Failed to check response times: {e}")
    
    def run_all_checks(self):
        """Run all performance threshold checks."""
        self.check_error_rates()
        self.check_response_times()


# Global instances
alert_manager = AlertManager()
threshold_checker = PerformanceThresholdChecker()