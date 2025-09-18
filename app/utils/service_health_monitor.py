"""
Service Health Monitor

This module provides comprehensive service health monitoring with feature flags,
Redis availability detection, and health check endpoints.
"""
import os
import logging
import time
import threading
import socket
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import redis
import psycopg2
import sqlite3
import requests
from flask import current_app


logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Health check result."""
    service_name: str
    status: ServiceStatus
    response_time_ms: float
    timestamp: datetime
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceConfig:
    """Service configuration for health monitoring."""
    name: str
    check_function: Callable[[], HealthCheckResult]
    check_interval: int = 30  # seconds
    timeout: int = 5  # seconds
    retry_attempts: int = 3
    retry_delay: int = 1  # seconds
    enabled: bool = True
    critical: bool = False  # If True, service failure affects overall health


class ServiceHealthMonitor:
    """
    Comprehensive service health monitoring system.
    
    This class monitors the availability of various services including databases,
    cache systems, external APIs, and other dependencies. It provides feature
    flags based on service availability and health check endpoints.
    """
    
    def __init__(self, app=None):
        """Initialize service health monitor."""
        self.app = app
        self._services: Dict[str, ServiceConfig] = {}
        self._health_results: Dict[str, HealthCheckResult] = {}
        self._feature_flags: Dict[str, bool] = {}
        self._health_callbacks: List[Callable[[str, HealthCheckResult], None]] = []
        
        # Monitoring control
        self._monitoring_active = False
        self._monitor_thread = None
        self._stop_event = threading.Event()
        
        # Configuration
        self._default_check_interval = 30  # seconds
        self._default_timeout = 5  # seconds
        self._health_check_enabled = True
        
        # Statistics
        self._stats = {
            'total_checks': 0,
            'successful_checks': 0,
            'failed_checks': 0,
            'last_check_time': None,
            'uptime_start': datetime.now()
        }
        
        if app is not None:
            self.init_app(app)
        else:
            # Register default services even without Flask app
            self._register_default_services()
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['service_health_monitor'] = self
        
        # Load configuration
        self._default_check_interval = app.config.get('HEALTH_CHECK_INTERVAL', 30)
        self._default_timeout = app.config.get('HEALTH_CHECK_TIMEOUT', 5)
        self._health_check_enabled = app.config.get('HEALTH_CHECK_ENABLED', True)
        
        # Register default services
        self._register_default_services()
        
        # Start monitoring if enabled
        if self._health_check_enabled:
            self.start_monitoring()
    
    def _register_default_services(self):
        """Register default services for monitoring."""
        # Database services
        self.register_service(ServiceConfig(
            name='postgresql',
            check_function=self._check_postgresql,
            check_interval=self._default_check_interval,
            timeout=self._default_timeout,
            critical=True
        ))
        
        self.register_service(ServiceConfig(
            name='sqlite',
            check_function=self._check_sqlite,
            check_interval=self._default_check_interval,
            timeout=self._default_timeout,
            critical=True
        ))
        
        # Cache services
        self.register_service(ServiceConfig(
            name='redis',
            check_function=self._check_redis,
            check_interval=self._default_check_interval,
            timeout=self._default_timeout,
            critical=False
        ))
        
        # External API services (check environment variables directly if no app)
        openai_key = (self.app.config.get('OPENAI_API_KEY') if self.app else None) or os.environ.get('OPENAI_API_KEY')
        if openai_key:
            self.register_service(ServiceConfig(
                name='openai',
                check_function=self._check_openai,
                check_interval=60,  # Less frequent for external APIs
                timeout=10,
                critical=False
            ))
        
        stripe_key = (self.app.config.get('STRIPE_SECRET_KEY') if self.app else None) or os.environ.get('STRIPE_SECRET_KEY')
        if stripe_key:
            self.register_service(ServiceConfig(
                name='stripe',
                check_function=self._check_stripe,
                check_interval=60,
                timeout=10,
                critical=False
            ))
        
        google_client_id = (self.app.config.get('GOOGLE_CLIENT_ID') if self.app else None) or os.environ.get('GOOGLE_CLIENT_ID')
        if google_client_id:
            self.register_service(ServiceConfig(
                name='google_oauth',
                check_function=self._check_google_oauth,
                check_interval=60,
                timeout=10,
                critical=False
            ))
        
        telegram_token = (self.app.config.get('TELEGRAM_BOT_TOKEN') if self.app else None) or os.environ.get('TELEGRAM_BOT_TOKEN')
        if telegram_token:
            self.register_service(ServiceConfig(
                name='telegram',
                check_function=self._check_telegram,
                check_interval=60,
                timeout=10,
                critical=False
            ))
        
        signal_phone = (self.app.config.get('SIGNAL_PHONE_NUMBER') if self.app else None) or os.environ.get('SIGNAL_PHONE_NUMBER')
        if signal_phone:
            self.register_service(ServiceConfig(
                name='signal',
                check_function=self._check_signal,
                check_interval=60,
                timeout=10,
                critical=False
            ))
        
        # Initialize feature flags after registering services
        self._update_feature_flags()
    
    def register_service(self, service_config: ServiceConfig):
        """
        Register a service for health monitoring.
        
        Args:
            service_config: Service configuration
        """
        self._services[service_config.name] = service_config
        logger.info(f"📋 Registered service for monitoring: {service_config.name}")
    
    def unregister_service(self, service_name: str):
        """
        Unregister a service from health monitoring.
        
        Args:
            service_name: Name of service to unregister
        """
        if service_name in self._services:
            del self._services[service_name]
            if service_name in self._health_results:
                del self._health_results[service_name]
            logger.info(f"📋 Unregistered service: {service_name}")
    
    def start_monitoring(self):
        """Start background health monitoring."""
        if self._monitoring_active:
            return
        
        self._stop_event.clear()
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name='ServiceHealthMonitor'
        )
        self._monitor_thread.start()
        logger.info("🔍 Service health monitoring started")
    
    def stop_monitoring(self):
        """Stop background health monitoring."""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        self._stop_event.set()
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
        
        logger.info("⏹️ Service health monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        next_checks = {name: datetime.now() for name in self._services.keys()}
        
        while self._monitoring_active and not self._stop_event.is_set():
            try:
                current_time = datetime.now()
                
                # Check which services need health checks
                for service_name, service_config in self._services.items():
                    if not service_config.enabled:
                        continue
                    
                    if current_time >= next_checks[service_name]:
                        # Perform health check
                        result = self._perform_health_check(service_config)
                        self._health_results[service_name] = result
                        
                        # Update feature flags
                        self._update_feature_flags()
                        
                        # Call callbacks
                        for callback in self._health_callbacks:
                            try:
                                callback(service_name, result)
                            except Exception as e:
                                logger.error(f"Health callback error for {service_name}: {e}")
                        
                        # Schedule next check
                        next_checks[service_name] = current_time + timedelta(seconds=service_config.check_interval)
                
                # Sleep for a short interval
                self._stop_event.wait(1)
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                self._stop_event.wait(5)  # Wait longer on error
    
    def _perform_health_check(self, service_config: ServiceConfig) -> HealthCheckResult:
        """
        Perform health check for a service.
        
        Args:
            service_config: Service configuration
            
        Returns:
            Health check result
        """
        self._stats['total_checks'] += 1
        self._stats['last_check_time'] = datetime.now()
        
        for attempt in range(service_config.retry_attempts):
            try:
                start_time = time.time()
                result = service_config.check_function()
                
                if result.status == ServiceStatus.HEALTHY:
                    self._stats['successful_checks'] += 1
                    return result
                
                # If not healthy and we have more attempts, retry
                if attempt < service_config.retry_attempts - 1:
                    time.sleep(service_config.retry_delay)
                    continue
                
                # Final attempt failed
                self._stats['failed_checks'] += 1
                return result
                
            except Exception as e:
                if attempt < service_config.retry_attempts - 1:
                    time.sleep(service_config.retry_delay)
                    continue
                
                # All attempts failed
                self._stats['failed_checks'] += 1
                return HealthCheckResult(
                    service_name=service_config.name,
                    status=ServiceStatus.UNHEALTHY,
                    response_time_ms=0,
                    timestamp=datetime.now(),
                    error_message=str(e)
                )
    
    def check_service_health(self, service_name: str) -> bool:
        """
        Check if a specific service is healthy.
        
        Args:
            service_name: Name of service to check
            
        Returns:
            True if service is healthy, False otherwise
        """
        if service_name not in self._services:
            return False
        
        if service_name not in self._health_results:
            # Perform immediate check if no cached result
            service_config = self._services[service_name]
            result = self._perform_health_check(service_config)
            self._health_results[service_name] = result
        
        result = self._health_results[service_name]
        return result.status == ServiceStatus.HEALTHY
    
    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all monitored services.
        
        Returns:
            Dictionary with service status information
        """
        status = {}
        
        for service_name, service_config in self._services.items():
            result = self._health_results.get(service_name)
            
            status[service_name] = {
                'enabled': service_config.enabled,
                'critical': service_config.critical,
                'status': result.status.value if result else ServiceStatus.UNKNOWN.value,
                'healthy': result.status == ServiceStatus.HEALTHY if result else False,
                'response_time_ms': result.response_time_ms if result else None,
                'last_check': result.timestamp.isoformat() if result else None,
                'error_message': result.error_message if result else None,
                'metadata': result.metadata if result else {}
            }
        
        return status
    
    def get_overall_health(self) -> Dict[str, Any]:
        """
        Get overall system health status.
        
        Returns:
            Dictionary with overall health information
        """
        healthy_services = 0
        unhealthy_services = 0
        critical_unhealthy = 0
        total_services = len(self._services)
        
        for service_name, service_config in self._services.items():
            if not service_config.enabled:
                continue
            
            result = self._health_results.get(service_name)
            if result and result.status == ServiceStatus.HEALTHY:
                healthy_services += 1
            else:
                unhealthy_services += 1
                if service_config.critical:
                    critical_unhealthy += 1
        
        # Determine overall status
        if critical_unhealthy > 0:
            overall_status = ServiceStatus.UNHEALTHY
        elif unhealthy_services > 0:
            overall_status = ServiceStatus.DEGRADED
        else:
            overall_status = ServiceStatus.HEALTHY
        
        uptime = datetime.now() - self._stats['uptime_start']
        
        return {
            'status': overall_status.value,
            'healthy': overall_status == ServiceStatus.HEALTHY,
            'total_services': total_services,
            'healthy_services': healthy_services,
            'unhealthy_services': unhealthy_services,
            'critical_unhealthy': critical_unhealthy,
            'uptime_seconds': uptime.total_seconds(),
            'monitoring_active': self._monitoring_active,
            'last_check': self._stats['last_check_time'].isoformat() if self._stats['last_check_time'] else None,
            'statistics': self._stats.copy()
        }
    
    def _update_feature_flags(self):
        """Update feature flags based on service health."""
        # Database features
        postgresql_healthy = self.check_service_health('postgresql')
        sqlite_healthy = self.check_service_health('sqlite')
        
        self._feature_flags.update({
            'database_postgresql': postgresql_healthy,
            'database_sqlite': sqlite_healthy,
            'database_available': postgresql_healthy or sqlite_healthy,
        })
        
        # Cache features
        redis_healthy = self.check_service_health('redis')
        self._feature_flags.update({
            'cache_redis': redis_healthy,
            'cache_available': True,  # Simple cache always available
            'rate_limiting': redis_healthy,  # Rate limiting requires Redis
            'session_storage': redis_healthy,  # Redis session storage
        })
        
        # External service features
        external_services = ['openai', 'stripe', 'google_oauth', 'telegram', 'signal']
        for service in external_services:
            if service in self._services:
                self._feature_flags[service] = self.check_service_health(service)
        
        # Composite features
        self._feature_flags.update({
            'ai_features': self._feature_flags.get('openai', False),
            'payment_processing': self._feature_flags.get('stripe', False),
            'oauth_login': self._feature_flags.get('google_oauth', False),
            'messaging': any([
                self._feature_flags.get('telegram', False),
                self._feature_flags.get('signal', False)
            ]),
            'background_tasks': redis_healthy,  # Celery requires Redis
        })
    
    def get_feature_flags(self) -> Dict[str, bool]:
        """
        Get current feature flags.
        
        Returns:
            Dictionary of feature flags
        """
        return self._feature_flags.copy()
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """
        Check if a feature is enabled.
        
        Args:
            feature_name: Name of feature to check
            
        Returns:
            True if feature is enabled, False otherwise
        """
        return self._feature_flags.get(feature_name, False)
    
    def enable_feature(self, feature_name: str):
        """
        Manually enable a feature.
        
        Args:
            feature_name: Name of feature to enable
        """
        self._feature_flags[feature_name] = True
        logger.info(f"🟢 Feature enabled: {feature_name}")
    
    def disable_feature(self, feature_name: str):
        """
        Manually disable a feature.
        
        Args:
            feature_name: Name of feature to disable
        """
        self._feature_flags[feature_name] = False
        logger.info(f"🔴 Feature disabled: {feature_name}")
    
    def add_health_callback(self, callback: Callable[[str, HealthCheckResult], None]):
        """
        Add callback for health status changes.
        
        Args:
            callback: Function called with (service_name, result) on health changes
        """
        self._health_callbacks.append(callback)
    
    def remove_health_callback(self, callback: Callable[[str, HealthCheckResult], None]):
        """
        Remove health callback.
        
        Args:
            callback: Callback function to remove
        """
        if callback in self._health_callbacks:
            self._health_callbacks.remove(callback)
    
    # Health check implementations
    def _check_postgresql(self) -> HealthCheckResult:
        """Check PostgreSQL health."""
        start_time = time.time()
        
        try:
            # Get connection string
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                host = os.environ.get('DB_HOST', 'localhost')
                port = os.environ.get('DB_PORT', '5432')
                database = os.environ.get('DB_NAME', 'ai_secretary')
                username = os.environ.get('DB_USER', 'postgres')
                password = os.environ.get('DB_PASSWORD', '')
                
                if password:
                    database_url = f'postgresql://{username}:{password}@{host}:{port}/{database}'
                else:
                    database_url = f'postgresql://{username}@{host}:{port}/{database}'
            
            # Handle Render.com format
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
            # Test connection
            conn = psycopg2.connect(database_url, connect_timeout=self._default_timeout)
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.fetchone()
            cursor.close()
            conn.close()
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name='postgresql',
                status=ServiceStatus.HEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                metadata={'connection_string': self._mask_password(database_url)}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name='postgresql',
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _check_sqlite(self) -> HealthCheckResult:
        """Check SQLite health."""
        start_time = time.time()
        
        try:
            # Get SQLite database path
            sqlite_url = os.environ.get('SQLITE_DATABASE_URL', 'sqlite:///ai_secretary.db')
            
            if sqlite_url.startswith('sqlite:///'):
                db_path = sqlite_url[10:]  # Remove 'sqlite:///'
                
                if db_path == ':memory:':
                    conn = sqlite3.connect(':memory:', timeout=self._default_timeout)
                else:
                    conn = sqlite3.connect(db_path, timeout=self._default_timeout)
                
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                cursor.fetchone()
                cursor.close()
                conn.close()
                
                response_time = (time.time() - start_time) * 1000
                
                return HealthCheckResult(
                    service_name='sqlite',
                    status=ServiceStatus.HEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    metadata={'database_path': db_path}
                )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name='sqlite',
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _check_redis(self) -> HealthCheckResult:
        """Check Redis health."""
        start_time = time.time()
        
        try:
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
            r = redis.from_url(redis_url, socket_connect_timeout=self._default_timeout)
            r.ping()
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name='redis',
                status=ServiceStatus.HEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                metadata={'redis_url': redis_url}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name='redis',
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _check_openai(self) -> HealthCheckResult:
        """Check OpenAI API health."""
        start_time = time.time()
        
        try:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise Exception("OpenAI API key not configured")
            
            # Simple API call to check connectivity
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                'https://api.openai.com/v1/models',
                headers=headers,
                timeout=self._default_timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return HealthCheckResult(
                    service_name='openai',
                    status=ServiceStatus.HEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    metadata={'api_available': True}
                )
            else:
                return HealthCheckResult(
                    service_name='openai',
                    status=ServiceStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    error_message=f"API returned status {response.status_code}"
                )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name='openai',
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _check_stripe(self) -> HealthCheckResult:
        """Check Stripe API health."""
        start_time = time.time()
        
        try:
            api_key = os.environ.get('STRIPE_SECRET_KEY')
            if not api_key:
                raise Exception("Stripe API key not configured")
            
            # Simple API call to check connectivity
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.get(
                'https://api.stripe.com/v1/account',
                headers=headers,
                timeout=self._default_timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return HealthCheckResult(
                    service_name='stripe',
                    status=ServiceStatus.HEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    metadata={'api_available': True}
                )
            else:
                return HealthCheckResult(
                    service_name='stripe',
                    status=ServiceStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    error_message=f"API returned status {response.status_code}"
                )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name='stripe',
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _check_google_oauth(self) -> HealthCheckResult:
        """Check Google OAuth health."""
        start_time = time.time()
        
        try:
            client_id = os.environ.get('GOOGLE_CLIENT_ID')
            if not client_id:
                raise Exception("Google OAuth client ID not configured")
            
            # Check if we can reach Google's OAuth discovery endpoint
            response = requests.get(
                'https://accounts.google.com/.well-known/openid_configuration',
                timeout=self._default_timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return HealthCheckResult(
                    service_name='google_oauth',
                    status=ServiceStatus.HEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    metadata={'oauth_available': True}
                )
            else:
                return HealthCheckResult(
                    service_name='google_oauth',
                    status=ServiceStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    error_message=f"OAuth endpoint returned status {response.status_code}"
                )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name='google_oauth',
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _check_telegram(self) -> HealthCheckResult:
        """Check Telegram Bot API health."""
        start_time = time.time()
        
        try:
            bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                raise Exception("Telegram bot token not configured")
            
            # Check bot info
            response = requests.get(
                f'https://api.telegram.org/bot{bot_token}/getMe',
                timeout=self._default_timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return HealthCheckResult(
                        service_name='telegram',
                        status=ServiceStatus.HEALTHY,
                        response_time_ms=response_time,
                        timestamp=datetime.now(),
                        metadata={
                            'bot_available': True,
                            'bot_username': data.get('result', {}).get('username')
                        }
                    )
            
            return HealthCheckResult(
                service_name='telegram',
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=f"API returned status {response.status_code}"
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name='telegram',
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _check_signal(self) -> HealthCheckResult:
        """Check Signal CLI health."""
        start_time = time.time()
        
        try:
            signal_cli_path = os.environ.get('SIGNAL_CLI_PATH', 'signal-cli')
            phone_number = os.environ.get('SIGNAL_PHONE_NUMBER')
            
            if not phone_number:
                raise Exception("Signal phone number not configured")
            
            # Check if signal-cli is available
            import subprocess
            result = subprocess.run(
                [signal_cli_path, '--version'],
                capture_output=True,
                text=True,
                timeout=self._default_timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if result.returncode == 0:
                return HealthCheckResult(
                    service_name='signal',
                    status=ServiceStatus.HEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    metadata={
                        'cli_available': True,
                        'version': result.stdout.strip()
                    }
                )
            else:
                return HealthCheckResult(
                    service_name='signal',
                    status=ServiceStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    error_message=f"Signal CLI returned code {result.returncode}"
                )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name='signal',
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _mask_password(self, connection_string: str) -> str:
        """Mask password in connection string for logging."""
        if '://' in connection_string and '@' in connection_string:
            parts = connection_string.split('://', 1)
            if len(parts) == 2:
                protocol = parts[0]
                rest = parts[1]
                
                if '@' in rest:
                    auth_part, host_part = rest.split('@', 1)
                    if ':' in auth_part:
                        username, password = auth_part.split(':', 1)
                        masked_auth = f"{username}:{'*' * len(password)}"
                        return f"{protocol}://{masked_auth}@{host_part}"
        
        return connection_string
    
    def cleanup(self):
        """Clean up resources and stop monitoring."""
        logger.info("🧹 Cleaning up service health monitor...")
        self.stop_monitoring()
        self._health_callbacks.clear()
        self._health_results.clear()
        self._feature_flags.clear()
        logger.info("✅ Service health monitor cleanup completed")
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore errors during cleanup


def get_service_health_monitor(app=None) -> ServiceHealthMonitor:
    """
    Get or create service health monitor instance.
    
    Args:
        app: Optional Flask app instance
        
    Returns:
        ServiceHealthMonitor instance
    """
    if app is None:
        app = current_app
    
    if 'service_health_monitor' not in app.extensions:
        monitor = ServiceHealthMonitor(app)
    else:
        monitor = app.extensions['service_health_monitor']
    
    return monitor