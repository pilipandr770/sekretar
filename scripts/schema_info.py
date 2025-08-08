#!/usr/bin/env python3
"""Get database schema information."""
from app import create_app
from app.utils.schema import get_schema_name
from sqlalchemy import text
from app import db

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        schema_name = get_schema_name()
        print(f'Current schema: {schema_name}')
        
        # Check if schema exists
        result = db.session.execute(
            text('SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema'),
            {'schema': schema_name}
        )
        
        if result.fetchone():
            print(f'Schema {schema_name} exists')
            
            # List tables in schema
            tables_result = db.session.execute(
                text('SELECT table_name FROM information_schema.tables WHERE table_schema = :schema'),
                {'schema': schema_name}
            )
            
            tables = [row[0] for row in tables_result.fetchall()]
            if tables:
                print(f'Tables in schema: {", ".join(tables)}')
            else:
                print('No tables in schema')
        else:
            print(f'Schema {schema_name} does not exist')