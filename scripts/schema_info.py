#!/usr/bin/env python3
"""Get database schema information with new system integration."""
from app import create_app, db
from sqlalchemy import text, inspect

def get_schema_info_new_system():
    """Get schema info using new system."""
    try:
        from app.utils.schema_manager import SchemaManager
        
        app = create_app()
        with app.app_context():
            schema_manager = SchemaManager(app, db)
            schema_info = schema_manager.get_schema_info()
            
            print("📊 Schema Information (New System):")
            for key, value in schema_info.items():
                if isinstance(value, list):
                    print(f"  {key}: {len(value)} items")
                    for item in value:
                        print(f"    - {item}")
                else:
                    print(f"  {key}: {value}")
            
            return True
            
    except ImportError:
        return False
    except Exception as e:
        print(f"❌ Error with new system: {e}")
        return False

def get_schema_info_legacy():
    """Get schema info using legacy method."""
    try:
        from app.utils.schema import get_schema_name
        
        app = create_app()
        with app.app_context():
            # Try to get schema name
            try:
                schema_name = get_schema_name()
                print(f'📋 Current schema: {schema_name}')
                
                # Check if schema exists (PostgreSQL)
                try:
                    result = db.session.execute(
                        text('SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema'),
                        {'schema': schema_name}
                    )
                    
                    if result.fetchone():
                        print(f'✅ Schema {schema_name} exists')
                        
                        # List tables in schema
                        tables_result = db.session.execute(
                            text('SELECT table_name FROM information_schema.tables WHERE table_schema = :schema'),
                            {'schema': schema_name}
                        )
                        
                        tables = [row[0] for row in tables_result.fetchall()]
                        if tables:
                            print(f'📊 Tables in schema ({len(tables)}):')
                            for table in sorted(tables):
                                print(f'  - {table}')
                        else:
                            print('⚠️  No tables in schema')
                    else:
                        print(f'❌ Schema {schema_name} does not exist')
                        
                except Exception:
                    # Fallback for SQLite or other databases
                    inspector = inspect(db.engine)
                    tables = inspector.get_table_names()
                    
                    print(f'📊 Database tables ({len(tables)}):')
                    for table in sorted(tables):
                        print(f'  - {table}')
                    
                    print(f'🗄️  Database: {db.engine.url}')
                    print(f'🔧 Driver: {db.engine.dialect.name}')
                    
            except Exception:
                # Basic fallback
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                
                print(f'📊 Database Information:')
                print(f'  Tables: {len(tables)}')
                print(f'  Database URL: {db.engine.url}')
                print(f'  Driver: {db.engine.dialect.name}')
                
                if tables:
                    print('  Table List:')
                    for table in sorted(tables):
                        print(f'    - {table}')
            
            return True
            
    except Exception as e:
        print(f'❌ Legacy schema info failed: {e}')
        return False

if __name__ == '__main__':
    print("🔍 Getting database schema information...")
    
    # Try new system first
    if get_schema_info_new_system():
        print("✅ Schema info retrieved using new system")
    elif get_schema_info_legacy():
        print("✅ Schema info retrieved using legacy method")
    else:
        print("❌ Failed to get schema information")
        exit(1)