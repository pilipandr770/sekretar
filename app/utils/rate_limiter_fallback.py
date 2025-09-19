"""
Rate limiter with Redis fallback for graceful degradation.
"""
import logging
import time
from collections import defaultdict, deque
from typing import Dict, Optional
from flask import request, current_app
from functools import wraps

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """Simple in-memory rate limiter as fallback when Redis is unavailable."""
    
    def __init__(self):
        self.requests = defaultdict(deque)
        self.cleanup_interval = 60  # Clean up old entries every 60 seconds
        self.last_cleanup = time.time()
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """
        Check if request is allowed based on rate limit.
        
        Args:
            key: Unique identifier for the rate limit (e.g., IP address)
            limit: Maximum number of requests allowed
            window: Time window in seconds
            
        Returns:
            True if request is allowed, False if rate limited
        """
        current_time = time.time()
        
        # Clean up old entries periodically
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(current_time)
            self.last_cleanup = current_time
        
        # Get request queue for this key
        request_queue = self.requests[key]
        
        # Remove requests outside the window
        cutoff_time = current_time - window
        while request_queue and request_queue[0] < cutoff_time:
            request_queue.popleft()
        
        # Check if limit is exceeded
        if len(request_queue) >= limit:
            return False
        
        # Add current request
        request_queue.append(current_time)
        return True
    
    def _cleanup_old_entries(self, current_time: float):
        """Clean up old entries to prevent memory leaks."""
        keys_to_remove = []
        
        for key, request_queue in self.requests.items():
            # Remove requests older than 1 hour
            cutoff_time = current_time - 3600
            while request_queue and request_queue[0] < cutoff_time:
                request_queue.popleft()
            
            # Remove empty queues
            if not request_queue:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.requests[key]
    
    def get_stats(self) -> Dict[str, int]:
        """Get rate limiter statistics."""
        return {
            'active_keys': len(self.requests),
            'total_requests': sum(len(queue) for queue in self.requests.values())
        }


class RateLimiterFallback:
    """Rate limiter with Redis fallback."""
    
    def __init__(self, app=None):
        self.app = app
        self.redis_available = False
        self.redis_client = None
        self.memory_limiter = InMemoryRateLimiter()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize rate limiter with Flask app."""
        self.app = app
        
        # Check Redis availability
        self._check_redis_availability()
        
        # Configure rate limiting
        self._configure_rate_limiting()
        
        logger.info(f"Rate limiter initialized (Redis: {self.redis_available})")
    
    def _check_redis_availability(self):
        """Check if Redis is available for rate limiting."""
        try:
            from app.utils.redis_fallback import get_redis_client
            self.redis_client = get_redis_client()
            self.redis_available = self.redis_client is not None
        except Exception as e:
            logger.warning(f"Redis not available for rate limiting: {e}")
            self.redis_available = False
            self.redis_client = None
    
    def _configure_rate_limiting(self):
        """Configure rate limiting based on Redis availability."""
        if self.redis_available:
            self.app.config['RATE_LIMITING_ENABLED'] = True
            self.app.config['RATE_LIMITING_BACKEND'] = 'redis'
            logger.info("🚦 Rate limiting enabled with Redis backend")
        else:
            # Use in-memory fallback
            self.app.config['RATE_LIMITING_ENABLED'] = True
            self.app.config['RATE_LIMITING_BACKEND'] = 'memory'
            logger.info("🚦 Rate limiting enabled with in-memory fallback")
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """
        Check if request is allowed based on rate limit.
        
        Args:
            key: Unique identifier for the rate limit
            limit: Maximum number of requests allowed
            window: Time window in seconds
            
        Returns:
            True if request is allowed, False if rate limited
        """
        try:
            if self.redis_available and self.redis_client:
                return self._redis_is_allowed(key, limit, window)
            else:
                return self.memory_limiter.is_allowed(key, limit, window)
        except Exception as e:
            logger.warning(f"Rate limiting check failed: {e}")
            # On error, allow the request (fail open)
            return True
    
    def _redis_is_allowed(self, key: str, limit: int, window: int) -> bool:
        """Check rate limit using Redis."""
        try:
            current_time = time.time()
            
            # Use Redis sliding window algorithm
            pipe = self.redis_client.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, current_time - window)
            
            # Count current requests
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, window)
            
            results = pipe.execute()
            
            # Check if limit is exceeded
            current_count = results[1]
            return current_count < limit
            
        except Exception as e:
            logger.warning(f"Redis rate limiting failed: {e}")
            # Fall back to memory limiter
            return self.memory_limiter.is_allowed(key, limit, window)
    
    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics."""
        stats = {
            'backend': 'redis' if self.redis_available else 'memory',
            'redis_available': self.redis_available
        }
        
        if not self.redis_available:
            stats.update(self.memory_limiter.get_stats())
        
        return stats


# Global instance
rate_limiter = RateLimiterFallback()


def init_rate_limiter_fallback(app):
    """Initialize rate limiter fallback for the application."""
    rate_limiter.init_app(app)
    return rate_limiter


def rate_limit(limit: int, window: int = 60, key_func=None):
    """
    Rate limiting decorator with Redis fallback.
    
    Args:
        limit: Maximum number of requests allowed
        window: Time window in seconds
        key_func: Function to generate rate limit key (defaults to IP address)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip rate limiting if disabled
            if not current_app.config.get('RATE_LIMITING_ENABLED', False):
                return f(*args, **kwargs)
            
            # Generate rate limit key
            if key_func:
                key = key_func()
            else:
                key = f"rate_limit:{request.remote_addr}:{request.endpoint}"
            
            # Check rate limit
            if not rate_limiter.is_allowed(key, limit, window):
                from flask import jsonify
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {limit} requests per {window} seconds allowed'
                }), 429
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def get_rate_limiter():
    """Get the global rate limiter instance."""
    return rate_limiter