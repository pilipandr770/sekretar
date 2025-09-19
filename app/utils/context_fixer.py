"""Flask application context fixing utilities."""
import logging
import functools
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from flask import Flask, current_app, has_app_context
from werkzeug.local import LocalProxy


logger = logging.getLogger(__name__)


@dataclass
class ContextFixResult:
    """Result of context fix operation."""
    success: bool
    fixed_issues: List[str]
    remaining_issues: List[str]
    errors: List[str]
    warnings: List[str]


class ContextFixer:
    """Fixes Flask application context errors."""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self.fixed_issues = []
        self.remaining_issues = []
        self.errors = []
        self.warnings = []
    
    def fix_all_context_issues(self) -> ContextFixResult:
        """Fix all known context issues."""
        logger.info("🔧 Starting context fixes...")
        
        # Reset tracking lists
        self.fixed_issues = []
        self.remaining_issues = []
        self.errors = []
        self.warnings = []
        
        try:
            self._perform_context_fixes()
                
        except Exception as e:
            logger.error(f"Failed to perform context fixes: {e}")
            self.errors.append(f"Failed to perform context fixes: {e}")
        
        result = ContextFixResult(
            success=len(self.errors) == 0,
            fixed_issues=self.fixed_issues,
            remaining_issues=self.remaining_issues,
            errors=self.errors,
            warnings=self.warnings
        )
        
        logger.info(f"✅ Context fixes completed. Fixed: {len(result.fixed_issues)}, Errors: {len(result.errors)}")
        return result
    
    def _perform_context_fixes(self):
        """Perform all context fixes."""
        # Fix health check context issues
        self._fix_health_check_contexts()
        
        # Fix monitoring context issues
        self._fix_monitoring_contexts()
        
        # Fix service initialization context issues
        self._fix_service_initialization_contexts()
        
        # Apply context decorators to problematic functions
        self._apply_context_decorators()
    
    def _fix_health_check_contexts(self):
        """Fix context issues in health checks."""
        try:
            # Patch service health monitor methods
            from app.utils import service_health_monitor
            
            # Wrap health check methods with app context
            if hasattr(service_health_monitor, 'ServiceHealthMonitor'):
                monitor_class = service_health_monitor.ServiceHealthMonitor
                
                # Patch PostgreSQL health check
                if hasattr(monitor_class, '_check_postgresql'):
                    original_check_postgresql = monitor_class._check_postgresql
                    monitor_class._check_postgresql = self._wrap_with_app_context(original_check_postgresql)
                    self.fixed_issues.append("Fixed PostgreSQL health check context")
                
                # Patch SQLite health check
                if hasattr(monitor_class, '_check_sqlite'):
                    original_check_sqlite = monitor_class._check_sqlite
                    monitor_class._check_sqlite = self._wrap_with_app_context(original_check_sqlite)
                    self.fixed_issues.append("Fixed SQLite health check context")
                
                # Patch Redis health check
                if hasattr(monitor_class, '_check_redis'):
                    original_check_redis = monitor_class._check_redis
                    monitor_class._check_redis = self._wrap_with_app_context(original_check_redis)
                    self.fixed_issues.append("Fixed Redis health check context")
                    
        except Exception as e:
            logger.error(f"Failed to fix health check contexts: {e}")
            self.errors.append(f"Failed to fix health check contexts: {e}")
    
    def _fix_monitoring_contexts(self):
        """Fix context issues in monitoring systems."""
        try:
            # Fix performance monitoring context issues
            from app.utils import performance_alerts
            
            if hasattr(performance_alerts, 'PerformanceThresholdChecker'):
                checker_class = performance_alerts.PerformanceThresholdChecker
                
                # Wrap threshold checking methods
                if hasattr(checker_class, 'check_error_rates'):
                    original_check_error_rates = checker_class.check_error_rates
                    checker_class.check_error_rates = self._wrap_with_app_context(original_check_error_rates)
                    self.fixed_issues.append("Fixed error rate checking context")
                
                if hasattr(checker_class, 'check_response_times'):
                    original_check_response_times = checker_class.check_response_times
                    checker_class.check_response_times = self._wrap_with_app_context(original_check_response_times)
                    self.fixed_issues.append("Fixed response time checking context")
                    
        except Exception as e:
            logger.error(f"Failed to fix monitoring contexts: {e}")
            self.errors.append(f"Failed to fix monitoring contexts: {e}")
    
    def _fix_service_initialization_contexts(self):
        """Fix context issues in service initialization."""
        try:
            # Fix database initialization context issues
            self._fix_database_initialization_context()
            
            # Fix cache initialization context issues
            self._fix_cache_initialization_context()
            
        except Exception as e:
            logger.error(f"Failed to fix service initialization contexts: {e}")
            self.errors.append(f"Failed to fix service initialization contexts: {e}")
    
    def _fix_database_initialization_context(self):
        """Fix database initialization context issues."""
        try:
            # Patch database operations that might run outside context
            from app.utils import database_fixer
            
            if hasattr(database_fixer, 'DatabaseFixer'):
                fixer_class = database_fixer.DatabaseFixer
                
                # Wrap database operations with context
                if hasattr(fixer_class, 'check_table_exists'):
                    original_check_table_exists = fixer_class.check_table_exists
                    fixer_class.check_table_exists = self._wrap_with_app_context(original_check_table_exists)
                    self.fixed_issues.append("Fixed database table existence check context")
                    
        except Exception as e:
            logger.warning(f"Could not fix database initialization context: {e}")
            self.warnings.append(f"Could not fix database initialization context: {e}")
    
    def _fix_cache_initialization_context(self):
        """Fix cache initialization context issues."""
        try:
            # Fix Redis cache context issues
            from app.utils import service_checker
            
            if hasattr(service_checker, 'ServiceChecker'):
                checker_class = service_checker.ServiceChecker
                
                # Wrap cache operations with context
                if hasattr(checker_class, 'check_redis'):
                    original_check_redis = checker_class.check_redis
                    checker_class.check_redis = self._wrap_with_app_context(original_check_redis)
                    self.fixed_issues.append("Fixed Redis cache check context")
                    
        except Exception as e:
            logger.warning(f"Could not fix cache initialization context: {e}")
            self.warnings.append(f"Could not fix cache initialization context: {e}")
    
    def _apply_context_decorators(self):
        """Apply context decorators to problematic functions."""
        try:
            # Apply decorators to common problematic patterns
            self._apply_database_context_decorators()
            self._apply_monitoring_context_decorators()
            
        except Exception as e:
            logger.error(f"Failed to apply context decorators: {e}")
            self.errors.append(f"Failed to apply context decorators: {e}")
    
    def _apply_database_context_decorators(self):
        """Apply context decorators to database operations."""
        try:
            # Patch common database operations
            from app import db
            
            # Wrap database session operations that might run outside context
            if hasattr(db, 'session'):
                # Note: This is more complex and might need specific implementation
                # based on the actual usage patterns in the application
                self.warnings.append("Database session context fixes may need manual review")
                
        except Exception as e:
            logger.warning(f"Could not apply database context decorators: {e}")
            self.warnings.append(f"Could not apply database context decorators: {e}")
    
    def _apply_monitoring_context_decorators(self):
        """Apply context decorators to monitoring operations."""
        try:
            # Fix background monitoring tasks
            from app.workers import monitoring
            
            if hasattr(monitoring, 'get_queue_health'):
                original_get_queue_health = monitoring.get_queue_health
                monitoring.get_queue_health = self._wrap_with_app_context_if_needed(original_get_queue_health)
                self.fixed_issues.append("Fixed queue health monitoring context")
                
        except Exception as e:
            logger.warning(f"Could not apply monitoring context decorators: {e}")
            self.warnings.append(f"Could not apply monitoring context decorators: {e}")
    
    def _wrap_with_app_context(self, func: Callable) -> Callable:
        """Wrap a function to ensure it runs within app context."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if has_app_context():
                # Already in app context, just call the function
                return func(*args, **kwargs)
            else:
                # Need to create app context
                if self.app:
                    with self.app.app_context():
                        return func(*args, **kwargs)
                else:
                    # Try to get app from current_app proxy
                    try:
                        app = current_app._get_current_object()
                        with app.app_context():
                            return func(*args, **kwargs)
                    except RuntimeError:
                        logger.error(f"No application context available for {func.__name__}")
                        return None
        
        return wrapper
    
    def _wrap_with_app_context_if_needed(self, func: Callable) -> Callable:
        """Wrap a function with app context only if it's not already wrapped."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Try to call the function normally first
                return func(*args, **kwargs)
            except RuntimeError as e:
                if "working outside of application context" in str(e).lower():
                    # Context error detected, wrap with app context
                    if self.app:
                        with self.app.app_context():
                            return func(*args, **kwargs)
                    else:
                        logger.error(f"Context error in {func.__name__} but no app available")
                        return None
                else:
                    # Different error, re-raise
                    raise
        
        return wrapper


def with_app_context(app: Optional[Flask] = None):
    """Decorator to ensure function runs within Flask application context."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if has_app_context():
                return func(*args, **kwargs)
            else:
                target_app = app
                if not target_app:
                    try:
                        target_app = current_app._get_current_object()
                    except RuntimeError:
                        logger.error(f"No application context available for {func.__name__}")
                        return None
                
                with target_app.app_context():
                    return func(*args, **kwargs)
        
        return wrapper
    return decorator


def safe_app_context_operation(func: Callable) -> Callable:
    """Decorator for safe operations that might need app context."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RuntimeError as e:
            if "working outside of application context" in str(e).lower():
                logger.warning(f"Context error in {func.__name__}: {e}")
                return None
            else:
                raise
    
    return wrapper


def ensure_app_context(app: Flask):
    """Context manager to ensure app context is available."""
    class AppContextManager:
        def __init__(self, app: Flask):
            self.app = app
            self.should_pop = False
        
        def __enter__(self):
            if not has_app_context():
                self.app.app_context().push()
                self.should_pop = True
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.should_pop:
                try:
                    self.app.app_context().pop()
                except Exception as e:
                    logger.warning(f"Error popping app context: {e}")
    
    return AppContextManager(app)