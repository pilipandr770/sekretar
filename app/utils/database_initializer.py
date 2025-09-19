"""
Database Initialization Infrastructure

This module provides comprehensive database initialization with automatic schema creation,
migration management, data seeding, and health validation.
"""
import os
import sys
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

from .database_init_logger import (
    get_database_init_logger, 
    DatabaseInitLogger, 
    LogLevel, 
    LogCategory
)
from .environment_config import (
    EnvironmentDetector,
    EnvironmentInitializer,
    get_environment_config,
    Environment,
    DatabaseType
)
from .database_errors import (
    DatabaseErrorHandler,
    DatabaseErrorCode,
    ErrorContext,
    ErrorSeverity,
    handle_database_error,
    create_error_context,
    get_database_error_handler
)
from .database_recovery import (
    get_database_recovery_manager,
    initialize_recovery_system
)

logger = logging.getLogger(__name__)


class InitializationStep(Enum):
    """Database initialization steps."""
    CONNECTION_TEST = "connection_test"
    SCHEMA_CHECK = "schema_check"
    SCHEMA_CREATION = "schema_creation"
    MIGRATION_CHECK = "migration_check"
    MIGRATION_EXECUTION = "migration_execution"
    DATA_SEEDING = "data_seeding"
    HEALTH_VALIDATION = "health_validation"
    CLEANUP = "cleanup"


