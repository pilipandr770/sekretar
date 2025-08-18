"""Rate limiting utilities for API endpoints."""
import redis
from flask import request, g, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger()


def get_rate_limit_key() -> str:
    """
    Generate rate limit key based on user/tenant context.
    
    Priority:
    1. User ID (if authenticated)
    2. Tenant ID (if available)
    3. IP address (fallback)
    """
    # Try to get user ID first
    user_id = getattr(g, 'user_id', None)
    if user_id:
        return f"user:{user_id}"
    
    # Try to get tenant ID
    tenant_id = getattr(g, 'tenant_id', None)
    if tenant_id:
        return f"tenant:{tenant_id}"
    
    # Fallback to IP address
    return f"ip:{get_remote_address()}"


def get_tenant_rate_limit_key() -> str:
    """Generate tenant-specific rate limit key."""
    tenant_id = getattr(g, 'tenant_id', None)
    if tenant_id:
        return f"tenant:{tenant_id}"
    return f"ip:{get_remote_address()}"


def get_user_rate_limit_key() -> str:
    """Generate user-specific rate limit key."""
    user_id = getattr(g, 'user_id', None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address()}"


class RateLimitConfig:
    """Rate limit configuration for different endpoint types."""
    
    # Default limits
    DEFAULT_LIMITS = ["1000 per hour", "100 per minute"]
    
    # Authentication endpoints
    AUTH_LIMITS = ["10 per minute", "50 per hour"]
    
    # API endpoints by category
    API_LIMITS = {
        "inbox": ["500 per hour", "50 per minute"],
        "crm": ["1000 per hour", "100 per minute"],
        "calendar": ["200 per hour", "20 per minute"],
        "knowledge": ["100 per hour", "10 per minute"],
        "billing": ["50 per hour", "5 per minute"],
        "kyb": ["100 per hour", "10 per minute"],
        "admin": ["200 per hour", "20 per minute"]
    }
    
    # Tenant-specific limits (higher limits for paid plans)
    TENANT_LIMITS = {
        "free": ["100 per hour", "10 per minute"],
        "starter": ["500 per hour", "50 per minute"],
        "pro": ["2000 per hour", "200 per minute"],
        "team": ["5000 per hour", "500 per minute"],
        "enterprise": ["10000 per hour", "1000 per minute"]
    }
    
    @classmethod
    def get_limits_for_endpoint(cls, endpoint: str) -> list:
        """Get rate limits for a specific endpoint."""
        # Extract category from endpoint path
        if "/auth/" in endpoint:
            return cls.AUTH_LIMITS
        
        for category in cls.API_LIMITS:
            if f"/{category}/" in endpoint:
                return cls.API_LIMITS[category]
        
        return cls.DEFAULT_LIMITS
    
    @classmethod
    def get_tenant_limits(cls, tenant_plan: str = "free") -> list:
        """Get rate limits based on tenant plan."""
        return cls.TENANT_LIMITS.get(tenant_plan.lower(), cls.TENANT_LIMITS["free"])


def create_limiter(app) -> Limiter:
    """Create and configure Flask-Limiter instance."""
    
    # Get Redis URL from config
    redis_url = app.config.get('RATE_LIMIT_STORAGE_URL', app.config.get('REDIS_URL'))
    
    limiter = Limiter(
        app=app,
        key_func=get_rate_limit_key,
        storage_uri=redis_url,
        default_limits=RateLimitConfig.DEFAULT_LIMITS,
        headers_enabled=True,
        swallow_errors=True,  # Don't break app if Redis is down
        strategy="fixed-window"
    )
    
    # Add custom error handler
    @limiter.request_filter
    def skip_rate_limiting():
        """Skip rate limiting for certain conditions."""
        # Skip for health checks
        if request.endpoint in ['api.health', 'api.status']:
            return True
        
        # Skip for testing environment
        if app.config.get('TESTING'):
            return True
        
        return False
    
    return limiter


