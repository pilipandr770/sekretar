"""
Tests for Schema Manager

This module tests the schema management functionality including
table existence checking, schema creation, validation, and repair.
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from app.utils.schema_manager import (
    SchemaManager, ValidationSeverity, ValidationIssue, ValidationResult,
    RepairResult, SchemaInfo, get_schema_manager
)


@pytest.fixture
def app():
    """Create test Flask application."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    return app


@pytest.fixture
def db(app):
    """Create test database."""
    db = SQLAlchemy()
    db.init_app(app)
    
    # Define test models within app context
    with app.app_context():
        class TestUser(db.Model):
            __tablename__ = 'test_users'
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(100), nullable=False)
            email = db.Column(db.String(120), unique=True, nullable=False)
            created_at = db.Column(db.DateTime, nullable=False)
        
        class TestPost(db.Model):
            __tablename__ = 'test_posts'
            id = db.Column(db.Integer, primary_key=True)
            title = db.Column(db.String(200), nullable=False)
            content = db.Column(db.Text)
            user_id = db.Column(db.Integer, db.ForeignKey('test_users.id'), nullable=False)
        
        # Store model classes for reference
        db.TestUser = TestUser
        db.TestPost = TestPost
        
        yield db


@pytest.fixture
def schema_manager(app, db):
    """Create schema manager instance."""
    with app.app_context():
        manager = SchemaManager(app, db)
        yield manager


