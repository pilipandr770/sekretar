"""
Comprehensive tests for DataSeeder class.

This module provides comprehensive unit and integration tests for the data
seeding system, covering all seeding operations, error scenarios, and
validation requirements.
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from app.utils.data_seeder import DataSeeder, SeedingResult
from app.models import User, Tenant, Role


class TestDataSeeder:
    """Test cases for DataSeeder class."""
    
    @pytest.fixture
    def mock_app(self):
        """Create mock Flask app."""
        app = Mock()
        app.config = {'TESTING': True}
        app.debug = False
        app.testing = True
        return app
    
    @pytest.fixture
    def mock_db(self):
        """Create mock SQLAlchemy instance."""
        db = Mock()
        db.session = Mock()
        return db
    
    @pytest.fixture
    def seeder(self, mock_app, mock_db):
        """Create DataSeeder instance."""
        with patch('app.utils.data_seeder.get_database_init_logger') as mock_logger:
            mock_logger.return_value = Mock()
            return DataSeeder(mock_app, mock_db)
    
    def test_initialization(self, mock_app, mock_db):
        """Test DataSeeder initialization."""
        with patch('app.utils.data_seeder.get_database_init_logger') as mock_logger:
            mock_logger.return_value = Mock()
            seeder = DataSeeder(mock_app, mock_db)
            
            assert seeder.app == mock_app
            assert seeder.db == mock_db
            assert seeder.default_admin_email == "admin@ai-secretary.com"
            assert seeder.default_admin_password == "admin123"
            assert seeder.default_tenant_name == "AI Secretary System"
            assert seeder.default_tenant_slug == "ai-secretary-system"
    
    def test_seed_initial_data_success(self, seeder):
        """Test successful initial data seeding."""
        # Mock system tenant creation
        mock_tenant = Mock()
        mock_tenant.id = 1
        mock_tenant.name = "AI Secretary System"
        seeder._create_system_tenant = Mock(return_value={
            'success': True,
            'tenant': mock_tenant,
            'created': True
        })
        
        # Mock system roles creation
        seeder._create_system_roles = Mock(return_value={
            'success': True,
            'created_count': 5,
            'skipped_count': 0
        })
        
        # Mock admin user creation
        mock_user = Mock()
        mock_user.email = "admin@ai-secretary.com"
        seeder._create_admin_user = Mock(return_value={
            'success': True,
            'user': mock_user,
            'created': True
        })
        
        result = seeder.seed_initial_data()
        
        assert result.success is True
        assert result.records_created['tenant'] == 1
        assert result.records_created['roles'] == 5
        assert result.records_created['admin_user'] == 1
        assert len(result.errors) == 0
        assert result.duration >= 0
    
    def test_seed_initial_data_tenant_creation_failure(self, seeder):
        """Test initial data seeding with tenant creation failure."""
        seeder._create_system_tenant = Mock(return_value={
            'success': False,
            'error': 'Database connection failed'
        })
        
        result = seeder.seed_initial_data()
        
        assert result.success is False
        assert any('Failed to create system tenant' in error for error in result.errors)
    
    def test_seed_initial_data_roles_creation_failure(self, seeder):
        """Test initial data seeding with roles creation failure."""
        # Mock successful tenant creation
        mock_tenant = Mock()
        mock_tenant.id = 1
        seeder._create_system_tenant = Mock(return_value={
            'success': True,
            'tenant': mock_tenant,
            'created': True
        })
        
        # Mock roles creation failure
        seeder._create_system_roles = Mock(return_value={
            'success': False,
            'error': 'Failed to create roles'
        })
        
        result = seeder.seed_initial_data()
        
        assert result.success is False
        assert any('Failed to create system roles' in error for error in result.errors)
    
    def test_seed_initial_data_admin_user_creation_failure(self, seeder):
        """Test initial data seeding with admin user creation failure."""
        # Mock successful tenant and roles creation
        mock_tenant = Mock()
        mock_tenant.id = 1
        seeder._create_system_tenant = Mock(return_value={
            'success': True,
            'tenant': mock_tenant,
            'created': True
        })
        
        seeder._create_system_roles = Mock(return_value={
            'success': True,
            'created_count': 5,
            'skipped_count': 0
        })
        
        # Mock admin user creation failure
        seeder._create_admin_user = Mock(return_value={
            'success': False,
            'error': 'Email already exists'
        })
        
        result = seeder.seed_initial_data()
        
        assert result.success is False
        assert any('Failed to create admin user' in error for error in result.errors)
    
    def test_seed_initial_data_with_existing_data(self, seeder):
        """Test initial data seeding when data already exists."""
        # Mock existing tenant
        mock_tenant = Mock()
        mock_tenant.id = 1
        seeder._create_system_tenant = Mock(return_value={
            'success': True,
            'tenant': mock_tenant,
            'created': False  # Already existed
        })
        
        # Mock existing roles
        seeder._create_system_roles = Mock(return_value={
            'success': True,
            'created_count': 2,
            'skipped_count': 3  # 3 already existed
        })
        
        # Mock existing admin user
        mock_user = Mock()
        mock_user.email = "admin@ai-secretary.com"
        seeder._create_admin_user = Mock(return_value={
            'success': True,
            'user': mock_user,
            'created': False  # Already existed
        })
        
        result = seeder.seed_initial_data()
        
        assert result.success is True
        assert result.records_skipped['tenant'] == 1
        assert result.records_created['roles'] == 2
        assert result.records_skipped['roles'] == 3
        assert result.records_skipped['admin_user'] == 1
    
    def test_create_admin_user_success(self, seeder):
        """Test successful admin user creation."""
        # Mock system tenant creation
        mock_tenant = Mock()
        mock_tenant.id = 1
        seeder._create_system_tenant = Mock(return_value={
            'success': True,
            'tenant': mock_tenant,
            'created': True
        })
        
        # Mock admin user creation
        mock_user = Mock()
        seeder._create_admin_user = Mock(return_value={
            'success': True,
            'user': mock_user,
            'created': True
        })
        
        result = seeder.create_admin_user()
        
        assert result is True
        seeder._create_admin_user.assert_called_once_with(1)
    
    def test_create_admin_user_with_tenant_id(self, seeder):
        """Test admin user creation with specific tenant ID."""
        mock_user = Mock()
        seeder._create_admin_user = Mock(return_value={
            'success': True,
            'user': mock_user,
            'created': True
        })
        
        result = seeder.create_admin_user(tenant_id=5)
        
        assert result is True
        seeder._create_admin_user.assert_called_once_with(5)
    
    def test_create_admin_user_failure(self, seeder):
        """Test admin user creation failure."""
        seeder._create_admin_user = Mock(return_value={
            'success': False,
            'error': 'Database error'
        })
        
        result = seeder.create_admin_user(tenant_id=1)
        
        assert result is False
    
    def test_create_system_tenants_success(self, seeder):
        """Test successful system tenants creation."""
        # Mock tenant creation
        mock_tenant = Mock()
        mock_tenant.id = 1
        seeder._create_system_tenant = Mock(return_value={
            'success': True,
            'tenant': mock_tenant,
            'created': True
        })
        
        # Mock roles creation
        seeder._create_system_roles = Mock(return_value={
            'success': True,
            'created_count': 5,
            'skipped_count': 0
        })
        
        result = seeder.create_system_tenants()
        
        assert result is True
    
    def test_create_system_tenants_failure(self, seeder):
        """Test system tenants creation failure."""
        seeder._create_system_tenant = Mock(return_value={
            'success': False,
            'error': 'Database error'
        })
        
        result = seeder.create_system_tenants()
        
        assert result is False
    
    @patch('app.utils.data_seeder.Tenant')
    @patch('app.utils.data_seeder.User')
    @patch('app.utils.data_seeder.Role')
    def test_validate_seed_data_success(self, mock_role, mock_user, mock_tenant, seeder):
        """Test successful seed data validation."""
        # Mock system tenant
        mock_system_tenant = Mock()
        mock_system_tenant.id = 1
        mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
        
        # Mock admin user
        mock_admin_user = Mock()
        mock_admin_user.check_password.return_value = True
        mock_admin_user.has_role.return_value = True
        mock_user.query.filter_by.return_value.first.return_value = mock_admin_user
        
        # Mock system roles
        mock_roles = [Mock() for _ in range(5)]
        mock_role.query.filter_by.return_value.first.side_effect = mock_roles
        
        # Mock owner role
        mock_owner_role = Mock()
        mock_role.query.filter_by.return_value.first.return_value = mock_owner_role
        
        result = seeder.validate_seed_data()
        
        assert result is True
    
    @patch('app.utils.data_seeder.Tenant')
    def test_validate_seed_data_no_system_tenant(self, mock_tenant, seeder):
        """Test seed data validation with missing system tenant."""
        mock_tenant.query.filter_by.return_value.first.return_value = None
        
        result = seeder.validate_seed_data()
        
        assert result is False
    
    @patch('app.utils.data_seeder.Tenant')
    @patch('app.utils.data_seeder.User')
    def test_validate_seed_data_no_admin_user(self, mock_user, mock_tenant, seeder):
        """Test seed data validation with missing admin user."""
        # Mock system tenant exists
        mock_system_tenant = Mock()
        mock_system_tenant.id = 1
        mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
        
        # Mock admin user doesn't exist
        mock_user.query.filter_by.return_value.first.return_value = None
        
        result = seeder.validate_seed_data()
        
        assert result is False
    
    @patch('app.utils.data_seeder.Tenant')
    @patch('app.utils.data_seeder.User')
    def test_validate_seed_data_invalid_password(self, mock_user, mock_tenant, seeder):
        """Test seed data validation with invalid admin password."""
        # Mock system tenant exists
        mock_system_tenant = Mock()
        mock_system_tenant.id = 1
        mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
        
        # Mock admin user with invalid password
        mock_admin_user = Mock()
        mock_admin_user.check_password.return_value = False
        mock_user.query.filter_by.return_value.first.return_value = mock_admin_user
        
        result = seeder.validate_seed_data()
        
        assert result is False
    
    def test_create_system_tenant_new_tenant(self, seeder):
        """Test creating new system tenant."""
        # Mock no existing tenant
        with patch('app.utils.data_seeder.Tenant') as mock_tenant_class:
            mock_tenant_class.query.filter_by.return_value.first.return_value = None
            
            # Mock new tenant creation
            mock_tenant = Mock()
            mock_tenant_class.return_value = mock_tenant
            
            result = seeder._create_system_tenant()
            
            assert result['success'] is True
            assert result['tenant'] == mock_tenant
            assert result['created'] is True
            seeder.db.session.add.assert_called_once_with(mock_tenant)
            seeder.db.session.commit.assert_called_once()
    
    def test_create_system_tenant_existing_tenant(self, seeder):
        """Test getting existing system tenant."""
        # Mock existing tenant
        with patch('app.utils.data_seeder.Tenant') as mock_tenant_class:
            mock_existing_tenant = Mock()
            mock_tenant_class.query.filter_by.return_value.first.return_value = mock_existing_tenant
            
            result = seeder._create_system_tenant()
            
            assert result['success'] is True
            assert result['tenant'] == mock_existing_tenant
            assert result['created'] is False
            seeder.db.session.add.assert_not_called()
    
    def test_create_system_tenant_integrity_error(self, seeder):
        """Test system tenant creation with integrity error."""
        with patch('app.utils.data_seeder.Tenant') as mock_tenant_class:
            # Mock no existing tenant initially
            mock_tenant_class.query.filter_by.return_value.first.side_effect = [None, Mock()]
            
            # Mock integrity error on commit
            seeder.db.session.commit.side_effect = IntegrityError("Duplicate key", None, None)
            
            result = seeder._create_system_tenant()
            
            assert result['success'] is True
            assert result['created'] is False
            seeder.db.session.rollback.assert_called_once()
    
    def test_create_system_tenant_general_error(self, seeder):
        """Test system tenant creation with general error."""
        with patch('app.utils.data_seeder.Tenant') as mock_tenant_class:
            mock_tenant_class.query.filter_by.return_value.first.return_value = None
            seeder.db.session.commit.side_effect = Exception("Database error")
            
            result = seeder._create_system_tenant()
            
            assert result['success'] is False
            assert 'Failed to create system tenant' in result['error']
            seeder.db.session.rollback.assert_called_once()
    
    def test_create_system_roles_new_roles(self, seeder):
        """Test creating new system roles."""
        with patch('app.utils.data_seeder.Role') as mock_role_class:
            # Mock no existing roles
            mock_role_class.query.filter_by.return_value.all.return_value = []
            
            # Mock role creation
            mock_roles = [Mock() for _ in range(5)]
            mock_role_class.side_effect = mock_roles
            
            result = seeder._create_system_roles(1)
            
            assert result['success'] is True
            assert result['created_count'] == 5
            assert result['skipped_count'] == 0
            assert seeder.db.session.add.call_count == 5
            seeder.db.session.commit.assert_called_once()
    
    def test_create_system_roles_existing_roles(self, seeder):
        """Test creating system roles when some already exist."""
        with patch('app.utils.data_seeder.Role') as mock_role_class:
            # Mock existing roles
            existing_roles = [Mock(name='Owner'), Mock(name='Manager')]
            mock_role_class.query.filter_by.return_value.all.return_value = existing_roles
            
            # Mock role creation for remaining roles
            mock_roles = [Mock() for _ in range(3)]
            mock_role_class.side_effect = mock_roles
            
            result = seeder._create_system_roles(1)
            
            assert result['success'] is True
            assert result['created_count'] == 3
            assert result['skipped_count'] == 2
            assert seeder.db.session.add.call_count == 3
    
    def test_create_system_roles_error(self, seeder):
        """Test system roles creation with error."""
        with patch('app.utils.data_seeder.Role') as mock_role_class:
            mock_role_class.query.filter_by.return_value.all.return_value = []
            seeder.db.session.commit.side_effect = Exception("Database error")
            
            result = seeder._create_system_roles(1)
            
            assert result['success'] is False
            assert 'Failed to create system roles' in result['error']
            seeder.db.session.rollback.assert_called_once()
    
    def test_create_admin_user_new_user(self, seeder):
        """Test creating new admin user."""
        with patch('app.utils.data_seeder.User') as mock_user_class, \
             patch('app.utils.data_seeder.Role') as mock_role_class:
            
            # Mock no existing user
            mock_user_class.query.filter_by.return_value.first.return_value = None
            
            # Mock new user creation
            mock_user = Mock()
            mock_user_class.return_value = mock_user
            
            # Mock owner role
            mock_owner_role = Mock()
            mock_role_class.query.filter_by.return_value.first.return_value = mock_owner_role
            
            result = seeder._create_admin_user(1)
            
            assert result['success'] is True
            assert result['user'] == mock_user
            assert result['created'] is True
            seeder.db.session.add.assert_called_once_with(mock_user)
            seeder.db.session.commit.assert_called_once()
            mock_user.add_role.assert_called_once_with(mock_owner_role)
    
    def test_create_admin_user_existing_user(self, seeder):
        """Test getting existing admin user."""
        with patch('app.utils.data_seeder.User') as mock_user_class, \
             patch('app.utils.data_seeder.Role') as mock_role_class:
            
            # Mock existing user
            mock_existing_user = Mock()
            mock_existing_user.has_role.return_value = True
            mock_user_class.query.filter_by.return_value.first.return_value = mock_existing_user
            
            # Mock owner role
            mock_owner_role = Mock()
            mock_role_class.query.filter_by.return_value.first.return_value = mock_owner_role
            
            result = seeder._create_admin_user(1)
            
            assert result['success'] is True
            assert result['user'] == mock_existing_user
            assert result['created'] is False
            seeder.db.session.add.assert_not_called()
    
    def test_create_admin_user_existing_user_missing_role(self, seeder):
        """Test existing admin user without owner role."""
        with patch('app.utils.data_seeder.User') as mock_user_class, \
             patch('app.utils.data_seeder.Role') as mock_role_class:
            
            # Mock existing user without owner role
            mock_existing_user = Mock()
            mock_existing_user.has_role.return_value = False
            mock_user_class.query.filter_by.return_value.first.return_value = mock_existing_user
            
            # Mock owner role
            mock_owner_role = Mock()
            mock_role_class.query.filter_by.return_value.first.return_value = mock_owner_role
            
            result = seeder._create_admin_user(1)
            
            assert result['success'] is True
            assert result['created'] is False
            mock_existing_user.add_role.assert_called_once_with(mock_owner_role)
            mock_existing_user.save.assert_called_once()
    
    def test_create_admin_user_integrity_error(self, seeder):
        """Test admin user creation with integrity error."""
        with patch('app.utils.data_seeder.User') as mock_user_class, \
             patch('app.utils.data_seeder.Role') as mock_role_class:
            
            # Mock no existing user initially, then existing user after error
            mock_existing_user = Mock()
            mock_user_class.query.filter_by.return_value.first.side_effect = [None, mock_existing_user]
            
            # Mock integrity error on commit
            seeder.db.session.commit.side_effect = IntegrityError("Duplicate email", None, None)
            
            result = seeder._create_admin_user(1)
            
            assert result['success'] is True
            assert result['user'] == mock_existing_user
            assert result['created'] is False
            seeder.db.session.rollback.assert_called_once()
    
    def test_create_admin_user_general_error(self, seeder):
        """Test admin user creation with general error."""
        with patch('app.utils.data_seeder.User') as mock_user_class:
            mock_user_class.query.filter_by.return_value.first.return_value = None
            seeder.db.session.commit.side_effect = Exception("Database error")
            
            result = seeder._create_admin_user(1)
            
            assert result['success'] is False
            assert 'Failed to create admin user' in result['error']
            seeder.db.session.rollback.assert_called_once()
    
    @patch('app.utils.data_seeder.Tenant')
    @patch('app.utils.data_seeder.User')
    @patch('app.utils.data_seeder.Role')
    def test_get_seeding_status_complete(self, mock_role, mock_user, mock_tenant, seeder):
        """Test getting seeding status when complete."""
        # Mock system tenant exists
        mock_system_tenant = Mock()
        mock_system_tenant.id = 1
        mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
        
        # Mock admin user exists
        mock_admin_user = Mock()
        mock_user.query.filter_by.return_value.first.return_value = mock_admin_user
        
        # Mock system roles exist
        mock_role.query.filter_by.return_value.count.return_value = 5
        
        # Mock validation passes
        seeder.validate_seed_data = Mock(return_value=True)
        
        status = seeder.get_seeding_status()
        
        assert status['system_tenant_exists'] is True
        assert status['admin_user_exists'] is True
        assert status['system_roles_exist'] is True
        assert status['seeding_complete'] is True
        assert status['validation_passed'] is True
    
    @patch('app.utils.data_seeder.Tenant')
    def test_get_seeding_status_incomplete(self, mock_tenant, seeder):
        """Test getting seeding status when incomplete."""
        # Mock no system tenant
        mock_tenant.query.filter_by.return_value.first.return_value = None
        
        status = seeder.get_seeding_status()
        
        assert status['system_tenant_exists'] is False
        assert status['admin_user_exists'] is False
        assert status['system_roles_exist'] is False
        assert status['seeding_complete'] is False
        assert status['validation_passed'] is False
    
    @patch('app.utils.data_seeder.Tenant')
    @patch('app.utils.data_seeder.User')
    @patch('app.utils.data_seeder.Role')
    def test_reset_seed_data_success(self, mock_role, mock_user, mock_tenant, seeder):
        """Test successful seed data reset."""
        # Enable debug mode
        seeder.app.debug = True
        
        # Mock system tenant
        mock_system_tenant = Mock()
        mock_system_tenant.id = 1
        mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
        
        # Mock admin user
        mock_admin_user = Mock()
        mock_user.query.filter_by.return_value.first.return_value = mock_admin_user
        
        # Mock system roles
        mock_system_roles = [Mock() for _ in range(5)]
        mock_role.query.filter_by.return_value.all.return_value = mock_system_roles
        
        result = seeder.reset_seed_data()
        
        assert result is True
        seeder.db.session.delete.assert_called()  # Should delete tenant, user, and roles
        seeder.db.session.commit.assert_called_once()
    
    def test_reset_seed_data_not_debug_mode(self, seeder):
        """Test seed data reset not allowed in non-debug mode."""
        seeder.app.debug = False
        seeder.app.testing = False
        
        result = seeder.reset_seed_data()
        
        assert result is False
    
    @patch('app.utils.data_seeder.Tenant')
    def test_reset_seed_data_no_tenant(self, mock_tenant, seeder):
        """Test seed data reset when no system tenant exists."""
        seeder.app.debug = True
        mock_tenant.query.filter_by.return_value.first.return_value = None
        
        result = seeder.reset_seed_data()
        
        assert result is True  # Should succeed even if no data to reset
    
    def test_reset_seed_data_error(self, seeder):
        """Test seed data reset with error."""
        seeder.app.debug = True
        
        with patch('app.utils.data_seeder.Tenant') as mock_tenant:
            mock_system_tenant = Mock()
            mock_tenant.query.filter_by.return_value.first.return_value = mock_system_tenant
            seeder.db.session.commit.side_effect = Exception("Database error")
            
            result = seeder.reset_seed_data()
            
            assert result is False
            seeder.db.session.rollback.assert_called_once()


class TestSeedingResult:
    """Test cases for SeedingResult dataclass."""
    
    def test_seeding_result_creation(self):
        """Test creating SeedingResult."""
        result = SeedingResult(success=True)
        
        assert result.success is True
        assert result.records_created == {}
        assert result.records_skipped == {}
        assert result.errors == []
        assert result.warnings == []
        assert result.duration == 0.0
        assert isinstance(result.timestamp, datetime)
    
    def test_add_created(self):
        """Test adding created record count."""
        result = SeedingResult(success=True)
        
        result.add_created('tenant', 1)
        result.add_created('user', 2)
        result.add_created('user', 1)  # Add to existing count
        
        assert result.records_created['tenant'] == 1
        assert result.records_created['user'] == 3
    
    def test_add_skipped(self):
        """Test adding skipped record count."""
        result = SeedingResult(success=True)
        
        result.add_skipped('tenant', 1)
        result.add_skipped('role', 5)
        
        assert result.records_skipped['tenant'] == 1
        assert result.records_skipped['role'] == 5
    
    def test_add_error(self):
        """Test adding error message."""
        result = SeedingResult(success=True)
        
        result.add_error("Database connection failed")
        
        assert "Database connection failed" in result.errors
        assert len(result.errors) == 1
    
    def test_add_warning(self):
        """Test adding warning message."""
        result = SeedingResult(success=True)
        
        result.add_warning("Duplicate data detected")
        
        assert "Duplicate data detected" in result.warnings
        assert len(result.warnings) == 1


class TestDataSeederIntegration:
    """Integration tests for DataSeeder with real database models."""
    
    @pytest.fixture
    def app_with_db(self):
        """Create Flask app with real database for integration testing."""
        from app import create_app
        
        app = create_app('testing')
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['TESTING'] = True
        
        with app.app_context():
            from app import db
            db.create_all()
            yield app, db
    
    def test_integration_seed_initial_data(self, app_with_db):
        """Test complete data seeding integration."""
        app, db = app_with_db
        
        with app.app_context():
            seeder = DataSeeder(app, db)
            
            result = seeder.seed_initial_data()
            
            assert result.success is True
            assert result.records_created.get('tenant', 0) >= 1
            assert result.records_created.get('admin_user', 0) >= 1
            assert result.records_created.get('roles', 0) >= 5
    
    def test_integration_validate_seed_data(self, app_with_db):
        """Test seed data validation integration."""
        app, db = app_with_db
        
        with app.app_context():
            seeder = DataSeeder(app, db)
            
            # Seed data first
            seeder.seed_initial_data()
            
            # Validate seeded data
            result = seeder.validate_seed_data()
            
            assert result is True
    
    def test_integration_idempotent_seeding(self, app_with_db):
        """Test that seeding is idempotent (can be run multiple times)."""
        app, db = app_with_db
        
        with app.app_context():
            seeder = DataSeeder(app, db)
            
            # First seeding
            result1 = seeder.seed_initial_data()
            assert result1.success is True
            
            # Second seeding should skip existing data
            result2 = seeder.seed_initial_data()
            assert result2.success is True
            assert sum(result2.records_skipped.values()) > 0


if __name__ == '__main__':
    pytest.main([__file__])