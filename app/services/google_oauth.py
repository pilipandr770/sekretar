"""Google OAuth service for calendar integration."""
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from flask import current_app, session, url_for
import structlog

from app.models.user import User
from app.utils.exceptions import OAuthError, ExternalAPIError

logger = structlog.get_logger()


class GoogleOAuthService:
    """Service for handling Google OAuth authentication and calendar access."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile'
    ]
    
    def __init__(self):
        """Initialize Google OAuth service."""
        self.client_id = current_app.config.get('GOOGLE_CLIENT_ID')
        self.client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = current_app.config.get('GOOGLE_REDIRECT_URI')
        
        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            logger.warning("Google OAuth not configured properly")
    
    def is_configured(self) -> bool:
        """Check if Google OAuth is properly configured."""
        return all([self.client_id, self.client_secret, self.redirect_uri])
    
    def get_authorization_url(self, user_id: int, state: Optional[str] = None) -> str:
        """Generate Google OAuth authorization URL."""
        if not self.is_configured():
            raise OAuthError("Google OAuth not configured")
        
        # Generate state parameter for CSRF protection
        if not state:
            state = secrets.token_urlsafe(32)
        
        # Store state and user_id in session for verification
        session['oauth_state'] = state
        session['oauth_user_id'] = user_id
        
        # Create OAuth flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.SCOPES
        )
        flow.redirect_uri = self.redirect_uri
        
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'  # Force consent to get refresh token
        )
        
        logger.info("Generated OAuth authorization URL", user_id=user_id)
        return authorization_url
    
    def handle_callback(self, authorization_code: str, state: str) -> Dict[str, Any]:
        """Handle OAuth callback and exchange code for tokens."""
        if not self.is_configured():
            raise OAuthError("Google OAuth not configured")
        
        # Verify state parameter
        session_state = session.get('oauth_state')
        session_user_id = session.get('oauth_user_id')
        
        if not session_state or session_state != state:
            raise OAuthError("Invalid state parameter")
        
        if not session_user_id:
            raise OAuthError("No user ID in session")
        
        try:
            # Create OAuth flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=self.SCOPES
            )
            flow.redirect_uri = self.redirect_uri
            
            # Exchange authorization code for tokens
            flow.fetch_token(code=authorization_code)
            
            credentials = flow.credentials
            token_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
                'expires_in': 3600  # Default to 1 hour
            }
            
            if credentials.expiry:
                expires_in = int((credentials.expiry - datetime.utcnow()).total_seconds())
                token_data['expires_in'] = max(expires_in, 0)
            
            # Get user info from Google
            user_info = self._get_user_info(credentials)
            
            # Store tokens in user record
            user = User.query.get(session_user_id)
            if not user:
                raise OAuthError("User not found")
            
            user.set_google_oauth_tokens(token_data)
            
            # Clear session data
            session.pop('oauth_state', None)
            session.pop('oauth_user_id', None)
            
            logger.info(
                "OAuth callback handled successfully",
                user_id=user.id,
                google_email=user_info.get('email')
            )
            
            return {
                'user': user,
                'user_info': user_info,
                'token_data': token_data
            }
            
        except Exception as e:
            logger.error("OAuth callback failed", error=str(e), exc_info=True)
            # Clear session data on error
            session.pop('oauth_state', None)
            session.pop('oauth_user_id', None)
            raise OAuthError(f"OAuth callback failed: {str(e)}")
    
    def refresh_token(self, user: User) -> bool:
        """Refresh Google OAuth token for user."""
        if not user.google_oauth_refresh_token:
            logger.warning("No refresh token available", user_id=user.id)
            return False
        
        try:
            # Create credentials from stored tokens
            token_data = user.get_google_oauth_tokens()
            if not token_data:
                logger.warning("No OAuth tokens found", user_id=user.id)
                return False
            
            credentials = Credentials(
                token=token_data.get('token'),
                refresh_token=user.google_oauth_refresh_token,
                token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=token_data.get('scopes', self.SCOPES)
            )
            
            # Refresh the token
            credentials.refresh(Request())
            
            # Update stored tokens
            new_token_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token or user.google_oauth_refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
                'expires_in': 3600
            }
            
            if credentials.expiry:
                expires_in = int((credentials.expiry - datetime.utcnow()).total_seconds())
                new_token_data['expires_in'] = max(expires_in, 0)
            
            user.set_google_oauth_tokens(new_token_data)
            
            logger.info("OAuth token refreshed successfully", user_id=user.id)
            return True
            
        except Exception as e:
            logger.error("Token refresh failed", user_id=user.id, error=str(e))
            # Clear invalid tokens
            user.clear_google_oauth_tokens()
            return False
    
    def get_valid_credentials(self, user: User) -> Optional[Credentials]:
        """Get valid Google credentials for user, refreshing if necessary."""
        if not user.google_calendar_connected:
            return None
        
        token_data = user.get_google_oauth_tokens()
        if not token_data:
            return None
        
        # Check if token is expired and refresh if needed
        if user.is_google_oauth_expired():
            if not self.refresh_token(user):
                return None
            # Get updated token data
            token_data = user.get_google_oauth_tokens()
        
        try:
            credentials = Credentials(
                token=token_data.get('token'),
                refresh_token=user.google_oauth_refresh_token,
                token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=token_data.get('scopes', self.SCOPES)
            )
            
            return credentials
            
        except Exception as e:
            logger.error("Failed to create credentials", user_id=user.id, error=str(e))
            return None
    
    def disconnect_calendar(self, user: User) -> bool:
        """Disconnect Google Calendar for user."""
        try:
            # Revoke the token with Google
            token_data = user.get_google_oauth_tokens()
            if token_data and token_data.get('token'):
                revoke_url = f"https://oauth2.googleapis.com/revoke?token={token_data['token']}"
                response = requests.post(revoke_url)
                if response.status_code not in [200, 400]:  # 400 is OK if token already invalid
                    logger.warning(
                        "Failed to revoke token with Google",
                        user_id=user.id,
                        status_code=response.status_code
                    )
            
            # Clear stored tokens
            user.clear_google_oauth_tokens()
            
            logger.info("Google Calendar disconnected", user_id=user.id)
            return True
            
        except Exception as e:
            logger.error("Failed to disconnect calendar", user_id=user.id, error=str(e))
            # Clear tokens anyway
            user.clear_google_oauth_tokens()
            return False
    
    def get_calendar_service(self, user: User):
        """Get Google Calendar service for user."""
        credentials = self.get_valid_credentials(user)
        if not credentials:
            raise OAuthError("No valid Google credentials")
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            return service
        except Exception as e:
            logger.error("Failed to build calendar service", user_id=user.id, error=str(e))
            raise ExternalAPIError(f"Failed to connect to Google Calendar: {str(e)}")
    
    def _get_user_info(self, credentials: Credentials) -> Dict[str, Any]:
        """Get user info from Google using credentials."""
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            return user_info
        except Exception as e:
            logger.error("Failed to get user info from Google", error=str(e))
            return {}
    
    def test_connection(self, user: User) -> Dict[str, Any]:
        """Test Google Calendar connection for user."""
        try:
            service = self.get_calendar_service(user)
            
            # Try to get calendar list
            calendars_result = service.calendarList().list().execute()
            calendars = calendars_result.get('items', [])
            
            return {
                'connected': True,
                'calendar_count': len(calendars),
                'primary_calendar': next(
                    (cal for cal in calendars if cal.get('primary')), 
                    None
                )
            }
            
        except Exception as e:
            logger.error("Calendar connection test failed", user_id=user.id, error=str(e))
            return {
                'connected': False,
                'error': str(e)
            }