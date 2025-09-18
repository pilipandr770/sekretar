#!/usr/bin/env python3
"""
Migration Runner Demo

This script demonstrates how to use the MigrationRunner class for database migration management.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.migration_runner import MigrationRunner
from flask import Flask


def create_demo_app():
    """Create a demo Flask app for testing."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///demo_migration.db'
    return app


def demo_migration_runner():
    """Demonstrate MigrationRunner functionality."""
    print("🚀 Migration Runner Demo")
    print("=" * 50)
    
    # Create demo app
    app = create_demo_app()
    
    try:
        # Initialize migration runner
        print("\n1. Initializing Migration Runner...")
        runner = MigrationRunner(app=app)
        print("✅ Migration Runner initialized successfully")
        
        # Check current revision
        print("\n2. Checking current database revision...")
        current_rev = runner.get_current_revision()
        print(f"📍 Current revision: {current_rev or 'None (empty database)'}")
        
        # Check for pending migrations
        print("\n3. Checking for pending migrations...")
        pending = runner.check_pending_migrations()
        if pending:
            print(f"📋 Found {len(pending)} pending migrations:")
            for migration in pending:
                info = runner.get_migration_info(migration)
                if info:
                    print(f"  • {migration}: {info.description}")
                else:
                    print(f"  • {migration}: (no description)")
        else:
            print("✅ No pending migrations found")
        
        # Validate migration state
        print("\n4. Validating migration state...")
        validation = runner.validate_migration_state()
        if validation['valid']:
            print("✅ Migration state is valid")
        else:
            print("❌ Migration state has issues:")
            for issue in validation['issues']:
                print(f"  • {issue}")
            
            if validation['warnings']:
                print("⚠️ Warnings:")
                for warning in validation['warnings']:
                    print(f"  • {warning}")
        
        # Get migration history
        print("\n5. Getting migration history...")
        history = runner.get_migration_history()
        if history:
            print(f"📚 Migration history ({len(history)} migrations):")
            for migration in history[:5]:  # Show first 5
                status = "✅ Applied" if migration['is_applied'] else "⏳ Pending"
                head_marker = " (HEAD)" if migration['is_head'] else ""
                print(f"  • {migration['revision']}: {migration['description']} - {status}{head_marker}")
            
            if len(history) > 5:
                print(f"  ... and {len(history) - 5} more migrations")
        else:
            print("📚 No migration history found")
        
        # Demonstrate migration execution (dry run)
        print("\n6. Migration execution simulation...")
        if pending:
            print("🔄 Would run the following migrations:")
            for migration in pending:
                print(f"  • {migration}")
            print("💡 Use runner.run_migrations() to actually execute them")
        else:
            print("✅ No migrations to run")
        
        # Show repair capabilities
        print("\n7. Migration repair capabilities...")
        repair_result = runner.repair_migration_state()
        if repair_result['success']:
            print("✅ Migration state is healthy")
            if repair_result['repairs_performed']:
                print("🔧 Repairs performed:")
                for repair in repair_result['repairs_performed']:
                    print(f"  • {repair}")
        else:
            print("⚠️ Migration state needs attention:")
            for issue in repair_result['issues_found']:
                print(f"  • {issue}")
            
            if repair_result['manual_intervention_required']:
                print("🛠️ Manual intervention required:")
                for intervention in repair_result['manual_intervention_required']:
                    print(f"  • {intervention}")
        
        print("\n✅ Migration Runner Demo completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def demo_migration_operations():
    """Demonstrate specific migration operations."""
    print("\n🔧 Migration Operations Demo")
    print("=" * 50)
    
    app = create_demo_app()
    
    try:
        runner = MigrationRunner(app=app)
        
        # Demonstrate stamping
        print("\n1. Database stamping...")
        print("💡 Stamping allows you to mark the database as being at a specific revision")
        print("   without actually running the migrations")
        
        # Demonstrate rollback (conceptual)
        print("\n2. Migration rollback...")
        print("💡 Rollback allows you to revert to a previous migration state")
        print("   Use runner.rollback_migration('revision_id') to rollback")
        
        # Demonstrate migration creation
        print("\n3. Migration creation...")
        print("💡 Create new migrations with runner.create_migration('description')")
        
        # Show validation features
        print("\n4. Advanced validation...")
        validation = runner.validate_migration_state()
        
        print(f"📊 Validation Summary:")
        print(f"  • Valid: {validation['valid']}")
        print(f"  • Current revision: {validation['current_revision'] or 'None'}")
        print(f"  • Head revisions: {len(validation['head_revisions'])}")
        print(f"  • Pending migrations: {len(validation['pending_migrations'])}")
        print(f"  • Issues found: {len(validation['issues'])}")
        print(f"  • Warnings: {len(validation['warnings'])}")
        
        if validation['orphaned_migrations']:
            print(f"  • Orphaned migrations: {len(validation['orphaned_migrations'])}")
        
        print("\n✅ Migration Operations Demo completed!")
        
    except Exception as e:
        print(f"\n❌ Operations demo failed: {e}")
        return False
    
    return True


if __name__ == '__main__':
    print("🎯 MigrationRunner Comprehensive Demo")
    print("=" * 60)
    
    success = True
    
    # Run basic demo
    if not demo_migration_runner():
        success = False
    
    # Run operations demo
    if not demo_migration_operations():
        success = False
    
    if success:
        print("\n🎉 All demos completed successfully!")
        print("\n💡 Key Features Demonstrated:")
        print("  • Migration detection and validation")
        print("  • Migration history tracking")
        print("  • State validation and repair")
        print("  • Error handling and recovery")
        print("  • Integration with Alembic")
        
        print("\n📚 Next Steps:")
        print("  • Integrate MigrationRunner into your database initialization")
        print("  • Use it in your application startup sequence")
        print("  • Add it to your deployment scripts")
        print("  • Monitor migration health in production")
    else:
        print("\n❌ Some demos failed - check the error messages above")
        sys.exit(1)