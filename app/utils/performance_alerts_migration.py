"""
Performance Alerts Table Migration

This module provides specific migration functionality for the performance_alerts table,
including both PostgreSQL and SQLite compatible schemas with proper indexes and constraints.
"""

import logging
from typing import Dict, Any, Optional, List
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


class PerformanceAlertsMigration:
    """
    Handles creation and management of the performance_alerts table.
    
    This class provides database-agnostic table creation with proper
    indexes and constraints for both PostgreSQL and SQLite.
    """
    
    def __init__(self):
        """Initialize the migration."""
        self.table_name = 'performance_alerts'
        self.required_indexes = [
            'idx_performance_alert_type_status',
            'idx_performance_alert_severity',
            'idx_performance_alert_endpoint',
            'idx_performance_alert_service'
        ]
    
    def create_table(self) -> Dict[str, Any]:
        """
        Create the performance_alerts table with appropriate schema.
        
        Returns:
            Dictionary with creation result details
        """
        result = {
            'success': False,
            'table_created': False,
            'indexes_created': [],
            'errors': [],
            'warnings': [],
            'database_type': None
        }
        
        try:
            # Detect database type
            db_url = str(db.engine.url)
            is_postgresql = 'postgresql' in db_url.lower()
            is_sqlite = 'sqlite' in db_url.lower()
            
            result['database_type'] = 'postgresql' if is_postgresql else 'sqlite' if is_sqlite else 'unknown'
            
            logger.info(f"🔄 Creating performance_alerts table for {result['database_type']} database...")
            
            # Check if table already exists
            if self.table_exists():
                logger.info("✅ performance_alerts table already exists")
                result['success'] = True
                result['warnings'].append("Table already exists")
                
                # Check and create missing indexes
                missing_indexes = self.get_missing_indexes()
                if missing_indexes:
                    created_indexes = self.create_missing_indexes(missing_indexes)
                    result['indexes_created'] = created_indexes
                
                return result
            
            # Create table with appropriate schema
            if is_postgresql:
                success = self._create_postgresql_table()
            elif is_sqlite:
                success = self._create_sqlite_table()
            else:
                # Default to SQLite schema for unknown databases
                logger.warning(f"Unknown database type, using SQLite schema")
                success = self._create_sqlite_table()
            
            if success:
                result['success'] = True
                result['table_created'] = True
                result['indexes_created'] = self.required_indexes.copy()
                logger.info("✅ Successfully created performance_alerts table")
            else:
                result['errors'].append("Failed to create table")
                logger.error("❌ Failed to create performance_alerts table")
                
        except Exception as e:
            logger.error(f"❌ Error creating performance_alerts table: {e}")
            result['errors'].append(str(e))
        
        return result
    
    def _create_postgresql_table(self) -> bool:
        """Create performance_alerts table with PostgreSQL schema."""
        try:
            sql_statements = [
                """
                CREATE TABLE performance_alerts (
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
                """,
                """
                CREATE INDEX idx_performance_alert_type_status 
                ON performance_alerts(alert_type, status);
                """,
                """
                CREATE INDEX idx_performance_alert_severity 
                ON performance_alerts(severity, first_occurrence);
                """,
                """
                CREATE INDEX idx_performance_alert_endpoint 
                ON performance_alerts(endpoint, status);
                """,
                """
                CREATE INDEX idx_performance_alert_service 
                ON performance_alerts(service_name, status);
                """,
                """
                CREATE INDEX idx_performance_alert_occurrence 
                ON performance_alerts(first_occurrence DESC);
                """,
                """
                CREATE INDEX idx_performance_alert_status_time 
                ON performance_alerts(status, last_occurrence DESC);
                """
            ]
            
            with db.engine.connect() as connection:
                for sql in sql_statements:
                    connection.execute(text(sql.strip()))
                connection.commit()
            
            logger.info("✅ Created PostgreSQL performance_alerts table with indexes")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create PostgreSQL table: {e}")
            return False
    
    def _create_sqlite_table(self) -> bool:
        """Create performance_alerts table with SQLite schema."""
        try:
            sql_statements = [
                """
                CREATE TABLE performance_alerts (
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
                """,
                """
                CREATE INDEX idx_performance_alert_type_status 
                ON performance_alerts(alert_type, status);
                """,
                """
                CREATE INDEX idx_performance_alert_severity 
                ON performance_alerts(severity, first_occurrence);
                """,
                """
                CREATE INDEX idx_performance_alert_endpoint 
                ON performance_alerts(endpoint, status);
                """,
                """
                CREATE INDEX idx_performance_alert_service 
                ON performance_alerts(service_name, status);
                """,
                """
                CREATE INDEX idx_performance_alert_occurrence 
                ON performance_alerts(first_occurrence DESC);
                """,
                """
                CREATE INDEX idx_performance_alert_status_time 
                ON performance_alerts(status, last_occurrence DESC);
                """
            ]
            
            with db.engine.connect() as connection:
                for sql in sql_statements:
                    connection.execute(text(sql.strip()))
                connection.commit()
            
            logger.info("✅ Created SQLite performance_alerts table with indexes")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create SQLite table: {e}")
            return False
    
    def table_exists(self) -> bool:
        """Check if the performance_alerts table exists."""
        try:
            inspector = inspect(db.engine)
            return self.table_name in inspector.get_table_names()
        except Exception as e:
            logger.error(f"❌ Failed to check if table exists: {e}")
            return False
    
    def get_missing_indexes(self) -> List[str]:
        """Get list of missing indexes for the performance_alerts table."""
        try:
            if not self.table_exists():
                return self.required_indexes.copy()
            
            inspector = inspect(db.engine)
            existing_indexes = inspector.get_indexes(self.table_name)
            existing_index_names = {idx['name'] for idx in existing_indexes}
            
            missing_indexes = []
            for required_index in self.required_indexes:
                if required_index not in existing_index_names:
                    missing_indexes.append(required_index)
            
            return missing_indexes
            
        except Exception as e:
            logger.error(f"❌ Failed to check missing indexes: {e}")
            return self.required_indexes.copy()
    
    def create_missing_indexes(self, missing_indexes: List[str]) -> List[str]:
        """Create missing indexes for the performance_alerts table."""
        created_indexes = []
        
        # Define index creation SQL
        index_sql = {
            'idx_performance_alert_type_status': 
                "CREATE INDEX idx_performance_alert_type_status ON performance_alerts(alert_type, status);",
            'idx_performance_alert_severity': 
                "CREATE INDEX idx_performance_alert_severity ON performance_alerts(severity, first_occurrence);",
            'idx_performance_alert_endpoint': 
                "CREATE INDEX idx_performance_alert_endpoint ON performance_alerts(endpoint, status);",
            'idx_performance_alert_service': 
                "CREATE INDEX idx_performance_alert_service ON performance_alerts(service_name, status);"
        }
        
        try:
            with db.engine.connect() as connection:
                for index_name in missing_indexes:
                    if index_name in index_sql:
                        try:
                            connection.execute(text(index_sql[index_name]))
                            created_indexes.append(index_name)
                            logger.info(f"✅ Created index: {index_name}")
                        except Exception as e:
                            logger.error(f"❌ Failed to create index {index_name}: {e}")
                
                connection.commit()
                
        except Exception as e:
            logger.error(f"❌ Failed to create indexes: {e}")
        
        return created_indexes
    
    def validate_table_schema(self) -> Dict[str, Any]:
        """Validate the performance_alerts table schema."""
        validation_result = {
            'valid': True,
            'table_exists': False,
            'required_columns': [],
            'missing_columns': [],
            'extra_columns': [],
            'required_indexes': [],
            'missing_indexes': [],
            'issues': [],
            'warnings': []
        }
        
        try:
            # Check if table exists
            validation_result['table_exists'] = self.table_exists()
            
            if not validation_result['table_exists']:
                validation_result['valid'] = False
                validation_result['issues'].append("Table does not exist")
                return validation_result
            
            # Define required columns
            required_columns = {
                'id', 'alert_type', 'severity', 'title', 'description',
                'endpoint', 'service_name', 'metric_value', 'threshold_value',
                'status', 'acknowledged_by', 'acknowledged_at', 'resolved_at',
                'first_occurrence', 'last_occurrence', 'occurrence_count',
                'alert_metadata', 'created_at', 'updated_at'
            }
            
            # Get actual table schema
            inspector = inspect(db.engine)
            columns = inspector.get_columns(self.table_name)
            actual_columns = {col['name'] for col in columns}
            
            # Check columns
            validation_result['required_columns'] = list(required_columns)
            validation_result['missing_columns'] = list(required_columns - actual_columns)
            validation_result['extra_columns'] = list(actual_columns - required_columns)
            
            if validation_result['missing_columns']:
                validation_result['valid'] = False
                validation_result['issues'].extend([
                    f"Missing column: {col}" for col in validation_result['missing_columns']
                ])
            
            if validation_result['extra_columns']:
                validation_result['warnings'].extend([
                    f"Extra column: {col}" for col in validation_result['extra_columns']
                ])
            
            # Check indexes
            validation_result['required_indexes'] = self.required_indexes.copy()
            validation_result['missing_indexes'] = self.get_missing_indexes()
            
            if validation_result['missing_indexes']:
                validation_result['warnings'].extend([
                    f"Missing index: {idx}" for idx in validation_result['missing_indexes']
                ])
            
            logger.info(f"🔍 Table validation: {'✅ Valid' if validation_result['valid'] else '❌ Invalid'}")
            
        except Exception as e:
            logger.error(f"❌ Failed to validate table schema: {e}")
            validation_result['valid'] = False
            validation_result['issues'].append(f"Validation failed: {str(e)}")
        
        return validation_result
    
    def drop_table(self) -> bool:
        """Drop the performance_alerts table (for testing/cleanup)."""
        try:
            if not self.table_exists():
                logger.info("✅ performance_alerts table does not exist")
                return True
            
            with db.engine.connect() as connection:
                connection.execute(text(f"DROP TABLE {self.table_name}"))
                connection.commit()
            
            logger.info("✅ Dropped performance_alerts table")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to drop table: {e}")
            return False
    
    def get_table_info(self) -> Dict[str, Any]:
        """Get comprehensive information about the performance_alerts table."""
        try:
            if not self.table_exists():
                return {
                    'exists': False,
                    'error': 'Table does not exist'
                }
            
            inspector = inspect(db.engine)
            columns = inspector.get_columns(self.table_name)
            indexes = inspector.get_indexes(self.table_name)
            
            # Get row count
            with db.engine.connect() as connection:
                result = connection.execute(text(f"SELECT COUNT(*) FROM {self.table_name}"))
                row_count = result.scalar()
            
            return {
                'exists': True,
                'name': self.table_name,
                'row_count': row_count,
                'column_count': len(columns),
                'index_count': len(indexes),
                'columns': [
                    {
                        'name': col['name'],
                        'type': str(col['type']),
                        'nullable': col['nullable'],
                        'default': str(col.get('default')) if col.get('default') else None,
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
                'database_type': str(db.engine.dialect.name)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get table info: {e}")
            return {
                'exists': False,
                'error': str(e)
            }


def create_performance_alerts_table() -> Dict[str, Any]:
    """
    Convenience function to create the performance_alerts table.
    
    Returns:
        Dictionary with creation result
    """
    migration = PerformanceAlertsMigration()
    return migration.create_table()


def validate_performance_alerts_table() -> Dict[str, Any]:
    """
    Convenience function to validate the performance_alerts table.
    
    Returns:
        Dictionary with validation result
    """
    migration = PerformanceAlertsMigration()
    return migration.validate_table_schema()


def get_performance_alerts_table_info() -> Dict[str, Any]:
    """
    Convenience function to get performance_alerts table information.
    
    Returns:
        Dictionary with table information
    """
    migration = PerformanceAlertsMigration()
    return migration.get_table_info()