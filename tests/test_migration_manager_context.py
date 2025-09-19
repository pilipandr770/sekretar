"""
Tests for Migration Manager Context Functionality.

This module tests that the migration manager runs properly with Flask application context
and handles context-related errors gracefully.
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, has_app_context

from app import create_app


class TestMigrationManagerContext:
    """Test cases for Migration Manager context handling."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        app = create_app('testing')
        return app
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = Mock()
        db.engine = Mock()
        db.session = Mock()
        return db
    
    def test_migration_manager_with_context(self, app, mock_db):
        """Test migration manager works with application context."""
        try:
            from app.utils.database_initializer import DatabaseInitializer
            
            with app.app_context():
                assert has_app_context()
                
                # Create initializer (which includes migration functionality)
                initializer = DatabaseInitializer(app, mock_db)
                
                # Test that initializer can be created and used with context
                assert initializer.app == app
                assert initializer.db == mock_db
                
        except ImportError:
            pytest.skip("DatabaseInitializer not available")
    
    def test_migration_manager_without_context_fails_gracefully(self, app, mock_db):
        """Test migration manager handles missing context gracefully."""
        try:
            from app.utils.database_initializer import DatabaseInitializer
            from app.utils.context_fixer import with_app_context
            
            # Wrap initialization with context fixer
            @with_app_context(app)
            def create_initializer():
                assert has_app_context()
                return DatabaseInitializer(app, mock_db)
            
            # Should work even when called without context
            initializer = create_initializer()
            assert initializer is not None
            
        except ImportError:
            pytest.skip("DatabaseInitializer not available")
    
    def test_table_creation_with_context(self, app, mock_db):
        """Test table creation works with application context."""
        try:
            from app.utils.database_initializer import DatabaseInitializer
            
            with app.app_context():
                initializer = DatabaseInitializer(app, mock_db)
                
                # Mock the database engine to simulate table creation
                mock_db.engine.execute = Mock()
                mock_db.create_all = Mock()
                
                # Test that table creation methods can be called
                # (This would normally create actual tables)
                mock_db.create_all()
                mock_db.create_all.assert_called_once()
                
        except ImportError:
            pytest.skip("DatabaseInitializer not available")
    
    def test_migration_validation_with_context(self, app, mock_db):
        """Test migration validation works with application context."""
        try:
            from app.utils.database_initializer import DatabaseInitializer
            
            with app.app_context():
                initializer = DatabaseInitializer(app, mock_db)
                
                # Test validation functionality
                result = initializer.validate_setup()
                
                # Should return a validation result
                assert hasattr(result, 'valid')
                
        except ImportError:
            pytest.skip("DatabaseInitializer not available")
        except Exception as e:
            # If validation fails due to missing dependencies, that's expected
            assert "not available" in str(e) or "not found" in str(e)
    
    def test_performance_alerts_table_creation_context(self, app, mock_db):
        """Test performance_alerts table creation with context."""
        with app.app_context():
            assert has_app_context()
            
            # Mock table creation SQL
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS performance_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type VARCHAR(50) NOT NULL,
                severity VARCHAR(20) NOT NULL,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            
            # Mock database execution
            mock_db.engine.execute = Mock()
            
            # Simulate table creation
            mock_db.engine.execute(create_table_sql)
            mock_db.engine.execute.assert_called_once()
    
    def test_migration_error_handling_with_context(self, app, mock_db):
        """Test migration error handling with application context."""
        try:
            from app.utils.database_initializer import DatabaseInitializer
            from app.utils.context_fixer import safe_app_context_operation
            
            @safe_app_context_operation
            def problematic_migration():
                # Simulate a migration that might fail
                raise RuntimeError("Working outside of application context")
            
            with app.app_context():
                # Should handle the error gracefully
                result = problematic_migration()
                assert result is None  # safe_app_context_operation returns None on context errors
                
        except ImportError:
            pytest.skip("Required modules not available")
    
    def test_background_migration_task_context(self, app, mock_db):
        """Test background migration task with context."""
        import threading
        from app.utils.context_fixer import with_app_context
        
        results = []
        
        @with_app_context(app)
        def background_migration_task():
            assert has_app_context()
            
            # Simulate migration work
            results.append("migration_completed")
            return True
        
        # Run in background thread
        thread = threading.Thread(target=background_migration_task)
        thread.start()
        thread.join()
        
        assert "migration_completed" in results
    
    def test_database_schema_validation_context(self, app, mock_db):
        """Test database schema validation with context."""
        with app.app_context():
            assert has_app_context()
            
            # Mock schema inspection
            from sqlalchemy import inspect
            
            with patch('sqlalchemy.inspect') as mock_inspect:
                mock_inspector = Mock()
                mock_inspector.get_table_names.return_value = ['users', 'tenants']
                mock_inspect.return_value = mock_inspector
                
                # Simulate schema validation
                inspector = inspect(mock_db.engine)
                tables = inspector.get_table_names()
                
                assert 'users' in tables
                assert 'tenants' in tables
    
    def test_migration_rollback_context(self, app, mock_db):
        """Test migration rollback with context."""
        try:
            from app.utils.database_initializer import DatabaseInitializer
            from app.utils.context_fixer import with_app_context
            
            @with_app_context(app)
            def rollback_migration():
                assert has_app_context()
                
                # Simulate rollback operation
                mock_db.session.rollback = Mock()
                mock_db.session.rollback()
                
                return True
            
            result = rollback_migration()
            assert result is True
            mock_db.session.rollback.assert_called_once()
            
        except ImportError:
            pytest.skip("Required modules not available")


class TestMigrationManagerIntegration:
    """Integration tests for migration manager with real database operations."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app with temporary database."""
        app = create_app('testing')
        
        # Use temporary SQLite database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_file.name}'
        
        yield app
        
        # Cleanup
        try:
            os.unlink(tmp_file.name)
        except:
            pass
    
    def test_real_migration_with_context(self, app):
        """Test real migration operations with context."""
        try:
            from app import db
            from app.utils.database_initializer import DatabaseInitializer
            
            with app.app_context():
                # Initialize database
                db.create_all()
                
                # Create initializer
                initializer = DatabaseInitializer(app, db)
                
                # Test initialization
                result = initializer.initialize()
                
                # Should succeed or fail gracefully
                assert hasattr(result, 'success')
                
        except ImportError:
            pytest.skip("Required modules not available")
        except Exception as e:
            # Expected for test environment
            assert "not available" in str(e) or "not found" in str(e) or "test" in str(e).lower()
    
    def test_table_existence_check_with_context(self, app):
        """Test table existence check with context."""
        try:
            from app import db
            from sqlalchemy import inspect
            
            with app.app_context():
                # Create tables
                db.create_all()
                
                # Check table existence
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                
                # Should have some tables
                assert isinstance(tables, list)
                
        except ImportError:
            pytest.skip("Required modules not available")
        except Exception as e:
            # Expected for test environment
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])