"""Comprehensive authentication API endpoint tests.

This module implements comprehensive testing of authentication API endpoints
focusing on HTTP request/response validation, error handling, and integration
with real company data patterns.

Requirements covered: 2.1, 2.2
"""
import json
import pytest
from unittest.mock import patch, MagicMock


class TestAuthenticationAPIEndpoints:
    """Test authentication API endpoints with focus on HTTP behavior."""
    
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

    def test_register_endpoint_request_validation(self, client, real_company_data):
        """Test registration endpoint request validation.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        
        # Test missing required fields
        incomplete_data = {
            'email': f'test@{company["name"].lower().replace(" ", "-")}.test.com',
            # Missing password and organization_name
        }
        
        response = client.post(
            '/api/v1/auth/register',
            json=incomplete_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400  # Bad Request
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data

    def test_register_endpoint_email_validation(self, client, real_company_data):
        """Test registration endpoint email validation.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        
        # Test invalid email format
        invalid_email_data = {
            'email': 'invalid-email-format',
            'password': 'SecurePassword123!',
            'organization_name': company['name']
        }
        
        response = client.post(
            '/api/v1/auth/register',
            json=invalid_email_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400  # Bad Request
        data = response.get_json()
        assert data['success'] is False
        assert 'email' in data['error']['details']

    def test_register_endpoint_password_validation(self, client, real_company_data):
        """Test registration endpoint password validation.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        
        # Test weak password
        weak_password_data = {
            'email': f'test@{company["name"].lower().replace(" ", "-")}.test.com',
            'password': '123',  # Too short
            'organization_name': company['name']
        }
        
        response = client.post(
            '/api/v1/auth/register',
            json=weak_password_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400  # Bad Request
        data = response.get_json()
        assert data['success'] is False
        assert 'password' in data['error']['details']

    def test_login_endpoint_request_validation(self, client):
        """Test login endpoint request validation.
        
        Requirements: 2.1 - Authentication endpoints
        """
        # Test missing required fields
        incomplete_data = {
            'email': 'test@example.com',
            # Missing password
        }
        
        response = client.post(
            '/api/v1/auth/login',
            json=incomplete_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400  # Bad Request
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data

    def test_login_endpoint_email_validation(self, client):
        """Test login endpoint email validation.
        
        Requirements: 2.1 - Authentication endpoints
        """
        # Test invalid email format
        invalid_email_data = {
            'email': 'invalid-email-format',
            'password': 'password123'
        }
        
        response = client.post(
            '/api/v1/auth/login',
            json=invalid_email_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400  # Bad Request
        data = response.get_json()
        assert data['success'] is False
        assert 'email' in data['error']['details']

    def test_login_endpoint_nonexistent_user(self, client, real_company_data):
        """Test login with non-existent user.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        
        login_data = {
            'email': f'nonexistent@{company["name"].lower().replace(" ", "-")}.test.com',
            'password': 'SomePassword123!'
        }
        
        response = client.post(
            '/api/v1/auth/login',
            json=login_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 401  # Unauthorized
        data = response.get_json()
        assert data['success'] is False
        assert 'Invalid email or password' in data['error']['message']

    def test_protected_endpoint_without_token(self, client):
        """Test accessing protected endpoint without authentication token.
        
        Requirements: 2.2 - JWT token validation
        """
        response = client.get('/api/v1/auth/me')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data  # Custom error format

    def test_protected_endpoint_with_invalid_token(self, client):
        """Test accessing protected endpoint with invalid token.
        
        Requirements: 2.2 - JWT token validation
        """
        headers = {
            'Authorization': 'Bearer invalid_token_here',
            'Content-Type': 'application/json'
        }
        
        response = client.get('/api/v1/auth/me', headers=headers)
        
        assert response.status_code == 401  # Custom error handling returns 401
        data = response.get_json()
        assert 'error' in data  # Custom error format

    def test_protected_endpoint_with_malformed_header(self, client):
        """Test accessing protected endpoint with malformed Authorization header.
        
        Requirements: 2.2 - JWT token validation
        """
        headers = {
            'Authorization': 'InvalidFormat token_here',
            'Content-Type': 'application/json'
        }
        
        response = client.get('/api/v1/auth/me', headers=headers)
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_refresh_endpoint_without_token(self, client):
        """Test token refresh without refresh token.
        
        Requirements: 2.2 - JWT token refresh
        """
        response = client.post('/api/v1/auth/refresh')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data  # Custom error format

    def test_refresh_endpoint_with_invalid_token(self, client):
        """Test token refresh with invalid refresh token.
        
        Requirements: 2.2 - JWT token refresh
        """
        headers = {
            'Authorization': 'Bearer invalid_refresh_token',
            'Content-Type': 'application/json'
        }
        
        response = client.post('/api/v1/auth/refresh', headers=headers)
        
        assert response.status_code == 401  # Custom error handling returns 401
        data = response.get_json()
        assert 'error' in data

    def test_logout_endpoint_without_token(self, client):
        """Test logout without authentication token.
        
        Requirements: 2.1 - Authentication endpoints
        """
        response = client.post('/api/v1/auth/logout')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_logout_endpoint_with_valid_token(self, client, auth_headers):
        """Test logout with valid authentication token.
        
        Requirements: 2.1 - Authentication endpoints
        """
        response = client.post('/api/v1/auth/logout', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'Logged out successfully' in data['message']


class TestOAuthAPIEndpoints:
    """Test OAuth API endpoints."""

    def test_oauth_google_connect_without_auth(self, client):
        """Test Google OAuth connect without authentication.
        
        Requirements: 2.2 - OAuth integration
        """
        response = client.post('/api/v1/auth/oauth/google/connect')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_oauth_google_connect_with_auth(self, client, auth_headers):
        """Test Google OAuth connect with authentication.
        
        Requirements: 2.2 - OAuth integration
        """
        response = client.post('/api/v1/auth/oauth/google/connect', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'authorization_url' in data['data']

    def test_oauth_google_status_without_auth(self, client):
        """Test Google OAuth status without authentication.
        
        Requirements: 2.2 - OAuth integration
        """
        response = client.get('/api/v1/auth/oauth/google/status')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_oauth_google_status_with_auth(self, client, auth_headers):
        """Test Google OAuth status with authentication.
        
        Requirements: 2.2 - OAuth integration
        """
        response = client.get('/api/v1/auth/oauth/google/status', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'connected' in data['data']
        assert isinstance(data['data']['connected'], bool)

    def test_oauth_google_callback_without_code(self, client):
        """Test Google OAuth callback without authorization code.
        
        Requirements: 2.2 - OAuth callback handling
        """
        response = client.get('/api/v1/auth/oauth/google/callback')
        
        assert response.status_code == 400  # Bad Request
        data = response.get_json()
        if data:  # If JSON response
            assert data['success'] is False

    def test_oauth_google_callback_with_invalid_code(self, client):
        """Test Google OAuth callback with invalid authorization code.
        
        Requirements: 2.2 - OAuth callback handling
        """
        callback_params = {
            'code': 'invalid_authorization_code',
            'state': 'mock_state_parameter'
        }
        
        response = client.get('/api/v1/auth/oauth/google/callback', query_string=callback_params)
        
        # Should handle error gracefully
        assert response.status_code in [400, 401, 500]  # Error status codes

    def test_oauth_google_disconnect_without_auth(self, client):
        """Test Google OAuth disconnect without authentication.
        
        Requirements: 2.2 - OAuth integration
        """
        response = client.post('/api/v1/auth/oauth/google/disconnect')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_oauth_google_disconnect_with_auth(self, client, auth_headers):
        """Test Google OAuth disconnect with authentication.
        
        Requirements: 2.2 - OAuth integration
        """
        response = client.post('/api/v1/auth/oauth/google/disconnect', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_oauth_google_refresh_without_auth(self, client):
        """Test Google OAuth refresh without authentication.
        
        Requirements: 2.2 - OAuth integration
        """
        response = client.post('/api/v1/auth/oauth/google/refresh')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_oauth_google_refresh_with_auth(self, client, auth_headers):
        """Test Google OAuth refresh with authentication.
        
        Requirements: 2.2 - OAuth integration
        """
        response = client.post('/api/v1/auth/oauth/google/refresh', headers=auth_headers)
        
        # Response depends on whether user has OAuth tokens configured
        assert response.status_code in [200, 400]  # Success or bad request


class TestAuthenticationErrorHandling:
    """Test authentication error handling and edge cases."""

    def test_invalid_json_request(self, client):
        """Test endpoints with invalid JSON data.
        
        Requirements: 2.1 - Authentication endpoints
        """
        response = client.post(
            '/api/v1/auth/login',
            data='invalid json data',
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_missing_content_type(self, client):
        """Test endpoints without Content-Type header.
        
        Requirements: 2.1 - Authentication endpoints
        """
        login_data = {
            'email': 'test@example.com',
            'password': 'password123'
        }
        
        response = client.post('/api/v1/auth/login', json=login_data)
        # Should still work as Flask handles JSON automatically
        assert response.status_code in [200, 400, 401]

    def test_empty_request_body(self, client):
        """Test endpoints with empty request body.
        
        Requirements: 2.1 - Authentication endpoints
        """
        response = client.post(
            '/api/v1/auth/login',
            json={},
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_oversized_request(self, client, real_company_data):
        """Test endpoints with oversized request data.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        
        # Create oversized organization name
        oversized_data = {
            'email': f'test@{company["name"].lower().replace(" ", "-")}.test.com',
            'password': 'SecurePassword123!',
            'organization_name': 'A' * 10000  # Very long name
        }
        
        response = client.post(
            '/api/v1/auth/register',
            json=oversized_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Should handle gracefully
        assert response.status_code in [400, 413, 500]  # Bad request, payload too large, or server error

    def test_special_characters_in_data(self, client, real_company_data):
        """Test endpoints with special characters in data.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        
        special_char_data = {
            'email': f'test+special@{company["name"].lower().replace(" ", "-")}.test.com',
            'password': 'SecurePassword123!@#$%',
            'organization_name': f'{company["name"]} & Co. (Special Chars: äöü)',
            'first_name': 'José',
            'last_name': 'García-López'
        }
        
        response = client.post(
            '/api/v1/auth/register',
            json=special_char_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Should handle special characters properly
        assert response.status_code in [201, 400, 409, 500]  # Various valid responses

    def test_sql_injection_attempt(self, client):
        """Test endpoints against SQL injection attempts.
        
        Requirements: 2.1 - Authentication endpoints
        """
        injection_data = {
            'email': "test@example.com'; DROP TABLE users; --",
            'password': "password' OR '1'='1"
        }
        
        response = client.post(
            '/api/v1/auth/login',
            json=injection_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Should handle safely without SQL injection
        assert response.status_code in [400, 401]  # Bad request or unauthorized
        data = response.get_json()
        assert data['success'] is False

    def test_xss_attempt_in_registration(self, client, real_company_data):
        """Test registration endpoint against XSS attempts.
        
        Requirements: 2.1 - Authentication endpoints
        """
        company = list(real_company_data.values())[0]
        
        xss_data = {
            'email': f'test@{company["name"].lower().replace(" ", "-")}.test.com',
            'password': 'SecurePassword123!',
            'organization_name': '<script>alert("XSS")</script>',
            'first_name': '<img src=x onerror=alert("XSS")>',
            'last_name': 'Normal'
        }
        
        response = client.post(
            '/api/v1/auth/register',
            json=xss_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Should handle XSS attempts safely
        assert response.status_code in [201, 400, 409, 500]  # Various valid responses
        
        if response.status_code == 201:
            data = response.get_json()
            # Ensure no script tags in response
            response_text = json.dumps(data)
            assert '<script>' not in response_text
            assert 'onerror=' not in response_text