"""Tests for role-based access control and authorization."""
import pytest
from flask import url_for
from flask_jwt_extended import create_access_token
from app.models.user import User
from app.models.role import Role, Permission
from app.models.tenant import Tenant
from app import db


class TestRoleBasedAccessControl:
    """Test role-based access control functionality."""
    
    def test_user_has_permission_with_roles(self, app, tenant, owner_user):
        """Test user permission checking with role-based system."""
        with app.app_context():
            # Create a custom role with specific permissions
            role = Role(
                tenant_id=tenant.id,
                name='Custom Role',
                description='Test role'
            )
            role.set_permissions([Permission.MANAGE_CRM, Permission.VIEW_KNOWLEDGE])
            role.save()
            
            # Create user and assign role
            user = User.create(
                email='test@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='support'
            )
            user.add_role(role)
            user.save()
            
            # Test permissions
            assert user.has_permission(Permission.MANAGE_CRM)
            assert user.has_permission(Permission.VIEW_KNOWLEDGE)
            assert not user.has_permission(Permission.MANAGE_BILLING)
    
    def test_user_has_permission_legacy_role(self, app, tenant):
        """Test user permission checking with legacy role system."""
        with app.app_context():
            # Create user with legacy role
            user = User.create(
                email='support@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='support'
            )
            
            # Test legacy role permissions
            assert user.has_permission(Permission.MANAGE_CRM)
            assert user.has_permission(Permission.VIEW_KNOWLEDGE)
            assert not user.has_permission(Permission.MANAGE_BILLING)
    
    def test_role_permission_management(self, app, tenant):
        """Test role permission management methods."""
        with app.app_context():
            role = Role(
                tenant_id=tenant.id,
                name='Test Role',
                description='Test role'
            )
            role.save()
            
            # Test adding permissions
            role.add_permission(Permission.MANAGE_CRM)
            role.add_permission(Permission.VIEW_KNOWLEDGE)
            
            permissions = role.get_permissions()
            assert Permission.MANAGE_CRM in permissions
            assert Permission.VIEW_KNOWLEDGE in permissions
            
            # Test removing permissions
            role.remove_permission(Permission.MANAGE_CRM)
            permissions = role.get_permissions()
            assert Permission.MANAGE_CRM not in permissions
            assert Permission.VIEW_KNOWLEDGE in permissions
    
    def test_system_roles_creation(self, app, tenant):
        """Test creation of system roles."""
        with app.app_context():
            roles = Role.create_system_roles(tenant.id)
            
            assert len(roles) == 5
            role_names = [role.name for role in roles]
            assert 'Owner' in role_names
            assert 'Manager' in role_names
            assert 'Support' in role_names
            assert 'Accounting' in role_names
            assert 'Read Only' in role_names
            
            # Test owner role permissions
            owner_role = next(role for role in roles if role.name == 'Owner')
            assert owner_role.has_permission(Permission.MANAGE_USERS)
            assert owner_role.has_permission(Permission.MANAGE_BILLING)
            assert owner_role.is_system_role
    
    def test_user_role_assignment(self, app, tenant):
        """Test user role assignment and removal."""
        with app.app_context():
            user = User.create(
                email='test@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='support'
            )
            
            role = Role(
                tenant_id=tenant.id,
                name='Custom Role',
                description='Test role'
            )
            role.set_permissions([Permission.MANAGE_CRM])
            role.save()
            
            # Test role assignment
            user.add_role(role)
            assert user.has_role('Custom Role')
            assert user.has_permission(Permission.MANAGE_CRM)
            
            # Test role removal
            user.remove_role(role)
            assert not user.has_role('Custom Role')


