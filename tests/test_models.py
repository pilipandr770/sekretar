"""Test models functionality."""
import pytest
from datetime import datetime, timedelta
from app.models.tenant import Tenant
from app.models.user import User
from app.models.audit_log import AuditLog
from app import db


class TestTenant:
    """Test Tenant model."""
    
    def test_create_tenant(self, app):
        """Test tenant creation."""
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
            assert tenant.is_active is True
            assert tenant.subscription_status == "trial"
    
    def test_tenant_settings(self, app):
        """Test tenant settings functionality."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Test setting values
            tenant.set_setting("feature_x", True)
            tenant.set_setting("max_users", 10)
            tenant.save()
            
            assert tenant.get_setting("feature_x") is True
            assert tenant.get_setting("max_users") == 10
            assert tenant.get_setting("nonexistent") is None
            assert tenant.get_setting("nonexistent", "default") == "default"
    
    def test_create_with_owner(self, app):
        """Test creating tenant with owner user."""
        with app.app_context():
            tenant, owner = Tenant.create_with_owner(
                name="Test Company",
                owner_email="owner@test.com",
                owner_password="password123"
            )
            
            assert tenant.id is not None
            assert owner.id is not None
            assert owner.tenant_id == tenant.id
            assert owner.role == "owner"
            assert owner.email == "owner@test.com"
    
    def test_trial_expiration(self, app):
        """Test trial expiration logic."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            
            # Test active trial
            future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
            tenant.trial_ends_at = future_date
            assert not tenant.is_trial_expired()
            
            # Test expired trial
            past_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
            tenant.trial_ends_at = past_date
            assert tenant.is_trial_expired()


class TestUser:
    """Test User model."""
    
    def test_create_user(self, app):
        """Test user creation."""
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
            assert user.full_name == "John Doe"
            assert user.check_password("password123")
    
    def test_password_hashing(self, app):
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
            
            # Should verify correct password
            assert user.check_password("password123")
            
            # Should reject incorrect password
            assert not user.check_password("wrongpassword")
    
    def test_user_permissions(self, app):
        """Test user permission system."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Test owner permissions
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
            assert owner.has_permission("manage_users")
            
            # Test read-only permissions
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
            assert not readonly.has_permission("manage_users")
            assert readonly.has_permission("view_crm")
    
    def test_password_reset_token(self, app):
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
            assert user.password_reset_token == token
            assert user.password_reset_expires is not None
            
            # Verify token
            assert user.verify_password_reset_token(token)
            assert not user.verify_password_reset_token("invalid_token")
            
            # Clear token
            user.clear_password_reset_token()
            user.save()
            
            assert user.password_reset_token is None
            assert user.password_reset_expires is None
    
    def test_user_authentication(self, app):
        """Test user authentication."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id
            )
            
            # Test successful authentication
            authenticated = User.authenticate("test@example.com", "password123", tenant.id)
            assert authenticated is not None
            assert authenticated.id == user.id
            
            # Test failed authentication
            assert User.authenticate("test@example.com", "wrongpassword", tenant.id) is None
            assert User.authenticate("wrong@example.com", "password123", tenant.id) is None


class TestAuditLog:
    """Test AuditLog model."""
    
    def test_create_audit_log(self, app):
        """Test audit log creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id
            )
            
            log = AuditLog.log_action(
                action="create",
                resource_type="user",
                tenant_id=tenant.id,
                user_id=user.id,
                resource_id=user.id,
                new_values={"email": "test@example.com"},
                ip_address="127.0.0.1"
            )
            
            assert log.id is not None
            assert log.action == "create"
            assert log.resource_type == "user"
            assert log.tenant_id == tenant.id
            assert log.user_id == user.id
            assert log.ip_address == "127.0.0.1"
    
    def test_log_user_action(self, app):
        """Test logging user actions."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id
            )
            
            log = AuditLog.log_user_action(
                user=user,
                action="update",
                resource_type="profile",
                resource_id=user.id,
                old_values={"name": "Old Name"},
                new_values={"name": "New Name"}
            )
            
            assert log.tenant_id == tenant.id
            assert log.user_id == user.id
            assert log.action == "update"
            assert log.old_values == {"name": "Old Name"}
            assert log.new_values == {"name": "New Name"}
    
    def test_log_login_logout(self, app):
        """Test login/logout logging."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            user = User.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id
            )
            
            # Test login log
            login_log = AuditLog.log_login(
                user=user,
                ip_address="127.0.0.1",
                user_agent="Test Browser"
            )
            
            assert login_log.action == "login"
            assert login_log.resource_type == "user"
            assert login_log.status == "success"
            
            # Test logout log
            logout_log = AuditLog.log_logout(
                user=user,
                ip_address="127.0.0.1"
            )
            
            assert logout_log.action == "logout"
            assert logout_log.resource_type == "user"