"""Main API routes."""
from flask import jsonify, request
from flask_babel import gettext as _
from app.api import api_bp
from app.utils.response import success_response, error_response
from app.utils.i18n import get_available_languages, set_user_language, get_user_language


@api_bp.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'ai-secretary-api',
        'version': '1.0.0',
        'language': get_user_language()
    })


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