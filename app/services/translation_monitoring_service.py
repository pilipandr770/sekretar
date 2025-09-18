"""
Translation system monitoring and alerting service.
"""

import os
import time
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from flask import current_app
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

# Prometheus metrics
TRANSLATION_REQUESTS = Counter(
    'translation_requests_total',
    'Total number of translation requests',
    ['language', 'status']
)

TRANSLATION_RESPONSE_TIME = Histogram(
    'translation_response_time_seconds',
    'Translation response time in seconds',
    ['language']
)

TRANSLATION_CACHE_HITS = Counter(
    'translation_cache_hits_total',
    'Total number of translation cache hits',
    ['cache_type']
)

TRANSLATION_CACHE_MISSES = Counter(
    'translation_cache_misses_total',
    'Total number of translation cache misses',
    ['cache_type']
)

TRANSLATION_ERRORS = Counter(
    'translation_errors_total',
    'Total number of translation errors',
    ['language', 'error_type']
)

TRANSLATION_FILE_SIZE = Gauge(
    'translation_file_size_bytes',
    'Size of translation files in bytes',
    ['language', 'file_type']
)

TRANSLATION_COVERAGE = Gauge(
    'translation_coverage_percentage',
    'Translation coverage percentage',
    ['language']
)

@dataclass
class TranslationAlert:
    """Translation system alert."""
    id: str
    severity: str  # critical, warning, info
    title: str
    message: str
    timestamp: datetime
    language: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None