class RateLimitManager:
    """Advanced rate limiting manager with tenant and user-specific limits."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def check_rate_limit(
        self, 
        key: str, 
        limit: int, 
        window: int,
        identifier: str = None
    ) -> Dict[str, Any]:
        """
        Check if rate limit is exceeded.
        
        Args:
            key: Rate limit key
            limit: Maximum requests allowed
            window: Time window in seconds
            identifier: Optional identifier for logging
        
        Returns:
            Dict with rate limit status and metadata
        """
        try:
            # Use sliding window counter
            import time
            now = int(time.time())
            pipeline = self.redis.pipeline()
            
            # Remove old entries
            pipeline.zremrangebyscore(key, 0, now - window)
            
            # Count current requests
            pipeline.zcard(key)
            
            # Add current request
            pipeline.zadd(key, {str(now): now})
            
            # Set expiry
            pipeline.expire(key, window)
            
            results = pipeline.execute()
            current_count = results[1]
            
            is_allowed = current_count < limit
            remaining = max(0, limit - current_count - 1)
            
            result = {
                'allowed': is_allowed,
                'limit': limit,
                'remaining': remaining,
                'reset_time': now + window,
                'current_count': current_count
            }
            
            if not is_allowed:
                logger.warning(
                    "Rate limit exceeded",
                    key=key,
                    identifier=identifier,
                    current_count=current_count,
                    limit=limit
                )
            
            return result
            
        except Exception as e:
            logger.error("Rate limit check failed", error=str(e), key=key)
            # Fail open - allow request if Redis is down
            return {
                'allowed': True,
                'limit': limit,
                'remaining': limit,
                'reset_time': 0,
                'current_count': 0,
                'error': str(e)
            }
    
    def get_tenant_plan(self, tenant_id: int) -> str:
        """Get tenant plan for rate limiting."""
        try:
            from app.models.tenant import Tenant
            from app.models.billing import Subscription
            
            tenant = Tenant.query.get(tenant_id)
            if not tenant:
                return "free"
            
            # Get active subscription
            subscription = Subscription.query.filter_by(
                tenant_id=tenant_id,
                status='active'
            ).first()
            
            if subscription and subscription.plan:
                return subscription.plan.name.lower()
            
            return "free"
            
        except Exception as e:
            logger.error("Failed to get tenant plan", error=str(e), tenant_id=tenant_id)
            return "free"
    
    def check_tenant_rate_limit(self, tenant_id: int, endpoint: str) -> Dict[str, Any]:
        """Check tenant-specific rate limits."""
        plan = self.get_tenant_plan(tenant_id)
        limits = RateLimitConfig.get_tenant_limits(plan)
        
        # Parse first limit (e.g., "500 per hour")
        limit_str = limits[0]
        parts = limit_str.split()
        limit = int(parts[0])
        
        if "minute" in limit_str:
            window = 60
        elif "hour" in limit_str:
            window = 3600
        else:
            window = 3600  # Default to hour
        
        key = f"tenant_rate_limit:{tenant_id}:{endpoint}"
        return self.check_rate_limit(key, limit, window, f"tenant:{tenant_id}")
    
    def check_user_rate_limit(self, user_id: int, endpoint: str) -> Dict[str, Any]:
        """Check user-specific rate limits."""
        limits = RateLimitConfig.get_limits_for_endpoint(endpoint)
        
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
        
        key = f"user_rate_limit:{user_id}:{endpoint}"
        return self.check_rate_limit(key, limit, window, f"user:{user_id}")


def init_rate_limiting(app):
    """Initialize rate limiting for the application."""
    
    # Create limiter instance
    limiter = create_limiter(app)
    
    # Store limiter in app extensions
    if not hasattr(app, 'extensions'):
        app.extensions = {}
    app.extensions['limiter'] = limiter
    
    # Create rate limit manager
    redis_client = redis.from_url(app.config.get('RATE_LIMIT_STORAGE_URL', app.config.get('REDIS_URL')))
    rate_limit_manager = RateLimitManager(redis_client)
    app.extensions['rate_limit_manager'] = rate_limit_manager
    
    logger.info("Rate limiting initialized", redis_url=app.config.get('RATE_LIMIT_STORAGE_URL'))
    
    return limiter, rate_limit_manager