"""Main API routes."""
import sys
import platform
from datetime import datetime
from flask import jsonify, request, current_app
from flask_babel import gettext as _
from app.api import api_bp
from app.utils.response import (
    success_response, error_response, health_response, 
    version_response, api_response
)
from app.utils.i18n import get_available_languages, set_user_language, get_user_language
from app.services.health_service import HealthService


@api_bp.route('/health')
def health_check():
    """Health check endpoint for system monitoring."""
    try:
        # Use the health service to get comprehensive health status
        health_result = HealthService.get_overall_health()
        
        # Format individual check results
        checks = {}
        for service_name, check_result in health_result.checks.items():
            check_data = {
                "status": check_result.status,
                "response_time_ms": check_result.response_time_ms
            }
            if check_result.error:
                check_data["error"] = check_result.error
            
            checks[service_name] = check_data
        
        # Determine proper HTTP status code based on health status
        # Database failure = 503 (Service Unavailable)
        # Redis failure alone = 200 (OK) but with unhealthy Redis status
        status_code = 503 if health_result.status == "unhealthy" else 200
        
        return health_response(
            status=health_result.status,
            checks=checks,
            version=current_app.config.get('API_VERSION', '1.0.0'),
            status_code=status_code
        )
        
    except Exception as e:
        # Fallback error response for unexpected failures
        current_app.logger.error(f"Health check service failed: {str(e)}")
        return error_response(
            error_code="HEALTH_CHECK_FAILED",
            message="Health check service failed",
            status_code=503,
            details=str(e)
        )


@api_bp.route('/version')
def version_info():
    """API version and build information endpoint."""
    try:
        import flask
        
        return version_response(
            version=current_app.config.get('API_VERSION', '1.0.0'),
            build_date=current_app.config.get('BUILD_DATE'),
            environment=current_app.config.get('FLASK_ENV', 'development'),
            python_version=platform.python_version(),
            flask_version=flask.__version__
        )
        
    except Exception as e:
        return error_response(
            error_code="VERSION_INFO_FAILED",
            message="Failed to retrieve version information",
            status_code=500,
            details=str(e)
        )


@api_bp.route('/status')
def status():
    """Status endpoint with more detailed information."""
    return success_response(
        message=_('System is operational'),
        data={
            'service': 'ai-secretary-api',
            'version': '1.0.0',
            'components': {
                'database': _('healthy'),
                'redis': _('healthy'),
                'celery': _('healthy')
            },
            'language': get_user_language()
        }
    )


@api_bp.route('/languages')
def get_languages():
    """Get available languages."""
    return success_response(
        message=_('Available languages'),
        data={
            'languages': get_available_languages(),
            'current': get_user_language()
        }
    )


@api_bp.route('/language', methods=['POST'])
def set_language():
    """Set user language preference."""
    data = request.get_json()
    
    if not data or 'language' not in data:
        return error_response(
            error_code='VALIDATION_ERROR',
            message=_('Language code is required'),
            status_code=400
        )
    
    language_code = data['language']
    
    if set_user_language(language_code):
        return success_response(
            message=_('Language updated successfully'),
            data={'language': language_code}
        )
    else:
        available_languages = list(get_available_languages().keys())
        return error_response(
            error_code='VALIDATION_ERROR',
            message=_('Invalid language code. Available: %(languages)s', 
                     languages=', '.join(available_languages)),
            status_code=400
        )


@api_bp.route('/docs')
def api_docs():
    """API documentation endpoint."""
    return success_response(
        message="API Documentation",
        data={
            "title": "AI Secretary API",
            "version": current_app.config.get('API_VERSION', '1.0.0'),
            "description": "Intelligent assistant API for managing communications, CRM, and more",
            "base_url": request.host_url.rstrip('/'),
            "endpoints": {
                "welcome": {
                    "method": "GET",
                    "path": "/",
                    "description": "Welcome endpoint with API information"
                },
                "health": {
                    "method": "GET", 
                    "path": "/api/v1/health",
                    "description": "System health check"
                },
                "version": {
                    "method": "GET",
                    "path": "/api/v1/version", 
                    "description": "API version information"
                },
                "status": {
                    "method": "GET",
                    "path": "/api/v1/status",
                    "description": "Detailed system status"
                },
                "languages": {
                    "method": "GET",
                    "path": "/api/v1/languages",
                    "description": "Available languages"
                },
                "set_language": {
                    "method": "POST",
                    "path": "/api/v1/language",
                    "description": "Set user language preference"
                },
                "docs": {
                    "method": "GET",
                    "path": "/api/v1/docs",
                    "description": "This documentation endpoint"
                }
            },
            "documentation": {
                "swagger_ui": "/api/v1/docs/swagger",
                "redoc": "/api/v1/docs/redoc",
                "openapi_spec": "/api/v1/docs/openapi.yaml",
                "api_tester": "/api/v1/docs/tester",
                "examples": "/api/v1/docs/examples",
                "integration_guide": "/api/v1/docs/integration-guide",
                "postman_collection": "/api/v1/docs/postman"
            },
            "supported_languages": get_available_languages(),
            "cors_origins": current_app.config.get('CORS_ORIGINS', []),
            "environment": current_app.config.get('FLASK_ENV', 'development')
        }
    )