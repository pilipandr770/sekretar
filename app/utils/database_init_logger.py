"""
Database Initialization Logging System

Provides comprehensive logging for database initialization steps with structured
output, progress tracking, and detailed error reporting.
"""
import logging
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum


class LogLevel(Enum):
    """Log levels for database initialization."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Categories for database initialization logs."""
    CONNECTION = "CONNECTION"
    SCHEMA = "SCHEMA"
    MIGRATION = "MIGRATION"
    SEEDING = "SEEDING"
    VALIDATION = "VALIDATION"
    REPAIR = "REPAIR"
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"


@dataclass
class LogEntry:
    """Structured log entry for database initialization."""
    timestamp: datetime
    level: LogLevel
    category: LogCategory
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[float] = None
    step: Optional[str] = None
    error: Optional[Exception] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary."""
        entry = {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'category': self.category.value,
            'message': self.message,
            'details': self.details
        }
        
        if self.duration is not None:
            entry['duration'] = self.duration
        
        if self.step:
            entry['step'] = self.step
        
        if self.error:
            entry['error'] = {
                'type': type(self.error).__name__,
                'message': str(self.error)
            }
        
        return entry


class DatabaseInitLogger:
    """
    Specialized logger for database initialization with progress tracking
    and structured output.
    """
    
    def __init__(self, name: str = "database_init", level: LogLevel = LogLevel.INFO):
        self.name = name
        self.level = level
        self.logger = logging.getLogger(name)
        self.entries: List[LogEntry] = []
        self.current_step: Optional[str] = None
        self.step_start_time: Optional[float] = None
        self.init_start_time: Optional[float] = None
        
        # Configure logger
        self._configure_logger()
        
        # Progress tracking
        self.total_steps = 0
        self.completed_steps = 0
        self.failed_steps = 0
        
        # Statistics
        self.stats = {
            'total_logs': 0,
            'errors': 0,
            'warnings': 0,
            'performance_metrics': {},
            'categories': {category.value: 0 for category in LogCategory}
        }
    
    def _configure_logger(self):
        """Configure the underlying Python logger."""
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Set level
        log_levels = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL
        }
        self.logger.setLevel(log_levels[self.level])
        
        # Create console handler with custom formatter
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_levels[self.level])
        
        # Custom formatter for database initialization
        formatter = DatabaseInitFormatter()
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(console_handler)
        self.logger.propagate = False
    
    def start_initialization(self, total_steps: int = 0):
        """Start initialization logging."""
        self.init_start_time = time.time()
        self.total_steps = total_steps
        self.completed_steps = 0
        self.failed_steps = 0
        
        self.log(
            LogLevel.INFO,
            LogCategory.CONNECTION,
            "🚀 Starting database initialization",
            details={'total_steps': total_steps}
        )
    
    def finish_initialization(self, success: bool):
        """Finish initialization logging."""
        duration = time.time() - self.init_start_time if self.init_start_time else 0
        
        if success:
            self.log(
                LogLevel.INFO,
                LogCategory.CONNECTION,
                f"✅ Database initialization completed successfully",
                details={
                    'duration': duration,
                    'completed_steps': self.completed_steps,
                    'failed_steps': self.failed_steps,
                    'total_logs': self.stats['total_logs'],
                    'errors': self.stats['errors'],
                    'warnings': self.stats['warnings']
                }
            )
        else:
            self.log(
                LogLevel.ERROR,
                LogCategory.CONNECTION,
                f"❌ Database initialization failed",
                details={
                    'duration': duration,
                    'completed_steps': self.completed_steps,
                    'failed_steps': self.failed_steps,
                    'total_logs': self.stats['total_logs'],
                    'errors': self.stats['errors'],
                    'warnings': self.stats['warnings']
                }
            )
    
    @contextmanager
    def step(self, step_name: str, category: LogCategory = LogCategory.CONNECTION):
        """Context manager for logging initialization steps."""
        self.start_step(step_name, category)
        step_success = True
        step_error = None
        
        try:
            yield
        except Exception as e:
            step_success = False
            step_error = e
            raise
        finally:
            self.finish_step(step_name, step_success, step_error)
    
    def start_step(self, step_name: str, category: LogCategory = LogCategory.CONNECTION):
        """Start logging a specific step."""
        self.current_step = step_name
        self.step_start_time = time.time()
        
        progress = f"({self.completed_steps + 1}/{self.total_steps})" if self.total_steps > 0 else ""
        
        self.log(
            LogLevel.INFO,
            category,
            f"📋 Starting step: {step_name} {progress}",
            step=step_name
        )
    
    def finish_step(self, step_name: str, success: bool = True, error: Optional[Exception] = None):
        """Finish logging a specific step."""
        duration = time.time() - self.step_start_time if self.step_start_time else 0
        
        if success:
            self.completed_steps += 1
            self.log(
                LogLevel.INFO,
                LogCategory.CONNECTION,
                f"✅ Completed step: {step_name}",
                details={'duration': duration},
                step=step_name,
                duration=duration
            )
        else:
            self.failed_steps += 1
            self.log(
                LogLevel.ERROR,
                LogCategory.CONNECTION,
                f"❌ Failed step: {step_name}",
                details={'duration': duration},
                step=step_name,
                duration=duration,
                error=error
            )
        
        self.current_step = None
        self.step_start_time = None
    
    def log(self, level: LogLevel, category: LogCategory, message: str, 
            details: Optional[Dict[str, Any]] = None, step: Optional[str] = None,
            duration: Optional[float] = None, error: Optional[Exception] = None):
        """Log a message with structured data."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            category=category,
            message=message,
            details=details or {},
            duration=duration,
            step=step or self.current_step,
            error=error
        )
        
        self.entries.append(entry)
        self._update_stats(entry)
        
        # Log to Python logger
        log_levels = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL
        }
        
        self.logger.log(
            log_levels[level],
            message,
            extra={
                'category': category.value,
                'details': details,
                'step': step or self.current_step,
                'duration': duration,
                'error': error
            }
        )
    
    def debug(self, category: LogCategory, message: str, **kwargs):
        """Log debug message."""
        self.log(LogLevel.DEBUG, category, message, **kwargs)
    
    def info(self, category: LogCategory, message: str, **kwargs):
        """Log info message."""
        self.log(LogLevel.INFO, category, message, **kwargs)
    
    def warning(self, category: LogCategory, message: str, **kwargs):
        """Log warning message."""
        self.log(LogLevel.WARNING, category, message, **kwargs)
    
    def error(self, category: LogCategory, message: str, **kwargs):
        """Log error message."""
        self.log(LogLevel.ERROR, category, message, **kwargs)
    
    def critical(self, category: LogCategory, message: str, **kwargs):
        """Log critical message."""
        self.log(LogLevel.CRITICAL, category, message, **kwargs)
    
    def log_connection_attempt(self, database_type: str, connection_string: str):
        """Log database connection attempt."""
        masked_string = self._mask_connection_string(connection_string)
        self.info(
            LogCategory.CONNECTION,
            f"🔌 Attempting {database_type} connection",
            details={'connection_string': masked_string, 'database_type': database_type}
        )
    
    def log_connection_success(self, database_type: str, duration: float):
        """Log successful database connection."""
        self.info(
            LogCategory.CONNECTION,
            f"✅ {database_type} connection successful",
            details={'database_type': database_type},
            duration=duration
        )
    
    def log_connection_failure(self, database_type: str, error: Exception, duration: float):
        """Log failed database connection."""
        self.error(
            LogCategory.CONNECTION,
            f"❌ {database_type} connection failed",
            details={'database_type': database_type, 'error_type': type(error).__name__},
            duration=duration,
            error=error
        )
    
    def log_schema_check(self, tables_found: int, tables_expected: int):
        """Log schema check results."""
        if tables_found == tables_expected:
            self.info(
                LogCategory.SCHEMA,
                f"✅ Schema check passed: {tables_found}/{tables_expected} tables found",
                details={'tables_found': tables_found, 'tables_expected': tables_expected}
            )
        else:
            self.warning(
                LogCategory.SCHEMA,
                f"⚠️ Schema incomplete: {tables_found}/{tables_expected} tables found",
                details={'tables_found': tables_found, 'tables_expected': tables_expected}
            )
    
    def log_migration_check(self, pending_migrations: List[str]):
        """Log migration check results."""
        if not pending_migrations:
            self.info(
                LogCategory.MIGRATION,
                "✅ No pending migrations",
                details={'pending_count': 0}
            )
        else:
            self.info(
                LogCategory.MIGRATION,
                f"📋 Found {len(pending_migrations)} pending migrations",
                details={'pending_count': len(pending_migrations), 'migrations': pending_migrations}
            )
    
    def log_seeding_result(self, table: str, created: int, skipped: int):
        """Log data seeding results."""
        self.info(
            LogCategory.SEEDING,
            f"🌱 Seeded {table}: {created} created, {skipped} skipped",
            details={'table': table, 'created': created, 'skipped': skipped}
        )
    
    def log_performance_metric(self, metric_name: str, value: float, unit: str = "ms"):
        """Log performance metric."""
        self.stats['performance_metrics'][metric_name] = {'value': value, 'unit': unit}
        self.debug(
            LogCategory.PERFORMANCE,
            f"📊 {metric_name}: {value}{unit}",
            details={'metric': metric_name, 'value': value, 'unit': unit}
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get initialization summary."""
        total_duration = time.time() - self.init_start_time if self.init_start_time else 0
        
        return {
            'total_duration': total_duration,
            'total_steps': self.total_steps,
            'completed_steps': self.completed_steps,
            'failed_steps': self.failed_steps,
            'success_rate': self.completed_steps / max(self.total_steps, 1),
            'statistics': self.stats.copy(),
            'entries_count': len(self.entries),
            'last_entry': self.entries[-1].to_dict() if self.entries else None
        }
    
    def get_entries(self, level: Optional[LogLevel] = None, 
                   category: Optional[LogCategory] = None) -> List[LogEntry]:
        """Get log entries with optional filtering."""
        entries = self.entries
        
        if level:
            entries = [e for e in entries if e.level == level]
        
        if category:
            entries = [e for e in entries if e.category == category]
        
        return entries
    
    def export_logs(self, format: str = "json") -> str:
        """Export logs in specified format."""
        if format == "json":
            import json
            return json.dumps([entry.to_dict() for entry in self.entries], indent=2)
        elif format == "csv":
            import csv
            import io
            output = io.StringIO()
            if self.entries:
                fieldnames = ['timestamp', 'level', 'category', 'message', 'step', 'duration']
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                for entry in self.entries:
                    row = {
                        'timestamp': entry.timestamp.isoformat(),
                        'level': entry.level.value,
                        'category': entry.category.value,
                        'message': entry.message,
                        'step': entry.step or '',
                        'duration': entry.duration or ''
                    }
                    writer.writerow(row)
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _update_stats(self, entry: LogEntry):
        """Update logging statistics."""
        self.stats['total_logs'] += 1
        self.stats['categories'][entry.category.value] += 1
        
        if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            self.stats['errors'] += 1
        elif entry.level == LogLevel.WARNING:
            self.stats['warnings'] += 1
    
    def _mask_connection_string(self, connection_string: str) -> str:
        """Mask sensitive information in connection string."""
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


class DatabaseInitFormatter(logging.Formatter):
    """Custom formatter for database initialization logs."""
    
    def __init__(self):
        super().__init__()
        
        # Color codes for different log levels
        self.colors = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m', # Magenta
            'RESET': '\033[0m'      # Reset
        }
        
        # Category icons
        self.category_icons = {
            'CONNECTION': '🔌',
            'SCHEMA': '🏗️',
            'MIGRATION': '🔄',
            'SEEDING': '🌱',
            'VALIDATION': '🔍',
            'REPAIR': '🔧',
            'PERFORMANCE': '📊',
            'SECURITY': '🔒'
        }
    
    def format(self, record):
        """Format log record with colors and structure."""
        # Get color for log level
        color = self.colors.get(record.levelname, '')
        reset = self.colors['RESET']
        
        # Get category icon
        category = getattr(record, 'category', 'CONNECTION')
        icon = self.category_icons.get(category, '📋')
        
        # Format timestamp
        timestamp = self.formatTime(record, '%H:%M:%S')
        
        # Format duration if available
        duration_str = ""
        if hasattr(record, 'duration') and record.duration is not None:
            duration_str = f" ({record.duration:.2f}s)"
        
        # Format step if available
        step_str = ""
        if hasattr(record, 'step') and record.step:
            step_str = f" [{record.step}]"
        
        # Build formatted message
        formatted = f"{color}{timestamp} {icon} {record.getMessage()}{duration_str}{step_str}{reset}"
        
        # Add error details if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted


# Global logger instance
_global_logger: Optional[DatabaseInitLogger] = None


def get_database_init_logger(name: str = "database_init", 
                           level: LogLevel = LogLevel.INFO) -> DatabaseInitLogger:
    """
    Get or create global database initialization logger.
    
    Args:
        name: Logger name
        level: Log level
        
    Returns:
        DatabaseInitLogger instance
    """
    global _global_logger
    
    if _global_logger is None:
        _global_logger = DatabaseInitLogger(name, level)
    
    return _global_logger


def reset_database_init_logger():
    """Reset global database initialization logger."""
    global _global_logger
    _global_logger = None