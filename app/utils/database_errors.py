"""
Database Initialization Error Handling and Recovery System

This module provides comprehensive error handling, recovery mechanisms, and user-friendly
error messages for database initialization failures.
"""
import os
import logging
import traceback
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Union
from datetime import datetime

from .exceptions import BaseAppException


class DatabaseErrorCode(Enum):
    """Specific error codes for database initialization failures."""
    
    # Connection Errors (1000-1099)
    CONNECTION_REFUSED = "DB_1001"
    CONNECTION_TIMEOUT = "DB_1002"
    AUTHENTICATION_FAILED = "DB_1003"
    INVALID_CREDENTIALS = "DB_1004"
    HOST_UNREACHABLE = "DB_1005"
    PORT_BLOCKED = "DB_1006"
    SSL_ERROR = "DB_1007"
    NETWORK_ERROR = "DB_1008"
    
    # Configuration Errors (1100-1199)
    MISSING_DATABASE_URL = "DB_1101"
    INVALID_DATABASE_URL = "DB_1102"
    UNSUPPORTED_DATABASE_TYPE = "DB_1103"
    MISSING_REQUIRED_CONFIG = "DB_1104"
    INVALID_CONFIG_VALUE = "DB_1105"
    ENVIRONMENT_MISMATCH = "DB_1106"
    
    # Schema Errors (1200-1299)
    SCHEMA_CREATION_FAILED = "DB_1201"
    TABLE_CREATION_FAILED = "DB_1202"
    INDEX_CREATION_FAILED = "DB_1203"
    CONSTRAINT_CREATION_FAILED = "DB_1204"
    SCHEMA_CORRUPTION = "DB_1205"
    SCHEMA_VERSION_MISMATCH = "DB_1206"
    PERMISSION_DENIED = "DB_1207"
    
    # Migration Errors (1300-1399)
    MIGRATION_FAILED = "DB_1301"
    MIGRATION_ROLLBACK_FAILED = "DB_1302"
    MIGRATION_FILE_CORRUPT = "DB_1303"
    MIGRATION_VERSION_CONFLICT = "DB_1304"
    MIGRATION_DEPENDENCY_MISSING = "DB_1305"
    MIGRATION_TIMEOUT = "DB_1306"
    
    # Data Seeding Errors (1400-1499)
    SEEDING_FAILED = "DB_1401"
    ADMIN_USER_CREATION_FAILED = "DB_1402"
    SYSTEM_DATA_CREATION_FAILED = "DB_1403"
    DATA_VALIDATION_FAILED = "DB_1404"
    DUPLICATE_DATA_CONFLICT = "DB_1405"
    
    # Health Validation Errors (1500-1599)
    HEALTH_CHECK_FAILED = "DB_1501"
    DATA_INTEGRITY_FAILED = "DB_1502"
    PERFORMANCE_DEGRADED = "DB_1503"
    STORAGE_FULL = "DB_1504"
    BACKUP_FAILED = "DB_1505"
    
    # File System Errors (1600-1699)
    DATABASE_FILE_NOT_FOUND = "DB_1601"
    DATABASE_FILE_LOCKED = "DB_1602"
    INSUFFICIENT_DISK_SPACE = "DB_1603"
    FILE_PERMISSION_DENIED = "DB_1604"
    DIRECTORY_NOT_WRITABLE = "DB_1605"
    
    # Recovery Errors (1700-1799)
    RECOVERY_FAILED = "DB_1701"
    BACKUP_RESTORE_FAILED = "DB_1702"
    REPAIR_FAILED = "DB_1703"
    MANUAL_INTERVENTION_REQUIRED = "DB_1704"
    
    # Generic Errors (1900-1999)
    UNKNOWN_ERROR = "DB_1901"
    INITIALIZATION_TIMEOUT = "DB_1902"
    RESOURCE_EXHAUSTED = "DB_1903"
    DEPENDENCY_MISSING = "DB_1904"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryAction(Enum):
    """Available recovery actions."""
    RETRY = "retry"
    REPAIR = "repair"
    RECREATE = "recreate"
    MANUAL = "manual"
    SKIP = "skip"
    ABORT = "abort"


