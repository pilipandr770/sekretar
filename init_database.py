#!/usr/bin/env python3
"""
Database Initialization Script for AI Secretary

This script initializes the database using the new comprehensive initialization system
with automatic schema creation, migration management, and data seeding.
"""
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment for SQLite mode (backward compatibility)
if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = 'sqlite:///ai_secretary.db'
if 'SQLITE_DATABASE_URL' not in os.environ:
    os.environ['SQLITE_DATABASE_URL'] = 'sqlite:///ai_secretary.db'
if 'FLASK_ENV' not in os.environ:
    os.environ['FLASK_ENV'] = 'development'
if 'SQLITE_MODE' not in os.environ:
    os.environ['SQLITE_MODE'] = 'True'

def init_database():
    """Initialize the database using the new initialization system."""
    try:
        from app import create_app, db
        from app.utils.database_initializer import DatabaseInitializer
        
        print("🔄 Initializing AI Secretary database using new initialization system...")
        
        # Create application
        app = create_app()
        
        with app.app_context():
            # Use the new database initialization system
            initializer = DatabaseInitializer(app, db)
            result = initializer.initialize()
            
            if result.success:
                print("✅ Database initialization completed successfully!")
                print("=" * 60)
                print("📧 Admin Email: admin@ai-secretary.com")
                print("🔑 Admin Password: admin123")
                print("🏢 Tenant: AI Secretary System")
                print(f"🗄️  Database Type: {result.database_type}")
                print(f"⏱️  Duration: {result.duration:.2f}s")
                print("=" * 60)
                
                # Show completed steps
                if result.steps_completed:
                    print("\n📋 Completed Steps:")
                    for step in result.steps_completed:
                        print(f"  ✅ {step}")
                
                # Show warnings if any
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
            
    except ImportError as e:
        print(f"⚠️  New initialization system not available: {e}")
        print("🔄 Falling back to legacy initialization...")
        return init_database_legacy()
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def init_database_legacy():
    """Legacy database initialization for backward compatibility."""
    try:
        from app import create_app, db
        from app.models.user import User
        from app.models.tenant import Tenant
        from werkzeug.security import generate_password_hash
        
        print("🔄 Using legacy database initialization...")
        
        # Create application
        app = create_app()
        
        with app.app_context():
            print("📋 Creating database tables...")
            
            # Drop all tables first (clean slate)
            db.drop_all()
            
            # Create all tables
            db.create_all()
            
            print("✅ Database tables created successfully")
            
            # Create default tenant
            print("🏢 Creating default tenant...")
            default_tenant = Tenant(
                name="Default Tenant",
                domain="localhost",
                slug="default",
                is_active=True
            )
            db.session.add(default_tenant)
            db.session.commit()
            
            print("✅ Default tenant created")
            
            # Create admin user
            print("👤 Creating admin user...")
            admin_user = User(
                tenant_id=default_tenant.id,
                email="admin@ai-secretary.com",
                password_hash=generate_password_hash("admin123"),
                first_name="Admin",
                last_name="User",
                role="admin",
                is_active=True,
                is_email_verified=True
            )
            db.session.add(admin_user)
            db.session.commit()
            
            print("✅ Admin user created")
            print()
            print("🎉 Database initialization completed successfully!")
            print("=" * 60)
            print("📧 Admin Email: admin@ai-secretary.com")
            print("🔑 Admin Password: admin123")
            print("🏢 Tenant: Default Tenant")
            print("🗄️  Database: ai_secretary.db")
            print("=" * 60)
            
            return True
            
    except Exception as e:
        print(f"❌ Legacy database initialization failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def verify_database():
    """Verify that the database was created correctly."""
    try:
        from app import create_app, db
        from app.models.user import User
        from app.models.tenant import Tenant
        
        app = create_app()
        
        with app.app_context():
            # Check if tables exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"📊 Found {len(tables)} tables in database")
            
            # Check if admin user exists
            admin = User.query.filter_by(email="admin@ai-secretary.com").first()
            if admin:
                print("✅ Admin user found")
                print(f"   Email: {admin.email}")
                print(f"   Role: {admin.role}")
                print(f"   Active: {admin.is_active}")
            else:
                print("❌ Admin user not found")
                return False
            
            # Check if default tenant exists
            tenant = Tenant.query.filter_by(slug="default").first()
            if tenant:
                print("✅ Default tenant found")
                print(f"   Name: {tenant.name}")
                print(f"   Domain: {tenant.domain}")
                print(f"   Active: {tenant.is_active}")
            else:
                print("❌ Default tenant not found")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False

def main():
    """Main function."""
    print("🚀 AI Secretary Database Initialization")
    print("=" * 60)
    
    # Initialize database
    if not init_database():
        print("❌ Failed to initialize database")
        sys.exit(1)
    
    # Verify database
    print("\n🔍 Verifying database...")
    if not verify_database():
        print("❌ Database verification failed")
        sys.exit(1)
    
    print("\n✅ Database is ready for use!")
    print("\nYou can now run the application with:")
    print("  python run.py")
    print("  or")
    print("  python run_sqlite_app.py")

if __name__ == "__main__":
    main()