class ValidationSeverity(Enum):
    """Validation issue severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class InitializationResult:
    """Result of database initialization process."""
    success: bool
    steps_completed: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration: float = 0.0
    database_type: Optional[str] = None
    connection_string: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_step(self, step: str):
        """Add a completed step."""
        self.steps_completed.append(step)
        logger.info(f"✅ Initialization step completed: {step}")
    
    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
        logger.error(f"❌ Initialization error: {error}")
    
    def add_warning(self, warning: str):
        """Add a warning message."""
        self.warnings.append(warning)
        logger.warning(f"⚠️ Initialization warning: {warning}")


@dataclass
class ValidationResult:
    """Result of database validation process."""
    valid: bool
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    severity: ValidationSeverity = ValidationSeverity.INFO
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_issue(self, issue: str, severity: ValidationSeverity = ValidationSeverity.ERROR):
        """Add a validation issue."""
        self.issues.append(issue)
        if severity.value > self.severity.value:
            self.severity = severity
        logger.log(
            logging.ERROR if severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] else logging.WARNING,
            f"Validation issue ({severity.value}): {issue}"
        )
    
    def add_suggestion(self, suggestion: str):
        """Add a suggestion for fixing issues."""
        self.suggestions.append(suggestion)
        logger.info(f"💡 Suggestion: {suggestion}")


@dataclass
class MigrationResult:
    """Result of database migration process."""
    success: bool
    migrations_applied: List[str] = field(default_factory=list)
    failed_migration: Optional[str] = None
    error_message: Optional[str] = None
    rollback_performed: bool = False
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SeedingResult:
    """Result of data seeding process."""
    success: bool
    records_created: Dict[str, int] = field(default_factory=dict)
    records_skipped: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RepairResult:
    """Result of database repair process."""
    success: bool
    repairs_performed: List[str] = field(default_factory=list)
    repairs_failed: List[str] = field(default_factory=list)
    manual_intervention_required: bool = False
    instructions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class DatabaseConfiguration:
    """Database configuration detection and management."""
    
    def __init__(self, app: Flask):
        self.app = app
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def detect_database_type(self) -> str:
        """
        Detect the database type from configuration.
        
        Returns:
            Database type ('postgresql', 'sqlite', 'mysql', etc.)
        """
        database_url = self._get_database_url()
        
        if database_url:
            if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
                return 'postgresql'
            elif database_url.startswith('sqlite://'):
                return 'sqlite'
            elif database_url.startswith('mysql://'):
                return 'mysql'
            else:
                self.logger.warning(f"Unknown database type in URL: {database_url}")
                return 'unknown'
        
        # Fallback to SQLite if no URL specified
        self.logger.info("No database URL specified, defaulting to SQLite")
        return 'sqlite'
    
    def get_connection_parameters(self) -> Dict[str, Any]:
        """
        Extract connection parameters from configuration.
        
        Returns:
            Dictionary of connection parameters
        """
        database_url = self._get_database_url()
        db_type = self.detect_database_type()
        
        params = {
            'database_type': db_type,
            'connection_string': database_url,
            'timeout': self.app.config.get('DATABASE_CONNECTION_TIMEOUT', 30),
            'pool_size': self.app.config.get('DATABASE_POOL_SIZE', 5),
            'max_overflow': self.app.config.get('DATABASE_MAX_OVERFLOW', 10),
            'pool_timeout': self.app.config.get('DATABASE_POOL_TIMEOUT', 30),
            'pool_recycle': self.app.config.get('DATABASE_POOL_RECYCLE', 3600),
            'echo': self.app.config.get('DATABASE_ECHO', False),
            'echo_pool': self.app.config.get('DATABASE_ECHO_POOL', False)
        }
        
        # Add database-specific parameters
        if db_type == 'postgresql':
            params.update(self._get_postgresql_parameters())
        elif db_type == 'sqlite':
            params.update(self._get_sqlite_parameters())
        
        return params
    
    def validate_configuration(self) -> ValidationResult:
        """
        Validate database configuration.
        
        Returns:
            ValidationResult with configuration validation details
        """
        result = ValidationResult(valid=True)
        
        database_url = self._get_database_url()
        if not database_url:
            result.valid = False
            result.add_issue("No database URL configured", ValidationSeverity.CRITICAL)
            result.add_suggestion("Set DATABASE_URL environment variable or SQLALCHEMY_DATABASE_URI in config")
        
        db_type = self.detect_database_type()
        if db_type == 'unknown':
            result.valid = False
            result.add_issue("Unknown database type", ValidationSeverity.ERROR)
            result.add_suggestion("Use supported database types: postgresql, sqlite, mysql")
        
        # Validate database-specific configuration
        if db_type == 'postgresql':
            self._validate_postgresql_config(result)
        elif db_type == 'sqlite':
            self._validate_sqlite_config(result)
        
        # Check for required Flask-SQLAlchemy settings
        if not self.app.config.get('SQLALCHEMY_DATABASE_URI'):
            result.add_issue("SQLALCHEMY_DATABASE_URI not configured", ValidationSeverity.WARNING)
            result.add_suggestion("Set SQLALCHEMY_DATABASE_URI in Flask configuration")
        
        return result
    
    def _get_database_url(self) -> Optional[str]:
        """Get database URL from various configuration sources."""
        # Try environment variable first
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Handle Render.com postgres:// format
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            return database_url
        
        # Try Flask config
        database_url = self.app.config.get('SQLALCHEMY_DATABASE_URI')
        if database_url:
            return database_url
        
        # Try individual components for PostgreSQL
        if all(os.environ.get(key) for key in ['DB_HOST', 'DB_NAME', 'DB_USER']):
            host = os.environ.get('DB_HOST')
            port = os.environ.get('DB_PORT', '5432')
            database = os.environ.get('DB_NAME')
            username = os.environ.get('DB_USER')
            password = os.environ.get('DB_PASSWORD', '')
            
            if password:
                return f'postgresql://{username}:{password}@{host}:{port}/{database}'
            else:
                return f'postgresql://{username}@{host}:{port}/{database}'
        
        return None
    
    def _get_postgresql_parameters(self) -> Dict[str, Any]:
        """Get PostgreSQL-specific parameters."""
        return {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': int(os.environ.get('DB_PORT', 5432)),
            'database': os.environ.get('DB_NAME', 'ai_secretary'),
            'username': os.environ.get('DB_USER', 'postgres'),
            'password': os.environ.get('DB_PASSWORD', ''),
            'schema': os.environ.get('DB_SCHEMA', 'public'),
            'sslmode': os.environ.get('DB_SSLMODE', 'prefer'),
            'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', 10))
        }
    
    def _get_sqlite_parameters(self) -> Dict[str, Any]:
        """Get SQLite-specific parameters."""
        sqlite_url = os.environ.get('SQLITE_DATABASE_URL')
        if sqlite_url and sqlite_url.startswith('sqlite:///'):
            db_path = sqlite_url[10:]  # Remove 'sqlite:///'
        else:
            db_path = self.app.config.get('SQLITE_DATABASE_PATH', 'ai_secretary.db')
        
        return {
            'database_path': db_path,
            'timeout': int(os.environ.get('SQLITE_TIMEOUT', 20)),
            'check_same_thread': False,
            'isolation_level': os.environ.get('SQLITE_ISOLATION_LEVEL'),
            'detect_types': os.environ.get('SQLITE_DETECT_TYPES', 'PARSE_DECLTYPES|PARSE_COLNAMES')
        }
    
    def _validate_postgresql_config(self, result: ValidationResult):
        """Validate PostgreSQL-specific configuration."""
        params = self._get_postgresql_parameters()
        
        if not params['host']:
            result.add_issue("PostgreSQL host not specified", ValidationSeverity.ERROR)
            result.add_suggestion("Set DB_HOST environment variable")
        
        if not params['database']:
            result.add_issue("PostgreSQL database name not specified", ValidationSeverity.ERROR)
            result.add_suggestion("Set DB_NAME environment variable")
        
        if not params['username']:
            result.add_issue("PostgreSQL username not specified", ValidationSeverity.ERROR)
            result.add_suggestion("Set DB_USER environment variable")
        
        # Check port range
        if not (1 <= params['port'] <= 65535):
            result.add_issue(f"Invalid PostgreSQL port: {params['port']}", ValidationSeverity.ERROR)
            result.add_suggestion("Set valid DB_PORT (1-65535)")
    
    def _validate_sqlite_config(self, result: ValidationResult):
        """Validate SQLite-specific configuration."""
        params = self._get_sqlite_parameters()
        
        db_path = params['database_path']
        if db_path != ':memory:':
            # Check if directory exists and is writable
            db_dir = os.path.dirname(os.path.abspath(db_path))
            if not os.path.exists(db_dir):
                result.add_issue(f"SQLite database directory does not exist: {db_dir}", ValidationSeverity.WARNING)
                result.add_suggestion(f"Create directory: {db_dir}")
            elif not os.access(db_dir, os.W_OK):
                result.add_issue(f"SQLite database directory not writable: {db_dir}", ValidationSeverity.ERROR)
                result.add_suggestion(f"Fix directory permissions: {db_dir}")


class DatabaseInitializer:
    """
    Main database initialization orchestrator.
    
    Coordinates all database initialization steps including schema creation,
    migrations, data seeding, and health validation.
    """
    
    def __init__(self, app: Flask, db: SQLAlchemy):
        self.app = app
        self.db = db
        self.config = DatabaseConfiguration(app)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize environment-specific configuration
        self.env_detector = EnvironmentDetector()
        self.env_config = get_environment_config()
        self.env_initializer = EnvironmentInitializer(self.env_config)
        
        # Initialize comprehensive logging system
        log_level = LogLevel.DEBUG if app.debug else LogLevel.INFO
        self.init_logger = get_database_init_logger("database_init", log_level)
        
        # Initialize comprehensive error handling and recovery system
        self.error_handler = get_database_error_handler()
        self.recovery_manager = initialize_recovery_system()
        
        # Log environment configuration
        self.logger.info(f"🌍 Environment: {self.env_config.environment.value}")
        self.logger.info(f"🗄️ Database type: {self.env_config.database_type.value}")
        self.logger.info(f"🔗 Database URL: {self._mask_connection_string(self.env_config.database_url)}")
        
        # Initialize components (will be implemented in subsequent tasks)
        self.schema_manager = None
        self.migration_runner = None
        
        # Initialize data seeder (implemented in task 4)
        from .data_seeder import DataSeeder
        self.data_seeder = DataSeeder(app, db)
        
        # Initialize health validator (implemented in task 5)
        from .health_validator import HealthValidator
        self.health_validator = HealthValidator(app, db)
        
        # Initialization state
        self._initialization_result = None
        self._last_initialization = None
        self._error_history = []
    
    def initialize(self) -> InitializationResult:
        """
        Perform complete database initialization.
        
        Returns:
            InitializationResult with initialization details
        """
        start_time = time.time()
        result = InitializationResult(success=True)
        
        # Start comprehensive logging
        self.init_logger.start_initialization(total_steps=7)
        
        try:
            # Step 0: Prepare environment-specific configuration
            with self.init_logger.step("Prepare Environment", LogCategory.CONNECTION):
                self.init_logger.info(
                    LogCategory.CONNECTION, 
                    f"Preparing {self.env_config.environment.value} environment with {self.env_config.database_type.value}"
                )
                
                try:
                    env_prepared = self.env_initializer.prepare_environment()
                    if not env_prepared:
                        error_context = create_error_context(
                            database_type=self.env_config.database_type.value,
                            operation="environment_preparation",
                            environment=self.env_config.environment.value
                        )
                        error_details = handle_database_error(
                            Exception("Environment preparation failed"),
                            error_context,
                            auto_recover=True
                        )
                        self._record_error(error_details)
                        
                        result.success = False
                        result.add_error(f"Failed to prepare environment: {error_details['message']}")
                        self.init_logger.error(LogCategory.CONNECTION, "Environment preparation failed")
                        return result
                    
                    self.init_logger.info(LogCategory.CONNECTION, "Environment preparation completed")
                    
                except Exception as env_error:
                    error_context = create_error_context(
                        database_type=self.env_config.database_type.value,
                        operation="environment_preparation",
                        environment=self.env_config.environment.value
                    )
                    error_details = handle_database_error(env_error, error_context, auto_recover=True)
                    self._record_error(error_details)
                    
                    result.success = False
                    result.add_error(f"Environment preparation error: {error_details['message']}")
                    return result
            
            # Step 1: Validate configuration
            with self.init_logger.step("Validate Configuration", LogCategory.CONNECTION):
                try:
                    config_validation = self.config.validate_configuration()
                    if not config_validation.valid:
                        # Handle configuration errors with comprehensive error handling
                        for issue in config_validation.issues:
                            error_context = create_error_context(
                                database_type=self.env_config.database_type.value,
                                operation="configuration_validation",
                                configuration_issue=issue
                            )
                            error_details = handle_database_error(
                                Exception(f"Configuration validation failed: {issue}"),
                                error_context,
                                auto_recover=True
                            )
                            self._record_error(error_details)
                            
                            result.add_error(f"Configuration error: {error_details['message']}")
                            self.init_logger.error(LogCategory.CONNECTION, f"Configuration error: {issue}")
                        
                        result.success = False
                        return result
                    
                    self.init_logger.info(LogCategory.CONNECTION, "Configuration validation passed")
                    result.add_step(InitializationStep.CONNECTION_TEST.value)
                    
                except Exception as config_error:
                    error_context = create_error_context(
                        database_type=self.env_config.database_type.value,
                        operation="configuration_validation"
                    )
                    error_details = handle_database_error(config_error, error_context, auto_recover=True)
                    self._record_error(error_details)
                    
                    result.success = False
                    result.add_error(f"Configuration validation error: {error_details['message']}")
                    return result
            
            # Get connection parameters from environment configuration
            conn_params = self._get_environment_connection_parameters()
            result.database_type = conn_params['database_type']
            result.connection_string = self._mask_connection_string(conn_params['connection_string'])
            
            # Step 2: Test database connection
            with self.init_logger.step("Test Database Connection", LogCategory.CONNECTION):
                self.init_logger.log_connection_attempt(
                    conn_params['database_type'], 
                    conn_params['connection_string']
                )
                
                connection_start = time.time()
                try:
                    connection_success = self._test_connection(conn_params)
                    connection_duration = time.time() - connection_start
                    
                    if connection_success:
                        self.init_logger.log_connection_success(
                            conn_params['database_type'], 
                            connection_duration
                        )
                        result.add_step(InitializationStep.SCHEMA_CHECK.value)
                    else:
                        # Handle connection failure with comprehensive error handling
                        connection_error = Exception("Database connection test failed")
                        error_context = create_error_context(
                            database_type=conn_params['database_type'],
                            connection_string=conn_params['connection_string'],
                            operation="connection_test",
                            database_path=conn_params.get('database_path')
                        )
                        error_details = handle_database_error(
                            connection_error,
                            error_context,
                            auto_recover=True
                        )
                        self._record_error(error_details)
                        
                        self.init_logger.log_connection_failure(
                            conn_params['database_type'], 
                            connection_error, 
                            connection_duration
                        )
                        
                        result.success = False
                        result.add_error(f"Database connection failed: {error_details['message']}")
                        
                        # Add recovery suggestions to result
                        if error_details.get('resolution', {}).get('recovery_steps'):
                            for step in error_details['resolution']['recovery_steps']:
                                if not step['automated']:
                                    result.add_warning(f"Recovery suggestion: {step['description']}")
                        
                        return result
                        
                except Exception as connection_error:
                    connection_duration = time.time() - connection_start
                    error_context = create_error_context(
                        database_type=conn_params['database_type'],
                        connection_string=conn_params['connection_string'],
                        operation="connection_test",
                        database_path=conn_params.get('database_path')
                    )
                    error_details = handle_database_error(connection_error, error_context, auto_recover=True)
                    self._record_error(error_details)
                    
                    self.init_logger.log_connection_failure(
                        conn_params['database_type'], 
                        connection_error, 
                        connection_duration
                    )
                    
                    result.success = False
                    result.add_error(f"Database connection error: {error_details['message']}")
                    return result
            
            # Step 3: Check and create schema (placeholder for now)
            with self.init_logger.step("Check Database Schema", LogCategory.SCHEMA):
                # TODO: Implement schema management in task 2
                self.init_logger.info(LogCategory.SCHEMA, "Schema management will be implemented in task 2")
                result.add_step(InitializationStep.SCHEMA_CREATION.value)
            
            # Step 4: Check and run migrations (placeholder for now)
            with self.init_logger.step("Check Database Migrations", LogCategory.MIGRATION):
                # TODO: Implement migration runner in task 3
                self.init_logger.info(LogCategory.MIGRATION, "Migration runner will be implemented in task 3")
                result.add_step(InitializationStep.MIGRATION_EXECUTION.value)
            
            # Step 5: Seed initial data (environment-specific)
            with self.init_logger.step("Seed Initial Data", LogCategory.SEEDING):
                if self.env_config.auto_seed_data:
                    self.init_logger.info(
                        LogCategory.SEEDING, 
                        f"Auto-seeding enabled for {self.env_config.environment.value} environment"
                    )
                    
                    try:
                        seeding_start = time.time()
                        seeding_result = self.data_seeder.seed_initial_data()
                        seeding_duration = time.time() - seeding_start
                        
                        if seeding_result.success:
                            self.init_logger.info(
                                LogCategory.SEEDING, 
                                f"Data seeding completed successfully in {seeding_duration:.2f}s"
                            )
                            
                            # Log seeding details
                            for record_type, count in seeding_result.records_created.items():
                                self.init_logger.info(LogCategory.SEEDING, f"Created {count} {record_type} records")
                            
                            for record_type, count in seeding_result.records_skipped.items():
                                self.init_logger.info(LogCategory.SEEDING, f"Skipped {count} existing {record_type} records")
                            
                            result.add_step(InitializationStep.DATA_SEEDING.value)
                        else:
                            # Handle seeding errors with comprehensive error handling
                            for error in seeding_result.errors:
                                error_context = create_error_context(
                                    database_type=conn_params['database_type'],
                                    operation="data_seeding",
                                    seeding_error=error
                                )
                                error_details = handle_database_error(
                                    Exception(f"Data seeding failed: {error}"),
                                    error_context,
                                    auto_recover=True
                                )
                                self._record_error(error_details)
                                
                                result.add_error(f"Data seeding error: {error_details['message']}")
                                self.init_logger.error(LogCategory.SEEDING, f"Data seeding error: {error}")
                            
                            result.success = False
                            return result
                            
                    except Exception as seeding_error:
                        error_context = create_error_context(
                            database_type=conn_params['database_type'],
                            operation="data_seeding"
                        )
                        error_details = handle_database_error(seeding_error, error_context, auto_recover=True)
                        self._record_error(error_details)
                        
                        result.success = False
                        result.add_error(f"Data seeding error: {error_details['message']}")
                        return result
                else:
                    self.init_logger.info(
                        LogCategory.SEEDING, 
                        f"Auto-seeding disabled for {self.env_config.environment.value} environment"
                    )
                    result.add_step(InitializationStep.DATA_SEEDING.value)
            
            # Step 6: Validate database health
            with self.init_logger.step("Validate Database Health", LogCategory.VALIDATION):
                try:
                    validation_start = time.time()
                    health_result = self.health_validator.run_comprehensive_health_check()
                    validation_duration = time.time() - validation_start
                    
                    if health_result.status.value in ['healthy', 'warning']:
                        self.init_logger.info(
                            LogCategory.VALIDATION, 
                            f"Database health validation completed in {validation_duration:.2f}s - Status: {health_result.status.value}"
                        )
                        
                        # Log health check details
                        self.init_logger.info(LogCategory.VALIDATION, f"Health checks: {health_result.checks_passed} passed, {health_result.checks_failed} failed")
                        
                        if health_result.warnings:
                            for warning in health_result.warnings:
                                result.add_warning(f"Health warning: {warning}")
                                self.init_logger.warning(LogCategory.VALIDATION, f"Health warning: {warning}")
                        
                        result.add_step(InitializationStep.HEALTH_VALIDATION.value)
                    else:
                        # Health validation failed - handle with comprehensive error handling
                        if health_result.status.value == 'critical':
                            for issue in health_result.issues:
                                error_context = create_error_context(
                                    database_type=conn_params['database_type'],
                                    operation="health_validation",
                                    health_issue=issue
                                )
                                error_details = handle_database_error(
                                    Exception(f"Health validation failed: {issue}"),
                                    error_context,
                                    auto_recover=True
                                )
                                self._record_error(error_details)
                                
                                result.add_error(f"Health validation error: {error_details['message']}")
                                self.init_logger.error(LogCategory.VALIDATION, f"Health validation error: {issue}")
                            
                            result.success = False
                            return result
                        else:
                            # Just warnings, continue
                            for warning in health_result.warnings:
                                result.add_warning(f"Health warning: {warning}")
                            result.add_step(InitializationStep.HEALTH_VALIDATION.value)
                            
                except Exception as health_error:
                    error_context = create_error_context(
                        database_type=conn_params['database_type'],
                        operation="health_validation"
                    )
                    error_details = handle_database_error(health_error, error_context, auto_recover=True)
                    self._record_error(error_details)
                    
                    # Health validation errors are not critical for initialization
                    result.add_warning(f"Health validation error: {error_details['message']}")
                    result.add_step(InitializationStep.HEALTH_VALIDATION.value)
            
            # Step 7: Environment-specific cleanup
            with self.init_logger.step("Cleanup", LogCategory.CONNECTION):
                # Perform environment-specific cleanup if needed
                if self.env_config.initialization_options.get('cleanup_on_exit', False):
                    cleanup_success = self.env_initializer.cleanup_environment()
                    if cleanup_success:
                        self.init_logger.info(LogCategory.CONNECTION, "Environment cleanup completed")
                    else:
                        self.init_logger.warning(LogCategory.CONNECTION, "Environment cleanup had issues")
                        result.add_warning("Environment cleanup had issues")
                
                self.init_logger.info(LogCategory.CONNECTION, "Initialization cleanup completed")
                result.add_step(InitializationStep.CLEANUP.value)
            
        except Exception as e:
            # Handle unexpected initialization errors with comprehensive error handling
            error_context = create_error_context(
                database_type=self.env_config.database_type.value,
                operation="database_initialization",
                environment=self.env_config.environment.value
            )
            error_details = handle_database_error(e, error_context, auto_recover=False)
            self._record_error(error_details)
            
            result.success = False
            result.add_error(f"Initialization failed: {error_details['message']}")
            
            # Add recovery suggestions to result
            if error_details.get('resolution', {}).get('recovery_steps'):
                for step in error_details['resolution']['recovery_steps']:
                    if not step['automated']:
                        result.add_warning(f"Recovery suggestion: {step['description']}")
            
            self.init_logger.critical(
                LogCategory.CONNECTION, 
                f"Database initialization failed with exception: {str(e)}", 
                error=e
            )
        
        finally:
            result.duration = time.time() - start_time
            self._initialization_result = result
            self._last_initialization = datetime.now()
            
            # Log performance metrics
            self.init_logger.log_performance_metric("total_initialization_time", result.duration * 1000, "ms")
            
            # Finish comprehensive logging
            self.init_logger.finish_initialization(result.success)
        
        return result
    
    def validate_setup(self) -> ValidationResult:
        """
        Validate current database setup.
        
        Returns:
            ValidationResult with validation details
        """
        self.logger.info("🔍 Validating database setup...")
        
        # Start with configuration validation
        result = self.config.validate_configuration()
        
        if result.valid:
            # Test connection
            conn_params = self.config.get_connection_parameters()
            if not self._test_connection(conn_params):
                result.valid = False
                result.add_issue("Cannot connect to database", ValidationSeverity.CRITICAL)
                result.add_suggestion("Check database server status and connection parameters")
        
        # Add health validation
        if result.valid and self.health_validator:
            health_result = self.health_validator.run_comprehensive_health_check()
            if health_result.status.value == 'critical':
                result.valid = False
                result.add_issue("Health validation failed", ValidationSeverity.CRITICAL)
                result.add_suggestion("Run database health check for detailed diagnostics")
        
        # TODO: Add schema validation when schema manager is implemented
        # TODO: Add migration validation when migration runner is implemented
        
        return result
    
    def repair_if_needed(self) -> RepairResult:
        """
        Attempt to repair database issues if needed.
        
        Returns:
            RepairResult with repair details
        """
        self.logger.info("🔧 Checking if database repair is needed...")
        
        result = RepairResult(success=True)
        
        # Validate current setup
        validation = self.validate_setup()
        
        if validation.valid:
            self.logger.info("✅ Database setup is valid, no repair needed")
            return result
        
        # TODO: Implement repair logic based on validation issues
        # This will be expanded as other components are implemented
        
        result.manual_intervention_required = True
        result.instructions.extend(validation.suggestions)
        
        return result
    
    def get_initialization_status(self) -> Dict[str, Any]:
        """
        Get current initialization status.
        
        Returns:
            Dictionary with initialization status details
        """
        status = {
            'initialized': self._initialization_result is not None,
            'last_initialization': self._last_initialization.isoformat() if self._last_initialization else None,
            'database_type': None,
            'connection_available': False,
            'schema_valid': False,
            'migrations_current': False,
            'data_seeded': False,
            'health_status': 'unknown'
        }
        
        if self._initialization_result:
            status.update({
                'success': self._initialization_result.success,
                'database_type': self._initialization_result.database_type,
                'steps_completed': self._initialization_result.steps_completed,
                'errors': self._initialization_result.errors,
                'warnings': self._initialization_result.warnings,
                'duration': self._initialization_result.duration
            })
        
        # Test current connection status
        conn_params = self.config.get_connection_parameters()
        status['connection_available'] = self._test_connection(conn_params)
        
        return status
    
    def _test_connection(self, conn_params: Dict[str, Any]) -> bool:
        """
        Test database connection.
        
        Args:
            conn_params: Connection parameters
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Ensure we have app context for database operations
            from flask import has_app_context, current_app
            
            if not has_app_context():
                if hasattr(self, 'app') and self.app:
                    with self.app.app_context():
                        return self._perform_connection_test(conn_params)
                else:
                    # Try to get app from current_app if available
                    try:
                        app = current_app._get_current_object()
                        with app.app_context():
                            return self._perform_connection_test(conn_params)
                    except RuntimeError:
                        # No app context available, proceed without it
                        return self._perform_connection_test(conn_params)
            else:
                return self._perform_connection_test(conn_params)
                
        except Exception as e:
            self.init_logger.error(
                LogCategory.CONNECTION,
                f"Database connection test failed: {str(e)}",
                error=e
            )
            return False
    
    def _perform_connection_test(self, conn_params: Dict[str, Any]) -> bool:
        """
        Perform the actual connection test.
        
        Args:
            conn_params: Connection parameters
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            connection_string = conn_params['connection_string']
            timeout = conn_params.get('timeout', 30)
            
            self.init_logger.debug(
                LogCategory.CONNECTION,
                f"Testing connection to {conn_params['database_type']} database",
                details={'timeout': timeout}
            )
            
            # Create engine with environment-specific parameters
            engine_kwargs = conn_params.get('engine_options', {}).copy()
            
            # Ensure basic options are set
            if 'pool_pre_ping' not in engine_kwargs:
                engine_kwargs['pool_pre_ping'] = True
            
            # Add pool settings if not already specified
            if conn_params['database_type'] != 'sqlite':
                if 'pool_timeout' not in engine_kwargs:
                    engine_kwargs['pool_timeout'] = timeout
                if 'pool_size' not in engine_kwargs:
                    engine_kwargs['pool_size'] = conn_params.get('pool_size', 5)
                if 'max_overflow' not in engine_kwargs:
                    engine_kwargs['max_overflow'] = conn_params.get('max_overflow', 10)
            
            self.init_logger.debug(
                LogCategory.CONNECTION,
                f"Creating engine with options: {list(engine_kwargs.keys())}"
            )
            
            engine = create_engine(connection_string, **engine_kwargs)
            
            # Test connection
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            
            engine.dispose()
            self.init_logger.debug(LogCategory.CONNECTION, "Database connection test successful")
            return True
            
        except Exception as e:
            self.init_logger.error(
                LogCategory.CONNECTION,
                f"Database connection test failed: {str(e)}",
                error=e
            )
            return False
    
    def _get_environment_connection_parameters(self) -> Dict[str, Any]:
        """
        Get connection parameters based on environment configuration.
        
        Returns:
            Dictionary of connection parameters
        """
        params = {
            'database_type': self.env_config.database_type.value,
            'connection_string': self.env_config.database_url,
            'timeout': self.env_config.connection_timeout,
            'pool_size': self.env_config.pool_size,
            'max_overflow': self.env_config.max_overflow,
            'engine_options': self.env_config.engine_options.copy()
        }
        
        # Add environment-specific parameters
        if self.env_config.database_type == DatabaseType.SQLITE:
            params.update({
                'database_path': self.env_config.database_file_path,
                'auto_create': self.env_config.auto_create_database,
                'isolated': self.env_config.isolated_database
            })
        elif self.env_config.database_type == DatabaseType.POSTGRESQL:
            params.update({
                'auto_create_schema': self.env_config.initialization_options.get('create_schema', False),
                'schema_name': os.environ.get('DB_SCHEMA', 'public'),
                'retry_attempts': self.env_config.initialization_options.get('retry_attempts', 3)
            })
        
        return params
    
    def _mask_connection_string(self, connection_string: Optional[str]) -> Optional[str]:
        """
        Mask sensitive information in connection string.
        
        Args:
            connection_string: Original connection string
            
        Returns:
            Masked connection string
        """
        if not connection_string:
            return None
        
        # Mask password in connection strings
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
    
    def get_initialization_logger(self) -> DatabaseInitLogger:
        """
        Get the initialization logger instance.
        
        Returns:
            DatabaseInitLogger instance
        """
        return self.init_logger
    
    def export_initialization_logs(self, format: str = "json") -> str:
        """
        Export initialization logs.
        
        Args:
            format: Export format ('json' or 'csv')
            
        Returns:
            Exported logs as string
        """
        return self.init_logger.export_logs(format)
    
    def get_initialization_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive initialization summary.
        
        Returns:
            Dictionary with initialization summary
        """
        summary = self.init_logger.get_summary()
        
        # Add initialization result details
        if self._initialization_result:
            summary.update({
                'initialization_success': self._initialization_result.success,
                'initialization_errors': self._initialization_result.errors,
                'initialization_warnings': self._initialization_result.warnings,
                'steps_completed': self._initialization_result.steps_completed,
                'database_type': self._initialization_result.database_type,
                'last_initialization': self._last_initialization.isoformat() if self._last_initialization else None
            })
        
        return summary
    
    def _record_error(self, error_details: Dict[str, Any]):
        """
        Record error details in the error history.
        
        Args:
            error_details: Error details from error handler
        """
        self._error_history.append(error_details)
        
        # Log error statistics periodically
        if len(self._error_history) % 10 == 0:
            stats = self.error_handler.get_error_statistics()
            self.logger.info(f"Error statistics: {stats}")
    
    def get_error_history(self) -> List[Dict[str, Any]]:
        """
        Get the history of initialization errors.
        
        Returns:
            List of error details dictionaries
        """
        return self._error_history.copy()
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about initialization errors.
        
        Returns:
            Dictionary with error statistics
        """
        return self.error_handler.get_error_statistics()
    
    def clear_error_history(self):
        """Clear the initialization error history."""
        self._error_history.clear()
        self.error_handler.clear_error_history()
        self.logger.info("Initialization error history cleared")
    
    def get_recovery_suggestions(self, error_code: str = None) -> List[Dict[str, Any]]:
        """
        Get recovery suggestions for initialization errors.
        
        Args:
            error_code: Specific error code to get suggestions for (optional)
            
        Returns:
            List of recovery suggestions
        """
        suggestions = []
        
        for error_record in self._error_history:
            if error_code is None or error_record.get('error_code') == error_code:
                resolution = error_record.get('resolution', {})
                if resolution.get('recovery_steps'):
                    suggestions.extend([
                        {
                            'error_code': error_record.get('error_code'),
                            'step': step,
                            'timestamp': error_record.get('timestamp')
                        }
                        for step in resolution['recovery_steps']
                        if not step.get('automated', False)
                    ])
        
        return suggestions
    
    def generate_troubleshooting_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive troubleshooting report.
        
        Returns:
            Dictionary with troubleshooting information
        """
        report = {
            'initialization_status': self.get_initialization_status(),
            'error_statistics': self.get_error_statistics(),
            'error_history': self.get_error_history(),
            'recovery_suggestions': self.get_recovery_suggestions(),
            'environment_info': {
                'environment': self.env_config.environment.value,
                'database_type': self.env_config.database_type.value,
                'database_url': self._mask_connection_string(self.env_config.database_url),
                'auto_seed_data': self.env_config.auto_seed_data,
                'auto_create_database': self.env_config.auto_create_database
            },
            'system_info': {
                'python_version': os.sys.version,
                'platform': os.name,
                'working_directory': os.getcwd(),
                'environment_variables': {
                    key: value for key, value in os.environ.items()
                    if key.startswith(('DB_', 'DATABASE_', 'SQLALCHEMY_'))
                    and 'PASSWORD' not in key.upper()
                }
            },
            'generated_at': datetime.now().isoformat()
        }
        
        return report