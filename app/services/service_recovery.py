"""
Automatic Service Recovery System

This module provides intelligent service recovery mechanisms with escalation,
circuit breaker patterns, and recovery strategy management.
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import redis
from flask import current_app
from sqlalchemy import text
from app import db
from app.services.service_health_monitor import ServiceStatus, service_health_monitor
from app.services.alerting_service import alerting_service, Alert, AlertSeverity, AlertStatus
import structlog

logger = structlog.get_logger()


class RecoveryStrategy(Enum):
    """Recovery strategy types."""
    RESTART_CONNECTION = "restart_connection"
    CLEAR_CACHE = "clear_cache"
    RESTART_SERVICE = "restart_service"
    FAILOVER = "failover"
    CIRCUIT_BREAKER = "circuit_breaker"
    GRACEFUL_DEGRADATION = "graceful_degradation"


class RecoveryResult(Enum):
    """Recovery attempt results."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt."""
    timestamp: datetime
    service_name: str
    strategy: RecoveryStrategy
    result: RecoveryResult
    duration_ms: float
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for a service."""
    service_name: str
    state: str = "closed"  # closed, open, half_open
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    half_open_max_calls: int = 3
    half_open_calls: int = 0


class ServiceRecoveryManager:
    """Manages automatic service recovery with intelligent strategies."""
    
    def __init__(self):
        self.recovery_strategies: Dict[str, List[Callable]] = defaultdict(list)
        self.recovery_history: deque = deque(maxlen=1000)
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self.recovery_in_progress: Dict[str, bool] = defaultdict(bool)
        self.escalation_levels: Dict[str, int] = defaultdict(int)
        self.max_escalation_level = 3
        self.recovery_cooldown = 300  # 5 minutes between recovery attempts
        self.last_recovery_attempts: Dict[str, datetime] = {}
    
    def register_recovery_strategy(
        self,
        service_name: str,
        strategy: RecoveryStrategy,
        action: Callable[[], Tuple[bool, str]],
        priority: int = 1
    ):
        """Register a recovery strategy for a service."""
        strategy_info = {
            'strategy': strategy,
            'action': action,
            'priority': priority,
            'success_count': 0,
            'failure_count': 0,
            'last_used': None
        }
        
        self.recovery_strategies[service_name].append(strategy_info)
        
        # Sort by priority (lower number = higher priority)
        self.recovery_strategies[service_name].sort(key=lambda x: x['priority'])
        
        logger.info("Recovery strategy registered", 
                   service=service_name, strategy=strategy.value, priority=priority)
    
    def init_circuit_breaker(self, service_name: str, **kwargs):
        """Initialize circuit breaker for a service."""
        self.circuit_breakers[service_name] = CircuitBreakerState(
            service_name=service_name,
            **kwargs
        )
        logger.info("Circuit breaker initialized", service=service_name)
    
    async def attempt_recovery(self, service_name: str, current_status: ServiceStatus) -> bool:
        """Attempt recovery for a failed service."""
        # Check if recovery is already in progress
        if self.recovery_in_progress.get(service_name, False):
            logger.info("Recovery already in progress", service=service_name)
            return False
        
        # Check cooldown period
        last_attempt = self.last_recovery_attempts.get(service_name)
        if (last_attempt and 
            datetime.utcnow() - last_attempt < timedelta(seconds=self.recovery_cooldown)):
            logger.info("Recovery cooldown active", service=service_name)
            return False
        
        # Check circuit breaker
        if not self._can_attempt_recovery(service_name):
            logger.info("Circuit breaker prevents recovery", service=service_name)
            return False
        
        self.recovery_in_progress[service_name] = True
        self.last_recovery_attempts[service_name] = datetime.utcnow()
        
        try:
            logger.info("Starting recovery attempt", 
                       service=service_name, status=current_status.value)
            
            # Get recovery strategies for this service
            strategies = self.recovery_strategies.get(service_name, [])
            if not strategies:
                logger.warning("No recovery strategies available", service=service_name)
                return False
            
            # Determine escalation level
            escalation_level = self.escalation_levels[service_name]
            
            # Try recovery strategies based on escalation level
            recovery_success = False
            for i, strategy_info in enumerate(strategies):
                if i > escalation_level:
                    break
                
                success = await self._execute_recovery_strategy(
                    service_name, strategy_info, current_status
                )
                
                if success:
                    recovery_success = True
                    # Reset escalation level on success
                    self.escalation_levels[service_name] = 0
                    self._record_circuit_breaker_success(service_name)
                    break
            
            if not recovery_success:
                # Escalate to next level
                self.escalation_levels[service_name] = min(
                    escalation_level + 1, 
                    self.max_escalation_level
                )
                self._record_circuit_breaker_failure(service_name)
                
                # Send escalation notification
                await self._send_escalation_notification(service_name, escalation_level + 1)
            
            return recovery_success
            
        except Exception as e:
            logger.error("Recovery attempt failed with exception", 
                        service=service_name, error=str(e))
            self._record_circuit_breaker_failure(service_name)
            return False
        
        finally:
            self.recovery_in_progress[service_name] = False
    
    async def _execute_recovery_strategy(
        self,
        service_name: str,
        strategy_info: Dict[str, Any],
        current_status: ServiceStatus
    ) -> bool:
        """Execute a specific recovery strategy."""
        strategy = strategy_info['strategy']
        action = strategy_info['action']
        
        start_time = time.time()
        
        try:
            logger.info("Executing recovery strategy", 
                       service=service_name, strategy=strategy.value)
            
            # Execute the recovery action
            success, message = action()
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Record the attempt
            attempt = RecoveryAttempt(
                timestamp=datetime.utcnow(),
                service_name=service_name,
                strategy=strategy,
                result=RecoveryResult.SUCCESS if success else RecoveryResult.FAILED,
                duration_ms=duration_ms,
                error_message=None if success else message,
                details={
                    'escalation_level': self.escalation_levels[service_name],
                    'previous_status': current_status.value
                }
            )
            
            self.recovery_history.append(attempt)
            
            # Update strategy statistics
            if success:
                strategy_info['success_count'] += 1
                logger.info("Recovery strategy succeeded", 
                           service=service_name, strategy=strategy.value, duration_ms=duration_ms)
            else:
                strategy_info['failure_count'] += 1
                logger.warning("Recovery strategy failed", 
                              service=service_name, strategy=strategy.value, error=message)
            
            strategy_info['last_used'] = datetime.utcnow()
            
            # Send recovery notification
            if success:
                await self._send_recovery_success_notification(service_name, strategy.value)
            
            return success
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_message = str(e)
            
            # Record the failed attempt
            attempt = RecoveryAttempt(
                timestamp=datetime.utcnow(),
                service_name=service_name,
                strategy=strategy,
                result=RecoveryResult.FAILED,
                duration_ms=duration_ms,
                error_message=error_message,
                details={'exception': True}
            )
            
            self.recovery_history.append(attempt)
            strategy_info['failure_count'] += 1
            strategy_info['last_used'] = datetime.utcnow()
            
            logger.error("Recovery strategy exception", 
                        service=service_name, strategy=strategy.value, error=error_message)
            
            return False
    
    def _can_attempt_recovery(self, service_name: str) -> bool:
        """Check if recovery can be attempted based on circuit breaker state."""
        if service_name not in self.circuit_breakers:
            return True
        
        breaker = self.circuit_breakers[service_name]
        now = datetime.utcnow()
        
        if breaker.state == "closed":
            return True
        elif breaker.state == "open":
            # Check if recovery timeout has passed
            if (breaker.last_failure_time and 
                now - breaker.last_failure_time >= timedelta(seconds=breaker.recovery_timeout)):
                breaker.state = "half_open"
                breaker.half_open_calls = 0
                logger.info("Circuit breaker transitioning to half-open", service=service_name)
                return True
            return False
        elif breaker.state == "half_open":
            return breaker.half_open_calls < breaker.half_open_max_calls
        
        return False
    
    def _record_circuit_breaker_success(self, service_name: str):
        """Record successful operation for circuit breaker."""
        if service_name not in self.circuit_breakers:
            return
        
        breaker = self.circuit_breakers[service_name]
        breaker.last_success_time = datetime.utcnow()
        
        if breaker.state == "half_open":
            breaker.half_open_calls += 1
            if breaker.half_open_calls >= breaker.half_open_max_calls:
                breaker.state = "closed"
                breaker.failure_count = 0
                logger.info("Circuit breaker closed after successful recovery", service=service_name)
        elif breaker.state == "closed":
            breaker.failure_count = 0
    
    def _record_circuit_breaker_failure(self, service_name: str):
        """Record failed operation for circuit breaker."""
        if service_name not in self.circuit_breakers:
            return
        
        breaker = self.circuit_breakers[service_name]
        breaker.failure_count += 1
        breaker.last_failure_time = datetime.utcnow()
        
        if breaker.state == "closed" and breaker.failure_count >= breaker.failure_threshold:
            breaker.state = "open"
            logger.warning("Circuit breaker opened due to failures", 
                          service=service_name, failures=breaker.failure_count)
        elif breaker.state == "half_open":
            breaker.state = "open"
            logger.warning("Circuit breaker reopened after failed recovery", service=service_name)
    
    async def _send_recovery_success_notification(self, service_name: str, strategy: str):
        """Send notification for successful recovery."""
        alert = Alert(
            id=f"recovery_success_{service_name}_{int(time.time())}",
            name=f"Service Recovery Success: {service_name}",
            severity=AlertSeverity.LOW,
            status=AlertStatus.RESOLVED,
            message=f"Service {service_name} recovered successfully",
            description=f"Service {service_name} was automatically recovered using {strategy} strategy",
            source="service_recovery_manager",
            labels={
                "service": service_name,
                "recovery_strategy": strategy,
                "event_type": "recovery_success"
            },
            annotations={
                "escalation_level": str(self.escalation_levels[service_name])
            },
            starts_at=datetime.utcnow(),
            ends_at=datetime.utcnow()
        )
        
        await alerting_service.fire_alert(alert)
    
    async def _send_escalation_notification(self, service_name: str, escalation_level: int):
        """Send notification for recovery escalation."""
        severity = AlertSeverity.HIGH if escalation_level >= 3 else AlertSeverity.MEDIUM
        
        alert = Alert(
            id=f"recovery_escalation_{service_name}_{int(time.time())}",
            name=f"Service Recovery Escalation: {service_name}",
            severity=severity,
            status=AlertStatus.ACTIVE,
            message=f"Service {service_name} recovery escalated to level {escalation_level}",
            description=f"Automatic recovery for {service_name} has escalated to level {escalation_level}. Manual intervention may be required.",
            source="service_recovery_manager",
            labels={
                "service": service_name,
                "escalation_level": str(escalation_level),
                "event_type": "recovery_escalation"
            },
            annotations={
                "max_escalation_level": str(self.max_escalation_level),
                "requires_manual_intervention": str(escalation_level >= self.max_escalation_level)
            },
            starts_at=datetime.utcnow()
        )
        
        await alerting_service.fire_alert(alert)
    
    def get_recovery_status(self, service_name: str) -> Dict[str, Any]:
        """Get recovery status for a service."""
        strategies = self.recovery_strategies.get(service_name, [])
        breaker = self.circuit_breakers.get(service_name)
        
        # Get recent recovery attempts
        recent_attempts = [
            {
                'timestamp': attempt.timestamp.isoformat(),
                'strategy': attempt.strategy.value,
                'result': attempt.result.value,
                'duration_ms': attempt.duration_ms,
                'error_message': attempt.error_message
            }
            for attempt in self.recovery_history
            if attempt.service_name == service_name
        ][-10:]  # Last 10 attempts
        
        return {
            "service_name": service_name,
            "recovery_in_progress": self.recovery_in_progress.get(service_name, False),
            "escalation_level": self.escalation_levels[service_name],
            "max_escalation_level": self.max_escalation_level,
            "last_recovery_attempt": self.last_recovery_attempts.get(service_name).isoformat() if service_name in self.last_recovery_attempts else None,
            "available_strategies": [
                {
                    'strategy': s['strategy'].value,
                    'priority': s['priority'],
                    'success_count': s['success_count'],
                    'failure_count': s['failure_count'],
                    'last_used': s['last_used'].isoformat() if s['last_used'] else None
                }
                for s in strategies
            ],
            "circuit_breaker": {
                "state": breaker.state if breaker else "disabled",
                "failure_count": breaker.failure_count if breaker else 0,
                "failure_threshold": breaker.failure_threshold if breaker else 0,
                "last_failure": breaker.last_failure_time.isoformat() if breaker and breaker.last_failure_time else None,
                "last_success": breaker.last_success_time.isoformat() if breaker and breaker.last_success_time else None
            } if breaker else None,
            "recent_attempts": recent_attempts,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_all_recovery_status(self) -> Dict[str, Any]:
        """Get recovery status for all services."""
        return {
            service_name: self.get_recovery_status(service_name)
            for service_name in self.recovery_strategies.keys()
        }


# Global service recovery manager instance
service_recovery_manager = ServiceRecoveryManager()


def init_service_recovery(app):
    """Initialize service recovery system with Flask app."""
    try:
        # Set up recovery strategies for core services
        setup_database_recovery_strategies()
        setup_redis_recovery_strategies()
        
        # Initialize circuit breakers
        service_recovery_manager.init_circuit_breaker("database", failure_threshold=3, recovery_timeout=60)
        service_recovery_manager.init_circuit_breaker("redis", failure_threshold=5, recovery_timeout=30)
        
        logger.info("Service recovery system initialized")
        return service_recovery_manager
        
    except Exception as e:
        logger.error("Failed to initialize service recovery system", error=str(e))
        return None


def setup_database_recovery_strategies():
    """Set up recovery strategies for database service."""
    
    def restart_db_connection() -> Tuple[bool, str]:
        """Restart database connection pool."""
        try:
            logger.info("Attempting database connection restart")
            db.engine.dispose()
            
            # Test new connection
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            return True, "Database connection pool restarted successfully"
        except Exception as e:
            return False, f"Database connection restart failed: {str(e)}"
    
    def clear_db_cache() -> Tuple[bool, str]:
        """Clear database-related caches."""
        try:
            logger.info("Attempting database cache clear")
            # Clear SQLAlchemy session
            db.session.remove()
            
            # Clear any application-level caches if they exist
            if hasattr(current_app, 'cache'):
                current_app.cache.clear()
            
            return True, "Database caches cleared successfully"
        except Exception as e:
            return False, f"Database cache clear failed: {str(e)}"
    
    # Register strategies in order of priority
    service_recovery_manager.register_recovery_strategy(
        "database", RecoveryStrategy.CLEAR_CACHE, clear_db_cache, priority=1
    )
    service_recovery_manager.register_recovery_strategy(
        "database", RecoveryStrategy.RESTART_CONNECTION, restart_db_connection, priority=2
    )


def setup_redis_recovery_strategies():
    """Set up recovery strategies for Redis service."""
    
    def restart_redis_connection() -> Tuple[bool, str]:
        """Restart Redis connection."""
        try:
            logger.info("Attempting Redis connection restart")
            redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
            redis_client = redis.from_url(redis_url, socket_timeout=5)
            redis_client.ping()
            
            return True, "Redis connection restarted successfully"
        except Exception as e:
            return False, f"Redis connection restart failed: {str(e)}"
    
    def enable_graceful_degradation() -> Tuple[bool, str]:
        """Enable graceful degradation for Redis-dependent features."""
        try:
            logger.info("Enabling graceful degradation for Redis")
            
            # Switch to simple cache
            current_app.config['CACHE_TYPE'] = 'simple'
            
            # Disable Celery if it depends on Redis
            current_app.config['CELERY_BROKER_URL'] = None
            
            return True, "Graceful degradation enabled for Redis-dependent features"
        except Exception as e:
            return False, f"Graceful degradation setup failed: {str(e)}"
    
    # Register strategies
    service_recovery_manager.register_recovery_strategy(
        "redis", RecoveryStrategy.RESTART_CONNECTION, restart_redis_connection, priority=1
    )
    service_recovery_manager.register_recovery_strategy(
        "redis", RecoveryStrategy.GRACEFUL_DEGRADATION, enable_graceful_degradation, priority=2
    )