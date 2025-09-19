"""
Performance optimization initialization for the Flask application.
"""

from flask import Flask
from app.utils.performance_optimizer import init_performance_optimization
from app.utils.connection_pool_manager import init_connection_pool_manager
from app.utils.static_asset_optimizer import init_static_optimization
from app.utils.optimized_queries import create_database_indexes
import structlog

logger = structlog.get_logger(__name__)


def init_all_performance_optimizations(app: Flask):
    """Initialize all performance optimizations for the Flask app."""
    
    optimizations_applied = []
    optimizations_skipped = []
    
    try:
        # 1. Initialize performance monitoring and query optimization
        if app.config.get('ENABLE_QUERY_OPTIMIZATION', True):
            performance_optimizer = init_performance_optimization(app)
            optimizations_applied.append('Query Optimization & Monitoring')
            logger.info("Performance optimizer initialized")
        else:
            optimizations_skipped.append('Query Optimization (disabled)')
        
        # 2. Initialize connection pool management
        if app.config.get('ENABLE_CONNECTION_POOLING', True):
            pool_manager = init_connection_pool_manager(app)
            optimizations_applied.append('Connection Pool Management')
            logger.info("Connection pool manager initialized")
        else:
            optimizations_skipped.append('Connection Pooling (disabled)')
        
        # 3. Initialize static asset optimization
        if app.config.get('ENABLE_STATIC_OPTIMIZATION', True):
            static_optimizers = init_static_optimization(app)
            optimizations_applied.append('Static Asset Optimization')
            logger.info("Static asset optimization initialized")
        else:
            optimizations_skipped.append('Static Asset Optimization (disabled)')
        
        # 4. Create database indexes for better query performance
        try:
            create_database_indexes()
            optimizations_applied.append('Database Indexes')
            logger.info("Database indexes created/verified")
        except Exception as e:
            logger.warning("Database index creation failed", error=str(e))
            optimizations_skipped.append('Database Indexes (failed)')
        
        # 5. Apply runtime optimizations
        try:
            _apply_runtime_optimizations(app)
            optimizations_applied.append('Runtime Optimizations')
            logger.info("Runtime optimizations applied")
        except Exception as e:
            logger.warning("Runtime optimizations failed", error=str(e))
            optimizations_skipped.append('Runtime Optimizations (failed)')
        
        # Log summary
        logger.info(
            "Performance optimizations initialized",
            applied=optimizations_applied,
            skipped=optimizations_skipped,
            total_applied=len(optimizations_applied),
            total_skipped=len(optimizations_skipped)
        )
        
        # Store optimization status in app config
        app.config['PERFORMANCE_OPTIMIZATIONS'] = {
            'applied': optimizations_applied,
            'skipped': optimizations_skipped,
            'initialized': True
        }
        
        return True
        
    except Exception as e:
        logger.error("Performance optimization initialization failed", error=str(e))
        app.config['PERFORMANCE_OPTIMIZATIONS'] = {
            'applied': optimizations_applied,
            'skipped': optimizations_skipped + ['Initialization failed'],
            'initialized': False,
            'error': str(e)
        }
        return False


def _apply_runtime_optimizations(app: Flask):
    """Apply runtime performance optimizations."""
    
    # Optimize connection settings if connection pool manager is available
    if hasattr(app, 'connection_pool_manager'):
        app.connection_pool_manager.optimize_connection_settings()
    
    # Pre-optimize static assets if static optimizer is available
    if hasattr(app, 'static_asset_optimizer'):
        app.static_asset_optimizer.optimize_assets()
    
    # Set up lazy loading for heavy components
    if app.config.get('ENABLE_LAZY_LOADING', True):
        _setup_lazy_loading(app)


