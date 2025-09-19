"""
Comprehensive tests for Application Context Fixes.

This module tests the ApplicationContextManager and related context fixing utilities
to ensure background services work without Flask application context errors.
"""
import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, has_app_context, current_app
from werkzeug.test import Client

from app import create_app
from app.utils.context_fixer import (
    ContextFixer, 
    with_app_context, 
    safe_app_context_operation,
    ensure_app_context,
    ContextFixResult
)


class TestContextFixer:
    """Test cases for ContextFixer class."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        app = create_app('testing')
        return app
    
    @pytest.fixture
    def context_fixer(self, app):
        """Create ContextFixer instance."""
        return ContextFixer(app)
    
    def test_context_fixer_initialization(self, app):
        """Test ContextFixer initialization."""
        fixer = ContextFixer(app)
        
        assert fixer.app == app
        assert fixer.fixed_issues == []
        assert fixer.remaining_issues == []
        assert fixer.errors == []
        assert fixer.warnings == []
    
    def test_context_fixer_without_app(self):
        """Test ContextFixer initialization without app."""
        fixer = ContextFixer()
        
        assert fixer.app is None
        assert fixer.fixed_issues == []
    
    def test_fix_all_context_issues_success(self, context_fixer):
        """Test successful context fixes."""
        with context_fixer.app.app_context():
            result = context_fixer.fix_all_context_issues()
            
            assert isinstance(result, ContextFixResult)
            assert result.success is True
            assert isinstance(result.fixed_issues, list)
            assert isinstance(result.remaining_issues, list)
            assert isinstance(result.errors, list)
            assert isinstance(result.warnings, list)
    
    def test_fix_all_context_issues_with_errors(self, context_fixer):
        """Test context fixes with errors."""
        # Mock a method to raise an exception
        with patch.object(context_fixer, '_perform_context_fixes', side_effect=Exception("Test error")):
            result = context_fixer.fix_all_context_issues()
            
            assert result.success is False
            assert len(result.errors) > 0
            assert "Test error" in result.errors[0]
    
    def test_wrap_with_app_context_with_existing_context(self, context_fixer):
        """Test wrapping function when app context already exists."""
        def test_function():
            return "test_result"
        
        wrapped_function = context_fixer._wrap_with_app_context(test_function)
        
        with context_fixer.app.app_context():
            result = wrapped_function()
            assert result == "test_result"
    
    def test_wrap_with_app_context_without_existing_context(self, context_fixer):
        """Test wrapping function when no app context exists."""
        def test_function():
            assert has_app_context()
            return "test_result"
        
        wrapped_function = context_fixer._wrap_with_app_context(test_function)
        
        # Call without app context
        result = wrapped_function()
        assert result == "test_result"
    
    def test_wrap_with_app_context_no_app_available(self):
        """Test wrapping function when no app is available."""
        fixer = ContextFixer()  # No app provided
        
        def test_function():
            return "test_result"
        
        wrapped_function = fixer._wrap_with_app_context(test_function)
        
        # Should return None when no app context available
        result = wrapped_function()
        assert result is None


class TestContextDecorators:
    """Test cases for context decorators."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        app = create_app('testing')
        return app
    
    def test_with_app_context_decorator_with_existing_context(self, app):
        """Test with_app_context decorator when context exists."""
        @with_app_context(app)
        def test_function():
            assert has_app_context()
            return "success"
        
        with app.app_context():
            result = test_function()
            assert result == "success"
    
    def test_with_app_context_decorator_without_existing_context(self, app):
        """Test with_app_context decorator when no context exists."""
        @with_app_context(app)
        def test_function():
            assert has_app_context()
            return "success"
        
        # Call without app context
        result = test_function()
        assert result == "success"
    
    def test_with_app_context_decorator_no_app_provided(self, app):
        """Test with_app_context decorator without app parameter."""
        @with_app_context()
        def test_function():
            assert has_app_context()
            return "success"
        
        with app.app_context():
            result = test_function()
            assert result == "success"
    
    def test_safe_app_context_operation_success(self):
        """Test safe_app_context_operation decorator with successful operation."""
        @safe_app_context_operation
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
    
    def test_safe_app_context_operation_context_error(self):
        """Test safe_app_context_operation decorator with context error."""
        @safe_app_context_operation
        def test_function():
            raise RuntimeError("Working outside of application context")
        
        result = test_function()
        assert result is None
    
    def test_safe_app_context_operation_other_error(self):
        """Test safe_app_context_operation decorator with non-context error."""
        @safe_app_context_operation
        def test_function():
            raise ValueError("Different error")
        
        with pytest.raises(ValueError):
            test_function()
    
    def test_ensure_app_context_manager_with_existing_context(self, app):
        """Test ensure_app_context context manager when context exists."""
        with app.app_context():
            with ensure_app_context(app):
                assert has_app_context()
    
    def test_ensure_app_context_manager_without_existing_context(self, app):
        """Test ensure_app_context context manager when no context exists."""
        with ensure_app_context(app):
            assert has_app_context()


