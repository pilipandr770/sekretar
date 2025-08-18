"""Base model classes."""
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String
from sqlalchemy.ext.declarative import declared_attr
from app import db
from app.utils.database import BaseModelMixin
from app.utils.schema import get_schema_name


def get_fk_reference(table_name):
    """Get foreign key reference with proper schema handling."""
    try:
        from flask import current_app
        if current_app.config.get('TESTING', False):
            return f'{table_name}.id'
        schema_name = get_schema_name()
        if schema_name:
            return f'{schema_name}.{table_name}.id'
        else:
            return f'{table_name}.id'
    except RuntimeError:
        # Outside application context, use environment variable
        import os
        testing = os.environ.get('TESTING', 'False').lower() == 'true'
        if testing:
            return f'{table_name}.id'
        schema_name = os.environ.get('DB_SCHEMA', 'ai_secretary')
        if schema_name:
            return f'{schema_name}.{table_name}.id'
        else:
            return f'{table_name}.id'


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BaseModel(db.Model, BaseModelMixin, TimestampMixin):
    """Base model class with common functionality."""
    
    __abstract__ = True
    
    @declared_attr
    def __table_args__(cls):
        """Set schema for all tables."""
        try:
            from flask import current_app
            if current_app.config.get('TESTING', False):
                return {}
            schema_name = get_schema_name()
            if schema_name:
                return {'schema': schema_name}
            return {}
        except RuntimeError:
            # Outside application context, use environment variable
            import os
            testing = os.environ.get('TESTING', 'False').lower() == 'true'
            if testing:
                return {}
            schema_name = os.environ.get('DB_SCHEMA', 'ai_secretary')
            if schema_name:
                return {'schema': schema_name}
            return {}
    
    id = Column(Integer, primary_key=True)


class TenantAwareModel(BaseModel):
    """Base model for tenant-aware entities."""
    
    __abstract__ = True
    
    @declared_attr
    def tenant_id(cls):
        """Foreign key to tenant."""
        return Column(Integer, db.ForeignKey(get_fk_reference('tenants')), nullable=False, index=True)
    
    @declared_attr
    def tenant(cls):
        """Relationship to tenant."""
        # Don't automatically create back_populates to avoid circular dependency issues
        return db.relationship('Tenant')


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    
    deleted_at = Column(DateTime, nullable=True)
    
    def soft_delete(self):
        """Mark record as deleted."""
        self.deleted_at = datetime.utcnow()
        return self.save()
    
    def restore(self):
        """Restore soft deleted record."""
        self.deleted_at = None
        return self.save()
    
    @property
    def is_deleted(self):
        """Check if record is soft deleted."""
        return self.deleted_at is not None
    
    @classmethod
    def active_only(cls):
        """Query only non-deleted records."""
        return cls.query.filter(cls.deleted_at.is_(None))


class AuditMixin:
    """Mixin for audit trail functionality."""
    
    @declared_attr
    def created_by_id(cls):
        """ID of user who created the record."""
        return Column(Integer, db.ForeignKey(get_fk_reference('users')), nullable=True)
    
    @declared_attr
    def updated_by_id(cls):
        """ID of user who last updated the record."""
        return Column(Integer, db.ForeignKey(get_fk_reference('users')), nullable=True)
    
    @declared_attr
    def created_by(cls):
        """User who created the record."""
        return db.relationship('User', foreign_keys=[cls.created_by_id], post_update=True)
    
    @declared_attr
    def updated_by(cls):
        """User who last updated the record."""
        return db.relationship('User', foreign_keys=[cls.updated_by_id], post_update=True)