class TestPermissionDecorators:
    """Test permission decorators."""
    
    def test_require_permission_decorator(self, client, app, tenant, owner_user):
        """Test require_permission decorator."""
        with app.app_context():
            # Create access token
            access_token = create_access_token(identity=owner_user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            # Test with sufficient permissions (owner has all permissions)
            response = client.get('/api/v1/admin/users', headers=headers)
            assert response.status_code == 200
            
            # Create user with limited permissions
            limited_user = User.create(
                email='limited@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='read_only'
            )
            
            limited_token = create_access_token(identity=limited_user)
            limited_headers = {'Authorization': f'Bearer {limited_token}'}
            
            # Test with insufficient permissions
            response = client.get('/api/v1/admin/users', headers=limited_headers)
            assert response.status_code == 403
            assert 'Permission required' in response.get_json()['error']['message']
    
    def test_require_permissions_decorator(self, client, app, tenant):
        """Test require_permissions decorator (multiple permissions)."""
        with app.app_context():
            # Create role with partial permissions
            role = Role(
                tenant_id=tenant.id,
                name='Partial Role',
                description='Role with some permissions'
            )
            role.set_permissions([Permission.MANAGE_CRM])  # Missing MANAGE_USERS
            role.save()
            
            user = User.create(
                email='partial@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='support'
            )
            user.add_role(role)
            user.save()
            
            access_token = create_access_token(identity=user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            # This would fail if endpoint required both MANAGE_CRM and MANAGE_USERS
            # For now, just test that the decorator exists and works
            response = client.get('/api/v1/admin/permissions', headers=headers)
            # Should fail because user doesn't have MANAGE_ROLES permission
            assert response.status_code == 403
    
    def test_require_owner_or_permission_decorator(self, client, app, tenant, owner_user):
        """Test require_owner_or_permission decorator."""
        with app.app_context():
            # Test with owner user
            owner_token = create_access_token(identity=owner_user)
            owner_headers = {'Authorization': f'Bearer {owner_token}'}
            
            response = client.get('/api/v1/admin/roles', headers=owner_headers)
            assert response.status_code == 200  # Owner should have access
            
            # Test with user having the required permission
            role = Role(
                tenant_id=tenant.id,
                name='Role Manager',
                description='Can manage roles'
            )
            role.set_permissions([Permission.MANAGE_ROLES])
            role.save()
            
            user = User.create(
                email='rolemanager@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='manager'
            )
            user.add_role(role)
            user.save()
            
            user_token = create_access_token(identity=user)
            user_headers = {'Authorization': f'Bearer {user_token}'}
            
            response = client.get('/api/v1/admin/roles', headers=user_headers)
            assert response.status_code == 200  # User with permission should have access


class TestAdminEndpoints:
    """Test admin endpoints for user and role management."""
    
    def test_list_users_endpoint(self, client, app, tenant, owner_user):
        """Test listing users endpoint."""
        with app.app_context():
            # Create additional users
            User.create(
                email='user1@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='support'
            )
            User.create(
                email='user2@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='accounting'
            )
            
            access_token = create_access_token(identity=owner_user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = client.get('/api/v1/admin/users', headers=headers)
            assert response.status_code == 200
            
            data = response.get_json()
            assert 'users' in data['data']
            assert len(data['data']['users']) >= 3  # owner + 2 created users
            assert 'pagination' in data['data']
    
    def test_create_user_endpoint(self, client, app, tenant, owner_user):
        """Test creating user endpoint."""
        with app.app_context():
            access_token = create_access_token(identity=owner_user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            user_data = {
                'email': 'newuser@example.com',
                'role': 'support',
                'first_name': 'New',
                'last_name': 'User'
            }
            
            response = client.post('/api/v1/admin/users', 
                                 json=user_data, 
                                 headers=headers)
            assert response.status_code == 201
            
            data = response.get_json()
            assert data['data']['user']['email'] == 'newuser@example.com'
            assert data['data']['user']['role'] == 'support'
            assert 'temporary_password' in data['data']
    
    def test_create_user_validation(self, client, app, tenant, owner_user):
        """Test user creation validation."""
        with app.app_context():
            access_token = create_access_token(identity=owner_user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            # Test invalid email
            response = client.post('/api/v1/admin/users', 
                                 json={'email': 'invalid-email', 'role': 'support'}, 
                                 headers=headers)
            assert response.status_code == 400
            
            # Test invalid role
            response = client.post('/api/v1/admin/users', 
                                 json={'email': 'test@example.com', 'role': 'invalid_role'}, 
                                 headers=headers)
            assert response.status_code == 400
            
            # Test duplicate email
            User.create(
                email='existing@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='support'
            )
            
            response = client.post('/api/v1/admin/users', 
                                 json={'email': 'existing@example.com', 'role': 'support'}, 
                                 headers=headers)
            assert response.status_code == 409
    
    def test_update_user_endpoint(self, client, app, tenant, owner_user):
        """Test updating user endpoint."""
        with app.app_context():
            # Create user to update
            user = User.create(
                email='updateme@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='support'
            )
            
            access_token = create_access_token(identity=owner_user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            update_data = {
                'first_name': 'Updated',
                'last_name': 'Name',
                'role': 'accounting'
            }
            
            response = client.put(f'/api/v1/admin/users/{user.id}', 
                                json=update_data, 
                                headers=headers)
            assert response.status_code == 200
            
            data = response.get_json()
            assert data['data']['first_name'] == 'Updated'
            assert data['data']['role'] == 'accounting'
    
    def test_delete_user_endpoint(self, client, app, tenant, owner_user):
        """Test deleting user endpoint."""
        with app.app_context():
            # Create user to delete
            user = User.create(
                email='deleteme@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='support'
            )
            
            access_token = create_access_token(identity=owner_user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = client.delete(f'/api/v1/admin/users/{user.id}', 
                                   headers=headers)
            assert response.status_code == 200
            
            # Verify user is soft deleted
            db.session.refresh(user)
            assert user.is_deleted
    
    def test_list_roles_endpoint(self, client, app, tenant, owner_user):
        """Test listing roles endpoint."""
        with app.app_context():
            # Create system roles
            Role.create_system_roles(tenant.id)
            
            access_token = create_access_token(identity=owner_user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = client.get('/api/v1/admin/roles', headers=headers)
            assert response.status_code == 200
            
            data = response.get_json()
            assert 'roles' in data['data']
            assert 'available_permissions' in data['data']
            assert 'permission_groups' in data['data']
            assert len(data['data']['roles']) == 5  # 5 system roles
    
    def test_create_role_endpoint(self, client, app, tenant, owner_user):
        """Test creating role endpoint."""
        with app.app_context():
            access_token = create_access_token(identity=owner_user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            role_data = {
                'name': 'Custom Role',
                'description': 'A custom role for testing',
                'permissions': [Permission.MANAGE_CRM, Permission.VIEW_KNOWLEDGE]
            }
            
            response = client.post('/api/v1/admin/roles', 
                                 json=role_data, 
                                 headers=headers)
            assert response.status_code == 201
            
            data = response.get_json()
            assert data['data']['name'] == 'Custom Role'
            assert Permission.MANAGE_CRM in data['data']['permissions']
    
    def test_update_role_endpoint(self, client, app, tenant, owner_user):
        """Test updating role endpoint."""
        with app.app_context():
            # Create role to update
            role = Role(
                tenant_id=tenant.id,
                name='Update Me',
                description='Role to update'
            )
            role.set_permissions([Permission.VIEW_CRM])
            role.save()
            
            access_token = create_access_token(identity=owner_user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            update_data = {
                'name': 'Updated Role',
                'description': 'Updated description',
                'permissions': [Permission.MANAGE_CRM, Permission.VIEW_KNOWLEDGE]
            }
            
            response = client.put(f'/api/v1/admin/roles/{role.id}', 
                                json=update_data, 
                                headers=headers)
            assert response.status_code == 200
            
            data = response.get_json()
            assert data['data']['name'] == 'Updated Role'
            assert Permission.MANAGE_CRM in data['data']['permissions']
    
    def test_delete_role_endpoint(self, client, app, tenant, owner_user):
        """Test deleting role endpoint."""
        with app.app_context():
            # Create role to delete
            role = Role(
                tenant_id=tenant.id,
                name='Delete Me',
                description='Role to delete'
            )
            role.save()
            
            access_token = create_access_token(identity=owner_user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = client.delete(f'/api/v1/admin/roles/{role.id}', 
                                   headers=headers)
            assert response.status_code == 200
            
            # Verify role is soft deleted
            db.session.refresh(role)
            assert role.is_deleted
    
    def test_system_role_protection(self, client, app, tenant, owner_user):
        """Test that system roles cannot be modified or deleted."""
        with app.app_context():
            # Create system roles
            roles = Role.create_system_roles(tenant.id)
            owner_role = next(role for role in roles if role.name == 'Owner')
            
            access_token = create_access_token(identity=owner_user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            # Try to update system role
            response = client.put(f'/api/v1/admin/roles/{owner_role.id}', 
                                json={'name': 'Modified Owner'}, 
                                headers=headers)
            assert response.status_code == 400
            assert 'system roles' in response.get_json()['error']['message']
            
            # Try to delete system role
            response = client.delete(f'/api/v1/admin/roles/{owner_role.id}', 
                                   headers=headers)
            assert response.status_code == 400
            assert 'system roles' in response.get_json()['error']['message']


class TestMiddleware:
    """Test role validation middleware."""
    
    def test_inactive_user_blocked(self, client, app, tenant):
        """Test that inactive users are blocked by middleware."""
        with app.app_context():
            # Create inactive user
            user = User.create(
                email='inactive@example.com',
                password='password123',
                tenant_id=tenant.id,
                role='support',
                is_active=False
            )
            
            access_token = create_access_token(identity=user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = client.get('/api/v1/admin/users', headers=headers)
            assert response.status_code == 403
            assert 'disabled' in response.get_json()['error']['message']
    
    def test_inactive_tenant_blocked(self, client, app):
        """Test that users from inactive tenants are blocked."""
        with app.app_context():
            # Create inactive tenant
            inactive_tenant = Tenant(
                name='Inactive Tenant',
                domain='inactive.example.com',
                is_active=False
            )
            inactive_tenant.save()
            
            user = User.create(
                email='user@inactive.example.com',
                password='password123',
                tenant_id=inactive_tenant.id,
                role='support'
            )
            
            access_token = create_access_token(identity=user)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = client.get('/api/v1/admin/users', headers=headers)
            assert response.status_code == 403
            assert 'organization' in response.get_json()['error']['message']