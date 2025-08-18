"""Tests for Google OAuth integration."""
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from flask import session

from app.models.user import User
from app.models.tenant import Tenant
from app.services.google_oauth import GoogleOAuthService
from app.utils.exceptions import OAuthError, ExternalAPIError


class TestGoogleOAuthService:
    """Test Google OAuth service functionality."""
    
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
    
    def test_is_configured_with_all_settings(self, oauth_service, app):
        """Test OAuth configuration check with all settings."""
        with app.app_context():
            app.config['GOOGLE_CLIENT_ID'] = 'test_client_id'
            app.config['GOOGLE_CLIENT_SECRET'] = 'test_client_secret'
            app.config['GOOGLE_REDIRECT_URI'] = 'http://localhost:5000/auth/oauth/google/callback'
            
            service = GoogleOAuthService()
            assert service.is_configured() is True
    
    def test_is_configured_missing_settings(self, oauth_service, app):
        """Test OAuth configuration check with missing settings."""
        with app.app_context():
            app.config['GOOGLE_CLIENT_ID'] = None
            app.config['GOOGLE_CLIENT_SECRET'] = 'test_client_secret'
            app.config['GOOGLE_REDIRECT_URI'] = 'http://localhost:5000/auth/oauth/google/callback'
            
            service = GoogleOAuthService()
            assert service.is_configured() is False
    
    def test_get_authorization_url_not_configured(self, oauth_service):
        """Test authorization URL generation when not configured."""
        with patch.object(oauth_service, 'is_configured', return_value=False):
            with pytest.raises(OAuthError, match="Google OAuth not configured"):
                oauth_service.get_authorization_url(1)
    
    @patch('app.services.google_oauth.Flow')
    def test_get_authorization_url_success(self, mock_flow, oauth_service, app):
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
                url = service.get_authorization_url(1, 'test_state')
                
                assert url == 'https://accounts.google.com/oauth/authorize?client_id=test'
                assert session['oauth_state'] == 'test_state'
                assert session['oauth_user_id'] == 1
                
                mock_flow_instance.authorization_url.assert_called_once_with(
                    access_type='offline',
                    include_granted_scopes='true',
                    state='test_state',
                    prompt='consent'
                )
    
    def test_handle_callback_invalid_state(self, oauth_service, app):
        """Test callback handling with invalid state."""
        with app.test_request_context():
            session['oauth_state'] = 'valid_state'
            session['oauth_user_id'] = 1
            
            with pytest.raises(OAuthError, match="Invalid state parameter"):
                oauth_service.handle_callback('auth_code', 'invalid_state')
    
    def test_handle_callback_no_user_id(self, oauth_service, app):
        """Test callback handling without user ID in session."""
        with app.test_request_context():
            session['oauth_state'] = 'test_state'
            # No oauth_user_id in session
            
            with pytest.raises(OAuthError, match="No user ID in session"):
                oauth_service.handle_callback('auth_code', 'test_state')
    
    @patch('app.services.google_oauth.Flow')
    @patch('app.services.google_oauth.build')
    def test_handle_callback_success(self, mock_build, mock_flow, oauth_service, app, test_user):
        """Test successful callback handling."""
        with app.app_context():
            app.config['GOOGLE_CLIENT_ID'] = 'test_client_id'
            app.config['GOOGLE_CLIENT_SECRET'] = 'test_client_secret'
            app.config['GOOGLE_REDIRECT_URI'] = 'http://localhost:5000/auth/oauth/google/callback'
            
            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = 'access_token'
            mock_credentials.refresh_token = 'refresh_token'
            mock_credentials.token_uri = 'https://oauth2.googleapis.com/token'
            mock_credentials.client_id = 'test_client_id'
            mock_credentials.client_secret = 'test_client_secret'
            mock_credentials.scopes = ['https://www.googleapis.com/auth/calendar']
            mock_credentials.expiry = datetime.utcnow() + timedelta(hours=1)
            
            # Mock Flow
            mock_flow_instance = Mock()
            mock_flow_instance.credentials = mock_credentials
            mock_flow.from_client_config.return_value = mock_flow_instance
            
            # Mock Google API service for user info
            mock_service = Mock()
            mock_userinfo = Mock()
            mock_userinfo.get.return_value.execute.return_value = {
                'email': 'test@example.com',
                'name': 'Test User'
            }
            mock_service.userinfo.return_value = mock_userinfo
            mock_build.return_value = mock_service
            
            service = GoogleOAuthService()
            
            with app.test_request_context():
                session['oauth_state'] = 'test_state'
                session['oauth_user_id'] = test_user.id
                
                result = service.handle_callback('auth_code', 'test_state')
                
                assert result['user'].id == test_user.id
                assert result['user_info']['email'] == 'test@example.com'
                assert result['user_info']['name'] == 'Test User'
                assert 'token_data' in result
                
                # Verify user tokens were stored
                test_user.refresh()
                assert test_user.google_calendar_connected is True
                assert test_user.google_oauth_refresh_token == 'refresh_token'
                
                # Verify session was cleared
                assert 'oauth_state' not in session
                assert 'oauth_user_id' not in session
    
    def test_refresh_token_no_refresh_token(self, oauth_service, test_user):
        """Test token refresh without refresh token."""
        result = oauth_service.refresh_token(test_user)
        assert result is False
    
    @patch('app.services.google_oauth.Credentials')
    @patch('app.services.google_oauth.Request')
    def test_refresh_token_success(self, mock_request, mock_credentials_class, oauth_service, test_user):
        """Test successful token refresh."""
        # Set up user with OAuth tokens
        token_data = {
            'token': 'old_access_token',
            'refresh_token': 'refresh_token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'scopes': ['https://www.googleapis.com/auth/calendar']
        }
        test_user.set_google_oauth_tokens(token_data)
        
        # Mock credentials
        mock_credentials = Mock()
        mock_credentials.token = 'new_access_token'
        mock_credentials.refresh_token = 'refresh_token'
        mock_credentials.token_uri = 'https://oauth2.googleapis.com/token'
        mock_credentials.client_id = 'test_client_id'
        mock_credentials.client_secret = 'test_client_secret'
        mock_credentials.scopes = ['https://www.googleapis.com/auth/calendar']
        mock_credentials.expiry = datetime.utcnow() + timedelta(hours=1)
        
        mock_credentials_class.return_value = mock_credentials
        
        result = oauth_service.refresh_token(test_user)
        
        assert result is True
        mock_credentials.refresh.assert_called_once()
        
        # Verify new tokens were stored
        test_user.refresh()
        new_token_data = test_user.get_google_oauth_tokens()
        assert new_token_data['token'] == 'new_access_token'
    
    @patch('app.services.google_oauth.Credentials')
    @patch('app.services.google_oauth.Request')
    def test_refresh_token_failure(self, mock_request, mock_credentials_class, oauth_service, test_user):
        """Test token refresh failure."""
        # Set up user with OAuth tokens
        token_data = {
            'token': 'old_access_token',
            'refresh_token': 'refresh_token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'scopes': ['https://www.googleapis.com/auth/calendar']
        }
        test_user.set_google_oauth_tokens(token_data)
        
        # Mock credentials to raise exception
        mock_credentials = Mock()
        mock_credentials.refresh.side_effect = Exception("Refresh failed")
        mock_credentials_class.return_value = mock_credentials
        
        result = oauth_service.refresh_token(test_user)
        
        assert result is False
        
        # Verify tokens were cleared
        test_user.refresh()
        assert test_user.google_calendar_connected is False
    
    def test_get_valid_credentials_not_connected(self, oauth_service, test_user):
        """Test getting credentials when not connected."""
        credentials = oauth_service.get_valid_credentials(test_user)
        assert credentials is None
    
    def test_get_valid_credentials_no_tokens(self, oauth_service, test_user):
        """Test getting credentials with no stored tokens."""
        test_user.google_calendar_connected = True
        test_user.save()
        
        credentials = oauth_service.get_valid_credentials(test_user)
        assert credentials is None
    
    @patch('app.services.google_oauth.Credentials')
    def test_get_valid_credentials_not_expired(self, mock_credentials_class, oauth_service, test_user):
        """Test getting valid credentials that are not expired."""
        # Set up user with valid OAuth tokens
        token_data = {
            'token': 'access_token',
            'refresh_token': 'refresh_token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'scopes': ['https://www.googleapis.com/auth/calendar']
        }
        test_user.set_google_oauth_tokens(token_data)
        test_user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=1)
        test_user.save()
        
        mock_credentials = Mock()
        mock_credentials_class.return_value = mock_credentials
        
        credentials = oauth_service.get_valid_credentials(test_user)
        
        assert credentials == mock_credentials
        mock_credentials_class.assert_called_once()
    
    @patch('requests.post')
    def test_disconnect_calendar_success(self, mock_post, oauth_service, test_user):
        """Test successful calendar disconnection."""
        # Set up user with OAuth tokens
        token_data = {
            'token': 'access_token',
            'refresh_token': 'refresh_token'
        }
        test_user.set_google_oauth_tokens(token_data)
        
        # Mock successful revoke response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = oauth_service.disconnect_calendar(test_user)
        
        assert result is True
        mock_post.assert_called_once_with(
            "https://oauth2.googleapis.com/revoke?token=access_token"
        )
        
        # Verify tokens were cleared
        test_user.refresh()
        assert test_user.google_calendar_connected is False
        assert test_user.google_oauth_token is None
    
    @patch('requests.post')
    def test_disconnect_calendar_revoke_failure(self, mock_post, oauth_service, test_user):
        """Test calendar disconnection with revoke failure."""
        # Set up user with OAuth tokens
        token_data = {
            'token': 'access_token',
            'refresh_token': 'refresh_token'
        }
        test_user.set_google_oauth_tokens(token_data)
        
        # Mock failed revoke response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        result = oauth_service.disconnect_calendar(test_user)
        
        # Should still return True and clear tokens
        assert result is True
        
        # Verify tokens were cleared despite revoke failure
        test_user.refresh()
        assert test_user.google_calendar_connected is False
    
    @patch('app.services.google_oauth.build')
    def test_get_calendar_service_success(self, mock_build, oauth_service, test_user):
        """Test successful calendar service creation."""
        # Set up user with valid OAuth tokens
        token_data = {
            'token': 'access_token',
            'refresh_token': 'refresh_token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'scopes': ['https://www.googleapis.com/auth/calendar']
        }
        test_user.set_google_oauth_tokens(token_data)
        test_user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=1)
        test_user.save()
        
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        with patch.object(oauth_service, 'get_valid_credentials') as mock_get_creds:
            mock_credentials = Mock()
            mock_get_creds.return_value = mock_credentials
            
            service = oauth_service.get_calendar_service(test_user)
            
            assert service == mock_service
            mock_build.assert_called_once_with('calendar', 'v3', credentials=mock_credentials)
    
    def test_get_calendar_service_no_credentials(self, oauth_service, test_user):
        """Test calendar service creation without credentials."""
        with pytest.raises(OAuthError, match="No valid Google credentials"):
            oauth_service.get_calendar_service(test_user)
    
    @patch('app.services.google_oauth.build')
    def test_get_calendar_service_build_failure(self, mock_build, oauth_service, test_user):
        """Test calendar service creation with build failure."""
        # Set up user with valid OAuth tokens
        token_data = {
            'token': 'access_token',
            'refresh_token': 'refresh_token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'scopes': ['https://www.googleapis.com/auth/calendar']
        }
        test_user.set_google_oauth_tokens(token_data)
        test_user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=1)
        test_user.save()
        
        mock_build.side_effect = Exception("Build failed")
        
        with patch.object(oauth_service, 'get_valid_credentials') as mock_get_creds:
            mock_credentials = Mock()
            mock_get_creds.return_value = mock_credentials
            
            with pytest.raises(ExternalAPIError, match="Failed to connect to Google Calendar"):
                oauth_service.get_calendar_service(test_user)
    
    def test_test_connection_success(self, oauth_service, test_user):
        """Test successful connection test."""
        mock_service = Mock()
        mock_calendar_list = Mock()
        mock_calendar_list.list.return_value.execute.return_value = {
            'items': [
                {'id': 'primary', 'primary': True, 'summary': 'Primary Calendar'},
                {'id': 'secondary', 'summary': 'Secondary Calendar'}
            ]
        }
        mock_service.calendarList.return_value = mock_calendar_list
        
        with patch.object(oauth_service, 'get_calendar_service', return_value=mock_service):
            result = oauth_service.test_connection(test_user)
            
            assert result['connected'] is True
            assert result['calendar_count'] == 2
            assert result['primary_calendar']['id'] == 'primary'
    
    def test_test_connection_failure(self, oauth_service, test_user):
        """Test connection test failure."""
        with patch.object(oauth_service, 'get_calendar_service', side_effect=Exception("Connection failed")):
            result = oauth_service.test_connection(test_user)
            
            assert result['connected'] is False
            assert 'error' in result


