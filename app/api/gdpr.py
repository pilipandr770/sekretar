"""GDPR compliance API endpoints."""
import logging
from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, validate, ValidationError
from app import db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.gdpr_compliance import (
    DataRetentionPolicy, ConsentRecord, ConsentType, ConsentStatus,
    DataDeletionRequest, DataExportRequest, PIIDetectionLog
)
from app.services.consent_service import ConsentService
from app.services.data_retention_service import DataRetentionService
from app.services.gdpr_request_service import GDPRRequestService
from app.services.pii_service import PIIDetector, DataMinimizer
from app.utils.auth import require_permission, get_current_tenant
from app.utils.validation import validate_json
# Worker imports moved to function level to avoid circular imports

logger = logging.getLogger(__name__)
gdpr_bp = Blueprint('gdpr', __name__, url_prefix='/api/v1/gdpr')


# Validation schemas
class ConsentGrantSchema(Schema):
    consent_type = fields.Str(required=True, validate=validate.OneOf([t.value for t in ConsentType]))
    purpose = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    user_id = fields.Int(required=False, allow_none=True)
    external_user_id = fields.Str(required=False, allow_none=True)
    email = fields.Email(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True)
    legal_basis = fields.Str(required=False, allow_none=True)
    expires_at = fields.DateTime(required=False, allow_none=True)
    source = fields.Str(required=False, allow_none=True)
    evidence = fields.Dict(required=False, allow_none=True)


class ConsentWithdrawSchema(Schema):
    consent_type = fields.Str(required=True, validate=validate.OneOf([t.value for t in ConsentType]))
    user_id = fields.Int(required=False, allow_none=True)
    external_user_id = fields.Str(required=False, allow_none=True)
    email = fields.Email(required=False, allow_none=True)
    reason = fields.Str(required=False, allow_none=True)


class RetentionPolicySchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(required=False, allow_none=True)
    data_type = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    table_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    retention_days = fields.Int(required=True, validate=validate.Range(min=1, max=36500))  # Max 100 years
    auto_delete = fields.Bool(required=False, allow_none=True)
    anonymize_instead = fields.Bool(required=False, allow_none=True)
    legal_basis = fields.Str(required=False, allow_none=True)
    config = fields.Dict(required=False, allow_none=True)


class DataDeletionRequestSchema(Schema):
    request_type = fields.Str(required=True, validate=validate.OneOf(['full_deletion', 'anonymization', 'specific_data']))
    user_id = fields.Int(required=False, allow_none=True)
    external_user_id = fields.Str(required=False, allow_none=True)
    email = fields.Email(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True)
    reason = fields.Str(required=False, allow_none=True)
    data_types = fields.List(fields.Str(), required=False, allow_none=True)


class DataExportRequestSchema(Schema):
    user_id = fields.Int(required=False, allow_none=True)
    external_user_id = fields.Str(required=False, allow_none=True)
    email = fields.Email(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True)
    export_format = fields.Str(required=False, allow_none=True, validate=validate.OneOf(['json', 'csv', 'xml']))
    data_types = fields.List(fields.Str(), required=False, allow_none=True)
    include_metadata = fields.Bool(required=False, allow_none=True)


# Consent Management Endpoints
@gdpr_bp.route('/consent/grant', methods=['POST'])
@jwt_required()
@require_permission('manage_settings')
def grant_consent():
    """Grant consent for a user."""
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400
    
    # Validate required fields
    required_fields = ['consent_type', 'purpose']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
    
    tenant = get_current_tenant()
    
    try:
        consent_service = ConsentService(db.session)
        
        consent_record = consent_service.grant_consent(
            tenant_id=tenant.id,
            consent_type=data['consent_type'],
            purpose=data['purpose'],
            user_id=data.get('user_id'),
            external_user_id=data.get('external_user_id'),
            email=data.get('email'),
            phone=data.get('phone'),
            legal_basis=data.get('legal_basis'),
            expires_at=data.get('expires_at'),
            source=data.get('source', 'api'),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            evidence=data.get('evidence')
        )
        
        return jsonify({
            'success': True,
            'message': 'Consent granted successfully',
            'consent_record': consent_record.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Error granting consent: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to grant consent',
            'details': str(e)
        }), 500


