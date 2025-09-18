"""
Health Validation System

This module provides comprehensive database health validation functionality
for connectivity testing, schema validation, and diagnostic reporting.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.exc import SQLAlchemyError

from .database_init_logger import get_database_init_logger, LogLevel, LogCategory

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ValidationSeverity(Enum):
    """Validation issue severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


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
class HealthCheckResult:
    """Result of health check process."""
    status: HealthStatus
    checks_passed: int = 0
    checks_failed: int = 0
    checks_total: int = 0
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_issue(self, issue: str, severity: HealthStatus = HealthStatus.CRITICAL):
        """Add a health issue."""
        if severity == HealthStatus.CRITICAL:
            self.issues.append(issue)
            self.checks_failed += 1
        else:
            self.warnings.append(issue)
        
        self.checks_total += 1
        
        # Update overall status
        if severity == HealthStatus.CRITICAL and self.status != HealthStatus.CRITICAL:
            self.status = HealthStatus.CRITICAL
        elif severity == HealthStatus.WARNING and self.status == HealthStatus.HEALTHY:
            self.status = HealthStatus.WARNING
    
    def add_success(self, check_name: str):
        """Add a successful check."""
        self.checks_passed += 1
        self.checks_total += 1
        logger.info(f"✅ Health check passed: {check_name}")


