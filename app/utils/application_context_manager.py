"""
Application Context Manager for Background Services

Provides proper Flask application context management for background services,
health checks, and long-running tasks to prevent "Working outside of application context" errors.
"""

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import Callable, Any, Optional, ContextManager, List
from flask import Flask, has_app_context, current_app, g
from flask_sqlalchemy import SQLAlchemy

from .error_rate_limiter import get_error_rate_limiter
from .improved_error_messages import log_actionable_error

logger = logging.getLogger(__name__)


@dataclass
class ContextState:
    """Track Flask application context state for diagnostics and debugging."""
    has_context: bool
    app_name: Optional[str] = None
    request_context: bool = False
    database_bound: bool = False
    session_active: bool = False
    error_details: Optional[str] = None
    thread_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert ContextState to dictionary for logging."""
        return {
            'has_context': self.has_context,
            'app_name': self.app_name,
            'request_context': self.request_context,
            'database_bound': self.database_bound,
            'session_active': self.session_active,
            'error_details': self.error_details,
            'thread_id': self.thread_id,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ContextRecoveryResult:
    """Result of context recovery attempt for tracking and monitoring."""
    success: bool
    context_created: bool = False
    error_message: Optional[str] = None
    recovery_method: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert ContextRecoveryResult to dictionary for logging."""
        return {
            'success': self.success,
            'context_created': self.context_created,
            'error_message': self.error_message,
            'recovery_method': self.recovery_method,
            'timestamp': self.timestamp.isoformat()
        }


