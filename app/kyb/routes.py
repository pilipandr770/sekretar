"""KYB monitoring API endpoints."""
from flask import Blueprint, request, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from sqlalchemy import and_, or_, desc
from datetime import datetime, timedelta
from app.models.kyb_monitoring import (
    Counterparty, CounterpartySnapshot, CounterpartyDiff, 
    KYBAlert, KYBMonitoringConfig
)
from app.models.user import User
from app.utils.decorators import (
    require_json, require_permission, 
    log_api_call, validate_pagination, audit_log
)
from app.utils.response import (
    success_response, error_response, validation_error_response,
    not_found_response, paginated_response, conflict_response
)
import structlog

logger = structlog.get_logger()

from app.kyb import kyb_bp


# ============================================================================
# COUNTERPARTY ENDPOINTS
# ============================================================================

@kyb_bp.route('/counterparties', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@validate_pagination()
@log_api_call('list_counterparties')
def list_counterparties():
    """List counterparties with filtering and pagination."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        page = g.page
        per_page = g.per_page
        
        # Build query
        query = Counterparty.query.filter_by(tenant_id=tenant_id)
        
        # Apply filters
        if request.args.get('status'):
            query = query.filter_by(status=request.args.get('status'))
        
        if request.args.get('risk_level'):
            query = query.filter_by(risk_level=request.args.get('risk_level'))
        
        if request.args.get('country_code'):
            query = query.filter_by(country_code=request.args.get('country_code'))
        
        if request.args.get('monitoring_enabled') == 'true':
            query = query.filter_by(monitoring_enabled=True)
        elif request.args.get('monitoring_enabled') == 'false':
            query = query.filter_by(monitoring_enabled=False)
        
        if request.args.get('search'):
            search_term = f"%{request.args.get('search')}%"
            query = query.filter(
                or_(
                    Counterparty.name.ilike(search_term),
                    Counterparty.vat_number.ilike(search_term),
                    Counterparty.lei_code.ilike(search_term),
                    Counterparty.registration_number.ilike(search_term),
                    Counterparty.email.ilike(search_term)
                )
            )
        
        # Filter by risk score range
        if request.args.get('min_risk_score'):
            try:
                min_score = float(request.args.get('min_risk_score'))
                query = query.filter(Counterparty.risk_score >= min_score)
            except ValueError:
                pass
        
        if request.args.get('max_risk_score'):
            try:
                max_score = float(request.args.get('max_risk_score'))
                query = query.filter(Counterparty.risk_score <= max_score)
            except ValueError:
                pass
        
        # Order by risk score (highest first), then name
        query = query.order_by(Counterparty.risk_score.desc(), Counterparty.name.asc())
        
        # Paginate
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        counterparties = [cp.to_dict() for cp in pagination.items]
        
        return paginated_response(
            items=counterparties,
            page=page,
            per_page=per_page,
            total=pagination.total,
            message=_('Counterparties retrieved successfully')
        )
        
    except Exception as e:
        logger.error("Failed to list counterparties", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve counterparties'),
            status_code=500
        )


@kyb_bp.route('/counterparties', methods=['POST'])
@jwt_required()
@require_permission('manage_kyb')
@require_json(['name'])
@log_api_call('create_counterparty')
@audit_log('create', 'counterparty')
def create_counterparty():
    """Create new counterparty."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        data = request.get_json()
        
        name = data['name'].strip()
        if not name:
            return validation_error_response({
                'name': [_('Counterparty name is required')]
            })
        
        # Check for duplicate VAT number if provided
        vat_number = data.get('vat_number')
        if vat_number:
            existing_cp = Counterparty.query.filter_by(
                tenant_id=tenant_id,
                vat_number=vat_number
            ).first()
            if existing_cp:
                return conflict_response(_('Counterparty with this VAT number already exists'))
        
        # Check for duplicate LEI code if provided
        lei_code = data.get('lei_code')
        if lei_code:
            existing_cp = Counterparty.query.filter_by(
                tenant_id=tenant_id,
                lei_code=lei_code
            ).first()
            if existing_cp:
                return conflict_response(_('Counterparty with this LEI code already exists'))
        
        # Create counterparty
        counterparty = Counterparty.create(
            tenant_id=tenant_id,
            name=name,
            vat_number=vat_number,
            lei_code=lei_code,
            registration_number=data.get('registration_number'),
            address=data.get('address'),
            country_code=data.get('country_code'),
            city=data.get('city'),
            postal_code=data.get('postal_code'),
            email=data.get('email'),
            phone=data.get('phone'),
            website=data.get('website'),
            monitoring_enabled=data.get('monitoring_enabled', True),
            monitoring_frequency=data.get('monitoring_frequency', 'daily'),
            notes=data.get('notes'),
            tags=data.get('tags', []),
            custom_fields=data.get('custom_fields', {})
        )
        
        logger.info("Counterparty created", counterparty_id=counterparty.id, tenant_id=tenant_id, user_id=user.id)
        
        return success_response(
            message=_('Counterparty created successfully'),
            data=counterparty.to_dict(),
            status_code=201
        )
        
    except Exception as e:
        logger.error("Failed to create counterparty", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to create counterparty'),
            status_code=500
        )


@kyb_bp.route('/counterparties/<int:counterparty_id>', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@log_api_call('get_counterparty')
def get_counterparty(counterparty_id):
    """Get specific counterparty with recent snapshots and alerts."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Find counterparty in same tenant
        counterparty = Counterparty.query.filter_by(
            id=counterparty_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not counterparty:
            return not_found_response('counterparty')
        
        # Get counterparty data with related information
        data = counterparty.to_dict()
        
        # Add recent snapshots (last 10)
        recent_snapshots = CounterpartySnapshot.query.filter_by(
            counterparty_id=counterparty_id
        ).order_by(CounterpartySnapshot.created_at.desc()).limit(10).all()
        
        data['recent_snapshots'] = [snapshot.to_dict() for snapshot in recent_snapshots]
        
        # Add recent alerts (last 10)
        recent_alerts = KYBAlert.query.filter_by(
            counterparty_id=counterparty_id
        ).order_by(KYBAlert.created_at.desc()).limit(10).all()
        
        data['recent_alerts'] = [alert.to_dict() for alert in recent_alerts]
        
        # Add statistics
        data['statistics'] = {
            'total_snapshots': CounterpartySnapshot.query.filter_by(counterparty_id=counterparty_id).count(),
            'total_alerts': KYBAlert.query.filter_by(counterparty_id=counterparty_id).count(),
            'open_alerts': KYBAlert.query.filter_by(counterparty_id=counterparty_id, status='open').count(),
            'last_check': counterparty.last_checked.isoformat() if counterparty.last_checked else None,
            'next_check': counterparty.next_check.isoformat() if counterparty.next_check else None
        }
        
        return success_response(
            message=_('Counterparty retrieved successfully'),
            data=data
        )
        
    except Exception as e:
        logger.error("Failed to get counterparty", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve counterparty'),
            status_code=500
        )


@kyb_bp.route('/counterparties/<int:counterparty_id>', methods=['PUT'])
@jwt_required()
@require_permission('manage_kyb')
@require_json()
@log_api_call('update_counterparty')
@audit_log('update', 'counterparty')
def update_counterparty(counterparty_id):
    """Update counterparty."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        data = request.get_json()
        
        # Find counterparty in same tenant
        counterparty = Counterparty.query.filter_by(
            id=counterparty_id,
            tenant_id=tenant_id
        ).first()
        
        if not counterparty:
            return not_found_response('counterparty')
        
        # Check for duplicate VAT number if being changed
        vat_number = data.get('vat_number')
        if vat_number and vat_number != counterparty.vat_number:
            existing_cp = Counterparty.query.filter_by(
                tenant_id=tenant_id,
                vat_number=vat_number
            ).first()
            if existing_cp:
                return conflict_response(_('Counterparty with this VAT number already exists'))
        
        # Check for duplicate LEI code if being changed
        lei_code = data.get('lei_code')
        if lei_code and lei_code != counterparty.lei_code:
            existing_cp = Counterparty.query.filter_by(
                tenant_id=tenant_id,
                lei_code=lei_code
            ).first()
            if existing_cp:
                return conflict_response(_('Counterparty with this LEI code already exists'))
        
        # Fields that can be updated
        updatable_fields = [
            'name', 'vat_number', 'lei_code', 'registration_number', 'address',
            'country_code', 'city', 'postal_code', 'email', 'phone', 'website',
            'monitoring_enabled', 'monitoring_frequency', 'notes', 'tags', 'custom_fields'
        ]
        
        for field in updatable_fields:
            if field in data:
                # Validate specific fields
                if field == 'name' and not data[field].strip():
                    return validation_error_response({
                        'name': [_('Counterparty name is required')]
                    })
                
                setattr(counterparty, field, data[field])
        
        # Update risk level based on risk score if risk score changed
        if 'risk_score' in data:
            counterparty.risk_score = data['risk_score']
            counterparty.update_risk_level()
        
        counterparty.save()
        
        logger.info("Counterparty updated", counterparty_id=counterparty.id, user_id=user.id)
        
        return success_response(
            message=_('Counterparty updated successfully'),
            data=counterparty.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to update counterparty", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update counterparty'),
            status_code=500
        )


@kyb_bp.route('/counterparties/<int:counterparty_id>', methods=['DELETE'])
@jwt_required()
@require_permission('manage_kyb')
@log_api_call('delete_counterparty')
@audit_log('delete', 'counterparty')
def delete_counterparty(counterparty_id):
    """Delete counterparty."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Find counterparty in same tenant
        counterparty = Counterparty.query.filter_by(
            id=counterparty_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not counterparty:
            return not_found_response('counterparty')
        
        # Soft delete (this will cascade to related records due to model relationships)
        counterparty.delete()
        
        logger.info("Counterparty deleted", counterparty_id=counterparty.id, user_id=user.id)
        
        return success_response(
            message=_('Counterparty deleted successfully')
        )
        
    except Exception as e:
        logger.error("Failed to delete counterparty", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to delete counterparty'),
            status_code=500
        )


# ============================================================================
# MONITORING CONFIGURATION ENDPOINTS
# ============================================================================

@kyb_bp.route('/config', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@log_api_call('get_kyb_config')
def get_kyb_config():
    """Get KYB monitoring configuration for tenant."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        
        # Get or create config
        config = KYBMonitoringConfig.query.filter_by(tenant_id=tenant_id).first()
        if not config:
            # Create default config
            config = KYBMonitoringConfig.create(tenant_id=tenant_id)
        
        return success_response(
            message=_('KYB configuration retrieved successfully'),
            data=config.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to get KYB config", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve KYB configuration'),
            status_code=500
        )


@kyb_bp.route('/config', methods=['PUT'])
@jwt_required()
@require_permission('manage_kyb')
@require_json()
@log_api_call('update_kyb_config')
@audit_log('update', 'kyb_config')
def update_kyb_config():
    """Update KYB monitoring configuration."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        data = request.get_json()
        
        # Get or create config
        config = KYBMonitoringConfig.query.filter_by(tenant_id=tenant_id).first()
        if not config:
            config = KYBMonitoringConfig.create(tenant_id=tenant_id)
        
        # Fields that can be updated
        updatable_fields = [
            'vies_enabled', 'gleif_enabled', 'sanctions_eu_enabled', 'sanctions_ofac_enabled',
            'sanctions_uk_enabled', 'insolvency_de_enabled', 'default_check_frequency',
            'high_risk_check_frequency', 'low_risk_check_frequency', 'alert_on_sanctions_match',
            'alert_on_vat_invalid', 'alert_on_lei_invalid', 'alert_on_insolvency',
            'alert_on_data_change', 'email_notifications', 'telegram_notifications',
            'webhook_notifications', 'webhook_url', 'sanctions_weight', 'insolvency_weight',
            'vat_invalid_weight', 'lei_invalid_weight', 'data_change_weight',
            'snapshot_retention_days', 'alert_retention_days'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(config, field, data[field])
        
        config.save()
        
        logger.info("KYB config updated", tenant_id=tenant_id, user_id=user.id)
        
        return success_response(
            message=_('KYB configuration updated successfully'),
            data=config.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to update KYB config", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update KYB configuration'),
            status_code=500
        )


# ============================================================================
# ALERT MANAGEMENT ENDPOINTS
# ============================================================================

@kyb_bp.route('/alerts', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@validate_pagination()
@log_api_call('list_kyb_alerts')
def list_kyb_alerts():
    """List KYB alerts with filtering and pagination."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        page = g.page
        per_page = g.per_page
        
        # Build query
        query = KYBAlert.query.filter_by(tenant_id=tenant_id)
        
        # Apply filters
        if request.args.get('status'):
            query = query.filter_by(status=request.args.get('status'))
        
        if request.args.get('severity'):
            query = query.filter_by(severity=request.args.get('severity'))
        
        if request.args.get('alert_type'):
            query = query.filter_by(alert_type=request.args.get('alert_type'))
        
        if request.args.get('counterparty_id'):
            query = query.filter_by(counterparty_id=int(request.args.get('counterparty_id')))
        
        if request.args.get('unread') == 'true':
            query = query.filter_by(status='open')
        
        if request.args.get('search'):
            search_term = f"%{request.args.get('search')}%"
            query = query.join(KYBAlert.counterparty).filter(
                or_(
                    KYBAlert.title.ilike(search_term),
                    KYBAlert.message.ilike(search_term),
                    Counterparty.name.ilike(search_term)
                )
            )
        
        # Order by severity (critical first), then creation date (newest first)
        severity_order = {
            'critical': 4,
            'high': 3,
            'medium': 2,
            'low': 1
        }
        
        query = query.order_by(
            KYBAlert.severity.desc(),
            KYBAlert.created_at.desc()
        )
        
        # Paginate
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        alerts = [alert.to_dict() for alert in pagination.items]
        
        return paginated_response(
            items=alerts,
            page=page,
            per_page=per_page,
            total=pagination.total,
            message=_('KYB alerts retrieved successfully')
        )
        
    except Exception as e:
        logger.error("Failed to list KYB alerts", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve KYB alerts'),
            status_code=500
        )


@kyb_bp.route('/alerts/<int:alert_id>', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@log_api_call('get_kyb_alert')
def get_kyb_alert(alert_id):
    """Get specific KYB alert."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Find alert in same tenant
        alert = KYBAlert.query.filter_by(
            id=alert_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not alert:
            return not_found_response('alert')
        
        return success_response(
            message=_('KYB alert retrieved successfully'),
            data=alert.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to get KYB alert", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve KYB alert'),
            status_code=500
        )


@kyb_bp.route('/alerts/<int:alert_id>/acknowledge', methods=['POST'])
@jwt_required()
@require_permission('manage_kyb')
@log_api_call('acknowledge_kyb_alert')
@audit_log('acknowledge', 'kyb_alert')
def acknowledge_kyb_alert(alert_id):
    """Acknowledge KYB alert."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json() or {}
        notes = data.get('notes')
        
        # Find alert in same tenant
        alert = KYBAlert.query.filter_by(
            id=alert_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not alert:
            return not_found_response('alert')
        
        if alert.status != 'open':
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Only open alerts can be acknowledged'),
                status_code=400
            )
        
        alert.acknowledge(user.id, notes)
        alert.save()
        
        logger.info("KYB alert acknowledged", alert_id=alert.id, user_id=user.id)
        
        return success_response(
            message=_('KYB alert acknowledged successfully'),
            data=alert.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to acknowledge KYB alert", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to acknowledge KYB alert'),
            status_code=500
        )


@kyb_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
@jwt_required()
@require_permission('manage_kyb')
@log_api_call('resolve_kyb_alert')
@audit_log('resolve', 'kyb_alert')
def resolve_kyb_alert(alert_id):
    """Resolve KYB alert."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json() or {}
        notes = data.get('notes')
        
        # Find alert in same tenant
        alert = KYBAlert.query.filter_by(
            id=alert_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not alert:
            return not_found_response('alert')
        
        if alert.status in ['resolved', 'false_positive']:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Alert is already resolved'),
                status_code=400
            )
        
        alert.resolve(user.id, notes)
        alert.save()
        
        logger.info("KYB alert resolved", alert_id=alert.id, user_id=user.id)
        
        return success_response(
            message=_('KYB alert resolved successfully'),
            data=alert.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to resolve KYB alert", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to resolve KYB alert'),
            status_code=500
        )


@kyb_bp.route('/alerts/<int:alert_id>/false-positive', methods=['POST'])
@jwt_required()
@require_permission('manage_kyb')
@log_api_call('mark_kyb_alert_false_positive')
@audit_log('mark_false_positive', 'kyb_alert')
def mark_kyb_alert_false_positive(alert_id):
    """Mark KYB alert as false positive."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json() or {}
        notes = data.get('notes')
        
        # Find alert in same tenant
        alert = KYBAlert.query.filter_by(
            id=alert_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not alert:
            return not_found_response('alert')
        
        if alert.status in ['resolved', 'false_positive']:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Alert is already resolved'),
                status_code=400
            )
        
        alert.mark_false_positive(user.id, notes)
        alert.save()
        
        logger.info("KYB alert marked as false positive", alert_id=alert.id, user_id=user.id)
        
        return success_response(
            message=_('KYB alert marked as false positive successfully'),
            data=alert.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to mark KYB alert as false positive", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to mark KYB alert as false positive'),
            status_code=500
        )


# ============================================================================
# LEI VALIDATION ENDPOINTS
# ============================================================================

@kyb_bp.route('/lei/validate', methods=['POST'])
@jwt_required()
@require_permission('view_kyb')
@require_json(['lei_code'])
@log_api_call('validate_lei')
def validate_lei():
    """Validate LEI code format and check against GLEIF database."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json()
        lei_code = data['lei_code'].strip()
        
        if not lei_code:
            return validation_error_response({
                'lei_code': [_('LEI code is required')]
            })
        
        # Import here to avoid circular imports
        from app.services.kyb_service import KYBService
        
        # Check LEI code
        result = KYBService.check_lei_code(
            lei_code,
            force_refresh=data.get('force_refresh', False),
            timeout=data.get('timeout', 15),
            include_relationships=data.get('include_relationships', False)
        )
        
        logger.info("LEI validation performed", 
                   lei_code=lei_code, 
                   status=result.get('status'),
                   user_id=user.id)
        
        return success_response(
            message=_('LEI validation completed'),
            data=result
        )
        
    except Exception as e:
        logger.error("Failed to validate LEI", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to validate LEI code'),
            status_code=500
        )


@kyb_bp.route('/lei/validate-format', methods=['POST'])
@jwt_required()
@require_permission('view_kyb')
@require_json(['lei_code'])
@log_api_call('validate_lei_format')
def validate_lei_format():
    """Validate LEI code format without making API call."""
    try:
        data = request.get_json()
        lei_code = data['lei_code'].strip()
        
        if not lei_code:
            return validation_error_response({
                'lei_code': [_('LEI code is required')]
            })
        
        # Import here to avoid circular imports
        from app.services.kyb_service import KYBService
        
        # Validate format only
        result = KYBService.validate_lei_format(lei_code)
        
        return success_response(
            message=_('LEI format validation completed'),
            data=result
        )
        
    except Exception as e:
        logger.error("Failed to validate LEI format", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to validate LEI format'),
            status_code=500
        )


@kyb_bp.route('/lei/batch-validate', methods=['POST'])
@jwt_required()
@require_permission('view_kyb')
@require_json(['lei_codes'])
@log_api_call('batch_validate_lei')
def batch_validate_lei():
    """Validate multiple LEI codes."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json()
        lei_codes = data['lei_codes']
        
        if not isinstance(lei_codes, list) or not lei_codes:
            return validation_error_response({
                'lei_codes': [_('LEI codes must be a non-empty list')]
            })
        
        if len(lei_codes) > 50:  # Limit batch size
            return validation_error_response({
                'lei_codes': [_('Maximum 50 LEI codes allowed per batch')]
            })
        
        # Import here to avoid circular imports
        from app.services.kyb_service import KYBService
        
        # Batch validate LEI codes
        results = KYBService.check_lei_batch(
            lei_codes,
            batch_delay=data.get('batch_delay', 0.5),
            max_workers=data.get('max_workers', 5),
            timeout=data.get('timeout', 15),
            include_relationships=data.get('include_relationships', False)
        )
        
        logger.info("LEI batch validation performed", 
                   count=len(lei_codes),
                   user_id=user.id)
        
        return success_response(
            message=_('LEI batch validation completed'),
            data={
                'results': results,
                'summary': {
                    'total': len(results),
                    'valid': len([r for r in results if r.get('status') == 'valid']),
                    'invalid': len([r for r in results if r.get('status') == 'not_found']),
                    'errors': len([r for r in results if r.get('status') == 'error'])
                }
            }
        )
        
    except Exception as e:
        logger.error("Failed to batch validate LEI", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to batch validate LEI codes'),
            status_code=500
        )


@kyb_bp.route('/lei/search', methods=['POST'])
@jwt_required()
@require_permission('view_kyb')
@require_json(['entity_name'])
@log_api_call('search_lei')
def search_lei():
    """Search for LEI codes by entity name."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json()
        entity_name = data['entity_name'].strip()
        
        if not entity_name:
            return validation_error_response({
                'entity_name': [_('Entity name is required')]
            })
        
        # Import here to avoid circular imports
        from app.services.kyb_service import KYBService
        
        # Search LEI by name
        results = KYBService.search_lei_by_name(
            entity_name,
            country_code=data.get('country_code'),
            limit=data.get('limit', 10),
            timeout=data.get('timeout', 15)
        )
        
        logger.info("LEI search performed", 
                   entity_name=entity_name,
                   results_count=len(results),
                   user_id=user.id)
        
        return success_response(
            message=_('LEI search completed'),
            data={
                'results': results,
                'search_term': entity_name,
                'total_results': len(results)
            }
        )
        
    except Exception as e:
        logger.error("Failed to search LEI", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to search LEI codes'),
            status_code=500
        )


@kyb_bp.route('/lei/<lei_code>/relationships', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@log_api_call('get_lei_relationships')
def get_lei_relationships(lei_code):
    """Get relationship information for a LEI code."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        if not lei_code.strip():
            return validation_error_response({
                'lei_code': [_('LEI code is required')]
            })
        
        # Import here to avoid circular imports
        from app.services.kyb_service import KYBService
        
        # Get LEI relationships
        result = KYBService.get_lei_relationships(
            lei_code,
            timeout=request.args.get('timeout', 15, type=int)
        )
        
        logger.info("LEI relationships retrieved", 
                   lei_code=lei_code,
                   status=result.get('status'),
                   user_id=user.id)
        
        return success_response(
            message=_('LEI relationships retrieved'),
            data=result
        )
        
    except Exception as e:
        logger.error("Failed to get LEI relationships", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve LEI relationships'),
            status_code=500
        )


# ============================================================================
# RISK ASSESSMENT AND REPORTING ENDPOINTS
# ============================================================================

@kyb_bp.route('/risk-assessment', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@log_api_call('get_risk_assessment')
def get_risk_assessment():
    """Get risk assessment overview for tenant."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        
        # Get counterparty statistics
        total_counterparties = Counterparty.query.filter_by(tenant_id=tenant_id).count()
        
        # Risk level distribution
        risk_distribution = {}
        for level in ['low', 'medium', 'high', 'critical']:
            count = Counterparty.query.filter_by(
                tenant_id=tenant_id,
                risk_level=level
            ).count()
            risk_distribution[level] = count
        
        # Alert statistics
        total_alerts = KYBAlert.query.filter_by(tenant_id=tenant_id).count()
        open_alerts = KYBAlert.query.filter_by(tenant_id=tenant_id, status='open').count()
        
        # Alert severity distribution
        alert_severity = {}
        for severity in ['low', 'medium', 'high', 'critical']:
            count = KYBAlert.query.filter_by(
                tenant_id=tenant_id,
                severity=severity,
                status='open'
            ).count()
            alert_severity[severity] = count
        
        # Recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_alerts = KYBAlert.query.filter(
            KYBAlert.tenant_id == tenant_id,
            KYBAlert.created_at >= thirty_days_ago
        ).count()
        
        recent_snapshots = CounterpartySnapshot.query.filter(
            CounterpartySnapshot.tenant_id == tenant_id,
            CounterpartySnapshot.created_at >= thirty_days_ago
        ).count()
        
        # Top risk counterparties (top 10)
        top_risk_counterparties = Counterparty.query.filter_by(
            tenant_id=tenant_id
        ).order_by(Counterparty.risk_score.desc()).limit(10).all()
        
        data = {
            'overview': {
                'total_counterparties': total_counterparties,
                'total_alerts': total_alerts,
                'open_alerts': open_alerts,
                'recent_alerts_30d': recent_alerts,
                'recent_checks_30d': recent_snapshots
            },
            'risk_distribution': risk_distribution,
            'alert_severity_distribution': alert_severity,
            'top_risk_counterparties': [
                {
                    'id': cp.id,
                    'name': cp.name,
                    'risk_score': cp.risk_score,
                    'risk_level': cp.risk_level,
                    'country_code': cp.country_code
                }
                for cp in top_risk_counterparties
            ],
            'generated_at': datetime.utcnow().isoformat()
        }
        
        return success_response(
            message=_('Risk assessment retrieved successfully'),
            data=data
        )
        
    except Exception as e:
        logger.error("Failed to get risk assessment", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve risk assessment'),
            status_code=500
        )


# ============================================================================
# INSOLVENCY MONITORING ENDPOINTS
# ============================================================================

@kyb_bp.route('/insolvency/check/<int:counterparty_id>', methods=['POST'])
@jwt_required()
@require_permission('manage_kyb')
@log_api_call('check_counterparty_insolvency')
@audit_log('check_insolvency', 'counterparty')
def check_counterparty_insolvency(counterparty_id):
    """Manually trigger insolvency check for a counterparty."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Find counterparty in same tenant
        counterparty = Counterparty.query.filter_by(
            id=counterparty_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not counterparty:
            return not_found_response('counterparty')
        
        # Import and use insolvency service
        from app.services.insolvency_service import InsolvencyMonitoringService
        
        insolvency_service = InsolvencyMonitoringService()
        result = insolvency_service.check_counterparty_insolvency(counterparty_id)
        
        logger.info("Manual insolvency check completed", 
                   counterparty_id=counterparty_id, user_id=user.id)
        
        return success_response(
            message=_('Insolvency check completed successfully'),
            data=result
        )
        
    except Exception as e:
        logger.error("Failed to check counterparty insolvency", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to check counterparty insolvency'),
            status_code=500
        )


@kyb_bp.route('/insolvency/batch-check', methods=['POST'])
@jwt_required()
@require_permission('manage_kyb')
@require_json(['counterparty_ids'])
@log_api_call('batch_check_insolvency')
@audit_log('batch_check_insolvency', 'counterparty')
def batch_check_insolvency():
    """Batch check multiple counterparties for insolvency."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json()
        counterparty_ids = data['counterparty_ids']
        
        if not isinstance(counterparty_ids, list) or not counterparty_ids:
            return validation_error_response({
                'counterparty_ids': [_('Must provide a list of counterparty IDs')]
            })
        
        # Verify all counterparties belong to the same tenant
        counterparties = Counterparty.query.filter(
            Counterparty.id.in_(counterparty_ids),
            Counterparty.tenant_id == user.tenant_id
        ).all()
        
        found_ids = {cp.id for cp in counterparties}
        missing_ids = set(counterparty_ids) - found_ids
        
        if missing_ids:
            return validation_error_response({
                'counterparty_ids': [f'Counterparties not found: {list(missing_ids)}']
            })
        
        # Import and use insolvency service
        from app.services.insolvency_service import InsolvencyMonitoringService
        
        insolvency_service = InsolvencyMonitoringService()
        results = insolvency_service.batch_check_insolvency(counterparty_ids)
        
        logger.info("Batch insolvency check completed", 
                   counterparty_count=len(counterparty_ids), user_id=user.id)
        
        return success_response(
            message=_('Batch insolvency check completed successfully'),
            data={
                'results': results,
                'total_checked': len(counterparty_ids),
                'completed_at': datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error("Failed to batch check insolvency", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to batch check insolvency'),
            status_code=500
        )


@kyb_bp.route('/insolvency/summary', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@log_api_call('get_insolvency_summary')
def get_insolvency_summary():
    """Get insolvency monitoring summary for tenant."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Import and use insolvency service
        from app.services.insolvency_service import InsolvencyMonitoringService
        
        insolvency_service = InsolvencyMonitoringService()
        summary = insolvency_service.get_insolvency_summary(user.tenant_id)
        
        return success_response(
            message=_('Insolvency summary retrieved successfully'),
            data=summary
        )
        
    except Exception as e:
        logger.error("Failed to get insolvency summary", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve insolvency summary'),
            status_code=500
        )


@kyb_bp.route('/insolvency/proceeding/<case_number>', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@log_api_call('get_proceeding_details')
def get_proceeding_details(case_number):
    """Get detailed information about a specific insolvency proceeding."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        court = request.args.get('court')
        
        # Import and use insolvency service
        from app.services.insolvency_service import InsolvencyMonitoringService
        
        insolvency_service = InsolvencyMonitoringService()
        details = insolvency_service.get_proceeding_details(case_number, court)
        
        return success_response(
            message=_('Proceeding details retrieved successfully'),
            data=details
        )
        
    except Exception as e:
        logger.error("Failed to get proceeding details", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve proceeding details'),
            status_code=500
        )
        
        return success_response(
            message=_('Risk assessment retrieved successfully'),
            data=data
        )
        
    except Exception as e:
        logger.error("Failed to get risk assessment", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve risk assessment'),
            status_code=500
        )


@kyb_bp.route('/reports/summary', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@log_api_call('get_kyb_summary_report')
def get_kyb_summary_report():
    """Get KYB summary report."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        
        # Date range (default to last 30 days)
        end_date = datetime.utcnow()
        start_date_param = request.args.get('start_date')
        if start_date_param:
            try:
                start_date = datetime.fromisoformat(start_date_param.replace('Z', '+00:00'))
            except ValueError:
                start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=30)
        
        # Monitoring activity
        snapshots_in_period = CounterpartySnapshot.query.filter(
            CounterpartySnapshot.tenant_id == tenant_id,
            CounterpartySnapshot.created_at >= start_date,
            CounterpartySnapshot.created_at <= end_date
        ).count()
        
        # Alert activity
        alerts_in_period = KYBAlert.query.filter(
            KYBAlert.tenant_id == tenant_id,
            KYBAlert.created_at >= start_date,
            KYBAlert.created_at <= end_date
        ).count()
        
        # Data source breakdown
        source_breakdown = {}
        snapshots_by_source = CounterpartySnapshot.query.filter(
            CounterpartySnapshot.tenant_id == tenant_id,
            CounterpartySnapshot.created_at >= start_date,
            CounterpartySnapshot.created_at <= end_date
        ).all()
        
        for snapshot in snapshots_by_source:
            source = snapshot.source
            if source not in source_breakdown:
                source_breakdown[source] = {'total': 0, 'valid': 0, 'invalid': 0, 'errors': 0}
            
            source_breakdown[source]['total'] += 1
            if snapshot.status == 'valid':
                source_breakdown[source]['valid'] += 1
            elif snapshot.status == 'invalid':
                source_breakdown[source]['invalid'] += 1
            elif snapshot.status == 'error':
                source_breakdown[source]['errors'] += 1
        
        data = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'activity': {
                'total_checks': snapshots_in_period,
                'total_alerts': alerts_in_period,
                'avg_checks_per_day': round(snapshots_in_period / max((end_date - start_date).days, 1), 2)
            },
            'data_sources': source_breakdown
        }
        
        return success_response(
            message=_('KYB summary report retrieved successfully'),
            data=data
        )
        
    except Exception as e:
        logger.error("Failed to get KYB summary report", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve KYB summary report'),
            status_code=500
        )


# ============================================================================
# SNAPSHOT AND DIFF ENDPOINTS
# ============================================================================

@kyb_bp.route('/counterparties/<int:counterparty_id>/snapshots', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@validate_pagination()
@log_api_call('list_counterparty_snapshots')
def list_counterparty_snapshots(counterparty_id):
    """List snapshots for a specific counterparty."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        page = g.page
        per_page = g.per_page
        
        # Verify counterparty exists and belongs to tenant
        counterparty = Counterparty.query.filter_by(
            id=counterparty_id,
            tenant_id=tenant_id
        ).first()
        
        if not counterparty:
            return not_found_response('counterparty')
        
        # Build query
        query = CounterpartySnapshot.query.filter_by(
            counterparty_id=counterparty_id
        )
        
        # Apply filters
        if request.args.get('source'):
            query = query.filter_by(source=request.args.get('source'))
        
        if request.args.get('check_type'):
            query = query.filter_by(check_type=request.args.get('check_type'))
        
        if request.args.get('status'):
            query = query.filter_by(status=request.args.get('status'))
        
        # Order by creation date (newest first)
        query = query.order_by(CounterpartySnapshot.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        snapshots = [snapshot.to_dict() for snapshot in pagination.items]
        
        return paginated_response(
            items=snapshots,
            page=page,
            per_page=per_page,
            total=pagination.total,
            message=_('Counterparty snapshots retrieved successfully')
        )
        
    except Exception as e:
        logger.error("Failed to list counterparty snapshots", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve counterparty snapshots'),
            status_code=500
        )


@kyb_bp.route('/counterparties/<int:counterparty_id>/diffs', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@validate_pagination()
@log_api_call('list_counterparty_diffs')
def list_counterparty_diffs(counterparty_id):
    """List diffs for a specific counterparty."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        page = g.page
        per_page = g.per_page
        
        # Verify counterparty exists and belongs to tenant
        counterparty = Counterparty.query.filter_by(
            id=counterparty_id,
            tenant_id=tenant_id
        ).first()
        
        if not counterparty:
            return not_found_response('counterparty')
        
        # Build query
        query = CounterpartyDiff.query.filter_by(
            counterparty_id=counterparty_id
        )
        
        # Apply filters
        if request.args.get('change_type'):
            query = query.filter_by(change_type=request.args.get('change_type'))
        
        if request.args.get('risk_impact'):
            query = query.filter_by(risk_impact=request.args.get('risk_impact'))
        
        if request.args.get('processed') == 'true':
            query = query.filter_by(processed=True)
        elif request.args.get('processed') == 'false':
            query = query.filter_by(processed=False)
        
        # Order by creation date (newest first)
        query = query.order_by(CounterpartyDiff.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        diffs = [diff.to_dict() for diff in pagination.items]
        
        return paginated_response(
            items=diffs,
            page=page,
            per_page=per_page,
            total=pagination.total,
            message=_('Counterparty diffs retrieved successfully')
        )
        
    except Exception as e:
        logger.error("Failed to list counterparty diffs", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve counterparty diffs'),
            status_code=500
        )
# ============================================================================
# SANCTIONS MONITORING ENDPOINTS
# ============================================================================

@kyb_bp.route('/sanctions/check', methods=['POST'])
@jwt_required()
@require_permission('manage_kyb')
@require_json()
@log_api_call('check_sanctions')
@audit_log('check', 'sanctions')
def check_sanctions():
    """Check entity against all sanctions sources."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json()
        entity_name = data.get('entity_name')
        counterparty_id = data.get('counterparty_id')
        
        if not entity_name:
            return validation_error_response({'entity_name': 'Entity name is required'})
        
        # Import here to avoid circular imports
        from app.services.sanctions_service import SanctionsMonitoringService
        
        # Initialize sanctions service
        sanctions_service = SanctionsMonitoringService()
        
        # Perform sanctions check
        result = sanctions_service.check_entity_all_sources(
            entity_name=entity_name,
            tenant_id=user.tenant_id,
            counterparty_id=counterparty_id,
            **data.get('options', {})
        )
        
        logger.info("Sanctions check completed via API",
                   entity_name=entity_name,
                   tenant_id=user.tenant_id,
                   matches_found=result.get('total_matches', 0))
        
        return success_response(result, _('Sanctions check completed'))
        
    except Exception as e:
        logger.error("Error in sanctions check API", error=str(e), exc_info=True)
        return error_response(_('Failed to perform sanctions check'), str(e))


@kyb_bp.route('/counterparties/<int:counterparty_id>/sanctions', methods=['POST'])
@jwt_required()
@require_permission('manage_kyb')
@log_api_call('check_counterparty_sanctions')
@audit_log('check', 'counterparty_sanctions')
def check_counterparty_sanctions(counterparty_id):
    """Check specific counterparty against sanctions sources."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Verify counterparty exists and belongs to tenant
        counterparty = Counterparty.query.filter_by(
            id=counterparty_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not counterparty:
            return not_found_response('counterparty')
        
        # Get options from request
        data = request.get_json() or {}
        
        # Import here to avoid circular imports
        from app.services.sanctions_service import SanctionsMonitoringService
        
        # Initialize sanctions service
        sanctions_service = SanctionsMonitoringService()
        
        # Perform sanctions check
        result = sanctions_service.check_counterparty_sanctions(
            counterparty_id=counterparty_id,
            **data.get('options', {})
        )
        
        logger.info("Counterparty sanctions check completed via API",
                   counterparty_id=counterparty_id,
                   counterparty_name=counterparty.name,
                   matches_found=result.get('total_matches', 0))
        
        return success_response(result, _('Counterparty sanctions check completed'))
        
    except ValueError as e:
        return not_found_response('counterparty')
    except Exception as e:
        logger.error("Error in counterparty sanctions check API", 
                    counterparty_id=counterparty_id, error=str(e), exc_info=True)
        return error_response(_('Failed to check counterparty sanctions'), str(e))


@kyb_bp.route('/sanctions/batch-check', methods=['POST'])
@jwt_required()
@require_permission('manage_kyb')
@require_json()
@log_api_call('batch_check_sanctions')
@audit_log('check', 'batch_sanctions')
def batch_check_sanctions():
    """Check multiple counterparties against sanctions sources."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json()
        counterparty_ids = data.get('counterparty_ids', [])
        
        if not counterparty_ids or not isinstance(counterparty_ids, list):
            return validation_error_response({'counterparty_ids': 'List of counterparty IDs is required'})
        
        # Verify all counterparties belong to tenant
        counterparties = Counterparty.query.filter(
            and_(
                Counterparty.id.in_(counterparty_ids),
                Counterparty.tenant_id == user.tenant_id
            )
        ).all()
        
        if len(counterparties) != len(counterparty_ids):
            return validation_error_response({'counterparty_ids': 'Some counterparties not found or not accessible'})
        
        # Import here to avoid circular imports
        from app.services.sanctions_service import SanctionsMonitoringService
        
        # Initialize sanctions service
        sanctions_service = SanctionsMonitoringService()
        
        # Perform batch sanctions check
        results = sanctions_service.batch_check_counterparties(
            counterparty_ids=counterparty_ids,
            **data.get('options', {})
        )
        
        # Calculate summary statistics
        total_matches = sum(result.get('total_matches', 0) for result in results)
        
        logger.info("Batch sanctions check completed via API",
                   counterparty_count=len(counterparty_ids),
                   total_matches=total_matches)
        
        return success_response({
            'results': results,
            'summary': {
                'total_checked': len(counterparty_ids),
                'total_matches': total_matches,
                'checked_at': datetime.utcnow().isoformat() + 'Z'
            }
        }, _('Batch sanctions check completed'))
        
    except Exception as e:
        logger.error("Error in batch sanctions check API", error=str(e), exc_info=True)
        return error_response(_('Failed to perform batch sanctions check'), str(e))


@kyb_bp.route('/sanctions/statistics', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@log_api_call('get_sanctions_statistics')
def get_sanctions_statistics():
    """Get sanctions monitoring statistics for the tenant."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Get query parameters
        days = request.args.get('days', 30, type=int)
        if days < 1 or days > 365:
            return validation_error_response({'days': 'Days must be between 1 and 365'})
        
        # Import here to avoid circular imports
        from app.services.sanctions_service import SanctionsMonitoringService
        
        # Initialize sanctions service
        sanctions_service = SanctionsMonitoringService()
        
        # Get statistics
        stats = sanctions_service.get_sanctions_statistics(
            tenant_id=user.tenant_id,
            days=days
        )
        
        logger.info("Sanctions statistics retrieved via API",
                   tenant_id=user.tenant_id,
                   period_days=days)
        
        return success_response(stats, _('Sanctions statistics retrieved'))
        
    except Exception as e:
        logger.error("Error getting sanctions statistics", error=str(e), exc_info=True)
        return error_response(_('Failed to get sanctions statistics'), str(e))


@kyb_bp.route('/sanctions/sources', methods=['GET'])
@jwt_required()
@require_permission('view_kyb')
@log_api_call('get_sanctions_sources')
def get_sanctions_sources():
    """Get information about available sanctions sources."""
    try:
        # Import here to avoid circular imports
        from app.services.sanctions_service import SanctionsMonitoringService
        
        # Initialize sanctions service
        sanctions_service = SanctionsMonitoringService()
        
        # Get information about each source
        sources_info = {}
        for source_name, adapter in sanctions_service.adapters.items():
            try:
                if hasattr(adapter, 'get_sanctions_info'):
                    sources_info[source_name] = adapter.get_sanctions_info()
                else:
                    sources_info[source_name] = {
                        'source': f'{source_name} Sanctions List',
                        'available': True
                    }
            except Exception as e:
                logger.warning(f"Error getting info for {source_name}", error=str(e))
                sources_info[source_name] = {
                    'source': f'{source_name} Sanctions List',
                    'available': False,
                    'error': str(e)
                }
        
        # Get adapter statistics
        adapter_stats = sanctions_service.get_adapter_stats()
        
        result = {
            'sources': sources_info,
            'adapter_stats': adapter_stats,
            'total_sources': len(sources_info)
        }
        
        return success_response(result, _('Sanctions sources information retrieved'))
        
    except Exception as e:
        logger.error("Error getting sanctions sources info", error=str(e), exc_info=True)
        return error_response(_('Failed to get sanctions sources information'), str(e))


@kyb_bp.route('/sanctions/update-data', methods=['POST'])
@jwt_required()
@require_permission('manage_kyb')
@log_api_call('update_sanctions_data')
@audit_log('update', 'sanctions_data')
def update_sanctions_data():
    """Update sanctions data for all sources."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Import here to avoid circular imports
        from app.services.sanctions_service import SanctionsMonitoringService
        
        # Initialize sanctions service
        sanctions_service = SanctionsMonitoringService()
        
        # Update sanctions data
        result = sanctions_service.update_all_sanctions_data()
        
        logger.info("Sanctions data update initiated via API",
                   tenant_id=user.tenant_id,
                   sources_updated=result.get('sources_updated', []))
        
        return success_response(result, _('Sanctions data update completed'))
        
    except Exception as e:
        logger.error("Error updating sanctions data", error=str(e), exc_info=True)
        return error_response(_('Failed to update sanctions data'), str(e))


@kyb_bp.route('/sanctions/search', methods=['POST'])
@jwt_required()
@require_permission('view_kyb')
@require_json()
@log_api_call('search_sanctions')
def search_sanctions():
    """Search sanctions lists for entities."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json()
        query = data.get('query')
        source = data.get('source', 'all')  # 'all', 'EU', 'OFAC', 'UK'
        limit = data.get('limit', 10)
        
        if not query or len(query.strip()) < 3:
            return validation_error_response({'query': 'Search query must be at least 3 characters'})
        
        if limit < 1 or limit > 100:
            return validation_error_response({'limit': 'Limit must be between 1 and 100'})
        
        # Import here to avoid circular imports
        from app.services.sanctions_service import SanctionsMonitoringService
        
        # Initialize sanctions service
        sanctions_service = SanctionsMonitoringService()
        
        results = {}
        
        # Search specific source or all sources
        if source == 'all':
            sources_to_search = sanctions_service.adapters.keys()
        else:
            if source not in sanctions_service.adapters:
                return validation_error_response({'source': f'Invalid source: {source}'})
            sources_to_search = [source]
        
        for source_name in sources_to_search:
            adapter = sanctions_service.adapters[source_name]
            try:
                if hasattr(adapter, 'search_entity'):
                    search_result = adapter.search_entity(query, limit)
                    results[source_name] = search_result
                else:
                    results[source_name] = {
                        'query': query,
                        'error': 'Search not supported for this source',
                        'total_results': 0,
                        'results': []
                    }
            except Exception as e:
                logger.warning(f"Search error for {source_name}", error=str(e))
                results[source_name] = {
                    'query': query,
                    'error': str(e),
                    'total_results': 0,
                    'results': []
                }
        
        # Calculate total results
        total_results = sum(result.get('total_results', 0) for result in results.values())
        
        response_data = {
            'query': query,
            'sources_searched': list(sources_to_search),
            'total_results': total_results,
            'results_by_source': results
        }
        
        logger.info("Sanctions search completed via API",
                   query=query,
                   sources_searched=len(sources_to_search),
                   total_results=total_results)
        
        return success_response(response_data, _('Sanctions search completed'))
        
    except Exception as e:
        logger.error("Error in sanctions search", error=str(e), exc_info=True)
        return error_response(_('Failed to search sanctions'), str(e))