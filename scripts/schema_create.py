#!/usr/bin/env python3
"""Create database schema."""
from app import create_app
from app.utils.schema import create_schema_if_not_exists, set_search_path

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        create_schema_if_not_exists()
        set_search_path()
        print(f'Schema {app.config["DB_SCHEMA"]} is ready')