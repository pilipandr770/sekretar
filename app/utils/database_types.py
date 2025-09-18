"""Database-agnostic type utilities."""
import uuid
from sqlalchemy import TypeDecorator, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.engine import Engine
from sqlalchemy import event


class UUID(TypeDecorator):
    """Database-agnostic UUID type.
    
    Uses PostgreSQL UUID when available, falls back to String for SQLite.
    """
    impl = String
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        """Load the appropriate implementation for the dialect."""
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgreSQLUUID(as_uuid=True))
        else:
            # For SQLite and other databases, use String(36)
            return dialect.type_descriptor(String(36))
    
    def process_bind_param(self, value, dialect):
        """Process value before binding to database."""
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            # For SQLite, convert UUID to string
            if isinstance(value, uuid.UUID):
                return str(value)
            return value
    
    def process_result_value(self, value, dialect):
        """Process value after retrieving from database."""
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            # For SQLite, convert string back to UUID
            if isinstance(value, str):
                return uuid.UUID(value)
            return value


class JSON(TypeDecorator):
    """Database-agnostic JSON type.
    
    Uses PostgreSQL JSON when available, falls back to Text for SQLite.
    """
    impl = Text
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        """Load the appropriate implementation for the dialect."""
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import JSON as PostgreSQLJSON
            return dialect.type_descriptor(PostgreSQLJSON())
        else:
            # For SQLite and other databases, use Text with JSON serialization
            return dialect.type_descriptor(Text())
    
    def process_bind_param(self, value, dialect):
        """Process value before binding to database."""
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            # For SQLite, serialize to JSON string
            import json
            return json.dumps(value)
    
    def process_result_value(self, value, dialect):
        """Process value after retrieving from database."""
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            # For SQLite, deserialize from JSON string
            import json
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            return value


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance and compatibility."""
    if 'sqlite' in str(dbapi_connection):
        cursor = dbapi_connection.cursor()
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys=ON")
        # Set journal mode to WAL for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        # Set synchronous mode to NORMAL for better performance
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()