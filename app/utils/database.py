"""Database utilities and helpers."""
from functools import wraps
from flask import g, request
from flask_jwt_extended import get_jwt
from app import db
from app.utils.errors import AuthorizationError
import structlog

logger = structlog.get_logger()


def get_current_tenant_id():
    """Get current tenant ID from JWT or context."""
    try:
        jwt_data = get_jwt()
        return jwt_data.get('tenant_id')
    except Exception:
        return getattr(g, 'tenant_id', None)


def set_tenant_context(tenant_id):
    """Set tenant context for the current request."""
    g.tenant_id = tenant_id


def tenant_required(f):
    """Decorator to ensure tenant context is set."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            raise AuthorizationError("Tenant context required")
        return f(*args, **kwargs)
    return decorated_function


class TenantQuery:
    """Query helper that automatically filters by tenant."""
    
    def __init__(self, model):
        self.model = model
        self.query = model.query
    
    def filter_by_tenant(self, tenant_id=None):
        """Filter query by tenant ID."""
        if tenant_id is None:
            tenant_id = get_current_tenant_id()
        
        if not tenant_id:
            raise AuthorizationError("Tenant context required")
        
        if hasattr(self.model, 'tenant_id'):
            self.query = self.query.filter(self.model.tenant_id == tenant_id)
        
        return self
    
    def filter(self, *args, **kwargs):
        """Add filter to query."""
        self.query = self.query.filter(*args, **kwargs)
        return self
    
    def filter_by(self, **kwargs):
        """Add filter_by to query."""
        self.query = self.query.filter_by(**kwargs)
        return self
    
    def order_by(self, *args):
        """Add order_by to query."""
        self.query = self.query.order_by(*args)
        return self
    
    def limit(self, limit):
        """Add limit to query."""
        self.query = self.query.limit(limit)
        return self
    
    def offset(self, offset):
        """Add offset to query."""
        self.query = self.query.offset(offset)
        return self
    
    def all(self):
        """Execute query and return all results."""
        return self.query.all()
    
    def first(self):
        """Execute query and return first result."""
        return self.query.first()
    
    def first_or_404(self):
        """Execute query and return first result or 404."""
        return self.query.first_or_404()
    
    def get(self, id):
        """Get by ID with tenant filtering."""
        return self.filter_by_tenant().filter(self.model.id == id).first()
    
    def get_or_404(self, id):
        """Get by ID with tenant filtering or 404."""
        result = self.get(id)
        if not result:
            from app.utils.errors import NotFoundError
            raise NotFoundError(f"{self.model.__name__} not found")
        return result
    
    def paginate(self, page=1, per_page=20, error_out=True):
        """Paginate query results."""
        return self.query.paginate(
            page=page,
            per_page=per_page,
            error_out=error_out
        )


def create_tenant_query(model):
    """Create a tenant-aware query for a model."""
    return TenantQuery(model).filter_by_tenant()


def safe_commit():
    """Safely commit database transaction with error handling."""
    try:
        db.session.commit()
        logger.info("Database transaction committed successfully")
    except Exception as e:
        db.session.rollback()
        logger.error("Database transaction failed", error=str(e), exc_info=True)
        raise


def safe_delete(obj):
    """Safely delete object with error handling."""
    try:
        db.session.delete(obj)
        safe_commit()
        logger.info("Object deleted successfully", model=obj.__class__.__name__, id=getattr(obj, 'id', None))
    except Exception as e:
        logger.error("Failed to delete object", error=str(e), exc_info=True)
        raise


class BaseModelMixin:
    """Base mixin for all models with common functionality."""
    
    def save(self):
        """Save the model to database."""
        db.session.add(self)
        safe_commit()
        return self
    
    def delete(self):
        """Delete the model from database."""
        safe_delete(self)
    
    def update(self, **kwargs):
        """Update model attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self.save()
    
    def to_dict(self, exclude=None):
        """Convert model to dictionary."""
        exclude = exclude or []
        result = {}
        
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                # Handle datetime serialization
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                result[column.name] = value
        
        return result
    
    @classmethod
    def create(cls, **kwargs):
        """Create new instance."""
        instance = cls(**kwargs)
        return instance.save()
    
    @classmethod
    def get_by_id(cls, id, tenant_id=None):
        """Get instance by ID with optional tenant filtering."""
        query = cls.query.filter(cls.id == id)
        
        if tenant_id and hasattr(cls, 'tenant_id'):
            query = query.filter(cls.tenant_id == tenant_id)
        
        return query.first()
    
    @classmethod
    def get_by_id_or_404(cls, id, tenant_id=None):
        """Get instance by ID or raise 404."""
        instance = cls.get_by_id(id, tenant_id)
        if not instance:
            from app.utils.errors import NotFoundError
            raise NotFoundError(f"{cls.__name__} not found")
        return instance