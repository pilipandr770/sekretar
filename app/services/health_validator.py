"""
Health Validator Service

Provides comprehensive health checking for external services with fallback modes
and informative status messages.
"""

import time
import asyncio
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import redis
from flask import current_app
from sqlalchemy import text
from app import db
from app.utils.application_context_manager import with_app_context, safe_context
import structlog

logger = structlog.get_logger()


class ServiceStatus(Enum):
    """Service status levels."""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    FALLBACK = "fallback"
    UNKNOWN = "unknown"


class ServiceType(Enum):
    """Types of services being validated."""
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL_API = "external_api"
    MESSAGING = "messaging"
    STORAGE = "storage"
    AUTHENTICATION = "authentication"


@dataclass
class ServiceValidationResult:
    """Result of service validation."""
    service_name: str
    service_type: ServiceType
    status: ServiceStatus
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    fallback_available: bool = False
    fallback_message: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)
    last_checked: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SystemHealthReport:
    """Comprehensive system health report."""
    overall_status: ServiceStatus
    services: Dict[str, ServiceValidationResult]
    fallback_services: List[str]
    critical_issues: List[str]
    warnings: List[str]
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class HealthValidator:
    """
    Comprehensive health validator for external services with fallback modes.
    
    This validator checks the health of various external services and provides
    fallback options when services are unavailable.
    """
    
    def __init__(self):
        self.timeout = 10  # Default timeout for external service checks
        self.fallback_modes = {}
        self._setup_fallback_modes()
    
    def _setup_fallback_modes(self):
        """Setup fallback modes for various services."""
        self.fallback_modes = {
            'openai': {
                'fallback_available': True,
                'fallback_message': 'AI features disabled - using basic text processing',
                'recommendations': [
                    'Set OPENAI_API_KEY environment variable',
                    'Verify API key has sufficient credits',
                    'Check OpenAI service status'
                ]
            },
            'stripe': {
                'fallback_available': True,
                'fallback_message': 'Billing features disabled - manual payment processing required',
                'recommendations': [
                    'Set STRIPE_SECRET_KEY environment variable',
                    'Configure webhook endpoints',
                    'Verify Stripe account status'
                ]
            },
            'redis': {
                'fallback_available': True,
                'fallback_message': 'Using in-memory cache - reduced performance expected',
                'recommendations': [
                    'Set REDIS_URL environment variable',
                    'Ensure Redis server is running',
                    'Check Redis connection settings'
                ]
            },
            'google_oauth': {
                'fallback_available': True,
                'fallback_message': 'Google integration disabled - manual calendar sync required',
                'recommendations': [
                    'Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET',
                    'Configure OAuth redirect URIs',
                    'Enable Google Calendar API'
                ]
            },
            'telegram': {
                'fallback_available': True,
                'fallback_message': 'Telegram notifications disabled - using email fallback',
                'recommendations': [
                    'Set TELEGRAM_BOT_TOKEN environment variable',
                    'Configure webhook URL',
                    'Verify bot permissions'
                ]
            },
            'signal': {
                'fallback_available': True,
                'fallback_message': 'Signal messaging disabled - using alternative channels',
                'recommendations': [
                    'Install signal-cli',
                    'Set SIGNAL_PHONE_NUMBER environment variable',
                    'Register Signal account'
                ]
            },
            'smtp': {
                'fallback_available': False,
                'fallback_message': 'Email notifications unavailable - critical service failure',
                'recommendations': [
                    'Set SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD',
                    'Verify SMTP server connectivity',
                    'Check email authentication settings'
                ]
            },
            'database': {
                'fallback_available': True,
                'fallback_message': 'Using SQLite fallback - reduced performance and features',
                'recommendations': [
                    'Check DATABASE_URL configuration',
                    'Verify database server connectivity',
                    'Ensure database credentials are correct'
                ]
            }
        }
    
    @with_app_context
    async def validate_database(self) -> ServiceValidationResult:
        """Validate database connectivity and performance with proper Flask context."""
        start_time = time.time()
        service_name = "database"
        
        try:
            # Test basic connectivity
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            
            # Test performance with a more complex query
            with db.engine.connect() as connection:
                result = connection.execute(text("SELECT COUNT(*) FROM information_schema.tables"))
                result.fetchone()
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine status based on response time
            if response_time > 5000:  # 5 seconds
                status = ServiceStatus.DEGRADED
                recommendations = ["Database response time is slow - consider optimization"]
            elif response_time > 1000:  # 1 second
                status = ServiceStatus.DEGRADED
                recommendations = ["Database response time is elevated - monitor performance"]
            else:
                status = ServiceStatus.AVAILABLE
                recommendations = []
            
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.DATABASE,
                status=status,
                response_time_ms=response_time,
                fallback_available=True,
                fallback_message="SQLite fallback available if needed",
                recommendations=recommendations
            )
            
        except Exception as e:
            error_msg = str(e)
            fallback_info = self.fallback_modes.get('database', {})
            
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.DATABASE,
                status=ServiceStatus.UNAVAILABLE,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=error_msg,
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
    
    @with_app_context
    async def validate_redis(self) -> ServiceValidationResult:
        """Validate Redis connectivity and performance with proper Flask context."""
        start_time = time.time()
        service_name = "redis"
        
        redis_url = current_app.config.get('REDIS_URL')
        if not redis_url:
            fallback_info = self.fallback_modes.get('redis', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.CACHE,
                status=ServiceStatus.FALLBACK,
                response_time_ms=None,
                error_message="Redis URL not configured",
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
        
        try:
            redis_client = redis.from_url(
                redis_url,
                socket_timeout=self.timeout,
                socket_connect_timeout=self.timeout
            )
            
            # Test basic connectivity
            redis_client.ping()
            
            # Test performance
            test_key = f"health_check_{int(time.time())}"
            redis_client.set(test_key, "test_value", ex=60)
            redis_client.get(test_key)
            redis_client.delete(test_key)
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine status based on response time
            if response_time > 1000:  # 1 second
                status = ServiceStatus.DEGRADED
                recommendations = ["Redis response time is slow - check server performance"]
            else:
                status = ServiceStatus.AVAILABLE
                recommendations = []
            
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.CACHE,
                status=status,
                response_time_ms=response_time,
                fallback_available=True,
                fallback_message="In-memory cache fallback active",
                recommendations=recommendations
            )
            
        except Exception as e:
            error_msg = str(e)
            fallback_info = self.fallback_modes.get('redis', {})
            
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.CACHE,
                status=ServiceStatus.FALLBACK,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=error_msg,
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
    
    async def validate_openai(self) -> ServiceValidationResult:
        """Validate OpenAI API connectivity and quota."""
        start_time = time.time()
        service_name = "openai"
        
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            fallback_info = self.fallback_modes.get('openai', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.EXTERNAL_API,
                status=ServiceStatus.FALLBACK,
                response_time_ms=None,
                error_message="OpenAI API key not configured",
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
        
        try:
            # Test API connectivity with a minimal request
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # Use models endpoint for lightweight check
            response = requests.get(
                'https://api.openai.com/v1/models',
                headers=headers,
                timeout=self.timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return ServiceValidationResult(
                    service_name=service_name,
                    service_type=ServiceType.EXTERNAL_API,
                    status=ServiceStatus.AVAILABLE,
                    response_time_ms=response_time,
                    fallback_available=True,
                    fallback_message="Basic text processing available as fallback",
                    recommendations=[]
                )
            elif response.status_code == 401:
                error_msg = "Invalid API key"
            elif response.status_code == 429:
                error_msg = "Rate limit exceeded or quota exhausted"
            else:
                error_msg = f"API error: {response.status_code}"
            
            fallback_info = self.fallback_modes.get('openai', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.EXTERNAL_API,
                status=ServiceStatus.FALLBACK,
                response_time_ms=response_time,
                error_message=error_msg,
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
            
        except requests.exceptions.Timeout:
            fallback_info = self.fallback_modes.get('openai', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.EXTERNAL_API,
                status=ServiceStatus.DEGRADED,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message="API request timeout",
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
        except Exception as e:
            fallback_info = self.fallback_modes.get('openai', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.EXTERNAL_API,
                status=ServiceStatus.UNAVAILABLE,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
    
    async def validate_stripe(self) -> ServiceValidationResult:
        """Validate Stripe API connectivity."""
        start_time = time.time()
        service_name = "stripe"
        
        api_key = current_app.config.get('STRIPE_SECRET_KEY')
        if not api_key:
            fallback_info = self.fallback_modes.get('stripe', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.EXTERNAL_API,
                status=ServiceStatus.FALLBACK,
                response_time_ms=None,
                error_message="Stripe API key not configured",
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
        
        try:
            # Test API connectivity with account retrieval
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.get(
                'https://api.stripe.com/v1/account',
                headers=headers,
                timeout=self.timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return ServiceValidationResult(
                    service_name=service_name,
                    service_type=ServiceType.EXTERNAL_API,
                    status=ServiceStatus.AVAILABLE,
                    response_time_ms=response_time,
                    fallback_available=True,
                    fallback_message="Manual payment processing available",
                    recommendations=[]
                )
            else:
                error_msg = f"Stripe API error: {response.status_code}"
                fallback_info = self.fallback_modes.get('stripe', {})
                return ServiceValidationResult(
                    service_name=service_name,
                    service_type=ServiceType.EXTERNAL_API,
                    status=ServiceStatus.FALLBACK,
                    response_time_ms=response_time,
                    error_message=error_msg,
                    fallback_available=fallback_info.get('fallback_available', False),
                    fallback_message=fallback_info.get('fallback_message'),
                    recommendations=fallback_info.get('recommendations', [])
                )
                
        except Exception as e:
            fallback_info = self.fallback_modes.get('stripe', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.EXTERNAL_API,
                status=ServiceStatus.UNAVAILABLE,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
    
    async def validate_google_oauth(self) -> ServiceValidationResult:
        """Validate Google OAuth configuration."""
        start_time = time.time()
        service_name = "google_oauth"
        
        client_id = current_app.config.get('GOOGLE_CLIENT_ID')
        client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            fallback_info = self.fallback_modes.get('google_oauth', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.AUTHENTICATION,
                status=ServiceStatus.FALLBACK,
                response_time_ms=None,
                error_message="Google OAuth credentials not configured",
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
        
        try:
            # Test Google OAuth discovery endpoint
            response = requests.get(
                'https://accounts.google.com/.well-known/openid_configuration',
                timeout=self.timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return ServiceValidationResult(
                    service_name=service_name,
                    service_type=ServiceType.AUTHENTICATION,
                    status=ServiceStatus.AVAILABLE,
                    response_time_ms=response_time,
                    fallback_available=True,
                    fallback_message="Manual calendar sync available",
                    recommendations=[]
                )
            else:
                error_msg = f"Google OAuth discovery failed: {response.status_code}"
                fallback_info = self.fallback_modes.get('google_oauth', {})
                return ServiceValidationResult(
                    service_name=service_name,
                    service_type=ServiceType.AUTHENTICATION,
                    status=ServiceStatus.DEGRADED,
                    response_time_ms=response_time,
                    error_message=error_msg,
                    fallback_available=fallback_info.get('fallback_available', False),
                    fallback_message=fallback_info.get('fallback_message'),
                    recommendations=fallback_info.get('recommendations', [])
                )
                
        except Exception as e:
            fallback_info = self.fallback_modes.get('google_oauth', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.AUTHENTICATION,
                status=ServiceStatus.UNAVAILABLE,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
    
    async def validate_telegram(self) -> ServiceValidationResult:
        """Validate Telegram Bot API connectivity."""
        start_time = time.time()
        service_name = "telegram"
        
        bot_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            fallback_info = self.fallback_modes.get('telegram', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.MESSAGING,
                status=ServiceStatus.FALLBACK,
                response_time_ms=None,
                error_message="Telegram bot token not configured",
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
        
        try:
            # Test bot API with getMe endpoint
            response = requests.get(
                f'https://api.telegram.org/bot{bot_token}/getMe',
                timeout=self.timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return ServiceValidationResult(
                        service_name=service_name,
                        service_type=ServiceType.MESSAGING,
                        status=ServiceStatus.AVAILABLE,
                        response_time_ms=response_time,
                        fallback_available=True,
                        fallback_message="Email notifications available as fallback",
                        recommendations=[]
                    )
                else:
                    error_msg = f"Telegram API error: {data.get('description', 'Unknown error')}"
            else:
                error_msg = f"Telegram API HTTP error: {response.status_code}"
            
            fallback_info = self.fallback_modes.get('telegram', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.MESSAGING,
                status=ServiceStatus.FALLBACK,
                response_time_ms=response_time,
                error_message=error_msg,
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
            
        except Exception as e:
            fallback_info = self.fallback_modes.get('telegram', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.MESSAGING,
                status=ServiceStatus.UNAVAILABLE,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
    
    async def validate_smtp(self) -> ServiceValidationResult:
        """Validate SMTP email service."""
        start_time = time.time()
        service_name = "smtp"
        
        smtp_server = current_app.config.get('SMTP_SERVER')
        smtp_username = current_app.config.get('SMTP_USERNAME')
        smtp_password = current_app.config.get('SMTP_PASSWORD')
        
        if not all([smtp_server, smtp_username, smtp_password]):
            fallback_info = self.fallback_modes.get('smtp', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.MESSAGING,
                status=ServiceStatus.UNAVAILABLE,
                response_time_ms=None,
                error_message="SMTP configuration incomplete",
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            
            smtp_port = current_app.config.get('SMTP_PORT', 587)
            
            # Test SMTP connection
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=self.timeout)
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.quit()
            
            response_time = (time.time() - start_time) * 1000
            
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.MESSAGING,
                status=ServiceStatus.AVAILABLE,
                response_time_ms=response_time,
                fallback_available=False,
                fallback_message="No fallback available for email service",
                recommendations=[]
            )
            
        except Exception as e:
            fallback_info = self.fallback_modes.get('smtp', {})
            return ServiceValidationResult(
                service_name=service_name,
                service_type=ServiceType.MESSAGING,
                status=ServiceStatus.UNAVAILABLE,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                fallback_available=fallback_info.get('fallback_available', False),
                fallback_message=fallback_info.get('fallback_message'),
                recommendations=fallback_info.get('recommendations', [])
            )
    
    async def validate_all_services(self) -> SystemHealthReport:
        """Validate all configured services and generate comprehensive report."""
        logger.info("Starting comprehensive service validation")
        
        # Run all validations concurrently
        validation_tasks = [
            self.validate_database(),
            self.validate_redis(),
            self.validate_openai(),
            self.validate_stripe(),
            self.validate_google_oauth(),
            self.validate_telegram(),
            self.validate_smtp()
        ]
        
        results = await asyncio.gather(*validation_tasks, return_exceptions=True)
        
        services = {}
        fallback_services = []
        critical_issues = []
        warnings = []
        recommendations = []
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                logger.error("Service validation failed", error=str(result))
                continue
            
            services[result.service_name] = result
            
            # Collect fallback services
            if result.status == ServiceStatus.FALLBACK:
                fallback_services.append(result.service_name)
            
            # Collect critical issues
            if result.status == ServiceStatus.UNAVAILABLE and not result.fallback_available:
                critical_issues.append(f"{result.service_name}: {result.error_message}")
            
            # Collect warnings
            if result.status in [ServiceStatus.DEGRADED, ServiceStatus.FALLBACK]:
                warnings.append(f"{result.service_name}: {result.error_message or 'Service degraded'}")
            
            # Collect recommendations
            recommendations.extend(result.recommendations)
        
        # Determine overall status
        if critical_issues:
            overall_status = ServiceStatus.UNAVAILABLE
        elif any(s.status == ServiceStatus.DEGRADED for s in services.values()):
            overall_status = ServiceStatus.DEGRADED
        elif fallback_services:
            overall_status = ServiceStatus.FALLBACK
        else:
            overall_status = ServiceStatus.AVAILABLE
        
        # Add general recommendations
        if fallback_services:
            recommendations.append("Consider configuring unavailable services to enable full functionality")
        
        if critical_issues:
            recommendations.append("Address critical service failures immediately")
        
        report = SystemHealthReport(
            overall_status=overall_status,
            services=services,
            fallback_services=fallback_services,
            critical_issues=critical_issues,
            warnings=warnings,
            recommendations=list(set(recommendations))  # Remove duplicates
        )
        
        logger.info("Service validation completed", 
                   overall_status=overall_status.value,
                   total_services=len(services),
                   fallback_services=len(fallback_services),
                   critical_issues=len(critical_issues))
        
        return report
    
    def get_service_status_message(self, service_name: str, result: ServiceValidationResult) -> str:
        """Generate informative status message for a service."""
        if result.status == ServiceStatus.AVAILABLE:
            return f"✅ {service_name.title()} is available and responding normally"
        
        elif result.status == ServiceStatus.DEGRADED:
            return f"⚠️ {service_name.title()} is experiencing performance issues: {result.error_message}"
        
        elif result.status == ServiceStatus.FALLBACK:
            return f"🔄 {service_name.title()} is unavailable, using fallback mode: {result.fallback_message}"
        
        elif result.status == ServiceStatus.UNAVAILABLE:
            if result.fallback_available:
                return f"❌ {service_name.title()} is unavailable: {result.error_message}. Fallback: {result.fallback_message}"
            else:
                return f"🚨 {service_name.title()} is unavailable with no fallback: {result.error_message}"
        
        else:
            return f"❓ {service_name.title()} status unknown"
    
    def generate_status_summary(self, report: SystemHealthReport) -> Dict[str, Any]:
        """Generate a human-readable status summary."""
        summary = {
            'overall_status': report.overall_status.value,
            'status_message': self._get_overall_status_message(report.overall_status),
            'services_summary': {
                'total': len(report.services),
                'available': len([s for s in report.services.values() if s.status == ServiceStatus.AVAILABLE]),
                'degraded': len([s for s in report.services.values() if s.status == ServiceStatus.DEGRADED]),
                'fallback': len([s for s in report.services.values() if s.status == ServiceStatus.FALLBACK]),
                'unavailable': len([s for s in report.services.values() if s.status == ServiceStatus.UNAVAILABLE])
            },
            'service_messages': {
                name: self.get_service_status_message(name, result)
                for name, result in report.services.items()
            },
            'critical_issues': report.critical_issues,
            'warnings': report.warnings,
            'recommendations': report.recommendations,
            'timestamp': report.timestamp.isoformat()
        }
        
        return summary
    
    def _get_overall_status_message(self, status: ServiceStatus) -> str:
        """Get overall system status message."""
        if status == ServiceStatus.AVAILABLE:
            return "🟢 All services are operational"
        elif status == ServiceStatus.DEGRADED:
            return "🟡 Some services are experiencing issues but system is functional"
        elif status == ServiceStatus.FALLBACK:
            return "🟠 Some services are unavailable but fallback modes are active"
        elif status == ServiceStatus.UNAVAILABLE:
            return "🔴 Critical services are unavailable - system functionality is limited"
        else:
            return "⚪ System status unknown"


# Global health validator instance
health_validator = HealthValidator()