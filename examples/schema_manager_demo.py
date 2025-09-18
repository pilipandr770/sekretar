#!/usr/bin/env python3
"""
Schema Manager Demo

This script demonstrates the SchemaManager functionality with the actual
AI Secretary application models.
"""
import os
import sys
import tempfile
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.utils.schema_manager import SchemaManager, get_schema_manager


def create_demo_app():
    """Create a demo Flask application with SQLite database."""
    app = Flask(__name__)
    
    # Use a temporary SQLite database
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_file.close()
    
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_file.name}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True
    
    return app, db_file.name


def demo_schema_manager():
    """Demonstrate SchemaManager functionality."""
    print("🔧 Schema Manager Demo")
    print("=" * 50)
    
    # Create demo app and database
    app, db_path = create_demo_app()
    
    try:
        with app.app_context():
            # Initialize database
            db = SQLAlchemy()
            db.init_app(app)
            
            # Import models to register them with SQLAlchemy
            print("📦 Importing application models...")
            from app.models import (
                User, Tenant, Role, Contact, Pipeline, Stage, Lead, Task, Note,
                KnowledgeSource, Document, Chunk, Plan, Subscription
            )
            
            # Create schema manager
            print("🔧 Creating schema manager...")
            schema_manager = SchemaManager(app, db)
            
            # Check initial schema state
            print("\n📊 Initial Schema State:")
            print(f"   Schema exists: {schema_manager.check_schema_exists()}")
            
            missing_tables = schema_manager.get_missing_tables()
            print(f"   Missing tables: {len(missing_tables)}")
            if missing_tables:
                print(f"   First 5 missing: {missing_tables[:5]}")
            
            existing_tables = schema_manager.get_existing_tables()
            print(f"   Existing tables: {len(existing_tables)}")
            
            # Validate schema
            print("\n🔍 Schema Validation:")
            validation_result = schema_manager.validate_schema()
            print(f"   Valid: {validation_result.valid}")
            print(f"   Issues found: {len(validation_result.issues)}")
            print(f"   Severity: {validation_result.severity.value}")
            
            if validation_result.issues:
                print("   Sample issues:")
                for issue in validation_result.issues[:3]:
                    print(f"     - {issue.issue_type}: {issue.message}")
            
            # Create schema
            print("\n🏗️  Creating Schema:")
            creation_success = schema_manager.create_schema()
            print(f"   Creation successful: {creation_success}")
            
            if creation_success:
                # Check schema after creation
                print("\n📊 Schema State After Creation:")
                print(f"   Schema exists: {schema_manager.check_schema_exists()}")
                
                existing_tables = schema_manager.get_existing_tables()
                print(f"   Existing tables: {len(existing_tables)}")
                
                missing_tables = schema_manager.get_missing_tables()
                print(f"   Missing tables: {len(missing_tables)}")
                
                # Validate schema again
                print("\n🔍 Post-Creation Validation:")
                validation_result = schema_manager.validate_schema()
                print(f"   Valid: {validation_result.valid}")
                print(f"   Issues found: {len(validation_result.issues)}")
                print(f"   Tables checked: {validation_result.tables_checked}")
                print(f"   Tables valid: {validation_result.tables_valid}")
                
                # Get detailed schema info
                print("\n📋 Detailed Schema Information:")
                schema_info = schema_manager.get_schema_info()
                print(f"   Database type: {schema_info.database_type}")
                print(f"   Total tables: {schema_info.total_tables}")
                print(f"   Existing tables: {len(schema_info.existing_tables)}")
                
                # Show some table details
                if schema_info.table_details:
                    print("   Sample table details:")
                    for table_name, details in list(schema_info.table_details.items())[:3]:
                        if isinstance(details, dict) and 'columns' in details:
                            print(f"     - {table_name}: {details['columns']} columns")
                
                # Test repair functionality (should report no repairs needed)
                print("\n🔧 Schema Repair Test:")
                repair_result = schema_manager.repair_schema()
                print(f"   Repair successful: {repair_result.success}")
                print(f"   Repairs attempted: {len(repair_result.repairs_attempted)}")
                print(f"   Repairs successful: {len(repair_result.repairs_successful)}")
                
                if repair_result.warnings:
                    print(f"   Warnings: {repair_result.warnings[0]}")
                
                # Test individual table operations
                print("\n🔧 Individual Table Operations:")
                
                # Test table existence
                test_table = 'users' if 'users' in existing_tables else existing_tables[0] if existing_tables else None
                if test_table:
                    print(f"   Table '{test_table}' exists: {schema_manager._table_exists(test_table)}")
                    
                    # Test table recreation
                    print(f"   Recreating table '{test_table}'...")
                    recreate_success = schema_manager.recreate_table(test_table)
                    print(f"   Recreation successful: {recreate_success}")
                    
                    # Verify table still exists
                    print(f"   Table '{test_table}' exists after recreation: {schema_manager._table_exists(test_table)}")
            
            else:
                print("   ❌ Schema creation failed")
                
                # Try repair
                print("\n🔧 Attempting Schema Repair:")
                repair_result = schema_manager.repair_schema()
                print(f"   Repair successful: {repair_result.success}")
                print(f"   Repairs attempted: {len(repair_result.repairs_attempted)}")
                print(f"   Repairs successful: {len(repair_result.repairs_successful)}")
                print(f"   Repairs failed: {len(repair_result.repairs_failed)}")
                
                if repair_result.errors:
                    print("   Errors:")
                    for error in repair_result.errors:
                        print(f"     - {error}")
            
            print("\n✅ Schema Manager Demo Complete!")
            
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean up temporary database file
        try:
            os.unlink(db_path)
            print(f"🧹 Cleaned up temporary database: {db_path}")
        except Exception as e:
            print(f"⚠️  Could not clean up database file: {e}")


def demo_get_schema_manager_function():
    """Demonstrate the get_schema_manager function."""
    print("\n🔧 get_schema_manager() Function Demo")
    print("=" * 50)
    
    app, db_path = create_demo_app()
    
    try:
        with app.app_context():
            db = SQLAlchemy()
            db.init_app(app)
            
            # Import a few models
            from app.models import User, Tenant
            
            # Get schema manager using the function
            manager1 = get_schema_manager(app, db)
            manager2 = get_schema_manager(app, db)
            
            print(f"   Manager 1 ID: {id(manager1)}")
            print(f"   Manager 2 ID: {id(manager2)}")
            print(f"   Same instance: {manager1 is manager2}")
            
            # Test functionality
            print(f"   Schema exists: {manager1.check_schema_exists()}")
            print(f"   Missing tables: {len(manager1.get_missing_tables())}")
            
    except Exception as e:
        print(f"❌ Function demo failed: {e}")
        
    finally:
        try:
            os.unlink(db_path)
        except Exception:
            pass


if __name__ == "__main__":
    demo_schema_manager()
    demo_get_schema_manager_function()