class TestUserOAuthMethods:
    """Test OAuth-related methods in User model."""
    
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
    
    def test_set_google_oauth_tokens(self, test_user):
        """Test setting Google OAuth tokens."""
        token_data = {
            'token': 'access_token',
            'refresh_token': 'refresh_token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'scopes': ['https://www.googleapis.com/auth/calendar'],
            'expires_in': 3600
        }
        
        test_user.set_google_oauth_tokens(token_data)
        
        assert test_user.google_calendar_connected is True
        assert test_user.google_oauth_refresh_token == 'refresh_token'
        assert test_user.google_oauth_expires_at is not None
        
        stored_tokens = test_user.get_google_oauth_tokens()
        assert stored_tokens['token'] == 'access_token'
        assert stored_tokens['refresh_token'] == 'refresh_token'
    
    def test_get_google_oauth_tokens_none(self, test_user):
        """Test getting OAuth tokens when none are stored."""
        tokens = test_user.get_google_oauth_tokens()
        assert tokens is None
    
    def test_get_google_oauth_tokens_invalid_json(self, test_user):
        """Test getting OAuth tokens with invalid JSON."""
        test_user.google_oauth_token = "invalid json"
        test_user.save()
        
        tokens = test_user.get_google_oauth_tokens()
        assert tokens is None
    
    def test_is_google_oauth_expired_no_expiry(self, test_user):
        """Test OAuth expiry check with no expiry date."""
        assert test_user.is_google_oauth_expired() is True
    
    def test_is_google_oauth_expired_not_expired(self, test_user):
        """Test OAuth expiry check with future expiry."""
        test_user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=1)
        test_user.save()
        
        assert test_user.is_google_oauth_expired() is False
    
    def test_is_google_oauth_expired_expired(self, test_user):
        """Test OAuth expiry check with past expiry."""
        test_user.google_oauth_expires_at = datetime.utcnow() - timedelta(hours=1)
        test_user.save()
        
        assert test_user.is_google_oauth_expired() is True
    
    def test_clear_google_oauth_tokens(self, test_user):
        """Test clearing Google OAuth tokens."""
        # Set up tokens first
        token_data = {
            'token': 'access_token',
            'refresh_token': 'refresh_token',
            'expires_in': 3600
        }
        test_user.set_google_oauth_tokens(token_data)
        
        # Clear tokens
        test_user.clear_google_oauth_tokens()
        
        assert test_user.google_calendar_connected is False
        assert test_user.google_oauth_token is None
        assert test_user.google_oauth_refresh_token is None
        assert test_user.google_oauth_expires_at is None
