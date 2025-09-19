"""
Tests for performance optimization functionality.
"""

import pytest
import time
from unittest.mock import Mock, patch
from flask import Flask
from app.utils.performance_optimizer import (
    DatabaseQueryOptimizer, CacheOptimizer, PerformanceMonitor, PerformanceOptimizer
)
from app.utils.connection_pool_manager import ConnectionPoolManager
from app.utils.static_asset_optimizer import StaticAssetOptimizer, LazyLoadingManager
from app.utils.performance_init import init_all_performance_optimizations


class TestDatabaseQueryOptimizer:
    """Test database query optimization."""
    
    def test_init_without_app(self):
        """Test initializing optimizer without app."""
        optimizer = DatabaseQueryOptimizer()
        assert optimizer.app is None
        assert optimizer.slow_query_threshold == 1000
        assert optimizer.query_stats == {}
    
    def test_init_with_app(self, app):
        """Test initializing optimizer with app."""
        optimizer = DatabaseQueryOptimizer(app)
        assert optimizer.app == app
        assert optimizer.slow_query_threshold == app.config.get('SLOW_QUERY_THRESHOLD_MS', 1000)
    
    def test_update_query_stats(self, app):
        """Test query statistics tracking."""
        optimizer = DatabaseQueryOptimizer(app)
        
        # Test SELECT query
        optimizer._update_query_stats("SELECT * FROM users", 500.0)
        assert 'SELECT' in optimizer.query_stats
        assert optimizer.query_stats['SELECT']['count'] == 1
        assert optimizer.query_stats['SELECT']['avg_time_ms'] == 500.0
        
        # Test another SELECT query
        optimizer._update_query_stats("SELECT id FROM users", 300.0)
        assert optimizer.query_stats['SELECT']['count'] == 2
        assert optimizer.query_stats['SELECT']['avg_time_ms'] == 400.0
    
    def test_get_query_stats(self, app):
        """Test getting query statistics."""
        optimizer = DatabaseQueryOptimizer(app)
        optimizer._update_query_stats("SELECT * FROM users", 500.0)
        
        stats = optimizer.get_query_stats()
        assert isinstance(stats, dict)
        assert 'SELECT' in stats
        assert stats['SELECT']['count'] == 1
    
    def test_reset_query_stats(self, app):
        """Test resetting query statistics."""
        optimizer = DatabaseQueryOptimizer(app)
        optimizer._update_query_stats("SELECT * FROM users", 500.0)
        
        optimizer.reset_query_stats()
        assert optimizer.query_stats == {}


class TestCacheOptimizer:
    """Test cache optimization."""
    
    def test_init_without_app(self):
        """Test initializing cache optimizer without app."""
        optimizer = CacheOptimizer()
        assert optimizer.app is None
        assert optimizer.cache_stats['hits'] == 0
    
    def test_cached_query_decorator(self, app):
        """Test cached query decorator."""
        with app.app_context():
            optimizer = CacheOptimizer(app)
            
            # Mock cache
            mock_cache = Mock()
            mock_cache.get.return_value = None  # Cache miss
            mock_cache.set.return_value = True
            
            with patch('app.utils.performance_optimizer.cache', mock_cache):
                @optimizer.cached_query(timeout=300, key_prefix='test')
                def test_function(arg1, arg2):
                    return f"result_{arg1}_{arg2}"
                
                # First call should be cache miss
                result = test_function("a", "b")
                assert result == "result_a_b"
                assert optimizer.cache_stats['misses'] == 1
                assert optimizer.cache_stats['sets'] == 1
                
                # Mock cache hit for second call
                mock_cache.get.return_value = "cached_result"
                result = test_function("a", "b")
                assert result == "cached_result"
                assert optimizer.cache_stats['hits'] == 1
    
    def test_get_cache_stats(self, app):
        """Test getting cache statistics."""
        optimizer = CacheOptimizer(app)
        optimizer.cache_stats['hits'] = 80
        optimizer.cache_stats['misses'] = 20
        
        stats = optimizer.get_cache_stats()
        assert stats['hits'] == 80
        assert stats['misses'] == 20
        assert stats['total_requests'] == 100
        assert stats['hit_rate_percent'] == 80.0


