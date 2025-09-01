"""Comprehensive Google Calendar OAuth integration tests."""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from flask import session

from app import create_app, db
from app.models.user import User
from app.models.tenant import Tenant
from app.services.google_oauth import GoogleOAuthService
from app.utils.exceptions import OAuthError


@pytest.fixture
def app():
    """Create test app with Google OAuth configuration."""
    app = create_app('testing')
    
    # Configure Google OAuth settings
    app.config.update({
        'GOOGLE_CLIENT_ID': 'test_google_client_id_12345',
        'GOOGLE_CLIENT_SECRET': 'test_google_client_secret_67890',
        'GOOGLE_REDIRECT_URI': 'http://localhost:5000/auth/oauth/google/callback',
        'SECRET_KEY': 'test_secret_key_for_sessions'
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def tenant(app):
    """Create test tenant."""
    with app.app_context():
        tenant = Tenant(
            name='Test Calendar Company',
            domain='calendar-test.example.com',
            slug='calendar-test',
            subscription_status='active'
        )
        tenant.save()
        return tenant


@pytest.fixture
def user(app, tenant):
    """Create test user."""
    with app.app_context():
        user = User.create(
            email='calendar-test@example.com',
            password='SecurePass123!',
            tenant_id=tenant.id,
            role='owner'
        )
        return user


@pytest.fixture
def auth_headers(app, user):
    """Create authentication headers."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(identity=user.id)
        return {'Authorization': f'Bearer {token}'}


class TestGoogleOAuthConfiguration:
    """Test Google OAuth service configuration."""
    
    def test_oauth_service_configured(self, app):
        """Test OAuth service is properly configured."""
        with app.app_context():
            service = GoogleOAuthService()
            
            assert service.is_configured() is True
            assert service.client_id == 'test_google_client_id_12345'
            assert service.client_secret == 'test_google_client_secret_67890'
            assert service.redirect_uri == 'http://localhost:5000/auth/oauth/google/callback'
    
    def test_oauth_service_not_configured(self, app):
        """Test OAuth service when not configured."""
        with app.app_context():
            # Clear configuration
            app.config['GOOGLE_CLIENT_ID'] = None
            
            service = GoogleOAuthService()
            assert service.is_configured() is False
    
    def test_oauth_scopes_configuration(self, app):
        """Test OAuth scopes are properly configured."""
        with app.app_context():
            service = GoogleOAuthService()
            
            expected_scopes = [
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/calendar.events',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile'
            ]
            
            assert service.SCOPES == expected_scopes


class TestOAuthAuthorizationFlow:
    """Test OAuth authorization flow."""
    
    def test_get_authorization_url_not_configured(self, app, user):
        """Test authorization URL generation when not configured."""
        with app.app_context():
            app.config['GOOGLE_CLIENT_ID'] = None
            
            service = GoogleOAuthService()
            
            with pytest.raises(OAuthError, match="Google OAuth not configured"):
                service.get_authorization_url(user.id)
    
    def test_get_authorization_url_success(self, app, user):
        """Test successful authorization URL generation."""
        with app.app_context():
            service = GoogleOAuthService()
            
            with app.test_request_context():
                auth_url = service.get_authorization_url(user.id, state='test_state_123')
                
                # Verify URL components
                assert 'accounts.google.com/o/oauth2/auth' in auth_url
                assert 'client_id=test_google_client_id_12345' in auth_url
                assert 'redirect_uri=http%3A//localhost%3A5000/auth/oauth/google/callback' in auth_url
                assert 'state=test_state_123' in auth_url
                assert 'access_type=offline' in auth_url
                assert 'prompt=consent' in auth_url
                
                # Verify session data
                assert session['oauth_state'] == 'test_state_123'
                assert session['oauth_user_id'] == user.id
    
    def test_get_authorization_url_auto_state(self, app, user):
        """Test authorization URL generation with auto-generated state."""
        with app.app_context():
            service = GoogleOAuthService()
            
            with app.test_request_context():
                auth_url = service.get_authorization_url(user.id)
                
                # Verify state was generated and stored
                assert 'oauth_state' in session
                assert 'oauth_user_id' in session
                assert session['oauth_user_id'] == user.id
                
                # Verify state is in URL
                state = session['oauth_state']
                assert f'state={state}' in auth_url
    
    def test_authorization_url_includes_all_scopes(self, app, user):
        """Test authorization URL includes all required scopes."""
        with app.app_context():
            service = GoogleOAuthService()
            
            with app.test_request_context():
                auth_url = service.get_authorization_url(user.id)
                
                # Check that calendar scopes are included
                assert 'https%3A//www.googleapis.com/auth/calendar' in auth_url
                assert 'https%3A//www.googleapis.com/auth/userinfo.email' in auth_url


class TestOAuthCallbackHandling:
    """Test OAuth callback handling."""
    
    @patch('app.services.google_oauth.Flow')
    @patch('app.services.google_oauth.build')
    def test_handle_callback_success(self, mock_build, mock_flow_class, app, user):
        """Test successful OAuth callback handling."""
        with app.app_context():
            # Mock Flow
            mock_flow = Mock()
            mock_flow_class.from_client_config.return_value = mock_flow
            
            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = 'access_token_12345'
            mock_credentials.refresh_token = 'refresh_token_67890'
            mock_credentials.token_uri = 'https://oauth2.googleapis.com/token'
            mock_credentials.client_id = 'test_google_client_id_12345'
            mock_credentials.client_secret = 'test_google_client_secret_67890'
            mock_credentials.scopes = [
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/userinfo.email'
            ]
            mock_credentials.expiry = datetime.utcnow() + timedelta(hours=1)
            
            mock_flow.credentials = mock_credentials
            
            # Mock user info service
            mock_service = Mock()
            mock_userinfo = Mock()
            mock_userinfo.get().execute.return_value = {
                'email': 'calendar-test@example.com',
                'name': 'Test User',
                'id': '123456789'
            }
            mock_service.userinfo.return_value = mock_userinfo
            mock_build.return_value = mock_service
            
            service = GoogleOAuthService()
            
            with app.test_request_context():
                # Set up session
                session['oauth_state'] = 'test_state_123'
                session['oauth_user_id'] = user.id
                
                result = service.handle_callback('auth_code_12345', 'test_state_123')
                
                # Verify result
                assert result['user'].id == user.id
                assert result['user_info']['email'] == 'calendar-test@example.com'
                assert 'token_data' in result
                
                # Verify user tokens were stored
                user.refresh()
                assert user.google_calendar_connected is True
                assert user.google_oauth_refresh_token == 'refresh_token_67890'
                
                # Verify session was cleared
                assert 'oauth_state' not in session
                assert 'oauth_user_id' not in session
    
    def test_handle_callback_invalid_state(self, app, user):
        """Test callback handling with invalid state."""
        with app.app_context():
            service = GoogleOAuthService()
            
            with app.test_request_context():
                session['oauth_state'] = 'correct_state'
                session['oauth_user_id'] = user.id
                
                with pytest.raises(OAuthError, match="Invalid state parameter"):
                    service.handle_callback('auth_code', 'wrong_state')
    
    def test_handle_callback_no_session_state(self, app, user):
        """Test callback handling without session state."""
        with app.app_context():
            service = GoogleOAuthService()
            
            with app.test_request_context():
                # No session state set
                with pytest.raises(OAuthError, match="Invalid state parameter"):
                    service.handle_callback('auth_code', 'test_state')
    
    def test_handle_callback_no_user_id(self, app):
        """Test callback handling without user ID in session."""
        with app.app_context():
            service = GoogleOAuthService()
            
            with app.test_request_context():
                session['oauth_state'] = 'test_state'
                # No user_id in session
                
                with pytest.raises(OAuthError, match="No user ID in session"):
                    service.handle_callback('auth_code', 'test_state')
    
    def test_handle_callback_user_not_found(self, app):
        """Test callback handling when user not found."""
        with app.app_context():
            service = GoogleOAuthService()
            
            with app.test_request_context():
                session['oauth_state'] = 'test_state'
                session['oauth_user_id'] = 99999  # Non-existent user
                
                with patch('app.services.google_oauth.Flow') as mock_flow_class:
                    mock_flow = Mock()
                    mock_flow_class.from_client_config.return_value = mock_flow
                    
                    mock_credentials = Mock()
                    mock_credentials.token = 'token'
                    mock_credentials.refresh_token = 'refresh'
                    mock_flow.credentials = mock_credentials
                    
                    with pytest.raises(OAuthError, match="User not found"):
                        service.handle_callback('auth_code', 'test_state')
    
    @patch('app.services.google_oauth.Flow')
    def test_handle_callback_flow_error(self, mock_flow_class, app, user):
        """Test callback handling when Flow raises exception."""
        with app.app_context():
            mock_flow_class.from_client_config.side_effect = Exception("Flow error")
            
            service = GoogleOAuthService()
            
            with app.test_request_context():
                session['oauth_state'] = 'test_state'
                session['oauth_user_id'] = user.id
                
                with pytest.raises(OAuthError, match="OAuth callback failed"):
                    service.handle_callback('auth_code', 'test_state')
                
                # Verify session was cleared
                assert 'oauth_state' not in session
                assert 'oauth_user_id' not in session


class TestTokenRefresh:
    """Test OAuth token refresh functionality."""
    
    def test_refresh_token_no_refresh_token(self, app, user):
        """Test token refresh when no refresh token available."""
        with app.app_context():
            # User has no refresh token
            user.google_oauth_refresh_token = None
            user.save()
            
            service = GoogleOAuthService()
            result = service.refresh_token(user)
            
            assert result is False
    
    def test_refresh_token_no_oauth_tokens(self, app, user):
        """Test token refresh when no OAuth tokens stored."""
        with app.app_context():
            user.google_oauth_refresh_token = 'refresh_token'
            user.google_oauth_token = None  # No tokens stored
            user.save()
            
            service = GoogleOAuthService()
            result = service.refresh_token(user)
            
            assert result is False
    
    @patch('app.services.google_oauth.Credentials')
    @patch('app.services.google_oauth.Request')
    def test_refresh_token_success(self, mock_request, mock_credentials_class, app, user):
        """Test successful token refresh."""
        with app.app_context():
            # Set up user with tokens
            token_data = {
                'token': 'old_access_token',
                'refresh_token': 'refresh_token_123',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['https://www.googleapis.com/auth/calendar'],
                'expires_in': 3600
            }
            user.set_google_oauth_tokens(token_data)
            
            # Mock credentials
            mock_credentials = Mock()
            mock_credentials.token = 'new_access_token'
            mock_credentials.refresh_token = 'refresh_token_123'
            mock_credentials.token_uri = 'https://oauth2.googleapis.com/token'
            mock_credentials.client_id = 'test_client_id'
            mock_credentials.client_secret = 'test_client_secret'
            mock_credentials.scopes = ['https://www.googleapis.com/auth/calendar']
            mock_credentials.expiry = datetime.utcnow() + timedelta(hours=1)
            
            mock_credentials_class.return_value = mock_credentials
            
            service = GoogleOAuthService()
            result = service.refresh_token(user)
            
            assert result is True
            
            # Verify credentials.refresh was called
            mock_credentials.refresh.assert_called_once()
            
            # Verify new tokens were stored
            user.refresh()
            updated_tokens = user.get_google_oauth_tokens()
            assert updated_tokens['token'] == 'new_access_token'
    
    @patch('app.services.google_oauth.Credentials')
    def test_refresh_token_failure(self, mock_credentials_class, app, user):
        """Test token refresh failure."""
        with app.app_context():
            # Set up user with tokens
            token_data = {
                'token': 'access_token',
                'refresh_token': 'refresh_token',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
            user.set_google_oauth_tokens(token_data)
            
            # Mock credentials to raise exception
            mock_credentials = Mock()
            mock_credentials.refresh.side_effect = Exception("Refresh failed")
            mock_credentials_class.return_value = mock_credentials
            
            service = GoogleOAuthService()
            result = service.refresh_token(user)
            
            assert result is False
            
            # Verify tokens were cleared
            user.refresh()
            assert user.google_calendar_connected is False


class TestCredentialsManagement:
    """Test credentials management functionality."""
    
    def test_get_valid_credentials_not_connected(self, app, user):
        """Test getting credentials when user not connected."""
        with app.app_context():
            user.google_calendar_connected = False
            user.save()
            
            service = GoogleOAuthService()
            credentials = service.get_valid_credentials(user)
            
            assert credentials is None
    
    def test_get_valid_credentials_no_tokens(self, app, user):
        """Test getting credentials when no tokens stored."""
        with app.app_context():
            user.google_calendar_connected = True
            user.google_oauth_token = None
            user.save()
            
            service = GoogleOAuthService()
            credentials = service.get_valid_credentials(user)
            
            assert credentials is None
    
    @patch('app.services.google_oauth.GoogleOAuthService.refresh_token')
    @patch('app.services.google_oauth.Credentials')
    def test_get_valid_credentials_expired_refresh_success(
        self, mock_credentials_class, mock_refresh, app, user
    ):
        """Test getting credentials when expired but refresh succeeds."""
        with app.app_context():
            # Set up user with expired tokens
            token_data = {
                'token': 'access_token',
                'refresh_token': 'refresh_token',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
            user.set_google_oauth_tokens(token_data)
            user.google_oauth_expires_at = datetime.utcnow() - timedelta(hours=1)  # Expired
            user.save()
            
            # Mock successful refresh
            mock_refresh.return_value = True
            
            # Mock updated token data after refresh
            updated_token_data = token_data.copy()
            updated_token_data['token'] = 'new_access_token'
            
            with patch.object(user, 'get_google_oauth_tokens', return_value=updated_token_data):
                mock_credentials = Mock()
                mock_credentials_class.return_value = mock_credentials
                
                service = GoogleOAuthService()
                credentials = service.get_valid_credentials(user)
                
                assert credentials is not None
                assert credentials == mock_credentials
                mock_refresh.assert_called_once_with(user)
    
    @patch('app.services.google_oauth.GoogleOAuthService.refresh_token')
    def test_get_valid_credentials_expired_refresh_fails(self, mock_refresh, app, user):
        """Test getting credentials when expired and refresh fails."""
        with app.app_context():
            # Set up user with expired tokens
            token_data = {
                'token': 'access_token',
                'refresh_token': 'refresh_token'
            }
            user.set_google_oauth_tokens(token_data)
            user.google_oauth_expires_at = datetime.utcnow() - timedelta(hours=1)  # Expired
            user.save()
            
            # Mock failed refresh
            mock_refresh.return_value = False
            
            service = GoogleOAuthService()
            credentials = service.get_valid_credentials(user)
            
            assert credentials is None
            mock_refresh.assert_called_once_with(user)
    
    @patch('app.services.google_oauth.Credentials')
    def test_get_valid_credentials_success(self, mock_credentials_class, app, user):
        """Test successful credentials retrieval."""
        with app.app_context():
            # Set up user with valid tokens
            token_data = {
                'token': 'access_token',
                'refresh_token': 'refresh_token',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
            user.set_google_oauth_tokens(token_data)
            user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=1)  # Valid
            user.save()
            
            mock_credentials = Mock()
            mock_credentials_class.return_value = mock_credentials
            
            service = GoogleOAuthService()
            credentials = service.get_valid_credentials(user)
            
            assert credentials is not None
            assert credentials == mock_credentials
    
    @patch('app.services.google_oauth.Credentials')
    def test_get_valid_credentials_creation_error(self, mock_credentials_class, app, user):
        """Test credentials retrieval when creation fails."""
        with app.app_context():
            # Set up user with tokens
            token_data = {
                'token': 'access_token',
                'refresh_token': 'refresh_token'
            }
            user.set_google_oauth_tokens(token_data)
            user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=1)
            user.save()
            
            # Mock credentials creation failure
            mock_credentials_class.side_effect = Exception("Credentials error")
            
            service = GoogleOAuthService()
            credentials = service.get_valid_credentials(user)
            
            assert credentials is None


class TestDisconnectCalendar:
    """Test calendar disconnection functionality."""
    
    @patch('requests.post')
    def test_disconnect_calendar_success(self, mock_post, app, user):
        """Test successful calendar disconnection."""
        with app.app_context():
            # Set up user with tokens
            token_data = {
                'token': 'access_token_to_revoke',
                'refresh_token': 'refresh_token'
            }
            user.set_google_oauth_tokens(token_data)
            
            # Mock successful revoke response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            service = GoogleOAuthService()
            result = service.disconnect_calendar(user)
            
            assert result is True
            
            # Verify revoke request was made
            mock_post.assert_called_once_with(
                'https://oauth2.googleapis.com/revoke?token=access_token_to_revoke'
            )
            
            # Verify tokens were cleared
            user.refresh()
            assert user.google_calendar_connected is False
            assert user.google_oauth_token is None
    
    @patch('requests.post')
    def test_disconnect_calendar_revoke_fails(self, mock_post, app, user):
        """Test calendar disconnection when revoke fails."""
        with app.app_context():
            # Set up user with tokens
            token_data = {'token': 'access_token'}
            user.set_google_oauth_tokens(token_data)
            
            # Mock failed revoke response
            mock_response = Mock()
            mock_response.status_code = 500
            mock_post.return_value = mock_response
            
            service = GoogleOAuthService()
            result = service.disconnect_calendar(user)
            
            assert result is True  # Still returns True, just logs warning
            
            # Verify tokens were cleared anyway
            user.refresh()
            assert user.google_calendar_connected is False
    
    def test_disconnect_calendar_no_tokens(self, app, user):
        """Test calendar disconnection when no tokens stored."""
        with app.app_context():
            # User has no tokens
            user.google_oauth_token = None
            user.save()
            
            service = GoogleOAuthService()
            result = service.disconnect_calendar(user)
            
            assert result is True
            
            # Verify user is disconnected
            user.refresh()
            assert user.google_calendar_connected is False
    
    @patch('requests.post')
    def test_disconnect_calendar_exception(self, mock_post, app, user):
        """Test calendar disconnection when exception occurs."""
        with app.app_context():
            # Set up user with tokens
            token_data = {'token': 'access_token'}
            user.set_google_oauth_tokens(token_data)
            
            # Mock exception during revoke
            mock_post.side_effect = Exception("Network error")
            
            service = GoogleOAuthService()
            result = service.disconnect_calendar(user)
            
            assert result is False
            
            # Verify tokens were cleared anyway
            user.refresh()
            assert user.google_calendar_connected is False


class TestCalendarServiceIntegration:
    """Test calendar service integration with OAuth."""
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_valid_credentials')
    @patch('app.services.google_oauth.build')
    def test_get_calendar_service_success(self, mock_build, mock_credentials, app, user):
        """Test successful calendar service creation."""
        with app.app_context():
            mock_creds = Mock()
            mock_credentials.return_value = mock_creds
            
            mock_service = Mock()
            mock_build.return_value = mock_service
            
            service = GoogleOAuthService()
            calendar_service = service.get_calendar_service(user)
            
            assert calendar_service == mock_service
            mock_build.assert_called_once_with('calendar', 'v3', credentials=mock_creds)
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_valid_credentials')
    def test_get_calendar_service_no_credentials(self, mock_credentials, app, user):
        """Test calendar service creation without valid credentials."""
        with app.app_context():
            mock_credentials.return_value = None
            
            service = GoogleOAuthService()
            
            with pytest.raises(OAuthError, match="No valid Google credentials"):
                service.get_calendar_service(user)
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_valid_credentials')
    @patch('app.services.google_oauth.build')
    def test_get_calendar_service_build_error(self, mock_build, mock_credentials, app, user):
        """Test calendar service creation when build fails."""
        with app.app_context():
            mock_credentials.return_value = Mock()
            mock_build.side_effect = Exception("Build failed")
            
            service = GoogleOAuthService()
            
            with pytest.raises(Exception, match="Failed to connect to Google Calendar"):
                service.get_calendar_service(user)


class TestConnectionTesting:
    """Test connection testing functionality."""
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_test_connection_success(self, mock_service, app, user):
        """Test successful connection test."""
        with app.app_context():
            # Mock calendar service
            mock_calendar_service = Mock()
            mock_service.return_value = mock_calendar_service
            
            # Mock calendar list response
            mock_calendar_service.calendarList().list().execute.return_value = {
                'items': [
                    {'id': 'primary', 'summary': 'Primary', 'primary': True},
                    {'id': 'work', 'summary': 'Work Calendar', 'primary': False}
                ]
            }
            
            service = GoogleOAuthService()
            result = service.test_connection(user)
            
            assert result['connected'] is True
            assert result['calendar_count'] == 2
            assert result['primary_calendar']['id'] == 'primary'
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_test_connection_failure(self, mock_service, app, user):
        """Test connection test failure."""
        with app.app_context():
            mock_service.side_effect = Exception("Connection failed")
            
            service = GoogleOAuthService()
            result = service.test_connection(user)
            
            assert result['connected'] is False
            assert 'error' in result
            assert 'Connection failed' in result['error']
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_test_connection_no_primary_calendar(self, mock_service, app, user):
        """Test connection test when no primary calendar exists."""
        with app.app_context():
            # Mock calendar service
            mock_calendar_service = Mock()
            mock_service.return_value = mock_calendar_service
            
            # Mock calendar list response without primary
            mock_calendar_service.calendarList().list().execute.return_value = {
                'items': [
                    {'id': 'work', 'summary': 'Work Calendar', 'primary': False}
                ]
            }
            
            service = GoogleOAuthService()
            result = service.test_connection(user)
            
            assert result['connected'] is True
            assert result['calendar_count'] == 1
            assert result['primary_calendar'] is None


class TestPermissionValidation:
    """Test permission validation for calendar operations."""
    
    def test_calendar_scopes_include_required_permissions(self, app):
        """Test that OAuth scopes include all required calendar permissions."""
        with app.app_context():
            service = GoogleOAuthService()
            
            required_scopes = [
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/calendar.events'
            ]
            
            for scope in required_scopes:
                assert scope in service.SCOPES
    
    def test_user_info_scopes_included(self, app):
        """Test that user info scopes are included for profile access."""
        with app.app_context():
            service = GoogleOAuthService()
            
            user_info_scopes = [
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile'
            ]
            
            for scope in user_info_scopes:
                assert scope in service.SCOPES


class TestTokenManagement:
    """Test token management and storage."""
    
    def test_token_expiry_calculation(self, app, user):
        """Test token expiry calculation and storage."""
        with app.app_context():
            token_data = {
                'token': 'access_token',
                'refresh_token': 'refresh_token',
                'expires_in': 3600
            }
            
            user.set_google_oauth_tokens(token_data)
            
            # Verify expiry was calculated and stored
            assert user.google_oauth_expires_at is not None
            
            # Should expire in approximately 1 hour
            time_diff = user.google_oauth_expires_at - datetime.utcnow()
            assert 3500 <= time_diff.total_seconds() <= 3600
    
    def test_token_expiry_check(self, app, user):
        """Test token expiry checking."""
        with app.app_context():
            # Set expired token
            user.google_oauth_expires_at = datetime.utcnow() - timedelta(hours=1)
            user.save()
            
            assert user.is_google_oauth_expired() is True
            
            # Set valid token
            user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=1)
            user.save()
            
            assert user.is_google_oauth_expired() is False
    
    def test_token_storage_and_retrieval(self, app, user):
        """Test token storage and retrieval."""
        with app.app_context():
            original_token_data = {
                'token': 'access_token_123',
                'refresh_token': 'refresh_token_456',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['https://www.googleapis.com/auth/calendar'],
                'expires_in': 3600
            }
            
            user.set_google_oauth_tokens(original_token_data)
            
            # Retrieve and verify
            retrieved_data = user.get_google_oauth_tokens()
            
            assert retrieved_data['token'] == 'access_token_123'
            assert retrieved_data['token_uri'] == 'https://oauth2.googleapis.com/token'
            assert retrieved_data['client_id'] == 'test_client_id'
            assert retrieved_data['scopes'] == ['https://www.googleapis.com/auth/calendar']
    
    def test_token_clearing(self, app, user):
        """Test token clearing functionality."""
        with app.app_context():
            # Set tokens
            token_data = {
                'token': 'access_token',
                'refresh_token': 'refresh_token'
            }
            user.set_google_oauth_tokens(token_data)
            
            assert user.google_calendar_connected is True
            
            # Clear tokens
            user.clear_google_oauth_tokens()
            
            assert user.google_calendar_connected is False
            assert user.google_oauth_token is None
            assert user.google_oauth_refresh_token is None
            assert user.google_oauth_expires_at is None