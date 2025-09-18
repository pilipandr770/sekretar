"""Admin routes for translation management and monitoring."""
from flask import request, jsonify, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from app.admin import admin_bp
from app.services.translation_service import TranslationService, TranslationValidationError
from app.models.translation_stats import TranslationStats, MissingTranslation, TranslationValidationError as ValidationErrorModel
from app.models.role import Permission
from app.utils.decorators import (
    require_json, log_api_call, validate_pagination,
    require_permission, require_permissions
)
from app.utils.response import (
    success_response, error_response, validation_error_response,
    unauthorized_response, not_found_response
)
from app.utils.i18n import LANGUAGES
from app import db
import structlog
from datetime import datetime

logger = structlog.get_logger()


# Translation Management Endpoints

@admin_bp.route('/translations/overview', methods=['GET'])
@jwt_required()
@require_permission(Permission.MANAGE_TRANSLATIONS)
@log_api_call('get_translation_overview')
def get_translation_overview():
    """Get comprehensive translation overview and statistics."""
    try:
        translation_service = TranslationService()
        
        # Get translation statistics
        stats = translation_service.get_translation_statistics()
        
        # Get database stats
        db_stats = TranslationStats.get_all_languages()
        db_stats_dict = {stat.language: stat.to_dict() for stat in db_stats}
        
        # Get missing translation counts
        missing_counts = {}
        validation_error_counts = {}
        
        for lang_code in LANGUAGES.keys():
            missing_counts[lang_code] = MissingTranslation.get_unresolved_count(lang_code)
            validation_error_counts[lang_code] = ValidationErrorModel.get_error_summary(lang_code)
        
        # Combine data
        overview = {
            'overall_statistics': {
                'overall_coverage': stats.get('overall_coverage', 0),
                'total_languages': stats.get('total_languages', 0),
                'complete_languages': stats.get('complete_languages', 0),
                'total_messages': stats.get('total_messages', 0),
                'last_updated': stats.get('last_updated')
            },
            'language_details': {},
            'system_status': {
                'translation_files_exist': True,
                'babel_configured': True,
                'extraction_available': True,
                'compilation_available': True
            }
        }
        
        # Process each language
        for lang_code, lang_name in LANGUAGES.items():
            file_stats = stats.get('languages', {}).get(lang_code, {})
            db_stat = db_stats_dict.get(lang_code, {})
            
            overview['language_details'][lang_code] = {
                'language_name': lang_name,
                'language_code': lang_code,
                'coverage_percentage': file_stats.get('coverage_percentage', 0),
                'status': file_stats.get('status', 'missing'),
                'total_messages': file_stats.get('total_messages', 0),
                'translated_messages': file_stats.get('translated_messages', 0),
                'untranslated_messages': file_stats.get('untranslated_messages', 0),
                'fuzzy_messages': file_stats.get('fuzzy_messages', 0),
                'missing_translations': missing_counts.get(lang_code, 0),
                'validation_errors': validation_error_counts.get(lang_code, {}).get('total_errors', 0),
                'last_updated': file_stats.get('last_updated'),
                'last_extraction': db_stat.get('last_extraction'),
                'last_compilation': db_stat.get('last_compilation')
            }
        
        return success_response(
            message=_('Translation overview retrieved successfully'),
            data=overview
        )
        
    except Exception as e:
        logger.error("Failed to get translation overview", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve translation overview'),
            status_code=500
        )


@admin_bp.route('/translations/extract', methods=['POST'])
@jwt_required()
@require_permission(Permission.MANAGE_TRANSLATIONS)
@log_api_call('extract_translations')
def extract_translations():
    """Extract translatable messages from the application."""
    try:
        current_user = get_current_user()
        translation_service = TranslationService()
        
        # Extract messages
        result = translation_service.extract_messages()
        
        # Update database statistics
        for lang_code in LANGUAGES.keys():
            TranslationStats.update_stats(lang_code, {
                'last_extraction': datetime.utcnow()
            })
        
        logger.info(
            "Translation extraction completed",
            extracted_messages=result.get('extracted_messages'),
            updated_languages=result.get('updated_languages'),
            user_id=current_user.id
        )
        
        return success_response(
            message=_('Translation extraction completed successfully'),
            data=result
        )
        
    except TranslationValidationError as e:
        logger.error("Translation extraction failed", error=str(e))
        return error_response(
            error_code='VALIDATION_ERROR',
            message=str(e),
            status_code=400
        )
    except Exception as e:
        logger.error("Failed to extract translations", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to extract translations'),
            status_code=500
        )