class TestBackgroundServiceContextFixes:
    """Test cases for background service context fixes."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        app = create_app('testing')
        return app
    
    def test_background_task_with_context_fix(self, app):
        """Test background task with context fix."""
        results = []
        
        @with_app_context(app)
        def background_task():
            assert has_app_context()
            results.append("task_completed")
        
        # Run in separate thread to simulate background service
        thread = threading.Thread(target=background_task)
        thread.start()
        thread.join()
        
        assert "task_completed" in results
    
    def test_health_check_with_context_fix(self, app):
        """Test health check with context fix."""
        @with_app_context(app)
        def health_check():
            assert has_app_context()
            # Simulate database health check
            return {"status": "healthy"}
        
        result = health_check()
        assert result["status"] == "healthy"
    
    def test_monitoring_service_with_context_fix(self, app):
        """Test monitoring service with context fix."""
        monitoring_results = []
        
        @with_app_context(app)
        def monitoring_task():
            assert has_app_context()
            monitoring_results.append("monitoring_completed")
        
        # Simulate periodic monitoring
        monitoring_task()
        
        assert "monitoring_completed" in monitoring_results
    
    def test_database_migration_with_context_fix(self, app):
        """Test database migration with context fix."""
        @with_app_context(app)
        def migration_task():
            assert has_app_context()
            # Simulate database migration
            return {"migrations_applied": 1}
        
        result = migration_task()
        assert result["migrations_applied"] == 1


class TestContextErrorScenarios:
    """Test cases for various context error scenarios."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        app = create_app('testing')
        return app
    
    def test_database_operation_without_context(self, app):
        """Test database operation that would fail without context."""
        def problematic_database_operation():
            # This would normally raise "Working outside of application context"
            raise RuntimeError("Working outside of application context")
        
        @safe_app_context_operation
        def safe_database_operation():
            problematic_database_operation()
        
        # Should return None instead of raising error
        result = safe_database_operation()
        assert result is None
    
    def test_service_initialization_without_context(self, app):
        """Test service initialization that would fail without context."""
        initialization_attempts = []
        
        @with_app_context(app)
        def initialize_service():
            assert has_app_context()
            initialization_attempts.append("initialized")
            return True
        
        # Should succeed even when called without context
        result = initialize_service()
        assert result is True
        assert "initialized" in initialization_attempts
    
    def test_concurrent_context_operations(self, app):
        """Test concurrent operations with context fixes."""
        results = []
        
        @with_app_context(app)
        def concurrent_task(task_id):
            assert has_app_context()
            time.sleep(0.1)  # Simulate work
            results.append(f"task_{task_id}_completed")
        
        # Run multiple tasks concurrently
        threads = []
        for i in range(3):
            thread = threading.Thread(target=concurrent_task, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        assert len(results) == 3
        assert all(f"task_{i}_completed" in results for i in range(3))


class TestIntegrationWithExistingServices:
    """Integration tests with existing services."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        app = create_app('testing')
        return app
    
    def test_health_validator_context_integration(self, app):
        """Test integration with HealthValidator."""
        try:
            from app.utils.health_validator import HealthValidator
            
            @with_app_context(app)
            def test_health_validation():
                assert has_app_context()
                validator = HealthValidator(app, None)
                # Test that validator can be created with context
                return True
            
            result = test_health_validation()
            assert result is True
            
        except ImportError:
            pytest.skip("HealthValidator not available")
    
    def test_database_initializer_context_integration(self, app):
        """Test integration with DatabaseInitializer."""
        try:
            from app.utils.database_initializer import DatabaseInitializer
            
            @with_app_context(app)
            def test_database_initialization():
                assert has_app_context()
                initializer = DatabaseInitializer(app, None)
                # Test that initializer can be created with context
                return True
            
            result = test_database_initialization()
            assert result is True
            
        except ImportError:
            pytest.skip("DatabaseInitializer not available")
    
    def test_service_health_monitor_context_integration(self, app):
        """Test integration with ServiceHealthMonitor."""
        try:
            from app.utils.service_health_monitor import ServiceHealthMonitor
            
            @with_app_context(app)
            def test_service_monitoring():
                assert has_app_context()
                monitor = ServiceHealthMonitor(app)
                # Test that monitor can be created with context
                return True
            
            result = test_service_monitoring()
            assert result is True
            
        except ImportError:
            pytest.skip("ServiceHealthMonitor not available")


class TestContextFixerPerformance:
    """Performance tests for context fixes."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        app = create_app('testing')
        return app
    
    def test_context_wrapper_performance(self, app):
        """Test performance impact of context wrapper."""
        @with_app_context(app)
        def simple_task():
            return "completed"
        
        # Measure time for multiple calls
        start_time = time.time()
        for _ in range(100):
            result = simple_task()
            assert result == "completed"
        end_time = time.time()
        
        # Should complete quickly (less than 1 second for 100 calls)
        assert (end_time - start_time) < 1.0
    
    def test_concurrent_context_performance(self, app):
        """Test performance of concurrent context operations."""
        results = []
        
        @with_app_context(app)
        def concurrent_task():
            results.append("completed")
        
        start_time = time.time()
        
        # Run 10 concurrent tasks
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=concurrent_task)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        assert len(results) == 10
        # Should complete quickly (less than 2 seconds)
        assert (end_time - start_time) < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])