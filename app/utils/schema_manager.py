"""
Schema Management System

This module provides comprehensive database schema management including
table existence checking, automatic table creation, schema validation,
and repair mechanisms for corrupted or incomplete schemas.
"""
import logging
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import inspect, text, MetaData, Table, Column
from sqlalchemy.exc import SQLAlchemyError, OperationalError, ProgrammingError
from flask import current_app
from flask_sqlalchemy import SQLAlchemy


logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Represents a schema validation issue."""
    table_name: str
    issue_type: str
    message: str
    severity: ValidationSeverity
    suggested_fix: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Result of schema validation."""
    valid: bool
    issues: List[ValidationIssue]
    tables_checked: int
    tables_valid: int
    suggestions: List[str]
    severity: ValidationSeverity
    
    @property
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return any(issue.severity == ValidationSeverity.CRITICAL for issue in self.issues)
    
    @property
    def has_errors(self) -> bool:
        """Check if there are any error-level issues."""
        return any(issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] 
                  for issue in self.issues)


@dataclass
class RepairResult:
    """Result of schema repair operation."""
    success: bool
    repairs_attempted: List[str]
    repairs_successful: List[str]
    repairs_failed: List[str]
    errors: List[str]
    warnings: List[str]


@dataclass
class SchemaInfo:
    """Information about database schema."""
    database_type: str
    total_tables: int
    existing_tables: List[str]
    missing_tables: List[str]
    table_details: Dict[str, Dict[str, Any]]
    indexes: Dict[str, List[str]]
    constraints: Dict[str, List[str]]
    last_updated: datetime


