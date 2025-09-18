"""
Database Error Logging Utilities

This module provides specialized logging utilities for database initialization errors,
including structured logging, error aggregation, and troubleshooting report generation.
"""
import os
import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from .database_errors import DatabaseErrorCode, ErrorSeverity


class DatabaseErrorLogger:
    """
    Specialized logger for database initialization errors.
    
    Provides structured logging, error aggregation, and report generation
    specifically for database initialization issues.
    """
    
    def __init__(self, log_dir: str = "logs", max_log_files: int = 10):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.max_log_files = max_log_files
        
        # Set up structured logger
        self.logger = logging.getLogger(f"{__name__}.DatabaseErrorLogger")
        self._setup_file_handler()
        
        # Error aggregation
        self._error_counts = {}
        self._recent_errors = []
        self._error_patterns = {}
    
    def _setup_file_handler(self):
        """Set up file handler for database error logging."""
        log_file = self.log_dir / f"database_errors_{datetime.now().strftime('%Y%m%d')}.log"
        
        # Create file handler with rotation
        handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        handler.setLevel(logging.DEBUG)
        
        # Create detailed formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s | '
            'error_code=%(error_code)s | severity=%(severity)s | '
            'operation=%(operation)s | database_type=%(database_type)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        # Add handler to logger
        if not self.logger.handlers:
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
        
        # Clean up old log files
        self._cleanup_old_logs()
    
    def log_database_error(
        self,
        error_code: DatabaseErrorCode,
        message: str,
        severity: ErrorSeverity,
        context: Dict[str, Any] = None,
        exception: Exception = None,
        recovery_attempted: bool = False,
        recovery_successful: bool = False
    ):
        """
        Log a database initialization error with full context.
        
        Args:
            error_code: Database error code
            message: Error message
            severity: Error severity level
            context: Additional context information
            exception: Original exception if available
            recovery_attempted: Whether recovery was attempted
            recovery_successful: Whether recovery was successful
        """
        context = context or {}
        
        # Prepare log record
        log_record = {
            'timestamp': datetime.now().isoformat(),
            'error_code': error_code.value,
            'message': message,
            'severity': severity.value,
            'context': context,
            'recovery_attempted': recovery_attempted,
            'recovery_successful': recovery_successful
        }
        
        # Add exception details if available
        if exception:
            log_record.update({
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'stack_trace': traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            })
        
        # Log with appropriate level
        log_level = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }.get(severity, logging.ERROR)
        
        # Create extra fields for formatter
        extra = {
            'error_code': error_code.value,
            'severity': severity.value,
            'operation': context.get('operation', 'unknown'),
            'database_type': context.get('database_type', 'unknown')
        }
        
        self.logger.log(log_level, message, extra=extra)
        
        # Update error aggregation
        self._update_error_aggregation(log_record)
        
        # Store recent error for analysis
        self._recent_errors.append(log_record)
        if len(self._recent_errors) > 100:  # Keep last 100 errors
            self._recent_errors.pop(0)
    
    def log_recovery_attempt(
        self,
        error_code: DatabaseErrorCode,
        recovery_method: str,
        success: bool,
        details: Dict[str, Any] = None
    ):
        """
        Log a recovery attempt for a database error.
        
        Args:
            error_code: Database error code being recovered from
            recovery_method: Method used for recovery
            success: Whether recovery was successful
            details: Additional recovery details
        """
        details = details or {}
        
        message = f"Recovery attempt for {error_code.value}: {recovery_method} - {'SUCCESS' if success else 'FAILED'}"
        
        log_record = {
            'timestamp': datetime.now().isoformat(),
            'error_code': error_code.value,
            'recovery_method': recovery_method,
            'success': success,
            'details': details
        }
        
        extra = {
            'error_code': error_code.value,
            'severity': 'info',
            'operation': 'recovery',
            'database_type': details.get('database_type', 'unknown')
        }
        
        log_level = logging.INFO if success else logging.WARNING
        self.logger.log(log_level, message, extra=extra)
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary of errors from the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with error summary
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_errors = [
            error for error in self._recent_errors
            if datetime.fromisoformat(error['timestamp']) > cutoff_time
        ]
        
        # Count errors by code and severity
        error_counts = {}
        severity_counts = {}
        recovery_stats = {'attempted': 0, 'successful': 0}
        
        for error in recent_errors:
            error_code = error['error_code']
            severity = error['severity']
            
            error_counts[error_code] = error_counts.get(error_code, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            if error.get('recovery_attempted'):
                recovery_stats['attempted'] += 1
                if error.get('recovery_successful'):
                    recovery_stats['successful'] += 1
        
        return {
            'time_period_hours': hours,
            'total_errors': len(recent_errors),
            'error_counts': error_counts,
            'severity_counts': severity_counts,
            'recovery_stats': recovery_stats,
            'recovery_success_rate': (
                recovery_stats['successful'] / recovery_stats['attempted']
                if recovery_stats['attempted'] > 0 else 0
            ),
            'most_common_error': (
                max(error_counts.items(), key=lambda x: x[1])[0]
                if error_counts else None
            ),
            'generated_at': datetime.now().isoformat()
        }
    
    def get_error_patterns(self) -> Dict[str, Any]:
        """
        Analyze error patterns and trends.
        
        Returns:
            Dictionary with error pattern analysis
        """
        if not self._recent_errors:
            return {'patterns': [], 'trends': {}}
        
        # Group errors by hour to identify patterns
        hourly_errors = {}
        error_sequences = []
        
        for error in self._recent_errors:
            timestamp = datetime.fromisoformat(error['timestamp'])
            hour_key = timestamp.strftime('%Y-%m-%d %H:00')
            
            if hour_key not in hourly_errors:
                hourly_errors[hour_key] = []
            hourly_errors[hour_key].append(error)
        
        # Identify error sequences (same error repeated)
        current_sequence = None
        sequence_count = 0
        
        for error in self._recent_errors:
            error_code = error['error_code']
            
            if current_sequence == error_code:
                sequence_count += 1
            else:
                if sequence_count > 2:  # Report sequences of 3 or more
                    error_sequences.append({
                        'error_code': current_sequence,
                        'count': sequence_count,
                        'pattern': 'repeated_error'
                    })
                current_sequence = error_code
                sequence_count = 1
        
        # Check for final sequence
        if sequence_count > 2:
            error_sequences.append({
                'error_code': current_sequence,
                'count': sequence_count,
                'pattern': 'repeated_error'
            })
        
        return {
            'patterns': error_sequences,
            'trends': {
                'hourly_distribution': {
                    hour: len(errors) for hour, errors in hourly_errors.items()
                },
                'peak_error_hour': (
                    max(hourly_errors.items(), key=lambda x: len(x[1]))[0]
                    if hourly_errors else None
                )
            },
            'analysis_timestamp': datetime.now().isoformat()
        }
    
    def generate_troubleshooting_report(
        self,
        include_stack_traces: bool = False,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Generate comprehensive troubleshooting report.
        
        Args:
            include_stack_traces: Whether to include full stack traces
            hours: Number of hours to analyze
            
        Returns:
            Dictionary with troubleshooting report
        """
        summary = self.get_error_summary(hours)
        patterns = self.get_error_patterns()
        
        # Get recent errors with details
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_errors = [
            error for error in self._recent_errors
            if datetime.fromisoformat(error['timestamp']) > cutoff_time
        ]
        
        # Remove stack traces if not requested
        if not include_stack_traces:
            for error in recent_errors:
                error.pop('stack_trace', None)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(summary, patterns)
        
        return {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'time_period_hours': hours,
                'total_errors_analyzed': len(recent_errors),
                'include_stack_traces': include_stack_traces
            },
            'error_summary': summary,
            'error_patterns': patterns,
            'recent_errors': recent_errors[-10:],  # Last 10 errors
            'recommendations': recommendations,
            'log_files': self._get_log_file_info()
        }
    
    def export_errors_to_json(self, filepath: str, hours: int = 24):
        """
        Export recent errors to JSON file.
        
        Args:
            filepath: Path to export file
            hours: Number of hours of errors to export
        """
        report = self.generate_troubleshooting_report(
            include_stack_traces=True,
            hours=hours
        )
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    
    def _update_error_aggregation(self, log_record: Dict[str, Any]):
        """Update error aggregation statistics."""
        error_code = log_record['error_code']
        severity = log_record['severity']
        
        # Update error counts
        if error_code not in self._error_counts:
            self._error_counts[error_code] = {
                'total': 0,
                'by_severity': {},
                'first_seen': log_record['timestamp'],
                'last_seen': log_record['timestamp']
            }
        
        self._error_counts[error_code]['total'] += 1
        self._error_counts[error_code]['last_seen'] = log_record['timestamp']
        
        if severity not in self._error_counts[error_code]['by_severity']:
            self._error_counts[error_code]['by_severity'][severity] = 0
        self._error_counts[error_code]['by_severity'][severity] += 1
    
    def _generate_recommendations(
        self,
        summary: Dict[str, Any],
        patterns: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on error analysis."""
        recommendations = []
        
        # High error rate recommendation
        if summary['total_errors'] > 10:
            recommendations.append({
                'priority': 'high',
                'category': 'error_rate',
                'title': 'High Error Rate Detected',
                'description': f"Detected {summary['total_errors']} errors in the last {summary['time_period_hours']} hours",
                'action': 'Review database configuration and connectivity'
            })
        
        # Low recovery success rate
        if summary['recovery_stats']['attempted'] > 0:
            success_rate = summary['recovery_success_rate']
            if success_rate < 0.5:
                recommendations.append({
                    'priority': 'medium',
                    'category': 'recovery',
                    'title': 'Low Recovery Success Rate',
                    'description': f"Recovery success rate is {success_rate:.1%}",
                    'action': 'Review recovery mechanisms and error handling'
                })
        
        # Repeated error pattern
        for pattern in patterns.get('patterns', []):
            if pattern['count'] > 5:
                recommendations.append({
                    'priority': 'medium',
                    'category': 'pattern',
                    'title': 'Repeated Error Pattern',
                    'description': f"Error {pattern['error_code']} repeated {pattern['count']} times",
                    'action': 'Investigate root cause of recurring error'
                })
        
        # Critical errors
        if summary['severity_counts'].get('critical', 0) > 0:
            recommendations.append({
                'priority': 'critical',
                'category': 'severity',
                'title': 'Critical Errors Detected',
                'description': f"Found {summary['severity_counts']['critical']} critical errors",
                'action': 'Immediate attention required for critical database issues'
            })
        
        return recommendations
    
    def _get_log_file_info(self) -> List[Dict[str, Any]]:
        """Get information about log files."""
        log_files = []
        
        for log_file in self.log_dir.glob("database_errors_*.log"):
            try:
                stat = log_file.stat()
                log_files.append({
                    'filename': log_file.name,
                    'path': str(log_file),
                    'size_bytes': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except OSError:
                continue
        
        return sorted(log_files, key=lambda x: x['modified'], reverse=True)
    
    def _cleanup_old_logs(self):
        """Clean up old log files."""
        log_files = list(self.log_dir.glob("database_errors_*.log"))
        
        if len(log_files) > self.max_log_files:
            # Sort by modification time and remove oldest
            log_files.sort(key=lambda f: f.stat().st_mtime)
            for old_file in log_files[:-self.max_log_files]:
                try:
                    old_file.unlink()
                except OSError:
                    pass


# Global error logger instance
_error_logger = None


def get_database_error_logger() -> DatabaseErrorLogger:
    """Get the global database error logger instance."""
    global _error_logger
    if _error_logger is None:
        _error_logger = DatabaseErrorLogger()
    return _error_logger