@admin_bp.route('/translations/compile', methods=['POST'])
@jwt_required()
@require_permission(Permission.MANAGE_TRANSLATIONS)
@log_api_call('compile_translations')
def compile_translations():
    """Compile translation files (.po to .mo)."""
    try:
        current_user = get_current_user()
        translation_service = TranslationService()
        
        # Compile translations
        result = translation_service.compile_translations()
        
        # Update database statistics
        for lang_code in result.get('compiled_languages', []):
            TranslationStats.update_stats(lang_code, {
                'last_compilation': datetime.utcnow()
            })
        
        logger.info(
            "Translation compilation completed",
            compiled_languages=result.get('compiled_languages'),
            compilation_errors=result.get('compilation_errors'),
            user_id=current_user.id
        )
        
        return success_response(
            message=_('Translation compilation completed successfully'),
            data=result
        )
        
    except TranslationValidationError as e:
        logger.error("Translation compilation failed", error=str(e))
        return error_response(
            error_code='VALIDATION_ERROR',
            message=str(e),
            status_code=400
        )
    except Exception as e:
        logger.error("Failed to compile translations", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to compile translations'),
            status_code=500
        )


@admin_bp.route('/translations/validate', methods=['POST'])
@jwt_required()
@require_permission(Permission.MANAGE_TRANSLATIONS)
@log_api_call('validate_translations')
def validate_translations():
    """Validate translations for consistency and correctness."""
    try:
        current_user = get_current_user()
        data = request.get_json() or {}
        language = data.get('language')  # Optional: validate specific language
        
        translation_service = TranslationService()
        
        # Validate translations
        validation_errors = translation_service.validate_translations(language)
        
        # Store validation errors in database
        for error in validation_errors:
            ValidationErrorModel.log_error(
                language=error['language'],
                message_id=error.get('message_id', ''),
                error_type=error['type'],
                error_message=error['message'],
                severity=error['severity'],
                source_file=error.get('locations', [None])[0] if error.get('locations') else None
            )
        
        # Update validation error counts in stats
        for lang_code in LANGUAGES.keys():
            if not language or language == lang_code:
                error_count = len([e for e in validation_errors if e['language'] == lang_code])
                TranslationStats.update_stats(lang_code, {
                    'validation_errors': error_count
                })
        
        logger.info(
            "Translation validation completed",
            total_errors=len(validation_errors),
            language=language,
            user_id=current_user.id
        )
        
        return success_response(
            message=_('Translation validation completed successfully'),
            data={
                'validation_errors': validation_errors,
                'total_errors': len(validation_errors),
                'errors_by_language': {
                    lang: len([e for e in validation_errors if e['language'] == lang])
                    for lang in LANGUAGES.keys()
                },
                'errors_by_severity': {
                    'error': len([e for e in validation_errors if e['severity'] == 'error']),
                    'warning': len([e for e in validation_errors if e['severity'] == 'warning']),
                    'info': len([e for e in validation_errors if e['severity'] == 'info'])
                }
            }
        )
        
    except TranslationValidationError as e:
        logger.error("Translation validation failed", error=str(e))
        return error_response(
            error_code='VALIDATION_ERROR',
            message=str(e),
            status_code=400
        )
    except Exception as e:
        logger.error("Failed to validate translations", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to validate translations'),
            status_code=500
        )


@admin_bp.route('/translations/coverage', methods=['GET'])
@jwt_required()
@require_permission(Permission.MANAGE_TRANSLATIONS)
@log_api_call('get_translation_coverage')
def get_translation_coverage():
    """Get detailed translation coverage for all languages."""
    try:
        translation_service = TranslationService()
        
        # Get coverage from files
        coverage_stats = translation_service.get_translation_coverage()
        
        # Update database with latest stats
        for lang_code, stats in coverage_stats.items():
            TranslationStats.update_stats(lang_code, stats)
        
        return success_response(
            message=_('Translation coverage retrieved successfully'),
            data={
                'languages': coverage_stats,
                'summary': {
                    'total_languages': len(coverage_stats),
                    'complete_languages': len([s for s in coverage_stats.values() if s['status'] == 'complete']),
                    'average_coverage': sum(s['coverage_percentage'] for s in coverage_stats.values()) / len(coverage_stats) if coverage_stats else 0
                }
            }
        )
        
    except Exception as e:
        logger.error("Failed to get translation coverage", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve translation coverage'),
            status_code=500
        )


