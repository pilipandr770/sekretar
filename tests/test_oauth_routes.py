"""Tests for OAuth authentication routes."""
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from flask import session

from app.models.user import User
from app.models.tenant import Tenant
from app.services.google_oauth import GoogleOAuthService
from app.utils.exceptions import OAuthError


class TestOAuthRoutes:
    """Test OAuth authentication routes."""
    
    @pytest.fixture
    def test_user(self, app, tenant):
        """Create test test_user."""
        with app.app_context():
            from app import db
            user = test_user.create(
                email="test@example.com",
                password="password123",
                tenant_id=tenant.id,
                role="owner"
            )
            db.session.commit()
            return user
    
    @pytest.fixture
    def auth_headers(self, test_user):
        """Create authentication headers."""
        from flask_jwt_extended import create_access_token
        token = create_access_token(identity=test_user)
        return {'Authorization': f'Bearer {token}'}
    
    def test_oauth_google_connect_not_authenticated(self, client):
        """Test OAuth connect without authentication."""
        response = client.post('/auth/oauth/google/connect')
        assert response.status_code == 401
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_connect_not_configured(self, mock_service_class, client, auth_headers):
        """Test OAuth connect when not configured."""
        mock_service = Mock()
        mock_service.is_configured.return_value = False
        mock_service_class.return_value = mock_service
        
        response = client.post('/auth/oauth/google/connect', headers=auth_headers)
        
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data['error']['code'] == 'CONFIGURATION_ERROR'
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_connect_success(self, mock_service_class, client, auth_headers):
        """Test successful OAuth connect."""
        mock_service = Mock()
        mock_service.is_configured.return_value = True
        mock_service.get_authorization_url.return_value = 'https://accounts.google.com/oauth/authorize?client_id=test'
        mock_service_class.return_value = mock_service
        
        response = client.post('/auth/oauth/google/connect', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'authorization_url' in data['data']
        assert data['data']['provider'] == 'google'
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_connect_oauth_error(self, mock_service_class, client, auth_headers):
        """Test OAuth connect with OAuth error."""
        mock_service = Mock()
        mock_service.is_configured.return_value = True
        mock_service.get_authorization_url.side_effect = OAuthError("OAuth failed")
        mock_service_class.return_value = mock_service
        
        response = client.post('/auth/oauth/google/connect', headers=auth_headers)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'OAUTH_ERROR'
    
    def test_oauth_google_callback_no_code(self, client):
        """Test OAuth callback without authorization code."""
        response = client.get('/auth/oauth/google/callback')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'OAUTH_ERROR'
        assert 'Authorization code not provided' in data['error']['message']
    
    def test_oauth_google_callback_no_state(self, client):
        """Test OAuth callback without state parameter."""
        response = client.get('/auth/oauth/google/callback?code=auth_code')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'OAUTH_ERROR'
        assert 'State parameter not provided' in data['error']['message']
    
    def test_oauth_google_callback_error_param(self, client):
        """Test OAuth callback with error parameter."""
        response = client.get('/auth/oauth/google/callback?error=access_denied&state=test_state')
        
        assert response.status_code == 302  # Redirect
        assert 'oauth_error=access_denied' in response.location
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_callback_success(self, mock_service_class, client, test_user):
        """Test successful OAuth callback."""
        mock_service = Mock()
        mock_service.handle_callback.return_value = {
            'user': user,
            'user_info': {'email': 'test@example.com', 'name': 'Test User'},
            'token_data': {'token': 'access_token'}
        }
        mock_service_class.return_value = mock_service
        
        response = client.get('/auth/oauth/google/callback?code=auth_code&state=test_state')
        
        assert response.status_code == 302  # Redirect
        assert 'oauth_success=true' in response.location
        assert 'provider=google' in response.location
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_callback_oauth_error(self, mock_service_class, client):
        """Test OAuth callback with OAuth error."""
        mock_service = Mock()
        mock_service.handle_callback.side_effect = OAuthError("Invalid state")
        mock_service_class.return_value = mock_service
        
        response = client.get('/auth/oauth/google/callback?code=auth_code&state=test_state')
        
        assert response.status_code == 302  # Redirect
        assert 'oauth_error=Invalid state' in response.location
    
    def test_oauth_google_status_not_authenticated(self, client):
        """Test OAuth status without authentication."""
        response = client.get('/auth/oauth/google/status')
        assert response.status_code == 401
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_status_not_configured(self, mock_service_class, client, auth_headers):
        """Test OAuth status when not configured."""
        mock_service = Mock()
        mock_service.is_configured.return_value = False
        mock_service_class.return_value = mock_service
        
        response = client.get('/auth/oauth/google/status', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['connected'] is False
        assert data['data']['configured'] is False
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_status_not_connected(self, mock_service_class, client, auth_headers, test_user):
        """Test OAuth status when not connected."""
        mock_service = Mock()
        mock_service.is_configured.return_value = True
        mock_service_class.return_value = mock_service
        
        response = client.get('/auth/oauth/google/status', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['connected'] is False
        assert data['data']['configured'] is True
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_status_connected(self, mock_service_class, client, auth_headers, test_user):
        """Test OAuth status when connected."""
        # Set up user as connected
        test_user.google_calendar_connected = True
        test_user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=1)
        test_user.save()
        
        mock_service = Mock()
        mock_service.is_configured.return_value = True
        mock_service.test_connection.return_value = {
            'connected': True,
            'calendar_count': 2
        }
        mock_service_class.return_value = mock_service
        
        response = client.get('/auth/oauth/google/status', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['connected'] is True
        assert data['data']['configured'] is True
        assert data['data']['is_expired'] is False
        assert data['data']['calendar_count'] == 2
    
    def test_oauth_google_disconnect_not_authenticated(self, client):
        """Test OAuth disconnect without authentication."""
        response = client.post('/auth/oauth/google/disconnect')
        assert response.status_code == 401
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_disconnect_not_connected(self, mock_service_class, client, auth_headers, test_user):
        """Test OAuth disconnect when not connected."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        response = client.post('/auth/oauth/google/disconnect', headers=auth_headers)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'
        assert 'not connected' in data['error']['message']
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_disconnect_success(self, mock_service_class, client, auth_headers, test_user):
        """Test successful OAuth disconnect."""
        # Set up user as connected
        test_user.google_calendar_connected = True
        test_user.save()
        
        mock_service = Mock()
        mock_service.disconnect_calendar.return_value = True
        mock_service_class.return_value = mock_service
        
        response = client.post('/auth/oauth/google/disconnect', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'disconnected successfully' in data['message']
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_disconnect_failure(self, mock_service_class, client, auth_headers, test_user):
        """Test OAuth disconnect failure."""
        # Set up user as connected
        test_user.google_calendar_connected = True
        test_user.save()
        
        mock_service = Mock()
        mock_service.disconnect_calendar.return_value = False
        mock_service_class.return_value = mock_service
        
        response = client.post('/auth/oauth/google/disconnect', headers=auth_headers)
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['error']['code'] == 'OAUTH_ERROR'
    
    def test_oauth_google_refresh_not_authenticated(self, client):
        """Test OAuth refresh without authentication."""
        response = client.post('/auth/oauth/google/refresh')
        assert response.status_code == 401
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_refresh_not_connected(self, mock_service_class, client, auth_headers, test_user):
        """Test OAuth refresh when not connected."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        response = client.post('/auth/oauth/google/refresh', headers=auth_headers)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'
        assert 'not connected' in data['error']['message']
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_refresh_success(self, mock_service_class, client, auth_headers, test_user):
        """Test successful OAuth refresh."""
        # Set up user as connected
        test_user.google_calendar_connected = True
        test_user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=1)
        test_user.save()
        
        mock_service = Mock()
        mock_service.refresh_token.return_value = True
        mock_service_class.return_value = mock_service
        
        response = client.post('/auth/oauth/google/refresh', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'refreshed successfully' in data['message']
        assert 'expires_at' in data['data']
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_google_refresh_failure(self, mock_service_class, client, auth_headers, test_user):
        """Test OAuth refresh failure."""
        # Set up user as connected
        test_user.google_calendar_connected = True
        test_user.save()
        
        mock_service = Mock()
        mock_service.refresh_token.return_value = False
        mock_service_class.return_value = mock_service
        
        response = client.post('/auth/oauth/google/refresh', headers=auth_headers)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'OAUTH_ERROR'
