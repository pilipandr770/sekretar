"""
Error Rate Limiter

This module provides error rate limiting functionality to prevent repeated error log spam
and provide periodic summaries of suppressed errors.
"""
import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class ErrorOccurrence:
    """Represents a single error occurrence."""
    timestamp: float
    error_type: str
    error_message: str
    context: Dict[str, Any] = field(default_factory=dict)
    traceback: Optional[str] = None


@dataclass
class ErrorSummary:
    """Summary of suppressed errors."""
    error_key: str
    error_type: str
    first_occurrence: float
    last_occurrence: float
    total_count: int
    suppressed_count: int
    sample_message: str
    sample_context: Dict[str, Any] = field(default_factory=dict)


class ErrorRateLimiter:
    """
    Rate limiter for error messages to prevent log spam.
    
    Features:
    - Rate limiting based on error type and message hash
    - Periodic summaries of suppressed errors
    - Configurable time windows and thresholds
    - Thread-safe operation
    """
    
    def __init__(self, 
                 max_errors_per_minute: int = 5,
                 max_errors_per_hour: int = 50,
                 summary_interval_minutes: int = 15,
                 cleanup_interval_minutes: int = 60,
                 max_stored_errors: int = 1000):
        """
        Initialize error rate limiter.
        
        Args:
            max_errors_per_minute: Maximum errors per minute before rate limiting
            max_errors_per_hour: Maximum errors per hour before rate limiting
            summary_interval_minutes: How often to log suppressed error summaries
            cleanup_interval_minutes: How often to clean up old error records
            max_stored_errors: Maximum number of error occurrences to store
        """
        self.max_errors_per_minute = max_errors_per_minute
        self.max_errors_per_hour = max_errors_per_hour
        self.summary_interval = summary_interval_minutes * 60  # Convert to seconds
        self.cleanup_interval = cleanup_interval_minutes * 60  # Convert to seconds
        self.max_stored_errors = max_stored_errors
        
        # Thread-safe storage
        self._lock = threading.RLock()
        
        # Error tracking
        self._error_occurrences: Dict[str, deque] = defaultdict(deque)
        self._error_summaries: Dict[str, ErrorSummary] = {}
        self._suppressed_errors: Dict[str, List[ErrorOccurrence]] = defaultdict(list)
        
        # Timing
        self._last_summary_time = time.time()
        self._last_cleanup_time = time.time()
        
        # Statistics
        self._total_errors_seen = 0
        self._total_errors_suppressed = 0
        self._total_summaries_logged = 0
    
    def should_log_error(self, 
                        error_type: str, 
                        error_message: str, 
                        context: Optional[Dict[str, Any]] = None,
                        traceback: Optional[str] = None) -> bool:
        """
        Determine if an error should be logged based on rate limiting rules.
        
        Args:
            error_type: Type of error (e.g., 'DatabaseConnectionError')
            error_message: Error message
            context: Additional context information
            traceback: Error traceback if available
            
        Returns:
            True if error should be logged, False if it should be suppressed
        """
        with self._lock:
            self._total_errors_seen += 1
            
            # Create error key for rate limiting
            error_key = self._create_error_key(error_type, error_message)
            
            # Create error occurrence
            occurrence = ErrorOccurrence(
                timestamp=time.time(),
                error_type=error_type,
                error_message=error_message,
                context=context or {},
                traceback=traceback
            )
            
            # Check if we should perform cleanup
            self._maybe_cleanup()
            
            # Check if we should log summary
            self._maybe_log_summary()
            
            # Get or create error occurrence deque
            if error_key not in self._error_occurrences:
                self._error_occurrences[error_key] = deque(maxlen=self.max_stored_errors)
            
            occurrences = self._error_occurrences[error_key]
            
            # Clean old occurrences
            current_time = time.time()
            self._clean_old_occurrences(occurrences, current_time)
            
            # Count recent occurrences
            minute_ago = current_time - 60
            hour_ago = current_time - 3600
            
            recent_minute_count = sum(1 for occ in occurrences if occ.timestamp > minute_ago)
            recent_hour_count = sum(1 for occ in occurrences if occ.timestamp > hour_ago)
            
            # Check rate limits (count current occurrence)
            should_log = (recent_minute_count < self.max_errors_per_minute and 
                         recent_hour_count < self.max_errors_per_hour)
            
            # Add occurrence to tracking
            occurrences.append(occurrence)
            
            if should_log:
                # Update or create summary for this error type
                self._update_error_summary(error_key, occurrence, suppressed=False)
            else:
                # Error is being suppressed
                self._total_errors_suppressed += 1
                self._suppressed_errors[error_key].append(occurrence)
                self._update_error_summary(error_key, occurrence, suppressed=True)
                
                # Log suppression notice occasionally
                if recent_minute_count == self.max_errors_per_minute:
                    logger.warning(
                        f"Rate limiting activated for error type: {error_type}. "
                        f"Further similar errors will be suppressed. "
                        f"Summary will be provided every {self.summary_interval // 60} minutes."
                    )
            
            return should_log
    
    def log_error_with_rate_limiting(self,
                                   error_type: str,
                                   error_message: str,
                                   log_level: str = 'error',
                                   context: Optional[Dict[str, Any]] = None,
                                   traceback: Optional[str] = None,
                                   logger_instance: Optional[logging.Logger] = None) -> bool:
        """
        Log an error with rate limiting applied.
        
        Args:
            error_type: Type of error
            error_message: Error message
            log_level: Log level ('debug', 'info', 'warning', 'error', 'critical')
            context: Additional context information
            traceback: Error traceback if available
            logger_instance: Logger instance to use (defaults to module logger)
            
        Returns:
            True if error was logged, False if it was suppressed
        """
        should_log = self.should_log_error(error_type, error_message, context, traceback)
        
        if should_log:
            log_instance = logger_instance or logger
            log_method = getattr(log_instance, log_level.lower(), log_instance.error)
            
            # Format log message
            log_data = {
                'error_type': error_type,
                'error_message': error_message,
                'timestamp': datetime.now().isoformat()
            }
            
            if context:
                log_data['context'] = context
            
            if traceback:
                log_data['traceback'] = traceback
            
            # Log with structured data
            log_method(f"[{error_type}] {error_message}", extra=log_data)
        
        return should_log
    
    def force_log_summary(self) -> Dict[str, Any]:
        """
        Force logging of current error summaries.
        
        Returns:
            Dictionary containing summary statistics
        """
        with self._lock:
            return self._log_suppressed_error_summary()
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get current error statistics.
        
        Returns:
            Dictionary containing error statistics
        """
        with self._lock:
            current_time = time.time()
            
            # Calculate active error types
            active_errors = {}
            for error_key, occurrences in self._error_occurrences.items():
                if occurrences:
                    recent_count = sum(1 for occ in occurrences 
                                     if current_time - occ.timestamp < 3600)  # Last hour
                    if recent_count > 0:
                        active_errors[error_key] = {
                            'recent_count': recent_count,
                            'total_count': len(occurrences),
                            'last_occurrence': max(occ.timestamp for occ in occurrences)
                        }
            
            return {
                'total_errors_seen': self._total_errors_seen,
                'total_errors_suppressed': self._total_errors_suppressed,
                'total_summaries_logged': self._total_summaries_logged,
                'active_error_types': len(active_errors),
                'active_errors': active_errors,
                'rate_limits': {
                    'max_errors_per_minute': self.max_errors_per_minute,
                    'max_errors_per_hour': self.max_errors_per_hour
                },
                'last_summary_time': self._last_summary_time,
                'last_cleanup_time': self._last_cleanup_time
            }
    
    def reset_error_counts(self, error_key: Optional[str] = None):
        """
        Reset error counts for debugging or testing.
        
        Args:
            error_key: Specific error key to reset, or None to reset all
        """
        with self._lock:
            if error_key:
                if error_key in self._error_occurrences:
                    self._error_occurrences[error_key].clear()
                if error_key in self._suppressed_errors:
                    self._suppressed_errors[error_key].clear()
                if error_key in self._error_summaries:
                    del self._error_summaries[error_key]
            else:
                self._error_occurrences.clear()
                self._suppressed_errors.clear()
                self._error_summaries.clear()
                self._total_errors_seen = 0
                self._total_errors_suppressed = 0
                self._total_summaries_logged = 0
    
    def _create_error_key(self, error_type: str, error_message: str) -> str:
        """Create a unique key for error rate limiting."""
        # Create hash of error type and message for grouping similar errors
        message_hash = hashlib.md5(error_message.encode('utf-8')).hexdigest()[:8]
        return f"{error_type}:{message_hash}"
    
    def _clean_old_occurrences(self, occurrences: deque, current_time: float):
        """Remove old occurrences from the deque."""
        # Remove occurrences older than 1 hour
        hour_ago = current_time - 3600
        while occurrences and occurrences[0].timestamp < hour_ago:
            occurrences.popleft()
    
    def _update_error_summary(self, error_key: str, occurrence: ErrorOccurrence, suppressed: bool):
        """Update error summary for the given error key."""
        if error_key not in self._error_summaries:
            self._error_summaries[error_key] = ErrorSummary(
                error_key=error_key,
                error_type=occurrence.error_type,
                first_occurrence=occurrence.timestamp,
                last_occurrence=occurrence.timestamp,
                total_count=1,
                suppressed_count=1 if suppressed else 0,
                sample_message=occurrence.error_message,
                sample_context=occurrence.context
            )
        else:
            summary = self._error_summaries[error_key]
            summary.last_occurrence = occurrence.timestamp
            summary.total_count += 1
            if suppressed:
                summary.suppressed_count += 1
    
    def _maybe_cleanup(self):
        """Perform cleanup if enough time has passed."""
        current_time = time.time()
        if current_time - self._last_cleanup_time > self.cleanup_interval:
            self._cleanup_old_data(current_time)
            self._last_cleanup_time = current_time
    
    def _maybe_log_summary(self):
        """Log summary if enough time has passed."""
        current_time = time.time()
        if current_time - self._last_summary_time > self.summary_interval:
            self._log_suppressed_error_summary()
            self._last_summary_time = current_time
    
    def _cleanup_old_data(self, current_time: float):
        """Clean up old error data to prevent memory leaks."""
        hour_ago = current_time - 3600
        
        # Clean up old occurrences
        for error_key in list(self._error_occurrences.keys()):
            occurrences = self._error_occurrences[error_key]
            self._clean_old_occurrences(occurrences, current_time)
            
            # Remove empty deques
            if not occurrences:
                del self._error_occurrences[error_key]
        
        # Clean up old suppressed errors
        for error_key in list(self._suppressed_errors.keys()):
            suppressed_list = self._suppressed_errors[error_key]
            self._suppressed_errors[error_key] = [
                occ for occ in suppressed_list if occ.timestamp > hour_ago
            ]
            
            # Remove empty lists
            if not self._suppressed_errors[error_key]:
                del self._suppressed_errors[error_key]
        
        # Clean up old summaries
        for error_key in list(self._error_summaries.keys()):
            summary = self._error_summaries[error_key]
            if summary.last_occurrence < hour_ago:
                del self._error_summaries[error_key]
    
    def _log_suppressed_error_summary(self) -> Dict[str, Any]:
        """Log summary of suppressed errors."""
        if not self._suppressed_errors:
            return {'suppressed_error_types': 0, 'total_suppressed': 0}
        
        summary_data = {
            'suppressed_error_types': len(self._suppressed_errors),
            'total_suppressed': sum(len(errors) for errors in self._suppressed_errors.values()),
            'summary_period_minutes': self.summary_interval // 60,
            'error_summaries': []
        }
        
        for error_key, suppressed_list in self._suppressed_errors.items():
            if not suppressed_list:
                continue
            
            # Get summary for this error type
            error_summary = self._error_summaries.get(error_key)
            if not error_summary:
                continue
            
            # Calculate time range
            first_time = min(occ.timestamp for occ in suppressed_list)
            last_time = max(occ.timestamp for occ in suppressed_list)
            
            summary_entry = {
                'error_type': error_summary.error_type,
                'suppressed_count': len(suppressed_list),
                'total_count': error_summary.total_count,
                'first_occurrence': datetime.fromtimestamp(first_time).isoformat(),
                'last_occurrence': datetime.fromtimestamp(last_time).isoformat(),
                'sample_message': error_summary.sample_message,
                'duration_minutes': (last_time - first_time) / 60
            }
            
            # Add sample context if available
            if error_summary.sample_context:
                summary_entry['sample_context'] = error_summary.sample_context
            
            summary_data['error_summaries'].append(summary_entry)
        
        # Log the summary
        if summary_data['total_suppressed'] > 0:
            logger.warning(
                f"Error Rate Limiter Summary: {summary_data['total_suppressed']} errors "
                f"suppressed across {summary_data['suppressed_error_types']} error types "
                f"in the last {summary_data['summary_period_minutes']} minutes",
                extra={'error_summary': summary_data}
            )
            
            self._total_summaries_logged += 1
        
        # Clear suppressed errors after logging summary
        self._suppressed_errors.clear()
        
        return summary_data


# Global instance for easy access
_global_error_rate_limiter: Optional[ErrorRateLimiter] = None


def get_error_rate_limiter(**kwargs) -> ErrorRateLimiter:
    """
    Get or create global error rate limiter instance.
    
    Args:
        **kwargs: Configuration parameters for ErrorRateLimiter
        
    Returns:
        ErrorRateLimiter instance
    """
    global _global_error_rate_limiter
    
    if _global_error_rate_limiter is None:
        # Try to get configuration from config manager
        try:
            from .error_logging_config import get_error_logging_config_manager
            config_manager = get_error_logging_config_manager()
            rate_limiter_config = config_manager.get_rate_limiter_config()
            
            # Merge with any provided kwargs (kwargs take precedence)
            final_config = {**rate_limiter_config, **kwargs}
            _global_error_rate_limiter = ErrorRateLimiter(**final_config)
        except ImportError:
            # Fallback to default configuration if config manager not available
            _global_error_rate_limiter = ErrorRateLimiter(**kwargs)
    
    return _global_error_rate_limiter


def should_log_error(error_type: str, 
                    error_message: str, 
                    context: Optional[Dict[str, Any]] = None,
                    traceback: Optional[str] = None) -> bool:
    """
    Convenience function to check if error should be logged.
    
    Args:
        error_type: Type of error
        error_message: Error message
        context: Additional context information
        traceback: Error traceback if available
        
    Returns:
        True if error should be logged, False if suppressed
    """
    limiter = get_error_rate_limiter()
    return limiter.should_log_error(error_type, error_message, context, traceback)


def log_error_with_rate_limiting(error_type: str,
                               error_message: str,
                               log_level: str = 'error',
                               context: Optional[Dict[str, Any]] = None,
                               traceback: Optional[str] = None,
                               logger_instance: Optional[logging.Logger] = None) -> bool:
    """
    Convenience function to log error with rate limiting.
    
    Args:
        error_type: Type of error
        error_message: Error message
        log_level: Log level
        context: Additional context information
        traceback: Error traceback if available
        logger_instance: Logger instance to use
        
    Returns:
        True if error was logged, False if suppressed
    """
    limiter = get_error_rate_limiter()
    return limiter.log_error_with_rate_limiting(
        error_type, error_message, log_level, context, traceback, logger_instance
    )