@dataclass
class ErrorContext:
    """Context information for database errors."""
    database_type: Optional[str] = None
    connection_string: Optional[str] = None
    operation: Optional[str] = None
    table_name: Optional[str] = None
    migration_id: Optional[str] = None
    file_path: Optional[str] = None
    environment: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    stack_trace: Optional[str] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryStep:
    """A single recovery step."""
    action: RecoveryAction
    description: str
    command: Optional[str] = None
    automated: bool = False
    risk_level: str = "low"  # low, medium, high
    estimated_time: Optional[str] = None
    prerequisites: List[str] = field(default_factory=list)


@dataclass
class ErrorResolution:
    """Complete error resolution information."""
    error_code: DatabaseErrorCode
    title: str
    description: str
    severity: ErrorSeverity
    recovery_steps: List[RecoveryStep] = field(default_factory=list)
    prevention_tips: List[str] = field(default_factory=list)
    related_docs: List[str] = field(default_factory=list)
    contact_support: bool = False


class DatabaseInitializationError(BaseAppException):
    """Base exception for database initialization errors."""
    
    def __init__(
        self,
        message: str,
        error_code: DatabaseErrorCode,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        recovery_suggestions: Optional[List[str]] = None
    ):
        self.db_error_code = error_code  # Store the enum separately
        self.context = context or ErrorContext()
        self.original_error = original_error
        self.recovery_suggestions = recovery_suggestions or []
        
        # Capture stack trace if not provided
        if not self.context.stack_trace and original_error:
            self.context.stack_trace = traceback.format_exception(
                type(original_error), original_error, original_error.__traceback__
            )
        
        super().__init__(message, error_code.value)
        # Override the string error_code with our enum after parent init
        self.error_code = error_code


class DatabaseConnectionError(DatabaseInitializationError):
    """Database connection related errors."""
    pass


class DatabaseSchemaError(DatabaseInitializationError):
    """Database schema related errors."""
    pass


class DatabaseMigrationError(DatabaseInitializationError):
    """Database migration related errors."""
    pass


class DatabaseSeedingError(DatabaseInitializationError):
    """Database seeding related errors."""
    pass


class DatabaseHealthError(DatabaseInitializationError):
    """Database health validation errors."""
    pass


class DatabaseRecoveryError(DatabaseInitializationError):
    """Database recovery operation errors."""
    pass


