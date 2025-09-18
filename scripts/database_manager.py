#!/usr/bin/env python3
"""
Enhanced Database Management Script

This script provides a comprehensive interface to the new database initialization system
with commands for initialization, health checking, repair, and management.
"""
import os
import sys
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def init_database(force=False):
    """Initialize database using the new system."""
    try:
        from app import create_app, db
        from app.utils.database_initializer import DatabaseInitializer
        
        print("🔄 Initializing database...")
        
        app = create_app()
        with app.app_context():
            initializer = DatabaseInitializer(app, db)
            
            if force:
                print("⚠️  Force mode: Dropping existing data...")
                db.drop_all()
            
            result = initializer.initialize()
            
            if result.success:
                print("✅ Database initialization completed successfully!")
                print(f"⏱️  Duration: {result.duration:.2f}s")
                print(f"🗄️  Database Type: {result.database_type}")
                
                if result.steps_completed:
                    print("\n📋 Completed Steps:")
                    for step in result.steps_completed:
                        print(f"  ✅ {step}")
                
                if result.warnings:
                    print("\n⚠️  Warnings:")
                    for warning in result.warnings:
                        print(f"  ⚠️  {warning}")
                
                return True
            else:
                print("❌ Database initialization failed!")
                if result.errors:
                    print("\n❌ Errors:")
                    for error in result.errors:
                        print(f"  ❌ {error}")
                return False
                
    except ImportError:
        print("⚠️  New initialization system not available, falling back to legacy...")
        return init_database_legacy(force)
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False


def init_database_legacy(force=False):
    """Legacy database initialization."""
    try:
        from app import create_app, db
        
        print("🔄 Using legacy database initialization...")
        
        app = create_app()
        with app.app_context():
            if force:
                print("⚠️  Force mode: Dropping existing data...")
                db.drop_all()
            
            db.create_all()
            print("✅ Database tables created")
            
            # Try to create admin user
            try:
                from app.services.data_seeder import DataSeeder
                seeder = DataSeeder(app)
                result = seeder.seed_initial_data()
                
                if result.success:
                    print("✅ Initial data seeded")
                else:
                    print("⚠️  Initial data seeding had issues")
                    
            except ImportError:
                print("⚠️  Data seeding system not available")
            
            return True
            
    except Exception as e:
        print(f"❌ Legacy initialization failed: {e}")
        return False


def check_health():
    """Check database health."""
    try:
        from app import create_app, db
        from app.utils.database_initializer import DatabaseInitializer
        
        print("🔍 Checking database health...")
        
        app = create_app()
        with app.app_context():
            initializer = DatabaseInitializer(app, db)
            result = initializer.validate_setup()
            
            if result.valid:
                print("✅ Database health check passed")
                print(f"🔧 Severity: {result.severity}")
                
                if result.suggestions:
                    print("\n💡 Suggestions:")
                    for suggestion in result.suggestions:
                        print(f"  💡 {suggestion}")
                        
                return True
            else:
                print("❌ Database health check failed")
                print(f"🔧 Severity: {result.severity}")
                
                if result.issues:
                    print("\n❌ Issues:")
                    for issue in result.issues:
                        print(f"  ❌ {issue}")
                
                if result.suggestions:
                    print("\n💡 Suggestions:")
                    for suggestion in result.suggestions:
                        print(f"  💡 {suggestion}")
                        
                return False
                
    except ImportError:
        print("⚠️  Health check system not available")
        return check_health_basic()
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def check_health_basic():
    """Basic health check without new system."""
    try:
        from app import create_app, db
        from sqlalchemy import inspect
        
        print("🔍 Performing basic health check...")
        
        app = create_app()
        with app.app_context():
            # Test connection
            try:
                db.engine.connect()
                print("✅ Database connection successful")
            except Exception as e:
                print(f"❌ Database connection failed: {e}")
                return False
            
            # Check tables
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"📊 Found {len(tables)} tables")
            
            if len(tables) > 0:
                print("✅ Database has tables")
                return True
            else:
                print("⚠️  Database has no tables")
                return False
                
    except Exception as e:
        print(f"❌ Basic health check failed: {e}")
        return False


def repair_database():
    """Attempt to repair database issues."""
    try:
        from app import create_app, db
        from app.utils.database_initializer import DatabaseInitializer
        
        print("🔧 Attempting database repair...")
        
        app = create_app()
        with app.app_context():
            initializer = DatabaseInitializer(app, db)
            result = initializer.repair_if_needed()
            
            if result.success:
                print("✅ Database repair completed successfully")
                
                if hasattr(result, 'actions_taken') and result.actions_taken:
                    print("\n🔧 Actions taken:")
                    for action in result.actions_taken:
                        print(f"  🔧 {action}")
                        
                return True
            else:
                print("❌ Database repair failed")
                
                if hasattr(result, 'errors') and result.errors:
                    print("\n❌ Errors:")
                    for error in result.errors:
                        print(f"  ❌ {error}")
                        
                return False
                
    except ImportError:
        print("⚠️  Repair system not available, attempting basic repair...")
        return repair_database_basic()
    except Exception as e:
        print(f"❌ Database repair failed: {e}")
        return False


def repair_database_basic():
    """Basic database repair without new system."""
    try:
        from app import create_app, db
        
        print("🔧 Performing basic database repair...")
        
        app = create_app()
        with app.app_context():
            # Recreate all tables
            db.create_all()
            print("✅ Database tables recreated")
            
            return True
            
    except Exception as e:
        print(f"❌ Basic repair failed: {e}")
        return False


def get_status():
    """Get database status information."""
    try:
        from app import create_app, db
        from app.utils.database_initializer import DatabaseInitializer
        from sqlalchemy import inspect
        
        print("📊 Getting database status...")
        
        app = create_app()
        with app.app_context():
            try:
                initializer = DatabaseInitializer(app, db)
                status = initializer.get_initialization_status()
                
                print("📋 Database Status:")
                for key, value in status.items():
                    print(f"  {key}: {value}")
                    
            except (ImportError, AttributeError):
                # Fallback to basic status
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                
                print("📋 Basic Database Status:")
                print(f"  Tables: {len(tables)}")
                print(f"  Database URL: {db.engine.url}")
                print(f"  Driver: {db.engine.dialect.name}")
                
                if tables:
                    print("  Table List:")
                    for table in sorted(tables):
                        print(f"    - {table}")
                        
            return True
            
    except Exception as e:
        print(f"❌ Failed to get status: {e}")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Enhanced Database Management")
    parser.add_argument(
        "command",
        choices=["init", "health", "repair", "status", "reset"],
        help="Command to execute"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force operation (drops existing data for init/reset)"
    )
    
    args = parser.parse_args()
    
    print("🗄️  AI Secretary Database Manager")
    print("=" * 50)
    
    success = False
    
    if args.command == "init":
        success = init_database(force=args.force)
    elif args.command == "health":
        success = check_health()
    elif args.command == "repair":
        success = repair_database()
    elif args.command == "status":
        success = get_status()
    elif args.command == "reset":
        print("⚠️  This will completely reset the database!")
        if args.force or input("Type 'yes' to confirm: ").lower() == 'yes':
            success = init_database(force=True)
        else:
            print("❌ Reset cancelled")
            return
    
    if success:
        print("\n✅ Operation completed successfully!")
    else:
        print("\n❌ Operation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()