class ApplicationContextManager:
    """
    Manages Flask application context for background services and tasks.
    
    This class ensures that all background services, health checks, and long-running
    tasks have proper Flask application context to access database, configuration,
    and other Flask-dependent resources.
    """
    
    def __init__(self, app: Flask):
        """
        Initialize the context manager with a Flask application.
        
        Args:
            app: Flask application instance
        """
        self.app = app
        self._context_stack = []
        self._lock = threading.Lock()
        self._recovery_history: List[ContextRecoveryResult] = []
        
        logger.info("ApplicationContextManager initialized")
    
    def validate_context(self) -> bool:
        """
        Check if Flask application context is active and valid.
        
        Returns:
            True if context is valid, False otherwise
        """
        try:
            if not has_app_context():
                return False
            
            # Try to access current_app to ensure context is fully functional
            _ = current_app.name
            return True
            
        except RuntimeError as e:
            if "working outside of application context" in str(e).lower():
                return False
            raise
        except Exception:
            return False
    
    def get_context_state(self) -> ContextState:
        """
        Get detailed information about current Flask application context state.
        
        Returns:
            ContextState object with comprehensive context information
        """
        context_state = ContextState(
            has_context=False,
            thread_id=threading.current_thread().ident
        )
        
        try:
            context_state.has_context = has_app_context()
            
            if context_state.has_context:
                try:
                    context_state.app_name = current_app.name
                    
                    # Check if we have request context
                    try:
                        from flask import has_request_context
                        context_state.request_context = has_request_context()
                    except ImportError:
                        context_state.request_context = False
                    
                    # Check database binding
                    try:
                        # Try to access the database extension
                        if hasattr(current_app, 'extensions') and 'sqlalchemy' in current_app.extensions:
                            db = current_app.extensions['sqlalchemy']
                            context_state.database_bound = True
                            
                            # Check if session is active
                            if hasattr(db, 'session'):
                                context_state.session_active = db.session.is_active
                        else:
                            context_state.database_bound = False
                    except Exception as db_error:
                        context_state.database_bound = False
                        context_state.error_details = f"Database check failed: {str(db_error)}"
                        
                except Exception as app_error:
                    context_state.error_details = f"App context check failed: {str(app_error)}"
                    
        except Exception as e:
            context_state.error_details = f"Context state check failed: {str(e)}"
            
        return context_state
    
    def diagnose_context_issues(self) -> dict:
        """
        Perform comprehensive context diagnostics for debugging.
        
        Returns:
            Dictionary with detailed diagnostic information
        """
        diagnostics = {
            'timestamp': datetime.now().isoformat(),
            'thread_info': {
                'current_thread_id': threading.current_thread().ident,
                'current_thread_name': threading.current_thread().name,
                'active_count': threading.active_count()
            },
            'context_state': self.get_context_state().to_dict(),
            'app_info': {
                'app_name': self.app.name if self.app else None,
                'app_instance_id': id(self.app) if self.app else None,
                'debug_mode': getattr(self.app, 'debug', None) if self.app else None
            },
            'recovery_history': [recovery.to_dict() for recovery in self._recovery_history[-5:]],  # Last 5 recoveries
            'context_stack_size': len(self._context_stack)
        }
        
        # Additional Flask-specific diagnostics
        try:
            if has_app_context():
                diagnostics['flask_context'] = {
                    'current_app_name': current_app.name,
                    'current_app_id': id(current_app),
                    'config_keys': list(current_app.config.keys()) if hasattr(current_app, 'config') else []
                }
            else:
                diagnostics['flask_context'] = {'status': 'no_app_context'}
        except Exception as e:
            diagnostics['flask_context'] = {'error': str(e)}
            
        return diagnostics
    
    def handle_context_error(self, error: Exception, function_name: str = "unknown") -> ContextRecoveryResult:
        """
        Handle context-related errors with automatic recovery mechanisms.
        
        This method attempts multiple recovery strategies when context errors occur,
        tracks recovery attempts, and provides detailed information about the process.
        
        Args:
            error: The context-related error that occurred
            function_name: Name of the function where the error occurred
            
        Returns:
            ContextRecoveryResult with details about the recovery attempt
        """
        logger.info(f"Attempting context recovery for error in {function_name}: {str(error)}")
        
        # Create initial recovery result
        recovery_result = ContextRecoveryResult(
            success=False,
            recovery_method="multi_strategy"
        )
        
        try:
            # Strategy 1: Simple context recreation
            recovery_result = self._attempt_simple_context_recovery(function_name)
            if recovery_result.success:
                self._record_recovery_attempt(recovery_result)
                return recovery_result
            
            # Strategy 2: Force context cleanup and recreation
            recovery_result = self._attempt_force_context_recovery(function_name)
            if recovery_result.success:
                self._record_recovery_attempt(recovery_result)
                return recovery_result
            
            # Strategy 3: Thread-specific context recovery
            recovery_result = self._attempt_thread_context_recovery(function_name)
            if recovery_result.success:
                self._record_recovery_attempt(recovery_result)
                return recovery_result
            
            # All strategies failed
            recovery_result.error_message = "All recovery strategies failed"
            recovery_result.recovery_method = "all_strategies_failed"
            
        except Exception as recovery_error:
            recovery_result.error_message = f"Recovery attempt failed: {str(recovery_error)}"
            recovery_result.recovery_method = "recovery_exception"
            logger.error(f"Context recovery attempt failed: {recovery_error}")
        
        self._record_recovery_attempt(recovery_result)
        return recovery_result
    
    def _attempt_simple_context_recovery(self, function_name: str) -> ContextRecoveryResult:
        """
        Attempt simple context recovery by creating new application context.
        
        Args:
            function_name: Name of the function for logging
            
        Returns:
            ContextRecoveryResult indicating success or failure
        """
        try:
            # Check if we already have a valid context
            if self.validate_context():
                return ContextRecoveryResult(
                    success=True,
                    context_created=False,
                    recovery_method="context_already_valid"
                )
            
            # Try to create new context
            with self.app.app_context():
                if self.validate_context():
                    logger.debug(f"Simple context recovery successful for {function_name}")
                    return ContextRecoveryResult(
                        success=True,
                        context_created=True,
                        recovery_method="simple_context_creation"
                    )
                else:
                    return ContextRecoveryResult(
                        success=False,
                        error_message="Context created but validation failed",
                        recovery_method="simple_context_creation"
                    )
                    
        except Exception as e:
            return ContextRecoveryResult(
                success=False,
                error_message=f"Simple recovery failed: {str(e)}",
                recovery_method="simple_context_creation"
            )
    
    def _attempt_force_context_recovery(self, function_name: str) -> ContextRecoveryResult:
        """
        Attempt forced context recovery with cleanup and recreation.
        
        Args:
            function_name: Name of the function for logging
            
        Returns:
            ContextRecoveryResult indicating success or failure
        """
        try:
            # Clear any existing context stack
            with self._lock:
                self._context_stack.clear()
            
            # Force garbage collection to clean up any lingering contexts
            import gc
            gc.collect()
            
            # Create fresh context
            with self.app.app_context():
                if self.validate_context():
                    logger.debug(f"Force context recovery successful for {function_name}")
                    return ContextRecoveryResult(
                        success=True,
                        context_created=True,
                        recovery_method="force_context_recreation"
                    )
                else:
                    return ContextRecoveryResult(
                        success=False,
                        error_message="Forced context created but validation failed",
                        recovery_method="force_context_recreation"
                    )
                    
        except Exception as e:
            return ContextRecoveryResult(
                success=False,
                error_message=f"Force recovery failed: {str(e)}",
                recovery_method="force_context_recreation"
            )
    
    def _attempt_thread_context_recovery(self, function_name: str) -> ContextRecoveryResult:
        """
        Attempt thread-specific context recovery for background services.
        
        Args:
            function_name: Name of the function for logging
            
        Returns:
            ContextRecoveryResult indicating success or failure
        """
        try:
            current_thread = threading.current_thread()
            logger.debug(f"Attempting thread-specific recovery for {function_name} in thread {current_thread.ident}")
            
            # Create context specifically for this thread
            app_context = self.app.app_context()
            app_context.push()
            
            try:
                if self.validate_context():
                    logger.debug(f"Thread context recovery successful for {function_name}")
                    return ContextRecoveryResult(
                        success=True,
                        context_created=True,
                        recovery_method="thread_specific_context"
                    )
                else:
                    return ContextRecoveryResult(
                        success=False,
                        error_message="Thread context created but validation failed",
                        recovery_method="thread_specific_context"
                    )
            finally:
                # Clean up the manually pushed context
                try:
                    app_context.pop()
                except Exception:
                    pass  # Context might have been cleaned up already
                    
        except Exception as e:
            return ContextRecoveryResult(
                success=False,
                error_message=f"Thread recovery failed: {str(e)}",
                recovery_method="thread_specific_context"
            )
    
    def _record_recovery_attempt(self, recovery_result: ContextRecoveryResult) -> None:
        """
        Record recovery attempt for monitoring and debugging.
        
        Args:
            recovery_result: Result of the recovery attempt
        """
        with self._lock:
            self._recovery_history.append(recovery_result)
            # Keep only the last 50 recovery attempts to prevent memory growth
            if len(self._recovery_history) > 50:
                self._recovery_history = self._recovery_history[-50:]
        
        # Log recovery attempt
        if recovery_result.success:
            logger.info(f"Context recovery successful using method: {recovery_result.recovery_method}")
        else:
            logger.warning(f"Context recovery failed using method: {recovery_result.recovery_method}, error: {recovery_result.error_message}")
    
    def get_recovery_statistics(self) -> dict:
        """
        Get statistics about context recovery attempts.
        
        Returns:
            Dictionary with recovery statistics
        """
        with self._lock:
            if not self._recovery_history:
                return {
                    'total_attempts': 0,
                    'successful_attempts': 0,
                    'success_rate': 0.0,
                    'common_methods': {},
                    'recent_failures': []
                }
            
            total_attempts = len(self._recovery_history)
            successful_attempts = sum(1 for r in self._recovery_history if r.success)
            success_rate = (successful_attempts / total_attempts) * 100 if total_attempts > 0 else 0.0
            
            # Count recovery methods
            method_counts = {}
            for recovery in self._recovery_history:
                method = recovery.recovery_method
                method_counts[method] = method_counts.get(method, 0) + 1
            
            # Get recent failures
            recent_failures = [
                {
                    'method': r.recovery_method,
                    'error': r.error_message,
                    'timestamp': r.timestamp.isoformat()
                }
                for r in self._recovery_history[-10:] if not r.success
            ]
            
            return {
                'total_attempts': total_attempts,
                'successful_attempts': successful_attempts,
                'success_rate': success_rate,
                'common_methods': method_counts,
                'recent_failures': recent_failures
            }
    
    def ensure_context(self, func: Callable) -> Callable:
        """
        Enhanced decorator to ensure Flask application context for a function.
        
        This decorator validates context before method execution, creates context
        when needed, and includes comprehensive error handling for context failures.
        
        Args:
            func: Function to wrap with context
            
        Returns:
            Wrapped function that runs with guaranteed Flask context
            
        Example:
            @context_manager.ensure_context
            def my_background_task():
                # This function can now safely access current_app, db, etc.
                return current_app.config['SOME_VALUE']
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            # First, validate existing context
            if self.validate_context():
                logger.debug(f"Function {func.__name__} has valid app context")
                try:
                    return func(*args, **kwargs)
                except RuntimeError as e:
                    if "working outside of application context" in str(e).lower():
                        # Context became invalid during execution, attempt recovery
                        logger.warning(f"Context became invalid during {func.__name__} execution, attempting recovery")
                        return self._execute_with_context_recovery(func, e, *args, **kwargs)
                    raise
            
            # No valid context, need to create one
            logger.debug(f"Creating app context for function {func.__name__}")
            return self._create_context_and_execute(func, *args, **kwargs)
        
        return wrapper
    
    def _create_context_and_execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Create application context and execute function with error handling.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of function execution
            
        Raises:
            Exception: If context creation fails or function execution fails
        """
        try:
            with self.app.app_context():
                # Validate that context was created successfully
                if not self.validate_context():
                    raise RuntimeError(f"Failed to create valid application context for {func.__name__}")
                
                logger.debug(f"Successfully created context for {func.__name__}")
                return func(*args, **kwargs)
                
        except Exception as e:
            # Enhanced error handling with context information
            context_state = self.get_context_state()
            error_context = {
                'function_name': func.__name__, 
                'error_type': type(e).__name__,
                'service_name': 'Application Context Manager',
                'context_state': context_state.to_dict(),
                'recovery_attempt': False
            }
            
            # Use rate limiting and improved error messages
            error_limiter = get_error_rate_limiter()
            if error_limiter.should_log_error(
                'ContextCreationError',
                f"Error creating context for {func.__name__}: {str(e)}",
                context=error_context
            ):
                log_actionable_error(
                    e,
                    context=error_context,
                    log_level='error',
                    logger_name=__name__
                )
            raise
    
    def _execute_with_context_recovery(self, func: Callable, original_error: Exception, *args, **kwargs) -> Any:
        """
        Attempt to recover from context errors and re-execute function.
        
        Args:
            func: Function to execute
            original_error: The original context error
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of function execution
            
        Raises:
            Exception: If recovery fails
        """
        recovery_result = self.handle_context_error(original_error, func.__name__)
        
        if recovery_result.success:
            try:
                logger.info(f"Context recovery successful for {func.__name__}, retrying execution")
                return func(*args, **kwargs)
            except Exception as retry_error:
                # Recovery succeeded but function still failed
                error_context = {
                    'function_name': func.__name__,
                    'original_error': str(original_error),
                    'retry_error': str(retry_error),
                    'recovery_method': recovery_result.recovery_method
                }
                
                error_limiter = get_error_rate_limiter()
                if error_limiter.should_log_error(
                    'PostRecoveryExecutionError',
                    f"Function {func.__name__} failed after successful context recovery: {str(retry_error)}",
                    context=error_context
                ):
                    logger.error(f"Function {func.__name__} failed after context recovery: {retry_error}")
                raise retry_error
        else:
            # Recovery failed, log and re-raise original error
            logger.error(f"Context recovery failed for {func.__name__}: {recovery_result.error_message}")
            raise original_error
    
    def run_with_context(self, func: Callable, *args, **kwargs) -> Any:
        """
        Run a function with guaranteed application context.
        
        This method is useful for running functions that need Flask context
        without using the decorator pattern.
        
        Args:
            func: Function to run
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call
            
        Example:
            result = context_manager.run_with_context(
                some_database_operation, 
                param1="value1"
            )
        """
        if has_app_context():
            logger.debug(f"Running {func.__name__} with existing app context")
            return func(*args, **kwargs)
        
        logger.debug(f"Running {func.__name__} with new app context")
        with self.app.app_context():
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Use rate limiting for context-related errors
                error_limiter = get_error_rate_limiter()
                if error_limiter.should_log_error(
                    'ApplicationContextError',
                    f"Error running {func.__name__} with app context: {str(e)}",
                    context={'function_name': func.__name__, 'error_type': type(e).__name__}
                ):
                    logger.error(f"Error running {func.__name__} with app context: {e}")
                raise
    
    @contextmanager
    def create_background_context(self) -> ContextManager:
        """
        Create a context manager for background tasks.
        
        This is useful for long-running background tasks that need to maintain
        Flask context throughout their execution.
        
        Returns:
            Context manager that provides Flask application context
            
        Example:
            with context_manager.create_background_context():
                # Long-running background task
                while True:
                    # Can safely access Flask resources here
                    config_value = current_app.config['SOME_VALUE']
                    time.sleep(60)
        """
        if has_app_context():
            logger.debug("Using existing app context for background task")
            yield
        else:
            logger.debug("Creating new app context for background task")
            with self.app.app_context():
                try:
                    yield
                except Exception as e:
                    # Use rate limiting for background context errors
                    error_limiter = get_error_rate_limiter()
                    if error_limiter.should_log_error(
                        'BackgroundContextError',
                        f"Error in background context: {str(e)}",
                        context={'error_type': type(e).__name__}
                    ):
                        logger.error(f"Error in background context: {e}")
                    raise
    
    def safe_context_operation(self, func: Callable) -> Callable:
        """
        Decorator for operations that should gracefully handle context errors.
        
        This decorator catches "Working outside of application context" errors
        and attempts to retry the operation with proper context. If that fails,
        it logs the error and returns None instead of crashing.
        
        Args:
            func: Function to wrap with safe context handling
            
        Returns:
            Wrapped function that handles context errors gracefully
            
        Example:
            @context_manager.safe_context_operation
            def optional_background_task():
                # This task won't crash the application if context fails
                return current_app.config.get('OPTIONAL_VALUE')
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # First attempt - try normal execution
                return func(*args, **kwargs)
            except RuntimeError as e:
                if "working outside of application context" in str(e).lower():
                    # Use rate limiting and improved error messages for context errors
                    error_limiter = get_error_rate_limiter()
                    context = {
                        'function_name': func.__name__, 
                        'retry_attempt': True,
                        'service_name': 'Flask Application Context'
                    }
                    
                    if error_limiter.should_log_error(
                        'WorkingOutsideApplicationContextError',
                        f"Context error in {func.__name__}: {str(e)}",
                        context=context
                    ):
                        log_actionable_error(
                            e,
                            context=context,
                            log_level='warning',
                            logger_name=__name__
                        )
                    
                    try:
                        # Second attempt - with explicit context
                        return self.run_with_context(func, *args, **kwargs)
                    except Exception as retry_error:
                        # Use rate limiting for retry failures
                        retry_context = {
                            'function_name': func.__name__, 
                            'original_error': str(e), 
                            'retry_error': str(retry_error),
                            'service_name': 'Flask Application Context'
                        }
                        
                        if error_limiter.should_log_error(
                            'ContextRetryFailedError',
                            f"Failed to run {func.__name__} even with context: {str(retry_error)}",
                            context=retry_context
                        ):
                            log_actionable_error(
                                retry_error,
                                context=retry_context,
                                log_level='error',
                                logger_name=__name__
                            )
                        return None
                else:
                    # Different RuntimeError, re-raise
                    raise
            except Exception as e:
                # Use rate limiting for unexpected errors
                error_limiter = get_error_rate_limiter()
                context = {
                    'function_name': func.__name__, 
                    'error_type': type(e).__name__,
                    'service_name': 'Application Context Manager'
                }
                
                if error_limiter.should_log_error(
                    'UnexpectedContextError',
                    f"Unexpected error in {func.__name__}: {str(e)}",
                    context=context
                ):
                    log_actionable_error(
                        e,
                        context=context,
                        log_level='error',
                        logger_name=__name__
                    )
                raise
        
        return wrapper
    
    def start_background_service(self, service_func: Callable, *args, **kwargs) -> threading.Thread:
        """
        Start a background service with proper context management.
        
        This method creates and starts a daemon thread that runs the service
        function with proper Flask application context.
        
        Args:
            service_func: Function to run as background service
            *args: Positional arguments for the service function
            **kwargs: Keyword arguments for the service function
            
        Returns:
            Thread object for the background service
            
        Example:
            def my_monitoring_service():
                while True:
                    # Monitor something
                    time.sleep(30)
            
            thread = context_manager.start_background_service(my_monitoring_service)
        """
        def service_wrapper():
            """Wrapper that ensures context for the entire service lifecycle."""
            logger.info(f"Starting background service: {service_func.__name__}")
            
            with self.create_background_context():
                try:
                    service_func(*args, **kwargs)
                except Exception as e:
                    # Use rate limiting for background service errors
                    error_limiter = get_error_rate_limiter()
                    if error_limiter.should_log_error(
                        'BackgroundServiceError',
                        f"Background service {service_func.__name__} failed: {str(e)}",
                        context={'service_name': service_func.__name__, 'error_type': type(e).__name__}
                    ):
                        logger.error(f"Background service {service_func.__name__} failed: {e}")
                finally:
                    logger.info(f"Background service {service_func.__name__} stopped")
        
        thread = threading.Thread(target=service_wrapper, daemon=True)
        thread.start()
        
        logger.info(f"Background service {service_func.__name__} started in thread {thread.ident}")
        return thread
    
    def create_periodic_task(self, func: Callable, interval_seconds: int, *args, **kwargs) -> threading.Thread:
        """
        Create a periodic task that runs with proper context.
        
        This method creates a background thread that runs the specified function
        at regular intervals with proper Flask application context.
        
        Args:
            func: Function to run periodically
            interval_seconds: Interval between executions in seconds
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Thread object for the periodic task
            
        Example:
            def health_check():
                # Perform health check
                pass
            
            thread = context_manager.create_periodic_task(health_check, 60)
        """
        def periodic_wrapper():
            """Wrapper that runs the function periodically with context."""
            logger.info(f"Starting periodic task: {func.__name__} (interval: {interval_seconds}s)")
            
            while True:
                try:
                    with self.create_background_context():
                        logger.debug(f"Running periodic task: {func.__name__}")
                        func(*args, **kwargs)
                except Exception as e:
                    # Use rate limiting for periodic task errors
                    error_limiter = get_error_rate_limiter()
                    if error_limiter.should_log_error(
                        'PeriodicTaskError',
                        f"Periodic task {func.__name__} failed: {str(e)}",
                        context={'task_name': func.__name__, 'error_type': type(e).__name__, 'interval': interval_seconds}
                    ):
                        logger.error(f"Periodic task {func.__name__} failed: {e}")
                
                time.sleep(interval_seconds)
        
        thread = threading.Thread(target=periodic_wrapper, daemon=True)
        thread.start()
        
        logger.info(f"Periodic task {func.__name__} started in thread {thread.ident}")
        return thread
    
    def get_context_info(self) -> dict:
        """
        Get information about the current context state.
        
        Returns:
            Dictionary with context information
        """
        return {
            'has_app_context': has_app_context(),
            'app_name': self.app.name if self.app else None,
            'context_stack_size': len(self._context_stack),
            'current_thread': threading.current_thread().ident
        }


# Global instance - will be initialized when app is created
context_manager: Optional[ApplicationContextManager] = None


def init_context_manager(app: Flask) -> ApplicationContextManager:
    """
    Initialize the global context manager with a Flask app.
    
    Args:
        app: Flask application instance
        
    Returns:
        Initialized ApplicationContextManager instance
    """
    global context_manager
    context_manager = ApplicationContextManager(app)
    logger.info("Global ApplicationContextManager initialized")
    return context_manager


def get_context_manager() -> Optional[ApplicationContextManager]:
    """
    Get the global context manager instance.
    
    Returns:
        ApplicationContextManager instance or None if not initialized
    """
    return context_manager


# Convenience decorators using global context manager
def with_app_context(func: Callable) -> Callable:
    """
    Convenience decorator using global context manager.
    
    Args:
        func: Function to wrap with context
        
    Returns:
        Wrapped function
    """
    if context_manager is None:
        logger.warning("Context manager not initialized, decorator may not work properly")
        return func
    
    return context_manager.ensure_context(func)


def safe_context(func: Callable) -> Callable:
    """
    Convenience decorator for safe context operations using global context manager.
    
    Args:
        func: Function to wrap with safe context handling
        
    Returns:
        Wrapped function
    """
    if context_manager is None:
        logger.warning("Context manager not initialized, decorator may not work properly")
        return func
    
    return context_manager.safe_context_operation(func)