@gdpr_bp.route('/consent/withdraw', methods=['POST'])
@jwt_required()
@require_permission('manage_settings')
def withdraw_consent():
    """Withdraw consent for a user."""
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400
    
    # Validate required fields
    if 'consent_type' not in data:
        return jsonify({'success': False, 'error': 'Missing required field: consent_type'}), 400
    
    tenant = get_current_tenant()
    
    try:
        consent_service = ConsentService(db.session)
        
        success = consent_service.withdraw_consent(
            tenant_id=tenant.id,
            consent_type=data['consent_type'],
            user_id=data.get('user_id'),
            external_user_id=data.get('external_user_id'),
            email=data.get('email'),
            reason=data.get('reason')
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Consent withdrawn successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No consent record found to withdraw'
            }), 404
            
    except Exception as e:
        logger.error(f"Error withdrawing consent: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to withdraw consent',
            'details': str(e)
        }), 500


@gdpr_bp.route('/consent/status', methods=['GET'])
@jwt_required()
@require_permission('view_crm')
def get_consent_status():
    """Get consent status for a user."""
    tenant = get_current_tenant()
    user_id = request.args.get('user_id', type=int)
    external_user_id = request.args.get('external_user_id')
    email = request.args.get('email')
    consent_type = request.args.get('consent_type')
    
    if not any([user_id, external_user_id, email]):
        return jsonify({
            'success': False,
            'error': 'Must provide user_id, external_user_id, or email'
        }), 400
    
    try:
        consent_service = ConsentService(db.session)
        
        if consent_type:
            # Check specific consent type
            has_consent = consent_service.has_valid_consent(
                tenant_id=tenant.id,
                consent_type=consent_type,
                user_id=user_id,
                external_user_id=external_user_id,
                email=email
            )
            
            return jsonify({
                'success': True,
                'consent_type': consent_type,
                'has_valid_consent': has_consent
            }), 200
        else:
            # Get all consents for user
            consents = consent_service.get_all_user_consents(
                tenant_id=tenant.id,
                user_id=user_id,
                external_user_id=external_user_id,
                email=email
            )
            
            return jsonify({
                'success': True,
                'consents': [consent.to_dict() for consent in consents]
            }), 200
            
    except Exception as e:
        logger.error(f"Error getting consent status: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get consent status',
            'details': str(e)
        }), 500


@gdpr_bp.route('/consent/summary', methods=['GET'])
@jwt_required()
@require_permission('view_analytics')
def get_consent_summary():
    """Get consent summary for tenant."""
    tenant = get_current_tenant()
    
    try:
        consent_service = ConsentService(db.session)
        summary = consent_service.get_consent_summary(tenant.id)
        
        return jsonify({
            'success': True,
            'summary': summary
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting consent summary: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get consent summary',
            'details': str(e)
        }), 500


# Data Retention Policy Endpoints
@gdpr_bp.route('/retention/policies', methods=['GET'])
@jwt_required()
@require_permission('manage_settings')
def get_retention_policies():
    """Get data retention policies for tenant."""
    tenant = get_current_tenant()
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    
    try:
        retention_service = DataRetentionService(db.session)
        policies = retention_service.get_tenant_policies(tenant.id, active_only)
        
        return jsonify({
            'success': True,
            'policies': [policy.to_dict() for policy in policies]
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting retention policies: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get retention policies',
            'details': str(e)
        }), 500


@gdpr_bp.route('/retention/policies', methods=['POST'])
@jwt_required()
@require_permission('manage_settings')
def create_retention_policy():
    """Create a new data retention policy."""
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400
    
    # Validate required fields
    required_fields = ['name', 'data_type', 'table_name', 'retention_days']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
    
    tenant = get_current_tenant()
    
    try:
        retention_service = DataRetentionService(db.session)
        
        policy = retention_service.create_retention_policy(
            tenant_id=tenant.id,
            name=data['name'],
            data_type=data['data_type'],
            table_name=data['table_name'],
            retention_days=data['retention_days'],
            auto_delete=data.get('auto_delete', True),
            anonymize_instead=data.get('anonymize_instead', False),
            legal_basis=data.get('legal_basis'),
            description=data.get('description'),
            config=data.get('config', {})
        )
        
        return jsonify({
            'success': True,
            'message': 'Retention policy created successfully',
            'policy': policy.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating retention policy: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to create retention policy',
            'details': str(e)
        }), 500


