
"""Middleware utilities."""
import os
import time
from functools import lru_cache
from flask import request, session, g
from flask_jwt_extended import get_current_user, jwt_required
from app.utils.i18n import get_user_language, set_user_language
import structlog

# Performance optimizations
@lru_cache(maxsize=128)
def cached_language_detection(accept_language):
    """Cached language detection to avoid repeated parsing"""
    # Your existing language detection logic here
    return 'en'  # Default fallback

# Disable slow operations in development
SKIP_SLOW_OPERATIONS = os.environ.get('FLASK_ENV') == 'development'

logger = structlog.get_logger()


def setup_language_middleware(app):
    """Setup language detection middleware."""
    
    @app.before_request
    def detect_language():
        """Detect and set user language before each request."""
        try:
            # Get language from various sources
            language = get_user_language()
            
            # Store in request context
            g.language = language
            
            # Update session if needed
            if 'language' not in session or session['language'] != language:
                session['language'] = language
            
            logger.debug("Language detected", language=language, path=request.path)
            
        except Exception as e:
            logger.warning("Failed to detect language", error=str(e))
            g.language = 'en'  # Fallback to English


def setup_tenant_middleware(app):
    """Setup tenant context middleware."""
    
    @app.before_request
    def setup_tenant_context():
        """Setup tenant context for the request."""
        # Initialize defaults
        g.tenant_id = None
        g.user_id = None
        g.current_user = None
        
        # Skip JWT processing for certain endpoints
        skip_paths = ['/static/', '/api/v1/health', '/api/v1/version', '/socket.io/']
        if any(request.path.startswith(path) for path in skip_paths):
            return
        
        try:
            # Only try to get user if we have an Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                logger.debug("No JWT token in request", path=request.path)
                return
            
            # Try to get tenant from JWT token
            user = get_current_user()
            if user and hasattr(user, 'tenant_id'):
                g.tenant_id = user.tenant_id
                g.user_id = user.id
                g.current_user = user
                
                # Update user's language preference if different
                if hasattr(user, 'language') and user.language != g.language:
                    user.language = g.language
                    user.save()
                
                logger.debug(
                    "Tenant context set", 
                    tenant_id=g.tenant_id, 
                    user_id=g.user_id,
                    language=g.language
                )
                
        except Exception as e:
            # JWT not required for all endpoints - don't log as error
            logger.debug("No tenant context available", error=str(e), path=request.path)


def setup_role_validation_middleware(app):
    """Setup role validation middleware for tenant operations."""
    
    @app.before_request
    def validate_tenant_access():
        """Validate user has access to tenant resources."""
        # Skip validation for non-API endpoints
        if not request.path.startswith('/api/v1/'):
            return
        
        # Skip validation for auth endpoints
        if request.path.startswith('/api/v1/auth/'):
            return
        
        # Skip validation for public endpoints
        public_endpoints = [
            '/api/v1/health',
            '/api/v1/status',
            '/api/v1/version',
            '/api/v1/docs'
        ]
        if request.path in public_endpoints:
            return
        
        try:
            user = getattr(g, 'current_user', None)
            if not user:
                return  # No user context, let JWT decorators handle it
            
            # Validate user is active
            if not user.is_active:
                from flask_babel import gettext as _
                from app.utils.response import error_response
                return error_response(
                    error_code='ACCOUNT_DISABLED',
                    message=_('Your account has been disabled'),
                    status_code=403
                )
            
            # Validate tenant is active
            if not user.tenant or not user.tenant.is_active:
                from flask_babel import gettext as _
                from app.utils.response import error_response
                return error_response(
                    error_code='TENANT_DISABLED',
                    message=_('Your organization account has been disabled'),
                    status_code=403
                )
            
            # Log access for audit purposes
            logger.debug(
                "Tenant access validated",
                user_id=user.id,
                tenant_id=user.tenant_id,
                path=request.path,
                method=request.method
            )
            
        except Exception as e:
            logger.error("Role validation middleware error", error=str(e), exc_info=True)
            # Don't block request on middleware errors


def setup_request_logging_middleware(app):
    """Setup request logging middleware."""
    
    @app.before_request
    def log_request():
        """Log incoming request."""
        # Skip logging for health checks and static files
        if request.path in ['/api/v1/health', '/api/v1/status'] or request.path.startswith('/static'):
            return
        
        logger.info(
            "Request started",
            method=request.method,
            path=request.path,
            remote_addr=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            language=getattr(g, 'language', 'unknown'),
            tenant_id=getattr(g, 'tenant_id', None)
        )
    
    @app.after_request
    def log_response(response):
        """Log response."""
        # Skip logging for health checks and static files
        if request.path in ['/api/v1/health', '/api/v1/status'] or request.path.startswith('/static'):
            return response
        
        logger.info(
            "Request completed",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            language=getattr(g, 'language', 'unknown'),
            tenant_id=getattr(g, 'tenant_id', None)
        )
        
        return response


def setup_error_handling_middleware(app):
    """Setup error handling middleware with i18n support."""
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors with i18n."""
        from flask_babel import gettext as _
        from app.utils.response import error_response
        
        return error_response(
            error_code='NOT_FOUND_ERROR',
            message=_('The requested resource was not found'),
            status_code=404
        )
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 errors with i18n."""
        from flask_babel import gettext as _
        from app.utils.response import error_response
        
        return error_response(
            error_code='METHOD_NOT_ALLOWED',
            message=_('Method not allowed for this endpoint'),
            status_code=405
        )
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors with i18n."""
        from flask_babel import gettext as _
        from app.utils.response import error_response
        
        logger.error("Internal server error", error=str(error), exc_info=True)
        
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('An internal server error occurred'),
            status_code=500
        )


def init_middleware(app):
    """Initialize all middleware."""
    setup_language_middleware(app)
    
    # Initialize performance monitoring middleware
    try:
        from app.utils.performance_middleware import init_performance_monitoring
        init_performance_monitoring(app)
        logger.info("✅ Performance monitoring middleware initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize performance monitoring middleware: {e}")
        # Continue without performance monitoring
    setup_tenant_middleware(app)
    setup_role_validation_middleware(app)
    setup_request_logging_middleware(app)
    setup_error_handling_middleware(app)
    
    # Initialize API localization middleware
    from app.utils.api_localization_middleware import init_api_localization_middleware
    init_api_localization_middleware(app)
    
    # Initialize tenant isolation middleware (skip in testing)
    import os
    tenant_middleware_enabled = app.config.get('TENANT_MIDDLEWARE_ENABLED', True)
    if os.environ.get('TENANT_MIDDLEWARE_ENABLED', 'true').lower() == 'false':
        tenant_middleware_enabled = False
    
    if tenant_middleware_enabled:
        from app.utils.tenant_middleware import init_tenant_middleware
        init_tenant_middleware(app)