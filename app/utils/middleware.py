"""Middleware utilities."""
from flask import request, session, g
from flask_jwt_extended import get_current_user, jwt_required
from app.utils.i18n import get_user_language, set_user_language
import structlog

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
        try:
            # Try to get tenant from JWT token
            user = get_current_user()
            if user and hasattr(user, 'tenant_id'):
                g.tenant_id = user.tenant_id
                g.user_id = user.id
                
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
            else:
                g.tenant_id = None
                g.user_id = None
                
        except Exception as e:
            # JWT not required for all endpoints
            g.tenant_id = None
            g.user_id = None
            logger.debug("No tenant context", error=str(e))


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
    setup_tenant_middleware(app)
    setup_request_logging_middleware(app)
    setup_error_handling_middleware(app)