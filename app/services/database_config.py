"""
Database Configuration Models

This module provides data models for database configuration, connection results,
and validation. These models support the intelligent database connection system
with proper type safety and validation.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, Union
from datetime import datetime


class DatabaseType(Enum):
    """Enumeration of supported database types."""
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    UNKNOWN = "unknown"


class ValidationResult(Enum):
    """Enumeration of validation results."""
    VALID = "valid"
    INVALID_FORMAT = "invalid_format"
    INVALID_SCHEME = "invalid_scheme"
    MISSING_COMPONENTS = "missing_components"
    CONNECTION_FAILED = "connection_failed"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class DatabaseConfig:
    """
    Configuration for database connections with validation.
    
    This dataclass holds all necessary information for establishing
    a database connection, including validation status and error details.
    """
    type: DatabaseType
    connection_string: str
    driver: str
    options: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    error_message: Optional[str] = None
    validation_result: ValidationResult = ValidationResult.VALID
    
    # Connection details extracted from URL
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    
    # Additional metadata
    created_at: datetime = field(default_factory=datetime.now)
    validated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        if not self.is_valid and not self.error_message:
            self.error_message = "Configuration marked as invalid without error message"
        
        # Set default options based on database type
        if not self.options:
            self.options = self._get_default_options()
    
    def _get_default_options(self) -> Dict[str, Any]:
        """Get default options based on database type."""
        if self.type == DatabaseType.POSTGRESQL:
            return {
                'pool_pre_ping': True,
                'pool_timeout': 10,
                'connect_args': {'connect_timeout': 10}
            }
        elif self.type == DatabaseType.SQLITE:
            return {
                'pool_pre_ping': True,
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': 10
                }
            }
        else:
            return {}
    
    def mask_password(self) -> str:
        """
        Return connection string with masked password for logging.
        
        Returns:
            Connection string with password replaced by asterisks
        """
        if not self.password or not self.connection_string:
            return self.connection_string
        
        return self.connection_string.replace(self.password, '*' * len(self.password))
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dictionary representation with masked password
        """
        return {
            'type': self.type.value,
            'connection_string': self.mask_password(),
            'driver': self.driver,
            'options': self.options,
            'is_valid': self.is_valid,
            'error_message': self.error_message,
            'validation_result': self.validation_result.value,
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'username': self.username,
            'has_password': bool(self.password),
            'created_at': self.created_at.isoformat(),
            'validated_at': self.validated_at.isoformat() if self.validated_at else None
        }
    
    def is_postgresql(self) -> bool:
        """Check if this is a PostgreSQL configuration."""
        return self.type == DatabaseType.POSTGRESQL
    
    def is_sqlite(self) -> bool:
        """Check if this is a SQLite configuration."""
        return self.type == DatabaseType.SQLITE
    
    def is_unknown(self) -> bool:
        """Check if this is an unknown database type."""
        return self.type == DatabaseType.UNKNOWN


@dataclass
class ConnectionResult:
    """
    Result of a database connection attempt.
    
    This dataclass holds the outcome of attempting to establish
    a database connection, including success status, timing,
    and error information.
    """
    success: bool
    database_type: DatabaseType
    connection_string: str
    engine: Optional[Any] = None  # SQLAlchemy Engine
    error_message: Optional[str] = None
    fallback_used: bool = False
    connection_time: Optional[float] = None
    attempt_count: int = 1
    
    # Timing information
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Post-initialization setup."""
        if self.completed_at is None:
            self.completed_at = datetime.now()
        
        # Calculate connection time if not provided
        if self.connection_time is None and self.completed_at:
            self.connection_time = (self.completed_at - self.started_at).total_seconds()
    
    def mask_connection_string(self) -> str:
        """
        Return connection string with masked password for logging.
        
        Returns:
            Connection string with password replaced by asterisks
        """
        if '://' in self.connection_string and '@' in self.connection_string:
            # Extract and mask password
            parts = self.connection_string.split('://', 1)
            if len(parts) == 2:
                protocol = parts[0]
                rest = parts[1]
                
                if '@' in rest:
                    auth_part, host_part = rest.split('@', 1)
                    if ':' in auth_part:
                        username, password = auth_part.split(':', 1)
                        masked_auth = f"{username}:{'*' * len(password)}"
                        return f"{protocol}://{masked_auth}@{host_part}"
        
        return self.connection_string
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert connection result to dictionary.
        
        Returns:
            Dictionary representation with masked connection string
        """
        return {
            'success': self.success,
            'database_type': self.database_type.value,
            'connection_string': self.mask_connection_string(),
            'has_engine': self.engine is not None,
            'error_message': self.error_message,
            'fallback_used': self.fallback_used,
            'connection_time': self.connection_time,
            'attempt_count': self.attempt_count,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
    
    def is_successful(self) -> bool:
        """Check if connection was successful."""
        return self.success and self.engine is not None
    
    def is_fallback(self) -> bool:
        """Check if fallback was used."""
        return self.fallback_used
    
    def get_duration(self) -> float:
        """Get connection duration in seconds."""
        return self.connection_time or 0.0


@dataclass
class ValidationError:
    """
    Detailed validation error information.
    
    This dataclass provides structured error information
    for database URL validation failures.
    """
    result: ValidationResult
    message: str
    suggestion: Optional[str] = None
    url_component: Optional[str] = None
    expected_format: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert validation error to dictionary."""
        return {
            'result': self.result.value,
            'message': self.message,
            'suggestion': self.suggestion,
            'url_component': self.url_component,
            'expected_format': self.expected_format
        }
    
    def __str__(self) -> str:
        """String representation of validation error."""
        msg = f"{self.result.value}: {self.message}"
        if self.suggestion:
            msg += f" Suggestion: {self.suggestion}"
        return msg


# Type aliases for better code readability
DatabaseURL = Union[str, None]
ConnectionEngine = Optional[Any]  # SQLAlchemy Engine type
ConfigDict = Dict[str, Any]