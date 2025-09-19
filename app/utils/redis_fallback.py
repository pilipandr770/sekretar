"""
Redis fallback utility for graceful degradation when Redis is unavailable.
"""
import logging
import time
from typing import Optional, Dict, Any, Union
from flask import current_app

logger = logging.getLogger(__name__)


class RedisFallbackManager:
    """Manages Redis connections with automatic fallback to simple alternatives."""
    
    def __init__(self, app=None):
        self.app = app
        self.redis_client = None
        self.redis_available = False
        self.last_check = 0
        self.check_interval = 30  # Check Redis availability every 30 seconds
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize Redis fallback manager with Flask app."""
        self.app = app
        
        # Test Redis connection on startup
        self.test_redis_connection()
        
        # Configure cache based on Redis availability
        self.configure_cache()
        
        # Configure Celery based on Redis availability
        self.configure_celery()
        
        # Configure rate limiting based on Redis availability
        self.configure_rate_limiting()
        
        logger.info(f"Redis fallback manager initialized (Redis available: {self.redis_available})")
    
    def test_redis_connection(self, force_check=False) -> bool:
        """
        Test Redis connection availability.
        
        Args:
            force_check: Force immediate check, ignoring check interval
            
        Returns:
            True if Redis is available, False otherwise
        """
        current_time = time.time()
        
        # Use cached result if within check interval
        if not force_check and (current_time - self.last_check) < self.check_interval:
            return self.redis_available
        
        self.last_check = current_time
        
        redis_url = self.app.config.get('REDIS_URL', '').strip()
        
        # Handle empty, None, or invalid REDIS_URL
        if not redis_url or redis_url.lower() in ['none', 'null', '']:
            if not hasattr(self, '_redis_not_configured_logged'):
                logger.info("ℹ️  Redis not configured, using fallback cache")
                self._redis_not_configured_logged = True
            self.redis_available = False
            self.redis_client = None
            return False
        
        # Validate Redis URL format
        if not self._is_valid_redis_url(redis_url):
            if not hasattr(self, '_redis_invalid_url_logged'):
                logger.warning(f"⚠️  Invalid Redis URL format: {redis_url[:20]}..., using fallback cache")
                self._redis_invalid_url_logged = True
            self.redis_available = False
            self.redis_client = None
            return False
        
        try:
            import redis
            
            # Create Redis client with short timeout and connection limits
            client = redis.from_url(
                redis_url,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=False,
                health_check_interval=30,
                max_connections=10
            )
            
            # Test connection with ping
            client.ping()
            
            self.redis_client = client
            self.redis_available = True
            
            # Reset failure logging flags on successful connection
            if hasattr(self, '_redis_failure_logged'):
                delattr(self, '_redis_failure_logged')
                logger.info("✅ Redis connection restored")
            elif not hasattr(self, '_redis_recovery_logged'):
                logger.info("✅ Redis connection established")
                self._redis_recovery_logged = True
            
            return True
            
        except ImportError:
            if not hasattr(self, '_redis_import_error_logged'):
                logger.warning("⚠️  Redis library not available, using fallback cache")
                self._redis_import_error_logged = True
            self.redis_client = None
            self.redis_available = False
            return False
            
        except Exception as e:
            self.redis_client = None
            self.redis_available = False
            
            # Rate limit error logging
            if not hasattr(self, '_redis_failure_logged'):
                error_type = type(e).__name__
                if 'ConnectionError' in error_type:
                    logger.warning(f"⚠️  Redis server unavailable, using fallback cache")
                elif 'TimeoutError' in error_type:
                    logger.warning(f"⚠️  Redis connection timeout, using fallback cache")
                elif 'AuthenticationError' in error_type:
                    logger.warning(f"⚠️  Redis authentication failed, check credentials")
                else:
                    logger.warning(f"⚠️  Redis connection failed ({error_type}), using fallback cache")
                self._redis_failure_logged = True
            
            return False
    
    def _is_valid_redis_url(self, url: str) -> bool:
        """
        Validate Redis URL format.
        
        Args:
            url: Redis URL to validate
            
        Returns:
            True if URL format is valid, False otherwise
        """
        try:
            import urllib.parse as urlparse
            parsed = urlparse.urlparse(url)
            
            # Check for valid Redis schemes
            valid_schemes = ['redis', 'rediss', 'redis+sentinel']
            if parsed.scheme not in valid_schemes:
                return False
            
            # Check for hostname
            if not parsed.hostname:
                return False
            
            # Check port is valid if specified
            if parsed.port is not None and (parsed.port < 1 or parsed.port > 65535):
                return False
            
            return True
            
        except Exception:
            return False
    
    def configure_cache(self):
        """Configure cache based on Redis availability."""
        if self.redis_available and self.redis_client:
            # Use Redis cache
            self.app.config['CACHE_TYPE'] = 'redis'
            self.app.config['CACHE_REDIS_URL'] = self.app.config.get('REDIS_URL')
            logger.info("💾 Using Redis cache")
        else:
            # Fallback to simple cache
            self.app.config['CACHE_TYPE'] = 'simple'
            self.app.config['CACHE_REDIS_URL'] = None
            logger.info("💾 Using simple cache fallback")
    
    def configure_celery(self):
        """Configure Celery based on Redis availability."""
        if self.redis_available:
            # Keep existing Celery configuration
            broker_url = self.app.config.get('CELERY_BROKER_URL', '').strip()
            result_backend = self.app.config.get('CELERY_RESULT_BACKEND', '').strip()
            
            # Validate Celery URLs
            if broker_url and result_backend and broker_url not in ['', 'none', 'null'] and result_backend not in ['', 'none', 'null']:
                # Test if Celery URLs are accessible
                if self._validate_celery_urls(broker_url, result_backend):
                    logger.info("🔄 Celery enabled with Redis broker")
                    self.app.config['CELERY_ENABLED'] = True
                else:
                    logger.warning("⚠️  Celery Redis URLs not accessible, disabling Celery")
                    self.app.config['CELERY_ENABLED'] = False
            else:
                logger.info("ℹ️  Celery URLs not configured, disabling Celery")
                self.app.config['CELERY_ENABLED'] = False
        else:
            # Disable Celery gracefully
            self.app.config['CELERY_BROKER_URL'] = None
            self.app.config['CELERY_RESULT_BACKEND'] = None
            self.app.config['CELERY_ENABLED'] = False
            logger.info("🔄 Celery disabled (Redis unavailable)")
    
    def _validate_celery_urls(self, broker_url: str, result_backend: str) -> bool:
        """
        Validate Celery Redis URLs are accessible.
        
        Args:
            broker_url: Celery broker URL
            result_backend: Celery result backend URL
            
        Returns:
            True if URLs are accessible, False otherwise
        """
        try:
            import redis
            
            # Test broker URL
            if broker_url and self._is_valid_redis_url(broker_url):
                broker_client = redis.from_url(broker_url, socket_connect_timeout=2, socket_timeout=2)
                broker_client.ping()
                broker_client.close()
            else:
                return False
            
            # Test result backend URL (if different from broker)
            if result_backend != broker_url and self._is_valid_redis_url(result_backend):
                backend_client = redis.from_url(result_backend, socket_connect_timeout=2, socket_timeout=2)
                backend_client.ping()
                backend_client.close()
            
            return True
            
        except Exception as e:
            logger.debug(f"Celery URL validation failed: {e}")
            return False
    
    def configure_rate_limiting(self):
        """Configure rate limiting based on Redis availability."""
        if self.redis_available:
            # Use Redis for rate limiting
            rate_limit_url = self.app.config.get('RATE_LIMIT_STORAGE_URL', '').strip()
            if rate_limit_url and rate_limit_url not in ['', 'none', 'null']:
                if self._is_valid_redis_url(rate_limit_url):
                    logger.info("🚦 Rate limiting enabled with Redis storage")
                    self.app.config['RATE_LIMITING_ENABLED'] = True
                else:
                    logger.warning("⚠️  Invalid rate limit storage URL, disabling rate limiting")
                    self.app.config['RATE_LIMITING_ENABLED'] = False
            else:
                logger.info("ℹ️  Rate limit storage URL not configured, disabling rate limiting")
                self.app.config['RATE_LIMITING_ENABLED'] = False
        else:
            # Use in-memory fallback for rate limiting
            self.app.config['RATE_LIMIT_STORAGE_URL'] = 'memory://'
            self.app.config['RATE_LIMITING_ENABLED'] = True
            logger.info("🚦 Rate limiting enabled with memory storage (Redis unavailable)")
    
    def get_redis_client(self) -> Optional[Any]:
        """
        Get Redis client if available.
        
        Returns:
            Redis client instance or None if unavailable
        """
        if self.test_redis_connection():
            return self.redis_client
        return None
    
    def set_cache_value(self, key: str, value: Any, timeout: int = 300) -> bool:
        """
        Set cache value with Redis fallback.
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Cache timeout in seconds
            
        Returns:
            True if value was cached, False otherwise
        """
        try:
            if self.redis_available and self.redis_client:
                # Use Redis
                import json
                serialized_value = json.dumps(value) if not isinstance(value, (str, bytes)) else value
                self.redis_client.setex(key, timeout, serialized_value)
                return True
            else:
                # Use Flask-Caching fallback (handled by Flask-Caching extension)
                from flask import current_app
                cache = current_app.extensions.get('cache')
                if cache:
                    cache.set(key, value, timeout=timeout)
                    return True
                return False
                
        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False
    
    def get_cache_value(self, key: str) -> Optional[Any]:
        """
        Get cache value with Redis fallback.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        try:
            if self.redis_available and self.redis_client:
                # Use Redis
                value = self.redis_client.get(key)
                if value:
                    import json
                    try:
                        return json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        return value.decode('utf-8') if isinstance(value, bytes) else value
                return None
            else:
                # Use Flask-Caching fallback
                from flask import current_app
                cache = current_app.extensions.get('cache')
                if cache:
                    return cache.get(key)
                return None
                
        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return None
    
    def delete_cache_value(self, key: str) -> bool:
        """
        Delete cache value with Redis fallback.
        
        Args:
            key: Cache key
            
        Returns:
            True if value was deleted, False otherwise
        """
        try:
            if self.redis_available and self.redis_client:
                # Use Redis
                return bool(self.redis_client.delete(key))
            else:
                # Use Flask-Caching fallback
                from flask import current_app
                cache = current_app.extensions.get('cache')
                if cache:
                    cache.delete(key)
                    return True
                return False
                
        except Exception as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get Redis fallback manager status.
        
        Returns:
            Status dictionary with connection info
        """
        return {
            'redis_available': self.redis_available,
            'redis_url': self.app.config.get('REDIS_URL', 'Not configured'),
            'cache_type': self.app.config.get('CACHE_TYPE', 'Unknown'),
            'celery_enabled': self.app.config.get('CELERY_ENABLED', False),
            'rate_limiting_enabled': self.app.config.get('RATE_LIMITING_ENABLED', False),
            'last_check': self.last_check,
            'check_interval': self.check_interval
        }


# Global instance
redis_fallback_manager = RedisFallbackManager()


def init_redis_fallback(app):
    """Initialize Redis fallback manager for the application."""
    redis_fallback_manager.init_app(app)
    return redis_fallback_manager


def get_redis_fallback_manager():
    """Get the global Redis fallback manager instance."""
    return redis_fallback_manager


def test_redis_connection() -> bool:
    """Test Redis connection using the global manager."""
    return redis_fallback_manager.test_redis_connection(force_check=True)


def get_redis_client():
    """Get Redis client using the global manager."""
    return redis_fallback_manager.get_redis_client()


def cache_set(key: str, value: Any, timeout: int = 300) -> bool:
    """Set cache value using the global manager."""
    return redis_fallback_manager.set_cache_value(key, value, timeout)


def cache_get(key: str) -> Optional[Any]:
    """Get cache value using the global manager."""
    return redis_fallback_manager.get_cache_value(key)


def cache_delete(key: str) -> bool:
    """Delete cache value using the global manager."""
    return redis_fallback_manager.delete_cache_value(key)