"""
Fixed authentication adapter with improved error handling and session management.
"""
import logging
from typing import Optional, Dict, Any, List
from flask import current_app, session
from flask_jwt_extended import create_access_token, create_refresh_token
from werkzeug.security import check_password_hash
import structlog

logger = structlog.get_logger()


class FixedAuthAdapter:
    """Fixed authentication adapter with improved reliability."""
    
    def __init__(self):
        self.logger = logger
    
    def authenticate_user(self, email: str, password: str) -> Optional[Any]:
        """
        Authenticate user with improved error handling.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            User object if authentication successful, None otherwise
        """
        try:
            from app.models.user import User
            
            # Find user by email
            user = User.query.filter_by(email=email).first()
            
            if not user:
                self.logger.warning("Authentication failed: user not found", email=email)
                return None
            
            # Check password
            if not user.check_password(password):
                self.logger.warning("Authentication failed: invalid password", email=email, user_id=user.id)
                return None
            
            self.logger.info("User authenticated successfully", email=email, user_id=user.id)
            return user
            
        except Exception as e:
            self.logger.error("Authentication error", email=email, error=str(e), exc_info=True)
            return None
    
    def validate_user_status(self, user: Any) -> Dict[str, Any]:
        """
        Validate user and tenant status with improved checks.
        
        Args:
            user: User object
            
        Returns:
            Dictionary with validation result
        """
        try:
            # Check if user is active
            if not user.is_active:
                return {
                    'valid': False,
                    'error_code': 'USER_INACTIVE',
                    'message': 'User account is inactive'
                }
            
            # Check if user has a tenant (if required)
            if hasattr(user, 'tenant_id') and user.tenant_id:
                # Try to load tenant
                try:
                    tenant = user.tenant
                    if not tenant:
                        return {
                            'valid': False,
                            'error_code': 'TENANT_NOT_FOUND',
                            'message': 'User tenant not found'
                        }
                    
                    # Check tenant status
                    if hasattr(tenant, 'is_active') and not tenant.is_active:
                        return {
                            'valid': False,
                            'error_code': 'TENANT_INACTIVE',
                            'message': 'Organization account is inactive'
                        }
                        
                except Exception as tenant_error:
                    self.logger.warning("Tenant validation failed", user_id=user.id, error=str(tenant_error))
                    # Continue without tenant validation if there's an error
            
            return {
                'valid': True,
                'error_code': None,
                'message': 'User validation successful'
            }
            
        except Exception as e:
            self.logger.error("User validation error", user_id=getattr(user, 'id', 'unknown'), error=str(e))
            return {
                'valid': False,
                'error_code': 'VALIDATION_ERROR',
                'message': 'User validation failed'
            }
    
    def generate_tokens(self, user: Any) -> Dict[str, str]:
        """
        Generate JWT tokens with improved configuration.
        
        Args:
            user: User object
            
        Returns:
            Dictionary with access and refresh tokens
        """
        try:
            # Create additional claims
            additional_claims = {
                'tenant_id': getattr(user, 'tenant_id', None),
                'role': getattr(user, 'role', 'user'),
                'email': getattr(user, 'email', ''),
                'is_active': getattr(user, 'is_active', True)
            }
            
            # Generate tokens
            access_token = create_access_token(
                identity=user,
                additional_claims=additional_claims
            )
            
            refresh_token = create_refresh_token(
                identity=user,
                additional_claims=additional_claims
            )
            
            # Store user info in session for fallback
            session['user_id'] = user.id
            session['tenant_id'] = getattr(user, 'tenant_id', None)
            session['email'] = getattr(user, 'email', '')
            
            self.logger.info("Tokens generated successfully", user_id=user.id)
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer'
            }
            
        except Exception as e:
            self.logger.error("Token generation failed", user_id=getattr(user, 'id', 'unknown'), error=str(e))
            raise
    
    def get_user_permissions(self, user: Any) -> List[str]:
        """
        Get user permissions with fallback handling.
        
        Args:
            user: User object
            
        Returns:
            List of user permissions
        """
        try:
            permissions = []
            
            # Basic permissions for all authenticated users
            permissions.extend([
                'read_profile',
                'update_profile',
                'read_dashboard'
            ])
            
            # Role-based permissions
            user_role = getattr(user, 'role', 'user')
            
            if user_role == 'admin':
                permissions.extend([
                    'manage_users',
                    'manage_tenant',
                    'read_audit_logs',
                    'manage_settings'
                ])
            elif user_role == 'owner':
                permissions.extend([
                    'manage_users',
                    'manage_tenant',
                    'read_audit_logs'
                ])
            elif user_role == 'manager':
                permissions.extend([
                    'read_users',
                    'manage_projects'
                ])
            
            # Tenant-specific permissions
            if hasattr(user, 'tenant_id') and user.tenant_id:
                permissions.extend([
                    'read_tenant_data',
                    'create_tenant_data'
                ])
            
            return list(set(permissions))  # Remove duplicates
            
        except Exception as e:
            self.logger.error("Failed to get user permissions", user_id=getattr(user, 'id', 'unknown'), error=str(e))
            # Return basic permissions as fallback
            return ['read_profile', 'read_dashboard']
    
    def refresh_user_token(self, user: Any) -> Dict[str, str]:
        """
        Refresh user access token.
        
        Args:
            user: User object
            
        Returns:
            Dictionary with new access token
        """
        try:
            # Validate user status before refreshing
            validation_result = self.validate_user_status(user)
            if not validation_result['valid']:
                raise Exception(f"User validation failed: {validation_result['message']}")
            
            # Generate new access token
            additional_claims = {
                'tenant_id': getattr(user, 'tenant_id', None),
                'role': getattr(user, 'role', 'user'),
                'email': getattr(user, 'email', ''),
                'is_active': getattr(user, 'is_active', True)
            }
            
            access_token = create_access_token(
                identity=user,
                additional_claims=additional_claims
            )
            
            self.logger.info("Token refreshed successfully", user_id=user.id)
            
            return {
                'access_token': access_token,
                'token_type': 'Bearer'
            }
            
        except Exception as e:
            self.logger.error("Token refresh failed", user_id=getattr(user, 'id', 'unknown'), error=str(e))
            raise
    
    def logout_user(self, user: Any) -> bool:
        """
        Logout user and clean up session.
        
        Args:
            user: User object
            
        Returns:
            True if logout successful
        """
        try:
            # Clear session data
            session.clear()
            
            # TODO: Add token to blacklist when Redis is available
            # For now, just log the logout
            self.logger.info("User logged out successfully", user_id=getattr(user, 'id', 'unknown'))
            
            return True
            
        except Exception as e:
            self.logger.error("Logout failed", user_id=getattr(user, 'id', 'unknown'), error=str(e))
            return False
    
    def get_user_from_session(self) -> Optional[Any]:
        """
        Get user from session as fallback when JWT fails.
        
        Returns:
            User object if found in session, None otherwise
        """
        try:
            user_id = session.get('user_id')
            if not user_id:
                return None
            
            from app.models.user import User
            user = User.query.get(user_id)
            
            if user:
                # Validate user status
                validation_result = self.validate_user_status(user)
                if validation_result['valid']:
                    return user
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to get user from session", error=str(e))
            return None


# Global instance
fixed_auth_adapter = FixedAuthAdapter()


def get_fixed_auth_adapter():
    """Get the fixed authentication adapter instance."""
    return fixed_auth_adapter