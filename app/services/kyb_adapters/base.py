"""Base adapter for KYB data sources."""
import time
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from flask import current_app
from redis import Redis
import structlog

logger = structlog.get_logger()


class KYBAdapterError(Exception):
    """Base exception for KYB adapter errors."""
    pass


class RateLimitExceeded(KYBAdapterError):
    """Raised when rate limit is exceeded."""
    pass


class DataSourceUnavailable(KYBAdapterError):
    """Raised when data source is unavailable."""
    pass


class ValidationError(KYBAdapterError):
    """Raised when input validation fails."""
    pass


class BaseKYBAdapter(ABC):
    """Base class for KYB data source adapters."""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize adapter with optional Redis client for caching."""
        self.redis_client = redis_client
        self.source_name = self.__class__.__name__.replace('Adapter', '').upper()
        
        # Rate limiting configuration (per minute)
        self.rate_limit = getattr(self, 'RATE_LIMIT', 60)
        self.rate_window = getattr(self, 'RATE_WINDOW', 60)  # seconds
        
        # Cache configuration
        self.cache_ttl = getattr(self, 'CACHE_TTL', 3600)  # 1 hour default
        self.enable_cache = getattr(self, 'ENABLE_CACHE', True)
        
        # Retry configuration
        self.max_retries = getattr(self, 'MAX_RETRIES', 3)
        self.retry_delay = getattr(self, 'RETRY_DELAY', 1)  # seconds
        
        logger.info(f"Initialized {self.source_name} adapter", 
                   rate_limit=self.rate_limit, 
                   cache_ttl=self.cache_ttl)
    
    @abstractmethod
    def check_single(self, identifier: str, **kwargs) -> Dict[str, Any]:
        """Check a single entity. Must be implemented by subclasses."""
        pass
    
    def check_batch(self, identifiers: List[str], **kwargs) -> List[Dict[str, Any]]:
        """Check multiple entities. Default implementation calls check_single for each."""
        results = []
        
        for identifier in identifiers:
            try:
                result = self.check_single(identifier, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch check failed for {identifier}", 
                           error=str(e), source=self.source_name)
                results.append({
                    'identifier': identifier,
                    'status': 'error',
                    'error': str(e),
                    'source': self.source_name,
                    'checked_at': datetime.utcnow().isoformat() + 'Z'
                })
        
        return results
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows the request."""
        if not self.redis_client:
            return True
        
        key = f"kyb_rate_limit:{self.source_name}"
        current_count = self.redis_client.get(key)
        
        if current_count is None:
            # First request in window
            self.redis_client.setex(key, self.rate_window, 1)
            return True
        
        current_count = int(current_count)
        if current_count >= self.rate_limit:
            logger.warning(f"Rate limit exceeded for {self.source_name}", 
                         current_count=current_count, limit=self.rate_limit)
            return False
        
        # Increment counter
        self.redis_client.incr(key)
        return True
    
    def _get_cache_key(self, identifier: str, **kwargs) -> str:
        """Generate cache key for the request."""
        # Include kwargs in cache key for different request types
        key_data = f"{self.source_name}:{identifier}"
        if kwargs:
            # Sort kwargs for consistent cache keys
            sorted_kwargs = sorted(kwargs.items())
            key_data += ":" + ":".join(f"{k}={v}" for k, v in sorted_kwargs)
        
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached result if available and not expired."""
        if not self.enable_cache or not self.redis_client:
            return None
        
        try:
            cached_data = self.redis_client.get(f"kyb_cache:{cache_key}")
            if cached_data:
                import json
                result = json.loads(cached_data)
                logger.debug(f"Cache hit for {self.source_name}", cache_key=cache_key)
                return result
        except Exception as e:
            logger.warning(f"Cache read error for {self.source_name}", 
                         error=str(e), cache_key=cache_key)
        
        return None
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache the result."""
        if not self.enable_cache or not self.redis_client:
            return
        
        try:
            import json
            self.redis_client.setex(
                f"kyb_cache:{cache_key}", 
                self.cache_ttl, 
                json.dumps(result, default=str)
            )
            logger.debug(f"Cached result for {self.source_name}", cache_key=cache_key)
        except Exception as e:
            logger.warning(f"Cache write error for {self.source_name}", 
                         error=str(e), cache_key=cache_key)
    
    def _execute_with_retry(self, func, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (ConnectionError, TimeoutError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Retry attempt {attempt + 1} for {self.source_name}", 
                                 delay=delay, error=str(e))
                    time.sleep(delay)
                else:
                    logger.error(f"All retry attempts failed for {self.source_name}", 
                               attempts=self.max_retries + 1, error=str(e))
            except Exception as e:
                # Don't retry for non-network errors
                logger.error(f"Non-retryable error for {self.source_name}", error=str(e))
                raise
        
        # If we get here, all retries failed
        raise DataSourceUnavailable(f"{self.source_name} unavailable after {self.max_retries + 1} attempts: {last_exception}")
    
    def _validate_identifier(self, identifier: str) -> str:
        """Validate and clean identifier. Override in subclasses."""
        if not identifier or not identifier.strip():
            raise ValidationError("Identifier cannot be empty")
        
        return identifier.strip().upper()
    
    def _create_error_result(self, identifier: str, error: str, status: str = 'error') -> Dict[str, Any]:
        """Create standardized error result."""
        return {
            'identifier': identifier,
            'status': status,
            'error': error,
            'source': self.source_name,
            'checked_at': datetime.utcnow().isoformat() + 'Z',
            'response_time_ms': 0
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        if not self.redis_client:
            return {'cache_enabled': False, 'rate_limit_enabled': False}
        
        try:
            rate_limit_key = f"kyb_rate_limit:{self.source_name}"
            current_requests = self.redis_client.get(rate_limit_key)
            current_requests = int(current_requests) if current_requests else 0
            
            # Get cache hit/miss stats (simplified)
            cache_stats = {
                'cache_enabled': self.enable_cache,
                'cache_ttl': self.cache_ttl
            }
            
            rate_stats = {
                'rate_limit_enabled': True,
                'rate_limit': self.rate_limit,
                'rate_window': self.rate_window,
                'current_requests': current_requests,
                'remaining_requests': max(0, self.rate_limit - current_requests)
            }
            
            return {
                **cache_stats,
                **rate_stats,
                'source': self.source_name
            }
        except Exception as e:
            logger.error(f"Failed to get stats for {self.source_name}", error=str(e))
            return {'error': str(e)}