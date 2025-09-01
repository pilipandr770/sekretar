"""Comprehensive OAuth integration testing suite with real Google credentials."""
import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from flask import session
from flask_jwt_extended import create_access_token

from app.models.user import User
from app.models.tenant import Tenant
from app.models.audit_log import AuditLog
from app.services.google_oauth import GoogleOAuthService
from app.utils.exceptions import OAuthError, ExternalAPIError
from app import db


class TestGoogleOAuthFlowIntegration:
    """Test complete Google OAuth flow with real credentials simulation."""
    
    @pytest.fixture
    def real_company_data(self):
        """Load real company data for OAuth testing."""
        try:
            with open('comprehensive_test_dataset.json', 'r', encoding='utf-8') as f:
                dataset = json.load(f)
            return dataset['companies']
        except FileNotFoundError:
            # Fallback to predefined data if file not found
            return {
                "oauth_test_company": {
                    "name": "Google Ireland Limited",
                    "vat_number": "IE6388047V",
                    "lei_code": "549300PPXHEU2JF0AM85",
                    "country_code": "IE",
                    "address": "Gordon House, Barrow Street, Dublin 4",
                    "industry": "Technology",
                    "size": "Large"
                }
            }
    
    @pytest.fixture
    def oauth_test_user(self, app, real_company_data):
        """Create test user with real company data for OAuth testing."""
        with app.app_context():
            company = real_company_data['oauth_test_company']
            
            # Create tenant with real company data
            tenant, owner = Tenant.create_with_owner(
                name=company['name'],
                owner_email='oauth.test@google.com',
                owner_password='SecurePassword123!',
                owner_first_name='OAuth',
                owner_last_name='Test'
            )
            tenant.vat_number = company['vat_number']
            tenant.lei_code = company['lei_code']
            tenant.address = company['address']
            tenant.country_code = company['country_code']
            tenant.save()
            
            return {
                'tenant': tenant,
                'user': owner,
                'company': company
            }
    
    @pytest.fixture
    def mock_google_config(self, app):
        """Mock Google OAuth configuration."""
        with app.app_context():
            app.config['GOOGLE_CLIENT_ID'] = 'test_google_client_id_12345'
            app.config['GOOGLE_CLIENT_SECRET'] = 'test_google_client_secret_67890'
            app.config['GOOGLE_REDIRECT_URI'] = 'http://localhost:5000/auth/oauth/google/callback'
            app.config['GOOGLE_SCOPES'] = [
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile'
            ]
            yield app
    
    def test_oauth_configuration_validation(self, mock_google_config):
        """Test OAuth configuration validation with real-like credentials."""
        with mock_google_config.app_context():
            service = GoogleOAuthService()
            
            # Test with all required configuration
            assert service.is_configured() is True
            
            # Test missing client ID
            mock_google_config.config['GOOGLE_CLIENT_ID'] = None
            service = GoogleOAuthService()
            assert service.is_configured() is False
            
            # Test missing client secret
            mock_google_config.config['GOOGLE_CLIENT_ID'] = 'test_client_id'
            mock_google_config.config['GOOGLE_CLIENT_SECRET'] = None
            service = GoogleOAuthService()
            assert service.is_configured() is False
            
            # Test missing redirect URI
            mock_google_config.config['GOOGLE_CLIENT_SECRET'] = 'test_secret'
            mock_google_config.config['GOOGLE_REDIRECT_URI'] = None
            service = GoogleOAuthService()
            assert service.is_configured() is False  
  @patch('app.services.google_oauth.Flow')
    def test_authorization_url_generation_with_real_params(self, mock_flow, mock_google_config, oauth_test_user):
        """Test authorization URL generation with realistic parameters."""
        with mock_google_config.app_context():
            user_data = oauth_test_user
            user = user_data['user']
            
            # Mock Flow to simulate Google's OAuth flow
            mock_flow_instance = Mock()
            expected_auth_url = (
                'https://accounts.google.com/o/oauth2/auth?'
                'response_type=code&client_id=test_google_client_id_12345&'
                'redirect_uri=http%3A//localhost%3A5000/auth/oauth/google/callback&'
                'scope=https%3A//www.googleapis.com/auth/calendar+https%3A//www.googleapis.com/auth/userinfo.email&'
                'state=oauth_state_12345&access_type=offline&prompt=consent'
            )
            mock_flow_instance.authorization_url.return_value = (expected_auth_url, 'oauth_state_12345')
            mock_flow.from_client_config.return_value = mock_flow_instance
            
            service = GoogleOAuthService()
            
            with mock_google_config.test_request_context():
                url = service.get_authorization_url(user.id, 'oauth_state_12345')
                
                assert url == expected_auth_url
                assert session['oauth_state'] == 'oauth_state_12345'
                assert session['oauth_user_id'] == user.id
                
                # Verify Flow was configured correctly
                mock_flow.from_client_config.assert_called_once()
                call_args = mock_flow.from_client_config.call_args[0]
                client_config = call_args[0]
                
                assert client_config['web']['client_id'] == 'test_google_client_id_12345'
                assert client_config['web']['client_secret'] == 'test_google_client_secret_67890'
                assert client_config['web']['redirect_uris'][0] == 'http://localhost:5000/auth/oauth/google/callback'
                
                # Verify authorization_url was called with correct parameters
                mock_flow_instance.authorization_url.assert_called_once_with(
                    access_type='offline',
                    include_granted_scopes='true',
                    state='oauth_state_12345',
                    prompt='consent'
                )
    
    @patch('app.services.google_oauth.Flow')
    @patch('app.services.google_oauth.build')
    def test_complete_oauth_callback_flow(self, mock_build, mock_flow, mock_google_config, oauth_test_user):
        """Test complete OAuth callback flow with realistic Google response."""
        with mock_google_config.app_context():
            user_data = oauth_test_user
            user = user_data['user']
            company = user_data['company']
            
            # Mock realistic Google credentials
            mock_credentials = Mock()
            mock_credentials.token = 'ya29.a0ARrdaM-realistic_access_token_example'
            mock_credentials.refresh_token = '1//04-realistic_refresh_token_example'
            mock_credentials.token_uri = 'https://oauth2.googleapis.com/token'
            mock_credentials.client_id = 'test_google_client_id_12345'
            mock_credentials.client_secret = 'test_google_client_secret_67890'
            mock_credentials.scopes = [
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile'
            ]
            mock_credentials.expiry = datetime.utcnow() + timedelta(hours=1)
            
            # Mock Flow
            mock_flow_instance = Mock()
            mock_flow_instance.credentials = mock_credentials
            mock_flow.from_client_config.return_value = mock_flow_instance
            
            # Mock Google API service for user info (realistic response)
            mock_service = Mock()
            mock_userinfo = Mock()
            mock_userinfo.get.return_value.execute.return_value = {
                'id': '123456789012345678901',
                'email': 'oauth.test@google.com',
                'verified_email': True,
                'name': 'OAuth Test User',
                'given_name': 'OAuth',
                'family_name': 'Test',
                'picture': 'https://lh3.googleusercontent.com/a/default-user=s96-c',
                'locale': 'en'
            }
            mock_service.userinfo.return_value = mock_userinfo
            mock_build.return_value = mock_service
            
            service = GoogleOAuthService()
            
            with mock_google_config.test_request_context():
                session['oauth_state'] = 'oauth_state_12345'
                session['oauth_user_id'] = user.id
                
                result = service.handle_callback('realistic_auth_code_example', 'oauth_state_12345')
                
                # Verify result structure
                assert result['user'].id == user.id
                assert result['user_info']['email'] == 'oauth.test@google.com'
                assert result['user_info']['name'] == 'OAuth Test User'
                assert result['user_info']['verified_email'] is True
                assert 'token_data' in result
                
                # Verify user tokens were stored correctly
                user.refresh()
                assert user.google_calendar_connected is True
                assert user.google_oauth_refresh_token == '1//04-realistic_refresh_token_example'
                assert user.google_oauth_expires_at is not None
                
                # Verify stored token data
                stored_tokens = user.get_google_oauth_tokens()
                assert stored_tokens['token'] == 'ya29.a0ARrdaM-realistic_access_token_example'
                assert stored_tokens['refresh_token'] == '1//04-realistic_refresh_token_example'
                assert stored_tokens['client_id'] == 'test_google_client_id_12345'
                
                # Verify session was cleared
                assert 'oauth_state' not in session
                assert 'oauth_user_id' not in session
                
                # Verify Flow was called correctly
                mock_flow_instance.fetch_token.assert_called_once_with(
                    authorization_response=None,
                    code='realistic_auth_code_example'
                )
    
    def test_oauth_callback_error_scenarios(self, mock_google_config, oauth_test_user):
        """Test OAuth callback error handling scenarios."""
        with mock_google_config.app_context():
            user_data = oauth_test_user
            user = user_data['user']
            
            service = GoogleOAuthService()
            
            with mock_google_config.test_request_context():
                # Test invalid state parameter
                session['oauth_state'] = 'valid_state'
                session['oauth_user_id'] = user.id
                
                with pytest.raises(OAuthError, match="Invalid state parameter"):
                    service.handle_callback('auth_code', 'invalid_state')
                
                # Test missing user ID in session
                session['oauth_state'] = 'test_state'
                del session['oauth_user_id']
                
                with pytest.raises(OAuthError, match="No user ID in session"):
                    service.handle_callback('auth_code', 'test_state')
                
                # Test non-existent user
                session['oauth_user_id'] = 99999
                
                with pytest.raises(OAuthError, match="User not found"):
                    service.handle_callback('auth_code', 'test_state')