class SchemaManager:
    """
    Manages database schema creation, validation, and repair.
    
    This class provides comprehensive schema management functionality including:
    - Table existence checking
    - Automatic table creation using SQLAlchemy metadata
    - Schema validation to verify table structures
    - Schema repair mechanisms for corrupted or incomplete schemas
    """
    
    def __init__(self, app=None, db: SQLAlchemy = None):
        """
        Initialize schema manager.
        
        Args:
            app: Flask application instance
            db: SQLAlchemy database instance
        """
        self.app = app
        self.db = db
        self._metadata = None
        self._inspector = None
        self._database_type = None
        
        if app is not None:
            self.init_app(app, db)
    
    def init_app(self, app, db: SQLAlchemy = None):
        """Initialize schema manager with Flask app."""
        self.app = app
        if db is not None:
            self.db = db
        
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['schema_manager'] = self
        
        # Initialize metadata and inspector when needed
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize SQLAlchemy components."""
        if self.db is None:
            logger.error("SQLAlchemy database instance not provided")
            return
        
        try:
            # Get metadata from SQLAlchemy models
            self._metadata = self.db.metadata
            
            # Create inspector for database introspection
            if self.db.engine:
                self._inspector = inspect(self.db.engine)
                self._database_type = self.db.engine.dialect.name
                logger.debug(f"Schema manager initialized for {self._database_type} database")
            else:
                logger.warning("Database engine not available for schema inspection")
                
        except Exception as e:
            logger.error(f"Failed to initialize schema manager components: {e}")
    
    def check_schema_exists(self) -> bool:
        """
        Check if database schema exists.
        
        Returns:
            True if all required tables exist, False otherwise
        """
        try:
            if not self._inspector:
                logger.error("Database inspector not available")
                return False
            
            # Get list of existing tables
            existing_tables = set(self._inspector.get_table_names())
            
            # Get list of required tables from metadata
            required_tables = set(self._metadata.tables.keys())
            
            # Check if all required tables exist
            missing_tables = required_tables - existing_tables
            
            if missing_tables:
                logger.info(f"Missing tables detected: {', '.join(sorted(missing_tables))}")
                return False
            
            logger.info(f"All {len(required_tables)} required tables exist")
            return True
            
        except Exception as e:
            logger.error(f"Failed to check schema existence: {e}")
            return False
    
    def get_missing_tables(self) -> List[str]:
        """
        Get list of missing tables.
        
        Returns:
            List of missing table names
        """
        try:
            if not self._inspector:
                return []
            
            existing_tables = set(self._inspector.get_table_names())
            required_tables = set(self._metadata.tables.keys())
            missing_tables = required_tables - existing_tables
            
            return sorted(list(missing_tables))
            
        except Exception as e:
            logger.error(f"Failed to get missing tables: {e}")
            return []
    
    def get_existing_tables(self) -> List[str]:
        """
        Get list of existing tables.
        
        Returns:
            List of existing table names
        """
        try:
            if not self._inspector:
                if self.db and self.db.engine:
                    self._inspector = inspect(self.db.engine)
                else:
                    return []
            
            # Refresh inspector to get latest table list
            self._inspector = inspect(self.db.engine)
            return sorted(self._inspector.get_table_names())
            
        except Exception as e:
            logger.error(f"Failed to get existing tables: {e}")
            return []
    
    def create_schema(self) -> bool:
        """
        Create database schema using SQLAlchemy metadata.
        
        Returns:
            True if schema creation successful, False otherwise
        """
        try:
            if not self.db:
                logger.error("Database instance not available for schema creation")
                return False
            
            # Check if engine is available
            try:
                engine = self.db.engine
                if not engine:
                    logger.error("Database engine not available for schema creation")
                    return False
            except Exception as e:
                logger.error(f"Database engine not available for schema creation: {e}")
                return False
            
            # Ensure components are initialized
            if not self._metadata or not self._inspector:
                self._initialize_components()
            
            logger.debug("Creating database schema...")
            
            # Get missing tables before creation
            missing_tables = self.get_missing_tables()
            
            if not missing_tables:
                logger.debug("All tables already exist, no schema creation needed")
                return True
            
            logger.debug(f"Creating {len(missing_tables)} missing tables: {', '.join(missing_tables)}")
            
            # Create all tables defined in metadata
            self._metadata.create_all(bind=self.db.engine)
            
            # Refresh inspector after table creation
            self._inspector = inspect(self.db.engine)
            
            # Verify tables were created
            created_tables = []
            failed_tables = []
            
            for table_name in missing_tables:
                if self._table_exists(table_name):
                    created_tables.append(table_name)
                else:
                    failed_tables.append(table_name)
            
            if created_tables:
                logger.debug(f"Successfully created tables: {', '.join(created_tables)}")
            
            if failed_tables:
                logger.error(f"Failed to create tables: {', '.join(failed_tables)}")
                return False
            
            logger.debug("✅ Database schema creation completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Schema creation failed: {e}")
            return False
    
    def create_table(self, table_name: str) -> bool:
        """
        Create a specific table.
        
        Args:
            table_name: Name of the table to create
            
        Returns:
            True if table creation successful, False otherwise
        """
        try:
            if not self.db or not self.db.engine:
                logger.error("Database engine not available")
                return False
            
            if table_name not in self._metadata.tables:
                logger.error(f"Table '{table_name}' not found in metadata")
                return False
            
            if self._table_exists(table_name):
                logger.info(f"Table '{table_name}' already exists")
                return True
            
            logger.info(f"Creating table: {table_name}")
            
            # Get table from metadata and create it
            table = self._metadata.tables[table_name]
            table.create(bind=self.db.engine)
            
            # Verify table was created
            if self._table_exists(table_name):
                logger.info(f"✅ Successfully created table: {table_name}")
                return True
            else:
                logger.error(f"❌ Failed to create table: {table_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to create table '{table_name}': {e}")
            return False
    
    def validate_schema(self) -> ValidationResult:
        """
        Validate database schema integrity.
        
        Returns:
            ValidationResult with validation details
        """
        issues = []
        tables_checked = 0
        tables_valid = 0
        suggestions = []
        
        try:
            if not self._inspector:
                issues.append(ValidationIssue(
                    table_name="",
                    issue_type="inspector_unavailable",
                    message="Database inspector not available",
                    severity=ValidationSeverity.CRITICAL,
                    suggested_fix="Check database connection and initialization"
                ))
                return ValidationResult(
                    valid=False,
                    issues=issues,
                    tables_checked=0,
                    tables_valid=0,
                    suggestions=["Ensure database connection is established"],
                    severity=ValidationSeverity.CRITICAL
                )
            
            # Get existing and required tables
            existing_tables = set(self.get_existing_tables())
            required_tables = set(self._metadata.tables.keys())
            
            # Check for missing tables
            missing_tables = required_tables - existing_tables
            if missing_tables:
                for table_name in missing_tables:
                    issues.append(ValidationIssue(
                        table_name=table_name,
                        issue_type="missing_table",
                        message=f"Required table '{table_name}' is missing",
                        severity=ValidationSeverity.ERROR,
                        suggested_fix=f"Create table '{table_name}' using schema creation"
                    ))
                suggestions.append("Run schema creation to create missing tables")
            
            # Check for extra tables (informational)
            extra_tables = existing_tables - required_tables
            if extra_tables:
                for table_name in extra_tables:
                    issues.append(ValidationIssue(
                        table_name=table_name,
                        issue_type="extra_table",
                        message=f"Table '{table_name}' exists but is not defined in models",
                        severity=ValidationSeverity.INFO,
                        suggested_fix="Consider adding model definition or removing unused table"
                    ))
            
            # Validate existing tables structure
            for table_name in existing_tables.intersection(required_tables):
                tables_checked += 1
                table_issues = self._validate_table_structure(table_name)
                issues.extend(table_issues)
                
                if not any(issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] 
                          for issue in table_issues):
                    tables_valid += 1
            
            # Determine overall severity
            if any(issue.severity == ValidationSeverity.CRITICAL for issue in issues):
                overall_severity = ValidationSeverity.CRITICAL
            elif any(issue.severity == ValidationSeverity.ERROR for issue in issues):
                overall_severity = ValidationSeverity.ERROR
            elif any(issue.severity == ValidationSeverity.WARNING for issue in issues):
                overall_severity = ValidationSeverity.WARNING
            else:
                overall_severity = ValidationSeverity.INFO
            
            # Add general suggestions
            if issues:
                if missing_tables:
                    suggestions.append("Use create_schema() to create missing tables")
                if any(issue.issue_type == "column_mismatch" for issue in issues):
                    suggestions.append("Consider running database migrations to fix column issues")
                if any(issue.issue_type == "index_missing" for issue in issues):
                    suggestions.append("Recreate missing indexes for better performance")
            
            is_valid = len(issues) == 0 or not any(
                issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] 
                for issue in issues
            )
            
            logger.info(f"Schema validation completed: {tables_valid}/{tables_checked} tables valid, "
                       f"{len(issues)} issues found")
            
            return ValidationResult(
                valid=is_valid,
                issues=issues,
                tables_checked=tables_checked,
                tables_valid=tables_valid,
                suggestions=suggestions,
                severity=overall_severity
            )
            
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            issues.append(ValidationIssue(
                table_name="",
                issue_type="validation_error",
                message=f"Schema validation failed: {e}",
                severity=ValidationSeverity.CRITICAL,
                suggested_fix="Check database connection and permissions"
            ))
            
            return ValidationResult(
                valid=False,
                issues=issues,
                tables_checked=tables_checked,
                tables_valid=tables_valid,
                suggestions=["Fix database connection issues and retry validation"],
                severity=ValidationSeverity.CRITICAL
            )
    
    def _validate_table_structure(self, table_name: str) -> List[ValidationIssue]:
        """
        Validate structure of a specific table.
        
        Args:
            table_name: Name of the table to validate
            
        Returns:
            List of validation issues for the table
        """
        issues = []
        
        try:
            # Get table definition from metadata
            if table_name not in self._metadata.tables:
                issues.append(ValidationIssue(
                    table_name=table_name,
                    issue_type="table_not_in_metadata",
                    message=f"Table '{table_name}' exists in database but not in metadata",
                    severity=ValidationSeverity.WARNING,
                    suggested_fix="Add model definition for this table"
                ))
                return issues
            
            expected_table = self._metadata.tables[table_name]
            
            # Get actual table structure from database
            try:
                actual_columns = {col['name']: col for col in self._inspector.get_columns(table_name)}
                expected_columns = {col.name: col for col in expected_table.columns}
                
                # Check for missing columns
                missing_columns = set(expected_columns.keys()) - set(actual_columns.keys())
                for col_name in missing_columns:
                    issues.append(ValidationIssue(
                        table_name=table_name,
                        issue_type="missing_column",
                        message=f"Column '{col_name}' is missing from table '{table_name}'",
                        severity=ValidationSeverity.ERROR,
                        suggested_fix=f"Add column '{col_name}' to table '{table_name}'"
                    ))
                
                # Check for extra columns
                extra_columns = set(actual_columns.keys()) - set(expected_columns.keys())
                for col_name in extra_columns:
                    issues.append(ValidationIssue(
                        table_name=table_name,
                        issue_type="extra_column",
                        message=f"Column '{col_name}' exists in table '{table_name}' but not in model",
                        severity=ValidationSeverity.INFO,
                        suggested_fix=f"Consider adding '{col_name}' to model or removing from table"
                    ))
                
                # Validate column types for common columns
                for col_name in set(expected_columns.keys()).intersection(set(actual_columns.keys())):
                    expected_col = expected_columns[col_name]
                    actual_col = actual_columns[col_name]
                    
                    # Basic type checking (simplified)
                    if not self._types_compatible(expected_col.type, actual_col['type']):
                        issues.append(ValidationIssue(
                            table_name=table_name,
                            issue_type="column_type_mismatch",
                            message=f"Column '{col_name}' type mismatch in table '{table_name}'",
                            severity=ValidationSeverity.WARNING,
                            suggested_fix=f"Check column type for '{col_name}' - expected: {expected_col.type}, actual: {actual_col['type']}",
                            details={
                                "expected_type": str(expected_col.type),
                                "actual_type": str(actual_col['type'])
                            }
                        ))
                
                # Check indexes
                try:
                    actual_indexes = self._inspector.get_indexes(table_name)
                    expected_indexes = [idx for idx in expected_table.indexes]
                    
                    # This is a simplified index check - in practice, you'd want more sophisticated comparison
                    if len(expected_indexes) > len(actual_indexes):
                        issues.append(ValidationIssue(
                            table_name=table_name,
                            issue_type="missing_indexes",
                            message=f"Table '{table_name}' may be missing some indexes",
                            severity=ValidationSeverity.WARNING,
                            suggested_fix=f"Review and recreate indexes for table '{table_name}'"
                        ))
                        
                except Exception as e:
                    logger.debug(f"Could not check indexes for table '{table_name}': {e}")
                
            except Exception as e:
                issues.append(ValidationIssue(
                    table_name=table_name,
                    issue_type="table_inspection_failed",
                    message=f"Failed to inspect table '{table_name}': {e}",
                    severity=ValidationSeverity.ERROR,
                    suggested_fix=f"Check table '{table_name}' exists and is accessible"
                ))
                
        except Exception as e:
            issues.append(ValidationIssue(
                table_name=table_name,
                issue_type="validation_error",
                message=f"Failed to validate table '{table_name}': {e}",
                severity=ValidationSeverity.ERROR,
                suggested_fix="Check database connection and table accessibility"
            ))
        
        return issues
    
    def _types_compatible(self, expected_type, actual_type) -> bool:
        """
        Check if database types are compatible.
        
        Args:
            expected_type: SQLAlchemy type from model
            actual_type: Database type from inspection
            
        Returns:
            True if types are compatible, False otherwise
        """
        # This is a simplified type compatibility check
        # In practice, you'd want more sophisticated type comparison
        try:
            expected_str = str(expected_type).lower()
            actual_str = str(actual_type).lower()
            
            # Basic compatibility mappings
            type_mappings = {
                'integer': ['int', 'integer', 'bigint'],
                'varchar': ['varchar', 'text', 'string'],
                'text': ['text', 'varchar', 'string'],
                'boolean': ['boolean', 'bool', 'tinyint'],
                'datetime': ['datetime', 'timestamp'],
                'float': ['float', 'real', 'double'],
                'decimal': ['decimal', 'numeric']
            }
            
            for expected_base, compatible_types in type_mappings.items():
                if expected_base in expected_str:
                    return any(compat in actual_str for compat in compatible_types)
            
            # If no specific mapping found, do basic string comparison
            return expected_str in actual_str or actual_str in expected_str
            
        except Exception:
            # If comparison fails, assume compatible to avoid false positives
            return True
    
    def repair_schema(self) -> RepairResult:
        """
        Attempt to repair corrupted or incomplete schema.
        
        Returns:
            RepairResult with repair operation details
        """
        repairs_attempted = []
        repairs_successful = []
        repairs_failed = []
        errors = []
        warnings = []
        
        try:
            logger.info("Starting schema repair...")
            
            # First, validate current schema to identify issues
            validation_result = self.validate_schema()
            
            if validation_result.valid:
                logger.info("Schema is valid, no repairs needed")
                return RepairResult(
                    success=True,
                    repairs_attempted=[],
                    repairs_successful=[],
                    repairs_failed=[],
                    errors=[],
                    warnings=["Schema is already valid"]
                )
            
            # Attempt to fix missing tables
            missing_tables = [issue.table_name for issue in validation_result.issues 
                            if issue.issue_type == "missing_table"]
            
            if missing_tables:
                repair_name = f"create_missing_tables_{len(missing_tables)}"
                repairs_attempted.append(repair_name)
                
                try:
                    if self.create_schema():
                        repairs_successful.append(repair_name)
                        logger.info(f"Successfully created {len(missing_tables)} missing tables")
                    else:
                        repairs_failed.append(repair_name)
                        errors.append(f"Failed to create missing tables: {', '.join(missing_tables)}")
                except Exception as e:
                    repairs_failed.append(repair_name)
                    errors.append(f"Error creating missing tables: {e}")
            
            # Attempt to fix missing columns (simplified approach)
            column_issues = [issue for issue in validation_result.issues 
                           if issue.issue_type == "missing_column"]
            
            for issue in column_issues:
                # Extract column name from message
                column_name = "unknown"
                if "'" in issue.message:
                    parts = issue.message.split("'")
                    if len(parts) > 1:
                        column_name = parts[1]
                repair_name = f"add_column_{issue.table_name}_{column_name}"
                repairs_attempted.append(repair_name)
                
                # For now, we'll just log these as warnings since column addition
                # requires careful consideration of data types and constraints
                warnings.append(f"Column repair needed: {issue.message}")
                warnings.append("Manual intervention may be required for column additions")
            
            # Check if repairs were successful
            if repairs_attempted:
                # Re-validate schema after repairs
                post_repair_validation = self.validate_schema()
                
                if post_repair_validation.valid:
                    logger.info("✅ Schema repair completed successfully")
                    return RepairResult(
                        success=True,
                        repairs_attempted=repairs_attempted,
                        repairs_successful=repairs_successful,
                        repairs_failed=repairs_failed,
                        errors=errors,
                        warnings=warnings
                    )
                else:
                    remaining_issues = len(post_repair_validation.issues)
                    warnings.append(f"Schema repair partially successful, {remaining_issues} issues remain")
            
            success = len(repairs_failed) == 0 and len(errors) == 0
            
            logger.info(f"Schema repair completed: {len(repairs_successful)} successful, "
                       f"{len(repairs_failed)} failed")
            
            return RepairResult(
                success=success,
                repairs_attempted=repairs_attempted,
                repairs_successful=repairs_successful,
                repairs_failed=repairs_failed,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            error_msg = f"Schema repair failed: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            return RepairResult(
                success=False,
                repairs_attempted=repairs_attempted,
                repairs_successful=repairs_successful,
                repairs_failed=repairs_failed,
                errors=errors,
                warnings=warnings
            )
    
    def get_schema_info(self) -> SchemaInfo:
        """
        Get comprehensive information about database schema.
        
        Returns:
            SchemaInfo with detailed schema information
        """
        try:
            existing_tables = self.get_existing_tables()
            missing_tables = self.get_missing_tables()
            total_tables = len(set(existing_tables + missing_tables))
            
            # Get detailed table information
            table_details = {}
            indexes = {}
            constraints = {}
            
            for table_name in existing_tables:
                try:
                    # Get column information
                    columns = self._inspector.get_columns(table_name)
                    table_details[table_name] = {
                        'columns': len(columns),
                        'column_details': columns
                    }
                    
                    # Get index information
                    try:
                        table_indexes = self._inspector.get_indexes(table_name)
                        indexes[table_name] = [idx['name'] for idx in table_indexes if idx.get('name')]
                    except Exception:
                        indexes[table_name] = []
                    
                    # Get constraint information
                    try:
                        pk_constraint = self._inspector.get_pk_constraint(table_name)
                        fk_constraints = self._inspector.get_foreign_keys(table_name)
                        unique_constraints = self._inspector.get_unique_constraints(table_name)
                        
                        table_constraints = []
                        if pk_constraint and pk_constraint.get('constrained_columns'):
                            table_constraints.append(f"PK: {pk_constraint['name'] or 'unnamed'}")
                        
                        for fk in fk_constraints:
                            table_constraints.append(f"FK: {fk.get('name', 'unnamed')}")
                        
                        for uc in unique_constraints:
                            table_constraints.append(f"UNIQUE: {uc.get('name', 'unnamed')}")
                        
                        constraints[table_name] = table_constraints
                        
                    except Exception:
                        constraints[table_name] = []
                        
                except Exception as e:
                    logger.debug(f"Could not get details for table '{table_name}': {e}")
                    table_details[table_name] = {'error': str(e)}
                    indexes[table_name] = []
                    constraints[table_name] = []
            
            return SchemaInfo(
                database_type=self._database_type or "unknown",
                total_tables=total_tables,
                existing_tables=existing_tables,
                missing_tables=missing_tables,
                table_details=table_details,
                indexes=indexes,
                constraints=constraints,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")
            return SchemaInfo(
                database_type=self._database_type or "unknown",
                total_tables=0,
                existing_tables=[],
                missing_tables=[],
                table_details={},
                indexes={},
                constraints={},
                last_updated=datetime.now()
            )
    
    def _table_exists(self, table_name: str) -> bool:
        """
        Check if a specific table exists in the database.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        try:
            if not self._inspector:
                if self.db and self.db.engine:
                    self._inspector = inspect(self.db.engine)
                else:
                    return False
            
            # Refresh inspector to get latest table list
            self._inspector = inspect(self.db.engine)
            existing_tables = self._inspector.get_table_names()
            return table_name in existing_tables
            
        except Exception as e:
            logger.debug(f"Error checking table existence for '{table_name}': {e}")
            return False
    
    def drop_table(self, table_name: str, force: bool = False) -> bool:
        """
        Drop a specific table.
        
        Args:
            table_name: Name of the table to drop
            force: If True, ignore errors and force drop
            
        Returns:
            True if table dropped successfully, False otherwise
        """
        try:
            if not self.db or not self.db.engine:
                logger.error("Database engine not available")
                return False
            
            if not self._table_exists(table_name):
                logger.info(f"Table '{table_name}' does not exist")
                return True
            
            logger.warning(f"Dropping table: {table_name}")
            
            # Drop table using raw SQL for better control
            with self.db.engine.connect() as conn:
                if force:
                    # For SQLite, we might need to handle foreign key constraints
                    if self._database_type == 'sqlite':
                        conn.execute(text('PRAGMA foreign_keys = OFF'))
                    
                conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
                conn.commit()
                
                if force and self._database_type == 'sqlite':
                    conn.execute(text('PRAGMA foreign_keys = ON'))
            
            # Verify table was dropped
            if not self._table_exists(table_name):
                logger.info(f"✅ Successfully dropped table: {table_name}")
                return True
            else:
                logger.error(f"❌ Failed to drop table: {table_name}")
                return False
                
        except Exception as e:
            if force:
                logger.warning(f"Error dropping table '{table_name}' (forced): {e}")
                return True
            else:
                logger.error(f"Failed to drop table '{table_name}': {e}")
                return False
    
    def recreate_table(self, table_name: str) -> bool:
        """
        Recreate a specific table (drop and create).
        
        Args:
            table_name: Name of the table to recreate
            
        Returns:
            True if table recreated successfully, False otherwise
        """
        try:
            logger.info(f"Recreating table: {table_name}")
            
            # Drop existing table
            if self._table_exists(table_name):
                if not self.drop_table(table_name):
                    logger.error(f"Failed to drop existing table '{table_name}'")
                    return False
            
            # Create new table
            if self.create_table(table_name):
                logger.info(f"✅ Successfully recreated table: {table_name}")
                return True
            else:
                logger.error(f"❌ Failed to recreate table: {table_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to recreate table '{table_name}': {e}")
            return False


def get_schema_manager(app=None, db=None) -> SchemaManager:
    """
    Get or create schema manager instance.
    
    Args:
        app: Optional Flask app instance
        db: Optional SQLAlchemy database instance
        
    Returns:
        SchemaManager instance
    """
    if app is None:
        app = current_app
    
    if 'schema_manager' not in app.extensions:
        manager = SchemaManager(app, db)
    else:
        manager = app.extensions['schema_manager']
    
    return manager