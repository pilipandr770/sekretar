"""CRM management API endpoints."""
from flask import Blueprint, request, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from sqlalchemy import and_, or_, desc
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.pipeline import Pipeline, Stage
from app.models.task import Task
from app.models.note import Note
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

# Import the CRM blueprint from the crm package
from app.crm import crm_bp


# ============================================================================
# CONTACT ENDPOINTS
# ============================================================================

@crm_bp.route('/contacts', methods=['GET'])
@jwt_required()
@require_permission('view_crm')
@validate_pagination()
@log_api_call('list_contacts')
def list_contacts():
    """List contacts with filtering and pagination."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        page = g.page
        per_page = g.per_page
        
        # Build query
        query = Contact.query.filter_by(tenant_id=tenant_id)
        
        # Apply filters
        if request.args.get('contact_type'):
            query = query.filter_by(contact_type=request.args.get('contact_type'))
        
        if request.args.get('status'):
            query = query.filter_by(status=request.args.get('status'))
        
        if request.args.get('search'):
            search_term = f"%{request.args.get('search')}%"
            query = query.filter(
                or_(
                    Contact.first_name.ilike(search_term),
                    Contact.last_name.ilike(search_term),
                    Contact.company.ilike(search_term),
                    Contact.email.ilike(search_term),
                    Contact.phone.ilike(search_term),
                    Contact.mobile.ilike(search_term)
                )
            )
        
        # Order by creation date (newest first)
        query = query.order_by(Contact.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        contacts = [contact.to_dict() for contact in pagination.items]
        
        return paginated_response(
            items=contacts,
            page=page,
            per_page=per_page,
            total=pagination.total,
            message=_('Contacts retrieved successfully')
        )
        
    except Exception as e:
        logger.error("Failed to list contacts", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve contacts'),
            status_code=500
        )


@crm_bp.route('/contacts', methods=['POST'])
@jwt_required()
@require_permission('manage_crm')
@require_json()
@log_api_call('create_contact')
@audit_log('create', 'contact')
def create_contact():
    """Create new contact."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        data = request.get_json()
        
        # Validate required fields
        if not data.get('first_name') and not data.get('last_name') and not data.get('company'):
            return validation_error_response({
                'name': [_('At least one of first name, last name, or company is required')]
            })
        
        # Check for duplicate email
        if data.get('email'):
            existing_contact = Contact.find_by_email(tenant_id, data['email'])
            if existing_contact:
                return conflict_response(_('Contact with this email already exists'))
        
        # Create contact
        contact = Contact.create(
            tenant_id=tenant_id,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            company=data.get('company', ''),
            title=data.get('title', ''),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            mobile=data.get('mobile', ''),
            website=data.get('website', ''),
            address_line1=data.get('address_line1', ''),
            address_line2=data.get('address_line2', ''),
            city=data.get('city', ''),
            state=data.get('state', ''),
            postal_code=data.get('postal_code', ''),
            country=data.get('country', ''),
            linkedin_url=data.get('linkedin_url', ''),
            twitter_handle=data.get('twitter_handle', ''),
            contact_type=data.get('contact_type', 'prospect'),
            source=data.get('source', ''),
            preferred_contact_method=data.get('preferred_contact_method', 'email'),
            timezone=data.get('timezone', ''),
            language=data.get('language', 'en'),
            email_opt_in=data.get('email_opt_in', True),
            sms_opt_in=data.get('sms_opt_in', False),
            custom_fields=data.get('custom_fields', {}),
            tags=data.get('tags', []),
            notes=data.get('notes', '')
        )
        
        logger.info("Contact created", contact_id=contact.id, tenant_id=tenant_id, user_id=user.id)
        
        return success_response(
            message=_('Contact created successfully'),
            data=contact.to_dict(),
            status_code=201
        )
        
    except Exception as e:
        logger.error("Failed to create contact", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to create contact'),
            status_code=500
        )


