#!/usr/bin/env python3
"""Drop database schema."""
import sys
from app import create_app
from app.utils.schema import drop_schema

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python schema_drop.py <schema_name>")
        sys.exit(1)
    
    schema_name = sys.argv[1]
    
    app = create_app()
    with app.app_context():
        drop_schema(schema_name)
        print(f'Schema {schema_name} dropped')