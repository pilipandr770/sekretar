"""Tenant isolation middleware for database queries."""
from functools import wraps
from flask import g, request
from flask_jwt_extended import get_jwt, get_current_user
from sqlalchemy import event
from sqlalchemy.orm import Query
from app import db
from app.utils.errors import AuthorizationError
import structlog

logger = structlog.get_logger()


class TenantIsolationMiddleware:
    """Middleware to enforce tenant isolation at the database level."""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the middleware with Flask app."""
        self.app = app
        
        # Set up before request handler
        app.before_request(self.setup_tenant_context)
        
        # Set up SQLAlchemy event listeners for automatic tenant filtering
        self.setup_query_filters()
    
    def setup_tenant_context(self):
        """Set up tenant context for the current request."""
        # Initialize defaults
        g.tenant_id = None
        g.user_id = None
        
        try:
            # Skip tenant context for certain endpoints
            if self.should_skip_tenant_context():
                return
            
            # Only try JWT if we have an Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return
            
            # Try to get tenant from JWT token
            user = get_current_user()
            if user and hasattr(user, 'tenant_id'):
                g.tenant_id = user.tenant_id
                g.user_id = user.id
                
                logger.debug(
                    "Tenant context established",
                    tenant_id=g.tenant_id,
                    user_id=g.user_id,
                    endpoint=request.endpoint
                )
            else:
                # Try to get from JWT claims directly
                jwt_data = get_jwt()
                if jwt_data:
                    g.tenant_id = jwt_data.get('tenant_id')
                    g.user_id = jwt_data.get('user_id')
                
        except Exception as e:
            # JWT not required for all endpoints - don't log as error
            logger.debug("No tenant context available", error=str(e), path=request.path)
    
    def should_skip_tenant_context(self):
        """Check if tenant context should be skipped for this request."""
        skip_endpoints = [
            'auth.login',
            'auth.register',
            'auth.refresh',
            'auth.forgot_password',
            'auth.reset_password',
            'main.health',
            'main.version',
            'main.welcome',
            'static'
        ]
        
        # Skip for static files and health checks
        if request.endpoint in skip_endpoints:
            return True
        
        # Skip for certain paths
        skip_paths = ['/static/', '/api/v1/health', '/api/v1/version']
        for path in skip_paths:
            if request.path.startswith(path):
                return True
        
        return False
    
    def setup_query_filters(self):
        """Set up automatic tenant filtering for SQLAlchemy queries."""
        # Note: Automatic query filtering is handled at the model level
        # and through decorators rather than SQLAlchemy events
        pass
    
    def apply_tenant_filter(self, query):
        """Apply tenant filter to a query if applicable."""
        try:
            tenant_id = getattr(g, 'tenant_id', None)
            if not tenant_id:
                return query
            
            # Get the model class from the query
            if hasattr(query, 'column_descriptions') and query.column_descriptions:
                model_class = query.column_descriptions[0]['type']
                
                # Check if model has tenant_id attribute
                if hasattr(model_class, 'tenant_id'):
                    query = query.filter(model_class.tenant_id == tenant_id)
                    logger.debug(
                        "Applied tenant filter",
                        model=model_class.__name__,
                        tenant_id=tenant_id
                    )
            
            return query
            
        except Exception as e:
            logger.warning("Failed to apply tenant filter", error=str(e))
            return query


def tenant_required(f):
    """Decorator to ensure tenant context is set for the request."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        tenant_id = getattr(g, 'tenant_id', None)
        if not tenant_id:
            raise AuthorizationError("Tenant context required for this operation")
        return f(*args, **kwargs)
    return decorated_function


def permission_required(permission):
    """Decorator to check if current user has required permission."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                raise AuthorizationError("Authentication required")
            
            if not user.has_permission(permission):
                raise AuthorizationError(f"Permission '{permission}' required")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def role_required(role_name):
    """Decorator to check if current user has required role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                raise AuthorizationError("Authentication required")
            
            if not user.has_role(role_name):
                raise AuthorizationError(f"Role '{role_name}' required")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def owner_or_manager_required(f):
    """Decorator to check if current user is owner or manager."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            raise AuthorizationError("Authentication required")
        
        if not (user.is_owner or user.is_manager):
            raise AuthorizationError("Owner or manager role required")
        
        return f(*args, **kwargs)
    return decorated_function


class TenantAwareQuery:
    """Helper class for tenant-aware database queries."""
    
    @staticmethod
    def filter_by_tenant(query, model_class=None, tenant_id=None):
        """Add tenant filter to a query."""
        if tenant_id is None:
            tenant_id = getattr(g, 'tenant_id', None)
        
        if not tenant_id:
            raise AuthorizationError("Tenant context required")
        
        # If model_class is not provided, try to infer it from the query
        if model_class is None and hasattr(query, 'column_descriptions'):
            if query.column_descriptions:
                model_class = query.column_descriptions[0]['type']
        
        # Apply tenant filter if model has tenant_id
        if model_class and hasattr(model_class, 'tenant_id'):
            query = query.filter(model_class.tenant_id == tenant_id)
        
        return query
    
    @staticmethod
    def get_by_id(model_class, id, tenant_id=None):
        """Get a record by ID with tenant filtering."""
        if tenant_id is None:
            tenant_id = getattr(g, 'tenant_id', None)
        
        if not tenant_id:
            raise AuthorizationError("Tenant context required")
        
        query = model_class.query.filter(model_class.id == id)
        
        if hasattr(model_class, 'tenant_id'):
            query = query.filter(model_class.tenant_id == tenant_id)
        
        return query.first()
    
    @staticmethod
    def get_by_id_or_404(model_class, id, tenant_id=None):
        """Get a record by ID with tenant filtering or raise 404."""
        record = TenantAwareQuery.get_by_id(model_class, id, tenant_id)
        if not record:
            from app.utils.errors import NotFoundError
            raise NotFoundError(f"{model_class.__name__} not found")
        return record
    
    @staticmethod
    def create_with_tenant(model_class, **kwargs):
        """Create a new record with automatic tenant assignment."""
        tenant_id = getattr(g, 'tenant_id', None)
        if not tenant_id:
            raise AuthorizationError("Tenant context required")
        
        if hasattr(model_class, 'tenant_id'):
            kwargs['tenant_id'] = tenant_id
        
        return model_class.create(**kwargs)


def init_tenant_middleware(app):
    """Initialize tenant isolation middleware."""
    middleware = TenantIsolationMiddleware(app)
    return middleware