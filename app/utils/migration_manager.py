"""
Migration Manager for Database Table Creation

This module provides functionality to automatically create missing database tables
and ensure the database schema is complete. It focuses on table existence checking
and creation rather than full migration management.
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy import text, inspect, MetaData, Table, Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app

from app import db
from app.utils.logging_config import get_logger
from app.utils.performance_alerts_migration import PerformanceAlertsMigration


logger = get_logger(__name__)


@dataclass
class TableCreationResult:
    """Result of table creation operation."""
    success: bool
    table_name: str
    error_message: Optional[str] = None
    already_existed: bool = False
    creation_time: float = 0.0


@dataclass
class MigrationResult:
    """Result of migration operation."""
    success: bool
    tables_checked: List[str]
    tables_created: List[str]
    tables_failed: List[str]
    errors: List[str]
    warnings: List[str]
    total_time: float = 0.0


class MigrationManager:
    """
    Manages database table creation and ensures required tables exist.
    
    This class focuses on ensuring that all required tables exist in the database,
    creating them if they are missing. It works alongside the existing Alembic
    migration system but handles immediate table creation needs.
    """
    
    def __init__(self, app=None):
        """Initialize migration manager."""
        self.app = app
        self.required_tables = [
            'performance_alerts',
            'users',
            'tenants',
            'roles',
            'audit_logs',
            'channels',
            'threads',
            'inbox_messages',
            'contacts',
            'pipelines',
            'stages',
            'leads',
            'tasks',
            'notes',
            'knowledge_sources',
            'documents',
            'chunks',
            'embeddings',
            'plans',
            'subscriptions',
            'usage_events',
            'entitlements',
            'invoices',
            'counterparties',
            'counterparty_snapshots',
            'counterparty_diffs',
            'kyb_alerts',
            'kyb_monitoring_configs',
            'dead_letter_tasks',
            'notification_templates',
            'notification_preferences',
            'notifications',
            'notification_events',
            'data_retention_policies',
            'consent_records',
            'pii_detection_logs',
            'data_deletion_requests',
            'data_export_requests',
            'performance_metrics',
            'slow_queries',
            'service_health'
        ]
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize migration manager with Flask app."""
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['migration_manager'] = self
    
    def ensure_tables_exist(self) -> MigrationResult:
        """
        Ensure all required tables exist, creating them if necessary.
        
        Returns:
            MigrationResult with operation details
        """
        start_time = time.time()
        result = MigrationResult(
            success=True,
            tables_checked=[],
            tables_created=[],
            tables_failed=[],
            errors=[],
            warnings=[]
        )
        
        logger.info("🔍 Checking for missing database tables...")
        
        try:
            # Check which tables are missing
            missing_tables = self.check_missing_tables()
            result.tables_checked = self.required_tables.copy()
            
            if not missing_tables:
                logger.info("✅ All required tables exist")
                result.total_time = time.time() - start_time
                return result
            
            logger.info(f"📋 Found {len(missing_tables)} missing tables: {missing_tables}")
            
            # Create missing tables
            for table_name in missing_tables:
                # Use specialized migration for performance_alerts
                if table_name == 'performance_alerts':
                    creation_result = self.create_performance_alerts_table()
                else:
                    creation_result = self._create_table(table_name)
                
                if creation_result.success:
                    if not creation_result.already_existed:
                        result.tables_created.append(table_name)
                        logger.info(f"✅ Created table: {table_name}")
                    else:
                        result.warnings.append(f"Table {table_name} already existed")
                else:
                    result.tables_failed.append(table_name)
                    result.errors.append(f"Failed to create {table_name}: {creation_result.error_message}")
                    logger.error(f"❌ Failed to create table {table_name}: {creation_result.error_message}")
            
            # Update overall success status
            result.success = len(result.tables_failed) == 0
            
            if result.success:
                logger.info(f"✅ Successfully created {len(result.tables_created)} missing tables")
            else:
                logger.error(f"❌ Failed to create {len(result.tables_failed)} tables")
                
        except Exception as e:
            logger.error(f"❌ Migration operation failed: {e}")
            result.success = False
            result.errors.append(f"Migration operation failed: {str(e)}")
        
        finally:
            result.total_time = time.time() - start_time
        
        return result
    
    def check_missing_tables(self) -> List[str]:
        """
        Check which required tables are missing from the database.
        
        Returns:
            List of missing table names
        """
        try:
            # Get database inspector
            inspector = inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            
            # Find missing tables
            missing_tables = []
            for table_name in self.required_tables:
                if table_name not in existing_tables:
                    missing_tables.append(table_name)
            
            logger.info(f"📊 Table status: {len(existing_tables)} exist, {len(missing_tables)} missing")
            
            return missing_tables
            
        except Exception as e:
            logger.error(f"❌ Failed to check missing tables: {e}")
            return self.required_tables.copy()  # Assume all are missing if check fails
    
    def create_performance_alerts_table(self) -> TableCreationResult:
        """
        Create the performance_alerts table specifically using specialized migration.
        
        Returns:
            TableCreationResult with creation details
        """
        start_time = time.time()
        
        try:
            # Use specialized performance alerts migration
            migration = PerformanceAlertsMigration()
            result = migration.create_table()
            
            return TableCreationResult(
                success=result['success'],
                table_name='performance_alerts',
                error_message='; '.join(result['errors']) if result['errors'] else None,
                already_existed='Table already exists' in result.get('warnings', []),
                creation_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to create performance_alerts table: {e}")
            return TableCreationResult(
                success=False,
                table_name='performance_alerts',
                error_message=str(e),
                creation_time=time.time() - start_time
            )
    
    def _create_table(self, table_name: str) -> TableCreationResult:
        """
        Create a specific table based on its name.
        
        Args:
            table_name: Name of the table to create
            
        Returns:
            TableCreationResult with creation details
        """
        start_time = time.time()
        
        try:
            # Check if table already exists
            inspector = inspect(db.engine)
            if table_name in inspector.get_table_names():
                return TableCreationResult(
                    success=True,
                    table_name=table_name,
                    already_existed=True,
                    creation_time=time.time() - start_time
                )
            
            # Get table creation SQL based on table name
            create_sql = self._get_table_creation_sql(table_name)
            
            if not create_sql:
                return TableCreationResult(
                    success=False,
                    table_name=table_name,
                    error_message=f"No creation SQL defined for table {table_name}",
                    creation_time=time.time() - start_time
                )
            
            # Execute table creation
            with db.engine.connect() as connection:
                # Handle multiple SQL statements
                if isinstance(create_sql, list):
                    for sql_statement in create_sql:
                        connection.execute(text(sql_statement))
                else:
                    # Split SQL into individual statements for SQLite compatibility
                    sql_statements = [stmt.strip() for stmt in create_sql.split(';') if stmt.strip()]
                    for sql_statement in sql_statements:
                        connection.execute(text(sql_statement))
                
                connection.commit()
            
            logger.info(f"✅ Successfully created table: {table_name}")
            
            return TableCreationResult(
                success=True,
                table_name=table_name,
                creation_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to create table {table_name}: {e}")
            return TableCreationResult(
                success=False,
                table_name=table_name,
                error_message=str(e),
                creation_time=time.time() - start_time
            )
    
    def _get_table_creation_sql(self, table_name: str) -> Optional[str]:
        """
        Get the SQL statement(s) to create a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            SQL statement(s) or None if not defined
        """
        # Define table creation SQL for each required table
        table_schemas = {
            'performance_alerts': self._get_performance_alerts_schema(),
            'performance_metrics': self._get_performance_metrics_schema(),
            'slow_queries': self._get_slow_queries_schema(),
            'service_health': self._get_service_health_schema(),
        }
        
        return table_schemas.get(table_name)
    
    def _get_performance_alerts_schema(self) -> str:
        """Get SQL schema for performance_alerts table."""
        # Detect database type for appropriate SQL syntax
        db_url = str(db.engine.url)
        is_postgresql = 'postgresql' in db_url
        
        if is_postgresql:
            return """
            CREATE TABLE IF NOT EXISTS performance_alerts (
                id SERIAL PRIMARY KEY,
                alert_type VARCHAR(50) NOT NULL,
                severity VARCHAR(20) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                endpoint VARCHAR(255),
                service_name VARCHAR(100),
                metric_value FLOAT,
                threshold_value FLOAT,
                status VARCHAR(20) DEFAULT 'active' NOT NULL,
                acknowledged_by INTEGER,
                acknowledged_at TIMESTAMP,
                resolved_at TIMESTAMP,
                first_occurrence TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                last_occurrence TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                occurrence_count INTEGER DEFAULT 1 NOT NULL,
                alert_metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_performance_alert_type_status ON performance_alerts(alert_type, status);
            CREATE INDEX IF NOT EXISTS idx_performance_alert_severity ON performance_alerts(severity, first_occurrence);
            CREATE INDEX IF NOT EXISTS idx_performance_alert_endpoint ON performance_alerts(endpoint, status);
            CREATE INDEX IF NOT EXISTS idx_performance_alert_service ON performance_alerts(service_name, status);
            """
        else:
            # SQLite
            return """
            CREATE TABLE IF NOT EXISTS performance_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type VARCHAR(50) NOT NULL,
                severity VARCHAR(20) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                endpoint VARCHAR(255),
                service_name VARCHAR(100),
                metric_value FLOAT,
                threshold_value FLOAT,
                status VARCHAR(20) DEFAULT 'active' NOT NULL,
                acknowledged_by INTEGER,
                acknowledged_at TIMESTAMP,
                resolved_at TIMESTAMP,
                first_occurrence TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                last_occurrence TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                occurrence_count INTEGER DEFAULT 1 NOT NULL,
                alert_metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_performance_alert_type_status ON performance_alerts(alert_type, status);
            CREATE INDEX IF NOT EXISTS idx_performance_alert_severity ON performance_alerts(severity, first_occurrence);
            CREATE INDEX IF NOT EXISTS idx_performance_alert_endpoint ON performance_alerts(endpoint, status);
            CREATE INDEX IF NOT EXISTS idx_performance_alert_service ON performance_alerts(service_name, status);
            """
    
    def _get_performance_metrics_schema(self) -> str:
        """Get SQL schema for performance_metrics table."""
        db_url = str(db.engine.url)
        is_postgresql = 'postgresql' in db_url
        
        if is_postgresql:
            return """
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id SERIAL PRIMARY KEY,
                endpoint VARCHAR(255) NOT NULL,
                method VARCHAR(10) NOT NULL,
                status_code INTEGER NOT NULL,
                response_time_ms FLOAT NOT NULL,
                db_query_time_ms FLOAT DEFAULT 0.0,
                db_query_count INTEGER DEFAULT 0,
                cache_hits INTEGER DEFAULT 0,
                cache_misses INTEGER DEFAULT 0,
                user_id INTEGER,
                tenant_id INTEGER,
                ip_address VARCHAR(45),
                user_agent TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                memory_usage_mb FLOAT,
                cpu_usage_percent FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_performance_endpoint ON performance_metrics(endpoint);
            CREATE INDEX IF NOT EXISTS idx_performance_status_code ON performance_metrics(status_code);
            CREATE INDEX IF NOT EXISTS idx_performance_response_time ON performance_metrics(response_time_ms);
            CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance_metrics(timestamp);
            CREATE INDEX IF NOT EXISTS idx_performance_user ON performance_metrics(user_id);
            CREATE INDEX IF NOT EXISTS idx_performance_endpoint_time ON performance_metrics(endpoint, timestamp);
            CREATE INDEX IF NOT EXISTS idx_performance_slow_requests ON performance_metrics(response_time_ms, timestamp);
            CREATE INDEX IF NOT EXISTS idx_performance_errors ON performance_metrics(status_code, timestamp);
            CREATE INDEX IF NOT EXISTS idx_performance_user_metrics ON performance_metrics(user_id, timestamp);
            """
        else:
            return """
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint VARCHAR(255) NOT NULL,
                method VARCHAR(10) NOT NULL,
                status_code INTEGER NOT NULL,
                response_time_ms FLOAT NOT NULL,
                db_query_time_ms FLOAT DEFAULT 0.0,
                db_query_count INTEGER DEFAULT 0,
                cache_hits INTEGER DEFAULT 0,
                cache_misses INTEGER DEFAULT 0,
                user_id INTEGER,
                tenant_id INTEGER,
                ip_address VARCHAR(45),
                user_agent TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                memory_usage_mb FLOAT,
                cpu_usage_percent FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_performance_endpoint ON performance_metrics(endpoint);
            CREATE INDEX IF NOT EXISTS idx_performance_status_code ON performance_metrics(status_code);
            CREATE INDEX IF NOT EXISTS idx_performance_response_time ON performance_metrics(response_time_ms);
            CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance_metrics(timestamp);
            CREATE INDEX IF NOT EXISTS idx_performance_user ON performance_metrics(user_id);
            CREATE INDEX IF NOT EXISTS idx_performance_endpoint_time ON performance_metrics(endpoint, timestamp);
            CREATE INDEX IF NOT EXISTS idx_performance_slow_requests ON performance_metrics(response_time_ms, timestamp);
            CREATE INDEX IF NOT EXISTS idx_performance_errors ON performance_metrics(status_code, timestamp);
            CREATE INDEX IF NOT EXISTS idx_performance_user_metrics ON performance_metrics(user_id, timestamp);
            """
    
    def _get_slow_queries_schema(self) -> str:
        """Get SQL schema for slow_queries table."""
        db_url = str(db.engine.url)
        is_postgresql = 'postgresql' in db_url
        
        if is_postgresql:
            return """
            CREATE TABLE IF NOT EXISTS slow_queries (
                id SERIAL PRIMARY KEY,
                query_hash VARCHAR(64) NOT NULL,
                query_text TEXT NOT NULL,
                normalized_query TEXT NOT NULL,
                execution_time_ms FLOAT NOT NULL,
                rows_examined INTEGER,
                rows_returned INTEGER,
                endpoint VARCHAR(255),
                user_id INTEGER,
                tenant_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                database_name VARCHAR(100),
                table_names JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_slow_query_hash ON slow_queries(query_hash);
            CREATE INDEX IF NOT EXISTS idx_slow_query_execution_time ON slow_queries(execution_time_ms);
            CREATE INDEX IF NOT EXISTS idx_slow_query_timestamp ON slow_queries(timestamp);
            CREATE INDEX IF NOT EXISTS idx_slow_query_endpoint ON slow_queries(endpoint);
            CREATE INDEX IF NOT EXISTS idx_slow_query_hash_time ON slow_queries(query_hash, timestamp);
            CREATE INDEX IF NOT EXISTS idx_slow_query_execution_time_ts ON slow_queries(execution_time_ms, timestamp);
            CREATE INDEX IF NOT EXISTS idx_slow_query_endpoint_ts ON slow_queries(endpoint, timestamp);
            """
        else:
            return """
            CREATE TABLE IF NOT EXISTS slow_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_hash VARCHAR(64) NOT NULL,
                query_text TEXT NOT NULL,
                normalized_query TEXT NOT NULL,
                execution_time_ms FLOAT NOT NULL,
                rows_examined INTEGER,
                rows_returned INTEGER,
                endpoint VARCHAR(255),
                user_id INTEGER,
                tenant_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                database_name VARCHAR(100),
                table_names TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_slow_query_hash ON slow_queries(query_hash);
            CREATE INDEX IF NOT EXISTS idx_slow_query_execution_time ON slow_queries(execution_time_ms);
            CREATE INDEX IF NOT EXISTS idx_slow_query_timestamp ON slow_queries(timestamp);
            CREATE INDEX IF NOT EXISTS idx_slow_query_endpoint ON slow_queries(endpoint);
            CREATE INDEX IF NOT EXISTS idx_slow_query_hash_time ON slow_queries(query_hash, timestamp);
            CREATE INDEX IF NOT EXISTS idx_slow_query_execution_time_ts ON slow_queries(execution_time_ms, timestamp);
            CREATE INDEX IF NOT EXISTS idx_slow_query_endpoint_ts ON slow_queries(endpoint, timestamp);
            """
    
    def _get_service_health_schema(self) -> str:
        """Get SQL schema for service_health table."""
        db_url = str(db.engine.url)
        is_postgresql = 'postgresql' in db_url
        
        if is_postgresql:
            return """
            CREATE TABLE IF NOT EXISTS service_health (
                id SERIAL PRIMARY KEY,
                service_name VARCHAR(100) NOT NULL,
                service_type VARCHAR(50) NOT NULL,
                endpoint_url VARCHAR(500),
                status VARCHAR(20) NOT NULL,
                response_time_ms FLOAT,
                error_message TEXT,
                check_type VARCHAR(50) NOT NULL,
                last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                next_check TIMESTAMP,
                version VARCHAR(50),
                extra_metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_service_health_name ON service_health(service_name);
            CREATE INDEX IF NOT EXISTS idx_service_health_status ON service_health(status);
            CREATE INDEX IF NOT EXISTS idx_service_health_last_check ON service_health(last_check);
            CREATE INDEX IF NOT EXISTS idx_service_health_next_check ON service_health(next_check);
            CREATE INDEX IF NOT EXISTS idx_service_health_name_status ON service_health(service_name, status);
            """
        else:
            return """
            CREATE TABLE IF NOT EXISTS service_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name VARCHAR(100) NOT NULL,
                service_type VARCHAR(50) NOT NULL,
                endpoint_url VARCHAR(500),
                status VARCHAR(20) NOT NULL,
                response_time_ms FLOAT,
                error_message TEXT,
                check_type VARCHAR(50) NOT NULL,
                last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                next_check TIMESTAMP,
                version VARCHAR(50),
                extra_metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_service_health_name ON service_health(service_name);
            CREATE INDEX IF NOT EXISTS idx_service_health_status ON service_health(status);
            CREATE INDEX IF NOT EXISTS idx_service_health_last_check ON service_health(last_check);
            CREATE INDEX IF NOT EXISTS idx_service_health_next_check ON service_health(next_check);
            CREATE INDEX IF NOT EXISTS idx_service_health_name_status ON service_health(service_name, status);
            """
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a specific table exists.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        try:
            inspector = inspect(db.engine)
            return table_name in inspector.get_table_names()
        except Exception as e:
            logger.error(f"❌ Failed to check if table {table_name} exists: {e}")
            return False
    
    def get_table_info(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary with table information or None if table doesn't exist
        """
        try:
            if not self.table_exists(table_name):
                return None
            
            inspector = inspect(db.engine)
            columns = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            return {
                'name': table_name,
                'columns': [
                    {
                        'name': col['name'],
                        'type': str(col['type']),
                        'nullable': col['nullable'],
                        'default': col.get('default'),
                        'primary_key': col.get('primary_key', False)
                    }
                    for col in columns
                ],
                'indexes': [
                    {
                        'name': idx['name'],
                        'columns': idx['column_names'],
                        'unique': idx['unique']
                    }
                    for idx in indexes
                ],
                'foreign_keys': [
                    {
                        'name': fk['name'],
                        'constrained_columns': fk['constrained_columns'],
                        'referred_table': fk['referred_table'],
                        'referred_columns': fk['referred_columns']
                    }
                    for fk in foreign_keys
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get table info for {table_name}: {e}")
            return None
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get comprehensive database information.
        
        Returns:
            Dictionary with database information
        """
        try:
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            missing_tables = self.check_missing_tables()
            
            return {
                'database_url': str(db.engine.url).split('@')[-1] if '@' in str(db.engine.url) else str(db.engine.url),
                'database_type': db.engine.dialect.name,
                'total_required_tables': len(self.required_tables),
                'existing_tables_count': len(existing_tables),
                'missing_tables_count': len(missing_tables),
                'existing_tables': sorted(existing_tables),
                'missing_tables': sorted(missing_tables),
                'required_tables': sorted(self.required_tables),
                'completion_percentage': round((len(existing_tables) / len(self.required_tables)) * 100, 2) if self.required_tables else 100
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get database info: {e}")
            return {
                'error': str(e),
                'database_type': 'unknown',
                'total_required_tables': len(self.required_tables),
                'existing_tables_count': 0,
                'missing_tables_count': len(self.required_tables),
                'completion_percentage': 0
            }


def get_migration_manager(app=None) -> MigrationManager:
    """
    Get or create migration manager instance.
    
    Args:
        app: Optional Flask app instance
        
    Returns:
        MigrationManager instance
    """
    if app is None:
        app = current_app
    
    if 'migration_manager' not in app.extensions:
        manager = MigrationManager(app)
    else:
        manager = app.extensions['migration_manager']
    
    return manager