@gdpr_bp.route('/retention/expired-data', methods=['GET'])
@jwt_required()
@require_permission('manage_settings')
def find_expired_data():
    """Find data that has expired according to retention policies."""
    tenant = get_current_tenant()
    policy_id = request.args.get('policy_id', type=int)
    
    try:
        retention_service = DataRetentionService(db.session)
        expired_data = retention_service.find_expired_data(tenant.id, policy_id)
        
        return jsonify({
            'success': True,
            'expired_data': expired_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error finding expired data: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to find expired data',
            'details': str(e)
        }), 500


@gdpr_bp.route('/retention/cleanup', methods=['POST'])
@jwt_required()
@require_permission('manage_settings')
def trigger_data_cleanup():
    """Trigger data cleanup according to retention policies."""
    tenant = get_current_tenant()
    data = request.get_json() or {}
    
    policy_id = data.get('policy_id', type=int)
    dry_run = data.get('dry_run', True)
    batch_size = data.get('batch_size', 100)
    
    try:
        # Import worker function locally to avoid circular imports
        from app.workers.data_retention import cleanup_expired_data
        
        # Trigger background task
        task = cleanup_expired_data.apply_async(
            kwargs={
                'tenant_id': tenant.id,
                'policy_id': policy_id,
                'dry_run': dry_run,
                'batch_size': batch_size
            }
        )
        
        return jsonify({
            'success': True,
            'message': 'Data cleanup task started',
            'task_id': task.id,
            'dry_run': dry_run
        }), 202
        
    except Exception as e:
        logger.error(f"Error triggering data cleanup: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to trigger data cleanup',
            'details': str(e)
        }), 500


# Data Deletion Request Endpoints
@gdpr_bp.route('/deletion-request', methods=['POST'])
@jwt_required()
@require_permission('manage_settings')
def create_deletion_request():
    """Create a data deletion request."""
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400
    
    # Validate required fields
    if 'request_type' not in data:
        return jsonify({'success': False, 'error': 'Missing required field: request_type'}), 400
    
    tenant = get_current_tenant()
    
    try:
        gdpr_service = GDPRRequestService(db.session)
        
        deletion_request = gdpr_service.create_deletion_request(
            tenant_id=tenant.id,
            request_type=data['request_type'],
            user_id=data.get('user_id'),
            external_user_id=data.get('external_user_id'),
            email=data.get('email'),
            phone=data.get('phone'),
            reason=data.get('reason'),
            data_types=data.get('data_types', [])
        )
        
        return jsonify({
            'success': True,
            'message': 'Deletion request created successfully',
            'request': deletion_request.to_dict(),
            'verification_token': deletion_request.verification_token
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating deletion request: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to create deletion request',
            'details': str(e)
        }), 500


@gdpr_bp.route('/deletion-request/<request_id>/verify', methods=['POST'])
@jwt_required()
@require_permission('manage_settings')
def verify_deletion_request(request_id):
    """Verify a data deletion request."""
    data = request.get_json() or {}
    token = data.get('token')
    
    if not token:
        return jsonify({
            'success': False,
            'error': 'Verification token is required'
        }), 400
    
    try:
        deletion_request = DataDeletionRequest.query.filter_by(
            request_id=request_id
        ).first()
        
        if not deletion_request:
            return jsonify({
                'success': False,
                'error': 'Deletion request not found'
            }), 404
        
        if deletion_request.verify_request(token):
            db.session.commit()
            
            # Import worker function locally to avoid circular imports
            from app.workers.data_retention import process_data_deletion_request
            
            # Trigger processing task
            task = process_data_deletion_request.apply_async(
                args=[request_id]
            )
            
            return jsonify({
                'success': True,
                'message': 'Deletion request verified and processing started',
                'task_id': task.id
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid verification token'
            }), 400
            
    except Exception as e:
        logger.error(f"Error verifying deletion request: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to verify deletion request',
            'details': str(e)
        }), 500


