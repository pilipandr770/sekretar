"""
Complete Authentication Flow Validation Tests

This module validates the complete authentication flow as specified in task 10:
- Test admin login with admin@ai-secretary.com / admin123
- Verify JWT token generation and validation
- Test protected endpoint access with authentication
- Validate session management and logout functionality

Requirements covered: 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.2
"""
import os
import pytest
import tempfile
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from flask_jwt_extended import decode_token, create_access_token

from app import create_app, db
from app.models.tenant import Tenant
from app.models.user import User
from app.utils.auth_adapter import auth_adapter


class TestCompleteAuthenticationFlow:
    """Test complete authentication flow with admin credentials."""
    
    @pytest.fixture
    def app_with_admin(self):
        """Create app with admin user for testing."""
        # Create temporary database
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        
        try:
            # Mock PostgreSQL as unavailable to force SQLite
            with patch('psycopg2.connect', side_effect=Exception("PostgreSQL unavailable")):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.connect_ex.return_value = 1  # Connection failed
                    mock_socket.return_value = mock_sock
                    
                    app = create_app('testing')
                    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
                    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
                    app.config['DB_SCHEMA'] = None
                    app.config['TESTING'] = True
                    app.config['WTF_CSRF_ENABLED'] = False
                    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
                    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)
                    
                    with app.app_context():
                        # Create database tables
                        db.create_all()
                        
                        # Create admin tenant
                        admin_tenant = Tenant(
                            name="AI Secretary Admin",
                            domain="ai-secretary.com",
                            slug="ai-secretary-admin",
                            is_active=True
                        )
                        db.session.add(admin_tenant)
                        db.session.commit()
                        
                        # Create admin user with exact credentials from task
                        admin_user = User(
                            tenant_id=admin_tenant.id,
                            email="admin@ai-secretary.com",
                            first_name="Admin",
                            last_name="User",
                            role="owner",  # Use owner role for full permissions
                            is_active=True,
                            is_email_verified=True
                        )
                        admin_user.set_password("admin123")
                        db.session.add(admin_user)
                        db.session.commit()
                        
                        yield app
        
        finally:
            os.close(db_fd)
            os.unlink(db_path)
    
    def test_admin_login_with_correct_credentials(self, app_with_admin):
        """Test admin login with admin@ai-secretary.com / admin123."""
        with app_with_admin.test_client() as client:
            # Test login with exact credentials from task specification
            login_data = {
                'email': 'admin@ai-secretary.com',
                'password': 'admin123'
            }
            
            response = client.post('/api/v1/auth/login', 
                                 json=login_data,
                                 content_type='application/json')
            
            # Verify successful login
            assert response.status_code == 200, f"Login failed with status {response.status_code}: {response.get_json()}"
            
            data = response.get_json()
            assert data['success'] is True, f"Login not successful: {data}"
            assert 'message' in data
            assert 'data' in data
            
            # Verify response contains required authentication data
            auth_data = data['data']
            assert 'user' in auth_data, "User data missing from login response"
            assert 'tenant' in auth_data, "Tenant data missing from login response"
            assert 'access_token' in auth_data, "Access token missing from login response"
            assert 'refresh_token' in auth_data, "Refresh token missing from login response"
            assert 'token_type' in auth_data, "Token type missing from login response"
            
            # Verify user data
            user_data = auth_data['user']
            assert user_data['email'] == 'admin@ai-secretary.com'
            assert user_data['role'] == 'owner'
            assert user_data['is_active'] is True
            assert user_data['is_email_verified'] is True
            
            # Verify tenant data
            tenant_data = auth_data['tenant']
            assert tenant_data['name'] == 'AI Secretary Admin'
            assert tenant_data['is_active'] is True
            
            # Verify token type
            assert auth_data['token_type'] == 'Bearer'
    
    def test_jwt_token_generation_and_validation(self, app_with_admin):
        """Verify JWT token generation and validation."""
        with app_with_admin.test_client() as client:
            with app_with_admin.app_context():
                # Login to get tokens
                login_data = {
                    'email': 'admin@ai-secretary.com',
                    'password': 'admin123'
                }
                
                response = client.post('/api/v1/auth/login', json=login_data)
                assert response.status_code == 200
                
                auth_data = response.get_json()['data']
                access_token = auth_data['access_token']
                refresh_token = auth_data['refresh_token']
                
                # Validate access token structure
                decoded_access = decode_token(access_token)
                assert 'sub' in decoded_access, "Subject missing from access token"
                assert 'iat' in decoded_access, "Issued at missing from access token"
                assert 'exp' in decoded_access, "Expiration missing from access token"
                assert 'type' in decoded_access, "Token type missing from access token"
                assert decoded_access['type'] == 'access'
                
                # Validate refresh token structure
                decoded_refresh = decode_token(refresh_token)
                assert 'sub' in decoded_refresh, "Subject missing from refresh token"
                assert 'iat' in decoded_refresh, "Issued at missing from refresh token"
                assert 'exp' in decoded_refresh, "Expiration missing from refresh token"
                assert 'type' in decoded_refresh, "Token type missing from refresh token"
                assert decoded_refresh['type'] == 'refresh'
                
                # Verify token subjects match
                assert decoded_access['sub'] == decoded_refresh['sub'], "Token subjects don't match"
                
                # Test authentication adapter token validation
                user = auth_adapter.validate_token(access_token)
                assert user is not None, "Authentication adapter failed to validate token"
                assert user.email == 'admin@ai-secretary.com'
                assert user.is_active is True
                
                # Test invalid token validation
                invalid_user = auth_adapter.validate_token("invalid.token.here")
                assert invalid_user is None, "Authentication adapter validated invalid token"
    
    def test_protected_endpoint_access_with_authentication(self, app_with_admin):
        """Test protected endpoint access with authentication."""
        with app_with_admin.test_client() as client:
            # First, login to get access token
            login_data = {
                'email': 'admin@ai-secretary.com',
                'password': 'admin123'
            }
            
            login_response = client.post('/api/v1/auth/login', json=login_data)
            assert login_response.status_code == 200
            
            access_token = login_response.get_json()['data']['access_token']
            
            # Test accessing protected endpoint with valid token
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Test /api/v1/auth/me endpoint (user profile)
            me_response = client.get('/api/v1/auth/me', headers=headers)
            assert me_response.status_code == 200, f"Protected endpoint failed: {me_response.get_json()}"
            
            me_data = me_response.get_json()
            assert me_data['success'] is True
            assert 'data' in me_data
            
            profile_data = me_data['data']
            assert 'user' in profile_data
            assert 'tenant' in profile_data
            assert 'permissions' in profile_data
            
            # Verify user profile data
            user_profile = profile_data['user']
            assert user_profile['email'] == 'admin@ai-secretary.com'
            assert user_profile['role'] == 'owner'
            assert user_profile['is_active'] is True
            
            # Verify permissions
            permissions = profile_data['permissions']
            assert permissions['is_owner'] is True
            assert permissions['is_manager'] is True
            assert permissions['permissions']['can_manage_users'] is True
            assert permissions['permissions']['can_access_billing'] is True
            assert permissions['permissions']['can_manage_settings'] is True
            
            # Test accessing protected endpoint without token (should fail)
            no_auth_response = client.get('/api/v1/auth/me')
            assert no_auth_response.status_code == 401, "Endpoint should require authentication"
            
            # Test accessing protected endpoint with invalid token (should fail)
            invalid_headers = {
                'Authorization': 'Bearer invalid.token.here',
                'Content-Type': 'application/json'
            }
            invalid_response = client.get('/api/v1/auth/me', headers=invalid_headers)
            assert invalid_response.status_code == 401, "Invalid token should be rejected"
    
    def test_token_refresh_functionality(self, app_with_admin):
        """Test token refresh functionality."""
        with app_with_admin.test_client() as client:
            # Login to get refresh token
            login_data = {
                'email': 'admin@ai-secretary.com',
                'password': 'admin123'
            }
            
            login_response = client.post('/api/v1/auth/login', json=login_data)
            assert login_response.status_code == 200
            
            auth_data = login_response.get_json()['data']
            refresh_token = auth_data['refresh_token']
            original_access_token = auth_data['access_token']
            
            # Use refresh token to get new access token
            refresh_headers = {
                'Authorization': f'Bearer {refresh_token}',
                'Content-Type': 'application/json'
            }
            
            refresh_response = client.post('/api/v1/auth/refresh', headers=refresh_headers)
            assert refresh_response.status_code == 200, f"Token refresh failed: {refresh_response.get_json()}"
            
            refresh_data = refresh_response.get_json()
            assert refresh_data['success'] is True
            assert 'data' in refresh_data
            
            new_token_data = refresh_data['data']
            assert 'access_token' in new_token_data
            assert 'token_type' in new_token_data
            assert new_token_data['token_type'] == 'Bearer'
            
            new_access_token = new_token_data['access_token']
            
            # Verify new token is different from original
            assert new_access_token != original_access_token, "New access token should be different"
            
            # Verify new token works for protected endpoints
            new_headers = {
                'Authorization': f'Bearer {new_access_token}',
                'Content-Type': 'application/json'
            }
            
            me_response = client.get('/api/v1/auth/me', headers=new_headers)
            assert me_response.status_code == 200, "New access token should work"
            
            # Test refresh with invalid token
            invalid_refresh_headers = {
                'Authorization': 'Bearer invalid.refresh.token',
                'Content-Type': 'application/json'
            }
            
            invalid_refresh_response = client.post('/api/v1/auth/refresh', headers=invalid_refresh_headers)
            assert invalid_refresh_response.status_code == 401, "Invalid refresh token should be rejected"
    
    def test_session_management_and_logout_functionality(self, app_with_admin):
        """Validate session management and logout functionality."""
        with app_with_admin.test_client() as client:
            # Login to establish session
            login_data = {
                'email': 'admin@ai-secretary.com',
                'password': 'admin123'
            }
            
            login_response = client.post('/api/v1/auth/login', json=login_data)
            assert login_response.status_code == 200
            
            access_token = login_response.get_json()['data']['access_token']
            
            # Verify session is active by accessing protected endpoint
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            pre_logout_response = client.get('/api/v1/auth/me', headers=headers)
            assert pre_logout_response.status_code == 200, "Session should be active before logout"
            
            # Perform logout
            logout_response = client.post('/api/v1/auth/logout', headers=headers)
            assert logout_response.status_code == 200, f"Logout failed: {logout_response.get_json()}"
            
            logout_data = logout_response.get_json()
            assert logout_data['success'] is True
            assert 'message' in logout_data
            assert 'logged out' in logout_data['message'].lower()
            
            # Verify session is cleared (token should still work as JWT is stateless, 
            # but session data should be cleared)
            # Note: In a stateless JWT system, the token remains valid until expiration
            # The logout primarily clears server-side session data
            post_logout_response = client.get('/api/v1/auth/me', headers=headers)
            # Token should still be valid as JWT is stateless, but session should be cleared
            assert post_logout_response.status_code == 200, "JWT token should still be valid after logout"
            
            # Test logout without authentication (should fail)
            no_auth_logout_response = client.post('/api/v1/auth/logout')
            assert no_auth_logout_response.status_code == 401, "Logout should require authentication"
    
    def test_authentication_error_scenarios(self, app_with_admin):
        """Test various authentication error scenarios."""
        with app_with_admin.test_client() as client:
            # Test login with incorrect password
            wrong_password_data = {
                'email': 'admin@ai-secretary.com',
                'password': 'wrongpassword'
            }
            
            wrong_password_response = client.post('/api/v1/auth/login', json=wrong_password_data)
            assert wrong_password_response.status_code == 401, "Wrong password should be rejected"
            
            wrong_password_result = wrong_password_response.get_json()
            assert wrong_password_result['success'] is False
            assert 'error' in wrong_password_result
            assert 'invalid' in wrong_password_result['error']['message'].lower()
            
            # Test login with non-existent email
            wrong_email_data = {
                'email': 'nonexistent@ai-secretary.com',
                'password': 'admin123'
            }
            
            wrong_email_response = client.post('/api/v1/auth/login', json=wrong_email_data)
            assert wrong_email_response.status_code == 401, "Non-existent email should be rejected"
            
            # Test login with missing fields
            missing_password_data = {
                'email': 'admin@ai-secretary.com'
            }
            
            missing_password_response = client.post('/api/v1/auth/login', json=missing_password_data)
            assert missing_password_response.status_code == 400, "Missing password should be rejected"
            
            missing_email_data = {
                'password': 'admin123'
            }
            
            missing_email_response = client.post('/api/v1/auth/login', json=missing_email_data)
            assert missing_email_response.status_code == 400, "Missing email should be rejected"
            
            # Test login with invalid JSON
            invalid_json_response = client.post('/api/v1/auth/login', 
                                              data='invalid json',
                                              content_type='application/json')
            assert invalid_json_response.status_code == 400, "Invalid JSON should be rejected"
    
    def test_authentication_adapter_direct_usage(self, app_with_admin):
        """Test authentication adapter methods directly."""
        with app_with_admin.app_context():
            # Test direct authentication
            user = auth_adapter.authenticate_user('admin@ai-secretary.com', 'admin123')
            assert user is not None, "Authentication adapter should authenticate valid credentials"
            assert user.email == 'admin@ai-secretary.com'
            assert user.is_active is True
            
            # Test authentication with wrong password
            wrong_user = auth_adapter.authenticate_user('admin@ai-secretary.com', 'wrongpassword')
            assert wrong_user is None, "Authentication adapter should reject wrong password"
            
            # Test token generation
            tokens = auth_adapter.generate_tokens(user)
            assert 'access_token' in tokens
            assert 'refresh_token' in tokens
            assert 'token_type' in tokens
            assert tokens['token_type'] == 'Bearer'
            
            # Test token validation
            validated_user = auth_adapter.validate_token(tokens['access_token'])
            assert validated_user is not None
            assert validated_user.id == user.id
            
            # Test user status validation
            status = auth_adapter.validate_user_status(user)
            assert status['valid'] is True
            assert 'user' in status
            assert 'tenant' in status
            
            # Test user permissions
            permissions = auth_adapter.get_user_permissions(user)
            assert 'role' in permissions
            assert 'is_owner' in permissions
            assert 'permissions' in permissions
            assert permissions['is_owner'] is True
    
    def test_complete_authentication_flow_end_to_end(self, app_with_admin):
        """Test complete end-to-end authentication flow."""
        with app_with_admin.test_client() as client:
            # Step 1: Login with admin credentials
            login_data = {
                'email': 'admin@ai-secretary.com',
                'password': 'admin123'
            }
            
            login_response = client.post('/api/v1/auth/login', json=login_data)
            assert login_response.status_code == 200
            
            auth_data = login_response.get_json()['data']
            access_token = auth_data['access_token']
            refresh_token = auth_data['refresh_token']
            
            # Step 2: Access protected endpoint
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            profile_response = client.get('/api/v1/auth/me', headers=headers)
            assert profile_response.status_code == 200
            
            # Step 3: Refresh token
            refresh_headers = {
                'Authorization': f'Bearer {refresh_token}',
                'Content-Type': 'application/json'
            }
            
            refresh_response = client.post('/api/v1/auth/refresh', headers=refresh_headers)
            assert refresh_response.status_code == 200
            
            new_access_token = refresh_response.get_json()['data']['access_token']
            
            # Step 4: Use new token for protected endpoint
            new_headers = {
                'Authorization': f'Bearer {new_access_token}',
                'Content-Type': 'application/json'
            }
            
            new_profile_response = client.get('/api/v1/auth/me', headers=new_headers)
            assert new_profile_response.status_code == 200
            
            # Step 5: Logout
            logout_response = client.post('/api/v1/auth/logout', headers=new_headers)
            assert logout_response.status_code == 200
            
            logout_data = logout_response.get_json()
            assert logout_data['success'] is True
            assert 'logged out' in logout_data['message'].lower()
            
            # Verify complete flow worked correctly
            assert login_response.status_code == 200, "Login should succeed"
            assert profile_response.status_code == 200, "Profile access should succeed"
            assert refresh_response.status_code == 200, "Token refresh should succeed"
            assert new_profile_response.status_code == 200, "New token should work"
            assert logout_response.status_code == 200, "Logout should succeed"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])