"""Decorators with i18n support."""
from functools import wraps
from flask import request, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from app.utils.response import error_response, unauthorized_response, forbidden_response
from app.utils.validators import validate_json_structure, validate_required_fields
import structlog

logger = structlog.get_logger()


def require_json(required_fields=None):
    """Decorator to require JSON input with optional field validation."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return error_response(
                    error_code='VALIDATION_ERROR',
                    message=_('Request must be JSON'),
                    status_code=400
                )
            
            data = request.get_json()
            if data is None:
                return error_response(
                    error_code='VALIDATION_ERROR',
                    message=_('Invalid JSON data'),
                    status_code=400
                )
            
            # Validate required fields
            if required_fields:
                try:
                    validate_required_fields(data, required_fields)
                except Exception as e:
                    return error_response(
                        error_code='VALIDATION_ERROR',
                        message=str(e),
                        status_code=400
                    )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_tenant():
    """Decorator to require tenant context."""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'tenant_id') or not g.tenant_id:
                return error_response(
                    error_code='AUTHORIZATION_ERROR',
                    message=_('Tenant context required'),
                    status_code=403
                )
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_role(*allowed_roles):
    """Decorator to require specific user roles."""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return unauthorized_response(_('Authentication required'))
            
            if user.role not in allowed_roles:
                return forbidden_response(
                    _('Insufficient permissions. Required roles: %(roles)s', 
                      roles=', '.join(allowed_roles))
                )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_permission(permission):
    """Decorator to require specific permission."""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return unauthorized_response(_('Authentication required'))
            
            if not user.has_permission(permission):
                return forbidden_response(
                    _('Permission required: %(permission)s', permission=permission)
                )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_active_subscription():
    """Decorator to require active subscription."""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user or not user.tenant:
                return unauthorized_response(_('Authentication required'))
            
            tenant = user.tenant
            
            # Check if trial expired
            if tenant.subscription_status == 'trial' and tenant.is_trial_expired():
                return error_response(
                    error_code='SUBSCRIPTION_REQUIRED',
                    message=_('Trial period has expired. Please upgrade your subscription.'),
                    status_code=402
                )
            
            # Check if subscription is active
            if tenant.subscription_status in ['suspended', 'cancelled']:
                return error_response(
                    error_code='SUBSCRIPTION_REQUIRED',
                    message=_('Active subscription required'),
                    status_code=402
                )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_feature_access(feature_name):
    """Decorator to require access to specific feature."""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user or not user.tenant:
                return unauthorized_response(_('Authentication required'))
            
            tenant = user.tenant
            
            if not tenant.can_access_feature(feature_name):
                if tenant.subscription_status == 'trial' and tenant.is_trial_expired():
                    message = _('Trial period has expired. Please upgrade to access this feature.')
                else:
                    message = _('This feature is not available in your current plan.')
                
                return error_response(
                    error_code='FEATURE_NOT_AVAILABLE',
                    message=message,
                    status_code=402
                )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_api_call(operation=None):
    """Decorator to log API calls."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            operation_name = operation or f.__name__
            
            logger.info(
                "API call started",
                operation=operation_name,
                method=request.method,
                path=request.path,
                user_id=getattr(g, 'user_id', None),
                tenant_id=getattr(g, 'tenant_id', None),
                language=getattr(g, 'language', 'unknown')
            )
            
            try:
                result = f(*args, **kwargs)
                
                logger.info(
                    "API call completed",
                    operation=operation_name,
                    user_id=getattr(g, 'user_id', None),
                    tenant_id=getattr(g, 'tenant_id', None)
                )
                
                return result
                
            except Exception as e:
                logger.error(
                    "API call failed",
                    operation=operation_name,
                    error=str(e),
                    user_id=getattr(g, 'user_id', None),
                    tenant_id=getattr(g, 'tenant_id', None),
                    exc_info=True
                )
                raise
                
        return decorated_function
    return decorator


def validate_pagination():
    """Decorator to validate pagination parameters."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                page = int(request.args.get('page', 1))
                per_page = int(request.args.get('per_page', 20))
                
                if page < 1:
                    return error_response(
                        error_code='VALIDATION_ERROR',
                        message=_('Page number must be positive'),
                        status_code=400
                    )
                
                if per_page < 1 or per_page > 100:
                    return error_response(
                        error_code='VALIDATION_ERROR',
                        message=_('Per page value must be between 1 and 100'),
                        status_code=400
                    )
                
                # Add to request context
                g.page = page
                g.per_page = per_page
                
                return f(*args, **kwargs)
                
            except ValueError:
                return error_response(
                    error_code='VALIDATION_ERROR',
                    message=_('Invalid pagination parameters'),
                    status_code=400
                )
                
        return decorated_function
    return decorator


def rate_limit(max_requests=100, window=3600):
    """Decorator for rate limiting (placeholder - implement with Redis)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # TODO: Implement Redis-based rate limiting
            # For now, just pass through
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def audit_log(action, resource_type):
    """Decorator to automatically create audit logs."""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return unauthorized_response(_('Authentication required'))
            
            # Execute the function
            result = f(*args, **kwargs)
            
            # Create audit log entry
            try:
                from app.models.audit_log import AuditLog
                
                # Extract resource ID from kwargs or result
                resource_id = kwargs.get('id') or kwargs.get('resource_id')
                if hasattr(result, 'get_json') and result.get_json():
                    data = result.get_json()
                    if isinstance(data, dict) and 'data' in data and 'id' in data['data']:
                        resource_id = data['data']['id']
                
                AuditLog.log_user_action(
                    user=user,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    request_context={
                        'ip_address': request.remote_addr,
                        'user_agent': request.headers.get('User-Agent'),
                        'request_id': getattr(g, 'request_id', None)
                    }
                )
                
            except Exception as e:
                logger.error("Failed to create audit log", error=str(e))
                # Don't fail the request if audit logging fails
            
            return result
            
        return decorated_function
    return decorator