@crm_bp.route('/contacts/<int:contact_id>', methods=['GET'])
@jwt_required()
@require_permission('view_crm')
@log_api_call('get_contact')
def get_contact(contact_id):
    """Get specific contact."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Find contact in same tenant
        contact = Contact.query.filter_by(
            id=contact_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not contact:
            return not_found_response('contact')
        
        return success_response(
            message=_('Contact retrieved successfully'),
            data=contact.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to get contact", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve contact'),
            status_code=500
        )


@crm_bp.route('/contacts/<int:contact_id>', methods=['PUT'])
@jwt_required()
@require_permission('manage_crm')
@require_json()
@log_api_call('update_contact')
@audit_log('update', 'contact')
def update_contact(contact_id):
    """Update contact."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        data = request.get_json()
        
        # Find contact in same tenant
        contact = Contact.query.filter_by(
            id=contact_id,
            tenant_id=tenant_id
        ).first()
        
        if not contact:
            return not_found_response('contact')
        
        # Check for duplicate email if email is being changed
        if data.get('email') and data['email'] != contact.email:
            existing_contact = Contact.find_by_email(tenant_id, data['email'])
            if existing_contact:
                return conflict_response(_('Contact with this email already exists'))
        
        # Fields that can be updated
        updatable_fields = [
            'first_name', 'last_name', 'company', 'title', 'email', 'phone', 'mobile',
            'website', 'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            'country', 'linkedin_url', 'twitter_handle', 'contact_type', 'source',
            'preferred_contact_method', 'timezone', 'language', 'email_opt_in',
            'sms_opt_in', 'custom_fields', 'tags', 'notes', 'status'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(contact, field, data[field])
        
        contact.save()
        
        logger.info("Contact updated", contact_id=contact.id, user_id=user.id)
        
        return success_response(
            message=_('Contact updated successfully'),
            data=contact.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to update contact", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update contact'),
            status_code=500
        )


@crm_bp.route('/contacts/<int:contact_id>', methods=['DELETE'])
@jwt_required()
@require_permission('manage_crm')
@log_api_call('delete_contact')
@audit_log('delete', 'contact')
def delete_contact(contact_id):
    """Delete contact."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Find contact in same tenant
        contact = Contact.query.filter_by(
            id=contact_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not contact:
            return not_found_response('contact')
        
        # Check if contact has leads
        if contact.leads:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Cannot delete contact with associated leads'),
                status_code=400
            )
        
        # Soft delete
        contact.delete()
        
        logger.info("Contact deleted", contact_id=contact.id, user_id=user.id)
        
        return success_response(
            message=_('Contact deleted successfully')
        )
        
    except Exception as e:
        logger.error("Failed to delete contact", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to delete contact'),
            status_code=500
        )


# ============================================================================
# PIPELINE ENDPOINTS
# ============================================================================

@crm_bp.route('/pipelines', methods=['GET'])
@jwt_required()
@require_permission('view_crm')
@log_api_call('list_pipelines')
def list_pipelines():
    """List pipelines."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        pipelines = Pipeline.query.filter_by(
            tenant_id=user.tenant_id,
            is_active=True
        ).order_by(Pipeline.is_default.desc(), Pipeline.created_at.asc()).all()
        
        return success_response(
            message=_('Pipelines retrieved successfully'),
            data=[pipeline.to_dict() for pipeline in pipelines]
        )
        
    except Exception as e:
        logger.error("Failed to list pipelines", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve pipelines'),
            status_code=500
        )


