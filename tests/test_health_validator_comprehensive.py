"""
Comprehensive tests for HealthValidator class.

This module provides comprehensive unit and integration tests for the health
validation system, covering connectivity testing, schema validation, and
diagnostic reporting.
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from app.utils.health_validator import (
    HealthValidator, ValidationResult, HealthCheckResult, 
    HealthStatus, ValidationSeverity
)


class TestHealthValidator:
    """Test cases for HealthValidator class."""
    
    @pytest.fixture
    def mock_app(self):
        """Create mock Flask app."""
        app = Mock()
        app.config = {
            'DATABASE_CONNECTION_TIMEOUT': 30,
            'DATABASE_QUERY_TIMEOUT': 10,
            'DATABASE_MAX_RETRIES': 3
        }
        app.debug = False
        return app
    
    @pytest.fixture
    def mock_db(self):
        """Create mock SQLAlchemy instance."""
        db = Mock()
        db.engine = Mock()
        db.session = Mock()
        return db
    
    @pytest.fixture
    def validator(self, mock_app, mock_db):
        """Create HealthValidator instance."""
        with patch('app.utils.health_validator.get_database_init_logger') as mock_logger:
            mock_logger.return_value = Mock()
            return HealthValidator(mock_app, mock_db)
    
    def test_initialization(self, mock_app, mock_db):
        """Test HealthValidator initialization."""
        with patch('app.utils.health_validator.get_database_init_logger') as mock_logger:
            mock_logger.return_value = Mock()
            validator = HealthValidator(mock_app, mock_db)
            
            assert validator.app == mock_app
            assert validator.db == mock_db
            assert validator.connection_timeout == 30
            assert validator.query_timeout == 10
            assert validator.max_retries == 3
    
    def test_validate_connectivity_success(self, validator):
        """Test successful connectivity validation."""
        # Mock successful connection
        mock_connection = Mock()
        mock_result = Mock()
        mock_result.fetchone.return_value = (1,)
        mock_connection.execute.return_value = mock_result
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        
        validator.db.engine.connect.return_value = mock_connection
        
        result = validator.validate_connectivity()
        
        assert result is True
    
    def test_validate_connectivity_failure(self, validator):
        """Test connectivity validation failure."""
        # Mock connection failure
        validator.db.engine.connect.side_effect = Exception("Connection failed")
        
        result = validator.validate_connectivity()
        
        assert result is False
    
    def test_validate_connectivity_invalid_response(self, validator):
        """Test connectivity validation with invalid response."""
        # Mock connection with invalid response
        mock_connection = Mock()
        mock_result = Mock()
        mock_result.fetchone.return_value = (0,)  # Invalid response
        mock_connection.execute.return_value = mock_result
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        
        validator.db.engine.connect.return_value = mock_connection
        
        result = validator.validate_connectivity()
        
        assert result is False
    
    @patch('app.utils.health_validator.inspect')
    def test_validate_schema_integrity_success(self, mock_inspect, validator):
        """Test successful schema integrity validation."""
        # Mock inspector with all expected tables
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = [
            'tenants', 'users', 'roles', 'user_roles',
            'channels', 'threads', 'inbox_messages',
            'contacts', 'leads', 'tasks', 'notes',
            'knowledge_sources', 'documents', 'chunks', 'embeddings',
            'plans', 'subscriptions', 'usage_events', 'invoices',
            'counterparties', 'kyb_alerts', 'audit_logs'
        ]
        mock_inspect.return_value = mock_inspector
        
        # Mock table structure validation
        validator._validate_table_structure = Mock()
        
        result = validator.validate_schema_integrity()
        
        assert result.valid is True
        assert len(result.issues) == 0
        assert 'existing_tables' in result.details
        assert 'missing_tables' in result.details
        assert len(result.details['missing_tables']) == 0
    
    @patch('app.utils.health_validator.inspect')
    def test_validate_schema_integrity_missing_tables(self, mock_inspect, validator):
        """Test schema integrity validation with missing tables."""
        # Mock inspector with missing tables
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ['tenants', 'users']  # Missing many tables
        mock_inspect.return_value = mock_inspector
        
        result = validator.validate_schema_integrity()
        
        assert result.valid is False
        assert len(result.issues) > 0
        assert any('Missing table:' in issue for issue in result.issues)
        assert len(result.details['missing_tables']) > 0
    
    @patch('app.utils.health_validator.inspect')
    def test_validate_schema_integrity_orphaned_tables(self, mock_inspect, validator):
        """Test schema integrity validation with orphaned tables."""
        # Mock inspector with orphaned tables
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = [
            'tenants', 'users', 'roles', 'user_roles',
            'channels', 'threads', 'inbox_messages',
            'contacts', 'leads', 'tasks', 'notes',
            'knowledge_sources', 'documents', 'chunks', 'embeddings',
            'plans', 'subscriptions', 'usage_events', 'invoices',
            'counterparties', 'kyb_alerts', 'audit_logs',
            'old_table', 'deprecated_table'  # Orphaned tables
        ]
        mock_inspect.return_value = mock_inspector
        
        validator._validate_table_structure = Mock()
        
        result = validator.validate_schema_integrity()
        
        assert result.valid is True  # Orphaned tables are warnings, not errors
        assert any('Orphaned table found:' in issue for issue in result.issues)
        assert len(result.details['orphaned_tables']) == 2
    
    @patch('app.utils.health_validator.inspect')
    def test_validate_schema_integrity_exception(self, mock_inspect, validator):
        """Test schema integrity validation with exception."""
        mock_inspect.side_effect = Exception("Inspector failed")
        
        result = validator.validate_schema_integrity()
        
        assert result.valid is False
        assert any('Schema validation failed with exception' in issue for issue in result.issues)
    
    @patch('app.utils.health_validator.Tenant')
    @patch('app.utils.health_validator.User')
    @patch('app.utils.health_validator.Role')
    def test_validate_data_integrity_success(self, mock_role, mock_user, mock_tenant, validator):
        """Test successful data integrity validation."""
        # Mock system tenant exists
        mock_system_tenant = Mock()
        mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
        
        # Mock admin user exists
        mock_admin_user = Mock()
        mock_user.query.filter_by.return_value.first.return_value = mock_admin_user
        
        # Mock system roles exist
        mock_system_roles = [Mock() for _ in range(5)]
        mock_role.query.filter_by.return_value.all.return_value = mock_system_roles
        
        # Mock data consistency checks
        validator._validate_data_consistency = Mock()
        
        result = validator.validate_data_integrity()
        
        assert result.valid is True
        assert len(result.issues) == 0
    
    @patch('app.utils.health_validator.Tenant')
    def test_validate_data_integrity_missing_system_tenant(self, mock_tenant, validator):
        """Test data integrity validation with missing system tenant."""
        mock_tenant.query.filter_by.return_value.first.return_value = None
        
        result = validator.validate_data_integrity()
        
        assert result.valid is False
        assert any('System tenant not found' in issue for issue in result.issues)
    
    @patch('app.utils.health_validator.Tenant')
    @patch('app.utils.health_validator.User')
    def test_validate_data_integrity_missing_admin_user(self, mock_user, mock_tenant, validator):
        """Test data integrity validation with missing admin user."""
        # Mock system tenant exists
        mock_system_tenant = Mock()
        mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
        
        # Mock admin user doesn't exist
        mock_user.query.filter_by.return_value.first.return_value = None
        
        result = validator.validate_data_integrity()
        
        assert result.valid is False
        assert any('Admin user not found' in issue for issue in result.issues)
    
    @patch('app.utils.health_validator.Tenant')
    @patch('app.utils.health_validator.User')
    @patch('app.utils.health_validator.Role')
    def test_validate_data_integrity_missing_system_roles(self, mock_role, mock_user, mock_tenant, validator):
        """Test data integrity validation with missing system roles."""
        # Mock system tenant and admin user exist
        mock_system_tenant = Mock()
        mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
        
        mock_admin_user = Mock()
        mock_user.query.filter_by.return_value.first.return_value = mock_admin_user
        
        # Mock missing system roles
        mock_role.query.filter_by.return_value.all.return_value = []  # No roles
        mock_role.query.filter_by.return_value.first.return_value = None  # No specific roles
        
        result = validator.validate_data_integrity()
        
        assert result.valid is False
        assert any('Missing system roles:' in issue for issue in result.issues)
    
    def test_generate_health_report_success(self, validator):
        """Test successful health report generation."""
        # Mock all validations to succeed
        validator.validate_connectivity = Mock(return_value=True)
        
        schema_result = ValidationResult(valid=True)
        validator.validate_schema_integrity = Mock(return_value=schema_result)
        
        data_result = ValidationResult(valid=True)
        validator.validate_data_integrity = Mock(return_value=data_result)
        
        validator._get_database_type = Mock(return_value='sqlite')
        
        report = validator.generate_health_report()
        
        assert report['overall_status'] == HealthStatus.HEALTHY.value
        assert report['connectivity']['status'] == 'healthy'
        assert report['schema']['status'] == 'healthy'
        assert report['data']['status'] == 'healthy'
        assert report['database_type'] == 'sqlite'
        assert 'timestamp' in report
        assert 'duration' in report
    
    def test_generate_health_report_connectivity_failure(self, validator):
        """Test health report generation with connectivity failure."""
        validator.validate_connectivity = Mock(return_value=False)
        validator._get_database_type = Mock(return_value='sqlite')
        
        report = validator.generate_health_report()
        
        assert report['overall_status'] == HealthStatus.CRITICAL.value
        assert report['connectivity']['status'] == 'critical'
        assert 'Database connectivity must be restored' in report['recommendations']
    
    def test_generate_health_report_schema_failure(self, validator):
        """Test health report generation with schema failure."""
        validator.validate_connectivity = Mock(return_value=True)
        
        schema_result = ValidationResult(valid=False)
        schema_result.add_issue("Missing table: users", ValidationSeverity.CRITICAL)
        schema_result.add_suggestion("Run database migrations")
        validator.validate_schema_integrity = Mock(return_value=schema_result)
        
        data_result = ValidationResult(valid=True)
        validator.validate_data_integrity = Mock(return_value=data_result)
        
        validator._get_database_type = Mock(return_value='sqlite')
        
        report = validator.generate_health_report()
        
        assert report['overall_status'] == HealthStatus.CRITICAL.value
        assert report['schema']['status'] == 'critical'
        assert 'Run database migrations' in report['recommendations']
    
    def test_generate_health_report_data_failure(self, validator):
        """Test health report generation with data failure."""
        validator.validate_connectivity = Mock(return_value=True)
        
        schema_result = ValidationResult(valid=True)
        validator.validate_schema_integrity = Mock(return_value=schema_result)
        
        data_result = ValidationResult(valid=False)
        data_result.add_issue("Admin user not found", ValidationSeverity.ERROR)
        data_result.add_suggestion("Run data seeding")
        validator.validate_data_integrity = Mock(return_value=data_result)
        
        validator._get_database_type = Mock(return_value='sqlite')
        
        report = validator.generate_health_report()
        
        assert report['overall_status'] == HealthStatus.WARNING.value
        assert report['data']['status'] == 'critical'
        assert 'Run data seeding' in report['recommendations']
    
    def test_generate_health_report_exception(self, validator):
        """Test health report generation with exception."""
        validator.validate_connectivity = Mock(side_effect=Exception("Validation failed"))
        validator._get_database_type = Mock(return_value='sqlite')
        
        report = validator.generate_health_report()
        
        assert report['overall_status'] == HealthStatus.CRITICAL.value
        assert 'error' in report
        assert 'Investigate health check system errors' in report['recommendations']
    
    def test_run_comprehensive_health_check_success(self, validator):
        """Test successful comprehensive health check."""
        # Mock all checks to succeed
        validator.validate_connectivity = Mock(return_value=True)
        
        schema_result = ValidationResult(valid=True)
        validator.validate_schema_integrity = Mock(return_value=schema_result)
        
        data_result = ValidationResult(valid=True)
        validator.validate_data_integrity = Mock(return_value=data_result)
        
        validator._check_performance_metrics = Mock(return_value={'status': 'healthy'})
        
        result = validator.run_comprehensive_health_check()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.checks_passed == 4
        assert result.checks_failed == 0
        assert result.checks_total == 4
        assert len(result.issues) == 0
    
    def test_run_comprehensive_health_check_connectivity_failure(self, validator):
        """Test comprehensive health check with connectivity failure."""
        validator.validate_connectivity = Mock(return_value=False)
        
        # Other checks should still run
        schema_result = ValidationResult(valid=True)
        validator.validate_schema_integrity = Mock(return_value=schema_result)
        
        data_result = ValidationResult(valid=True)
        validator.validate_data_integrity = Mock(return_value=data_result)
        
        validator._check_performance_metrics = Mock(return_value={'status': 'healthy'})
        
        result = validator.run_comprehensive_health_check()
        
        assert result.status == HealthStatus.CRITICAL
        assert result.checks_passed == 3
        assert result.checks_failed == 1
        assert result.checks_total == 4
        assert any('Database connectivity failed' in issue for issue in result.issues)
    
    def test_run_comprehensive_health_check_schema_failure(self, validator):
        """Test comprehensive health check with schema failure."""
        validator.validate_connectivity = Mock(return_value=True)
        
        schema_result = ValidationResult(valid=False)
        schema_result.add_issue("Missing table: users", ValidationSeverity.CRITICAL)
        validator.validate_schema_integrity = Mock(return_value=schema_result)
        
        data_result = ValidationResult(valid=True)
        validator.validate_data_integrity = Mock(return_value=data_result)
        
        validator._check_performance_metrics = Mock(return_value={'status': 'healthy'})
        
        result = validator.run_comprehensive_health_check()
        
        assert result.status == HealthStatus.CRITICAL
        assert result.checks_passed == 3
        assert result.checks_failed == 1
        assert 'schema_issues' in result.details
    
    def test_run_comprehensive_health_check_data_failure(self, validator):
        """Test comprehensive health check with data failure."""
        validator.validate_connectivity = Mock(return_value=True)
        
        schema_result = ValidationResult(valid=True)
        validator.validate_schema_integrity = Mock(return_value=schema_result)
        
        data_result = ValidationResult(valid=False)
        data_result.add_issue("Admin user not found", ValidationSeverity.ERROR)
        validator.validate_data_integrity = Mock(return_value=data_result)
        
        validator._check_performance_metrics = Mock(return_value={'status': 'healthy'})
        
        result = validator.run_comprehensive_health_check()
        
        assert result.status == HealthStatus.WARNING
        assert result.checks_passed == 3
        assert result.checks_failed == 1
        assert 'data_issues' in result.details
    
    def test_run_comprehensive_health_check_performance_warning(self, validator):
        """Test comprehensive health check with performance warning."""
        validator.validate_connectivity = Mock(return_value=True)
        
        schema_result = ValidationResult(valid=True)
        validator.validate_schema_integrity = Mock(return_value=schema_result)
        
        data_result = ValidationResult(valid=True)
        validator.validate_data_integrity = Mock(return_value=data_result)
        
        validator._check_performance_metrics = Mock(return_value={
            'status': 'warning',
            'message': 'Slow query performance'
        })
        
        result = validator.run_comprehensive_health_check()
        
        assert result.status == HealthStatus.WARNING
        assert result.checks_passed == 3
        assert result.checks_failed == 1
        assert 'performance' in result.details
    
    def test_run_comprehensive_health_check_exception(self, validator):
        """Test comprehensive health check with exception."""
        validator.validate_connectivity = Mock(side_effect=Exception("Check failed"))
        
        result = validator.run_comprehensive_health_check()
        
        assert result.status == HealthStatus.CRITICAL
        assert any('Health check failed with exception' in issue for issue in result.issues)
    
    def test_validate_table_structure_success(self, validator):
        """Test successful table structure validation."""
        # Mock inspector
        mock_inspector = Mock()
        mock_inspector.get_columns.return_value = [
            {'name': 'id'}, {'name': 'name'}, {'name': 'slug'}, 
            {'name': 'is_active'}, {'name': 'created_at'}
        ]
        mock_inspector.get_indexes.return_value = []
        mock_inspector.get_foreign_keys.return_value = []
        
        result = ValidationResult(valid=True)
        
        validator._validate_table_structure(mock_inspector, 'tenants', result)
        
        assert result.valid is True
        assert len(result.issues) == 0
        assert 'tenants_structure' in result.details
    
    def test_validate_table_structure_missing_columns(self, validator):
        """Test table structure validation with missing columns."""
        # Mock inspector with missing columns
        mock_inspector = Mock()
        mock_inspector.get_columns.return_value = [
            {'name': 'id'}, {'name': 'name'}  # Missing required columns
        ]
        mock_inspector.get_indexes.return_value = []
        mock_inspector.get_foreign_keys.return_value = []
        
        result = ValidationResult(valid=True)
        
        validator._validate_table_structure(mock_inspector, 'tenants', result)
        
        assert result.valid is False
        assert any('missing columns' in issue for issue in result.issues)
    
    def test_validate_table_structure_exception(self, validator):
        """Test table structure validation with exception."""
        mock_inspector = Mock()
        mock_inspector.get_columns.side_effect = Exception("Column query failed")
        
        result = ValidationResult(valid=True)
        
        validator._validate_table_structure(mock_inspector, 'tenants', result)
        
        assert any('Failed to validate table' in issue for issue in result.issues)
    
    @patch('app.utils.health_validator.Tenant')
    def test_validate_system_tenant_exists(self, mock_tenant, validator):
        """Test system tenant validation when tenant exists."""
        mock_system_tenant = Mock()
        mock_system_tenant.id = 1
        mock_system_tenant.name = "AI Secretary System"
        mock_system_tenant.is_active = True
        mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
        
        result = ValidationResult(valid=True)
        
        validator._validate_system_tenant(result)
        
        assert result.valid is True
        assert len(result.issues) == 0
        assert 'system_tenant' in result.details
        assert result.details['system_tenant']['id'] == 1
    
    @patch('app.utils.health_validator.Tenant')
    def test_validate_system_tenant_missing(self, mock_tenant, validator):
        """Test system tenant validation when tenant is missing."""
        mock_tenant.query.filter_by.return_value.first.return_value = None
        
        result = ValidationResult(valid=True)
        
        validator._validate_system_tenant(result)
        
        assert result.valid is False
        assert any('System tenant not found' in issue for issue in result.issues)
    
    @patch('app.utils.health_validator.User')
    def test_validate_admin_user_exists(self, mock_user, validator):
        """Test admin user validation when user exists."""
        mock_admin_user = Mock()
        mock_admin_user.id = 1
        mock_admin_user.email = "admin@ai-secretary.com"
        mock_admin_user.is_active = True
        mock_admin_user.role = "owner"
        mock_user.query.filter_by.return_value.first.return_value = mock_admin_user
        
        result = ValidationResult(valid=True)
        
        validator._validate_admin_user(result)
        
        assert result.valid is True
        assert len(result.issues) == 0
        assert 'admin_user' in result.details
        assert result.details['admin_user']['email'] == "admin@ai-secretary.com"
    
    @patch('app.utils.health_validator.User')
    def test_validate_admin_user_missing(self, mock_user, validator):
        """Test admin user validation when user is missing."""
        mock_user.query.filter_by.return_value.first.return_value = None
        
        result = ValidationResult(valid=True)
        
        validator._validate_admin_user(result)
        
        assert result.valid is False
        assert any('Admin user not found' in issue for issue in result.issues)
    
    @patch('app.utils.health_validator.Role')
    def test_validate_system_roles_complete(self, mock_role, validator):
        """Test system roles validation when all roles exist."""
        mock_roles = [Mock(name=name) for name in ['Owner', 'Manager', 'Support', 'Accounting', 'Read Only']]
        mock_role.query.filter_by.return_value.all.return_value = mock_roles
        mock_role.query.filter_by.return_value.first.side_effect = mock_roles
        
        result = ValidationResult(valid=True)
        
        validator._validate_system_roles(result)
        
        assert result.valid is True
        assert len(result.issues) == 0
        assert 'system_roles' in result.details
        assert result.details['system_roles']['total'] == 5
        assert len(result.details['system_roles']['missing']) == 0
    
    @patch('app.utils.health_validator.Role')
    def test_validate_system_roles_missing(self, mock_role, validator):
        """Test system roles validation when some roles are missing."""
        mock_roles = [Mock(name='Owner'), Mock(name='Manager')]  # Missing 3 roles
        mock_role.query.filter_by.return_value.all.return_value = mock_roles
        mock_role.query.filter_by.return_value.first.side_effect = [
            Mock(), Mock(), None, None, None  # First 2 exist, last 3 don't
        ]
        
        result = ValidationResult(valid=True)
        
        validator._validate_system_roles(result)
        
        assert result.valid is False
        assert any('Missing system roles:' in issue for issue in result.issues)
        assert len(result.details['system_roles']['missing']) == 3
    
    def test_check_performance_metrics_good_performance(self, validator):
        """Test performance metrics check with good performance."""
        # Mock fast query
        mock_connection = Mock()
        mock_connection.execute.return_value = None
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        
        validator.db.engine.connect.return_value = mock_connection
        
        result = validator._check_performance_metrics()
        
        assert result['status'] == 'healthy'
        assert 'Good query performance' in result['message']
        assert result['query_time'] < 1.0
    
    def test_check_performance_metrics_slow_performance(self, validator):
        """Test performance metrics check with slow performance."""
        # Mock slow query by adding delay
        def slow_execute(*args, **kwargs):
            time.sleep(1.1)  # Simulate slow query
            return None
        
        mock_connection = Mock()
        mock_connection.execute.side_effect = slow_execute
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        
        validator.db.engine.connect.return_value = mock_connection
        
        result = validator._check_performance_metrics()
        
        assert result['status'] == 'warning'
        assert 'Slow query performance' in result['message']
        assert result['query_time'] > 1.0
    
    def test_check_performance_metrics_error(self, validator):
        """Test performance metrics check with error."""
        validator.db.engine.connect.side_effect = Exception("Connection failed")
        
        result = validator._check_performance_metrics()
        
        assert result['status'] == 'error'
        assert 'Performance check failed' in result['message']
        assert 'error' in result
    
    def test_get_database_type_success(self, validator):
        """Test getting database type successfully."""
        validator.db.engine.dialect.name = 'postgresql'
        
        result = validator._get_database_type()
        
        assert result == 'postgresql'
    
    def test_get_database_type_error(self, validator):
        """Test getting database type with error."""
        validator.db.engine.dialect = None
        
        result = validator._get_database_type()
        
        assert result == 'unknown'
    
    def test_get_health_status_success(self, validator):
        """Test getting health status successfully."""
        # Mock successful connectivity
        validator.validate_connectivity = Mock(return_value=True)
        validator._get_database_type = Mock(return_value='sqlite')
        
        # Mock inspector and models
        with patch('app.utils.health_validator.inspect') as mock_inspect, \
             patch('app.utils.health_validator.Tenant') as mock_tenant:
            
            mock_inspector = Mock()
            mock_inspector.get_table_names.return_value = ['tenants', 'users']
            mock_inspect.return_value = mock_inspector
            
            mock_tenant.query.count.return_value = 1
            
            status = validator.get_health_status()
            
            assert status['overall_status'] == HealthStatus.HEALTHY.value
            assert status['connectivity'] is True
            assert status['database_type'] == 'sqlite'
            assert status['checks']['connectivity'] == 'passed'
            assert status['checks']['schema'] == 'passed'
            assert status['checks']['data'] == 'passed'
    
    def test_get_health_status_connectivity_failure(self, validator):
        """Test getting health status with connectivity failure."""
        validator.validate_connectivity = Mock(return_value=False)
        validator._get_database_type = Mock(return_value='sqlite')
        
        status = validator.get_health_status()
        
        assert status['overall_status'] == HealthStatus.CRITICAL.value
        assert status['connectivity'] is False
        assert status['checks']['connectivity'] == 'failed'
        assert status['checks']['schema'] == 'unknown'
        assert status['checks']['data'] == 'unknown'
    
    def test_get_health_status_exception(self, validator):
        """Test getting health status with exception."""
        validator.validate_connectivity = Mock(side_effect=Exception("Check failed"))
        
        status = validator.get_health_status()
        
        assert status['overall_status'] == HealthStatus.CRITICAL.value
        assert 'error' in status


class TestValidationResult:
    """Test cases for ValidationResult dataclass."""
    
    def test_validation_result_creation(self):
        """Test creating ValidationResult."""
        result = ValidationResult(valid=True)
        
        assert result.valid is True
        assert result.issues == []
        assert result.suggestions == []
        assert result.severity == ValidationSeverity.INFO
        assert result.details == {}
        assert isinstance(result.timestamp, datetime)
    
    def test_add_issue_error(self):
        """Test adding error issue."""
        result = ValidationResult(valid=True)
        
        result.add_issue("Database connection failed", ValidationSeverity.ERROR)
        
        assert "Database connection failed" in result.issues
        assert result.severity == ValidationSeverity.ERROR
    
    def test_add_issue_critical(self):
        """Test adding critical issue."""
        result = ValidationResult(valid=True)
        
        result.add_issue("Schema corruption detected", ValidationSeverity.CRITICAL)
        
        assert "Schema corruption detected" in result.issues
        assert result.severity == ValidationSeverity.CRITICAL
    
    def test_add_issue_severity_escalation(self):
        """Test that severity escalates to highest level."""
        result = ValidationResult(valid=True)
        
        result.add_issue("Warning message", ValidationSeverity.WARNING)
        assert result.severity == ValidationSeverity.WARNING
        
        result.add_issue("Error message", ValidationSeverity.ERROR)
        assert result.severity == ValidationSeverity.ERROR
        
        result.add_issue("Critical message", ValidationSeverity.CRITICAL)
        assert result.severity == ValidationSeverity.CRITICAL
        
        # Adding lower severity should not downgrade
        result.add_issue("Another warning", ValidationSeverity.WARNING)
        assert result.severity == ValidationSeverity.CRITICAL
    
    def test_add_suggestion(self):
        """Test adding suggestion."""
        result = ValidationResult(valid=True)
        
        result.add_suggestion("Run database migrations")
        
        assert "Run database migrations" in result.suggestions


class TestHealthCheckResult:
    """Test cases for HealthCheckResult dataclass."""
    
    def test_health_check_result_creation(self):
        """Test creating HealthCheckResult."""
        result = HealthCheckResult(status=HealthStatus.HEALTHY)
        
        assert result.status == HealthStatus.HEALTHY
        assert result.checks_passed == 0
        assert result.checks_failed == 0
        assert result.checks_total == 0
        assert result.issues == []
        assert result.warnings == []
        assert result.details == {}
        assert result.duration == 0.0
        assert isinstance(result.timestamp, datetime)
    
    def test_add_issue_critical(self):
        """Test adding critical issue."""
        result = HealthCheckResult(status=HealthStatus.HEALTHY)
        
        result.add_issue("Database connection failed", HealthStatus.CRITICAL)
        
        assert "Database connection failed" in result.issues
        assert result.checks_failed == 1
        assert result.checks_total == 1
        assert result.status == HealthStatus.CRITICAL
    
    def test_add_issue_warning(self):
        """Test adding warning issue."""
        result = HealthCheckResult(status=HealthStatus.HEALTHY)
        
        result.add_issue("Performance degraded", HealthStatus.WARNING)
        
        assert "Performance degraded" in result.warnings
        assert result.checks_total == 1
        assert result.status == HealthStatus.WARNING
    
    def test_add_success(self):
        """Test adding successful check."""
        result = HealthCheckResult(status=HealthStatus.HEALTHY)
        
        result.add_success("Database connectivity")
        
        assert result.checks_passed == 1
        assert result.checks_total == 1
        assert result.status == HealthStatus.HEALTHY
    
    def test_status_escalation(self):
        """Test that status escalates appropriately."""
        result = HealthCheckResult(status=HealthStatus.HEALTHY)
        
        # Add warning - should change to warning
        result.add_issue("Warning", HealthStatus.WARNING)
        assert result.status == HealthStatus.WARNING
        
        # Add critical - should change to critical
        result.add_issue("Critical", HealthStatus.CRITICAL)
        assert result.status == HealthStatus.CRITICAL
        
        # Add another warning - should stay critical
        result.add_issue("Another warning", HealthStatus.WARNING)
        assert result.status == HealthStatus.CRITICAL


if __name__ == '__main__':
    pytest.main([__file__])