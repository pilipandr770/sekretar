"""CRM routes with i18n support."""
from flask import request, g
from flask_babel import gettext as _
from app.crm import crm_bp
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.task import Task
from app.models.pipeline import Pipeline
from app.utils.decorators import (
    require_tenant, require_json, require_permission, 
    validate_pagination, log_api_call, audit_log
)
from app.utils.response import (
    success_response, error_response, not_found_response,
    validation_error_response, paginated_response
)
from app.utils.validators import validate_email, validate_phone
import structlog

logger = structlog.get_logger()


@crm_bp.route('/contacts', methods=['GET'])
@require_tenant()
@validate_pagination()
@log_api_call('list_contacts')
def list_contacts():
    """List contacts with pagination."""
    try:
        search = request.args.get('search', '').strip()
        contact_type = request.args.get('type')
        
        query = Contact.query.filter_by(tenant_id=g.tenant_id)
        
        # Apply filters
        if search:
            search_term = f'%{search}%'
            query = query.filter(
                Contact.first_name.ilike(search_term) |
                Contact.last_name.ilike(search_term) |
                Contact.company.ilike(search_term) |
                Contact.email.ilike(search_term)
            )
        
        if contact_type:
            query = query.filter_by(contact_type=contact_type)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        contacts = query.offset((g.page - 1) * g.per_page)\
                       .limit(g.per_page)\
                       .all()
        
        return paginated_response(
            items=[contact.to_dict() for contact in contacts],
            page=g.page,
            per_page=g.per_page,
            total=total,
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
@require_tenant()
@require_json(['email'])
@require_permission('manage_crm')
@log_api_call('create_contact')
@audit_log('create', 'contact')
def create_contact():
    """Create new contact."""
    try:
        data = request.get_json()
        
        # Validate email
        email = data.get('email', '').strip().lower()
        if not validate_email(email):
            return validation_error_response({
                'email': [_('Invalid email address')]
            })
        
        # Check if contact already exists
        existing = Contact.find_by_email(g.tenant_id, email)
        if existing:
            return error_response(
                error_code='CONFLICT_ERROR',
                message=_('Contact with this email already exists'),
                status_code=409
            )
        
        # Validate phone if provided
        phone = data.get('phone', '').strip()
        if phone and not validate_phone(phone):
            return validation_error_response({
                'phone': [_('Invalid phone number')]
            })
        
        # Create contact
        contact = Contact.create(
            tenant_id=g.tenant_id,
            email=email,
            first_name=data.get('first_name', '').strip(),
            last_name=data.get('last_name', '').strip(),
            company=data.get('company', '').strip(),
            phone=phone,
            contact_type=data.get('contact_type', 'prospect'),
            source=data.get('source', 'manual'),
            created_by_id=g.user_id
        )
        
        logger.info("Contact created", contact_id=contact.id, email=email)
        
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
@require_tenant()
@log_api_call('get_contact')
def get_contact(contact_id):
    """Get contact by ID."""
    try:
        contact = Contact.get_by_id_or_404(contact_id, g.tenant_id)
        
        return success_response(
            message=_('Contact retrieved successfully'),
            data=contact.to_dict()
        )
        
    except Exception as e:
        if 'not found' in str(e).lower():
            return not_found_response(_('Contact'))
        
        logger.error("Failed to get contact", contact_id=contact_id, error=str(e))
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve contact'),
            status_code=500
        )