class TestSchemaManager:
    """Test cases for SchemaManager class."""
    
    def test_initialization(self, app, db):
        """Test schema manager initialization."""
        with app.app_context():
            manager = SchemaManager(app, db)
            
            assert manager.app == app
            assert manager.db == db
            assert manager._metadata is not None
            assert manager._inspector is not None
            assert manager._database_type == 'sqlite'
    
    def test_check_schema_exists_empty_database(self, schema_manager):
        """Test schema existence check with empty database."""
        # Empty database should not have required tables
        assert not schema_manager.check_schema_exists()
    
    def test_check_schema_exists_with_tables(self, schema_manager):
        """Test schema existence check with existing tables."""
        # Create tables first
        schema_manager.db.create_all()
        
        # Now schema should exist
        assert schema_manager.check_schema_exists()
    
    def test_get_missing_tables(self, schema_manager):
        """Test getting list of missing tables."""
        missing_tables = schema_manager.get_missing_tables()
        
        # Should have our test tables as missing
        assert 'test_users' in missing_tables
        assert 'test_posts' in missing_tables
        assert len(missing_tables) >= 2
    
    def test_get_existing_tables(self, schema_manager):
        """Test getting list of existing tables."""
        # Initially no tables
        existing_tables = schema_manager.get_existing_tables()
        assert len(existing_tables) == 0
        
        # Create tables
        schema_manager.db.create_all()
        
        # Now should have tables
        existing_tables = schema_manager.get_existing_tables()
        assert 'test_users' in existing_tables
        assert 'test_posts' in existing_tables
    
    def test_create_schema(self, schema_manager):
        """Test schema creation."""
        # Initially no tables
        assert not schema_manager.check_schema_exists()
        
        # Create schema
        result = schema_manager.create_schema()
        assert result is True
        
        # Now schema should exist
        assert schema_manager.check_schema_exists()
        
        # Verify specific tables exist
        existing_tables = schema_manager.get_existing_tables()
        assert 'test_users' in existing_tables
        assert 'test_posts' in existing_tables
    
    def test_create_table_specific(self, schema_manager):
        """Test creating a specific table."""
        # Initially table doesn't exist
        assert not schema_manager._table_exists('test_users')
        
        # Create specific table
        result = schema_manager.create_table('test_users')
        assert result is True
        
        # Verify table exists
        assert schema_manager._table_exists('test_users')
        
        # Other table should still not exist
        assert not schema_manager._table_exists('test_posts')
    
    def test_create_table_nonexistent(self, schema_manager):
        """Test creating a table that doesn't exist in metadata."""
        result = schema_manager.create_table('nonexistent_table')
        assert result is False
    
    def test_validate_schema_empty_database(self, schema_manager):
        """Test schema validation with empty database."""
        validation_result = schema_manager.validate_schema()
        
        assert not validation_result.valid
        assert validation_result.has_errors
        assert len(validation_result.issues) >= 2  # At least our test tables missing
        
        # Check for missing table issues
        missing_table_issues = [
            issue for issue in validation_result.issues 
            if issue.issue_type == "missing_table"
        ]
        assert len(missing_table_issues) >= 2
        
        # Check severity
        assert validation_result.severity == ValidationSeverity.ERROR
    
    def test_validate_schema_with_tables(self, schema_manager):
        """Test schema validation with existing tables."""
        # Create tables first
        schema_manager.create_schema()
        
        # Validate schema
        validation_result = schema_manager.validate_schema()
        
        assert validation_result.valid
        assert not validation_result.has_critical_issues
        assert validation_result.tables_checked >= 2
        assert validation_result.tables_valid >= 2
    
    def test_repair_schema(self, schema_manager):
        """Test schema repair functionality."""
        # Initially schema is broken (missing tables)
        validation_result = schema_manager.validate_schema()
        assert not validation_result.valid
        
        # Attempt repair
        repair_result = schema_manager.repair_schema()
        
        assert repair_result.success
        assert len(repair_result.repairs_attempted) > 0
        assert len(repair_result.repairs_successful) > 0
        assert len(repair_result.repairs_failed) == 0
        
        # Schema should now be valid
        post_repair_validation = schema_manager.validate_schema()
        assert post_repair_validation.valid
    
    def test_repair_schema_already_valid(self, schema_manager):
        """Test schema repair when schema is already valid."""
        # Create schema first
        schema_manager.create_schema()
        
        # Attempt repair on valid schema
        repair_result = schema_manager.repair_schema()
        
        assert repair_result.success
        assert len(repair_result.repairs_attempted) == 0
        assert len(repair_result.warnings) > 0
        assert "already valid" in repair_result.warnings[0]
    
    def test_get_schema_info(self, schema_manager):
        """Test getting schema information."""
        # Get info for empty database
        schema_info = schema_manager.get_schema_info()
        
        assert schema_info.database_type == 'sqlite'
        assert schema_info.total_tables >= 2
        assert len(schema_info.existing_tables) == 0
        assert len(schema_info.missing_tables) >= 2
        assert 'test_users' in schema_info.missing_tables
        assert 'test_posts' in schema_info.missing_tables
        
        # Create tables and get info again
        schema_manager.create_schema()
        schema_info = schema_manager.get_schema_info()
        
        assert len(schema_info.existing_tables) >= 2
        assert len(schema_info.missing_tables) == 0
        assert 'test_users' in schema_info.existing_tables
        assert 'test_posts' in schema_info.existing_tables
        
        # Check table details
        assert 'test_users' in schema_info.table_details
        assert 'test_posts' in schema_info.table_details
        assert schema_info.table_details['test_users']['columns'] >= 4  # id, name, email, created_at
    
    def test_drop_table(self, schema_manager):
        """Test dropping a table."""
        # Create tables first
        schema_manager.create_schema()
        assert schema_manager._table_exists('test_users')
        
        # Drop table
        result = schema_manager.drop_table('test_users')
        assert result is True
        
        # Verify table is gone
        assert not schema_manager._table_exists('test_users')
        
        # Other table should still exist
        assert schema_manager._table_exists('test_posts')
    
    def test_drop_nonexistent_table(self, schema_manager):
        """Test dropping a table that doesn't exist."""
        result = schema_manager.drop_table('nonexistent_table')
        assert result is True  # Should succeed (table already doesn't exist)
    
    def test_recreate_table(self, schema_manager):
        """Test recreating a table."""
        # Create tables first
        schema_manager.create_schema()
        assert schema_manager._table_exists('test_users')
        
        # Recreate table
        result = schema_manager.recreate_table('test_users')
        assert result is True
        
        # Table should still exist
        assert schema_manager._table_exists('test_users')
    
    def test_get_schema_manager_function(self, app, db):
        """Test the get_schema_manager function."""
        with app.app_context():
            manager1 = get_schema_manager(app, db)
            manager2 = get_schema_manager(app, db)
            
            # Should return the same instance
            assert manager1 is manager2
            assert manager1.app == app
            assert manager1.db == db


