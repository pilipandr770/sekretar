"""Comprehensive authentication endpoint tests with real user credentials.

This module implements comprehensive testing of authentication endpoints using
real company data from the comprehensive test dataset. Tests cover:
- Login/logout flow with real user credentials
- JWT token validation and refresh
- OAuth callback handling
- Error scenarios and edge cases

Requirements covered: 2.1, 2.2
"""
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import jwt


class TestAuthenticationEndpoints:
    """Comprehensive authentication endpoint tests."""
    
    @pytest.fixture
    def real_company_data(self):
        """Load real company data for testing."""
        try:
            with open('comprehensive_test_dataset.json', 'r') as f:
                dataset = json.load(f)
            return dataset['companies']
        except FileNotFoundError:
            # Fallback to minimal test data
            return {
                'sap_germany': {
                    'name': 'SAP SE',
                    'vat_number': 'DE143593636',
                    'country_code': 'DE',
                    'address': 'Dietmar-Hopp-Allee 16, 69190 Walldorf'
                }
            }

    @patch('app.models.tenant.Tenant.create_with_owner')
    def test_register_endpoint_with_real_company_data(self, mock_create_tenant, client, real_company_data):
        """Test user registration with real company data.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        
        # Mock successful tenant and user creation
        mock_tenant = MagicMock()
        mock_tenant.id = 1
        mock_tenant.name = company['name']
        mock_tenant.is_active = True
        mock_tenant.to_dict.return_value = {
            'id': 1,
            'name': company['name'],
            'is_active': True
        }
        
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = f'owner@{company["name"].lower().replace(" ", "-")}.test.com'
        mock_user.first_name = 'Company'
        mock_user.last_name = 'Owner'
        mock_user.is_active = True
        mock_user.tenant_id = 1
        mock_user.to_dict.return_value = {
            'id': 1,
            'email': f'owner@{company["name"].lower().replace(" ", "-")}.test.com',
            'first_name': 'Company',
            'last_name': 'Owner',
            'is_active': True
        }
        
        mock_create_tenant.return_value = (mock_tenant, mock_user)
        
        registration_data = {
            'email': f'owner@{company["name"].lower().replace(" ", "-")}.test.com',
            'password': 'SecurePassword123!',
            'organization_name': company['name'],
            'first_name': 'Company',
            'last_name': 'Owner',
            'language': 'en'
        }
        
        with patch('app.models.user.User.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = None  # No existing user
            
            with patch('flask_jwt_extended.create_access_token') as mock_access_token, \
                 patch('flask_jwt_extended.create_refresh_token') as mock_refresh_token, \
                 patch('app.models.audit_log.AuditLog.log_action'):
                
                mock_access_token.return_value = 'mock_access_token'
                mock_refresh_token.return_value = 'mock_refresh_token'
                
                response = client.post(
                    '/api/v1/auth/register',
                    json=registration_data,
                    headers={'Content-Type': 'application/json'}
                )
                
                assert response.status_code == 201
                data = response.get_json()
                
                # Verify response structure
                assert data['success'] is True
                assert 'data' in data
                assert 'user' in data['data']
                assert 'tenant' in data['data']
                assert 'access_token' in data['data']
                assert 'refresh_token' in data['data']
                
                # Verify tokens
                assert data['data']['access_token'] == 'mock_access_token'
                assert data['data']['refresh_token'] == 'mock_refresh_token'
                assert data['data']['token_type'] == 'Bearer'

    @patch('app.models.user.User.authenticate')
    def test_login_endpoint_with_valid_credentials(self, mock_authenticate, client, real_company_data):
        """Test login with valid user credentials.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        test_email = f'test@{company["name"].lower().replace(" ", "-")}.test.com'
        
        # Mock successful authentication
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = test_email
        mock_user.is_active = True
        mock_user.tenant_id = 1
        mock_user.language = 'en'
        mock_user.to_dict.return_value = {
            'id': 1,
            'email': test_email,
            'is_active': True
        }
        
        mock_tenant = MagicMock()
        mock_tenant.id = 1
        mock_tenant.name = company['name']
        mock_tenant.is_active = True
        mock_tenant.to_dict.return_value = {
            'id': 1,
            'name': company['name'],
            'is_active': True
        }
        
        mock_user.tenant = mock_tenant
        mock_authenticate.return_value = mock_user
        
        login_data = {
            'email': test_email,
            'password': 'SecurePassword123!'
        }
        
        with patch('flask_jwt_extended.create_access_token') as mock_access_token, \
             patch('flask_jwt_extended.create_refresh_token') as mock_refresh_token, \
             patch('app.models.audit_log.AuditLog.log_login'):
            
            mock_access_token.return_value = 'mock_access_token'
            mock_refresh_token.return_value = 'mock_refresh_token'
            
            response = client.post(
                '/api/v1/auth/login',
                json=login_data,
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Verify response structure
            assert data['success'] is True
            assert 'data' in data
            assert 'user' in data['data']
            assert 'tenant' in data['data']
            assert 'access_token' in data['data']
            assert 'refresh_token' in data['data']
            assert data['data']['token_type'] == 'Bearer'
            
            # Verify tokens
            assert data['data']['access_token'] == 'mock_access_token'
            assert data['data']['refresh_token'] == 'mock_refresh_token'

    @patch('app.models.user.User.authenticate')
    def test_login_endpoint_with_invalid_credentials(self, mock_authenticate, client, real_company_data):
        """Test login with invalid credentials.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        test_email = f'test@{company["name"].lower().replace(" ", "-")}.test.com'
        
        # Mock failed authentication
        mock_authenticate.return_value = None
        
        login_data = {
            'email': test_email,
            'password': 'WrongPassword123!'
        }
        
        with patch('app.models.audit_log.AuditLog.log_action'):
            response = client.post(
                '/api/v1/auth/login',
                json=login_data,
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 401
            data = response.get_json()
            
            assert data['success'] is False
            assert 'error' in data
            assert 'Invalid email or password' in data['error']['message']

    def test_jwt_token_validation(self, client, auth_headers, real_company_data):
        """Test JWT token validation for protected endpoints.
        
        Requirements: 2.2 - JWT token validation
        """
        company = list(real_company_data.values())[0]
        test_email = f'test@{company["name"].lower().replace(" ", "-")}.test.com'
        
        # Test protected endpoint with valid token (using auth_headers fixture)
        response = client.get('/api/v1/auth/me', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        assert 'data' in data
        assert 'user' in data['data']

    def test_jwt_token_validation_with_invalid_token(self, client):
        """Test JWT token validation with invalid token.
        
        Requirements: 2.2 - JWT token validation
        """
        # Test with invalid token
        headers = {
            'Authorization': 'Bearer invalid_token_here',
            'Content-Type': 'application/json'
        }
        
        response = client.get('/api/v1/auth/me', headers=headers)
        
        assert response.status_code == 422  # Unprocessable Entity for invalid JWT
        data = response.get_json()
        
        assert 'msg' in data  # Flask-JWT-Extended error format

    @patch('flask_jwt_extended.get_current_user')
    @patch('flask_jwt_extended.create_access_token')
    def test_jwt_token_refresh(self, mock_create_token, mock_get_user, client, real_company_data):
        """Test JWT token refresh functionality.
        
        Requirements: 2.2 - JWT token refresh
        """
        company = list(real_company_data.values())[0]
        test_email = f'test@{company["name"].lower().replace(" ", "-")}.test.com'
        
        # Mock current user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = test_email
        mock_user.is_active = True
        mock_get_user.return_value = mock_user
        
        # Mock new access token
        mock_create_token.return_value = 'new_access_token'
        
        # Test token refresh with mock refresh token
        headers = {
            'Authorization': 'Bearer mock_refresh_token',
            'Content-Type': 'application/json'
        }
        
        response = client.post('/api/v1/auth/refresh', headers=headers)
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        assert 'data' in data
        assert 'access_token' in data['data']
        assert data['data']['token_type'] == 'Bearer'
        assert data['data']['access_token'] == 'new_access_token'

    def test_logout_endpoint(self, client, auth_headers):
        """Test logout endpoint functionality.
        
        Requirements: 2.1 - Authentication endpoints
        """
        with patch('app.models.audit_log.AuditLog.log_logout'):
            response = client.post('/api/v1/auth/logout', headers=auth_headers)
            
            assert response.status_code == 200
            data = response.get_json()
            
            assert data['success'] is True
            assert 'Logged out successfully' in data['message']


class TestOAuthEndpoints:
    """OAuth callback handling tests."""
    
    @pytest.fixture
    def mock_google_oauth_response(self):
        """Mock Google OAuth response data."""
        return {
            'access_token': 'mock_google_access_token',
            'refresh_token': 'mock_google_refresh_token',
            'expires_in': 3600,
            'token_type': 'Bearer',
            'scope': 'openid email profile https://www.googleapis.com/auth/calendar'
        }
    
    @pytest.fixture
    def mock_google_user_info(self):
        """Mock Google user info response."""
        return {
            'id': '123456789',
            'email': 'test.user@gmail.com',
            'verified_email': True,
            'name': 'Test User',
            'given_name': 'Test',
            'family_name': 'User',
            'picture': 'https://example.com/avatar.jpg'
        }

    @patch('app.services.google_oauth_service.GoogleOAuthService.exchange_code_for_tokens')
    @patch('app.services.google_oauth_service.GoogleOAuthService.get_user_info')
    def test_oauth_google_callback_success(self, mock_get_user_info, mock_exchange_tokens, 
                                         client, app, mock_google_oauth_response, mock_google_user_info):
        """Test successful Google OAuth callback.
        
        Requirements: 2.2 - OAuth callback handling
        """
        # Mock OAuth service responses
        mock_exchange_tokens.return_value = mock_google_oauth_response
        mock_get_user_info.return_value = mock_google_user_info
        
        # Test OAuth callback
        callback_params = {
            'code': 'mock_authorization_code',
            'state': 'mock_state_parameter'
        }
        
        response = client.get('/api/v1/auth/oauth/google/callback', query_string=callback_params)
        
        # OAuth callback typically redirects, so check for redirect status
        assert response.status_code in [200, 302]  # Success or redirect
        
        # Verify OAuth service was called
        mock_exchange_tokens.assert_called_once_with('mock_authorization_code')
        mock_get_user_info.assert_called_once_with(mock_google_oauth_response['access_token'])

    @patch('app.services.google_oauth_service.GoogleOAuthService.exchange_code_for_tokens')
    def test_oauth_google_callback_invalid_code(self, mock_exchange_tokens, client):
        """Test Google OAuth callback with invalid authorization code.
        
        Requirements: 2.2 - OAuth callback handling
        """
        # Mock OAuth service to raise exception
        mock_exchange_tokens.side_effect = Exception("Invalid authorization code")
        
        callback_params = {
            'code': 'invalid_authorization_code',
            'state': 'mock_state_parameter'
        }
        
        response = client.get('/api/v1/auth/oauth/google/callback', query_string=callback_params)
        
        # Should handle error gracefully
        assert response.status_code in [400, 401, 500]  # Error status codes

    def test_oauth_google_callback_missing_code(self, client):
        """Test Google OAuth callback without authorization code.
        
        Requirements: 2.2 - OAuth callback handling
        """
        # Test callback without required code parameter
        response = client.get('/api/v1/auth/oauth/google/callback')
        
        assert response.status_code == 400  # Bad Request
        data = response.get_json()
        
        if data:  # If JSON response
            assert data['success'] is False

    def test_oauth_google_connect_authenticated_user(self, client, app, auth_headers):
        """Test Google OAuth connect for authenticated user.
        
        Requirements: 2.2 - OAuth integration
        """
        with app.app_context():
            # Test OAuth connect initiation
            response = client.post(
                '/api/v1/auth/oauth/google/connect',
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            
            assert data['success'] is True
            assert 'data' in data
            assert 'authorization_url' in data['data']
            
            # Verify authorization URL contains required parameters
            auth_url = data['data']['authorization_url']
            assert 'https://accounts.google.com/o/oauth2/auth' in auth_url
            assert 'client_id' in auth_url
            assert 'redirect_uri' in auth_url
            assert 'scope' in auth_url

    def test_oauth_google_status(self, client, app, auth_headers):
        """Test Google OAuth connection status.
        
        Requirements: 2.2 - OAuth integration
        """
        with app.app_context():
            response = client.get(
                '/api/v1/auth/oauth/google/status',
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            
            assert data['success'] is True
            assert 'data' in data
            assert 'connected' in data['data']
            assert isinstance(data['data']['connected'], bool)

    def test_oauth_google_disconnect(self, client, app, auth_headers):
        """Test Google OAuth disconnect.
        
        Requirements: 2.2 - OAuth integration
        """
        with app.app_context():
            response = client.post(
                '/api/v1/auth/oauth/google/disconnect',
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            
            assert data['success'] is True


class TestAuthenticationErrorScenarios:
    """Test authentication error scenarios and edge cases."""
    
    @patch('app.models.user.User.query')
    def test_registration_with_duplicate_email(self, mock_query, client, real_company_data):
        """Test registration with already existing email.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        
        # Mock existing user
        mock_existing_user = MagicMock()
        mock_query.filter_by.return_value.first.return_value = mock_existing_user
        
        registration_data = {
            'email': 'duplicate@test.com',
            'password': 'SecurePassword123!',
            'organization_name': company['name'],
            'first_name': 'First',
            'last_name': 'User'
        }
        
        response = client.post(
            '/api/v1/auth/register',
            json=registration_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 409  # Conflict
        data = response.get_json()
        assert data['success'] is False
        assert 'already exists' in data['error']['message']

    def test_registration_with_invalid_email(self, client, real_company_data):
        """Test registration with invalid email format.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        
        registration_data = {
            'email': 'invalid-email-format',
            'password': 'SecurePassword123!',
            'organization_name': company['name'],
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        response = client.post(
            '/api/v1/auth/register',
            json=registration_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400  # Bad Request
        data = response.get_json()
        assert data['success'] is False
        assert 'email' in data['error']['details']

    def test_registration_with_weak_password(self, client, real_company_data):
        """Test registration with weak password.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        
        registration_data = {
            'email': 'test@example.com',
            'password': '123',  # Too short
            'organization_name': company['name'],
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        response = client.post(
            '/api/v1/auth/register',
            json=registration_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400  # Bad Request
        data = response.get_json()
        assert data['success'] is False
        assert 'password' in data['error']['details']

    @patch('app.models.user.User.authenticate')
    def test_login_with_inactive_user(self, mock_authenticate, client, real_company_data):
        """Test login with inactive user account.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        test_email = f'test@{company["name"].lower().replace(" ", "-")}.test.com'
        
        # Mock inactive user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = test_email
        mock_user.is_active = False  # Inactive user
        mock_authenticate.return_value = mock_user
        
        login_data = {
            'email': test_email,
            'password': 'SecurePassword123!'
        }
        
        response = client.post(
            '/api/v1/auth/login',
            json=login_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
        assert 'disabled' in data['error']['message']

    def test_protected_endpoint_without_token(self, client):
        """Test accessing protected endpoint without authentication token.
        
        Requirements: 2.2 - JWT token validation
        """
        response = client.get('/api/v1/auth/me')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'msg' in data  # Flask-JWT-Extended error format

    def test_token_refresh_with_access_token(self, client, auth_headers):
        """Test token refresh using access token instead of refresh token.
        
        Requirements: 2.2 - JWT token refresh
        """
        # Try to refresh using access token (should fail)
        response = client.post('/api/v1/auth/refresh', headers=auth_headers)
        
        assert response.status_code == 422  # Unprocessable Entity
        data = response.get_json()
        assert 'msg' in data  # Flask-JWT-Extended error format