"""
Database URL Parser

This module provides intelligent parsing and validation of database URLs
with support for PostgreSQL, SQLite, and automatic type detection.
It includes comprehensive validation and clear error messages.
"""
import re
import os
import logging
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from .database_config import (
    DatabaseConfig, DatabaseType, ValidationResult, ValidationError, DatabaseURL
)

logger = logging.getLogger(__name__)


class DatabaseURLParser:
    """
    Intelligent database URL parser with type detection and validation.
    
    This class can parse various database URL formats, detect the database type,
    validate the URL structure, and provide detailed error messages for
    configuration issues.
    """
    
    # Regex patterns for database URL validation
    POSTGRESQL_PATTERNS = [
        r'^postgresql://.*',
        r'^postgres://.*',
        r'^psql://.*'
    ]
    
    SQLITE_PATTERNS = [
        r'^sqlite:///.*',
        r'^sqlite://.*'
    ]
    
    # Common PostgreSQL URL formats
    POSTGRESQL_FULL_PATTERN = re.compile(
        r'^(postgresql|postgres|psql)://(?:([^:]+)(?::([^@]*))?@)?([^:/]+)(?::(\d+))?/([^?]+)(?:\?(.*))?$'
    )
    
    # SQLite URL formats
    SQLITE_PATTERN = re.compile(
        r'^sqlite:///(.+)$'
    )
    
    SQLITE_MEMORY_PATTERN = re.compile(
        r'^sqlite:///:memory:$'
    )
    
    def __init__(self):
        """Initialize the database URL parser."""
        self.validation_cache = {}
    
    def parse_url(self, url: DatabaseURL) -> DatabaseConfig:
        """
        Parse database URL and return configuration.
        
        Args:
            url: Database URL string or None
            
        Returns:
            DatabaseConfig with parsed information and validation status
        """
        if not url or not isinstance(url, str) or not url.strip():
            return self._create_default_sqlite_config("Empty or None URL provided")
        
        url = url.strip()
        
        # Check cache first
        if url in self.validation_cache:
            cached_result = self.validation_cache[url]
            logger.debug(f"Using cached validation result for URL")
            return cached_result
        
        try:
            # Detect database type
            db_type = self.detect_database_type(url)
            
            if db_type == DatabaseType.POSTGRESQL:
                config = self._parse_postgresql_url(url)
            elif db_type == DatabaseType.SQLITE:
                config = self._parse_sqlite_url(url)
            else:
                config = self._create_invalid_config(
                    url, 
                    DatabaseType.UNKNOWN,
                    "Unknown database type",
                    ValidationResult.INVALID_SCHEME,
                    "Use 'postgresql://' for PostgreSQL or 'sqlite:///' for SQLite"
                )
            
            # Cache the result
            self.validation_cache[url] = config
            
            return config
            
        except Exception as e:
            logger.error(f"Error parsing database URL: {e}")
            return self._create_invalid_config(
                url,
                DatabaseType.UNKNOWN,
                f"Parsing error: {str(e)}",
                ValidationResult.UNKNOWN_ERROR
            )
    
    def detect_database_type(self, url: str) -> DatabaseType:
        """
        Detect database type from URL scheme.
        
        Args:
            url: Database URL string
            
        Returns:
            DatabaseType enum value
        """
        if not url:
            return DatabaseType.UNKNOWN
        
        url_lower = url.lower().strip()
        
        # Check PostgreSQL patterns
        for pattern in self.POSTGRESQL_PATTERNS:
            if re.match(pattern, url_lower):
                return DatabaseType.POSTGRESQL
        
        # Check SQLite patterns
        for pattern in self.SQLITE_PATTERNS:
            if re.match(pattern, url_lower):
                return DatabaseType.SQLITE
        
        return DatabaseType.UNKNOWN
    
    def validate_url(self, url: str) -> ValidationError:
        """
        Validate URL format and accessibility.
        
        Args:
            url: Database URL string
            
        Returns:
            ValidationError with detailed information
        """
        if not url or not isinstance(url, str) or not url.strip():
            return ValidationError(
                result=ValidationResult.INVALID_FORMAT,
                message="URL is empty or None",
                suggestion="Provide a valid database URL like 'postgresql://user:pass@host:port/db' or 'sqlite:///path/to/db.sqlite'"
            )
        
        url = url.strip()
        db_type = self.detect_database_type(url)
        
        if db_type == DatabaseType.UNKNOWN:
            return ValidationError(
                result=ValidationResult.INVALID_SCHEME,
                message=f"Unknown database scheme in URL: {url}",
                suggestion="Use 'postgresql://' for PostgreSQL or 'sqlite:///' for SQLite",
                url_component="scheme"
            )
        
        if db_type == DatabaseType.POSTGRESQL:
            return self._validate_postgresql_url(url)
        elif db_type == DatabaseType.SQLITE:
            return self._validate_sqlite_url(url)
        
        return ValidationError(
            result=ValidationResult.UNKNOWN_ERROR,
            message="Unexpected validation path"
        )
    
    def _parse_postgresql_url(self, url: str) -> DatabaseConfig:
        """Parse PostgreSQL URL and create configuration."""
        validation_error = self._validate_postgresql_url(url)
        
        if validation_error.result != ValidationResult.VALID:
            return self._create_invalid_config(
                url,
                DatabaseType.POSTGRESQL,
                validation_error.message,
                validation_error.result,
                validation_error.suggestion
            )
        
        # Parse URL components
        match = self.POSTGRESQL_FULL_PATTERN.match(url)
        if not match:
            return self._create_invalid_config(
                url,
                DatabaseType.POSTGRESQL,
                "Invalid PostgreSQL URL format",
                ValidationResult.INVALID_FORMAT,
                "Expected format: postgresql://user:password@host:port/database"
            )
        
        scheme, username, password, host, port, database, query_string = match.groups()
        
        # Convert port to integer
        port_int = None
        if port:
            try:
                port_int = int(port)
            except ValueError:
                return self._create_invalid_config(
                    url,
                    DatabaseType.POSTGRESQL,
                    f"Invalid port number: {port}",
                    ValidationResult.INVALID_FORMAT,
                    "Port must be a valid integer"
                )
        
        # Parse query parameters
        options = {}
        if query_string:
            try:
                query_params = parse_qs(query_string)
                options.update({k: v[0] if len(v) == 1 else v for k, v in query_params.items()})
            except Exception as e:
                logger.warning(f"Failed to parse query parameters: {e}")
        
        # Normalize scheme to postgresql
        normalized_url = url
        if scheme in ['postgres', 'psql']:
            normalized_url = url.replace(f'{scheme}://', 'postgresql://', 1)
        
        return DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            connection_string=normalized_url,
            driver='psycopg2',
            options=options,
            is_valid=True,
            error_message=None,
            validation_result=ValidationResult.VALID,
            host=host,
            port=port_int,
            database=database,
            username=username,
            password=password
        )
    
    def _parse_sqlite_url(self, url: str) -> DatabaseConfig:
        """Parse SQLite URL and create configuration."""
        validation_error = self._validate_sqlite_url(url)
        
        if validation_error.result != ValidationResult.VALID:
            return self._create_invalid_config(
                url,
                DatabaseType.SQLITE,
                validation_error.message,
                validation_error.result,
                validation_error.suggestion
            )
        
        # Handle memory database
        if self.SQLITE_MEMORY_PATTERN.match(url):
            return DatabaseConfig(
                type=DatabaseType.SQLITE,
                connection_string=url,
                driver='sqlite3',
                options={},
                is_valid=True,
                error_message=None,
                validation_result=ValidationResult.VALID,
                database=':memory:'
            )
        
        # Handle file database
        match = self.SQLITE_PATTERN.match(url)
        if match:
            db_path = match.group(1)
            
            return DatabaseConfig(
                type=DatabaseType.SQLITE,
                connection_string=url,
                driver='sqlite3',
                options={},
                is_valid=True,
                error_message=None,
                validation_result=ValidationResult.VALID,
                database=db_path
            )
        
        return self._create_invalid_config(
            url,
            DatabaseType.SQLITE,
            "Invalid SQLite URL format",
            ValidationResult.INVALID_FORMAT,
            "Expected format: sqlite:///path/to/database.db or sqlite:///:memory:"
        )
    
    def _validate_postgresql_url(self, url: str) -> ValidationError:
        """Validate PostgreSQL URL format."""
        if not any(re.match(pattern, url.lower()) for pattern in self.POSTGRESQL_PATTERNS):
            return ValidationError(
                result=ValidationResult.INVALID_SCHEME,
                message="URL does not match PostgreSQL scheme",
                suggestion="Use 'postgresql://', 'postgres://', or 'psql://' scheme",
                url_component="scheme"
            )
        
        # Parse URL to check components
        try:
            parsed = urlparse(url)
        except Exception as e:
            return ValidationError(
                result=ValidationResult.INVALID_FORMAT,
                message=f"Failed to parse URL: {e}",
                suggestion="Check URL format for special characters or encoding issues"
            )
        
        # Check required components
        if not parsed.hostname:
            return ValidationError(
                result=ValidationResult.MISSING_COMPONENTS,
                message="Missing hostname in PostgreSQL URL",
                suggestion="Include hostname: postgresql://user:pass@hostname:port/database",
                url_component="hostname"
            )
        
        if not parsed.path or parsed.path == '/':
            return ValidationError(
                result=ValidationResult.MISSING_COMPONENTS,
                message="Missing database name in PostgreSQL URL",
                suggestion="Include database name: postgresql://user:pass@host:port/database_name",
                url_component="database"
            )
        
        # Validate port if present
        if parsed.port is not None:
            if not (1 <= parsed.port <= 65535):
                return ValidationError(
                    result=ValidationResult.INVALID_FORMAT,
                    message=f"Invalid port number: {parsed.port}",
                    suggestion="Port must be between 1 and 65535",
                    url_component="port"
                )
        
        return ValidationError(
            result=ValidationResult.VALID,
            message="PostgreSQL URL is valid"
        )
    
    def _validate_sqlite_url(self, url: str) -> ValidationError:
        """Validate SQLite URL format."""
        if not any(re.match(pattern, url.lower()) for pattern in self.SQLITE_PATTERNS):
            return ValidationError(
                result=ValidationResult.INVALID_SCHEME,
                message="URL does not match SQLite scheme",
                suggestion="Use 'sqlite:///' scheme for SQLite",
                url_component="scheme"
            )
        
        # Check for memory database
        if self.SQLITE_MEMORY_PATTERN.match(url):
            return ValidationError(
                result=ValidationResult.VALID,
                message="SQLite memory database URL is valid"
            )
        
        # Check for file database
        match = self.SQLITE_PATTERN.match(url)
        if not match:
            return ValidationError(
                result=ValidationResult.INVALID_FORMAT,
                message="Invalid SQLite URL format",
                suggestion="Use 'sqlite:///path/to/database.db' or 'sqlite:///:memory:'",
                expected_format="sqlite:///path/to/database.db"
            )
        
        db_path = match.group(1)
        
        # Validate path
        if not db_path:
            return ValidationError(
                result=ValidationResult.MISSING_COMPONENTS,
                message="Missing database path in SQLite URL",
                suggestion="Provide path: sqlite:///path/to/database.db",
                url_component="path"
            )
        
        # Check if path is reasonable (not validating existence as it may not exist yet)
        try:
            path_obj = Path(db_path)
            # Check if parent directory exists or can be created
            if not path_obj.parent.exists():
                # This is just a warning, not an error
                logger.debug(f"Parent directory does not exist: {path_obj.parent}")
        except Exception as e:
            return ValidationError(
                result=ValidationResult.INVALID_FORMAT,
                message=f"Invalid file path: {e}",
                suggestion="Use a valid file system path",
                url_component="path"
            )
        
        return ValidationError(
            result=ValidationResult.VALID,
            message="SQLite URL is valid"
        )
    
    def _create_default_sqlite_config(self, reason: str) -> DatabaseConfig:
        """Create default SQLite configuration."""
        default_url = 'sqlite:///ai_secretary.db'
        
        return DatabaseConfig(
            type=DatabaseType.SQLITE,
            connection_string=default_url,
            driver='sqlite3',
            options={},
            is_valid=True,
            error_message=f"Using default SQLite: {reason}",
            validation_result=ValidationResult.VALID,
            database='ai_secretary.db'
        )
    
    def _create_invalid_config(
        self, 
        url: str, 
        db_type: DatabaseType, 
        error_message: str,
        validation_result: ValidationResult,
        suggestion: Optional[str] = None
    ) -> DatabaseConfig:
        """Create invalid configuration with error details."""
        full_message = error_message
        if suggestion:
            full_message += f" Suggestion: {suggestion}"
        
        return DatabaseConfig(
            type=db_type,
            connection_string=url,
            driver='unknown',
            options={},
            is_valid=False,
            error_message=full_message,
            validation_result=validation_result
        )
    
    def get_example_urls(self) -> Dict[str, str]:
        """
        Get example URLs for different database types.
        
        Returns:
            Dictionary with example URLs
        """
        return {
            'postgresql_full': 'postgresql://username:password@localhost:5432/database_name',
            'postgresql_no_auth': 'postgresql://localhost:5432/database_name',
            'postgresql_default_port': 'postgresql://username:password@localhost/database_name',
            'sqlite_file': 'sqlite:///path/to/database.db',
            'sqlite_relative': 'sqlite:///./data/app.db',
            'sqlite_memory': 'sqlite:///:memory:',
            'postgres_scheme': 'postgres://username:password@localhost:5432/database_name'
        }
    
    def clear_cache(self):
        """Clear the validation cache."""
        self.validation_cache.clear()
        logger.debug("Database URL validation cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'cache_size': len(self.validation_cache),
            'cached_urls': list(self.validation_cache.keys())
        }