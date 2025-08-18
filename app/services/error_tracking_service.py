"""
Error tracking and analysis service for AI Secretary.
Provides comprehensive error monitoring, categorization, and reporting.
"""

import time
import traceback
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
from enum import Enum
import redis
from flask import request, g, current_app
import structlog

logger = structlog.get_logger()


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories."""
    APPLICATION = "application"
    DATABASE = "database"
    EXTERNAL_API = "external_api"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    PERMISSION = "permission"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    NETWORK = "network"
    UNKNOWN = "unknown"


@dataclass
class ErrorEvent:
    """Error event data structure."""
    id: str
    fingerprint: str
    message: str
    exception_type: str
    stack_trace: str
    category: ErrorCategory
    severity: ErrorSeverity
    timestamp: datetime
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['category'] = self.category.value
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class ErrorSummary:
    """Error summary statistics."""
    fingerprint: str
    message: str
    exception_type: str
    category: ErrorCategory
    severity: ErrorSeverity
    count: int
    first_seen: datetime
    last_seen: datetime
    affected_users: int
    affected_tenants: int
    endpoints: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['category'] = self.category.value
        data['severity'] = self.severity.value
        data['first_seen'] = self.first_seen.isoformat()
        data['last_seen'] = self.last_seen.isoformat()
        return data


class ErrorTrackingService:
    """Main error tracking service."""
    
    def __init__(self, redis_client: redis.Redis = None):
        self.redis = redis_client
        self.error_buffer = []
        self.error_summaries: Dict[str, ErrorSummary] = {}
        self.categorization_rules = self._setup_categorization_rules()
        self.severity_rules = self._setup_severity_rules()
        
    def _setup_categorization_rules(self) -> List[Tuple[str, ErrorCategory]]:
        """Set up error categorization rules."""
        return [
            # Database errors
            ('psycopg2', ErrorCategory.DATABASE),
            ('sqlalchemy', ErrorCategory.DATABASE),
            ('database', ErrorCategory.DATABASE),
            ('connection', ErrorCategory.DATABASE),
            
            # External API errors
            ('requests.exceptions', ErrorCategory.EXTERNAL_API),
            ('httpx', ErrorCategory.EXTERNAL_API),
            ('openai', ErrorCategory.EXTERNAL_API),
            ('stripe', ErrorCategory.EXTERNAL_API),
            ('google', ErrorCategory.EXTERNAL_API),
            
            # Authentication errors
            ('jwt', ErrorCategory.AUTHENTICATION),
            ('unauthorized', ErrorCategory.AUTHENTICATION),
            ('authentication', ErrorCategory.AUTHENTICATION),
            ('login', ErrorCategory.AUTHENTICATION),
            
            # Validation errors
            ('validation', ErrorCategory.VALIDATION),
            ('marshmallow', ErrorCategory.VALIDATION),
            ('pydantic', ErrorCategory.VALIDATION),
            ('invalid', ErrorCategory.VALIDATION),
            
            # Permission errors
            ('permission', ErrorCategory.PERMISSION),
            ('forbidden', ErrorCategory.PERMISSION),
            ('access', ErrorCategory.PERMISSION),
            
            # Rate limiting
            ('rate', ErrorCategory.RATE_LIMIT),
            ('limit', ErrorCategory.RATE_LIMIT),
            ('throttle', ErrorCategory.RATE_LIMIT),
            
            # Timeout errors
            ('timeout', ErrorCategory.TIMEOUT),
            ('timed out', ErrorCategory.TIMEOUT),
            
            # Network errors
            ('network', ErrorCategory.NETWORK),
            ('connection', ErrorCategory.NETWORK),
            ('dns', ErrorCategory.NETWORK),
        ]
    
    def _setup_severity_rules(self) -> List[Tuple[str, ErrorSeverity]]:
        """Set up error severity rules."""
        return [
            # Critical errors
            ('outofmemory', ErrorSeverity.CRITICAL),
            ('systemerror', ErrorSeverity.CRITICAL),
            ('database.*down', ErrorSeverity.CRITICAL),
            ('redis.*down', ErrorSeverity.CRITICAL),
            
            # High severity
            ('500', ErrorSeverity.HIGH),
            ('internal.*server.*error', ErrorSeverity.HIGH),
            ('exception', ErrorSeverity.HIGH),
            
            # Medium severity
            ('400', ErrorSeverity.MEDIUM),
            ('401', ErrorSeverity.MEDIUM),
            ('403', ErrorSeverity.MEDIUM),
            ('404', ErrorSeverity.MEDIUM),
            
            # Low severity
            ('warning', ErrorSeverity.LOW),
            ('info', ErrorSeverity.LOW),
        ]
    
    def _categorize_error(self, error_message: str, exception_type: str) -> ErrorCategory:
        """Categorize error based on message and type."""
        text = f"{error_message} {exception_type}".lower()
        
        for pattern, category in self.categorization_rules:
            if pattern.lower() in text:
                return category
        
        return ErrorCategory.UNKNOWN
    
    def _determine_severity(self, error_message: str, exception_type: str) -> ErrorSeverity:
        """Determine error severity."""
        import re
        
        text = f"{error_message} {exception_type}".lower()
        
        for pattern, severity in self.severity_rules:
            if re.search(pattern.lower(), text):
                return severity
        
        # Default severity based on exception type
        if 'error' in exception_type.lower():
            return ErrorSeverity.HIGH
        elif 'exception' in exception_type.lower():
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW
    
    def _generate_fingerprint(self, exception_type: str, message: str, stack_trace: str) -> str:
        """Generate unique fingerprint for error grouping."""
        # Extract relevant parts of stack trace (function names and line numbers)
        lines = stack_trace.split('\n')
        relevant_lines = []
        
        for line in lines:
            if 'File "' in line and 'line' in line:
                # Extract file and line info
                relevant_lines.append(line.strip())
            elif line.strip().startswith('in '):
                # Extract function name
                relevant_lines.append(line.strip())
        
        # Create fingerprint from exception type, message, and stack trace
        fingerprint_data = f"{exception_type}:{message}:{':'.join(relevant_lines[-5:])}"
        return hashlib.md5(fingerprint_data.encode()).hexdigest()
    
    def track_error(
        self,
        exception: Exception,
        context: Dict[str, Any] = None,
        custom_message: str = None
    ) -> str:
        """Track an error occurrence."""
        try:
            # Generate error details
            exception_type = type(exception).__name__
            message = custom_message or str(exception)
            stack_trace = traceback.format_exc()
            
            # Generate fingerprint for grouping
            fingerprint = self._generate_fingerprint(exception_type, message, stack_trace)
            
            # Categorize and determine severity
            category = self._categorize_error(message, exception_type)
            severity = self._determine_severity(message, exception_type)
            
            # Create error event
            error_event = ErrorEvent(
                id=f"err_{int(time.time() * 1000)}_{hash(stack_trace) % 10000}",
                fingerprint=fingerprint,
                message=message,
                exception_type=exception_type,
                stack_trace=stack_trace,
                category=category,
                severity=severity,
                timestamp=datetime.utcnow(),
                context=context or {}
            )
            
            # Add request context if available
            if request:
                error_event.request_id = getattr(g, 'request_id', None)
                error_event.user_id = getattr(g, 'user_id', None)
                error_event.tenant_id = getattr(g, 'tenant_id', None)
                error_event.endpoint = request.endpoint
                error_event.method = request.method
                error_event.user_agent = request.headers.get('User-Agent', '')
                error_event.ip_address = request.remote_addr
            
            # Store error
            self._store_error(error_event)
            
            # Update error summary
            self._update_error_summary(error_event)
            
            # Log error
            logger.error(
                "Error tracked",
                error_id=error_event.id,
                fingerprint=fingerprint,
                category=category.value,
                severity=severity.value,
                exception_type=exception_type,
                message=message
            )
            
            return error_event.id
            
        except Exception as e:
            logger.error("Failed to track error", error=str(e))
            return None
    
    def _store_error(self, error_event: ErrorEvent):
        """Store error event."""
        # Store in memory buffer
        self.error_buffer.append(error_event)
        
        # Keep buffer size manageable
        if len(self.error_buffer) > 1000:
            self.error_buffer = self.error_buffer[-500:]
        
        # Store in Redis if available
        if self.redis:
            try:
                # Store individual error
                error_key = f"errors:events:{error_event.id}"
                self.redis.setex(error_key, 86400 * 7, error_event.to_dict())  # Keep for 7 days
                
                # Add to fingerprint group
                group_key = f"errors:groups:{error_event.fingerprint}"
                self.redis.lpush(group_key, error_event.id)
                self.redis.expire(group_key, 86400 * 30)  # Keep for 30 days
                
                # Update counters
                counter_key = f"errors:counters:{datetime.utcnow().strftime('%Y-%m-%d-%H')}"
                self.redis.hincrby(counter_key, error_event.fingerprint, 1)
                self.redis.expire(counter_key, 86400 * 7)
                
            except Exception as e:
                logger.warning("Failed to store error in Redis", error=str(e))
    
    def _update_error_summary(self, error_event: ErrorEvent):
        """Update error summary statistics."""
        fingerprint = error_event.fingerprint
        
        if fingerprint in self.error_summaries:
            summary = self.error_summaries[fingerprint]
            summary.count += 1
            summary.last_seen = error_event.timestamp
            
            # Update affected users/tenants
            if error_event.user_id:
                summary.affected_users = len(set([error_event.user_id]))  # Simplified
            if error_event.tenant_id:
                summary.affected_tenants = len(set([error_event.tenant_id]))  # Simplified
            
            # Update endpoints
            if error_event.endpoint and error_event.endpoint not in summary.endpoints:
                summary.endpoints.append(error_event.endpoint)
        else:
            # Create new summary
            self.error_summaries[fingerprint] = ErrorSummary(
                fingerprint=fingerprint,
                message=error_event.message,
                exception_type=error_event.exception_type,
                category=error_event.category,
                severity=error_event.severity,
                count=1,
                first_seen=error_event.timestamp,
                last_seen=error_event.timestamp,
                affected_users=1 if error_event.user_id else 0,
                affected_tenants=1 if error_event.tenant_id else 0,
                endpoints=[error_event.endpoint] if error_event.endpoint else []
            )
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get error summary for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Filter recent errors
        recent_errors = [
            error for error in self.error_buffer
            if error.timestamp >= cutoff_time
        ]
        
        # Calculate statistics
        total_errors = len(recent_errors)
        error_by_category = Counter(error.category for error in recent_errors)
        error_by_severity = Counter(error.severity for error in recent_errors)
        error_by_endpoint = Counter(error.endpoint for error in recent_errors if error.endpoint)
        
        # Top error fingerprints
        fingerprint_counts = Counter(error.fingerprint for error in recent_errors)
        top_errors = []
        
        for fingerprint, count in fingerprint_counts.most_common(10):
            if fingerprint in self.error_summaries:
                summary = self.error_summaries[fingerprint]
                top_errors.append({
                    'fingerprint': fingerprint,
                    'message': summary.message,
                    'exception_type': summary.exception_type,
                    'category': summary.category.value,
                    'severity': summary.severity.value,
                    'count': count
                })
        
        return {
            'period_hours': hours,
            'total_errors': total_errors,
            'errors_by_category': {cat.value: count for cat, count in error_by_category.items()},
            'errors_by_severity': {sev.value: count for sev, count in error_by_severity.items()},
            'errors_by_endpoint': dict(error_by_endpoint.most_common(10)),
            'top_errors': top_errors,
            'error_rate': total_errors / hours if hours > 0 else 0
        }
    
    def get_error_details(self, fingerprint: str, limit: int = 50) -> Dict[str, Any]:
        """Get detailed information about a specific error."""
        if fingerprint not in self.error_summaries:
            return None
        
        summary = self.error_summaries[fingerprint]
        
        # Get recent occurrences
        recent_occurrences = [
            error.to_dict() for error in self.error_buffer
            if error.fingerprint == fingerprint
        ][-limit:]
        
        return {
            'summary': summary.to_dict(),
            'recent_occurrences': recent_occurrences,
            'occurrence_count': len(recent_occurrences)
        }
    
    def get_error_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get error trends over time."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Group errors by hour
        hourly_counts = defaultdict(int)
        hourly_by_severity = defaultdict(lambda: defaultdict(int))
        
        for error in self.error_buffer:
            if error.timestamp >= cutoff_time:
                hour_key = error.timestamp.strftime('%Y-%m-%d %H:00')
                hourly_counts[hour_key] += 1
                hourly_by_severity[hour_key][error.severity.value] += 1
        
        # Convert to sorted lists
        sorted_hours = sorted(hourly_counts.keys())
        
        return {
            'period_hours': hours,
            'hourly_counts': [
                {
                    'hour': hour,
                    'total': hourly_counts[hour],
                    'by_severity': dict(hourly_by_severity[hour])
                }
                for hour in sorted_hours
            ]
        }
    
    def clear_old_errors(self, days: int = 7):
        """Clear old errors from memory."""
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        # Filter out old errors
        self.error_buffer = [
            error for error in self.error_buffer
            if error.timestamp >= cutoff_time
        ]
        
        # Clean up old summaries
        old_fingerprints = []
        for fingerprint, summary in self.error_summaries.items():
            if summary.last_seen < cutoff_time:
                old_fingerprints.append(fingerprint)
        
        for fingerprint in old_fingerprints:
            del self.error_summaries[fingerprint]
        
        logger.info("Old errors cleared", cleared_count=len(old_fingerprints))


# Global error tracking service
error_tracking_service = ErrorTrackingService()


def init_error_tracking(app):
    """Initialize error tracking service."""
    try:
        # Initialize Redis client if available
        redis_url = app.config.get('REDIS_URL')
        if redis_url:
            redis_client = redis.from_url(redis_url)
            error_tracking_service.redis = redis_client
        
        # Set up Flask error handler
        @app.errorhandler(Exception)
        def handle_exception(e):
            # Track the error
            error_tracking_service.track_error(e)
            
            # Re-raise to let Flask handle it normally
            raise e
        
        logger.info("Error tracking service initialized")
        return error_tracking_service
        
    except Exception as e:
        logger.error("Failed to initialize error tracking service", error=str(e))
        return None


def track_error(exception: Exception, context: Dict[str, Any] = None, message: str = None) -> str:
    """Convenience function to track an error."""
    return error_tracking_service.track_error(exception, context, message)