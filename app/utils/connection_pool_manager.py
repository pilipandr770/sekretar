"""
Database connection pool management for optimal performance.
"""

import time
import threading
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool, StaticPool
from flask import current_app
import structlog

logger = structlog.get_logger(__name__)


class ConnectionPoolManager:
    """Manages database connection pools for optimal performance."""
    
    def __init__(self, app=None):
        self.app = app
        self.pool_stats = {
            'connections_created': 0,
            'connections_closed': 0,
            'connections_active': 0,
            'pool_overflows': 0,
            'pool_timeouts': 0
        }
        self._lock = threading.Lock()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize connection pool manager with Flask app."""
        self.app = app
        
        # Configure connection pool based on database type
        self._configure_connection_pool()
        
        # Set up connection pool monitoring
        self._setup_pool_monitoring()
        
        logger.info("Connection pool manager initialized")
    
    def _configure_connection_pool(self):
        """Configure connection pool settings based on database type and environment."""
        if not self.app:
            return
        
        db_uri = self.app.config.get('SQLALCHEMY_DATABASE_URI', '')
        environment = self.app.config.get('FLASK_ENV', 'development')
        
        # Get current engine options
        engine_options = self.app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {})
        
        if 'sqlite:///' in db_uri:
            # SQLite configuration
            pool_config = self._get_sqlite_pool_config(environment)
        else:
            # PostgreSQL configuration
            pool_config = self._get_postgresql_pool_config(environment)
        
        # Merge pool configuration with existing engine options
        engine_options.update(pool_config)
        self.app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
        
        logger.info(
            "Connection pool configured",
            database_type='sqlite' if 'sqlite' in db_uri else 'postgresql',
            environment=environment,
            pool_size=pool_config.get('pool_size', 'default'),
            max_overflow=pool_config.get('max_overflow', 'default')
        )
    
    def _get_sqlite_pool_config(self, environment: str) -> Dict[str, Any]:
        """Get SQLite-specific connection pool configuration."""
        if environment == 'production':
            return {
                'poolclass': StaticPool,
                'pool_pre_ping': True,
                'pool_recycle': 300,
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': 30,
                    'isolation_level': None,  # Autocommit mode
                    'journal_mode': 'WAL',    # Write-Ahead Logging for better concurrency
                    'synchronous': 'NORMAL',  # Balance between safety and performance
                    'cache_size': -64000,     # 64MB cache
                    'temp_store': 'MEMORY'    # Store temp tables in memory
                }
            }
        else:
            # Development configuration
            return {
                'poolclass': StaticPool,
                'pool_pre_ping': True,
                'pool_recycle': 300,
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': 20,
                    'isolation_level': None,
                    'journal_mode': 'WAL',
                    'synchronous': 'NORMAL',
                    'cache_size': -32000,     # 32MB cache for development
                    'temp_store': 'MEMORY'
                }
            }
    
    def _get_postgresql_pool_config(self, environment: str) -> Dict[str, Any]:
        """Get PostgreSQL-specific connection pool configuration."""
        if environment == 'production':
            return {
                'poolclass': QueuePool,
                'pool_size': 20,              # Base pool size
                'max_overflow': 30,           # Additional connections beyond pool_size
                'pool_timeout': 30,           # Timeout for getting connection from pool
                'pool_recycle': 3600,         # Recycle connections every hour
                'pool_pre_ping': True,        # Validate connections before use
                'echo': False,                # Disable SQL logging in production
                'connect_args': {
                    'connect_timeout': 10,
                    'application_name': 'ai_secretary_prod',
                    'sslmode': 'prefer',
                    'keepalives_idle': 600,
                    'keepalives_interval': 30,
                    'keepalives_count': 3
                }
            }
        elif environment == 'testing':
            return {
                'poolclass': StaticPool,
                'pool_pre_ping': False,       # Skip ping in tests for speed
                'pool_recycle': -1,           # Don't recycle connections in tests
                'connect_args': {
                    'connect_timeout': 5,
                    'application_name': 'ai_secretary_test'
                }
            }
        else:
            # Development configuration
            return {
                'poolclass': QueuePool,
                'pool_size': 5,               # Smaller pool for development
                'max_overflow': 10,
                'pool_timeout': 20,
                'pool_recycle': 1800,         # 30 minutes
                'pool_pre_ping': True,
                'echo': False,                # Can be enabled for debugging
                'connect_args': {
                    'connect_timeout': 10,
                    'application_name': 'ai_secretary_dev'
                }
            }
    
    def _setup_pool_monitoring(self):
        """Set up connection pool monitoring."""
        
        @event.listens_for(Engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            """Track connection creation."""
            with self._lock:
                self.pool_stats['connections_created'] += 1
                self.pool_stats['connections_active'] += 1
            
            logger.debug("Database connection created")
        
        @event.listens_for(Engine, "close")
        def receive_close(dbapi_connection, connection_record):
            """Track connection closure."""
            with self._lock:
                self.pool_stats['connections_closed'] += 1
                self.pool_stats['connections_active'] = max(0, self.pool_stats['connections_active'] - 1)
            
            logger.debug("Database connection closed")
        
        @event.listens_for(Engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Track connection checkout from pool."""
            logger.debug("Connection checked out from pool")
        
        @event.listens_for(Engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Track connection checkin to pool."""
            logger.debug("Connection checked in to pool")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get current connection pool statistics."""
        with self._lock:
            stats = self.pool_stats.copy()
        
        # Add calculated metrics
        stats['connections_reused'] = max(0, stats['connections_closed'] - stats['connections_created'])
        stats['pool_efficiency'] = (
            stats['connections_reused'] / max(1, stats['connections_created']) * 100
        )
        
        return stats
    
    def get_pool_status(self) -> Dict[str, Any]:
        """Get detailed connection pool status."""
        try:
            from app.extensions import db
            
            if hasattr(db.engine, 'pool'):
                pool = db.engine.pool
                
                return {
                    'pool_size': getattr(pool, 'size', lambda: 'N/A')(),
                    'checked_in': getattr(pool, 'checkedin', lambda: 'N/A')(),
                    'checked_out': getattr(pool, 'checkedout', lambda: 'N/A')(),
                    'overflow': getattr(pool, 'overflow', lambda: 'N/A')(),
                    'invalid': getattr(pool, 'invalid', lambda: 'N/A')(),
                    'pool_class': pool.__class__.__name__,
                    'stats': self.get_pool_stats()
                }
            else:
                return {
                    'error': 'Pool information not available',
                    'stats': self.get_pool_stats()
                }
        
        except Exception as e:
            logger.error("Failed to get pool status", error=str(e))
            return {
                'error': str(e),
                'stats': self.get_pool_stats()
            }
    
    def optimize_connection_settings(self):
        """Optimize database connection settings at runtime."""
        try:
            from app.extensions import db
            
            db_uri = self.app.config.get('SQLALCHEMY_DATABASE_URI', '')
            
            if 'sqlite:///' in db_uri:
                self._optimize_sqlite_settings()
            else:
                self._optimize_postgresql_settings()
            
            logger.info("Connection settings optimized")
            
        except Exception as e:
            logger.error("Failed to optimize connection settings", error=str(e))
    
    def _optimize_sqlite_settings(self):
        """Optimize SQLite connection settings."""
        from app.extensions import db
        
        # SQLite-specific optimizations
        optimizations = [
            "PRAGMA journal_mode = WAL",           # Write-Ahead Logging
            "PRAGMA synchronous = NORMAL",         # Balance safety and performance
            "PRAGMA cache_size = -64000",          # 64MB cache
            "PRAGMA temp_store = MEMORY",          # Temp tables in memory
            "PRAGMA mmap_size = 268435456",        # 256MB memory-mapped I/O
            "PRAGMA optimize"                      # Optimize query planner
        ]
        
        for pragma in optimizations:
            try:
                db.session.execute(text(pragma))
                logger.debug("Applied SQLite optimization", pragma=pragma)
            except Exception as e:
                logger.warning("Failed to apply SQLite optimization", pragma=pragma, error=str(e))
        
        try:
            db.session.commit()
        except Exception as e:
            logger.warning("Failed to commit SQLite optimizations", error=str(e))
            db.session.rollback()
    
    def _optimize_postgresql_settings(self):
        """Optimize PostgreSQL connection settings."""
        from app.extensions import db
        
        # PostgreSQL-specific optimizations
        optimizations = [
            "SET work_mem = '16MB'",               # Memory for sorts and joins
            "SET maintenance_work_mem = '64MB'",   # Memory for maintenance operations
            "SET effective_cache_size = '256MB'",  # Estimate of OS cache
            "SET random_page_cost = 1.1",          # SSD optimization
            "SET seq_page_cost = 1.0"              # Sequential scan cost
        ]
        
        for setting in optimizations:
            try:
                db.session.execute(text(setting))
                logger.debug("Applied PostgreSQL optimization", setting=setting)
            except Exception as e:
                logger.warning("Failed to apply PostgreSQL optimization", setting=setting, error=str(e))
        
        try:
            db.session.commit()
        except Exception as e:
            logger.warning("Failed to commit PostgreSQL optimizations", error=str(e))
            db.session.rollback()
    
    def test_connection_performance(self, iterations: int = 10) -> Dict[str, Any]:
        """Test connection pool performance."""
        from app.extensions import db
        
        results = {
            'iterations': iterations,
            'connection_times': [],
            'query_times': [],
            'total_time': 0,
            'avg_connection_time': 0,
            'avg_query_time': 0
        }
        
        start_time = time.time()
        
        for i in range(iterations):
            # Test connection acquisition
            conn_start = time.time()
            
            try:
                # Simple query to test connection
                result = db.session.execute(text("SELECT 1")).scalar()
                
                conn_time = (time.time() - conn_start) * 1000  # Convert to milliseconds
                results['connection_times'].append(conn_time)
                
                # Test query performance
                query_start = time.time()
                db.session.execute(text("SELECT COUNT(*) FROM users")).scalar()
                query_time = (time.time() - query_start) * 1000
                results['query_times'].append(query_time)
                
            except Exception as e:
                logger.error("Connection test failed", iteration=i, error=str(e))
                results['connection_times'].append(-1)
                results['query_times'].append(-1)
        
        results['total_time'] = (time.time() - start_time) * 1000
        
        # Calculate averages (excluding failed attempts)
        valid_conn_times = [t for t in results['connection_times'] if t >= 0]
        valid_query_times = [t for t in results['query_times'] if t >= 0]
        
        if valid_conn_times:
            results['avg_connection_time'] = sum(valid_conn_times) / len(valid_conn_times)
        if valid_query_times:
            results['avg_query_time'] = sum(valid_query_times) / len(valid_query_times)
        
        results['success_rate'] = len(valid_conn_times) / iterations * 100
        
        logger.info(
            "Connection performance test completed",
            iterations=iterations,
            avg_connection_time_ms=round(results['avg_connection_time'], 2),
            avg_query_time_ms=round(results['avg_query_time'], 2),
            success_rate=round(results['success_rate'], 1)
        )
        
        return results
    
    def health_check(self) -> Dict[str, Any]:
        """Perform connection pool health check."""
        try:
            from app.extensions import db
            
            # Test basic connectivity
            start_time = time.time()
            result = db.session.execute(text("SELECT 1")).scalar()
            response_time = (time.time() - start_time) * 1000
            
            pool_status = self.get_pool_status()
            
            # Determine health status
            is_healthy = (
                result == 1 and
                response_time < 1000 and  # Less than 1 second
                pool_status.get('checked_out', 0) < pool_status.get('pool_size', 1)
            )
            
            return {
                'healthy': is_healthy,
                'response_time_ms': round(response_time, 2),
                'pool_status': pool_status,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error("Connection pool health check failed", error=str(e))
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': time.time()
            }


# Global instance
connection_pool_manager = ConnectionPoolManager()


def init_connection_pool_manager(app):
    """Initialize connection pool manager for the Flask app."""
    connection_pool_manager.init_app(app)
    return connection_pool_manager