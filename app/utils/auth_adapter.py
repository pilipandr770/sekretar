"""Authentication adapter for database-agnostic authentication."""
from typing import Optional, Dict, Any
from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token
from app.models.user import User
import structlog

logger = structlog.get_logger()


class AuthenticationAdapter:
    """Database-agnostic authentication adapter."""
    
    def __init__(self):
        """Initialize the authentication adapter."""
        self.logger = logger.bind(component="auth_adapter")
    
    def authenticate_user(self, email: str, password: str, tenant_id: Optional[int] = None) -> Optional[User]:
        """Authenticate user by email and password.
        
        Args:
            email: User email address
            password: User password
            tenant_id: Optional tenant ID for multi-tenant authentication
            
        Returns:
            User object if authentication successful, None otherwise
        """
        try:
            # Validate input parameters
            if not email or not password:
                self.logger.warning(
                    "Authentication failed: missing credentials",
                    email=email if email else "missing",
                    password_provided=bool(password)
                )
                return None
            
            # Normalize email
            email = email.strip().lower()
            
            # Use the User model's authenticate method which is already database-agnostic
            user = User.authenticate(email, password, tenant_id)
            
            if user:
                self.logger.info(
                    "User authentication successful",
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    email=email
                )
                return user
            else:
                self.logger.warning(
                    "User authentication failed",
                    email=email,
                    tenant_id=tenant_id,
                    reason="invalid_credentials"
                )
                return None
                
        except Exception as e:
            self.logger.error(
                "Authentication error",
                email=email,
                tenant_id=tenant_id,
                error=str(e),
                exc_info=True
            )
            return None
    
    def generate_tokens(self, user: User) -> Dict[str, str]:
        """Generate JWT access and refresh tokens for user.
        
        Args:
            user: User object
            
        Returns:
            Dictionary containing access_token, refresh_token, and token_type
        """
        try:
            # Generate tokens using Flask-JWT-Extended
            access_token = create_access_token(identity=user)
            refresh_token = create_refresh_token(identity=user)
            
            self.logger.info(
                "JWT tokens generated",
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email
            )
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer'
            }
            
        except Exception as e:
            self.logger.error(
                "Token generation failed",
                user_id=user.id,
                tenant_id=user.tenant_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    def validate_token(self, token: str) -> Optional[User]:
        """Validate JWT token and return associated user.
        
        Args:
            token: JWT token string
            
        Returns:
            User object if token is valid, None otherwise
        """
        try:
            if not token:
                self.logger.warning("Token validation failed: empty token")
                return None
            
            # Decode token to get user identity
            decoded_token = decode_token(token)
            user_id = decoded_token.get('sub')
            
            if not user_id:
                self.logger.warning("Token validation failed: no subject")
                return None
            
            # Convert string ID to integer if needed
            if isinstance(user_id, str) and user_id.isdigit():
                user_id = int(user_id)
            elif not isinstance(user_id, int):
                self.logger.warning(
                    "Token validation failed: invalid user ID format",
                    user_id=user_id,
                    user_id_type=type(user_id)
                )
                return None
            
            # Use database-agnostic user lookup
            user = User.find_by_id(user_id)
            
            if user:
                self.logger.debug(
                    "Token validation successful",
                    user_id=user.id,
                    tenant_id=user.tenant_id
                )
                return user
            else:
                self.logger.warning(
                    "Token validation failed: user not found or inactive",
                    user_id=user_id
                )
                return None
                
        except Exception as e:
            self.logger.warning(
                "Token validation failed",
                error=str(e),
                token_preview=token[:20] + "..." if len(token) > 20 else token
            )
            return None
    
    def refresh_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """Generate new access token using refresh token.
        
        Args:
            refresh_token: JWT refresh token
            
        Returns:
            Dictionary with new access_token and token_type, or None if invalid
        """
        try:
            if not refresh_token:
                self.logger.warning("Refresh token validation failed: empty token")
                return None
            
            # Decode refresh token
            decoded_token = decode_token(refresh_token)
            user_id = decoded_token.get('sub')
            
            if not user_id:
                self.logger.warning("Refresh token validation failed: no subject")
                return None
            
            # Convert string ID to integer if needed
            if isinstance(user_id, str) and user_id.isdigit():
                user_id = int(user_id)
            elif not isinstance(user_id, int):
                self.logger.warning(
                    "Refresh token validation failed: invalid user ID format",
                    user_id=user_id,
                    user_id_type=type(user_id)
                )
                return None
            
            # Use database-agnostic user lookup
            user = User.find_by_id(user_id)
            
            if not user:
                self.logger.warning(
                    "Refresh token validation failed: user not found or inactive",
                    user_id=user_id
                )
                return None
            
            # Validate user status before generating new token
            validation_result = self.validate_user_status(user)
            if not validation_result['valid']:
                self.logger.warning(
                    "Refresh token validation failed: user status invalid",
                    user_id=user_id,
                    error_code=validation_result.get('error_code')
                )
                return None
            
            # Generate new access token
            access_token = create_access_token(identity=user)
            
            self.logger.info(
                "Access token refreshed",
                user_id=user.id,
                tenant_id=user.tenant_id
            )
            
            return {
                'access_token': access_token,
                'token_type': 'Bearer'
            }
            
        except Exception as e:
            self.logger.warning(
                "Token refresh failed",
                error=str(e),
                token_preview=refresh_token[:20] + "..." if len(refresh_token) > 20 else refresh_token
            )
            return None
    
    def validate_user_status(self, user: User) -> Dict[str, Any]:
        """Validate user and tenant status for authentication.
        
        Args:
            user: User object to validate
            
        Returns:
            Dictionary with validation result and error details if any
        """
        try:
            # Check if user is active
            if not user.is_active:
                return {
                    'valid': False,
                    'error_code': 'USER_DISABLED',
                    'message': 'User account is disabled'
                }
            
            # Check if tenant exists and is active
            if not user.tenant:
                return {
                    'valid': False,
                    'error_code': 'TENANT_NOT_FOUND',
                    'message': 'Organization not found'
                }
            
            if not user.tenant.is_active:
                return {
                    'valid': False,
                    'error_code': 'TENANT_DISABLED',
                    'message': 'Organization account is disabled'
                }
            
            # All validations passed
            return {
                'valid': True,
                'user': user,
                'tenant': user.tenant
            }
            
        except Exception as e:
            self.logger.error(
                "User status validation failed",
                user_id=user.id if user else None,
                error=str(e),
                exc_info=True
            )
            return {
                'valid': False,
                'error_code': 'VALIDATION_ERROR',
                'message': 'User validation failed'
            }
    
    def get_user_permissions(self, user: User) -> Dict[str, Any]:
        """Get user permissions and capabilities.
        
        Args:
            user: User object
            
        Returns:
            Dictionary with user permissions and role information
        """
        try:
            return {
                'role': user.role,
                'is_owner': user.is_owner,
                'is_manager': user.is_manager,
                'permissions': {
                    'can_manage_users': user.can_manage_users,
                    'can_access_billing': user.can_access_billing,
                    'can_manage_settings': user.can_manage_settings
                },
                'roles': [role.to_dict() for role in user.roles] if user.roles else [],
                'all_permissions': user.get_all_permissions()
            }
            
        except Exception as e:
            self.logger.error(
                "Failed to get user permissions",
                user_id=user.id,
                error=str(e),
                exc_info=True
            )
            return {
                'role': 'read_only',
                'is_owner': False,
                'is_manager': False,
                'permissions': {
                    'can_manage_users': False,
                    'can_access_billing': False,
                    'can_manage_settings': False
                },
                'roles': [],
                'all_permissions': []
            }


# Global authentication adapter instance
auth_adapter = AuthenticationAdapter()