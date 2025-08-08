"""Base model classes."""
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String
from sqlalchemy.ext.declarative import declared_attr
from app import db
from app.utils.database import BaseModelMixin
from app.utils.schema import get_schema_name


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
        return {'schema': get_schema_name()}
    
    id = Column(Integer, primary_key=True)


class TenantAwareModel(BaseModel):
    """Base model for tenant-aware entities."""
    
    __abstract__ = True
    
    @declared_attr
    def tenant_id(cls):
        """Foreign key to tenant."""
        return Column(Integer, db.ForeignKey(f'{get_schema_name()}.tenants.id'), nullable=False, index=True)
    
    @declared_attr
    def tenant(cls):
        """Relationship to tenant."""
        return db.relationship('Tenant', back_populates=cls.__tablename__ + 's')


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
        return Column(Integer, db.ForeignKey(f'{get_schema_name()}.users.id'), nullable=True)
    
    @declared_attr
    def updated_by_id(cls):
        """ID of user who last updated the record."""
        return Column(Integer, db.ForeignKey(f'{get_schema_name()}.users.id'), nullable=True)
    
    @declared_attr
    def created_by(cls):
        """User who created the record."""
        return db.relationship('User', foreign_keys=[cls.created_by_id], post_update=True)
    
    @declared_attr
    def updated_by(cls):
        """User who last updated the record."""
        return db.relationship('User', foreign_keys=[cls.updated_by_id], post_update=True)