class TestPerformanceMonitor:
    """Test performance monitoring."""
    
    def test_init_without_app(self):
        """Test initializing monitor without app."""
        monitor = PerformanceMonitor()
        assert monitor.app is None
        assert monitor.request_times == []
        assert monitor.slow_requests == []
    
    def test_get_performance_stats_empty(self, app):
        """Test getting stats with no data."""
        monitor = PerformanceMonitor(app)
        
        stats = monitor.get_performance_stats()
        assert stats['total_requests'] == 0
        assert stats['avg_response_time_ms'] == 0
        assert stats['slow_requests_count'] == 0
    
    def test_get_performance_stats_with_data(self, app):
        """Test getting stats with data."""
        monitor = PerformanceMonitor(app)
        
        # Add some request times
        monitor.request_times = [100, 200, 300, 400, 500]
        monitor.slow_requests = [
            {'method': 'GET', 'path': '/slow', 'duration_ms': 3000, 'status_code': 200}
        ]
        
        stats = monitor.get_performance_stats()
        assert stats['total_requests'] == 5
        assert stats['avg_response_time_ms'] == 300.0
        assert stats['max_response_time_ms'] == 500.0
        assert stats['min_response_time_ms'] == 100.0
        assert stats['slow_requests_count'] == 1


class TestConnectionPoolManager:
    """Test connection pool management."""
    
    def test_init_without_app(self):
        """Test initializing manager without app."""
        manager = ConnectionPoolManager()
        assert manager.app is None
        assert manager.pool_stats['connections_created'] == 0
    
    def test_get_pool_stats(self, app):
        """Test getting pool statistics."""
        manager = ConnectionPoolManager(app)
        
        # Simulate some connections
        manager.pool_stats['connections_created'] = 10
        manager.pool_stats['connections_closed'] = 8
        
        stats = manager.get_pool_stats()
        assert stats['connections_created'] == 10
        assert stats['connections_closed'] == 8
        assert stats['connections_reused'] == 0  # max(0, 8-10)
        assert 'pool_efficiency' in stats
    
    def test_sqlite_pool_config(self, app):
        """Test SQLite pool configuration."""
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
        manager = ConnectionPoolManager(app)
        
        config = manager._get_sqlite_pool_config('development')
        assert 'connect_args' in config
        assert config['connect_args']['check_same_thread'] is False
        assert config['connect_args']['journal_mode'] == 'WAL'
    
    def test_postgresql_pool_config(self, app):
        """Test PostgreSQL pool configuration."""
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@localhost/db'
        manager = ConnectionPoolManager(app)
        
        config = manager._get_postgresql_pool_config('production')
        assert config['pool_size'] == 20
        assert config['max_overflow'] == 30
        assert 'connect_args' in config


class TestStaticAssetOptimizer:
    """Test static asset optimization."""
    
    def test_init_without_app(self):
        """Test initializing optimizer without app."""
        optimizer = StaticAssetOptimizer()
        assert optimizer.app is None
        assert optimizer.asset_cache == {}
        assert optimizer.asset_stats['requests'] == 0
    
    def test_should_compress(self, app):
        """Test file compression detection."""
        optimizer = StaticAssetOptimizer(app)
        
        assert optimizer._should_compress('app.js') is True
        assert optimizer._should_compress('style.css') is True
        assert optimizer._should_compress('image.png') is False
        assert optimizer._should_compress('document.pdf') is False
    
    def test_is_versioned_asset(self, app):
        """Test versioned asset detection."""
        optimizer = StaticAssetOptimizer(app)
        
        assert optimizer._is_versioned_asset('app.a1b2c3d4.js') is True
        assert optimizer._is_versioned_asset('style-v1.2.3.css') is True
        assert optimizer._is_versioned_asset('app.js') is False
    
    def test_get_asset_stats(self, app):
        """Test getting asset statistics."""
        optimizer = StaticAssetOptimizer(app)
        
        optimizer.asset_stats['requests'] = 100
        optimizer.asset_stats['cache_hits'] = 80
        optimizer.asset_stats['compressions'] = 20
        
        stats = optimizer.get_asset_stats()
        assert stats['cache_hit_rate'] == 80.0
        assert stats['compression_rate'] == 20.0


