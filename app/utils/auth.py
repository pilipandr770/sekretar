"""Authentication and authorization utilities."""
from functools import wraps
from flask import request, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from app.utils.response import error_response, unauthorized_response, forbidden_response


def require_auth(f):
    """Decorator to require authentication."""
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return unauthorized_response(_('Authentication required'))
        
        # Set current user in request context
        request.current_user = user
        g.user_id = user.id
        g.tenant_id = user.tenant_id
        
        return f(*args, **kwargs)
    return decorated_function


def require_permission(permission):
    """Decorator to require specific permission."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = getattr(request, 'current_user', None)
            if not user:
                return unauthorized_response(_('Authentication required'))
            
            if not user.has_permission(permission):
                return forbidden_response(
                    _('Permission required: %(permission)s', permission=permission)
                )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_role(*allowed_roles):
    """Decorator to require specific user roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = getattr(request, 'current_user', None)
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


def require_tenant():
    """Decorator to require tenant context."""
    def decorator(f):
        @wraps(f)
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


def require_active_subscription():
    """Decorator to require active subscription."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = getattr(request, 'current_user', None)
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


def get_current_tenant():
    """Get current tenant from request context."""
    user = getattr(request, 'current_user', None)
    if user and user.tenant:
        return user.tenant
    
    # Try to get from JWT
    try:
        user = get_current_user()
        if user and user.tenant:
            return user.tenant
    except:
        pass
    
    return None