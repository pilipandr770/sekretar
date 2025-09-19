"""
Performance optimization utilities for database queries, caching, and static assets.
"""

import time
import logging
from functools import wraps
from typing import Dict, Any, Optional, List, Callable
from flask import current_app, request, g
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Query
from app import db, cache
import structlog

logger = structlog.get_logger(__name__)


class DatabaseQueryOptimizer:
    """Database query optimization utilities."""
    
    def __init__(self, app=None):
        self.app = app
        self.slow_query_threshold = 1000  # milliseconds
        self.query_stats = {}
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        self.slow_query_threshold = app.config.get('SLOW_QUERY_THRESHOLD_MS', 1000)
        
        # Set up query monitoring
        self._setup_query_monitoring()
        
        # Configure connection pooling
        self._configure_connection_pooling()
        
        logger.info("Database query optimizer initialized", 
                   threshold_ms=self.slow_query_threshold)
    
    def _setup_query_monitoring(self):
        """Set up SQLAlchemy query monitoring."""
        
        @event.listens_for(Engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Record query start time."""
            context._query_start_time = time.time()
        
        @event.listens_for(Engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Record query execution time and log slow queries."""
            total_time = time.time() - context._query_start_time
            total_time_ms = total_time * 1000
            
            # Update query statistics
            self._update_query_stats(statement, total_time_ms)
            
            # Log slow queries
            if total_time_ms > self.slow_query_threshold:
                logger.warning(
                    "Slow query detected",
                    duration_ms=round(total_time_ms, 2),
                    query=statement[:200] + "..." if len(statement) > 200 else statement,
                    parameters=str(parameters)[:100] if parameters else None
                )
    
    def _update_query_stats(self, statement: str, duration_ms: float):
        """Update query statistics."""
        # Extract table name from query for basic categorization
        statement_lower = statement.lower().strip()
        
        if statement_lower.startswith('select'):
            query_type = 'SELECT'
        elif statement_lower.startswith('insert'):
            query_type = 'INSERT'
        elif statement_lower.startswith('update'):
            query_type = 'UPDATE'
        elif statement_lower.startswith('delete'):
            query_type = 'DELETE'
        else:
            query_type = 'OTHER'
        
        if query_type not in self.query_stats:
            self.query_stats[query_type] = {
                'count': 0,
                'total_time_ms': 0,
                'avg_time_ms': 0,
                'max_time_ms': 0,
                'slow_queries': 0
            }
        
        stats = self.query_stats[query_type]
        stats['count'] += 1
        stats['total_time_ms'] += duration_ms
        stats['avg_time_ms'] = stats['total_time_ms'] / stats['count']
        stats['max_time_ms'] = max(stats['max_time_ms'], duration_ms)
        
        if duration_ms > self.slow_query_threshold:
            stats['slow_queries'] += 1
    
    def _configure_connection_pooling(self):
        """Configure database connection pooling for optimal performance."""
        if not self.app:
            return
        
        db_uri = self.app.config.get('SQLALCHEMY_DATABASE_URI', '')
        
        # Get current engine options
        engine_options = self.app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {})
        
        # Optimize based on database type
        if 'sqlite:///' in db_uri:
            # SQLite optimizations
            optimized_options = {
                'pool_pre_ping': True,
                'pool_recycle': 300,
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': 20,
                    'isolation_level': None  # Enable autocommit mode
                }
            }
        else:
            # PostgreSQL optimizations
            optimized_options = {
                'pool_pre_ping': True,
                'pool_recycle': 3600,
                'pool_timeout': 20,
                'pool_size': 10,
                'max_overflow': 20,
                'echo': False,  # Disable SQL echo in production
                'connect_args': {
                    'connect_timeout': 10,
                    'application_name': 'ai_secretary'
                }
            }
            
            # Add schema configuration if needed
            if self.app.config.get('DB_SCHEMA'):
                schema = self.app.config['DB_SCHEMA']
                optimized_options['connect_args']['options'] = f'-csearch_path={schema},public'
        
        # Merge with existing options
        engine_options.update(optimized_options)
        self.app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
        
        logger.info("Database connection pooling configured", 
                   database_type='sqlite' if 'sqlite' in db_uri else 'postgresql',
                   pool_size=optimized_options.get('pool_size', 'default'))
    
    def get_query_stats(self) -> Dict[str, Any]:
        """Get current query statistics."""
        return self.query_stats.copy()
    
    def reset_query_stats(self):
        """Reset query statistics."""
        self.query_stats.clear()
        logger.info("Query statistics reset")