class HealthValidator:
    """
    Database health validation system.
    
    Provides comprehensive health checks including connectivity testing,
    schema validation, and diagnostic reporting.
    """
    
    def __init__(self, app: Flask, db: SQLAlchemy):
        self.app = app
        self.db = db
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize logging system
        log_level = LogLevel.DEBUG if app.debug else LogLevel.INFO
        self.init_logger = get_database_init_logger("health_validator", log_level)
        
        # Health check configuration
        self.connection_timeout = app.config.get('DATABASE_CONNECTION_TIMEOUT', 30)
        self.query_timeout = app.config.get('DATABASE_QUERY_TIMEOUT', 10)
        self.max_retries = app.config.get('DATABASE_MAX_RETRIES', 3)
    
    def validate_connectivity(self) -> bool:
        """
        Validate database connectivity.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            self.init_logger.info(LogCategory.VALIDATION, "Testing database connectivity...")
            
            # Test basic connection
            with self.db.engine.connect() as conn:
                result = conn.execute(text('SELECT 1'))
                row = result.fetchone()
                
                if row and row[0] == 1:
                    self.init_logger.info(LogCategory.VALIDATION, "✅ Database connectivity test passed")
                    return True
                else:
                    self.init_logger.error(LogCategory.VALIDATION, "❌ Database connectivity test failed: Invalid response")
                    return False
        
        except Exception as e:
            self.init_logger.error(
                LogCategory.VALIDATION,
                f"❌ Database connectivity test failed: {str(e)}",
                error=e
            )
            return False
    
    def validate_schema_integrity(self) -> ValidationResult:
        """
        Validate database schema integrity.
        
        Returns:
            ValidationResult with schema validation details
        """
        result = ValidationResult(valid=True)
        
        try:
            self.init_logger.info(LogCategory.VALIDATION, "Validating database schema integrity...")
            
            # Get database inspector
            inspector = inspect(self.db.engine)
            
            # Check if tables exist
            existing_tables = inspector.get_table_names()
            
            # Define expected core tables
            expected_tables = [
                'tenants', 'users', 'roles', 'user_roles',
                'channels', 'threads', 'inbox_messages',
                'contacts', 'leads', 'tasks', 'notes',
                'knowledge_sources', 'documents', 'chunks', 'embeddings',
                'plans', 'subscriptions', 'usage_events', 'invoices',
                'counterparties', 'kyb_alerts', 'audit_logs'
            ]
            
            # Check for missing tables
            missing_tables = [table for table in expected_tables if table not in existing_tables]
            if missing_tables:
                result.valid = False
                for table in missing_tables:
                    result.add_issue(f"Missing table: {table}", ValidationSeverity.CRITICAL)
                    result.add_suggestion(f"Create table '{table}' using database migrations")
            
            # Check table structures for critical tables
            critical_tables = ['tenants', 'users', 'roles']
            for table_name in critical_tables:
                if table_name in existing_tables:
                    self._validate_table_structure(inspector, table_name, result)
            
            # Check for orphaned tables
            orphaned_tables = [table for table in existing_tables if table not in expected_tables and not table.startswith('alembic')]
            if orphaned_tables:
                for table in orphaned_tables:
                    result.add_issue(f"Orphaned table found: {table}", ValidationSeverity.WARNING)
                    result.add_suggestion(f"Review table '{table}' - may be leftover from old migrations")
            
            result.details['existing_tables'] = existing_tables
            result.details['expected_tables'] = expected_tables
            result.details['missing_tables'] = missing_tables
            result.details['orphaned_tables'] = orphaned_tables
            
            if result.valid:
                self.init_logger.info(LogCategory.VALIDATION, "✅ Schema integrity validation passed")
            else:
                self.init_logger.error(LogCategory.VALIDATION, f"❌ Schema integrity validation failed: {len(result.issues)} issues found")
        
        except Exception as e:
            result.valid = False
            result.add_issue(f"Schema validation failed with exception: {str(e)}", ValidationSeverity.CRITICAL)
            self.init_logger.error(
                LogCategory.VALIDATION,
                f"❌ Schema validation failed with exception: {str(e)}",
                error=e
            )
        
        return result
    
    def validate_data_integrity(self) -> ValidationResult:
        """
        Validate database data integrity.
        
        Returns:
            ValidationResult with data validation details
        """
        result = ValidationResult(valid=True)
        
        try:
            self.init_logger.info(LogCategory.VALIDATION, "Validating database data integrity...")
            
            # Check for essential system data
            self._validate_system_tenant(result)
            self._validate_admin_user(result)
            self._validate_system_roles(result)
            
            # Check for data consistency
            self._validate_data_consistency(result)
            
            if result.valid:
                self.init_logger.info(LogCategory.VALIDATION, "✅ Data integrity validation passed")
            else:
                self.init_logger.error(LogCategory.VALIDATION, f"❌ Data integrity validation failed: {len(result.issues)} issues found")
        
        except Exception as e:
            result.valid = False
            result.add_issue(f"Data validation failed with exception: {str(e)}", ValidationSeverity.CRITICAL)
            self.init_logger.error(
                LogCategory.VALIDATION,
                f"❌ Data validation failed with exception: {str(e)}",
                error=e
            )
        
        return result
    
    def generate_health_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive health report.
        
        Returns:
            Dictionary with health report details
        """
        start_time = time.time()
        
        self.init_logger.info(LogCategory.VALIDATION, "Generating comprehensive health report...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'database_type': self._get_database_type(),
            'connectivity': {
                'status': 'unknown',
                'details': {}
            },
            'schema': {
                'status': 'unknown',
                'details': {}
            },
            'data': {
                'status': 'unknown',
                'details': {}
            },
            'overall_status': HealthStatus.UNKNOWN.value,
            'recommendations': [],
            'duration': 0.0
        }
        
        try:
            # Test connectivity
            connectivity_ok = self.validate_connectivity()
            report['connectivity']['status'] = 'healthy' if connectivity_ok else 'critical'
            
            if connectivity_ok:
                # Validate schema
                schema_result = self.validate_schema_integrity()
                report['schema']['status'] = 'healthy' if schema_result.valid else 'critical'
                report['schema']['details'] = {
                    'issues': schema_result.issues,
                    'suggestions': schema_result.suggestions,
                    'table_info': schema_result.details
                }
                
                # Validate data
                data_result = self.validate_data_integrity()
                report['data']['status'] = 'healthy' if data_result.valid else 'critical'
                report['data']['details'] = {
                    'issues': data_result.issues,
                    'suggestions': data_result.suggestions,
                    'data_info': data_result.details
                }
                
                # Determine overall status
                if connectivity_ok and schema_result.valid and data_result.valid:
                    report['overall_status'] = HealthStatus.HEALTHY.value
                elif not connectivity_ok:
                    report['overall_status'] = HealthStatus.CRITICAL.value
                    report['recommendations'].append("Fix database connectivity issues before proceeding")
                elif not schema_result.valid:
                    report['overall_status'] = HealthStatus.CRITICAL.value
                    report['recommendations'].extend(schema_result.suggestions)
                elif not data_result.valid:
                    report['overall_status'] = HealthStatus.WARNING.value
                    report['recommendations'].extend(data_result.suggestions)
            else:
                report['overall_status'] = HealthStatus.CRITICAL.value
                report['recommendations'].append("Database connectivity must be restored")
        
        except Exception as e:
            report['overall_status'] = HealthStatus.CRITICAL.value
            report['error'] = str(e)
            report['recommendations'].append("Investigate health check system errors")
            self.init_logger.error(
                LogCategory.VALIDATION,
                f"❌ Health report generation failed: {str(e)}",
                error=e
            )
        
        finally:
            report['duration'] = time.time() - start_time
            self.init_logger.info(
                LogCategory.VALIDATION,
                f"Health report generated in {report['duration']:.2f}s - Status: {report['overall_status']}"
            )
        
        return report
    
    def run_comprehensive_health_check(self) -> HealthCheckResult:
        """
        Run comprehensive health check.
        
        Returns:
            HealthCheckResult with complete health assessment
        """
        start_time = time.time()
        result = HealthCheckResult(status=HealthStatus.HEALTHY)
        
        self.init_logger.info(LogCategory.VALIDATION, "Running comprehensive health check...")
        
        try:
            # Check 1: Database connectivity
            if self.validate_connectivity():
                result.add_success("Database connectivity")
            else:
                result.add_issue("Database connectivity failed", HealthStatus.CRITICAL)
            
            # Check 2: Schema integrity
            schema_result = self.validate_schema_integrity()
            if schema_result.valid:
                result.add_success("Schema integrity")
            else:
                result.add_issue(f"Schema integrity failed: {len(schema_result.issues)} issues", HealthStatus.CRITICAL)
                result.details['schema_issues'] = schema_result.issues
            
            # Check 3: Data integrity
            data_result = self.validate_data_integrity()
            if data_result.valid:
                result.add_success("Data integrity")
            else:
                result.add_issue(f"Data integrity failed: {len(data_result.issues)} issues", HealthStatus.WARNING)
                result.details['data_issues'] = data_result.issues
            
            # Check 4: Performance metrics
            perf_result = self._check_performance_metrics()
            if perf_result['status'] == 'healthy':
                result.add_success("Performance metrics")
            else:
                result.add_issue(f"Performance issues detected: {perf_result['message']}", HealthStatus.WARNING)
                result.details['performance'] = perf_result
        
        except Exception as e:
            result.add_issue(f"Health check failed with exception: {str(e)}", HealthStatus.CRITICAL)
            self.init_logger.error(
                LogCategory.VALIDATION,
                f"❌ Comprehensive health check failed: {str(e)}",
                error=e
            )
        
        finally:
            result.duration = time.time() - start_time
            
            # Log final status
            if result.status == HealthStatus.HEALTHY:
                self.init_logger.info(
                    LogCategory.VALIDATION,
                    f"✅ Health check completed: {result.checks_passed}/{result.checks_total} checks passed"
                )
            else:
                self.init_logger.error(
                    LogCategory.VALIDATION,
                    f"❌ Health check completed with issues: {result.checks_failed} failed, {len(result.warnings)} warnings"
                )
        
        return result
    
    def _validate_table_structure(self, inspector, table_name: str, result: ValidationResult):
        """Validate structure of a specific table."""
        try:
            columns = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            # Define expected columns for critical tables
            expected_columns = {
                'tenants': ['id', 'name', 'slug', 'is_active', 'created_at'],
                'users': ['id', 'tenant_id', 'email', 'password_hash', 'is_active', 'created_at'],
                'roles': ['id', 'tenant_id', 'name', 'permissions', 'is_system_role', 'created_at']
            }
            
            if table_name in expected_columns:
                existing_columns = [col['name'] for col in columns]
                missing_columns = [col for col in expected_columns[table_name] if col not in existing_columns]
                
                if missing_columns:
                    result.add_issue(f"Table '{table_name}' missing columns: {missing_columns}", ValidationSeverity.ERROR)
                    result.add_suggestion(f"Add missing columns to table '{table_name}'")
            
            result.details[f'{table_name}_structure'] = {
                'columns': len(columns),
                'indexes': len(indexes),
                'foreign_keys': len(foreign_keys)
            }
        
        except Exception as e:
            result.add_issue(f"Failed to validate table '{table_name}' structure: {str(e)}", ValidationSeverity.WARNING)
    
    def _validate_system_tenant(self, result: ValidationResult):
        """Validate system tenant exists."""
        try:
            from app.models import Tenant
            
            system_tenant = Tenant.query.filter_by(slug='ai-secretary-system').first()
            if not system_tenant:
                result.add_issue("System tenant not found", ValidationSeverity.CRITICAL)
                result.add_suggestion("Run data seeding to create system tenant")
            else:
                result.details['system_tenant'] = {
                    'id': system_tenant.id,
                    'name': system_tenant.name,
                    'is_active': system_tenant.is_active
                }
        
        except Exception as e:
            result.add_issue(f"Failed to validate system tenant: {str(e)}", ValidationSeverity.ERROR)
    
    def _validate_admin_user(self, result: ValidationResult):
        """Validate admin user exists."""
        try:
            from app.models import User
            
            admin_user = User.query.filter_by(email='admin@ai-secretary.com').first()
            if not admin_user:
                result.add_issue("Admin user not found", ValidationSeverity.CRITICAL)
                result.add_suggestion("Run data seeding to create admin user")
            else:
                result.details['admin_user'] = {
                    'id': admin_user.id,
                    'email': admin_user.email,
                    'is_active': admin_user.is_active,
                    'role': admin_user.role
                }
        
        except Exception as e:
            result.add_issue(f"Failed to validate admin user: {str(e)}", ValidationSeverity.ERROR)
    
    def _validate_system_roles(self, result: ValidationResult):
        """Validate system roles exist."""
        try:
            from app.models import Role
            
            system_roles = Role.query.filter_by(is_system_role=True).all()
            expected_roles = ['Owner', 'Manager', 'Support', 'Accounting', 'Read Only']
            
            existing_role_names = [role.name for role in system_roles]
            missing_roles = [name for name in expected_roles if name not in existing_role_names]
            
            if missing_roles:
                result.add_issue(f"Missing system roles: {missing_roles}", ValidationSeverity.CRITICAL)
                result.add_suggestion("Run data seeding to create missing system roles")
            
            result.details['system_roles'] = {
                'total': len(system_roles),
                'expected': len(expected_roles),
                'missing': missing_roles
            }
        
        except Exception as e:
            result.add_issue(f"Failed to validate system roles: {str(e)}", ValidationSeverity.ERROR)
    
    def _validate_data_consistency(self, result: ValidationResult):
        """Validate data consistency across tables."""
        try:
            # Check for orphaned records
            self._check_orphaned_users(result)
            self._check_orphaned_roles(result)
            
        except Exception as e:
            result.add_issue(f"Failed to validate data consistency: {str(e)}", ValidationSeverity.WARNING)
    
    def _check_orphaned_users(self, result: ValidationResult):
        """Check for users without valid tenants."""
        try:
            from app.models import User, Tenant
            
            # Find users with non-existent tenant_id
            orphaned_users = self.db.session.query(User).outerjoin(Tenant).filter(Tenant.id.is_(None)).count()
            
            if orphaned_users > 0:
                result.add_issue(f"Found {orphaned_users} orphaned users", ValidationSeverity.WARNING)
                result.add_suggestion("Clean up orphaned user records")
            
            result.details['orphaned_users'] = orphaned_users
        
        except Exception as e:
            result.add_issue(f"Failed to check orphaned users: {str(e)}", ValidationSeverity.WARNING)
    
    def _check_orphaned_roles(self, result: ValidationResult):
        """Check for roles without valid tenants."""
        try:
            from app.models import Role, Tenant
            
            # Find roles with non-existent tenant_id
            orphaned_roles = self.db.session.query(Role).outerjoin(Tenant).filter(Tenant.id.is_(None)).count()
            
            if orphaned_roles > 0:
                result.add_issue(f"Found {orphaned_roles} orphaned roles", ValidationSeverity.WARNING)
                result.add_suggestion("Clean up orphaned role records")
            
            result.details['orphaned_roles'] = orphaned_roles
        
        except Exception as e:
            result.add_issue(f"Failed to check orphaned roles: {str(e)}", ValidationSeverity.WARNING)
    
    def _check_performance_metrics(self) -> Dict[str, Any]:
        """Check database performance metrics."""
        try:
            start_time = time.time()
            
            # Simple query performance test
            with self.db.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            
            query_time = time.time() - start_time
            
            if query_time > 1.0:  # More than 1 second for simple query
                return {
                    'status': 'warning',
                    'message': f'Slow query performance: {query_time:.2f}s',
                    'query_time': query_time
                }
            else:
                return {
                    'status': 'healthy',
                    'message': f'Good query performance: {query_time:.3f}s',
                    'query_time': query_time
                }
        
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Performance check failed: {str(e)}',
                'error': str(e)
            }
    
    def _get_database_type(self) -> str:
        """Get database type from engine."""
        try:
            return self.db.engine.dialect.name
        except:
            return 'unknown'
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get current health status summary.
        
        Returns:
            Dictionary with health status summary
        """
        try:
            connectivity = self.validate_connectivity()
            
            status = {
                'overall_status': HealthStatus.HEALTHY.value if connectivity else HealthStatus.CRITICAL.value,
                'connectivity': connectivity,
                'database_type': self._get_database_type(),
                'last_check': datetime.now().isoformat(),
                'checks': {
                    'connectivity': 'passed' if connectivity else 'failed',
                    'schema': 'unknown',
                    'data': 'unknown'
                }
            }
            
            if connectivity:
                # Quick schema check
                try:
                    inspector = inspect(self.db.engine)
                    tables = inspector.get_table_names()
                    status['checks']['schema'] = 'passed' if len(tables) > 0 else 'failed'
                except:
                    status['checks']['schema'] = 'failed'
                
                # Quick data check
                try:
                    from app.models import Tenant
                    tenant_count = Tenant.query.count()
                    status['checks']['data'] = 'passed' if tenant_count > 0 else 'warning'
                except:
                    status['checks']['data'] = 'failed'
            
            return status
        
        except Exception as e:
            return {
                'overall_status': HealthStatus.CRITICAL.value,
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }