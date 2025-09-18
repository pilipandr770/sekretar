#!/usr/bin/env python3
"""
Legacy Database Setup Compatibility Layer

This script provides backward compatibility for existing database setup procedures
while integrating with the new initialization system when available.
"""
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def setup_database_legacy():
    """Setup database using legacy methods."""
    try:
        from app import create_app, db
        from app.models.user import User
        from app.models.tenant import Tenant
        from werkzeug.security import generate_password_hash
        
        print("🔄 Setting up database using legacy methods...")
        
        app = create_app()
        with app.app_context():
            # Create all tables
            db.create_all()
            print("✅ Database tables created")
            
            # Check if admin user already exists
            admin = User.query.filter_by(email="admin@ai-secretary.com").first()
            if admin:
                print("✅ Admin user already exists")
                return True
            
            # Create default tenant if it doesn't exist
            tenant = Tenant.query.filter_by(slug="default").first()
            if not tenant:
                tenant = Tenant(
                    name="Default Tenant",
                    domain="localhost",
                    slug="default",
                    is_active=True
                )
                db.session.add(tenant)
                db.session.commit()
                print("✅ Default tenant created")
            
            # Create admin user
            admin_user = User(
                tenant_id=tenant.id,
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
            
            return True
            
    except Exception as e:
        print(f"❌ Legacy setup failed: {e}")
        return False


def setup_database_new_system():
    """Setup database using new initialization system."""
    try:
        from app import create_app, db
        from app.utils.database_initializer import DatabaseInitializer
        
        print("🔄 Setting up database using new initialization system...")
        
        app = create_app()
        with app.app_context():
            initializer = DatabaseInitializer(app, db)
            result = initializer.initialize()
            
            if result.success:
                print("✅ Database setup completed using new system")
                return True
            else:
                print("❌ New system setup failed")
                if result.errors:
                    for error in result.errors:
                        print(f"  ❌ {error}")
                return False
                
    except ImportError:
        print("⚠️  New initialization system not available")
        return False
    except Exception as e:
        print(f"❌ New system setup failed: {e}")
        return False


def ensure_database_ready():
    """Ensure database is ready for use with any available method."""
    print("🚀 Ensuring database is ready...")
    
    # Try new system first
    if setup_database_new_system():
        return True
    
    # Fall back to legacy
    print("🔄 Falling back to legacy setup...")
    if setup_database_legacy():
        return True
    
    print("❌ All database setup methods failed")
    return False


def verify_database_setup():
    """Verify that database setup was successful."""
    try:
        from app import create_app, db
        from app.models.user import User
        from app.models.tenant import Tenant
        from sqlalchemy import inspect
        
        print("🔍 Verifying database setup...")
        
        app = create_app()
        with app.app_context():
            # Check tables exist
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if len(tables) == 0:
                print("❌ No tables found in database")
                return False
            
            print(f"✅ Found {len(tables)} tables")
            
            # Check admin user exists
            admin = User.query.filter_by(email="admin@ai-secretary.com").first()
            if not admin:
                print("❌ Admin user not found")
                return False
            
            print("✅ Admin user found")
            
            # Check tenant exists
            tenant = Tenant.query.first()
            if not tenant:
                print("❌ No tenant found")
                return False
            
            print("✅ Tenant found")
            
            print("✅ Database verification passed")
            return True
            
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False


def main():
    """Main function for backward compatibility."""
    print("🗄️  Legacy Database Setup")
    print("=" * 40)
    
    # Ensure database is ready
    if not ensure_database_ready():
        print("❌ Failed to setup database")
        sys.exit(1)
    
    # Verify setup
    if not verify_database_setup():
        print("❌ Database verification failed")
        sys.exit(1)
    
    print("\n✅ Database is ready for use!")
    print("=" * 40)
    print("📧 Admin Email: admin@ai-secretary.com")
    print("🔑 Admin Password: admin123")
    print("=" * 40)


if __name__ == "__main__":
    main()