def _setup_lazy_loading(app: Flask):
    """Set up lazy loading for heavy components."""
    
    if not hasattr(app, 'lazy_loading_manager'):
        return
    
    lazy_manager = app.lazy_loading_manager
    
    # Register heavy components for lazy loading
    
    # 1. OpenAI service
    def load_openai_service():
        try:
            from app.services.openai_service import OpenAIService
            return OpenAIService(app.config.get('OPENAI_API_KEY'))
        except ImportError:
            return None
    
    lazy_manager.register_lazy_component('openai_service', load_openai_service)
    
    # 2. Stripe service
    def load_stripe_service():
        try:
            from app.services.stripe_service import StripeService
            return StripeService(app.config.get('STRIPE_SECRET_KEY'))
        except ImportError:
            return None
    
    lazy_manager.register_lazy_component('stripe_service', load_stripe_service)
    
    # 3. Email service
    def load_email_service():
        try:
            from app.services.email_service import EmailService
            return EmailService(app)
        except ImportError:
            return None
    
    lazy_manager.register_lazy_component('email_service', load_email_service)
    
    # 4. Document processor
    def load_document_processor():
        try:
            from app.services.document_processor import DocumentProcessor
            return DocumentProcessor()
        except ImportError:
            return None
    
    lazy_manager.register_lazy_component('document_processor', load_document_processor)
    
    # 5. Embedding service (depends on OpenAI)
    def load_embedding_service():
        try:
            from app.services.embedding_service import EmbeddingService
            openai_service = lazy_manager.get_component('openai_service')
            return EmbeddingService(openai_service)
        except ImportError:
            return None
    
    lazy_manager.register_lazy_component(
        'embedding_service', 
        load_embedding_service, 
        dependencies=['openai_service']
    )
    
    logger.info("Lazy loading components registered", 
               count=len(lazy_manager.lazy_components))


def get_performance_status(app: Flask) -> dict:
    """Get current performance optimization status."""
    
    status = {
        'optimizations': app.config.get('PERFORMANCE_OPTIMIZATIONS', {}),
        'stats': {},
        'health': {}
    }
    
    # Get performance statistics
    try:
        if hasattr(app, 'performance_optimizer'):
            status['stats']['performance'] = app.performance_optimizer.get_comprehensive_stats()
        
        if hasattr(app, 'connection_pool_manager'):
            status['stats']['connection_pool'] = app.connection_pool_manager.get_pool_status()
            status['health']['connection_pool'] = app.connection_pool_manager.health_check()
        
        if hasattr(app, 'static_asset_optimizer'):
            status['stats']['static_assets'] = app.static_asset_optimizer.get_asset_stats()
        
        if hasattr(app, 'lazy_loading_manager'):
            status['stats']['lazy_loading'] = app.lazy_loading_manager.get_load_stats()
        
    except Exception as e:
        logger.error("Failed to get performance status", error=str(e))
        status['error'] = str(e)
    
    return status


def run_performance_diagnostics(app: Flask) -> dict:
    """Run comprehensive performance diagnostics."""
    
    diagnostics = {
        'timestamp': time.time(),
        'tests': {},
        'recommendations': []
    }
    
    try:
        # Test connection pool performance
        if hasattr(app, 'connection_pool_manager'):
            diagnostics['tests']['connection_pool'] = (
                app.connection_pool_manager.test_connection_performance()
            )
        
        # Analyze query performance
        from app.utils.optimized_queries import analyze_query_performance
        diagnostics['tests']['query_analysis'] = analyze_query_performance()
        
        # Generate recommendations
        diagnostics['recommendations'] = _generate_performance_recommendations(diagnostics)
        
    except Exception as e:
        logger.error("Performance diagnostics failed", error=str(e))
        diagnostics['error'] = str(e)
    
    return diagnostics


def _generate_performance_recommendations(diagnostics: dict) -> list:
    """Generate performance optimization recommendations based on diagnostics."""
    
    recommendations = []
    
    # Connection pool recommendations
    conn_test = diagnostics.get('tests', {}).get('connection_pool', {})
    if conn_test.get('avg_connection_time', 0) > 100:  # > 100ms
        recommendations.append(
            "Connection times are high - consider increasing connection pool size"
        )
    
    if conn_test.get('success_rate', 100) < 95:
        recommendations.append(
            "Connection success rate is low - check database connectivity"
        )
    
    # Query performance recommendations
    query_analysis = diagnostics.get('tests', {}).get('query_analysis', {})
    suggestions = query_analysis.get('suggestions', [])
    recommendations.extend(suggestions)
    
    # Cache recommendations
    cache_stats = query_analysis.get('stats', {}).get('cache', {})
    hit_rate = cache_stats.get('hit_rate_percent', 0)
    
    if hit_rate < 50:
        recommendations.append(
            "Cache hit rate is low - consider caching more frequently accessed data"
        )
    elif hit_rate > 90:
        recommendations.append(
            "Excellent cache performance - consider expanding caching to more operations"
        )
    
    return recommendations


import time