@gdpr_bp.route('/deletion-request/<request_id>', methods=['GET'])
@jwt_required()
@require_permission('manage_settings')
def get_deletion_request(request_id):
    """Get deletion request status."""
    try:
        deletion_request = DataDeletionRequest.query.filter_by(
            request_id=request_id
        ).first()
        
        if not deletion_request:
            return jsonify({
                'success': False,
                'error': 'Deletion request not found'
            }), 404
        
        return jsonify({
            'success': True,
            'request': deletion_request.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting deletion request: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get deletion request',
            'details': str(e)
        }), 500


# Data Export Request Endpoints
@gdpr_bp.route('/export-request', methods=['POST'])
@jwt_required()
@require_permission('view_crm')
def create_export_request():
    """Create a data export request."""
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400
    
    data = request.get_json() or {}
    tenant = get_current_tenant()
    
    try:
        gdpr_service = GDPRRequestService(db.session)
        
        export_request = gdpr_service.create_export_request(
            tenant_id=tenant.id,
            user_id=data.get('user_id'),
            external_user_id=data.get('external_user_id'),
            email=data.get('email'),
            phone=data.get('phone'),
            export_format=data.get('export_format', 'json'),
            data_types=data.get('data_types', []),
            include_metadata=data.get('include_metadata', True)
        )
        
        # Import worker function locally to avoid circular imports
        from app.workers.data_retention import process_data_export_request
        
        # Trigger processing task
        task = process_data_export_request.apply_async(
            args=[export_request.request_id]
        )
        
        return jsonify({
            'success': True,
            'message': 'Export request created and processing started',
            'request': export_request.to_dict(),
            'task_id': task.id
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating export request: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to create export request',
            'details': str(e)
        }), 500


@gdpr_bp.route('/export-request/<request_id>', methods=['GET'])
@jwt_required()
@require_permission('view_crm')
def get_export_request(request_id):
    """Get export request status."""
    try:
        export_request = DataExportRequest.query.filter_by(
            request_id=request_id
        ).first()
        
        if not export_request:
            return jsonify({
                'success': False,
                'error': 'Export request not found'
            }), 404
        
        return jsonify({
            'success': True,
            'request': export_request.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting export request: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get export request',
            'details': str(e)
        }), 500


@gdpr_bp.route('/export-request/<request_id>/download', methods=['GET'])
@jwt_required()
@require_permission('view_crm')
def download_export(request_id):
    """Download exported data file."""
    token = request.args.get('token')
    
    if not token:
        return jsonify({
            'success': False,
            'error': 'Download token is required'
        }), 400
    
    try:
        export_request = DataExportRequest.query.filter_by(
            request_id=request_id,
            download_token=token
        ).first()
        
        if not export_request:
            return jsonify({
                'success': False,
                'error': 'Export request not found or invalid token'
            }), 404
        
        if not export_request.can_download():
            return jsonify({
                'success': False,
                'error': 'Export is expired or download limit exceeded'
            }), 403
        
        if not export_request.file_path or not os.path.exists(export_request.file_path):
            return jsonify({
                'success': False,
                'error': 'Export file not found'
            }), 404
        
        # Record download
        export_request.record_download()
        db.session.commit()
        
        # Send file
        return send_file(
            export_request.file_path,
            as_attachment=True,
            download_name=f"data_export_{request_id}.{export_request.export_format}"
        )
        
    except Exception as e:
        logger.error(f"Error downloading export: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to download export',
            'details': str(e)
        }), 500


# PII Detection Endpoints
@gdpr_bp.route('/pii/detect', methods=['POST'])
@jwt_required()
@require_permission('manage_settings')
def detect_pii():
    """Detect PII in provided text."""
    data = request.get_json() or {}
    text = data.get('text', '')
    
    if not text:
        return jsonify({
            'success': False,
            'error': 'Text is required'
        }), 400
    
    try:
        pii_detector = PIIDetector()
        detected_pii = pii_detector.detect_pii_in_text(text)
        
        return jsonify({
            'success': True,
            'detected_pii': detected_pii,
            'pii_count': len(detected_pii)
        }), 200
        
    except Exception as e:
        logger.error(f"Error detecting PII: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to detect PII',
            'details': str(e)
        }), 500


