"""
Enhanced Service Health Monitoring System

This module provides comprehensive service health monitoring with automatic recovery,
degradation detection, and notification capabilities.
"""

import time
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import redis
from flask import current_app
from sqlalchemy import text
from app import db
from app.services.health_service import HealthService, HealthCheckResult
from app.services.alerting_service import alerting_service, Alert, AlertSeverity, AlertStatus
from app.utils.application_context_manager import get_context_manager, with_app_context, safe_context
import structlog

logger = structlog.get_logger()


class ServiceStatus(Enum):
    """Service status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


class ServiceType(Enum):
    """Types of services being monitored."""
    DATABASE = "database"
    REDIS = "redis"
    EXTERNAL_API = "external_api"
    STORAGE = "storage"
    MESSAGING = "messaging"
    MONITORING = "monitoring"


@dataclass
class ServiceHealthMetrics:
    """Health metrics for a service."""
    service_name: str
    service_type: ServiceType
    status: ServiceStatus
    response_time_ms: Optional[float]
    error_rate: float
    uptime_percentage: float
    last_check: datetime
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_checks: int = 0
    total_failures: int = 0
    error_message: Optional[str] = None
    recovery_attempts: int = 0
    last_recovery_attempt: Optional[datetime] = None
    
    def update_success(self, response_time_ms: float):
        """Update metrics for successful check."""
        self.status = ServiceStatus.HEALTHY if self.consecutive_failures == 0 else ServiceStatus.RECOVERING
        self.response_time_ms = response_time_ms
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.total_checks += 1
        self.last_check = datetime.utcnow()
        self.error_message = None
        
        # Update uptime percentage
        self.uptime_percentage = ((self.total_checks - self.total_failures) / self.total_checks) * 100
    
    def update_failure(self, error_message: str):
        """Update metrics for failed check."""
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.total_checks += 1
        self.total_failures += 1
        self.error_message = error_message
        self.last_check = datetime.utcnow()
        
        # Determine status based on consecutive failures
        if self.consecutive_failures >= 3:
            self.status = ServiceStatus.UNHEALTHY
        elif self.consecutive_failures >= 1:
            self.status = ServiceStatus.DEGRADED
        
        # Update error rate and uptime
        self.error_rate = (self.total_failures / self.total_checks) * 100
        self.uptime_percentage = ((self.total_checks - self.total_failures) / self.total_checks) * 100


@dataclass
class RecoveryAction:
    """Recovery action definition."""
    name: str
    description: str
    action: Callable[[], bool]
    max_attempts: int = 3
    cooldown_minutes: int = 5
    severity_threshold: ServiceStatus = ServiceStatus.DEGRADED


class ServiceHealthMonitor:
    """Enhanced service health monitoring with automatic recovery."""
    
    def __init__(self):
        self.services: Dict[str, ServiceHealthMetrics] = {}
        self.recovery_actions: Dict[str, List[RecoveryAction]] = defaultdict(list)
        self.health_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.monitoring_enabled = True
        self.check_interval = 30  # seconds
        self.notification_cooldown = 300  # 5 minutes
        self.last_notifications: Dict[str, datetime] = {}
        self._monitoring_thread = None
        self._stop_monitoring = threading.Event()
    
    def register_service(
        self,
        service_name: str,
        service_type: ServiceType,
        health_check: Callable[[], HealthCheckResult]
    ):
        """Register a service for monitoring."""
        self.services[service_name] = ServiceHealthMetrics(
            service_name=service_name,
            service_type=service_type,
            status=ServiceStatus.UNKNOWN,
            response_time_ms=None,
            error_rate=0.0,
            uptime_percentage=100.0,
            last_check=datetime.utcnow(),
            total_checks=0,
            total_failures=0
        )
        
        # Store health check function
        setattr(self, f"_check_{service_name}", health_check)
        
        logger.info("Service registered for monitoring", 
                   service=service_name, type=service_type.value)
    
    def add_recovery_action(self, service_name: str, action: RecoveryAction):
        """Add recovery action for a service."""
        self.recovery_actions[service_name].append(action)
        logger.info("Recovery action added", 
                   service=service_name, action=action.name)
    
    @safe_context
    def check_service_health(self, service_name: str) -> ServiceHealthMetrics:
        """Check health of a specific service with proper Flask context."""
        if service_name not in self.services:
            raise ValueError(f"Service {service_name} not registered")
        
        metrics = self.services[service_name]
        health_check = getattr(self, f"_check_{service_name}", None)
        
        if not health_check:
            logger.error("Health check function not found", service=service_name)
            metrics.update_failure("Health check function not available")
            return metrics
        
        try:
            # Ensure health check runs with proper context
            context_manager = get_context_manager()
            if context_manager:
                result = context_manager.run_with_context(health_check)
            else:
                # Fallback if context manager not available
                result = health_check()
            
            if result.status == "healthy":
                metrics.update_success(result.response_time_ms or 0)
                logger.debug("Service health check passed", service=service_name)
            else:
                metrics.update_failure(result.error or "Unknown error")
                logger.warning("Service health check failed", 
                             service=service_name, error=result.error)
                
                # Attempt recovery if needed
                self._attempt_recovery(service_name, metrics)
        
        except Exception as e:
            error_msg = f"Health check exception: {str(e)}"
            metrics.update_failure(error_msg)
            logger.error("Service health check exception", 
                        service=service_name, error=str(e))
        
        # Store in history
        self.health_history[service_name].append({
            'timestamp': metrics.last_check.isoformat(),
            'status': metrics.status.value,
            'response_time_ms': metrics.response_time_ms,
            'error_message': metrics.error_message
        })
        
        # Send notifications if needed
        self._check_notification_needed(service_name, metrics)
        
        return metrics
    
    async def _attempt_recovery(self, service_name: str, metrics: ServiceHealthMetrics):
        """Attempt automatic recovery for a service."""
        # Import here to avoid circular imports
        from app.services.service_recovery import service_recovery_manager
        
        # Check if status warrants recovery
        if metrics.status not in [ServiceStatus.DEGRADED, ServiceStatus.UNHEALTHY]:
            return
        
        # Use the advanced recovery manager
        try:
            recovery_success = await service_recovery_manager.attempt_recovery(
                service_name, metrics.status
            )
            
            if recovery_success:
                metrics.recovery_attempts += 1
                metrics.last_recovery_attempt = datetime.utcnow()
                logger.info("Advanced recovery succeeded", service=service_name)
            else:
                logger.warning("Advanced recovery failed", service=service_name)
                
        except Exception as e:
            logger.error("Advanced recovery exception", 
                        service=service_name, error=str(e))
    
    async def _check_notification_needed(self, service_name: str, metrics: ServiceHealthMetrics):
        """Check if notification should be sent for service status change."""
        # Check cooldown period
        last_notification = self.last_notifications.get(service_name)
        if (last_notification and 
            datetime.utcnow() - last_notification < timedelta(seconds=self.notification_cooldown)):
            return
        
        # Send notification for status changes
        if metrics.status in [ServiceStatus.DEGRADED, ServiceStatus.UNHEALTHY]:
            await self._send_degradation_notification(service_name, metrics)
            self.last_notifications[service_name] = datetime.utcnow()
        elif metrics.status == ServiceStatus.HEALTHY and metrics.consecutive_successes == 1:
            # Service just recovered
            await self._send_recovery_notification(service_name, "automatic")
            self.last_notifications[service_name] = datetime.utcnow()
    
    async def _send_degradation_notification(self, service_name: str, metrics: ServiceHealthMetrics):
        """Send service degradation notification."""
        severity = AlertSeverity.HIGH if metrics.status == ServiceStatus.UNHEALTHY else AlertSeverity.MEDIUM
        
        alert = Alert(
            id=f"service_degradation_{service_name}_{int(time.time())}",
            name=f"Service Degradation: {service_name}",
            severity=severity,
            status=AlertStatus.ACTIVE,
            message=f"Service {service_name} is {metrics.status.value}",
            description=f"Service {service_name} has been {metrics.status.value} for {metrics.consecutive_failures} consecutive checks. Error: {metrics.error_message}",
            source="service_health_monitor",
            labels={
                "service": service_name,
                "service_type": metrics.service_type.value,
                "status": metrics.status.value
            },
            annotations={
                "error_rate": str(metrics.error_rate),
                "uptime_percentage": str(metrics.uptime_percentage),
                "consecutive_failures": str(metrics.consecutive_failures),
                "last_error": metrics.error_message or "Unknown"
            },
            starts_at=datetime.utcnow()
        )
        
        await alerting_service.fire_alert(alert)
        logger.info("Service degradation notification sent", 
                   service=service_name, status=metrics.status.value)
    
    async def _send_recovery_notification(self, service_name: str, recovery_method: str):
        """Send service recovery notification."""
        alert = Alert(
            id=f"service_recovery_{service_name}_{int(time.time())}",
            name=f"Service Recovery: {service_name}",
            severity=AlertSeverity.LOW,
            status=AlertStatus.RESOLVED,
            message=f"Service {service_name} has recovered",
            description=f"Service {service_name} is now healthy after {recovery_method} recovery",
            source="service_health_monitor",
            labels={
                "service": service_name,
                "recovery_method": recovery_method
            },
            annotations={},
            starts_at=datetime.utcnow(),
            ends_at=datetime.utcnow()
        )
        
        await alerting_service.fire_alert(alert)
        logger.info("Service recovery notification sent", 
                   service=service_name, method=recovery_method)
    
    def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Get current status of a service."""
        if service_name not in self.services:
            return {"error": f"Service {service_name} not found"}
        
        metrics = self.services[service_name]
        return {
            "service_name": metrics.service_name,
            "service_type": metrics.service_type.value,
            "status": metrics.status.value,
            "response_time_ms": metrics.response_time_ms,
            "error_rate": metrics.error_rate,
            "uptime_percentage": metrics.uptime_percentage,
            "last_check": metrics.last_check.isoformat(),
            "consecutive_failures": metrics.consecutive_failures,
            "consecutive_successes": metrics.consecutive_successes,
            "total_checks": metrics.total_checks,
            "total_failures": metrics.total_failures,
            "error_message": metrics.error_message,
            "recovery_attempts": metrics.recovery_attempts,
            "last_recovery_attempt": metrics.last_recovery_attempt.isoformat() if metrics.last_recovery_attempt else None
        }
    
    def get_all_services_status(self) -> Dict[str, Any]:
        """Get status of all monitored services."""
        services_status = {}
        overall_status = ServiceStatus.HEALTHY
        
        for service_name in self.services:
            service_status = self.get_service_status(service_name)
            services_status[service_name] = service_status
            
            # Determine overall status
            service_status_enum = ServiceStatus(service_status["status"])
            if service_status_enum == ServiceStatus.UNHEALTHY:
                overall_status = ServiceStatus.UNHEALTHY
            elif service_status_enum == ServiceStatus.DEGRADED and overall_status != ServiceStatus.UNHEALTHY:
                overall_status = ServiceStatus.DEGRADED
        
        return {
            "overall_status": overall_status.value,
            "services": services_status,
            "total_services": len(self.services),
            "healthy_services": sum(1 for s in services_status.values() if s["status"] == "healthy"),
            "degraded_services": sum(1 for s in services_status.values() if s["status"] == "degraded"),
            "unhealthy_services": sum(1 for s in services_status.values() if s["status"] == "unhealthy"),
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def get_service_history(self, service_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get health history for a service."""
        if service_name not in self.health_history:
            return []
        
        return list(self.health_history[service_name])[-limit:]
    
    def start_monitoring(self):
        """Start the health monitoring thread."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            logger.warning("Health monitoring already running")
            return
        
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        
        logger.info("Service health monitoring started", interval=self.check_interval)
    
    def stop_monitoring(self):
        """Stop the health monitoring thread."""
        self._stop_monitoring.set()
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=10)
        
        logger.info("Service health monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop with proper Flask context."""
        context_manager = get_context_manager()
        
        while not self._stop_monitoring.is_set():
            try:
                # Use context manager for the entire monitoring loop
                if context_manager:
                    with context_manager.create_background_context():
                        # Check all registered services
                        for service_name in self.services:
                            if self._stop_monitoring.is_set():
                                break
                            
                            self.check_service_health(service_name)
                else:
                    # Fallback without context manager
                    logger.warning("Context manager not available for health monitoring")
                    for service_name in self.services:
                        if self._stop_monitoring.is_set():
                            break
                        
                        self.check_service_health(service_name)
                
                # Wait for next check interval
                self._stop_monitoring.wait(self.check_interval)
                
            except Exception as e:
                logger.error("Error in health monitoring loop", error=str(e))
                self._stop_monitoring.wait(self.check_interval)


# Global service health monitor instance
service_health_monitor = ServiceHealthMonitor()


def init_service_health_monitoring(app):
    """Initialize service health monitoring with Flask app."""
    try:
        # Register core services for monitoring
        service_health_monitor.register_service(
            "database",
            ServiceType.DATABASE,
            HealthService.check_database
        )
        
        service_health_monitor.register_service(
            "redis",
            ServiceType.REDIS,
            HealthService.check_redis
        )
        
        # Add recovery actions
        setup_recovery_actions()
        
        # Start monitoring if enabled
        if app.config.get('MONITORING_ENABLED', True):
            service_health_monitor.start_monitoring()
        
        logger.info("Service health monitoring initialized")
        return service_health_monitor
        
    except Exception as e:
        logger.error("Failed to initialize service health monitoring", error=str(e))
        return None


def setup_recovery_actions():
    """Set up default recovery actions for services."""
    
    # Database recovery actions
    @with_app_context
    def restart_database_connection():
        """Attempt to restart database connection pool with proper context."""
        try:
            db.engine.dispose()
            # Test new connection
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error("Database connection restart failed", error=str(e))
            return False
    
    db_recovery = RecoveryAction(
        name="restart_db_connection",
        description="Restart database connection pool",
        action=restart_database_connection,
        max_attempts=3,
        cooldown_minutes=2,
        severity_threshold=ServiceStatus.DEGRADED
    )
    service_health_monitor.add_recovery_action("database", db_recovery)
    
    # Redis recovery actions
    @with_app_context
    def restart_redis_connection():
        """Attempt to restart Redis connection with proper context."""
        try:
            # This would need to be implemented based on how Redis is used in the app
            # For now, just test connection
            redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
            redis_client = redis.from_url(redis_url, socket_timeout=5)
            redis_client.ping()
            return True
        except Exception as e:
            logger.error("Redis connection restart failed", error=str(e))
            return False
    
    redis_recovery = RecoveryAction(
        name="restart_redis_connection",
        description="Restart Redis connection",
        action=restart_redis_connection,
        max_attempts=2,
        cooldown_minutes=1,
        severity_threshold=ServiceStatus.DEGRADED
    )
    service_health_monitor.add_recovery_action("redis", redis_recovery)
    
    logger.info("Default recovery actions configured")