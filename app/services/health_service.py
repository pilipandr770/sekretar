"""Health check service for system monitoring."""

import time
from dataclasses import dataclass
from typing import Dict, Optional
import redis
from flask import current_app
from sqlalchemy import text
from app import db


@dataclass
class HealthCheckResult:
    """Result of a health check for a specific service."""
    status: str  # "healthy" | "unhealthy"
    response_time_ms: Optional[int]
    error: Optional[str] = None


@dataclass
class OverallHealthResult:
    """Overall health status aggregating all service checks."""
    status: str  # "healthy" | "unhealthy"
    checks: Dict[str, HealthCheckResult]
    timestamp: str


class HealthService:
    """Service for performing health checks on system dependencies."""
    
    @staticmethod
    def check_database() -> HealthCheckResult:
        """Check database connectivity and response time."""
        start_time = time.time()
        
        try:
            # Get timeout from config, default to 5 seconds
            timeout = current_app.config.get('HEALTH_CHECK_TIMEOUT', 5)
            
            # Simple query to test database connectivity with timeout
            with db.engine.connect() as connection:
                # Set statement timeout for this connection
                connection.execute(text(f"SET statement_timeout = '{timeout * 1000}ms'"))
                connection.execute(text("SELECT 1"))
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            return HealthCheckResult(
                status="healthy",
                response_time_ms=response_time_ms
            )
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_message = str(e)
            
            # Categorize different types of database errors
            if "timeout" in error_message.lower() or "timed out" in error_message.lower():
                error_message = f"Database connection timeout after {timeout}s"
            elif "connection" in error_message.lower():
                error_message = "Database connection failed"
            elif "authentication" in error_message.lower():
                error_message = "Database authentication failed"
            else:
                error_message = f"Database error: {error_message}"
            
            current_app.logger.warning(f"Database health check failed: {error_message}")
            
            return HealthCheckResult(
                status="unhealthy",
                response_time_ms=response_time_ms if response_time_ms < timeout * 1000 else None,
                error=error_message
            )
    
    @staticmethod
    def check_redis() -> HealthCheckResult:
        """Check Redis connectivity and response time."""
        start_time = time.time()
        
        try:
            # Get timeout from config, default to 5 seconds
            timeout = current_app.config.get('HEALTH_CHECK_TIMEOUT', 5)
            
            # Create Redis client with timeout
            redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
            redis_client = redis.from_url(
                redis_url,
                socket_timeout=timeout,
                socket_connect_timeout=timeout,
                health_check_interval=30,
                retry_on_timeout=False,
                retry_on_error=[]
            )
            
            # Test Redis connectivity with ping
            redis_client.ping()
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            return HealthCheckResult(
                status="healthy",
                response_time_ms=response_time_ms
            )
            
        except redis.TimeoutError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_message = f"Redis connection timeout after {timeout}s"
            current_app.logger.warning(f"Redis health check failed: {error_message}")
            
            return HealthCheckResult(
                status="unhealthy",
                response_time_ms=response_time_ms if response_time_ms < timeout * 1000 else None,
                error=error_message
            )
            
        except redis.ConnectionError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_message = "Redis connection failed"
            current_app.logger.warning(f"Redis health check failed: {error_message}")
            
            return HealthCheckResult(
                status="unhealthy",
                response_time_ms=response_time_ms if response_time_ms < timeout * 1000 else None,
                error=error_message
            )
            
        except redis.AuthenticationError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_message = "Redis authentication failed"
            current_app.logger.warning(f"Redis health check failed: {error_message}")
            
            return HealthCheckResult(
                status="unhealthy",
                response_time_ms=response_time_ms if response_time_ms < timeout * 1000 else None,
                error=error_message
            )
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_message = f"Redis error: {str(e)}"
            current_app.logger.warning(f"Redis health check failed: {error_message}")
            
            return HealthCheckResult(
                status="unhealthy",
                response_time_ms=response_time_ms if response_time_ms < timeout * 1000 else None,
                error=error_message
            )
    
    @staticmethod
    def check_rate_limiting() -> HealthCheckResult:
        """Check rate limiting system health."""
        start_time = time.time()
        
        try:
            # Check if rate limit manager is available
            rate_limit_manager = current_app.extensions.get('rate_limit_manager')
            if not rate_limit_manager:
                return HealthCheckResult(
                    status="unhealthy",
                    response_time_ms=None,
                    error="Rate limit manager not initialized"
                )
            
            # Test rate limiting Redis connection
            test_key = "health_check:rate_limit_test"
            result = rate_limit_manager.check_rate_limit(test_key, 100, 60, "health_check")
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if 'error' in result:
                return HealthCheckResult(
                    status="unhealthy",
                    response_time_ms=response_time_ms,
                    error=f"Rate limiting error: {result['error']}"
                )
            
            return HealthCheckResult(
                status="healthy",
                response_time_ms=response_time_ms
            )
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_message = f"Rate limiting health check failed: {str(e)}"
            current_app.logger.warning(error_message)
            
            return HealthCheckResult(
                status="unhealthy",
                response_time_ms=response_time_ms,
                error=error_message
            )
    
    @staticmethod
    def check_monitoring() -> HealthCheckResult:
        """Check monitoring system health."""
        start_time = time.time()
        
        try:
            # Check if monitoring service is available
            from app.services.monitoring_service import monitoring_service
            
            if not monitoring_service._initialized:
                return HealthCheckResult(
                    status="unhealthy",
                    response_time_ms=None,
                    error="Monitoring service not initialized"
                )
            
            # Test monitoring service functionality
            metrics = monitoring_service.get_metrics_summary()
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if 'error' in metrics:
                return HealthCheckResult(
                    status="unhealthy",
                    response_time_ms=response_time_ms,
                    error=f"Monitoring error: {metrics['error']}"
                )
            
            return HealthCheckResult(
                status="healthy",
                response_time_ms=response_time_ms
            )
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_message = f"Monitoring health check failed: {str(e)}"
            current_app.logger.warning(error_message)
            
            return HealthCheckResult(
                status="unhealthy",
                response_time_ms=response_time_ms,
                error=error_message
            )
    
    @staticmethod
    def get_overall_health() -> OverallHealthResult:
        """Get overall health status by checking all services."""
        from datetime import datetime
        
        checks = {}
        overall_status = "healthy"
        
        # Check database if enabled
        if current_app.config.get('HEALTH_CHECK_DATABASE_ENABLED', True):
            try:
                db_result = HealthService.check_database()
                checks['database'] = db_result
                
                # Database failure makes overall status unhealthy
                if db_result.status == "unhealthy":
                    overall_status = "unhealthy"
                    current_app.logger.error(f"Database health check failed: {db_result.error}")
                    
            except Exception as e:
                # Graceful degradation - if health check itself fails
                current_app.logger.error(f"Database health check service failed: {str(e)}")
                checks['database'] = HealthCheckResult(
                    status="unhealthy",
                    response_time_ms=None,
                    error="Health check service failed"
                )
                overall_status = "unhealthy"
        
        # Check Redis if enabled
        if current_app.config.get('HEALTH_CHECK_REDIS_ENABLED', True):
            try:
                redis_result = HealthService.check_redis()
                checks['redis'] = redis_result
                
                # Redis failure doesn't make overall status unhealthy
                # as per requirement 1.5 - Redis failure should still return 200
                # but indicate Redis as unhealthy
                if redis_result.status == "unhealthy":
                    current_app.logger.warning(f"Redis health check failed: {redis_result.error}")
                    
            except Exception as e:
                # Graceful degradation - if health check itself fails
                current_app.logger.warning(f"Redis health check service failed: {str(e)}")
                checks['redis'] = HealthCheckResult(
                    status="unhealthy",
                    response_time_ms=None,
                    error="Health check service failed"
                )
        
        # Check rate limiting if enabled
        try:
            rate_limit_result = HealthService.check_rate_limiting()
            checks['rate_limiting'] = rate_limit_result
            
            if rate_limit_result.status == "unhealthy":
                current_app.logger.warning(f"Rate limiting health check failed: {rate_limit_result.error}")
                
        except Exception as e:
            current_app.logger.warning(f"Rate limiting health check service failed: {str(e)}")
            checks['rate_limiting'] = HealthCheckResult(
                status="unhealthy",
                response_time_ms=None,
                error="Health check service failed"
            )
        
        # Check monitoring service if enabled
        try:
            monitoring_result = HealthService.check_monitoring()
            checks['monitoring'] = monitoring_result
            
            if monitoring_result.status == "unhealthy":
                current_app.logger.warning(f"Monitoring health check failed: {monitoring_result.error}")
                
        except Exception as e:
            current_app.logger.warning(f"Monitoring health check service failed: {str(e)}")
            checks['monitoring'] = HealthCheckResult(
                status="unhealthy",
                response_time_ms=None,
                error="Health check service failed"
            )
        
        # If no checks were performed, consider it unhealthy
        if not checks:
            current_app.logger.error("No health checks were performed - all checks disabled")
            overall_status = "unhealthy"
        
        return OverallHealthResult(
            status=overall_status,
            checks=checks,
            timestamp=datetime.utcnow().isoformat() + 'Z'
        )