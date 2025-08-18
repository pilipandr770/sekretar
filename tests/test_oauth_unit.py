"""Unit tests for Google OAuth integration without Flask app context."""
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.models.user import User
from app.models.tenant import Tenant


def test_user_oauth_token_methods_unit():
    """Test OAuth token methods in User model without database."""
    # Create a mock user object
    user = User()
    user.id = 1
    user.tenant_id = 1
    user.email = "test@example.com"
    
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
    
    # Mock the save method
    user.save = Mock(return_value=user)
    
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


def test_user_oauth_token_invalid_json():
    """Test getting OAuth tokens with invalid JSON."""
    user = User()
    user.google_oauth_token = "invalid json"
    
    tokens = user.get_google_oauth_tokens()
    assert tokens is None


def test_user_oauth_token_none():
    """Test getting OAuth tokens when none are stored."""
    user = User()
    user.google_oauth_token = None
    
    tokens = user.get_google_oauth_tokens()
    assert tokens is None


def test_user_oauth_expiry_no_date():
    """Test OAuth expiry check with no expiry date."""
    user = User()
    user.google_oauth_expires_at = None
    
    assert user.is_google_oauth_expired() is True


@patch('app.services.google_oauth.current_app')
def test_oauth_service_configuration(mock_current_app):
    """Test OAuth service configuration."""
    from app.services.google_oauth import GoogleOAuthService
    
    # Test without configuration
    mock_current_app.config.get.side_effect = lambda key: None
    
    service = GoogleOAuthService()
    assert service.is_configured() is False
    
    # Test with configuration
    config_values = {
        'GOOGLE_CLIENT_ID': 'test_client_id',
        'GOOGLE_CLIENT_SECRET': 'test_client_secret',
        'GOOGLE_REDIRECT_URI': 'http://localhost:5000/auth/oauth/google/callback'
    }
    mock_current_app.config.get.side_effect = lambda key: config_values.get(key)
    
    service = GoogleOAuthService()
    assert service.is_configured() is True


@patch('app.services.google_oauth.current_app')
def test_oauth_service_authorization_url_not_configured(mock_current_app):
    """Test authorization URL generation when not configured."""
    from app.services.google_oauth import GoogleOAuthService
    from app.utils.exceptions import OAuthError
    
    mock_current_app.config.get.side_effect = lambda key: None
    
    service = GoogleOAuthService()
    
    with pytest.raises(OAuthError, match="Google OAuth not configured"):
        service.get_authorization_url(1)


def test_oauth_service_refresh_token_no_refresh_token():
    """Test token refresh without refresh token."""
    from app.services.google_oauth import GoogleOAuthService
    
    user = User()
    user.google_oauth_refresh_token = None
    
    service = GoogleOAuthService()
    result = service.refresh_token(user)
    assert result is False


def test_oauth_service_get_valid_credentials_not_connected():
    """Test getting credentials when not connected."""
    from app.services.google_oauth import GoogleOAuthService
    
    user = User()
    user.google_calendar_connected = False
    
    service = GoogleOAuthService()
    credentials = service.get_valid_credentials(user)
    assert credentials is None


def test_oauth_service_get_valid_credentials_no_tokens():
    """Test getting credentials with no stored tokens."""
    from app.services.google_oauth import GoogleOAuthService
    
    user = User()
    user.google_calendar_connected = True
    user.google_oauth_token = None
    
    service = GoogleOAuthService()
    credentials = service.get_valid_credentials(user)
    assert credentials is None