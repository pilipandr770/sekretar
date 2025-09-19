"""Database error fixing utilities."""
import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from flask import Flask, current_app
from sqlalchemy import text, inspect, MetaData, Table, Column, Integer, String, DateTime, Float, Text, JSON, Boolean
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from app import db


logger = logging.getLogger(__name__)


@dataclass
class DatabaseFixResult:
    """Result of database fix operation."""
    success: bool
    fixed_issues: List[str]
    remaining_issues: List[str]
    errors: List[str]
    warnings: List[str]


class DatabaseFixer:
    """Fixes common database errors and issues."""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self.fixed_issues = []
        self.remaining_issues = []
        self.errors = []
        self.warnings = []
    
    def fix_all_database_issues(self) -> DatabaseFixResult:
        """Fix all known database issues."""
        logger.info("🔧 Starting database fixes...")
        
        # Reset tracking lists
        self.fixed_issues = []
        self.remaining_issues = []
        self.errors = []
        self.warnings = []
        
        try:
            # Ensure we have application context
            if self.app:
                with self.app.app_context():
                    self._perform_fixes()
            else:
                self._perform_fixes()
                
        except Exception as e:
            logger.error(f"Failed to perform database fixes: {e}")
            self.errors.append(f"Failed to perform database fixes: {e}")
        
        result = DatabaseFixResult(
            success=len(self.errors) == 0,
            fixed_issues=self.fixed_issues,
            remaining_issues=self.remaining_issues,
            errors=self.errors,
            warnings=self.warnings
        )
        
        logger.info(f"✅ Database fixes completed. Fixed: {len(result.fixed_issues)}, Errors: {len(result.errors)}")
        return result
    
    def _perform_fixes(self):
        """Perform all database fixes."""
        # Fix missing performance_alerts table
        self._fix_performance_alerts_table()
        
        # Fix table existence checks
        self._add_table_existence_checks()
        
        # Fix SQLite configuration issues
        self._fix_sqlite_configuration()
        
        # Validate database schema
        self._validate_database_schema()
    
    def _fix_performance_alerts_table(self):
        """Ensure performance_alerts table exists."""
        try:
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            if 'performance_alerts' not in existing_tables:
                logger.info("Creating missing performance_alerts table...")
                self._create_performance_alerts_table()
                self.fixed_issues.append("Created missing performance_alerts table")
            else:
                logger.info("performance_alerts table already exists")
                
        except Exception as e:
            logger.error(f"Failed to fix performance_alerts table: {e}")
            self.errors.append(f"Failed to fix performance_alerts table: {e}")
    
    def _create_performance_alerts_table(self):
        """Create the performance_alerts table manually."""
        try:
            # Create table using SQLAlchemy Core
            metadata = MetaData()
            
            performance_alerts = Table(
                'performance_alerts', metadata,
                Column('id', Integer, primary_key=True),
                Column('alert_type', String(50), nullable=False, index=True),
                Column('severity', String(20), nullable=False, index=True),
                Column('title', String(255), nullable=False),
                Column('description', Text, nullable=False),
                Column('endpoint', String(255), nullable=True, index=True),
                Column('service_name', String(100), nullable=True, index=True),
                Column('metric_value', Float, nullable=True),
                Column('threshold_value', Float, nullable=True),
                Column('status', String(20), nullable=False, default='active', index=True),
                Column('acknowledged_by', Integer, nullable=True),
                Column('acknowledged_at', DateTime, nullable=True),
                Column('resolved_at', DateTime, nullable=True),
                Column('first_occurrence', DateTime, nullable=False, default=datetime.utcnow, index=True),
                Column('last_occurrence', DateTime, nullable=False, default=datetime.utcnow),
                Column('occurrence_count', Integer, nullable=False, default=1),
                Column('alert_metadata', JSON, nullable=True),
                Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
                Column('updated_at', DateTime, nullable=False, default=datetime.utcnow)
            )
            
            # Create the table
            metadata.create_all(db.engine, tables=[performance_alerts])
            
            # Create additional indexes
            self._create_performance_alerts_indexes()
            
            logger.info("✅ performance_alerts table created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create performance_alerts table: {e}")
            raise
    
    def _create_performance_alerts_indexes(self):
        """Create indexes for performance_alerts table."""
        try:
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_performance_alert_type_status ON performance_alerts (alert_type, status)",
                "CREATE INDEX IF NOT EXISTS idx_performance_alert_severity ON performance_alerts (severity, first_occurrence)",
                "CREATE INDEX IF NOT EXISTS idx_performance_alert_endpoint ON performance_alerts (endpoint, status)"
            ]
            
            for index_sql in indexes:
                try:
                    db.engine.execute(text(index_sql))
                except Exception as e:
                    logger.warning(f"Failed to create index: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to create performance_alerts indexes: {e}")
    
    def _add_table_existence_checks(self):
        """Add table existence checks to prevent errors."""
        try:
            # Check all critical tables exist
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            critical_tables = [
                'users', 'tenants', 'performance_metrics', 
                'performance_alerts', 'service_health', 'slow_queries'
            ]
            
            missing_tables = []
            for table in critical_tables:
                if table not in existing_tables:
                    missing_tables.append(table)
            
            if missing_tables:
                self.warnings.append(f"Missing critical tables: {', '.join(missing_tables)}")
                logger.warning(f"Missing critical tables: {', '.join(missing_tables)}")
            else:
                self.fixed_issues.append("All critical tables exist")
                
        except Exception as e:
            logger.error(f"Failed to check table existence: {e}")
            self.errors.append(f"Failed to check table existence: {e}")
    
    def _fix_sqlite_configuration(self):
        """Fix SQLite specific configuration issues."""
        try:
            database_url = os.environ.get('DATABASE_URL', '')
            
            if database_url.startswith('sqlite'):
                # Enable foreign keys for SQLite
                db.engine.execute(text('PRAGMA foreign_keys=ON'))
                
                # Set journal mode to WAL for better concurrency
                db.engine.execute(text('PRAGMA journal_mode=WAL'))
                
                # Set synchronous mode to NORMAL for better performance
                db.engine.execute(text('PRAGMA synchronous=NORMAL'))
                
                self.fixed_issues.append("Applied SQLite configuration optimizations")
                logger.info("✅ SQLite configuration optimized")
                
        except Exception as e:
            logger.error(f"Failed to fix SQLite configuration: {e}")
            self.errors.append(f"Failed to fix SQLite configuration: {e}")
    
    def _validate_database_schema(self):
        """Validate database schema integrity."""
        try:
            # Test basic database operations
            result = db.engine.execute(text('SELECT 1')).fetchone()
            if result and result[0] == 1:
                self.fixed_issues.append("Database connection and basic queries working")
            else:
                self.errors.append("Database basic query test failed")
                
        except Exception as e:
            logger.error(f"Database schema validation failed: {e}")
            self.errors.append(f"Database schema validation failed: {e}")
    
    def check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        try:
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            return table_name in existing_tables
        except Exception as e:
            logger.error(f"Failed to check if table {table_name} exists: {e}")
            return False
    
    def safe_query_with_table_check(self, table_name: str, query: str, params: Optional[Dict] = None):
        """Execute query only if table exists."""
        try:
            if not self.check_table_exists(table_name):
                logger.warning(f"Table {table_name} does not exist, skipping query")
                return None
                
            return db.engine.execute(text(query), params or {})
            
        except Exception as e:
            logger.error(f"Failed to execute safe query on {table_name}: {e}")
            return None
    
    def create_missing_tables_from_models(self):
        """Create missing tables from SQLAlchemy models."""
        try:
            # Import all models to ensure they're registered
            from app.models import performance, base
            
            # Create all tables
            db.create_all()
            
            self.fixed_issues.append("Created missing tables from models")
            logger.info("✅ Missing tables created from models")
            
        except Exception as e:
            logger.error(f"Failed to create tables from models: {e}")
            self.errors.append(f"Failed to create tables from models: {e}")


def safe_database_operation(func):
    """Decorator to safely execute database operations with proper error handling."""
    def wrapper(*args, **kwargs):
        try:
            # Ensure we have application context
            if not current_app:
                logger.error("No application context available for database operation")
                return None
                
            return func(*args, **kwargs)
            
        except OperationalError as e:
            if "no such table" in str(e).lower():
                logger.error(f"Table missing error in {func.__name__}: {e}")
                # Try to fix the missing table
                fixer = DatabaseFixer(current_app)
                fixer.create_missing_tables_from_models()
                # Retry the operation
                try:
                    return func(*args, **kwargs)
                except Exception as retry_e:
                    logger.error(f"Retry failed for {func.__name__}: {retry_e}")
                    return None
            else:
                logger.error(f"Database operational error in {func.__name__}: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            return None
    
    return wrapper