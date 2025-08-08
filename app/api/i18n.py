"""Internationalization API endpoints."""
from flask import Blueprint, request, session, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from app.utils.response import success_response, error_response, validation_error_response
from app.utils.i18n import get_available_languages, set_user_language, get_user_language
from app.utils.multilingual import (
    TaskPriority, LeadStatus, ContactType, 
    get_validation_messages, localize_model_data
)
from app.models.user import User
from app import db
import structlog

logger = structlog.get_logger()

i18n_bp = Blueprint('i18n', __name__)


@i18n_bp.route('/languages', methods=['GET'])
def get_languages():
    """Get available languages and current language."""
    current_lang = get_user_language()
    
    return success_response(
        message=_('Available languages retrieved'),
        data={
            'languages': get_available_languages(),
            'current': current_lang,
            'supported': list(get_available_languages().keys())
        }
    )


@i18n_bp.route('/language', methods=['POST'])
def set_language():
    """Set user language preference."""
    data = request.get_json()
    
    if not data or 'language' not in data:
        return validation_error_response({
            'language': [_('Language code is required')]
        })
    
    language_code = data['language']
    available_languages = get_available_languages()
    
    if language_code not in available_languages:
        return error_response(
            error_code='VALIDATION_ERROR',
            message=_('Invalid language code'),
            status_code=400,
            details={
                'available_languages': list(available_languages.keys()),
                'provided': language_code
            }
        )
    
    # Set in session
    if set_user_language(language_code):
        # Update user profile if authenticated
        try:
            user = get_current_user()
            if user:
                user.language = language_code
                user.save()
                logger.info(
                    "User language updated",
                    user_id=user.id,
                    language=language_code
                )
        except Exception as e:
            logger.warning(
                "Failed to update user language in profile",
                error=str(e),
                language=language_code
            )
        
        return success_response(
            message=_('Language updated successfully'),
            data={
                'language': language_code,
                'language_name': available_languages[language_code]
            }
        )
    else:
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to set language'),
            status_code=500
        )


@i18n_bp.route('/enums', methods=['GET'])
def get_localized_enums():
    """Get localized enum values."""
    current_lang = get_user_language()
    
    return success_response(
        message=_('Localized enums retrieved'),
        data={
            'language': current_lang,
            'enums': {
                'task_priority': TaskPriority.get_choices(current_lang),
                'lead_status': LeadStatus.get_choices(current_lang),
                'contact_type': ContactType.get_choices(current_lang)
            }
        }
    )


@i18n_bp.route('/validation-messages', methods=['GET'])
def get_localized_validation_messages():
    """Get localized validation messages."""
    return success_response(
        message=_('Validation messages retrieved'),
        data={
            'language': get_user_language(),
            'messages': get_validation_messages()
        }
    )


@i18n_bp.route('/user/language', methods=['GET'])
@jwt_required()
def get_user_language_preference():
    """Get current user's language preference."""
    user = get_current_user()
    
    return success_response(
        message=_('User language preference retrieved'),
        data={
            'user_language': user.language,
            'session_language': session.get('language'),
            'current_language': get_user_language(),
            'available_languages': get_available_languages()
        }
    )


@i18n_bp.route('/user/language', methods=['PUT'])
@jwt_required()
def update_user_language_preference():
    """Update current user's language preference."""
    user = get_current_user()
    data = request.get_json()
    
    if not data or 'language' not in data:
        return validation_error_response({
            'language': [_('Language code is required')]
        })
    
    language_code = data['language']
    available_languages = get_available_languages()
    
    if language_code not in available_languages:
        return error_response(
            error_code='VALIDATION_ERROR',
            message=_('Invalid language code'),
            status_code=400,
            details={'available_languages': list(available_languages.keys())}
        )
    
    # Update user profile
    old_language = user.language
    user.language = language_code
    user.save()
    
    # Update session
    session['language'] = language_code
    
    logger.info(
        "User language preference updated",
        user_id=user.id,
        old_language=old_language,
        new_language=language_code
    )
    
    return success_response(
        message=_('Language preference updated successfully'),
        data={
            'language': language_code,
            'language_name': available_languages[language_code],
            'previous_language': old_language
        }
    )


