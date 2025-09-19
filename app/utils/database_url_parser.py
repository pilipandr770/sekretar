"""
Database URL Parser and Configuration System

This module provides intelligent database URL parsing and configuration
for automatic database type detection and connection management.
"""
import os
import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs


logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    """Supported database types."""
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    UNKNOWN = "unknown"


@dataclass
class DatabaseConfig:
    """Database configuration with validation and error handling."""
    type: DatabaseType
    connection_string: str
    driver: str
    options: Dict[str, Any]
    is_valid: bool
    error_message: Optional[str] = None
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.connection_string:
            self.is_valid = False
            self.error_message = "Connection string cannot be empty"
        elif self.type == DatabaseType.UNKNOWN:
            self.is_valid = False
            self.error_message = "Unknown database type"


@dataclass
class ConnectionResult:
    """Result of a database connection attempt."""
    success: bool
    database_type: DatabaseType
    connection_string: str
    engine: Optional[Any] = None
    error_message: Optional[str] = None
    fallback_used: bool = False


@dataclass
class ValidationResult:
    """Result of URL validation."""
    is_valid: bool
    error_message: Optional[str] = None
    warnings: list = None
    
    def __post_init__(self):
        """Initialize warnings list if not provided."""
        if self.warnings is None:
            self.warnings = []