@admin_bp.route('/translations/missing', methods=['GET'])
@jwt_required()
@require_permission(Permission.MANAGE_TRANSLATIONS)
@validate_pagination()
@log_api_call('get_missing_translations')
def get_missing_translations():
    """Get missing translations with pagination and filtering."""
    try:
        language = request.args.get('language')
        priority = request.args.get('priority')
        
        # Build query
        query = MissingTranslation.query.filter_by(is_resolved=False)
        
        if language:
            query = query.filter_by(language=language)
        
        if priority:
            query = query.filter_by(priority=priority)
        
        # Apply sorting
        sort_by = request.args.get('sort_by', 'occurrence_count')
        sort_order = request.args.get('sort_order', 'desc')
        
        if hasattr(MissingTranslation, sort_by):
            if sort_order == 'asc':
                query = query.order_by(getattr(MissingTranslation, sort_by).asc())
            else:
                query = query.order_by(getattr(MissingTranslation, sort_by).desc())
        
        # Paginate
        pagination = query.paginate(
            page=g.page,
            per_page=g.per_page,
            error_out=False
        )
        
        # Get summary statistics
        summary = {}
        for lang_code in LANGUAGES.keys():
            summary[lang_code] = MissingTranslation.get_unresolved_count(lang_code)
        
        return success_response(
            message=_('Missing translations retrieved successfully'),
            data={
                'missing_translations': [item.to_dict() for item in pagination.items],
                'pagination': {
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                },
                'summary': summary
            }
        )
        
    except Exception as e:
        logger.error("Failed to get missing translations", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve missing translations'),
            status_code=500
        )


@admin_bp.route('/translations/missing/refresh', methods=['POST'])
@jwt_required()
@require_permission(Permission.MANAGE_TRANSLATIONS)
@log_api_call('refresh_missing_translations')
def refresh_missing_translations():
    """Refresh missing translations by scanning translation files."""
    try:
        current_user = get_current_user()
        translation_service = TranslationService()
        
        # Get missing translations from files
        missing_translations = translation_service.get_missing_translations()
        
        # Update database
        total_missing = 0
        for lang_code, missing_list in missing_translations.items():
            for message_id in missing_list:
                MissingTranslation.log_missing(lang_code, message_id)
                total_missing += 1
        
        logger.info(
            "Missing translations refreshed",
            total_missing=total_missing,
            languages=list(missing_translations.keys()),
            user_id=current_user.id
        )
        
        return success_response(
            message=_('Missing translations refreshed successfully'),
            data={
                'total_missing': total_missing,
                'by_language': {lang: len(missing) for lang, missing in missing_translations.items()}
            }
        )
        
    except Exception as e:
        logger.error("Failed to refresh missing translations", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to refresh missing translations'),
            status_code=500
        )


@admin_bp.route('/translations/validation-errors', methods=['GET'])
@jwt_required()
@require_permission(Permission.MANAGE_TRANSLATIONS)
@validate_pagination()
@log_api_call('get_validation_errors')
def get_validation_errors():
    """Get translation validation errors with pagination and filtering."""
    try:
        language = request.args.get('language')
        error_type = request.args.get('error_type')
        severity = request.args.get('severity')
        
        # Build query
        query = ValidationErrorModel.query.filter_by(is_resolved=False)
        
        if language:
            query = query.filter_by(language=language)
        
        if error_type:
            query = query.filter_by(error_type=error_type)
        
        if severity:
            query = query.filter_by(severity=severity)
        
        # Apply sorting
        sort_by = request.args.get('sort_by', 'detection_count')
        sort_order = request.args.get('sort_order', 'desc')
        
        if hasattr(ValidationErrorModel, sort_by):
            if sort_order == 'asc':
                query = query.order_by(getattr(ValidationErrorModel, sort_by).asc())
            else:
                query = query.order_by(getattr(ValidationErrorModel, sort_by).desc())
        
        # Paginate
        pagination = query.paginate(
            page=g.page,
            per_page=g.per_page,
            error_out=False
        )
        
        # Get summary statistics
        summary = {}
        for lang_code in LANGUAGES.keys():
            summary[lang_code] = ValidationErrorModel.get_error_summary(lang_code)
        
        return success_response(
            message=_('Validation errors retrieved successfully'),
            data={
                'validation_errors': [item.to_dict() for item in pagination.items],
                'pagination': {
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                },
                'summary': summary
            }
        )
        
    except Exception as e:
        logger.error("Failed to get validation errors", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve validation errors'),
            status_code=500
        )