class DatabaseErrorHandler:
    """
    Comprehensive error handler for database initialization.
    
    Provides error classification, user-friendly messages, recovery suggestions,
    and automated recovery mechanisms.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._error_resolutions = self._initialize_error_resolutions()
        self._recovery_handlers: Dict[DatabaseErrorCode, Callable] = {}
        self._error_history: List[Dict[str, Any]] = []
    
    def handle_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        auto_recover: bool = True
    ) -> Dict[str, Any]:
        """
        Handle a database initialization error.
        
        Args:
            error: The original exception
            context: Error context information
            auto_recover: Whether to attempt automatic recovery
            
        Returns:
            Dictionary with error details and recovery information
        """
        # Classify the error
        error_code, db_error = self._classify_error(error, context)
        
        # Get error resolution information
        resolution = self._get_error_resolution(error_code)
        
        # Log the error
        self._log_error(db_error, resolution)
        
        # Record error in history
        error_record = {
            'timestamp': datetime.now().isoformat(),
            'error_code': error_code.value,
            'message': str(error),
            'context': context.__dict__ if context else {},
            'severity': resolution.severity.value,
            'auto_recovery_attempted': auto_recover
        }
        self._error_history.append(error_record)
        
        # Attempt automatic recovery if enabled
        recovery_result = None
        if auto_recover and error_code in self._recovery_handlers:
            try:
                recovery_result = self._attempt_recovery(error_code, db_error, context)
                error_record['recovery_result'] = recovery_result
            except Exception as recovery_error:
                self.logger.error(f"Recovery attempt failed: {recovery_error}")
                error_record['recovery_error'] = str(recovery_error)
        
        return {
            'error_code': error_code.value,
            'error_type': type(db_error).__name__,
            'message': str(db_error),
            'severity': resolution.severity.value,
            'resolution': {
                'title': resolution.title,
                'description': resolution.description,
                'recovery_steps': [
                    {
                        'action': step.action.value,
                        'description': step.description,
                        'command': step.command,
                        'automated': step.automated,
                        'risk_level': step.risk_level,
                        'estimated_time': step.estimated_time,
                        'prerequisites': step.prerequisites
                    }
                    for step in resolution.recovery_steps
                ],
                'prevention_tips': resolution.prevention_tips,
                'related_docs': resolution.related_docs,
                'contact_support': resolution.contact_support
            },
            'context': context.__dict__ if context else {},
            'recovery_result': recovery_result,
            'timestamp': datetime.now().isoformat()
        }
    
    def _classify_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None
    ) -> tuple[DatabaseErrorCode, DatabaseInitializationError]:
        """
        Classify an error and return appropriate error code and database error.
        
        Args:
            error: Original exception
            context: Error context
            
        Returns:
            Tuple of (error_code, database_error)
        """
        error_msg = str(error).lower()
        
        # Connection errors
        if any(keyword in error_msg for keyword in ['connection refused', 'could not connect']):
            return DatabaseErrorCode.CONNECTION_REFUSED, DatabaseConnectionError(
                "Database connection was refused. The database server may not be running.",
                DatabaseErrorCode.CONNECTION_REFUSED,
                context,
                error
            )
        
        if any(keyword in error_msg for keyword in ['timeout', 'timed out']):
            return DatabaseErrorCode.CONNECTION_TIMEOUT, DatabaseConnectionError(
                "Database connection timed out. The server may be overloaded or unreachable.",
                DatabaseErrorCode.CONNECTION_TIMEOUT,
                context,
                error
            )
        
        if any(keyword in error_msg for keyword in ['authentication failed', 'access denied', 'login failed']):
            return DatabaseErrorCode.AUTHENTICATION_FAILED, DatabaseConnectionError(
                "Database authentication failed. Please check your credentials.",
                DatabaseErrorCode.AUTHENTICATION_FAILED,
                context,
                error
            )
        
        if any(keyword in error_msg for keyword in ['host unreachable', 'name resolution failed']):
            return DatabaseErrorCode.HOST_UNREACHABLE, DatabaseConnectionError(
                "Database host is unreachable. Please check the hostname and network connectivity.",
                DatabaseErrorCode.HOST_UNREACHABLE,
                context,
                error
            )
        
        # Configuration errors
        if 'database_url' in error_msg or 'sqlalchemy_database_uri' in error_msg:
            return DatabaseErrorCode.MISSING_DATABASE_URL, DatabaseInitializationError(
                "Database URL is not configured. Please set DATABASE_URL environment variable.",
                DatabaseErrorCode.MISSING_DATABASE_URL,
                context,
                error
            )
        
        # Schema errors
        if any(keyword in error_msg for keyword in ['no such table', 'table does not exist']):
            return DatabaseErrorCode.SCHEMA_CREATION_FAILED, DatabaseSchemaError(
                "Required database tables are missing. Schema initialization failed.",
                DatabaseErrorCode.SCHEMA_CREATION_FAILED,
                context,
                error
            )
        
        if any(keyword in error_msg for keyword in ['permission denied', 'access is denied']):
            return DatabaseErrorCode.PERMISSION_DENIED, DatabaseSchemaError(
                "Insufficient permissions to create database schema.",
                DatabaseErrorCode.PERMISSION_DENIED,
                context,
                error
            )
        
        # File system errors (SQLite specific)
        if any(keyword in error_msg for keyword in ['no such file', 'file not found']):
            return DatabaseErrorCode.DATABASE_FILE_NOT_FOUND, DatabaseInitializationError(
                "SQLite database file not found and could not be created.",
                DatabaseErrorCode.DATABASE_FILE_NOT_FOUND,
                context,
                error
            )
        
        if any(keyword in error_msg for keyword in ['database is locked', 'file is locked']):
            return DatabaseErrorCode.DATABASE_FILE_LOCKED, DatabaseInitializationError(
                "SQLite database file is locked by another process.",
                DatabaseErrorCode.DATABASE_FILE_LOCKED,
                context,
                error
            )
        
        if any(keyword in error_msg for keyword in ['disk full', 'no space left']):
            return DatabaseErrorCode.INSUFFICIENT_DISK_SPACE, DatabaseInitializationError(
                "Insufficient disk space to create or modify database.",
                DatabaseErrorCode.INSUFFICIENT_DISK_SPACE,
                context,
                error
            )
        
        # Migration errors
        if 'migration' in error_msg:
            return DatabaseErrorCode.MIGRATION_FAILED, DatabaseMigrationError(
                "Database migration failed during initialization.",
                DatabaseErrorCode.MIGRATION_FAILED,
                context,
                error
            )
        
        # Seeding errors
        if any(keyword in error_msg for keyword in ['admin user', 'seeding', 'initial data']):
            return DatabaseErrorCode.SEEDING_FAILED, DatabaseSeedingError(
                "Failed to seed initial data during database initialization.",
                DatabaseErrorCode.SEEDING_FAILED,
                context,
                error
            )
        
        # Default to unknown error
        return DatabaseErrorCode.UNKNOWN_ERROR, DatabaseInitializationError(
            f"An unknown database initialization error occurred: {str(error)}",
            DatabaseErrorCode.UNKNOWN_ERROR,
            context,
            error
        )
    
    def _get_error_resolution(self, error_code: DatabaseErrorCode) -> ErrorResolution:
        """Get error resolution information for a specific error code."""
        return self._error_resolutions.get(error_code, self._get_default_resolution(error_code))
    
    def _get_default_resolution(self, error_code: DatabaseErrorCode) -> ErrorResolution:
        """Get default resolution for unknown error codes."""
        return ErrorResolution(
            error_code=error_code,
            title="Unknown Database Error",
            description="An unknown database error occurred during initialization.",
            severity=ErrorSeverity.HIGH,
            recovery_steps=[
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Check application logs for detailed error information",
                    automated=False
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Contact system administrator or support team",
                    automated=False
                )
            ],
            contact_support=True
        )
    
    def _log_error(self, error: DatabaseInitializationError, resolution: ErrorResolution):
        """Log error with appropriate severity level."""
        log_level = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }.get(resolution.severity, logging.ERROR)
        
        self.logger.log(
            log_level,
            f"Database initialization error [{error.error_code.value}]: {str(error)}",
            extra={
                'error_code': error.error_code.value,
                'severity': resolution.severity.value,
                'context': error.context.__dict__ if error.context else {},
                'original_error': str(error.original_error) if error.original_error else None
            }
        )
    
    def _attempt_recovery(
        self,
        error_code: DatabaseErrorCode,
        error: DatabaseInitializationError,
        context: Optional[ErrorContext]
    ) -> Dict[str, Any]:
        """Attempt automatic recovery for the given error."""
        if error_code not in self._recovery_handlers:
            return {'success': False, 'reason': 'No recovery handler available'}
        
        try:
            handler = self._recovery_handlers[error_code]
            return handler(error, context)
        except Exception as recovery_error:
            return {
                'success': False,
                'reason': f'Recovery handler failed: {str(recovery_error)}'
            }
    
    def register_recovery_handler(
        self,
        error_code: DatabaseErrorCode,
        handler: Callable[[DatabaseInitializationError, Optional[ErrorContext]], Dict[str, Any]]
    ):
        """Register a recovery handler for a specific error code."""
        self._recovery_handlers[error_code] = handler
        self.logger.info(f"Registered recovery handler for {error_code.value}")
    
    def get_error_history(self) -> List[Dict[str, Any]]:
        """Get the history of handled errors."""
        return self._error_history.copy()
    
    def clear_error_history(self):
        """Clear the error history."""
        self._error_history.clear()
        self.logger.info("Error history cleared")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get statistics about handled errors."""
        if not self._error_history:
            return {'total_errors': 0}
        
        error_counts = {}
        severity_counts = {}
        recovery_success_count = 0
        
        for error_record in self._error_history:
            error_code = error_record['error_code']
            severity = error_record['severity']
            
            error_counts[error_code] = error_counts.get(error_code, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            if error_record.get('recovery_result', {}).get('success'):
                recovery_success_count += 1
        
        return {
            'total_errors': len(self._error_history),
            'error_counts': error_counts,
            'severity_counts': severity_counts,
            'recovery_success_rate': recovery_success_count / len(self._error_history) if self._error_history else 0,
            'most_common_error': max(error_counts.items(), key=lambda x: x[1])[0] if error_counts else None
        }   
 
    def _initialize_error_resolutions(self) -> Dict[DatabaseErrorCode, ErrorResolution]:
        """Initialize comprehensive error resolutions for all error codes."""
        resolutions = {}
        
        # Connection Errors
        resolutions[DatabaseErrorCode.CONNECTION_REFUSED] = ErrorResolution(
            error_code=DatabaseErrorCode.CONNECTION_REFUSED,
            title="Database Connection Refused",
            description="The database server refused the connection. This usually means the database server is not running or is not accepting connections.",
            severity=ErrorSeverity.CRITICAL,
            recovery_steps=[
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Check if the database server is running",
                    command="systemctl status postgresql" if os.name != 'nt' else "sc query postgresql",
                    automated=False,
                    risk_level="low",
                    estimated_time="2-5 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Start the database server if it's not running",
                    command="systemctl start postgresql" if os.name != 'nt' else "sc start postgresql",
                    automated=False,
                    risk_level="low",
                    estimated_time="1-2 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Check database server configuration and port settings",
                    automated=False,
                    risk_level="low",
                    estimated_time="5-10 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.RETRY,
                    description="Retry database connection after server is running",
                    automated=True,
                    risk_level="low",
                    estimated_time="30 seconds"
                )
            ],
            prevention_tips=[
                "Set up database server monitoring to detect when it goes down",
                "Configure database server to start automatically on system boot",
                "Use connection pooling with retry logic for transient failures"
            ],
            related_docs=[
                "Database Server Installation Guide",
                "Connection Configuration Documentation"
            ]
        )
        
        resolutions[DatabaseErrorCode.CONNECTION_TIMEOUT] = ErrorResolution(
            error_code=DatabaseErrorCode.CONNECTION_TIMEOUT,
            title="Database Connection Timeout",
            description="The connection to the database server timed out. This may indicate network issues or server overload.",
            severity=ErrorSeverity.HIGH,
            recovery_steps=[
                RecoveryStep(
                    action=RecoveryAction.RETRY,
                    description="Retry connection with longer timeout",
                    automated=True,
                    risk_level="low",
                    estimated_time="1-2 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Check network connectivity to database server",
                    command="ping <database_host>",
                    automated=False,
                    risk_level="low",
                    estimated_time="2-3 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Check database server load and performance",
                    automated=False,
                    risk_level="low",
                    estimated_time="5-10 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Increase connection timeout in configuration",
                    automated=False,
                    risk_level="low",
                    estimated_time="2-3 minutes"
                )
            ],
            prevention_tips=[
                "Configure appropriate connection timeouts for your environment",
                "Monitor database server performance and resource usage",
                "Use connection pooling to manage database connections efficiently"
            ]
        )
        
        resolutions[DatabaseErrorCode.AUTHENTICATION_FAILED] = ErrorResolution(
            error_code=DatabaseErrorCode.AUTHENTICATION_FAILED,
            title="Database Authentication Failed",
            description="Authentication to the database failed. This indicates incorrect credentials or authentication configuration issues.",
            severity=ErrorSeverity.CRITICAL,
            recovery_steps=[
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Verify database username and password in configuration",
                    automated=False,
                    risk_level="low",
                    estimated_time="2-3 minutes",
                    prerequisites=["Access to configuration files or environment variables"]
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Check if database user exists and has proper permissions",
                    command="psql -U postgres -c \"\\du\"",
                    automated=False,
                    risk_level="low",
                    estimated_time="3-5 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Reset database user password if necessary",
                    automated=False,
                    risk_level="medium",
                    estimated_time="5-10 minutes",
                    prerequisites=["Database administrator access"]
                ),
                RecoveryStep(
                    action=RecoveryAction.RETRY,
                    description="Retry connection with corrected credentials",
                    automated=True,
                    risk_level="low",
                    estimated_time="30 seconds"
                )
            ],
            prevention_tips=[
                "Use environment variables for database credentials",
                "Implement credential rotation policies",
                "Test database connections in staging before production deployment"
            ]
        )
        
        # Configuration Errors
        resolutions[DatabaseErrorCode.MISSING_DATABASE_URL] = ErrorResolution(
            error_code=DatabaseErrorCode.MISSING_DATABASE_URL,
            title="Missing Database URL Configuration",
            description="The database URL is not configured. The application cannot connect to the database without this configuration.",
            severity=ErrorSeverity.CRITICAL,
            recovery_steps=[
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Set DATABASE_URL environment variable",
                    command="export DATABASE_URL='postgresql://user:password@host:port/database'",
                    automated=False,
                    risk_level="low",
                    estimated_time="2-3 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Or set SQLALCHEMY_DATABASE_URI in Flask configuration",
                    automated=False,
                    risk_level="low",
                    estimated_time="2-3 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="For SQLite, ensure database file path is accessible",
                    command="touch /path/to/database.db && chmod 664 /path/to/database.db",
                    automated=False,
                    risk_level="low",
                    estimated_time="1-2 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.RETRY,
                    description="Restart application with proper configuration",
                    automated=False,
                    risk_level="low",
                    estimated_time="1-2 minutes"
                )
            ],
            prevention_tips=[
                "Use configuration templates with required environment variables",
                "Implement configuration validation on application startup",
                "Document all required environment variables"
            ]
        )
        
        # Schema Errors
        resolutions[DatabaseErrorCode.SCHEMA_CREATION_FAILED] = ErrorResolution(
            error_code=DatabaseErrorCode.SCHEMA_CREATION_FAILED,
            title="Database Schema Creation Failed",
            description="Failed to create required database tables and schema. This prevents the application from functioning properly.",
            severity=ErrorSeverity.CRITICAL,
            recovery_steps=[
                RecoveryStep(
                    action=RecoveryAction.REPAIR,
                    description="Attempt automatic schema creation",
                    automated=True,
                    risk_level="low",
                    estimated_time="2-5 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Check database user permissions for DDL operations",
                    automated=False,
                    risk_level="low",
                    estimated_time="3-5 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Manually run database initialization script",
                    command="python init_database.py",
                    automated=False,
                    risk_level="medium",
                    estimated_time="5-10 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.RECREATE,
                    description="Drop and recreate database (development only)",
                    automated=False,
                    risk_level="high",
                    estimated_time="10-15 minutes",
                    prerequisites=["Development environment", "Data backup if needed"]
                )
            ],
            prevention_tips=[
                "Ensure database user has CREATE, ALTER, and DROP permissions",
                "Test schema creation in development environment first",
                "Use database migration tools for schema changes"
            ]
        )
        
        resolutions[DatabaseErrorCode.PERMISSION_DENIED] = ErrorResolution(
            error_code=DatabaseErrorCode.PERMISSION_DENIED,
            title="Database Permission Denied",
            description="The database user does not have sufficient permissions to perform the required operations.",
            severity=ErrorSeverity.HIGH,
            recovery_steps=[
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Grant necessary permissions to database user",
                    command="GRANT CREATE, ALTER, DROP, SELECT, INSERT, UPDATE, DELETE ON DATABASE dbname TO username;",
                    automated=False,
                    risk_level="medium",
                    estimated_time="5-10 minutes",
                    prerequisites=["Database administrator access"]
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="For SQLite, check file and directory permissions",
                    command="chmod 664 database.db && chmod 755 /path/to/database/directory",
                    automated=False,
                    risk_level="low",
                    estimated_time="2-3 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.RETRY,
                    description="Retry initialization after permission fix",
                    automated=True,
                    risk_level="low",
                    estimated_time="1-2 minutes"
                )
            ],
            prevention_tips=[
                "Use principle of least privilege for database users",
                "Document required permissions for each environment",
                "Test permissions in staging environment"
            ]
        )
        
        # File System Errors (SQLite)
        resolutions[DatabaseErrorCode.DATABASE_FILE_LOCKED] = ErrorResolution(
            error_code=DatabaseErrorCode.DATABASE_FILE_LOCKED,
            title="SQLite Database File Locked",
            description="The SQLite database file is locked by another process, preventing access.",
            severity=ErrorSeverity.HIGH,
            recovery_steps=[
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Check for other processes using the database file",
                    command="lsof database.db" if os.name != 'nt' else "handle database.db",
                    automated=False,
                    risk_level="low",
                    estimated_time="2-3 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Stop other processes accessing the database",
                    automated=False,
                    risk_level="medium",
                    estimated_time="5-10 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Remove lock files if they exist",
                    command="rm -f database.db-shm database.db-wal",
                    automated=False,
                    risk_level="medium",
                    estimated_time="1-2 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.RETRY,
                    description="Retry database access",
                    automated=True,
                    risk_level="low",
                    estimated_time="30 seconds"
                )
            ],
            prevention_tips=[
                "Use connection pooling to manage SQLite connections",
                "Implement proper connection cleanup in application code",
                "Consider using WAL mode for better concurrency"
            ]
        )
        
        resolutions[DatabaseErrorCode.INSUFFICIENT_DISK_SPACE] = ErrorResolution(
            error_code=DatabaseErrorCode.INSUFFICIENT_DISK_SPACE,
            title="Insufficient Disk Space",
            description="There is not enough disk space to create or modify the database.",
            severity=ErrorSeverity.CRITICAL,
            recovery_steps=[
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Check available disk space",
                    command="df -h" if os.name != 'nt' else "dir",
                    automated=False,
                    risk_level="low",
                    estimated_time="1-2 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Free up disk space by removing unnecessary files",
                    automated=False,
                    risk_level="medium",
                    estimated_time="10-30 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Move database to a location with more space",
                    automated=False,
                    risk_level="high",
                    estimated_time="15-30 minutes",
                    prerequisites=["Database backup", "Application downtime"]
                ),
                RecoveryStep(
                    action=RecoveryAction.RETRY,
                    description="Retry initialization after freeing space",
                    automated=True,
                    risk_level="low",
                    estimated_time="2-5 minutes"
                )
            ],
            prevention_tips=[
                "Monitor disk space usage regularly",
                "Set up disk space alerts",
                "Implement database cleanup and archiving policies"
            ],
            contact_support=True
        )
        
        # Migration Errors
        resolutions[DatabaseErrorCode.MIGRATION_FAILED] = ErrorResolution(
            error_code=DatabaseErrorCode.MIGRATION_FAILED,
            title="Database Migration Failed",
            description="A database migration failed during initialization, which may leave the database in an inconsistent state.",
            severity=ErrorSeverity.HIGH,
            recovery_steps=[
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Check migration logs for specific error details",
                    automated=False,
                    risk_level="low",
                    estimated_time="3-5 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.REPAIR,
                    description="Attempt to rollback failed migration",
                    automated=True,
                    risk_level="medium",
                    estimated_time="5-10 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Manually fix data issues preventing migration",
                    automated=False,
                    risk_level="high",
                    estimated_time="30-60 minutes",
                    prerequisites=["Database expertise", "Data backup"]
                ),
                RecoveryStep(
                    action=RecoveryAction.RETRY,
                    description="Retry migration after fixing issues",
                    automated=True,
                    risk_level="medium",
                    estimated_time="5-15 minutes"
                )
            ],
            prevention_tips=[
                "Test migrations thoroughly in development environment",
                "Always backup database before running migrations",
                "Use migration tools with rollback capabilities"
            ]
        )
        
        # Seeding Errors
        resolutions[DatabaseErrorCode.ADMIN_USER_CREATION_FAILED] = ErrorResolution(
            error_code=DatabaseErrorCode.ADMIN_USER_CREATION_FAILED,
            title="Admin User Creation Failed",
            description="Failed to create the default admin user during database initialization.",
            severity=ErrorSeverity.HIGH,
            recovery_steps=[
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Check if admin user already exists",
                    automated=False,
                    risk_level="low",
                    estimated_time="2-3 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.REPAIR,
                    description="Attempt to create admin user manually",
                    command="python create_admin_user.py",
                    automated=True,
                    risk_level="low",
                    estimated_time="2-5 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Verify user table schema and constraints",
                    automated=False,
                    risk_level="low",
                    estimated_time="5-10 minutes"
                ),
                RecoveryStep(
                    action=RecoveryAction.MANUAL,
                    description="Create admin user through application interface after startup",
                    automated=False,
                    risk_level="low",
                    estimated_time="5-10 minutes"
                )
            ],
            prevention_tips=[
                "Validate user data before attempting to create admin user",
                "Check for unique constraint violations",
                "Use idempotent seeding scripts"
            ]
        )
        
        return resolutions


# Global error handler instance
_error_handler = None


def get_database_error_handler() -> DatabaseErrorHandler:
    """Get the global database error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = DatabaseErrorHandler()
    return _error_handler


def handle_database_error(
    error: Exception,
    context: Optional[ErrorContext] = None,
    auto_recover: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to handle database errors.
    
    Args:
        error: The original exception
        context: Error context information
        auto_recover: Whether to attempt automatic recovery
        
    Returns:
        Dictionary with error details and recovery information
    """
    handler = get_database_error_handler()
    return handler.handle_error(error, context, auto_recover)


def create_error_context(
    database_type: Optional[str] = None,
    connection_string: Optional[str] = None,
    operation: Optional[str] = None,
    **kwargs
) -> ErrorContext:
    """
    Create an error context with the provided information.
    
    Args:
        database_type: Type of database (postgresql, sqlite, etc.)
        connection_string: Database connection string
        operation: Operation being performed when error occurred
        **kwargs: Additional context information
        
    Returns:
        ErrorContext instance
    """
    context = ErrorContext(
        database_type=database_type,
        connection_string=connection_string,
        operation=operation
    )
    
    # Add additional context information
    for key, value in kwargs.items():
        context.additional_info[key] = value
    
    return context