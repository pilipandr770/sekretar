"""JWT handlers and utilities."""
from flask import jsonify, current_app
from flask_jwt_extended import get_jwt_identity, get_jwt
import structlog

logger = structlog.get_logger()


def register_jwt_handlers(jwt_manager):
    """Register JWT handlers."""
    
    @jwt_manager.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        """Handle expired tokens."""
        logger.warning("Expired token used", user_id=jwt_payload.get('sub'))
        return jsonify({
            'error': {
                'code': 'TOKEN_EXPIRED',
                'message': 'Token has expired'
            }
        }), 401
    
    @jwt_manager.invalid_token_loader
    def invalid_token_callback(error):
        """Handle invalid tokens."""
        logger.warning("Invalid token used", error=str(error))
        return jsonify({
            'error': {
                'code': 'INVALID_TOKEN',
                'message': 'Invalid token'
            }
        }), 401
    
    @jwt_manager.unauthorized_loader
    def missing_token_callback(error):
        """Handle missing tokens."""
        logger.warning("Missing token", error=str(error))
        return jsonify({
            'error': {
                'code': 'TOKEN_REQUIRED',
                'message': 'Authentication token required'
            }
        }), 401
    
    @jwt_manager.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        """Handle non-fresh tokens."""
        logger.warning("Non-fresh token used", user_id=jwt_payload.get('sub'))
        return jsonify({
            'error': {
                'code': 'FRESH_TOKEN_REQUIRED',
                'message': 'Fresh token required'
            }
        }), 401
    
    @jwt_manager.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        """Handle revoked tokens."""
        logger.warning("Revoked token used", user_id=jwt_payload.get('sub'))
        return jsonify({
            'error': {
                'code': 'TOKEN_REVOKED',
                'message': 'Token has been revoked'
            }
        }), 401
    
    @jwt_manager.user_identity_loader
    def user_identity_lookup(user):
        """Return user identity for JWT."""
        return str(user.id)  # Ensure identity is always a string
    
    @jwt_manager.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """Load user from JWT using fixed authentication adapter."""
        try:
            from app.utils.auth_adapter_fixed import get_fixed_auth_adapter
            from app.models.user import User
            
            auth_adapter = get_fixed_auth_adapter()
            identity = jwt_data["sub"]
            
            # Validate identity format
            if isinstance(identity, str) and identity.isdigit():
                identity = int(identity)
            elif not isinstance(identity, int):
                logger.warning("Invalid JWT subject type", subject=identity, type=type(identity))
                return None
            
            # Use database-agnostic user lookup with fallback
            try:
                user = User.query.get(identity)
            except Exception as db_error:
                logger.warning("Database lookup failed, trying session fallback", error=str(db_error))
                user = auth_adapter.get_user_from_session()
                if user and user.id == identity:
                    return user
                return None
            
            if user:
                # Validate user and tenant status
                validation_result = auth_adapter.validate_user_status(user)
                if validation_result['valid']:
                    return user
                else:
                    logger.warning(
                        "User lookup failed validation",
                        user_id=identity,
                        error_code=validation_result.get('error_code'),
                        message=validation_result.get('message')
                    )
                    return None
            else:
                logger.warning("User not found", user_id=identity)
                # Try session fallback
                session_user = auth_adapter.get_user_from_session()
                if session_user and session_user.id == identity:
                    return session_user
                return None
                
        except Exception as e:
            logger.warning("Failed to load user from JWT", error=str(e), jwt_data=jwt_data)
            # Try session fallback as last resort
            try:
                from app.utils.auth_adapter_fixed import get_fixed_auth_adapter
                auth_adapter = get_fixed_auth_adapter()
                return auth_adapter.get_user_from_session()
            except Exception:
                return None
    
    @jwt_manager.additional_claims_loader
    def add_claims_to_jwt(user):
        """Add additional claims to JWT."""
        return {
            'tenant_id': user.tenant_id,
            'role': user.role,
            'is_active': user.is_active
        }
    
    @jwt_manager.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        """Check if token is revoked."""
        # TODO: Implement token blacklist using Redis
        # For now, return False (no tokens are revoked)
        return False