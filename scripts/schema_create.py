#!/usr/bin/env python3
"""Create database schema with new initialization system integration."""
from app import create_app, db

def create_schema_new_system():
    """Create schema using new initialization system."""
    try:
        from app.utils.schema_manager import SchemaManager
        
        app = create_app()
        with app.app_context():
            schema_manager = SchemaManager(app, db)
            
            if not schema_manager.check_schema_exists():
                result = schema_manager.create_schema()
                if result:
                    print(f'✅ Schema created successfully')
                    
                    # Validate the created schema
                    validation = schema_manager.validate_schema()
                    if validation.valid:
                        print('✅ Schema validation passed')
                    else:
                        print('⚠️  Schema validation issues:')
                        for issue in validation.issues:
                            print(f'  ⚠️  {issue}')
                else:
                    print('❌ Schema creation failed')
                    return False
            else:
                print('✅ Schema already exists')
            
            return True
            
    except ImportError:
        return False
    except Exception as e:
        print(f'❌ Error with new system: {e}')
        return False

def create_schema_legacy():
    """Create schema using legacy method."""
    try:
        from app.utils.schema import create_schema_if_not_exists, set_search_path
        
        app = create_app()
        with app.app_context():
            create_schema_if_not_exists()
            set_search_path()
            schema_name = app.config.get("DB_SCHEMA", "ai_secretary")
            print(f'✅ Schema {schema_name} is ready (legacy method)')
            return True
            
    except Exception as e:
        print(f'❌ Legacy schema creation failed: {e}')
        return False

if __name__ == '__main__':
    print("🔄 Creating database schema...")
    
    # Try new system first
    if create_schema_new_system():
        print("✅ Schema created using new system")
    elif create_schema_legacy():
        print("✅ Schema created using legacy method")
    else:
        print("❌ Schema creation failed with all methods")
        exit(1)