@gdpr_bp.route('/pii/mask', methods=['POST'])
@jwt_required()
@require_permission('manage_settings')
def mask_pii():
    """Mask PII in provided text."""
    data = request.get_json() or {}
    text = data.get('text', '')
    mask_char = data.get('mask_char', '*')
    preserve_chars = data.get('preserve_chars', 2)
    
    if not text:
        return jsonify({
            'success': False,
            'error': 'Text is required'
        }), 400
    
    try:
        pii_detector = PIIDetector()
        masked_text, masked_items = pii_detector.mask_pii_in_text(text, mask_char, preserve_chars)
        
        return jsonify({
            'success': True,
            'original_text': text,
            'masked_text': masked_text,
            'masked_items': masked_items,
            'pii_count': len(masked_items)
        }), 200
        
    except Exception as e:
        logger.error(f"Error masking PII: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to mask PII',
            'details': str(e)
        }), 500


@gdpr_bp.route('/pii/logs', methods=['GET'])
@jwt_required()
@require_permission('view_analytics')
def get_pii_logs():
    """Get PII detection logs."""
    tenant = get_current_tenant()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    pii_type = request.args.get('pii_type')
    source_table = request.args.get('source_table')
    
    try:
        query = PIIDetectionLog.query.filter_by(tenant_id=tenant.id)
        
        if pii_type:
            query = query.filter_by(pii_type=pii_type)
        if source_table:
            query = query.filter_by(source_table=source_table)
        
        query = query.order_by(PIIDetectionLog.created_at.desc())
        
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'success': True,
            'logs': [log.to_dict() for log in pagination.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting PII logs: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get PII logs',
            'details': str(e)
        }), 500


# Utility Endpoints
@gdpr_bp.route('/check-expired-consents', methods=['POST'])
@jwt_required()
@require_permission('manage_settings')
def trigger_consent_check():
    """Trigger expired consent check."""
    tenant = get_current_tenant()
    
    try:
        # Import worker function locally to avoid circular imports
        from app.workers.data_retention import check_expired_consents
        
        task = check_expired_consents.apply_async(
            kwargs={'tenant_id': tenant.id}
        )
        
        return jsonify({
            'success': True,
            'message': 'Expired consent check started',
            'task_id': task.id
        }), 202
        
    except Exception as e:
        logger.error(f"Error triggering consent check: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to trigger consent check',
            'details': str(e)
        }), 500


@gdpr_bp.route('/compliance-report', methods=['GET'])
@jwt_required()
@require_permission('view_analytics')
def get_compliance_report():
    """Get GDPR compliance report for tenant."""
    tenant = get_current_tenant()
    
    try:
        # Get consent summary
        consent_service = ConsentService(db.session)
        consent_summary = consent_service.get_consent_summary(tenant.id)
        
        # Get retention policies
        retention_service = DataRetentionService(db.session)
        policies = retention_service.get_tenant_policies(tenant.id)
        expired_data = retention_service.find_expired_data(tenant.id)
        
        # Get recent PII detections
        recent_pii_logs = PIIDetectionLog.query.filter_by(tenant_id=tenant.id)\
            .order_by(PIIDetectionLog.created_at.desc())\
            .limit(10).all()
        
        # Get pending requests
        pending_deletions = DataDeletionRequest.query.filter_by(
            tenant_id=tenant.id,
            status='pending'
        ).count()
        
        pending_exports = DataExportRequest.query.filter_by(
            tenant_id=tenant.id,
            status='pending'
        ).count()
        
        report = {
            'tenant_id': tenant.id,
            'report_date': datetime.utcnow().isoformat(),
            'consent_summary': consent_summary,
            'retention_policies': {
                'total_policies': len(policies),
                'active_policies': len([p for p in policies if p.is_active]),
                'expired_data_summary': expired_data
            },
            'pii_detection': {
                'recent_detections': len(recent_pii_logs),
                'detection_types': list(set(log.pii_type for log in recent_pii_logs))
            },
            'pending_requests': {
                'deletion_requests': pending_deletions,
                'export_requests': pending_exports
            }
        }
        
        return jsonify({
            'success': True,
            'compliance_report': report
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating compliance report: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to generate compliance report',
            'details': str(e)
        }), 500