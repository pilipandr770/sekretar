"""Tests for tenant management API endpoints."""
import pytest
import json
from unittest.mock import patch, MagicMock
from flask_jwt_extended import create_access_token
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role
from app.models.audit_log import AuditLog


class TestTenantAPI:
    """Test tenant management API endpoints."""
    
    @pytest.fixture
    def tenant_with_users(self, db_session):
        """Create tenant with multiple users for testing."""
        # Create tenant
        tenant = Tenant(
            name="Test Organization",
            slug="test-org",
            email="admin@test.com",
            subscription_status="active"
        )
        tenant.save()
        
        # Create owner user
        owner = User.create(
            email="owner@test.com",
            password="password123",
            tenant_id=tenant.id,
            role="owner",
            first_name="Owner",
            last_name="User",
            is_active=True
        )
        
        # Create manager user
        manager = User.create(
            email="manager@test.com",
            password="password123",
            tenant_id=tenant.id,
            role="manager",
            first_name="Manager",
            last_name="User",
            is_active=True
        )
        
        # Create support user
        support = User.create(
            email="support@test.com",
            password="password123",
            tenant_id=tenant.id,
            role="support",
            first_name="Support",
            last_name="User",
            is_active=True
        )
        
        return {
            'tenant': tenant,
            'owner': owner,
            'manager': manager,
            'support': support
        }
    
    def test_get_tenant_success(self, client, tenant_with_users):
        """Test successful tenant retrieval."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = client.get('/api/v1/tenant/', headers=headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'tenant' in data['data']
        assert 'stats' in data['data']
        assert data['data']['tenant']['name'] == "Test Organization"
        assert data['data']['stats']['user_count'] == 3
        assert data['data']['stats']['subscription_status'] == "active"
    
    def test_get_tenant_unauthorized(self, client):
        """Test tenant retrieval without authentication."""
        response = client.get('/api/v1/tenant/')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error']['code'] == 'TOKEN_REQUIRED'
    
    def test_update_tenant_success(self, client, tenant_with_users):
        """Test successful tenant update."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        update_data = {
            'name': 'Updated Organization',
            'email': 'updated@test.com',
            'phone': '+1234567890'
        }
        
        response = client.put('/api/v1/tenant/', 
                            headers=headers, 
                            data=json.dumps(update_data))
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['name'] == 'Updated Organization'
        assert data['data']['email'] == 'updated@test.com'
        assert data['data']['phone'] == '+1234567890'
    
    def test_update_tenant_invalid_email(self, client, tenant_with_users):
        """Test tenant update with invalid email."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        update_data = {
            'email': 'invalid-email'
        }
        
        response = client.put('/api/v1/tenant/', 
                            headers=headers, 
                            data=json.dumps(update_data))
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'email' in data['error']['details']['validation_errors']
    
    def test_update_tenant_insufficient_permissions(self, client, tenant_with_users):
        """Test tenant update with insufficient permissions."""
        tenant_data = tenant_with_users
        support = tenant_data['support']
        
        # Create access token for support user (no manage_settings permission)
        access_token = create_access_token(identity=support)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        update_data = {
            'name': 'Updated Organization'
        }
        
        response = client.put('/api/v1/tenant/', 
                            headers=headers, 
                            data=json.dumps(update_data))
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error']['code'] == 'AUTHORIZATION_ERROR'
    
    def test_get_tenant_settings_success(self, client, tenant_with_users):
        """Test successful tenant settings retrieval."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        tenant = tenant_data['tenant']
        
        # Set some settings
        tenant.settings = {'feature_x': True, 'max_users': 10}
        tenant.save()
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = client.get('/api/v1/tenant/settings', headers=headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['settings']['feature_x'] is True
        assert data['data']['settings']['max_users'] == 10
        assert data['data']['subscription_status'] == 'active'
    
    def test_update_tenant_settings_success(self, client, tenant_with_users):
        """Test successful tenant settings update."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        settings_data = {
            'settings': {
                'feature_y': False,
                'notification_email': 'notify@test.com'
            }
        }
        
        response = client.put('/api/v1/tenant/settings', 
                            headers=headers, 
                            data=json.dumps(settings_data))
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['settings']['feature_y'] is False
        assert data['data']['settings']['notification_email'] == 'notify@test.com'
    
    def test_list_tenant_users_success(self, client, tenant_with_users):
        """Test successful tenant users listing."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = client.get('/api/v1/tenant/users', headers=headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 3
        assert data['data']['pagination']['total'] == 3
        
        # Check user data
        emails = [user['email'] for user in data['data']['items']]
        assert 'owner@test.com' in emails
        assert 'manager@test.com' in emails
        assert 'support@test.com' in emails
    
    def test_list_tenant_users_with_filters(self, client, tenant_with_users):
        """Test tenant users listing with filters."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Filter by role
        response = client.get('/api/v1/tenant/users?role=manager', headers=headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['email'] == 'manager@test.com'
    
    def test_list_tenant_users_with_search(self, client, tenant_with_users):
        """Test tenant users listing with search."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Search by name
        response = client.get('/api/v1/tenant/users?search=Support', headers=headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['first_name'] == 'Support'
    
    def test_create_tenant_user_success(self, client, tenant_with_users):
        """Test successful tenant user creation."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        user_data = {
            'email': 'newuser@test.com',
            'role': 'support',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = client.post('/api/v1/tenant/users', 
                             headers=headers, 
                             data=json.dumps(user_data))
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['user']['email'] == 'newuser@test.com'
        assert data['data']['user']['role'] == 'support'
        assert data['data']['user']['first_name'] == 'New'
        assert 'temporary_password' in data['data']
    
    def test_create_tenant_user_invalid_email(self, client, tenant_with_users):
        """Test tenant user creation with invalid email."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        user_data = {
            'email': 'invalid-email',
            'role': 'support'
        }
        
        response = client.post('/api/v1/tenant/users', 
                             headers=headers, 
                             data=json.dumps(user_data))
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'email' in data['error']['details']['validation_errors']
    
    def test_create_tenant_user_duplicate_email(self, client, tenant_with_users):
        """Test tenant user creation with duplicate email."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        user_data = {
            'email': 'manager@test.com',  # Already exists
            'role': 'support'
        }
        
        response = client.post('/api/v1/tenant/users', 
                             headers=headers, 
                             data=json.dumps(user_data))
        
        assert response.status_code == 409
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error']['code'] == 'CONFLICT_ERROR'
    
    def test_create_owner_user_non_owner(self, client, tenant_with_users):
        """Test creating owner user by non-owner."""
        tenant_data = tenant_with_users
        manager = tenant_data['manager']
        
        # Create access token for manager
        access_token = create_access_token(identity=manager)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        user_data = {
            'email': 'newowner@test.com',
            'role': 'owner'
        }
        
        response = client.post('/api/v1/tenant/users', 
                             headers=headers, 
                             data=json.dumps(user_data))
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error']['code'] == 'AUTHORIZATION_ERROR'
    
    def test_get_tenant_user_success(self, client, tenant_with_users):
        """Test successful tenant user retrieval."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        manager = tenant_data['manager']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = client.get(f'/api/v1/tenant/users/{manager.id}', headers=headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['email'] == 'manager@test.com'
        assert data['data']['role'] == 'manager'
    
    def test_get_tenant_user_not_found(self, client, tenant_with_users):
        """Test tenant user retrieval with non-existent user."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = client.get('/api/v1/tenant/users/99999', headers=headers)
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error']['code'] == 'NOT_FOUND_ERROR'
    
    def test_update_tenant_user_success(self, client, tenant_with_users):
        """Test successful tenant user update."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        manager = tenant_data['manager']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        update_data = {
            'first_name': 'Updated',
            'last_name': 'Manager',
            'role': 'support'
        }
        
        response = client.put(f'/api/v1/tenant/users/{manager.id}', 
                            headers=headers, 
                            data=json.dumps(update_data))
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['first_name'] == 'Updated'
        assert data['data']['last_name'] == 'Manager'
        assert data['data']['role'] == 'support'
    
    def test_update_tenant_user_self_deactivation(self, client, tenant_with_users):
        """Test preventing self-deactivation."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        update_data = {
            'is_active': False
        }
        
        response = client.put(f'/api/v1/tenant/users/{owner.id}', 
                            headers=headers, 
                            data=json.dumps(update_data))
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error']['code'] == 'VALIDATION_ERROR'
    
    def test_delete_tenant_user_success(self, client, tenant_with_users):
        """Test successful tenant user deletion."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        support = tenant_data['support']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = client.delete(f'/api/v1/tenant/users/{support.id}', headers=headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Verify user is deactivated
        support.refresh()
        assert support.is_active is False
    
    def test_delete_tenant_user_self_deletion(self, client, tenant_with_users):
        """Test preventing self-deletion."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = client.delete(f'/api/v1/tenant/users/{owner.id}', headers=headers)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error']['code'] == 'VALIDATION_ERROR'
    
    def test_resend_user_invitation_success(self, client, tenant_with_users):
        """Test successful invitation resend."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        support = tenant_data['support']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = client.post(f'/api/v1/tenant/users/{support.id}/invite', headers=headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Verify token was generated
        support.refresh()
        assert support.email_verification_token is not None
    
    @patch('app.models.audit_log.AuditLog.log_user_action')
    def test_audit_logging(self, mock_audit_log, client, tenant_with_users):
        """Test that audit logs are created for tenant operations."""
        tenant_data = tenant_with_users
        owner = tenant_data['owner']
        
        # Create access token
        access_token = create_access_token(identity=owner)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Update tenant
        update_data = {'name': 'Audited Organization'}
        response = client.put('/api/v1/tenant/', 
                            headers=headers, 
                            data=json.dumps(update_data))
        
        assert response.status_code == 200
        
        # Verify audit log was called
        mock_audit_log.assert_called()
        call_args = mock_audit_log.call_args
        assert call_args[1]['action'] == 'update'
        assert call_args[1]['resource_type'] == 'tenant'
        assert call_args[1]['user'] == owner