@i18n_bp.route('/tenant/language', methods=['GET'])
@jwt_required()
def get_tenant_language_settings():
    """Get tenant's language settings."""
    user = get_current_user()
    
    if not user.tenant:
        return error_response(
            error_code='NOT_FOUND_ERROR',
            message=_('Tenant not found'),
            status_code=404
        )
    
    tenant_settings = {
        'default_language': user.tenant.get_setting('default_language', 'en'),
        'supported_languages': user.tenant.get_setting('supported_languages', ['en', 'de', 'uk']),
        'auto_detect_language': user.tenant.get_setting('auto_detect_language', True)
    }
    
    return success_response(
        message=_('Tenant language settings retrieved'),
        data=tenant_settings
    )


@i18n_bp.route('/tenant/language', methods=['PUT'])
@jwt_required()
def update_tenant_language_settings():
    """Update tenant's language settings."""
    user = get_current_user()
    
    if not user.can_manage_settings:
        return error_response(
            error_code='AUTHORIZATION_ERROR',
            message=_('Insufficient permissions to manage tenant settings'),
            status_code=403
        )
    
    if not user.tenant:
        return error_response(
            error_code='NOT_FOUND_ERROR',
            message=_('Tenant not found'),
            status_code=404
        )
    
    data = request.get_json()
    if not data:
        return validation_error_response({
            'data': [_('Request data is required')]
        })
    
    available_languages = list(get_available_languages().keys())
    errors = {}
    
    # Validate default_language
    if 'default_language' in data:
        if data['default_language'] not in available_languages:
            errors['default_language'] = [_('Invalid default language')]
    
    # Validate supported_languages
    if 'supported_languages' in data:
        if not isinstance(data['supported_languages'], list):
            errors['supported_languages'] = [_('Supported languages must be a list')]
        else:
            invalid_langs = [lang for lang in data['supported_languages'] 
                           if lang not in available_languages]
            if invalid_langs:
                errors['supported_languages'] = [
                    _('Invalid languages: %(languages)s', 
                      languages=', '.join(invalid_langs))
                ]
    
    if errors:
        return validation_error_response(errors)
    
    # Update tenant settings
    if 'default_language' in data:
        user.tenant.set_setting('default_language', data['default_language'])
    
    if 'supported_languages' in data:
        user.tenant.set_setting('supported_languages', data['supported_languages'])
    
    if 'auto_detect_language' in data:
        user.tenant.set_setting('auto_detect_language', bool(data['auto_detect_language']))
    
    user.tenant.save()
    
    logger.info(
        "Tenant language settings updated",
        tenant_id=user.tenant_id,
        user_id=user.id,
        settings=data
    )
    
    return success_response(
        message=_('Tenant language settings updated successfully'),
        data={
            'default_language': user.tenant.get_setting('default_language'),
            'supported_languages': user.tenant.get_setting('supported_languages'),
            'auto_detect_language': user.tenant.get_setting('auto_detect_language')
        }
    )


@i18n_bp.route('/localize', methods=['POST'])
def localize_data():
    """Localize data based on model type."""
    data = request.get_json()
    
    if not data or 'model_type' not in data or 'data' not in data:
        return validation_error_response({
            'model_type': [_('Model type is required')],
            'data': [_('Data is required')]
        })
    
    model_type = data['model_type']
    model_data = data['data']
    language = data.get('language', get_user_language())
    
    try:
        localized_data = localize_model_data(model_data, model_type)
        
        return success_response(
            message=_('Data localized successfully'),
            data={
                'localized_data': localized_data,
                'language': language,
                'model_type': model_type
            }
        )
    except Exception as e:
        logger.error(
            "Failed to localize data",
            model_type=model_type,
            error=str(e),
            exc_info=True
        )
        
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to localize data'),
            status_code=500
        )