class TranslationMonitoringService:
    """Service for monitoring translation system health and performance."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.alerts = []
        self.alert_handlers = []
        self.metrics_enabled = True
        self.last_health_check = None
        self.health_check_interval = 300  # 5 minutes
        
        # Thresholds for alerting
        self.thresholds = {
            'response_time_warning': 0.5,  # 500ms
            'response_time_critical': 2.0,  # 2s
            'cache_hit_rate_warning': 50.0,  # 50%
            'cache_hit_rate_critical': 20.0,  # 20%
            'error_rate_warning': 5.0,  # 5%
            'error_rate_critical': 15.0,  # 15%
            'coverage_warning': 80.0,  # 80%
            'coverage_critical': 60.0,  # 60%
        }
    
    def record_translation_request(self, language: str, success: bool, response_time: float):
        """Record a translation request for monitoring."""
        if not self.metrics_enabled:
            return
        
        status = 'success' if success else 'error'
        
        # Update Prometheus metrics
        TRANSLATION_REQUESTS.labels(language=language, status=status).inc()
        TRANSLATION_RESPONSE_TIME.labels(language=language).observe(response_time)
        
        # Check thresholds
        self._check_response_time_threshold(language, response_time)
    
    def record_cache_hit(self, cache_type: str):
        """Record a cache hit."""
        if self.metrics_enabled:
            TRANSLATION_CACHE_HITS.labels(cache_type=cache_type).inc()
    
    def record_cache_miss(self, cache_type: str):
        """Record a cache miss."""
        if self.metrics_enabled:
            TRANSLATION_CACHE_MISSES.labels(cache_type=cache_type).inc()
    
    def record_translation_error(self, language: str, error_type: str):
        """Record a translation error."""
        if self.metrics_enabled:
            TRANSLATION_ERRORS.labels(language=language, error_type=error_type).inc()
        
        # Create alert for critical errors
        if error_type in ['file_not_found', 'compilation_error', 'system_error']:
            self._create_alert(
                severity='critical',
                title=f'Translation Error: {error_type}',
                message=f'Critical translation error in {language}: {error_type}',
                language=language
            )
    
    def update_file_metrics(self):
        """Update translation file size metrics."""
        if not self.metrics_enabled:
            return
        
        languages = ['en', 'de', 'uk']
        
        for language in languages:
            # Update .po file size
            po_path = os.path.join(
                current_app.root_path,
                'translations',
                language,
                'LC_MESSAGES',
                'messages.po'
            )
            
            if os.path.exists(po_path):
                size = os.path.getsize(po_path)
                TRANSLATION_FILE_SIZE.labels(language=language, file_type='po').set(size)
            
            # Update .mo file size
            mo_path = os.path.join(
                current_app.root_path,
                'translations',
                language,
                'LC_MESSAGES',
                'messages.mo'
            )
            
            if os.path.exists(mo_path):
                size = os.path.getsize(mo_path)
                TRANSLATION_FILE_SIZE.labels(language=language, file_type='mo').set(size)
    
    def update_coverage_metrics(self):
        """Update translation coverage metrics."""
        if not self.metrics_enabled:
            return
        
        try:
            from app.services.translation_service import TranslationService
            translation_service = TranslationService()
            
            coverage = translation_service.get_translation_coverage()
            
            for language, percentage in coverage.items():
                TRANSLATION_COVERAGE.labels(language=language).set(percentage)
                
                # Check coverage thresholds
                self._check_coverage_threshold(language, percentage)
                
        except Exception as e:
            self.logger.error(f"Failed to update coverage metrics: {e}")
    
    def _check_response_time_threshold(self, language: str, response_time: float):
        """Check response time against thresholds."""
        if response_time > self.thresholds['response_time_critical']:
            self._create_alert(
                severity='critical',
                title='Critical Response Time',
                message=f'{language} translation response time is {response_time:.2f}s (threshold: {self.thresholds["response_time_critical"]}s)',
                language=language,
                metric_name='response_time',
                metric_value=response_time,
                threshold=self.thresholds['response_time_critical']
            )
        elif response_time > self.thresholds['response_time_warning']:
            self._create_alert(
                severity='warning',
                title='Slow Response Time',
                message=f'{language} translation response time is {response_time:.2f}s (threshold: {self.thresholds["response_time_warning"]}s)',
                language=language,
                metric_name='response_time',
                metric_value=response_time,
                threshold=self.thresholds['response_time_warning']
            )
    
    def _check_coverage_threshold(self, language: str, coverage: float):
        """Check coverage against thresholds."""
        if coverage < self.thresholds['coverage_critical']:
            self._create_alert(
                severity='critical',
                title='Critical Translation Coverage',
                message=f'{language} translation coverage is {coverage:.1f}% (threshold: {self.thresholds["coverage_critical"]}%)',
                language=language,
                metric_name='coverage',
                metric_value=coverage,
                threshold=self.thresholds['coverage_critical']
            )
        elif coverage < self.thresholds['coverage_warning']:
            self._create_alert(
                severity='warning',
                title='Low Translation Coverage',
                message=f'{language} translation coverage is {coverage:.1f}% (threshold: {self.thresholds["coverage_warning"]}%)',
                language=language,
                metric_name='coverage',
                metric_value=coverage,
                threshold=self.thresholds['coverage_warning']
            )
    
    def _create_alert(self, severity: str, title: str, message: str, **kwargs):
        """Create a new alert."""
        alert_id = f"{severity}_{int(time.time())}_{hash(message) % 10000}"
        
        alert = TranslationAlert(
            id=alert_id,
            severity=severity,
            title=title,
            message=message,
            timestamp=datetime.utcnow(),
            **kwargs
        )
        
        self.alerts.append(alert)
        self.logger.warning(f"Translation alert created: {title} - {message}")
        
        # Trigger alert handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                self.logger.error(f"Alert handler failed: {e}")
        
        # Keep only recent alerts (last 24 hours)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.alerts = [a for a in self.alerts if a.timestamp > cutoff]
    
    def get_active_alerts(self) -> List[TranslationAlert]:
        """Get all active (unresolved) alerts."""
        return [alert for alert in self.alerts if not alert.resolved]
    
    def get_alerts_by_severity(self, severity: str) -> List[TranslationAlert]:
        """Get alerts by severity level."""
        return [alert for alert in self.alerts if alert.severity == severity and not alert.resolved]
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert by ID."""
        for alert in self.alerts:
            if alert.id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                self.logger.info(f"Alert resolved: {alert.title}")
                return True
        return False
    
    def add_alert_handler(self, handler):
        """Add an alert handler function."""
        self.alert_handlers.append(handler)
    
    def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        now = datetime.utcnow()
        
        # Skip if too recent
        if (self.last_health_check and 
            (now - self.last_health_check).total_seconds() < self.health_check_interval):
            return {'status': 'skipped', 'reason': 'too_recent'}
        
        self.last_health_check = now
        
        health_status = {
            'timestamp': now.isoformat(),
            'overall_status': 'healthy',
            'checks': {},
            'alerts_summary': {
                'critical': len(self.get_alerts_by_severity('critical')),
                'warning': len(self.get_alerts_by_severity('warning')),
                'info': len(self.get_alerts_by_severity('info'))
            }
        }
        
        # Check translation files
        health_status['checks']['files'] = self._check_translation_files()
        
        # Check cache performance
        health_status['checks']['cache'] = self._check_cache_performance()
        
        # Check translation coverage
        health_status['checks']['coverage'] = self._check_translation_coverage()
        
        # Check system resources
        health_status['checks']['resources'] = self._check_system_resources()
        
        # Determine overall status
        failed_checks = [name for name, check in health_status['checks'].items() 
                        if check.get('status') == 'fail']
        
        if failed_checks:
            health_status['overall_status'] = 'unhealthy'
            health_status['failed_checks'] = failed_checks
        elif health_status['alerts_summary']['critical'] > 0:
            health_status['overall_status'] = 'critical'
        elif health_status['alerts_summary']['warning'] > 0:
            health_status['overall_status'] = 'warning'
        
        return health_status
    
    def _check_translation_files(self) -> Dict[str, Any]:
        """Check translation file status."""
        languages = ['en', 'de', 'uk']
        file_status = {'status': 'pass', 'languages': {}}
        
        for language in languages:
            lang_status = {'po_exists': False, 'mo_exists': False, 'po_size': 0, 'mo_size': 0}
            
            po_path = os.path.join(current_app.root_path, 'translations', language, 'LC_MESSAGES', 'messages.po')
            mo_path = os.path.join(current_app.root_path, 'translations', language, 'LC_MESSAGES', 'messages.mo')
            
            if os.path.exists(po_path):
                lang_status['po_exists'] = True
                lang_status['po_size'] = os.path.getsize(po_path)
            else:
                file_status['status'] = 'fail'
            
            if os.path.exists(mo_path):
                lang_status['mo_exists'] = True
                lang_status['mo_size'] = os.path.getsize(mo_path)
            else:
                file_status['status'] = 'fail'
            
            file_status['languages'][language] = lang_status
        
        return file_status
    
    def _check_cache_performance(self) -> Dict[str, Any]:
        """Check cache performance."""
        try:
            from app.services.translation_cache_service import get_translation_cache_service
            cache_service = get_translation_cache_service()
            stats = cache_service.get_cache_stats()
            
            cache_status = {
                'status': 'pass',
                'hit_rate': stats.get('hit_rate', 0),
                'stats': stats
            }
            
            if stats.get('hit_rate', 0) < self.thresholds['cache_hit_rate_critical']:
                cache_status['status'] = 'fail'
            elif stats.get('hit_rate', 0) < self.thresholds['cache_hit_rate_warning']:
                cache_status['status'] = 'warning'
            
            return cache_status
            
        except Exception as e:
            return {
                'status': 'fail',
                'error': str(e)
            }
    
    def _check_translation_coverage(self) -> Dict[str, Any]:
        """Check translation coverage."""
        try:
            from app.services.translation_service import TranslationService
            translation_service = TranslationService()
            coverage = translation_service.get_translation_coverage()
            
            coverage_status = {
                'status': 'pass',
                'coverage': coverage
            }
            
            for language, percentage in coverage.items():
                if percentage < self.thresholds['coverage_critical']:
                    coverage_status['status'] = 'fail'
                    break
                elif percentage < self.thresholds['coverage_warning']:
                    coverage_status['status'] = 'warning'
            
            return coverage_status
            
        except Exception as e:
            return {
                'status': 'fail',
                'error': str(e)
            }
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resources related to translations."""
        try:
            import psutil
            
            # Check memory usage
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            resource_status = {
                'status': 'pass',
                'memory_percent': memory.percent,
                'disk_percent': disk.percent
            }
            
            if memory.percent > 90 or disk.percent > 95:
                resource_status['status'] = 'fail'
            elif memory.percent > 80 or disk.percent > 90:
                resource_status['status'] = 'warning'
            
            return resource_status
            
        except ImportError:
            return {
                'status': 'skip',
                'reason': 'psutil not available'
            }
        except Exception as e:
            return {
                'status': 'fail',
                'error': str(e)
            }
    
    def get_metrics(self) -> str:
        """Get Prometheus metrics."""
        if not self.metrics_enabled:
            return ""
        
        # Update file and coverage metrics
        self.update_file_metrics()
        self.update_coverage_metrics()
        
        return generate_latest()
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for monitoring dashboard."""
        return {
            'health_status': self.perform_health_check(),
            'active_alerts': [asdict(alert) for alert in self.get_active_alerts()],
            'alert_summary': {
                'critical': len(self.get_alerts_by_severity('critical')),
                'warning': len(self.get_alerts_by_severity('warning')),
                'info': len(self.get_alerts_by_severity('info'))
            },
            'metrics_enabled': self.metrics_enabled,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None
        }

