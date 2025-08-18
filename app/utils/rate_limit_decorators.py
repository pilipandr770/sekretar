"""Rate limiting decorators for API endpoints."""
from functools import wraps
from flask import request, g, current_app, jsonify
from typing import List, Optional, Callable
import structlog

logger = structlog.get_logger()


def rate_limit(
    limits: Optional[List[str]] = None,
    per_tenant: bool = True,
    per_user: bool = True,
    key_func: Optional[Callable] = None
):
    """
    Rate limiting decorator with tenant and user-specific limits.
    
    Args:
        limits: List of rate limit strings (e.g., ["100 per hour", "10 per minute"])
        per_tenant: Apply tenant-specific rate limits
        per_user: Apply user-specific rate limits
        key_func: Custom key function for rate limiting
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip rate limiting in testing
            if current_app.config.get('TESTING'):
                return f(*args, **kwargs)
            
            # Get rate limit manager
            rate_limit_manager = current_app.extensions.get('rate_limit_manager')
            if not rate_limit_manager:
                logger.warning("Rate limit manager not initialized")
                return f(*args, **kwargs)
            
            endpoint = request.endpoint or request.path
            
            # Check tenant rate limits
            if per_tenant and hasattr(g, 'tenant_id') and g.tenant_id:
                tenant_result = rate_limit_manager.check_tenant_rate_limit(g.tenant_id, endpoint)
                if not tenant_result['allowed']:
                    return _rate_limit_exceeded_response(tenant_result, 'tenant')
            
            # Check user rate limits
            if per_user and hasattr(g, 'user_id') and g.user_id:
                user_result = rate_limit_manager.check_user_rate_limit(g.user_id, endpoint)
                if not user_result['allowed']:
                    return _rate_limit_exceeded_response(user_result, 'user')
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def auth_rate_limit():
    """Rate limiting decorator specifically for authentication endpoints."""
    return rate_limit(
        limits=["10 per minute", "50 per hour"],
        per_tenant=False,
        per_user=False
    )


def api_rate_limit(category: str = None):
    """Rate limiting decorator for API endpoints with category-specific limits."""
    from app.utils.rate_limiter import RateLimitConfig
    
    limits = None
    if category:
        limits = RateLimitConfig.API_LIMITS.get(category, RateLimitConfig.DEFAULT_LIMITS)
    
    return rate_limit(limits=limits, per_tenant=True, per_user=True)


def admin_rate_limit():
    """Rate limiting decorator for admin endpoints."""
    return rate_limit(
        limits=["200 per hour", "20 per minute"],
        per_tenant=True,
        per_user=True
    )


def _rate_limit_exceeded_response(rate_limit_result: dict, limit_type: str):
    """Generate rate limit exceeded response."""
    from flask_babel import gettext as _
    
    response = jsonify({
        'error': {
            'code': 'RATE_LIMIT_EXCEEDED',
            'message': _('Rate limit exceeded. Please try again later.'),
            'details': {
                'limit_type': limit_type,
                'limit': rate_limit_result['limit'],
                'remaining': rate_limit_result['remaining'],
                'reset_time': rate_limit_result['reset_time']
            }
        }
    })
    
    response.status_code = 429
    
    # Add rate limit headers
    response.headers['X-RateLimit-Limit'] = str(rate_limit_result['limit'])
    response.headers['X-RateLimit-Remaining'] = str(rate_limit_result['remaining'])
    response.headers['X-RateLimit-Reset'] = str(rate_limit_result['reset_time'])
    response.headers['Retry-After'] = str(rate_limit_result.get('retry_after', 60))
    
    return response


class RateLimitMiddleware:
    """Middleware for applying rate limits to all API endpoints."""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize rate limiting middleware."""
        app.before_request(self.before_request)
    
    def before_request(self):
        """Apply rate limiting before each request."""
        # Skip non-API endpoints
        if not request.path.startswith('/api/v1/'):
            return
        
        # Skip health checks
        if request.endpoint in ['api.health', 'api.status']:
            return
        
        # Skip in testing
        if current_app.config.get('TESTING'):
            return
        
        # Get rate limit manager
        rate_limit_manager = current_app.extensions.get('rate_limit_manager')
        if not rate_limit_manager:
            return
        
        endpoint = request.endpoint or request.path
        
        # Apply global rate limits based on endpoint category
        if '/auth/' in request.path:
            limits = ["10 per minute", "50 per hour"]
        else:
            from app.utils.rate_limiter import RateLimitConfig
            limits = RateLimitConfig.get_limits_for_endpoint(endpoint)
        
        # Check IP-based rate limit as fallback
        if not hasattr(g, 'user_id') or not g.user_id:
            from app.utils.rate_limiter import get_remote_address
            ip = get_remote_address()
            
            # Parse first limit
            limit_str = limits[0]
            parts = limit_str.split()
            limit = int(parts[0])
            
            if "minute" in limit_str:
                window = 60
            elif "hour" in limit_str:
                window = 3600
            else:
                window = 3600
            
            key = f"ip_rate_limit:{ip}:{endpoint}"
            result = rate_limit_manager.check_rate_limit(key, limit, window, f"ip:{ip}")
            
            if not result['allowed']:
                return _rate_limit_exceeded_response(result, 'ip')


def setup_rate_limiting_middleware(app):
    """Setup rate limiting middleware."""
    middleware = RateLimitMiddleware(app)
    logger.info("Rate limiting middleware initialized")
    return middleware