@crm_bp.route('/contacts/<int:contact_id>', methods=['PUT'])
@require_tenant()
@require_json()
@require_permission('manage_crm')
@log_api_call('update_contact')
@audit_log('update', 'contact')
def update_contact(contact_id):
    """Update contact."""
    try:
        contact = Contact.get_by_id_or_404(contact_id, g.tenant_id)
        data = request.get_json()
        
        # Validate email if provided
        if 'email' in data:
            email = data['email'].strip().lower()
            if not validate_email(email):
                return validation_error_response({
                    'email': [_('Invalid email address')]
                })
            
            # Check for duplicates
            existing = Contact.find_by_email(g.tenant_id, email)
            if existing and existing.id != contact.id:
                return error_response(
                    error_code='CONFLICT_ERROR',
                    message=_('Contact with this email already exists'),
                    status_code=409
                )
            
            contact.email = email
        
        # Validate phone if provided
        if 'phone' in data:
            phone = data['phone'].strip()
            if phone and not validate_phone(phone):
                return validation_error_response({
                    'phone': [_('Invalid phone number')]
                })
            contact.phone = phone
        
        # Update other fields
        updatable_fields = [
            'first_name', 'last_name', 'company', 'title',
            'mobile', 'website', 'contact_type', 'status',
            'preferred_contact_method', 'timezone', 'language',
            'email_opt_in', 'sms_opt_in', 'notes'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(contact, field, data[field])
        
        contact.updated_by_id = g.user_id
        contact.save()
        
        logger.info("Contact updated", contact_id=contact.id)
        
        return success_response(
            message=_('Contact updated successfully'),
            data=contact.to_dict()
        )
        
    except Exception as e:
        if 'not found' in str(e).lower():
            return not_found_response(_('Contact'))
        
        logger.error("Failed to update contact", contact_id=contact_id, error=str(e))
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update contact'),
            status_code=500
        )


@crm_bp.route('/leads', methods=['GET'])
@require_tenant()
@validate_pagination()
@log_api_call('list_leads')
def list_leads():
    """List leads with pagination."""
    try:
        status = request.args.get('status')
        pipeline_id = request.args.get('pipeline_id')
        stage_id = request.args.get('stage_id')
        assigned_to = request.args.get('assigned_to')
        
        query = Lead.query.filter_by(tenant_id=g.tenant_id)
        
        # Apply filters
        if status:
            query = query.filter_by(status=status)
        
        if pipeline_id:
            query = query.filter_by(pipeline_id=pipeline_id)
        
        if stage_id:
            query = query.filter_by(stage_id=stage_id)
        
        if assigned_to:
            if assigned_to == 'me':
                query = query.filter_by(assigned_to_id=g.user_id)
            elif assigned_to == 'unassigned':
                query = query.filter_by(assigned_to_id=None)
            else:
                try:
                    user_id = int(assigned_to)
                    query = query.filter_by(assigned_to_id=user_id)
                except ValueError:
                    pass
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        leads = query.order_by(Lead.created_at.desc())\
                    .offset((g.page - 1) * g.per_page)\
                    .limit(g.per_page)\
                    .all()
        
        return paginated_response(
            items=[lead.to_dict() for lead in leads],
            page=g.page,
            per_page=g.per_page,
            total=total,
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
@require_tenant()
@require_json(['title'])
@require_permission('manage_crm')
@log_api_call('create_lead')
@audit_log('create', 'lead')
def create_lead():
    """Create new lead."""
    try:
        data = request.get_json()
        
        # Get or create default pipeline
        pipeline_id = data.get('pipeline_id')
        if not pipeline_id:
            default_pipeline = Pipeline.get_default(g.tenant_id)
            if not default_pipeline:
                default_pipeline = Pipeline.create_default(g.tenant_id)
            pipeline_id = default_pipeline.id
        
        # Create lead
        lead = Lead.create_from_contact(
            tenant_id=g.tenant_id,
            contact_id=data.get('contact_id'),
            title=data['title'],
            pipeline_id=pipeline_id,
            description=data.get('description'),
            value=data.get('value'),
            probability=data.get('probability', 50),
            expected_close_date=data.get('expected_close_date'),
            source=data.get('source', 'manual'),
            priority=data.get('priority', 'medium'),
            assigned_to_id=data.get('assigned_to_id'),
            created_by_id=g.user_id
        )
        
        logger.info("Lead created", lead_id=lead.id, title=lead.title)
        
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


@crm_bp.route('/pipelines', methods=['GET'])
@require_tenant()
@log_api_call('list_pipelines')
def list_pipelines():
    """List pipelines."""
    try:
        pipelines = Pipeline.query.filter_by(
            tenant_id=g.tenant_id,
            is_active=True
        ).all()
        
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