@crm_bp.route('/pipelines', methods=['POST'])
@jwt_required()
@require_permission('manage_crm')
@require_json(['name'])
@log_api_call('create_pipeline')
@audit_log('create', 'pipeline')
def create_pipeline():
    """Create new pipeline."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        data = request.get_json()
        
        name = data['name'].strip()
        if not name:
            return validation_error_response({
                'name': [_('Pipeline name is required')]
            })
        
        # Create pipeline
        pipeline = Pipeline.create(
            tenant_id=tenant_id,
            name=name,
            description=data.get('description', ''),
            is_default=data.get('is_default', False),
            settings=data.get('settings', {})
        )
        
        # Create default stages if none provided
        stages_data = data.get('stages', [
            {"name": "Lead", "color": "#3498db", "description": "New leads"},
            {"name": "Qualified", "color": "#f39c12", "description": "Qualified prospects"},
            {"name": "Proposal", "color": "#e74c3c", "description": "Proposal sent"},
            {"name": "Negotiation", "color": "#9b59b6", "description": "In negotiation"},
            {"name": "Closed Won", "color": "#27ae60", "description": "Successfully closed", "is_closed": True, "is_won": True},
            {"name": "Closed Lost", "color": "#95a5a6", "description": "Lost opportunity", "is_closed": True, "is_won": False}
        ])
        
        stage_ids = []
        for i, stage_data in enumerate(stages_data):
            stage = Stage.create(
                tenant_id=tenant_id,
                pipeline_id=pipeline.id,
                position=i,
                **stage_data
            )
            stage_ids.append(stage.id)
        
        pipeline.stages_order = stage_ids
        pipeline.save()
        
        logger.info("Pipeline created", pipeline_id=pipeline.id, tenant_id=tenant_id, user_id=user.id)
        
        return success_response(
            message=_('Pipeline created successfully'),
            data=pipeline.to_dict(),
            status_code=201
        )
        
    except Exception as e:
        logger.error("Failed to create pipeline", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to create pipeline'),
            status_code=500
        )


@crm_bp.route('/pipelines/<int:pipeline_id>', methods=['GET'])
@jwt_required()
@require_permission('view_crm')
@log_api_call('get_pipeline')
def get_pipeline(pipeline_id):
    """Get specific pipeline."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Find pipeline in same tenant
        pipeline = Pipeline.query.filter_by(
            id=pipeline_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not pipeline:
            return not_found_response('pipeline')
        
        return success_response(
            message=_('Pipeline retrieved successfully'),
            data=pipeline.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to get pipeline", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve pipeline'),
            status_code=500
        )


@crm_bp.route('/pipelines/<int:pipeline_id>', methods=['PUT'])
@jwt_required()
@require_permission('manage_crm')
@require_json()
@log_api_call('update_pipeline')
@audit_log('update', 'pipeline')
def update_pipeline(pipeline_id):
    """Update pipeline."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json()
        
        # Find pipeline in same tenant
        pipeline = Pipeline.query.filter_by(
            id=pipeline_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not pipeline:
            return not_found_response('pipeline')
        
        # Fields that can be updated
        updatable_fields = ['name', 'description', 'is_default', 'is_active', 'settings']
        
        for field in updatable_fields:
            if field in data:
                if field == 'name' and not data[field].strip():
                    return validation_error_response({
                        'name': [_('Pipeline name is required')]
                    })
                
                setattr(pipeline, field, data[field])
        
        pipeline.save()
        
        logger.info("Pipeline updated", pipeline_id=pipeline.id, user_id=user.id)
        
        return success_response(
            message=_('Pipeline updated successfully'),
            data=pipeline.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to update pipeline", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update pipeline'),
            status_code=500
        )


@crm_bp.route('/pipelines/<int:pipeline_id>/stages', methods=['PUT'])
@jwt_required()
@require_permission('manage_crm')
@require_json(['stages_order'])
@log_api_call('update_pipeline_stages_order')
@audit_log('update_stages_order', 'pipeline')
def update_pipeline_stages_order(pipeline_id):
    """Update pipeline stages order."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json()
        stages_order = data['stages_order']
        
        # Find pipeline in same tenant
        pipeline = Pipeline.query.filter_by(
            id=pipeline_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not pipeline:
            return not_found_response('pipeline')
        
        # Validate stage IDs belong to this pipeline
        stage_ids = [stage.id for stage in pipeline.stages]
        for stage_id in stages_order:
            if stage_id not in stage_ids:
                return validation_error_response({
                    'stages_order': [_('Invalid stage ID: %(stage_id)s', stage_id=stage_id)]
                })
        
        pipeline.update_stages_order(stages_order)
        pipeline.save()
        
        logger.info("Pipeline stages order updated", pipeline_id=pipeline.id, user_id=user.id)
        
        return success_response(
            message=_('Pipeline stages order updated successfully'),
            data=pipeline.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to update pipeline stages order", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update pipeline stages order'),
            status_code=500
        )


# ============================================================================
# LEAD ENDPOINTS
# ============================================================================

@crm_bp.route('/leads', methods=['GET'])
@jwt_required()
@require_permission('view_crm')
@validate_pagination()
@log_api_call('list_leads')
def list_leads():
    """List leads with filtering and pagination."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        page = g.page
        per_page = g.per_page
        
        # Build query
        query = Lead.query.filter_by(tenant_id=tenant_id)
        
        # Apply filters
        if request.args.get('status'):
            query = query.filter_by(status=request.args.get('status'))
        
        if request.args.get('pipeline_id'):
            query = query.filter_by(pipeline_id=int(request.args.get('pipeline_id')))
        
        if request.args.get('stage_id'):
            query = query.filter_by(stage_id=int(request.args.get('stage_id')))
        
        if request.args.get('assigned_to_id'):
            query = query.filter_by(assigned_to_id=int(request.args.get('assigned_to_id')))
        
        if request.args.get('contact_id'):
            query = query.filter_by(contact_id=int(request.args.get('contact_id')))
        
        if request.args.get('priority'):
            query = query.filter_by(priority=request.args.get('priority'))
        
        if request.args.get('search'):
            search_term = f"%{request.args.get('search')}%"
            query = query.join(Lead.contact, isouter=True).filter(
                or_(
                    Lead.title.ilike(search_term),
                    Lead.description.ilike(search_term),
                    Contact.first_name.ilike(search_term),
                    Contact.last_name.ilike(search_term),
                    Contact.company.ilike(search_term)
                )
            )
        
        # Order by creation date (newest first)
        query = query.order_by(Lead.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        leads = [lead.to_dict() for lead in pagination.items]
        
        return paginated_response(
            items=leads,
            page=page,
            per_page=per_page,
            total=pagination.total,
            message=_('Leads retrieved successfully')
        )
        
    except Exception as e:
        logger.error("Failed to list leads", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve leads'),
            status_code=500
        )


@crm_bp.route('/leads', methods=['POST'])
@jwt_required()
@require_permission('manage_crm')
@require_json(['title'])
@log_api_call('create_lead')
@audit_log('create', 'lead')
def create_lead():
    """Create new lead."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        data = request.get_json()
        
        title = data['title'].strip()
        if not title:
            return validation_error_response({
                'title': [_('Lead title is required')]
            })
        
        # Validate contact if provided
        contact_id = data.get('contact_id')
        if contact_id:
            contact = Contact.query.filter_by(
                id=contact_id,
                tenant_id=tenant_id
            ).first()
            if not contact:
                return not_found_response('contact')
        
        # Validate pipeline and get default if not provided
        pipeline_id = data.get('pipeline_id')
        if not pipeline_id:
            default_pipeline = Pipeline.get_default(tenant_id)
            if not default_pipeline:
                return validation_error_response({
                    'pipeline_id': [_('No pipeline specified and no default pipeline found')]
                })
            pipeline_id = default_pipeline.id
        else:
            pipeline = Pipeline.query.filter_by(
                id=pipeline_id,
                tenant_id=tenant_id
            ).first()
            if not pipeline:
                return not_found_response('pipeline')
        
        # Get first stage of pipeline
        pipeline = Pipeline.query.get(pipeline_id)
        first_stage = pipeline.get_first_stage()
        if not first_stage:
            return validation_error_response({
                'pipeline_id': [_('Pipeline has no stages')]
            })
        
        # Validate assignee if provided
        assigned_to_id = data.get('assigned_to_id')
        if assigned_to_id:
            assignee = User.query.filter_by(
                id=assigned_to_id,
                tenant_id=tenant_id
            ).first()
            if not assignee:
                return validation_error_response({
                    'assigned_to_id': [_('Invalid user assignment')]
                })
        
        # Create lead
        lead = Lead.create(
            tenant_id=tenant_id,
            title=title,
            description=data.get('description', ''),
            contact_id=contact_id,
            pipeline_id=pipeline_id,
            stage_id=first_stage.id,
            value=data.get('value'),
            probability=data.get('probability', 50),
            expected_close_date=data.get('expected_close_date'),
            priority=data.get('priority', 'medium'),
            assigned_to_id=assigned_to_id,
            source=data.get('source', ''),
            campaign=data.get('campaign', ''),
            custom_fields=data.get('custom_fields', {}),
            tags=data.get('tags', [])
        )
        
        logger.info("Lead created", lead_id=lead.id, tenant_id=tenant_id, user_id=user.id)
        
        return success_response(
            message=_('Lead created successfully'),
            data=lead.to_dict(),
            status_code=201
        )
        
    except Exception as e:
        logger.error("Failed to create lead", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to create lead'),
            status_code=500
        )


@crm_bp.route('/leads/<int:lead_id>', methods=['GET'])
@jwt_required()
@require_permission('view_crm')
@log_api_call('get_lead')
def get_lead(lead_id):
    """Get specific lead."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Find lead in same tenant
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not lead:
            return not_found_response('lead')
        
        return success_response(
            message=_('Lead retrieved successfully'),
            data=lead.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to get lead", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve lead'),
            status_code=500
        )


@crm_bp.route('/leads/<int:lead_id>', methods=['PUT'])
@jwt_required()
@require_permission('manage_crm')
@require_json()
@log_api_call('update_lead')
@audit_log('update', 'lead')
def update_lead(lead_id):
    """Update lead."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant_id = user.tenant_id
        data = request.get_json()
        
        # Find lead in same tenant
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=tenant_id
        ).first()
        
        if not lead:
            return not_found_response('lead')
        
        # Fields that can be updated
        updatable_fields = [
            'title', 'description', 'value', 'probability', 'expected_close_date',
            'priority', 'assigned_to_id', 'source', 'campaign', 'custom_fields', 'tags'
        ]
        
        for field in updatable_fields:
            if field in data:
                # Validate specific fields
                if field == 'title' and not data[field].strip():
                    return validation_error_response({
                        'title': [_('Lead title is required')]
                    })
                
                if field == 'assigned_to_id' and data[field]:
                    # Validate user exists and belongs to tenant
                    assignee = User.query.filter_by(
                        id=data[field],
                        tenant_id=tenant_id
                    ).first()
                    if not assignee:
                        return validation_error_response({
                            'assigned_to_id': [_('Invalid user assignment')]
                        })
                
                setattr(lead, field, data[field])
        
        lead.save()
        
        logger.info("Lead updated", lead_id=lead.id, user_id=user.id)
        
        return success_response(
            message=_('Lead updated successfully'),
            data=lead.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to update lead", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update lead'),
            status_code=500
        )


@crm_bp.route('/leads/<int:lead_id>', methods=['DELETE'])
@jwt_required()
@require_permission('manage_crm')
@log_api_call('delete_lead')
@audit_log('delete', 'lead')
def delete_lead(lead_id):
    """Delete lead."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Find lead in same tenant
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not lead:
            return not_found_response('lead')
        
        # Soft delete
        lead.delete()
        
        logger.info("Lead deleted", lead_id=lead.id, user_id=user.id)
        
        return success_response(
            message=_('Lead deleted successfully')
        )
        
    except Exception as e:
        logger.error("Failed to delete lead", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to delete lead'),
            status_code=500
        )


@crm_bp.route('/leads/<int:lead_id>/stage', methods=['PUT'])
@jwt_required()
@require_permission('manage_crm')
@require_json(['stage_id'])
@log_api_call('move_lead_stage')
@audit_log('move_stage', 'lead')
def move_lead_stage(lead_id):
    """Move lead to different stage."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json()
        stage_id = data['stage_id']
        
        # Find lead in same tenant
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not lead:
            return not_found_response('lead')
        
        # Validate stage belongs to same pipeline
        stage = Stage.query.filter_by(
            id=stage_id,
            pipeline_id=lead.pipeline_id
        ).first()
        
        if not stage:
            return validation_error_response({
                'stage_id': [_('Invalid stage for this pipeline')]
            })
        
        old_stage_id = lead.stage_id
        lead.move_to_stage(stage_id)
        lead.save()
        
        logger.info(
            "Lead moved to stage",
            lead_id=lead.id,
            old_stage_id=old_stage_id,
            new_stage_id=stage_id,
            user_id=user.id
        )
        
        return success_response(
            message=_('Lead moved to stage successfully'),
            data=lead.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to move lead stage", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to move lead stage'),
            status_code=500
        )


@crm_bp.route('/leads/<int:lead_id>/status', methods=['PUT'])
@jwt_required()
@require_permission('manage_crm')
@require_json(['status'])
@log_api_call('update_lead_status')
@audit_log('update_status', 'lead')
def update_lead_status(lead_id):
    """Update lead status (won/lost/reopen)."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        data = request.get_json()
        status = data['status']
        
        # Find lead in same tenant
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not lead:
            return not_found_response('lead')
        
        valid_statuses = ['won', 'lost', 'open']
        if status not in valid_statuses:
            return validation_error_response({
                'status': [_('Invalid status. Valid values: %(statuses)s', 
                           statuses=', '.join(valid_statuses))]
            })
        
        old_status = lead.status
        
        if status == 'won':
            lead.mark_as_won()
        elif status == 'lost':
            reason = data.get('reason', '')
            lead.mark_as_lost(reason)
        elif status == 'open':
            lead.reopen()
        
        lead.save()
        
        logger.info(
            "Lead status updated",
            lead_id=lead.id,
            old_status=old_status,
            new_status=status,
            user_id=user.id
        )
        
        return success_response(
            message=_('Lead status updated successfully'),
            data=lead.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to update lead status", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update lead status'),
            status_code=500
        )


# ============================================================================
# LEAD HISTORY ENDPOINTS
# ============================================================================

@crm_bp.route('/leads/<int:lead_id>/history', methods=['GET'])
@jwt_required()
@require_permission('view_crm')
@log_api_call('get_lead_history')
def get_lead_history(lead_id):
    """Get lead history including tasks, notes, and activities."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        # Find lead in same tenant
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not lead:
            return not_found_response('lead')
        
        # Get tasks for this lead
        tasks = Task.get_by_lead(lead_id)
        
        # Get notes for this lead (filter private notes)
        notes = Note.get_by_lead(lead_id, user)
        
        # Get conversation threads linked to this lead
        threads = lead.get_active_threads()
        
        return success_response(
            message=_('Lead history retrieved successfully'),
            data={
                'lead': lead.to_dict(),
                'tasks': [task.to_dict() for task in tasks],
                'notes': [note.to_dict() for note in notes],
                'threads': [{'id': thread.id, 'subject': thread.subject, 'status': thread.status} for thread in threads]
            }
        )
        
    except Exception as e:
        logger.error("Failed to get lead history", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve lead history'),
            status_code=500
        )


# Import and register task, note, and stage endpoints from existing files
from app.api.crm_endpoints import register_task_endpoints, register_note_endpoints
from app.api.crm_stage_endpoints import register_stage_endpoints

# Register all endpoints
register_task_endpoints(crm_bp)
register_note_endpoints(crm_bp)
register_stage_endpoints(crm_bp)