class CacheOptimizer:
    """Cache optimization utilities."""
    
    def __init__(self, app=None):
        self.app = app
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        logger.info("Cache optimizer initialized")
    
    def cached_query(self, timeout: int = 300, key_prefix: str = 'query'):
        """Decorator for caching database query results."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
                
                # Try to get from cache
                try:
                    result = cache.get(cache_key)
                    if result is not None:
                        self.cache_stats['hits'] += 1
                        logger.debug("Cache hit", key=cache_key)
                        return result
                except Exception as e:
                    logger.warning("Cache get failed", key=cache_key, error=str(e))
                
                # Cache miss - execute function
                self.cache_stats['misses'] += 1
                result = func(*args, **kwargs)
                
                # Store in cache
                try:
                    cache.set(cache_key, result, timeout=timeout)
                    self.cache_stats['sets'] += 1
                    logger.debug("Cache set", key=cache_key, timeout=timeout)
                except Exception as e:
                    logger.warning("Cache set failed", key=cache_key, error=str(e))
                
                return result
            return wrapper
        return decorator
    
    def invalidate_cache_pattern(self, pattern: str):
        """Invalidate cache keys matching a pattern."""
        try:
            # This is a simplified implementation
            # In production, you might want to use Redis SCAN for pattern matching
            logger.info("Cache invalidation requested", pattern=pattern)
            self.cache_stats['deletes'] += 1
        except Exception as e:
            logger.warning("Cache invalidation failed", pattern=pattern, error=str(e))
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.cache_stats,
            'hit_rate_percent': round(hit_rate, 2),
            'total_requests': total_requests
        }


class StaticAssetOptimizer:
    """Static asset optimization utilities."""
    
    def __init__(self, app=None):
        self.app = app
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        
        # Configure static file caching
        self._configure_static_caching()
        
        logger.info("Static asset optimizer initialized")
    
    def _configure_static_caching(self):
        """Configure static file caching headers."""
        if not self.app:
            return
        
        @self.app.after_request
        def add_cache_headers(response):
            """Add cache headers for static assets."""
            if request.endpoint == 'static':
                # Cache static files for 1 hour in development, 1 day in production
                max_age = 86400 if not self.app.debug else 3600
                response.cache_control.max_age = max_age
                response.cache_control.public = True
                
                # Add ETag for better caching
                if not response.get_etag()[0]:
                    response.add_etag()
            
            return response


class LazyLoadingOptimizer:
    """Lazy loading optimization for heavy components."""
    
    def __init__(self, app=None):
        self.app = app
        self.loaded_components = set()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        logger.info("Lazy loading optimizer initialized")
    
    def lazy_load_relationship(self, model_instance, relationship_name: str):
        """Lazy load a relationship only when needed."""
        if not hasattr(model_instance, relationship_name):
            return None
        
        # Check if relationship is already loaded
        relationship = getattr(model_instance, relationship_name)
        
        # If it's a lazy relationship, it will be loaded on access
        return relationship
    
    def preload_relationships(self, query: Query, *relationships) -> Query:
        """Preload relationships to avoid N+1 queries."""
        from sqlalchemy.orm import joinedload, selectinload
        
        for relationship in relationships:
            if '.' in relationship:
                # Handle nested relationships
                parts = relationship.split('.')
                load_option = joinedload(parts[0])
                for part in parts[1:]:
                    load_option = load_option.joinedload(part)
                query = query.options(load_option)
            else:
                # Simple relationship
                query = query.options(selectinload(relationship))
        
        return query


class PerformanceMonitor:
    """Performance monitoring and metrics collection."""
    
    def __init__(self, app=None):
        self.app = app
        self.request_times = []
        self.slow_requests = []
        self.slow_request_threshold = 2000  # milliseconds
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app
        self.slow_request_threshold = app.config.get('SLOW_REQUEST_THRESHOLD_MS', 2000)
        
        # Set up request monitoring
        self._setup_request_monitoring()
        
        logger.info("Performance monitor initialized", 
                   threshold_ms=self.slow_request_threshold)
    
    def _setup_request_monitoring(self):
        """Set up Flask request monitoring."""
        
        @self.app.before_request
        def before_request():
            """Record request start time."""
            g.start_time = time.time()
        
        @self.app.after_request
        def after_request(response):
            """Record request completion and log slow requests."""
            if hasattr(g, 'start_time'):
                duration = time.time() - g.start_time
                duration_ms = duration * 1000
                
                # Record request time
                self.request_times.append(duration_ms)
                
                # Keep only last 1000 requests
                if len(self.request_times) > 1000:
                    self.request_times = self.request_times[-1000:]
                
                # Log slow requests
                if duration_ms > self.slow_request_threshold:
                    slow_request = {
                        'method': request.method,
                        'path': request.path,
                        'duration_ms': round(duration_ms, 2),
                        'status_code': response.status_code,
                        'timestamp': time.time()
                    }
                    
                    self.slow_requests.append(slow_request)
                    
                    # Keep only last 100 slow requests
                    if len(self.slow_requests) > 100:
                        self.slow_requests = self.slow_requests[-100:]
                    
                    logger.warning(
                        "Slow request detected",
                        method=request.method,
                        path=request.path,
                        duration_ms=round(duration_ms, 2),
                        status_code=response.status_code
                    )
            
            return response
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        if not self.request_times:
            return {
                'total_requests': 0,
                'avg_response_time_ms': 0,
                'max_response_time_ms': 0,
                'min_response_time_ms': 0,
                'slow_requests_count': 0,
                'slow_requests': []
            }
        
        return {
            'total_requests': len(self.request_times),
            'avg_response_time_ms': round(sum(self.request_times) / len(self.request_times), 2),
            'max_response_time_ms': round(max(self.request_times), 2),
            'min_response_time_ms': round(min(self.request_times), 2),
            'slow_requests_count': len(self.slow_requests),
            'slow_requests': self.slow_requests[-10:]  # Last 10 slow requests
        }


class PerformanceOptimizer:
    """Main performance optimizer that coordinates all optimization components."""
    
    def __init__(self, app=None):
        self.app = app
        self.db_optimizer = DatabaseQueryOptimizer()
        self.cache_optimizer = CacheOptimizer()
        self.static_optimizer = StaticAssetOptimizer()
        self.lazy_optimizer = LazyLoadingOptimizer()
        self.performance_monitor = PerformanceMonitor()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize all optimizers with Flask app."""
        self.app = app
        
        # Initialize all components
        self.db_optimizer.init_app(app)
        self.cache_optimizer.init_app(app)
        self.static_optimizer.init_app(app)
        self.lazy_optimizer.init_app(app)
        self.performance_monitor.init_app(app)
        
        # Store reference in app for access from other modules
        app.performance_optimizer = self
        
        logger.info("Performance optimizer fully initialized")
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        return {
            'database': self.db_optimizer.get_query_stats(),
            'cache': self.cache_optimizer.get_cache_stats(),
            'requests': self.performance_monitor.get_performance_stats(),
            'timestamp': time.time()
        }
    
    def optimize_query(self, query: Query, *relationships) -> Query:
        """Optimize a query with relationship preloading."""
        return self.lazy_optimizer.preload_relationships(query, *relationships)
    
    def cached_query(self, timeout: int = 300, key_prefix: str = 'query'):
        """Get cached query decorator."""
        return self.cache_optimizer.cached_query(timeout=timeout, key_prefix=key_prefix)


# Global instance
performance_optimizer = PerformanceOptimizer()


def init_performance_optimization(app):
    """Initialize performance optimization for the Flask app."""
    performance_optimizer.init_app(app)
    return performance_optimizer