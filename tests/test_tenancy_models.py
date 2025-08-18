"""Test core tenancy models (Tenant, User, Role)."""
import pytest
from datetime import datetime, timedelta
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role, Permission
from app.models.audit_log import AuditLog
from app import db


class TestTenantModel:
    """Test Tenant model functionality."""
    
    def test_create_tenant(self, app):
        """Test basic tenant creation."""
        with app.app_context():
            tenant = Tenant(
                name="Test Company",
                slug="test-company",
                email="test@company.com"
            )
            tenant.save()
            
            assert tenant.id is not None
            assert tenant.name == "Test Company"
            assert tenant.slug == "test-company"
            assert tenant.email == "test@company.com"
            assert tenant.is_active is True
            assert tenant.subscription_status == "trial"
            assert tenant.settings == {}
    
    def test_tenant_settings_management(self, app):
        """Test tenant settings functionality."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Test setting values
            tenant.set_setting("feature_x", True)
            tenant.set_setting("max_users", 10)
            tenant.set_setting("theme", {"color": "blue"})
            tenant.save()
            
            assert tenant.get_setting("feature_x") is True
            assert tenant.get_setting("max_users") == 10
            assert tenant.get_setting("theme") == {"color": "blue"}
            assert tenant.get_setting("nonexistent") is None
            assert tenant.get_setting("nonexistent", "default") == "default"
    
    def test_create_tenant_with_owner(self, app):
        """Test creating tenant with owner user and default roles."""
        with app.app_context():
            tenant, owner = Tenant.create_with_owner(
                name="Test Company",
                owner_email="owner@test.com",
                owner_password="password123"
            )
            
            # Verify tenant
            assert tenant.id is not None
            assert tenant.name == "Test Company"
            assert tenant.slug == "test-company"
            
            # Verify owner user
            assert owner.id is not None
            assert owner.tenant_id == tenant.id
            assert owner.role == "owner"
            assert owner.email == "owner@test.com"
            assert owner.check_password("password123")
            
            # Verify default roles were created
            roles = Role.query.filter_by(tenant_id=tenant.id).all()
            assert len(roles) == 5  # Owner, Manager, Support, Accounting, Read Only
            
            role_names = [role.name for role in roles]
            assert "Owner" in role_names
            assert "Manager" in role_names
            assert "Support" in role_names
            assert "Accounting" in role_names
            assert "Read Only" in role_names
            
            # Verify owner has Owner role assigned
            assert owner.has_role("Owner")
    
    def test_trial_expiration_logic(self, app):
        """Test trial expiration functionality."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Test active trial
            future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
            tenant.trial_ends_at = future_date
            assert not tenant.is_trial_expired()
            
            # Test expired trial
            past_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
            tenant.trial_ends_at = past_date
            assert tenant.is_trial_expired()
            
            # Test no trial end date
            tenant.trial_ends_at = None
            assert not tenant.is_trial_expired()
    
    def test_feature_access_control(self, app):
        """Test feature access control based on subscription status."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Test active trial
            tenant.subscription_status = "trial"
            future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
            tenant.trial_ends_at = future_date
            assert tenant.can_access_feature("inbox_read")
            assert tenant.can_access_feature("crm_manage")
            
            # Test expired trial
            past_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
            tenant.trial_ends_at = past_date
            assert tenant.can_access_feature("inbox_read")  # Basic feature
            assert not tenant.can_access_feature("crm_manage")  # Premium feature
            
            # Test suspended account
            tenant.subscription_status = "suspended"
            assert not tenant.can_access_feature("inbox_read")
            
            # Test active subscription
            tenant.subscription_status = "active"
            assert tenant.can_access_feature("inbox_read")
            assert tenant.can_access_feature("crm_manage")
    
    def test_tenant_to_dict(self, app):
        """Test tenant dictionary conversion."""
        with app.app_context():
            tenant = Tenant(
                name="Test Company",
                slug="test-company",
                email="test@company.com"
            )
            tenant.save()
            
            data = tenant.to_dict()
            
            assert data['name'] == "Test Company"
            assert data['slug'] == "test-company"
            assert data['email'] == "test@company.com"
            assert data['is_active'] is True
            assert data['subscription_status'] == "trial"
            assert 'settings' not in data  # Should be excluded by default
            assert 'user_count' in data
            assert 'is_trial' in data


class TestUserModel:
    """Test User model functionality."""
    
    def test_create_user(self, app):
        """Test basic user creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id,
                first_name="John",
                last_name="Doe",
                role="manager"
            )
            
            assert user.id is not None
            assert user.email == "test@example.com"
            assert user.tenant_id == tenant.id
            assert user.role == "manager"
            assert user.first_name == "John"
            assert user.last_name == "Doe"
            assert user.full_name == "John Doe"
            assert user.check_password("password123")
            assert user.is_active is True
            assert user.is_email_verified is False
    
    def test_password_hashing_and_verification(self, app):
        """Test password hashing and verification."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id
            )
            
            # Password should be hashed
            assert user.password_hash != "password123"
            assert len(user.password_hash) > 50  # Hashed passwords are long
            
            # Should verify correct password
            assert user.check_password("password123")
            
            # Should reject incorrect password
            assert not user.check_password("wrongpassword")
            assert not user.check_password("")
            assert not user.check_password(None)
    
    def test_user_role_properties(self, app):
        """Test user role-based properties."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Test owner
            owner = User.create(
                email="owner@test.com",
                password="password",
                tenant_id=tenant.id,
                role="owner"
            )
            
            assert owner.is_owner
            assert owner.is_manager
            assert owner.can_manage_users
            assert owner.can_access_billing
            assert owner.can_manage_settings
            
            # Test manager
            manager = User.create(
                email="manager@test.com",
                password="password",
                tenant_id=tenant.id,
                role="manager"
            )
            
            assert not manager.is_owner
            assert manager.is_manager
            assert manager.can_manage_users
            assert manager.can_access_billing
            assert manager.can_manage_settings
            
            # Test read-only user
            readonly = User.create(
                email="readonly@test.com",
                password="password",
                tenant_id=tenant.id,
                role="read_only"
            )
            
            assert not readonly.is_owner
            assert not readonly.is_manager
            assert not readonly.can_manage_users
            assert not readonly.can_access_billing
            assert not readonly.can_manage_settings
    
    def test_user_authentication(self, app):
        """Test user authentication."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id,
                is_active=True
            )
            
            # Test successful authentication
            authenticated = User.authenticate("test@example.com", "password123", tenant.id)
            assert authenticated is not None
            assert authenticated.id == user.id
            assert authenticated.last_login_at is not None
            
            # Test failed authentication - wrong password
            assert User.authenticate("test@example.com", "wrongpassword", tenant.id) is None
            
            # Test failed authentication - wrong email
            assert User.authenticate("wrong@example.com", "password123", tenant.id) is None
            
            # Test failed authentication - inactive user
            user.is_active = False
            user.save()
            assert User.authenticate("test@example.com", "password123", tenant.id) is None
    
    def test_password_reset_functionality(self, app):
        """Test password reset token functionality."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id
            )
            
            # Generate reset token
            token = user.generate_password_reset_token()
            user.save()
            
            assert token is not None
            assert len(token) > 20  # Tokens should be reasonably long
            assert user.password_reset_token == token
            assert user.password_reset_expires is not None
            assert user.password_reset_expires > datetime.utcnow()
            
            # Verify valid token
            assert user.verify_password_reset_token(token)
            
            # Verify invalid token
            assert not user.verify_password_reset_token("invalid_token")
            assert not user.verify_password_reset_token("")
            assert not user.verify_password_reset_token(None)
            
            # Test expired token
            user.password_reset_expires = datetime.utcnow() - timedelta(hours=1)
            user.save()
            assert not user.verify_password_reset_token(token)
            
            # Clear token
            user.clear_password_reset_token()
            user.save()
            
            assert user.password_reset_token is None
            assert user.password_reset_expires is None
    
    def test_email_verification(self, app):
        """Test email verification functionality."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id
            )
            
            # User should have verification token generated
            assert user.email_verification_token is not None
            assert not user.is_email_verified
            
            # Test successful verification
            token = user.email_verification_token
            assert user.verify_email_token(token)
            assert user.is_email_verified
            assert user.email_verification_token is None
            
            # Test failed verification
            user.is_email_verified = False
            user.generate_email_verification_token()
            user.save()
            
            assert not user.verify_email_token("invalid_token")
            assert not user.is_email_verified


class TestRoleModel:
    """Test Role model functionality."""
    
    def test_create_role(self, app):
        """Test basic role creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            role = Role(
                tenant_id=tenant.id,
                name="Custom Role",
                description="A custom role for testing"
            )
            role.set_permissions(['view_crm', 'manage_calendar'])
            role.save()
            
            assert role.id is not None
            assert role.name == "Custom Role"
            assert role.description == "A custom role for testing"
            assert role.tenant_id == tenant.id
            assert role.is_active is True
            assert role.is_system_role is False
            assert role.get_permissions() == ['view_crm', 'manage_calendar']
    
    def test_role_permissions_management(self, app):
        """Test role permissions management."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            role = Role(tenant_id=tenant.id, name="Test Role")
            role.save()
            
            # Test setting permissions
            permissions = ['view_crm', 'manage_calendar', 'view_knowledge']
            role.set_permissions(permissions)
            role.save()
            
            assert role.get_permissions() == permissions
            assert role.has_permission('view_crm')
            assert role.has_permission('manage_calendar')
            assert not role.has_permission('manage_users')
            
            # Test adding permission
            role.add_permission('manage_users')
            role.save()
            
            assert role.has_permission('manage_users')
            assert len(role.get_permissions()) == 4
            
            # Test removing permission
            role.remove_permission('view_crm')
            role.save()
            
            assert not role.has_permission('view_crm')
            assert len(role.get_permissions()) == 3
            
            # Test adding duplicate permission (should not duplicate)
            role.add_permission('manage_users')
            role.save()
            
            permissions = role.get_permissions()
            assert permissions.count('manage_users') == 1
    
    def test_create_system_roles(self, app):
        """Test creation of default system roles."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            roles = Role.create_system_roles(tenant.id)
            
            assert len(roles) == 5
            
            # Check all expected roles were created
            role_names = [role.name for role in roles]
            assert "Owner" in role_names
            assert "Manager" in role_names
            assert "Support" in role_names
            assert "Accounting" in role_names
            assert "Read Only" in role_names
            
            # Check that all roles are system roles
            for role in roles:
                assert role.is_system_role is True
                assert role.tenant_id == tenant.id
                assert len(role.get_permissions()) > 0
            
            # Check specific role permissions
            owner_role = next(role for role in roles if role.name == "Owner")
            assert owner_role.has_permission('manage_users')
            assert owner_role.has_permission('manage_settings')
            assert owner_role.has_permission('manage_billing')
            
            readonly_role = next(role for role in roles if role.name == "Read Only")
            assert readonly_role.has_permission('view_crm')
            assert not readonly_role.has_permission('manage_users')
    
    def test_role_to_dict(self, app):
        """Test role dictionary conversion."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            role = Role(
                tenant_id=tenant.id,
                name="Test Role",
                description="Test description"
            )
            role.set_permissions(['view_crm', 'manage_calendar'])
            role.save()
            
            data = role.to_dict()
            
            assert data['name'] == "Test Role"
            assert data['description'] == "Test description"
            assert data['is_system_role'] is False
            assert data['is_active'] is True
            assert data['permissions'] == ['view_crm', 'manage_calendar']


class TestUserRoleIntegration:
    """Test User-Role integration functionality."""
    
    def test_user_role_assignment(self, app):
        """Test assigning roles to users."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Create roles
            manager_role = Role(tenant_id=tenant.id, name="Manager")
            manager_role.set_permissions(['manage_crm', 'view_analytics'])
            manager_role.save()
            
            support_role = Role(tenant_id=tenant.id, name="Support")
            support_role.set_permissions(['view_crm', 'manage_channels'])
            support_role.save()
            
            # Create user
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id
            )
            
            # Assign roles
            user.add_role(manager_role)
            user.add_role(support_role)
            user.save()
            
            # Test role assignment
            assert user.has_role("Manager")
            assert user.has_role("Support")
            assert not user.has_role("Owner")
            
            # Test permissions from roles
            assert user.has_permission('manage_crm')  # From manager role
            assert user.has_permission('view_analytics')  # From manager role
            assert user.has_permission('view_crm')  # From support role
            assert user.has_permission('manage_channels')  # From support role
            
            # Test get all permissions
            all_permissions = user.get_all_permissions()
            assert 'manage_crm' in all_permissions
            assert 'view_analytics' in all_permissions
            assert 'view_crm' in all_permissions
            assert 'manage_channels' in all_permissions
            
            # Test removing role
            user.remove_role(support_role)
            user.save()
            
            assert user.has_role("Manager")
            assert not user.has_role("Support")
            assert user.has_permission('manage_crm')  # Still from manager
            assert not user.has_permission('manage_channels')  # No longer has support role
    
    def test_user_to_dict_with_roles(self, app):
        """Test user dictionary conversion with roles."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Create role
            role = Role(tenant_id=tenant.id, name="Test Role")
            role.set_permissions(['view_crm', 'manage_calendar'])
            role.save()
            
            # Create user with role
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id,
                first_name="John",
                last_name="Doe"
            )
            user.add_role(role)
            user.save()
            
            data = user.to_dict()
            
            assert data['email'] == "test@example.com"
            assert data['full_name'] == "John Doe"
            assert 'password_hash' not in data
            assert 'roles' in data
            assert len(data['roles']) == 1
            assert data['roles'][0]['name'] == "Test Role"
            assert 'permissions' in data
            assert 'view_crm' in data['permissions']
            assert 'manage_calendar' in data['permissions']


class TestPermissionConstants:
    """Test Permission constants and utilities."""
    
    def test_permission_constants(self, app):
        """Test that all permission constants are defined."""
        assert Permission.MANAGE_USERS == 'manage_users'
        assert Permission.MANAGE_ROLES == 'manage_roles'
        assert Permission.MANAGE_SETTINGS == 'manage_settings'
        assert Permission.MANAGE_BILLING == 'manage_billing'
        assert Permission.MANAGE_CHANNELS == 'manage_channels'
        assert Permission.MANAGE_KNOWLEDGE == 'manage_knowledge'
        assert Permission.VIEW_KNOWLEDGE == 'view_knowledge'
        assert Permission.MANAGE_CRM == 'manage_crm'
        assert Permission.VIEW_CRM == 'view_crm'
        assert Permission.MANAGE_CALENDAR == 'manage_calendar'
        assert Permission.VIEW_CALENDAR == 'view_calendar'
        assert Permission.MANAGE_KYB == 'manage_kyb'
        assert Permission.VIEW_KYB == 'view_kyb'
        assert Permission.VIEW_ANALYTICS == 'view_analytics'
        assert Permission.VIEW_AUDIT_LOGS == 'view_audit_logs'
    
    def test_get_all_permissions(self, app):
        """Test getting all available permissions."""
        all_permissions = Permission.get_all_permissions()
        
        assert isinstance(all_permissions, list)
        assert len(all_permissions) > 10
        assert Permission.MANAGE_USERS in all_permissions
        assert Permission.VIEW_CRM in all_permissions
        assert Permission.MANAGE_BILLING in all_permissions
    
    def test_get_permission_groups(self, app):
        """Test getting permissions grouped by category."""
        groups = Permission.get_permission_groups()
        
        assert isinstance(groups, dict)
        assert 'User Management' in groups
        assert 'CRM' in groups
        assert 'Billing' in groups
        
        assert Permission.MANAGE_USERS in groups['User Management']
        assert Permission.VIEW_CRM in groups['CRM']
        assert Permission.MANAGE_BILLING in groups['Billing']