# Email alert handler
def email_alert_handler(alert: TranslationAlert):
    """Send email alerts for critical issues."""
    if alert.severity != 'critical':
        return
    
    try:
        # Email configuration from Flask config
        smtp_server = current_app.config.get('MAIL_SERVER')
        smtp_port = current_app.config.get('MAIL_PORT', 587)
        smtp_username = current_app.config.get('MAIL_USERNAME')
        smtp_password = current_app.config.get('MAIL_PASSWORD')
        alert_recipients = current_app.config.get('TRANSLATION_ALERT_RECIPIENTS', [])
        
        if not all([smtp_server, smtp_username, smtp_password, alert_recipients]):
            current_app.logger.warning("Email alert configuration incomplete")
            return
        
        # Create email
        msg = MimeMultipart()
        msg['From'] = smtp_username
        msg['To'] = ', '.join(alert_recipients)
        msg['Subject'] = f"[CRITICAL] Translation System Alert: {alert.title}"
        
        body = f"""
Translation System Critical Alert

Title: {alert.title}
Message: {alert.message}
Language: {alert.language or 'N/A'}
Timestamp: {alert.timestamp.isoformat()}

Please investigate this issue immediately.

Alert ID: {alert.id}
        """
        
        msg.attach(MimeText(body, 'plain'))
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        current_app.logger.info(f"Critical alert email sent: {alert.title}")
        
    except Exception as e:
        current_app.logger.error(f"Failed to send alert email: {e}")