class TestValidationIssue:
    """Test cases for ValidationIssue dataclass."""
    
    def test_validation_issue_creation(self):
        """Test creating validation issue."""
        issue = ValidationIssue(
            table_name="test_table",
            issue_type="missing_column",
            message="Column 'name' is missing",
            severity=ValidationSeverity.ERROR,
            suggested_fix="Add column 'name' to table",
            details={"column": "name", "type": "VARCHAR"}
        )
        
        assert issue.table_name == "test_table"
        assert issue.issue_type == "missing_column"
        assert issue.message == "Column 'name' is missing"
        assert issue.severity == ValidationSeverity.ERROR
        assert issue.suggested_fix == "Add column 'name' to table"
        assert issue.details["column"] == "name"


class TestValidationResult:
    """Test cases for ValidationResult dataclass."""
    
    def test_validation_result_properties(self):
        """Test validation result properties."""
        issues = [
            ValidationIssue("table1", "error", "Error message", ValidationSeverity.ERROR),
            ValidationIssue("table2", "warning", "Warning message", ValidationSeverity.WARNING),
            ValidationIssue("table3", "critical", "Critical message", ValidationSeverity.CRITICAL)
        ]
        
        result = ValidationResult(
            valid=False,
            issues=issues,
            tables_checked=3,
            tables_valid=1,
            suggestions=["Fix errors"],
            severity=ValidationSeverity.CRITICAL
        )
        
        assert result.has_critical_issues
        assert result.has_errors
        assert not result.valid
        assert len(result.issues) == 3
    
    def test_validation_result_no_critical_issues(self):
        """Test validation result without critical issues."""
        issues = [
            ValidationIssue("table1", "warning", "Warning message", ValidationSeverity.WARNING),
            ValidationIssue("table2", "info", "Info message", ValidationSeverity.INFO)
        ]
        
        result = ValidationResult(
            valid=True,
            issues=issues,
            tables_checked=2,
            tables_valid=2,
            suggestions=[],
            severity=ValidationSeverity.WARNING
        )
        
        assert not result.has_critical_issues
        assert not result.has_errors
        assert result.valid


class TestSchemaManagerErrorHandling:
    """Test error handling in SchemaManager."""
    
    def test_schema_manager_without_db(self, app):
        """Test schema manager without database."""
        with app.app_context():
            manager = SchemaManager(app, None)
            
            # Should handle missing database gracefully
            assert not manager.check_schema_exists()
            assert not manager.create_schema()
            assert manager.get_missing_tables() == []
            assert manager.get_existing_tables() == []
    
    def test_schema_manager_without_engine(self, app):
        """Test schema manager without database engine."""
        with app.app_context():
            # Create a database instance without initializing it
            db_without_engine = SQLAlchemy()
            # Don't call db_without_engine.init_app(app) so it has no engine
            
            manager = SchemaManager(app, db_without_engine)
            
            # Should handle missing engine gracefully
            assert not manager.create_schema()
            assert not manager.create_table('test_table')
    
    @patch('app.utils.schema_manager.inspect')
    def test_schema_manager_inspector_error(self, mock_inspect, app, db):
        """Test schema manager with inspector errors."""
        mock_inspect.side_effect = Exception("Inspector error")
        
        with app.app_context():
            manager = SchemaManager(app, db)
            
            # Should handle inspector errors gracefully
            validation_result = manager.validate_schema()
            assert not validation_result.valid
            assert validation_result.has_critical_issues