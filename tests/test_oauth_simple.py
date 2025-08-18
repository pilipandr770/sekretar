"""Simple tests for Google OAuth integration."""
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.models.user import User
from app.models.tenant import Tenant
from app.services.google_oauth import GoogleOAuthService
from app.utils.exceptions import OAuthError


def test_user_oauth_token_methods(app, tenant, user):
    """Test OAuth token methods in User model."""
    with app.app_context():
        # Test setting OAuth tokens
        token_data = {
            'token': 'access_token',
            'refresh_token': 'refresh_token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'scopes': ['https://www.googleapis.com/auth/calendar'],
            'expires_in': 3600
        }
        
        user.set_google_oauth_tokens(token_data)
        
        assert user.google_calendar_connected is True
        assert user.google_oauth_refresh_token == 'refresh_token'
        assert user.google_oauth_expires_at is not None
        
        # Test getting OAuth tokens
        stored_tokens = user.get_google_oauth_tokens()
        assert stored_tokens['token'] == 'access_token'
        assert stored_tokens['refresh_token'] == 'refresh_token'
        
        # Test expiry check
        user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=1)
        assert user.is_google_oauth_expired() is False
        
        user.google_oauth_expires_at = datetime.utcnow() - timedelta(hours=1)
        assert user.is_google_oauth_expired() is True
        
        # Test clearing tokens
        user.clear_google_oauth_tokens()
        assert user.google_calendar_connected is False
        assert user.google_oauth_token is None
        assert user.google_oauth_refresh_token is None
        assert user.google_oauth_expires_at is None


def test_oauth_service_configuration(app):
    """Test OAuth service configuration."""
    with app.app_context():
        # Test without configuration
        app.config['GOOGLE_CLIENT_ID'] = None
        app.config['GOOGLE_CLIENT_SECRET'] = None
        app.config['GOOGLE_REDIRECT_URI'] = None
        
        service = GoogleOAuthService()
        assert service.is_configured() is False
        
        # Test with configuration
        app.config['GOOGLE_CLIENT_ID'] = 'test_client_id'
        app.config['GOOGLE_CLIENT_SECRET'] = 'test_client_secret'
        app.config['GOOGLE_REDIRECT_URI'] = 'http://localhost:5000/auth/oauth/google/callback'
        
        service = GoogleOAuthService()
        assert service.is_configured() is True


def test_oauth_service_authorization_url_not_configured(app):
    """Test authorization URL generation when not configured."""
    with app.app_context():
        app.config['GOOGLE_CLIENT_ID'] = None
        service = GoogleOAuthService()
        
        with pytest.raises(OAuthError, match="Google OAuth not configured"):
            service.get_authorization_url(1)


@patch('app.services.google_oauth.Flow')
def test_oauth_service_authorization_url_success(mock_flow, app):
    """Test successful authorization URL generation."""
    with app.app_context():
        app.config['GOOGLE_CLIENT_ID'] = 'test_client_id'
        app.config['GOOGLE_CLIENT_SECRET'] = 'test_client_secret'
        app.config['GOOGLE_REDIRECT_URI'] = 'http://localhost:5000/auth/oauth/google/callback'
        
        # Mock Flow
        mock_flow_instance = Mock()
        mock_flow_instance.authorization_url.return_value = (
            'https://accounts.google.com/oauth/authorize?client_id=test',
            'state123'
        )
        mock_flow.from_client_config.return_value = mock_flow_instance
        
        service = GoogleOAuthService()
        
        with app.test_request_context():
            from flask import session
            url = service.get_authorization_url(1, 'test_state')
            
            assert url == 'https://accounts.google.com/oauth/authorize?client_id=test'
            assert session['oauth_state'] == 'test_state'
            assert session['oauth_user_id'] == 1


def test_oauth_routes_connect_not_authenticated(client):
    """Test OAuth connect without authentication."""
    response = client.post('/auth/oauth/google/connect')
    assert response.status_code == 401


@patch('app.auth.oauth_routes.GoogleOAuthService')
def test_oauth_routes_connect_success(mock_service_class, client, user):
    """Test successful OAuth connect."""
    from flask_jwt_extended import create_access_token
    
    mock_service = Mock()
    mock_service.is_configured.return_value = True
    mock_service.get_authorization_url.return_value = 'https://accounts.google.com/oauth/authorize?client_id=test'
    mock_service_class.return_value = mock_service
    
    token = create_access_token(identity=user)
    headers = {'Authorization': f'Bearer {token}'}
    
    response = client.post('/auth/oauth/google/connect', headers=headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'authorization_url' in data['data']
    assert data['data']['provider'] == 'google'


def test_oauth_routes_status_not_authenticated(client):
    """Test OAuth status without authentication."""
    response = client.get('/auth/oauth/google/status')
    assert response.status_code == 401


@patch('app.auth.oauth_routes.GoogleOAuthService')
def test_oauth_routes_status_not_connected(mock_service_class, client, user):
    """Test OAuth status when not connected."""
    from flask_jwt_extended import create_access_token
    
    mock_service = Mock()
    mock_service.is_configured.return_value = True
    mock_service_class.return_value = mock_service
    
    token = create_access_token(identity=user)
    headers = {'Authorization': f'Bearer {token}'}
    
    response = client.get('/auth/oauth/google/status', headers=headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['data']['connected'] is False
    assert data['data']['configured'] is True