class TestOAuthAPIEndpointsIntegration:
    """Test OAuth API endpoints with comprehensive integration scenarios."""
    
    @pytest.fixture
    def oauth_test_setup(self, app, real_company_data):
        """Set up OAuth test environment with multiple users."""
        with app.app_context():
            company = real_company_data['oauth_test_company']
            
            # Create tenant with real company data
            tenant, owner = Tenant.create_with_owner(
                name=company['name'],
                owner_email='oauth.owner@google.com',
                owner_password='SecurePassword123!',
                owner_first_name='OAuth',
                owner_last_name='Owner'
            )
            
            # Create additional user
            manager = User.create(
                email='oauth.manager@google.com',
                password='SecurePassword123!',
                tenant_id=tenant.id,
                first_name='OAuth',
                last_name='Manager',
                role='manager'
            )
            
            return {
                'tenant': tenant,
                'owner': owner,
                'manager': manager,
                'company': company
            }
    
    @patch('app.auth.oauth_routes.GoogleOAuthService')
    def test_oauth_connect_endpoint_comprehensive(self, mock_service_class, client, oauth_test_setup, mock_google_config):
        """Test OAuth connect endpoint with comprehensive scenarios."""
        test_data = oauth_test_setup
        owner = test_data['owner']
        manager = test_data['manager']
        
        # Create access tokens
        owner_token = create_access_token(identity=owner)
        manager_token = create_access_token(identity=manager)
        
        owner_headers = {'Authorization': f'Bearer {owner_token}'}
        manager_headers = {'Authorization': f'Bearer {manager_token}'}
        
        # Mock OAuth service
        mock_service = Mock()
        mock_service.is_configured.return_value = True
        mock_service.get_authorization_url.return_value = (
            'https://accounts.google.com/o/oauth2/auth?'
            'client_id=test_google_client_id_12345&'
            'redirect_uri=http%3A//localhost%3A5000/auth/oauth/google/callback&'
            'scope=calendar&state=oauth_state_12345'
        )
        mock_service_class.return_value = mock_service
        
        # Test owner can connect
        response = client.post('/auth/oauth/google/connect', headers=owner_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'authorization_url' in data['data']
        assert data['data']['provider'] == 'google'
        assert 'oauth_state_12345' in data['data']['authorization_url']
        
        # Test manager can also connect
        response = client.post('/auth/oauth/google/connect', headers=manager_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Verify service was called with correct user IDs
        calls = mock_service.get_authorization_url.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == owner.id  # First call with owner ID
        assert calls[1][0][0] == manager.id  # Second call with manager ID


class TestOAuthTokenManagementIntegration:
    """Test OAuth token management with realistic scenarios."""
    
    @pytest.fixture
    def token_test_user(self, app, real_company_data):
        """Create user for token management testing."""
        with app.app_context():
            company = real_company_data['oauth_test_company']
            
            tenant, owner = Tenant.create_with_owner(
                name=company['name'],
                owner_email='token.test@google.com',
                owner_password='SecurePassword123!',
                owner_first_name='Token',
                owner_last_name='Test'
            )
            
            return owner
    
    def test_token_storage_and_retrieval(self, app, token_test_user):
        """Test comprehensive token storage and retrieval."""
        with app.app_context():
            user = token_test_user
            
            # Test storing comprehensive token data
            token_data = {
                'token': 'ya29.a0ARrdaM-comprehensive_access_token_example_12345',
                'refresh_token': '1//04-comprehensive_refresh_token_example_67890',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_google_client_id_12345',
                'client_secret': 'test_google_client_secret_67890',
                'scopes': [
                    'https://www.googleapis.com/auth/calendar',
                    'https://www.googleapis.com/auth/userinfo.email',
                    'https://www.googleapis.com/auth/userinfo.profile'
                ],
                'expires_in': 3600,
                'id_token': 'eyJhbGciOiJSUzI1NiIsImtpZCI6IjExIn0.example_id_token'
            }
            
            user.set_google_oauth_tokens(token_data)
            
            # Verify all fields were stored correctly
            assert user.google_calendar_connected is True
            assert user.google_oauth_refresh_token == '1//04-comprehensive_refresh_token_example_67890'
            assert user.google_oauth_expires_at is not None
            
            # Verify token retrieval
            stored_tokens = user.get_google_oauth_tokens()
            assert stored_tokens['token'] == 'ya29.a0ARrdaM-comprehensive_access_token_example_12345'
            assert stored_tokens['refresh_token'] == '1//04-comprehensive_refresh_token_example_67890'
            assert stored_tokens['client_id'] == 'test_google_client_id_12345'
            assert stored_tokens['client_secret'] == 'test_google_client_secret_67890'
            assert len(stored_tokens['scopes']) == 3
            assert 'https://www.googleapis.com/auth/calendar' in stored_tokens['scopes']
            
            # Test expiry calculation
            expected_expiry = datetime.utcnow() + timedelta(seconds=3600)
            actual_expiry = user.google_oauth_expires_at
            time_diff = abs((expected_expiry - actual_expiry).total_seconds())
            assert time_diff < 60  # Within 1 minute tolerance
    
    def test_token_expiry_scenarios(self, app, token_test_user):
        """Test various token expiry scenarios."""
        with app.app_context():
            user = token_test_user
            
            # Test with no expiry date (should be considered expired)
            user.google_oauth_expires_at = None
            assert user.is_google_oauth_expired() is True
            
            # Test with future expiry (not expired)
            user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=1)
            assert user.is_google_oauth_expired() is False
            
            # Test with past expiry (expired)
            user.google_oauth_expires_at = datetime.utcnow() - timedelta(minutes=5)
            assert user.is_google_oauth_expired() is True
            
            # Test with expiry very close to now (within 5 minutes - should be considered expired)
            user.google_oauth_expires_at = datetime.utcnow() + timedelta(minutes=2)
            assert user.is_google_oauth_expired() is True  # Assuming 5-minute buffer
            
            # Test with expiry well in the future (not expired)
            user.google_oauth_expires_at = datetime.utcnow() + timedelta(hours=2)
            assert user.is_google_oauth_expired() is False
    
    def test_token_clearing_comprehensive(self, app, token_test_user):
        """Test comprehensive token clearing."""
        with app.app_context():
            user = token_test_user
            
            # Set up user with full token data
            token_data = {
                'token': 'ya29.a0ARrdaM-token_to_clear',
                'refresh_token': '1//04-refresh_token_to_clear',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['https://www.googleapis.com/auth/calendar'],
                'expires_in': 3600
            }
            user.set_google_oauth_tokens(token_data)
            
            # Verify tokens are set
            assert user.google_calendar_connected is True
            assert user.google_oauth_token is not None
            assert user.google_oauth_refresh_token is not None
            assert user.google_oauth_expires_at is not None
            
            # Clear tokens
            user.clear_google_oauth_tokens()
            
            # Verify all token-related fields are cleared
            assert user.google_calendar_connected is False
            assert user.google_oauth_token is None
            assert user.google_oauth_refresh_token is None
            assert user.google_oauth_expires_at is None
            
            # Verify get_google_oauth_tokens returns None
            assert user.get_google_oauth_tokens() is None