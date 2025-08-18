"""OAuth authentication routes."""
from flask import request, redirect, session, url_for
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _

from app.auth import auth_bp
from app.services.google_oauth import GoogleOAuthService
from app.models.audit_log import AuditLog
from app.utils.decorators import log_api_call
from app.utils.response import (
    success_response, error_response, validation_error_response
)
from app.utils.exceptions import OAuthError, ExternalAPIError
import structlog

logger = structlog.get_logger()


@auth_bp.route('/oauth/google/connect', methods=['POST'])
@jwt_required()
@log_api_call('oauth_google_connect')
def oauth_google_connect():
    """Initiate Google OAuth flow for calendar access."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        oauth_service = GoogleOAuthService()
        
        if not oauth_service.is_configured():
            return error_response(
                error_code='CONFIGURATION_ERROR',
                message=_('Google OAuth is not configured'),
                status_code=503
            )
        
        # Generate authorization URL
        authorization_url = oauth_service.get_authorization_url(user.id)
        
        # Log OAuth initiation
        AuditLog.log_user_action(
            user=user,
            action='oauth_initiate',
            resource_type='google_calendar',
            metadata={'provider': 'google'}
        )
        
        logger.info("OAuth flow initiated", user_id=user.id)
        
        return success_response(
            message=_('OAuth authorization URL generated'),
            data={
                'authorization_url': authorization_url,
                'provider': 'google'
            }
        )
        
    except OAuthError as e:
        logger.error("OAuth initiation failed", error=str(e))
        return error_response(
            error_code='OAUTH_ERROR',
            message=str(e),
            status_code=400
        )
    except Exception as e:
        logger.error("OAuth initiation failed", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to initiate OAuth flow'),
            status_code=500
        )


@auth_bp.route('/oauth/google/callback', methods=['GET'])
@log_api_call('oauth_google_callback')
def oauth_google_callback():
    """Handle Google OAuth callback."""
    try:
        # Get authorization code and state from query parameters
        authorization_code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        if error:
            logger.warning("OAuth callback error", error=error)
            return redirect(f"{request.host_url}?oauth_error={error}")
        
        if not authorization_code:
            return error_response(
                error_code='OAUTH_ERROR',
                message=_('Authorization code not provided'),
                status_code=400
            )
        
        if not state:
            return error_response(
                error_code='OAUTH_ERROR',
                message=_('State parameter not provided'),
                status_code=400
            )
        
        oauth_service = GoogleOAuthService()
        
        # Handle the callback
        result = oauth_service.handle_callback(authorization_code, state)
        user = result['user']
        user_info = result['user_info']
        
        # Log successful OAuth connection
        AuditLog.log_user_action(
            user=user,
            action='oauth_connect',
            resource_type='google_calendar',
            metadata={
                'provider': 'google',
                'google_email': user_info.get('email'),
                'google_name': user_info.get('name')
            }
        )
        
        logger.info(
            "OAuth callback successful",
            user_id=user.id,
            google_email=user_info.get('email')
        )
        
        # Redirect to frontend with success
        frontend_url = request.host_url.rstrip('/')
        return redirect(f"{frontend_url}?oauth_success=true&provider=google")
        
    except OAuthError as e:
        logger.error("OAuth callback failed", error=str(e))
        frontend_url = request.host_url.rstrip('/')
        return redirect(f"{frontend_url}?oauth_error={str(e)}")
    except Exception as e:
        logger.error("OAuth callback failed", error=str(e), exc_info=True)
        frontend_url = request.host_url.rstrip('/')
        return redirect(f"{frontend_url}?oauth_error=internal_error")


@auth_bp.route('/oauth/google/status', methods=['GET'])
@jwt_required()
@log_api_call('oauth_google_status')
def oauth_google_status():
    """Get Google OAuth connection status."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        oauth_service = GoogleOAuthService()
        
        if not oauth_service.is_configured():
            return success_response(
                message=_('Google OAuth status retrieved'),
                data={
                    'connected': False,
                    'configured': False,
                    'error': 'Google OAuth not configured'
                }
            )
        
        # Test connection if user has tokens
        connection_status = {
            'connected': user.google_calendar_connected,
            'configured': True,
            'expires_at': user.google_oauth_expires_at.isoformat() if user.google_oauth_expires_at else None,
            'is_expired': user.is_google_oauth_expired() if user.google_calendar_connected else None
        }
        
        if user.google_calendar_connected:
            # Test the connection
            test_result = oauth_service.test_connection(user)
            connection_status.update(test_result)
        
        return success_response(
            message=_('Google OAuth status retrieved'),
            data=connection_status
        )
        
    except Exception as e:
        logger.error("Failed to get OAuth status", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to get OAuth status'),
            status_code=500
        )


@auth_bp.route('/oauth/google/disconnect', methods=['POST'])
@jwt_required()
@log_api_call('oauth_google_disconnect')
def oauth_google_disconnect():
    """Disconnect Google OAuth integration."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        if not user.google_calendar_connected:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Google Calendar is not connected'),
                status_code=400
            )
        
        oauth_service = GoogleOAuthService()
        success = oauth_service.disconnect_calendar(user)
        
        # Log disconnection
        AuditLog.log_user_action(
            user=user,
            action='oauth_disconnect',
            resource_type='google_calendar',
            metadata={'provider': 'google'}
        )
        
        if success:
            logger.info("OAuth disconnected successfully", user_id=user.id)
            return success_response(
                message=_('Google Calendar disconnected successfully')
            )
        else:
            return error_response(
                error_code='OAUTH_ERROR',
                message=_('Failed to disconnect Google Calendar'),
                status_code=500
            )
        
    except Exception as e:
        logger.error("OAuth disconnection failed", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to disconnect Google Calendar'),
            status_code=500
        )


@auth_bp.route('/oauth/google/refresh', methods=['POST'])
@jwt_required()
@log_api_call('oauth_google_refresh')
def oauth_google_refresh():
    """Refresh Google OAuth token."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        if not user.google_calendar_connected:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Google Calendar is not connected'),
                status_code=400
            )
        
        oauth_service = GoogleOAuthService()
        success = oauth_service.refresh_token(user)
        
        if success:
            # Log token refresh
            AuditLog.log_user_action(
                user=user,
                action='oauth_refresh',
                resource_type='google_calendar',
                metadata={'provider': 'google'}
            )
            
            logger.info("OAuth token refreshed", user_id=user.id)
            return success_response(
                message=_('Google OAuth token refreshed successfully'),
                data={
                    'expires_at': user.google_oauth_expires_at.isoformat() if user.google_oauth_expires_at else None
                }
            )
        else:
            return error_response(
                error_code='OAUTH_ERROR',
                message=_('Failed to refresh Google OAuth token'),
                status_code=400
            )
        
    except Exception as e:
        logger.error("OAuth token refresh failed", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to refresh OAuth token'),
            status_code=500
        )