class TestLazyLoadingManager:
    """Test lazy loading management."""
    
    def test_init_without_app(self):
        """Test initializing manager without app."""
        manager = LazyLoadingManager()
        assert manager.app is None
        assert manager.lazy_components == {}
        assert manager.load_stats['components_registered'] == 0
    
    def test_register_lazy_component(self, app):
        """Test registering lazy component."""
        manager = LazyLoadingManager(app)
        
        def test_loader():
            return "test_component"
        
        manager.register_lazy_component('test', test_loader, ['dependency1'])
        
        assert 'test' in manager.lazy_components
        assert manager.lazy_components['test']['loader'] == test_loader
        assert manager.lazy_components['test']['dependencies'] == ['dependency1']
        assert manager.lazy_components['test']['loaded'] is False
        assert manager.load_stats['components_registered'] == 1
    
    def test_load_component(self, app):
        """Test loading lazy component."""
        manager = LazyLoadingManager(app)
        
        def test_loader():
            return "loaded_component"
        
        manager.register_lazy_component('test', test_loader)
        
        # Load component
        result = manager.load_component('test')
        assert result == "loaded_component"
        assert manager.lazy_components['test']['loaded'] is True
        assert manager.load_stats['components_loaded'] == 1
    
    def test_load_component_with_dependencies(self, app):
        """Test loading component with dependencies."""
        manager = LazyLoadingManager(app)
        
        def dep_loader():
            return "dependency"
        
        def main_loader():
            return "main_component"
        
        manager.register_lazy_component('dependency', dep_loader)
        manager.register_lazy_component('main', main_loader, ['dependency'])
        
        # Load main component (should load dependency first)
        result = manager.load_component('main')
        assert result == "main_component"
        assert manager.lazy_components['dependency']['loaded'] is True
        assert manager.lazy_components['main']['loaded'] is True
    
    def test_get_load_stats(self, app):
        """Test getting load statistics."""
        manager = LazyLoadingManager(app)
        
        manager.load_stats['components_registered'] = 5
        manager.load_stats['components_loaded'] = 3
        manager.load_stats['total_load_time'] = 1.5
        
        stats = manager.get_load_stats()
        assert stats['load_rate'] == 60.0  # 3/5 * 100
        assert stats['avg_load_time'] == 0.5  # 1.5/3


class TestPerformanceOptimizer:
    """Test main performance optimizer."""
    
    def test_init_without_app(self):
        """Test initializing optimizer without app."""
        optimizer = PerformanceOptimizer()
        assert optimizer.app is None
        assert isinstance(optimizer.db_optimizer, DatabaseQueryOptimizer)
        assert isinstance(optimizer.cache_optimizer, CacheOptimizer)
    
    def test_init_with_app(self, app):
        """Test initializing optimizer with app."""
        optimizer = PerformanceOptimizer(app)
        assert optimizer.app == app
        assert hasattr(app, 'performance_optimizer')
    
    def test_get_comprehensive_stats(self, app):
        """Test getting comprehensive statistics."""
        optimizer = PerformanceOptimizer(app)
        
        stats = optimizer.get_comprehensive_stats()
        assert 'database' in stats
        assert 'cache' in stats
        assert 'requests' in stats
        assert 'timestamp' in stats


class TestPerformanceInit:
    """Test performance initialization."""
    
    def test_init_all_performance_optimizations(self, app):
        """Test initializing all performance optimizations."""
        # Set all optimization flags to True
        app.config['ENABLE_QUERY_OPTIMIZATION'] = True
        app.config['ENABLE_CONNECTION_POOLING'] = True
        app.config['ENABLE_STATIC_OPTIMIZATION'] = True
        app.config['ENABLE_LAZY_LOADING'] = True
        
        success = init_all_performance_optimizations(app)
        assert success is True
        
        # Check that optimization status is stored
        assert 'PERFORMANCE_OPTIMIZATIONS' in app.config
        optimizations = app.config['PERFORMANCE_OPTIMIZATIONS']
        assert optimizations['initialized'] is True
        assert len(optimizations['applied']) > 0
    
    def test_init_with_disabled_optimizations(self, app):
        """Test initialization with some optimizations disabled."""
        app.config['ENABLE_QUERY_OPTIMIZATION'] = False
        app.config['ENABLE_CONNECTION_POOLING'] = True
        app.config['ENABLE_STATIC_OPTIMIZATION'] = False
        app.config['ENABLE_LAZY_LOADING'] = True
        
        success = init_all_performance_optimizations(app)
        assert success is True
        
        optimizations = app.config['PERFORMANCE_OPTIMIZATIONS']
        assert len(optimizations['skipped']) > 0
        
        # Check that disabled optimizations are in skipped list
        skipped_names = ' '.join(optimizations['skipped'])
        assert 'Query Optimization' in skipped_names
        assert 'Static Asset Optimization' in skipped_names


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SLOW_QUERY_THRESHOLD_MS'] = 1000
    app.config['SLOW_REQUEST_THRESHOLD_MS'] = 2000
    
    return app