# Global monitoring service instance
_monitoring_service = None

def get_translation_monitoring_service() -> TranslationMonitoringService:
    """Get or create the global translation monitoring service."""
    global _monitoring_service
    
    if _monitoring_service is None:
        _monitoring_service = TranslationMonitoringService()
        
        # Add default alert handlers
        _monitoring_service.add_alert_handler(email_alert_handler)
    
    return _monitoring_service

def init_translation_monitoring(app):
    """Initialize translation monitoring with Flask app."""
    global _monitoring_service
    
    _monitoring_service = TranslationMonitoringService()
    
    # Configure from app config
    if app.config.get('TRANSLATION_MONITORING_ENABLED', True):
        _monitoring_service.metrics_enabled = True
        
        # Add alert handlers
        _monitoring_service.add_alert_handler(email_alert_handler)
        
        # Add monitoring endpoints
        @app.route('/admin/translation/health')
        def translation_health():
            from flask import jsonify
            return jsonify(_monitoring_service.perform_health_check())
        
        @app.route('/admin/translation/alerts')
        def translation_alerts():
            from flask import jsonify
            return jsonify([asdict(alert) for alert in _monitoring_service.get_active_alerts()])
        
        @app.route('/admin/translation/metrics')
        def translation_metrics():
            from flask import Response
            return Response(_monitoring_service.get_metrics(), mimetype='text/plain')
        
        @app.route('/admin/translation/dashboard')
        def translation_dashboard():
            from flask import jsonify
            return jsonify(_monitoring_service.get_dashboard_data())
        
        app.logger.info("Translation monitoring initialized")
    else:
        _monitoring_service.metrics_enabled = False
        app.logger.info("Translation monitoring disabled")
    
    return _monitoring_service