@admin_bp.route('/translations/update', methods=['POST'])
@jwt_required()
@require_json(['language', 'message_id', 'translation'])
@require_permission(Permission.MANAGE_TRANSLATIONS)
@log_api_call('update_translation')
def update_translation():
    """Update a specific translation."""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        language = data['language']
        message_id = data['message_id']
        translation = data['translation']
        
        # Validate language
        if language not in LANGUAGES:
            return validation_error_response({
                'language': [_('Invalid language code')]
            })
        
        translation_service = TranslationService()
        
        # Update translation
        success = translation_service.update_translation(language, message_id, translation)
        
        if success:
            # Mark missing translation as resolved
            MissingTranslation.mark_resolved(language, message_id)
            
            # Mark related validation errors as resolved
            ValidationErrorModel.mark_resolved(language, message_id, 'missing_translation')
            
            logger.info(
                "Translation updated successfully",
                language=language,
                message_id=message_id,
                user_id=current_user.id
            )
            
            return success_response(
                message=_('Translation updated successfully'),
                data={
                    'language': language,
                    'message_id': message_id,
                    'translation': translation
                }
            )
        else:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Failed to update translation'),
                status_code=400
            )
        
    except Exception as e:
        logger.error("Failed to update translation", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update translation'),
            status_code=500
        )


@admin_bp.route('/translations/statistics', methods=['GET'])
@jwt_required()
@require_permission(Permission.MANAGE_TRANSLATIONS)
@log_api_call('get_translation_statistics')
def get_translation_statistics():
    """Get comprehensive translation statistics and trends."""
    try:
        # Get current statistics
        translation_service = TranslationService()
        current_stats = translation_service.get_translation_statistics()
        
        # Get historical data from database
        db_stats = TranslationStats.get_all_languages()
        
        # Get missing translations and validation errors
        missing_summary = {}
        validation_summary = {}
        
        for lang_code in LANGUAGES.keys():
            missing_summary[lang_code] = MissingTranslation.get_unresolved_count(lang_code)
            validation_summary[lang_code] = ValidationErrorModel.get_error_summary(lang_code)
        
        # Compile comprehensive statistics
        statistics = {
            'overview': current_stats,
            'database_stats': [stat.to_dict() for stat in db_stats],
            'missing_translations': missing_summary,
            'validation_errors': validation_summary,
            'system_health': {
                'total_missing': sum(missing_summary.values()),
                'total_validation_errors': sum(s['total_errors'] for s in validation_summary.values()),
                'languages_with_issues': len([lang for lang, count in missing_summary.items() if count > 0]),
                'overall_health_score': _calculate_health_score(current_stats, missing_summary, validation_summary)
            }
        }
        
        return success_response(
            message=_('Translation statistics retrieved successfully'),
            data=statistics
        )
        
    except Exception as e:
        logger.error("Failed to get translation statistics", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve translation statistics'),
            status_code=500
        )


def _calculate_health_score(stats, missing_summary, validation_summary):
    """Calculate overall translation system health score (0-100)."""
    try:
        # Base score from coverage
        coverage_score = stats.get('overall_coverage', 0)
        
        # Penalty for missing translations
        total_missing = sum(missing_summary.values())
        missing_penalty = min(total_missing * 2, 30)  # Max 30 point penalty
        
        # Penalty for validation errors
        total_errors = sum(s['total_errors'] for s in validation_summary.values())
        error_penalty = min(total_errors * 1, 20)  # Max 20 point penalty
        
        # Calculate final score
        health_score = max(0, coverage_score - missing_penalty - error_penalty)
        
        return round(health_score, 1)
        
    except Exception:
        return 0.0