class DatabaseURLParser:
    """
    Intelligent database URL parser that detects database types
    and provides proper configuration for connection management.
    """
    
    # URL patterns for different database types
    POSTGRESQL_PATTERNS = [
        r'^postgresql://',
        r'^postgres://',
        r'^psycopg2://',
    ]
    
    SQLITE_PATTERNS = [
        r'^sqlite://',
        r'^sqlite3://',
    ]
    
    def __init__(self):
        """Initialize the URL parser."""
        self.postgresql_regex = re.compile('|'.join(self.POSTGRESQL_PATTERNS), re.IGNORECASE)
        self.sqlite_regex = re.compile('|'.join(self.SQLITE_PATTERNS), re.IGNORECASE)
    
    def parse_url(self, url: str) -> DatabaseConfig:
        """
        Parse database URL and return configuration.
        
        Args:
            url: Database URL to parse
            
        Returns:
            DatabaseConfig with parsed information
        """
        if not url or not url.strip():
            return DatabaseConfig(
                type=DatabaseType.UNKNOWN,
                connection_string="",
                driver="",
                options={},
                is_valid=False,
                error_message="Empty or None URL provided"
            )
        
        url = url.strip()
        db_type = self.detect_database_type(url)
        
        try:
            if db_type == DatabaseType.POSTGRESQL:
                return self._parse_postgresql_url(url)
            elif db_type == DatabaseType.SQLITE:
                return self._parse_sqlite_url(url)
            else:
                return DatabaseConfig(
                    type=DatabaseType.UNKNOWN,
                    connection_string=url,
                    driver="",
                    options={},
                    is_valid=False,
                    error_message=f"Unsupported database URL format: {url[:50]}..."
                )
        
        except Exception as e:
            logger.error(f"Error parsing database URL: {e}")
            return DatabaseConfig(
                type=DatabaseType.UNKNOWN,
                connection_string=url,
                driver="",
                options={},
                is_valid=False,
                error_message=f"Failed to parse URL: {str(e)}"
            )
    
    def detect_database_type(self, url: str) -> DatabaseType:
        """
        Detect database type from URL scheme.
        
        Args:
            url: Database URL to analyze
            
        Returns:
            DatabaseType enum value
        """
        if not url:
            return DatabaseType.UNKNOWN
        
        url = url.strip().lower()
        
        if self.postgresql_regex.match(url):
            return DatabaseType.POSTGRESQL
        elif self.sqlite_regex.match(url):
            return DatabaseType.SQLITE
        else:
            return DatabaseType.UNKNOWN
    
    def validate_url(self, url: str) -> ValidationResult:
        """
        Validate URL format and accessibility.
        
        Args:
            url: Database URL to validate
            
        Returns:
            ValidationResult with validation details
        """
        if not url or not url.strip():
            return ValidationResult(
                is_valid=False,
                error_message="URL cannot be empty"
            )
        
        url = url.strip()
        warnings = []
        
        try:
            parsed = urlparse(url)
            
            if not parsed.scheme:
                return ValidationResult(
                    is_valid=False,
                    error_message="URL must include a scheme (e.g., postgresql://, sqlite://)"
                )
            
            db_type = self.detect_database_type(url)
            
            if db_type == DatabaseType.UNKNOWN:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Unsupported database scheme: {parsed.scheme}"
                )
            
            # Type-specific validation
            if db_type == DatabaseType.POSTGRESQL:
                return self._validate_postgresql_url(parsed, warnings)
            elif db_type == DatabaseType.SQLITE:
                return self._validate_sqlite_url(parsed, warnings)
            
            return ValidationResult(is_valid=True, warnings=warnings)
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid URL format: {str(e)}"
            )
    
    def _parse_postgresql_url(self, url: str) -> DatabaseConfig:
        """Parse PostgreSQL URL and return configuration."""
        # Handle Render.com format conversion
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        
        parsed = urlparse(url)
        
        # Extract connection options
        options = {}
        if parsed.query:
            query_params = parse_qs(parsed.query)
            options = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
        
        # Add default options for better connection handling
        default_options = {
            'pool_pre_ping': True,
            'pool_timeout': 10,
            'connect_timeout': 10
        }
        options.update(default_options)
        
        return DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            connection_string=url,
            driver="psycopg2",
            options=options,
            is_valid=True
        )
    
    def _parse_sqlite_url(self, url: str) -> DatabaseConfig:
        """Parse SQLite URL and return configuration."""
        parsed = urlparse(url)
        
        # Extract path
        db_path = parsed.path
        if db_path.startswith('/'):
            db_path = db_path[1:]  # Remove leading slash
        
        # Handle special cases
        if not db_path or db_path == ':memory:':
            db_path = ':memory:'
        
        # Extract connection options
        options = {}
        if parsed.query:
            query_params = parse_qs(parsed.query)
            options = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
        
        # Add default options for SQLite
        default_options = {
            'check_same_thread': False,
            'timeout': 10,
            'pool_pre_ping': True
        }
        options.update(default_options)
        
        return DatabaseConfig(
            type=DatabaseType.SQLITE,
            connection_string=url,
            driver="sqlite3",
            options=options,
            is_valid=True
        )
    
    def _validate_postgresql_url(self, parsed, warnings: list) -> ValidationResult:
        """Validate PostgreSQL URL format."""
        if not parsed.hostname:
            return ValidationResult(
                is_valid=False,
                error_message="PostgreSQL URL must include hostname"
            )
        
        if not parsed.path or parsed.path == '/':
            warnings.append("No database name specified in URL")
        
        if not parsed.username:
            warnings.append("No username specified in URL")
        
        if not parsed.password:
            warnings.append("No password specified in URL - may cause authentication issues")
        
        # Check for common issues
        if parsed.port and (parsed.port < 1 or parsed.port > 65535):
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid port number: {parsed.port}"
            )
        
        return ValidationResult(is_valid=True, warnings=warnings)
    
    def _validate_sqlite_url(self, parsed, warnings: list) -> ValidationResult:
        """Validate SQLite URL format."""
        if not parsed.path:
            return ValidationResult(
                is_valid=False,
                error_message="SQLite URL must include database path"
            )
        
        db_path = parsed.path[1:] if parsed.path.startswith('/') else parsed.path
        
        # Check for in-memory database
        if db_path == ':memory:':
            warnings.append("Using in-memory database - data will not persist")
            return ValidationResult(is_valid=True, warnings=warnings)
        
        # Check if directory exists for file-based database
        if db_path:
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                warnings.append(f"Database directory does not exist: {db_dir}")
        
        return ValidationResult(is_valid=True, warnings=warnings)
    
    def get_default_sqlite_config(self) -> DatabaseConfig:
        """Get default SQLite configuration for fallback."""
        return DatabaseConfig(
            type=DatabaseType.SQLITE,
            connection_string="sqlite:///ai_secretary.db",
            driver="sqlite3",
            options={
                'check_same_thread': False,
                'timeout': 10,
                'pool_pre_ping': True
            },
            is_valid=True
        )
    
    def get_memory_sqlite_config(self) -> DatabaseConfig:
        """Get in-memory SQLite configuration for testing."""
        return DatabaseConfig(
            type=DatabaseType.SQLITE,
            connection_string="sqlite:///:memory:",
            driver="sqlite3",
            options={
                'check_same_thread': False,
                'timeout': 10,
                'pool_pre_ping': True
            },
            is_valid=True
        )