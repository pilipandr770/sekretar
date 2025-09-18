"""Authentication routes with i18n support."""
from flask import request, session
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_current_user
from flask_babel import gettext as _
from app.auth import auth_bp
from app.models.tenant import Tenant
from app.models.user import User
from app.models.audit_log import AuditLog
from app.utils.decorators import require_json, log_api_call
from app.utils.response import (
    success_response, error_response, validation_error_response,
    unauthorized_response
)
from app.utils.validators import validate_email
from app.utils.i18n import set_user_language, get_available_languages
from app.utils.rate_limit_decorators import auth_rate_limit, api_rate_limit
import structlog

logger = structlog.get_logger()


@auth_bp.route('/register', methods=['POST'])
@auth_rate_limit()
@require_json(['email', 'password', 'organization_name'])
@log_api_call('register')
def register():
    """Register new tenant and owner user."""
    try:
        data = request.get_json()
        
        # Validate input
        email = data['email'].strip().lower()
        password = data['password']
        org_name = data['organization_name'].strip()
        
        if not validate_email(email):
            return validation_error_response({
                'email': [_('Invalid email address')]
            })
        
        if len(password) < 8:
            return validation_error_response({
                'password': [_('Password must be at least 8 characters')]
            })
        
        if len(org_name) < 2:
            return validation_error_response({
                'organization_name': [_('Organization name must be at least 2 characters')]
            })
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return error_response(
                error_code='CONFLICT_ERROR',
                message=_('User with this email already exists'),
                status_code=409
            )
        
        # Create tenant and owner
        tenant, owner = Tenant.create_with_owner(
            name=org_name,
            owner_email=email,
            owner_password=password,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            language=data.get('language', 'en')
        )
        
        # Set user language preference
        if 'language' in data and data['language'] in get_available_languages():
            set_user_language(data['language'])
            owner.language = data['language']
            owner.save()
        
        # Create access tokens
        access_token = create_access_token(identity=owner)
        refresh_token = create_refresh_token(identity=owner)
        
        # Log registration
        AuditLog.log_action(
            action='register',
            resource_type='user',
            tenant_id=tenant.id,
            user_id=owner.id,
            new_values={
                'email': email,
                'organization': org_name
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        logger.info(
            "User registered successfully",
            user_id=owner.id,
            tenant_id=tenant.id,
            email=email,
            organization=org_name
        )
        
        return success_response(
            message=_('Registration successful. Welcome to %(app_name)s!', app_name='AI Secretary'),
            data={
                'user': owner.to_dict(),
                'tenant': tenant.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer'
            },
            status_code=201
        )
        
    except Exception as e:
        logger.error("Registration failed", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Registration failed. Please try again.'),
            status_code=500
        )


@auth_bp.route('/login', methods=['POST'])
@auth_rate_limit()
@require_json(['email', 'password'])
@log_api_call('login')
def login():
    """Authenticate user and return tokens."""
    try:
        data = request.get_json()
        
        email = data['email'].strip().lower()
        password = data['password']
        
        if not validate_email(email):
            return validation_error_response({
                'email': [_('Invalid email address')]
            })
        
        # Use authentication adapter for database-agnostic authentication
        from app.utils.auth_adapter import auth_adapter
        
        user = auth_adapter.authenticate_user(email, password)
        if not user:
            # Try to log failed login attempt, but don't fail if we can't
            try:
                # For failed logins, we might not have a tenant_id, so we'll skip audit logging
                # This is acceptable since we're logging the failure in the application logs
                logger.warning(
                    "Failed login attempt",
                    email=email,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    reason='invalid_credentials'
                )
            except Exception as audit_error:
                logger.warning(f"Failed to log audit entry: {audit_error}")
            
            return unauthorized_response(_('Invalid email or password'))
        
        # Validate user and tenant status
        validation_result = auth_adapter.validate_user_status(user)
        if not validation_result['valid']:
            return error_response(
                error_code=validation_result['error_code'],
                message=_(validation_result['message']),
                status_code=401
            )
        
        # Set user language preference
        if user.language:
            set_user_language(user.language)
        
        try:
            # Generate JWT tokens using authentication adapter
            tokens = auth_adapter.generate_tokens(user)
            
            # Update last login
            user.update_last_login()
            
            # Log successful login
            AuditLog.log_login(
                user=user,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                success=True
            )
            
            logger.info(
                "User logged in successfully",
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=email
            )
            
            # Get user permissions
            permissions = auth_adapter.get_user_permissions(user)
            
            return success_response(
                message=_('Login successful. Welcome back!'),
                data={
                    'user': user.to_dict(),
                    'tenant': user.tenant.to_dict(),
                    'permissions': permissions,
                    **tokens
                }
            )
            
        except Exception as token_error:
            logger.error(
                "Token generation failed during login",
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=email,
                error=str(token_error),
                exc_info=True
            )
            return error_response(
                error_code='TOKEN_GENERATION_ERROR',
                message=_('Login successful but token generation failed. Please try again.'),
                status_code=500
            )
        
    except Exception as e:
        logger.error("Login failed", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Login failed. Please try again.'),
            status_code=500
        )


@auth_bp.route('/logout', methods=['POST'])
@api_rate_limit()
@jwt_required()
@log_api_call('logout')
def logout():
    """Logout user."""
    try:
        user = get_current_user()
        
        if user:
            # Log logout
            AuditLog.log_logout(
                user=user,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            
            logger.info("User logged out", user_id=user.id, tenant_id=user.tenant_id)
        
        # Clear session
        session.clear()
        
        return success_response(
            message=_('Logged out successfully')
        )
        
    except Exception as e:
        logger.error("Logout failed", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Logout failed'),
            status_code=500
        )


@auth_bp.route('/me', methods=['GET'])
@api_rate_limit()
@jwt_required()
@log_api_call('get_profile')
def get_profile():
    """Get current user profile."""
    try:
        user = get_current_user()
        
        if not user:
            return unauthorized_response(_('Authentication required'))
        
        # Get comprehensive user permissions using authentication adapter
        from app.utils.auth_adapter import auth_adapter
        permissions = auth_adapter.get_user_permissions(user)
        
        return success_response(
            message=_('Profile retrieved successfully'),
            data={
                'user': user.to_dict(),
                'tenant': user.tenant.to_dict() if user.tenant else None,
                'permissions': permissions
            }
        )
        
    except Exception as e:
        logger.error("Failed to get profile", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve profile'),
            status_code=500
        )


@auth_bp.route('/me', methods=['PUT'])
@api_rate_limit()
@jwt_required()
@require_json()
@log_api_call('update_profile')
def update_profile():
    """Update current user profile."""
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not user:
            return unauthorized_response(_('Authentication required'))
        
        # Update allowed fields
        updatable_fields = [
            'first_name', 'last_name', 'timezone', 'language',
            'notification_preferences'
        ]
        
        old_values = {}
        new_values = {}
        
        for field in updatable_fields:
            if field in data:
                old_values[field] = getattr(user, field)
                new_values[field] = data[field]
                setattr(user, field, data[field])
        
        # Validate language
        if 'language' in data:
            if data['language'] not in get_available_languages():
                return validation_error_response({
                    'language': [_('Invalid language code')]
                })
            
            # Update session language
            set_user_language(data['language'])
        
        user.save()
        
        # Log profile update
        AuditLog.log_user_action(
            user=user,
            action='update',
            resource_type='profile',
            resource_id=user.id,
            old_values=old_values,
            new_values=new_values
        )
        
        logger.info("Profile updated", user_id=user.id)
        
        return success_response(
            message=_('Profile updated successfully'),
            data=user.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to update profile", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update profile'),
            status_code=500
        )


@auth_bp.route('/refresh', methods=['POST'])
@auth_rate_limit()
@jwt_required(refresh=True)
@log_api_call('refresh_token')
def refresh():
    """Refresh access token."""
    try:
        user = get_current_user()
        
        if not user:
            return unauthorized_response(_('Authentication required'))
        
        # Validate user status using authentication adapter
        from app.utils.auth_adapter import auth_adapter
        validation_result = auth_adapter.validate_user_status(user)
        
        if not validation_result['valid']:
            return error_response(
                error_code=validation_result['error_code'],
                message=_(validation_result['message']),
                status_code=401
            )
        
        # Create new access token
        access_token = create_access_token(identity=user)
        
        return success_response(
            message=_('Token refreshed successfully'),
            data={
                'access_token': access_token,
                'token_type': 'Bearer'
            }
        )
        
    except Exception as e:
        logger.error("Token refresh failed", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Token refresh failed'),
            status_code=500
        )