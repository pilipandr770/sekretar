"""Tenant management API endpoints."""
from flask import Blueprint, request, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from sqlalchemy.exc import IntegrityError
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role
from app.models.audit_log import AuditLog
from app.utils.decorators import (
    require_json, require_permission, require_role, 
    log_api_call, validate_pagination, audit_log
)
from app.utils.response import (
    success_response, error_response, validation_error_response,
    not_found_response, conflict_response, paginated_response
)
from app.utils.validators import validate_email, validate_required_fields
import structlog

logger = structlog.get_logger()

tenant_bp = Blueprint('tenant', __name__)


@tenant_bp.route('/', methods=['GET'])
@jwt_required()
@log_api_call('get_tenant')
def get_tenant():
    """Get current tenant information."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant = user.tenant
        
        # Get additional statistics
        stats = {
            'user_count': len(tenant.users) if tenant.users else 0,
            'active_user_count': len([u for u in tenant.users if u.is_active]) if tenant.users else 0,
            'subscription_status': tenant.subscription_status,
            'is_trial': tenant.subscription_status == 'trial',
            'trial_expired': tenant.is_trial_expired() if tenant.subscription_status == 'trial' else False
        }
        
        return success_response(
            message=_('Tenant information retrieved successfully'),
            data={
                'tenant': tenant.to_dict(),
                'stats': stats
            }
        )
        
    except Exception as e:
        logger.error("Failed to get tenant", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve tenant information'),
            status_code=500
        )


@tenant_bp.route('/', methods=['PUT'])
@jwt_required()
@require_permission('manage_settings')
@require_json()
@log_api_call('update_tenant')
@audit_log('update', 'tenant')
def update_tenant():
    """Update tenant information."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant = user.tenant
        data = request.get_json()
        
        # Fields that can be updated
        updatable_fields = ['name', 'domain', 'email', 'phone', 'address']
        
        old_values = {}
        new_values = {}
        
        for field in updatable_fields:
            if field in data:
                old_values[field] = getattr(tenant, field)
                new_values[field] = data[field]
                
                # Validate specific fields
                if field == 'email' and data[field]:
                    if not validate_email(data[field]):
                        return validation_error_response({
                            'email': [_('Invalid email address')]
                        })
                
                if field == 'name' and not data[field].strip():
                    return validation_error_response({
                        'name': [_('Organization name is required')]
                    })
                
                setattr(tenant, field, data[field])
        
        # Handle domain uniqueness
        if 'domain' in data and data['domain']:
            existing_tenant = Tenant.query.filter(
                Tenant.domain == data['domain'],
                Tenant.id != tenant.id
            ).first()
            
            if existing_tenant:
                return conflict_response(_('Domain is already in use'))
        
        tenant.save()
        
        # Log the update
        AuditLog.log_user_action(
            user=user,
            action='update',
            resource_type='tenant',
            resource_id=tenant.id,
            old_values=old_values,
            new_values=new_values
        )
        
        logger.info("Tenant updated", tenant_id=tenant.id, user_id=user.id)
        
        return success_response(
            message=_('Tenant information updated successfully'),
            data=tenant.to_dict()
        )
        
    except IntegrityError as e:
        logger.error("Tenant update failed - integrity error", error=str(e))
        return conflict_response(_('Domain or slug already exists'))
    except Exception as e:
        logger.error("Failed to update tenant", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update tenant information'),
            status_code=500
        )


@tenant_bp.route('/settings', methods=['GET'])
@jwt_required()
@require_permission('manage_settings')
@log_api_call('get_tenant_settings')
def get_tenant_settings():
    """Get tenant settings."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant = user.tenant
        
        return success_response(
            message=_('Tenant settings retrieved successfully'),
            data={
                'settings': tenant.settings or {},
                'subscription_status': tenant.subscription_status,
                'trial_ends_at': tenant.trial_ends_at
            }
        )
        
    except Exception as e:
        logger.error("Failed to get tenant settings", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve tenant settings'),
            status_code=500
        )


@tenant_bp.route('/settings', methods=['PUT'])
@jwt_required()
@require_permission('manage_settings')
@require_json()
@log_api_call('update_tenant_settings')
@audit_log('update_settings', 'tenant')
def update_tenant_settings():
    """Update tenant settings."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant = user.tenant
        data = request.get_json()
        
        if 'settings' not in data:
            return validation_error_response({
                'settings': [_('Settings object is required')]
            })
        
        new_settings = data['settings']
        if not isinstance(new_settings, dict):
            return validation_error_response({
                'settings': [_('Settings must be an object')]
            })
        
        old_settings = tenant.settings.copy() if tenant.settings else {}
        
        # Update settings
        if tenant.settings is None:
            tenant.settings = {}
        
        tenant.settings.update(new_settings)
        tenant.save()
        
        # Log the update
        AuditLog.log_user_action(
            user=user,
            action='update_settings',
            resource_type='tenant',
            resource_id=tenant.id,
            old_values={'settings': old_settings},
            new_values={'settings': tenant.settings}
        )
        
        logger.info("Tenant settings updated", tenant_id=tenant.id, user_id=user.id)
        
        return success_response(
            message=_('Tenant settings updated successfully'),
            data={'settings': tenant.settings}
        )
        
    except Exception as e:
        logger.error("Failed to update tenant settings", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update tenant settings'),
            status_code=500
        )


@tenant_bp.route('/users', methods=['GET'])
@jwt_required()
@require_permission('manage_users')
@validate_pagination()
@log_api_call('list_tenant_users')
def list_tenant_users():
    """List tenant users with pagination."""
    try:
        user = get_current_user()
        if not user or not user.tenant:
            return not_found_response('tenant')
        
        tenant = user.tenant
        page = g.page
        per_page = g.per_page
        
        # Build query
        query = User.query.filter_by(tenant_id=tenant.id)
        
        # Apply filters
        if request.args.get('role'):
            query = query.filter_by(role=request.args.get('role'))
        
        if request.args.get('is_active') is not None:
            is_active = request.args.get('is_active').lower() == 'true'
            query = query.filter_by(is_active=is_active)
        
        if request.args.get('search'):
            search_term = f"%{request.args.get('search')}%"
            query = query.filter(
                User.email.ilike(search_term) |
                User.first_name.ilike(search_term) |
                User.last_name.ilike(search_term)
            )
        
        # Order by creation date (newest first)
        query = query.order_by(User.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        users = [user.to_dict() for user in pagination.items]
        
        return paginated_response(
            items=users,
            page=page,
            per_page=per_page,
            total=pagination.total,
            message=_('Users retrieved successfully')
        )
        
    except Exception as e:
        logger.error("Failed to list tenant users", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve users'),
            status_code=500
        )


@tenant_bp.route('/users', methods=['POST'])
@jwt_required()
@require_permission('manage_users')
@require_json(['email', 'role'])
@log_api_call('create_tenant_user')
@audit_log('create', 'user')
def create_tenant_user():
    """Create new tenant user."""
    try:
        current_user = get_current_user()
        if not current_user or not current_user.tenant:
            return not_found_response('tenant')
        
        tenant = current_user.tenant
        data = request.get_json()
        
        # Validate input
        email = data['email'].strip().lower()
        role = data['role']
        
        if not validate_email(email):
            return validation_error_response({
                'email': [_('Invalid email address')]
            })
        
        # Validate role
        valid_roles = ['owner', 'manager', 'support', 'accounting', 'read_only']
        if role not in valid_roles:
            return validation_error_response({
                'role': [_('Invalid role. Valid roles: %(roles)s', roles=', '.join(valid_roles))]
            })
        
        # Only owners can create other owners
        if role == 'owner' and not current_user.is_owner:
            return error_response(
                error_code='AUTHORIZATION_ERROR',
                message=_('Only owners can create other owners'),
                status_code=403
            )
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return conflict_response(_('User with this email already exists'))
        
        # Generate temporary password
        import secrets
        import string
        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        
        # Create user
        new_user = User.create(
            email=email,
            password=temp_password,
            tenant_id=tenant.id,
            role=role,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            language=data.get('language', 'en'),
            is_active=data.get('is_active', True)
        )
        
        # Assign role-based permissions
        if tenant.roles:
            role_obj = next((r for r in tenant.roles if r.name.lower() == role.lower()), None)
            if role_obj:
                new_user.add_role(role_obj)
                new_user.save()
        
        # Log user creation
        AuditLog.log_user_action(
            user=current_user,
            action='create',
            resource_type='user',
            resource_id=new_user.id,
            new_values={
                'email': email,
                'role': role,
                'tenant_id': tenant.id
            }
        )
        
        logger.info(
            "User created",
            user_id=new_user.id,
            tenant_id=tenant.id,
            created_by=current_user.id,
            email=email,
            role=role
        )
        
        # TODO: Send invitation email with temporary password
        
        return success_response(
            message=_('User created successfully. Invitation email will be sent.'),
            data={
                'user': new_user.to_dict(),
                'temporary_password': temp_password  # Remove this in production
            },
            status_code=201
        )
        
    except Exception as e:
        logger.error("Failed to create user", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to create user'),
            status_code=500
        )


@tenant_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
@require_permission('manage_users')
@log_api_call('get_tenant_user')
def get_tenant_user(user_id):
    """Get specific tenant user."""
    try:
        current_user = get_current_user()
        if not current_user or not current_user.tenant:
            return not_found_response('tenant')
        
        tenant = current_user.tenant
        
        # Find user in same tenant
        user = User.query.filter_by(id=user_id, tenant_id=tenant.id).first()
        if not user:
            return not_found_response('user')
        
        return success_response(
            message=_('User retrieved successfully'),
            data=user.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to get user", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve user'),
            status_code=500
        )


@tenant_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
@require_permission('manage_users')
@require_json()
@log_api_call('update_tenant_user')
@audit_log('update', 'user')
def update_tenant_user(user_id):
    """Update tenant user."""
    try:
        current_user = get_current_user()
        if not current_user or not current_user.tenant:
            return not_found_response('tenant')
        
        tenant = current_user.tenant
        data = request.get_json()
        
        # Find user in same tenant
        user = User.query.filter_by(id=user_id, tenant_id=tenant.id).first()
        if not user:
            return not_found_response('user')
        
        # Prevent self-deactivation
        if user.id == current_user.id and 'is_active' in data and not data['is_active']:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Cannot deactivate your own account'),
                status_code=400
            )
        
        # Only owners can modify other owners
        if user.role == 'owner' and not current_user.is_owner:
            return error_response(
                error_code='AUTHORIZATION_ERROR',
                message=_('Only owners can modify other owners'),
                status_code=403
            )
        
        # Fields that can be updated
        updatable_fields = ['first_name', 'last_name', 'role', 'is_active', 'language']
        
        old_values = {}
        new_values = {}
        
        for field in updatable_fields:
            if field in data:
                old_values[field] = getattr(user, field)
                new_values[field] = data[field]
                
                # Validate role change
                if field == 'role':
                    valid_roles = ['owner', 'manager', 'support', 'accounting', 'read_only']
                    if data[field] not in valid_roles:
                        return validation_error_response({
                            'role': [_('Invalid role. Valid roles: %(roles)s', roles=', '.join(valid_roles))]
                        })
                    
                    # Only owners can assign owner role
                    if data[field] == 'owner' and not current_user.is_owner:
                        return error_response(
                            error_code='AUTHORIZATION_ERROR',
                            message=_('Only owners can assign owner role'),
                            status_code=403
                        )
                
                setattr(user, field, data[field])
        
        user.save()
        
        # Log the update
        AuditLog.log_user_action(
            user=current_user,
            action='update',
            resource_type='user',
            resource_id=user.id,
            old_values=old_values,
            new_values=new_values
        )
        
        logger.info("User updated", user_id=user.id, updated_by=current_user.id)
        
        return success_response(
            message=_('User updated successfully'),
            data=user.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to update user", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update user'),
            status_code=500
        )


@tenant_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
@require_permission('manage_users')
@log_api_call('delete_tenant_user')
@audit_log('delete', 'user')
def delete_tenant_user(user_id):
    """Delete (deactivate) tenant user."""
    try:
        current_user = get_current_user()
        if not current_user or not current_user.tenant:
            return not_found_response('tenant')
        
        tenant = current_user.tenant
        
        # Find user in same tenant
        user = User.query.filter_by(id=user_id, tenant_id=tenant.id).first()
        if not user:
            return not_found_response('user')
        
        # Prevent self-deletion
        if user.id == current_user.id:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Cannot delete your own account'),
                status_code=400
            )
        
        # Only owners can delete other owners
        if user.role == 'owner' and not current_user.is_owner:
            return error_response(
                error_code='AUTHORIZATION_ERROR',
                message=_('Only owners can delete other owners'),
                status_code=403
            )
        
        # Soft delete (deactivate) instead of hard delete
        user.is_active = False
        user.save()
        
        # Log the deletion
        AuditLog.log_user_action(
            user=current_user,
            action='delete',
            resource_type='user',
            resource_id=user.id,
            old_values={'is_active': True},
            new_values={'is_active': False}
        )
        
        logger.info("User deleted", user_id=user.id, deleted_by=current_user.id)
        
        return success_response(
            message=_('User deleted successfully')
        )
        
    except Exception as e:
        logger.error("Failed to delete user", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to delete user'),
            status_code=500
        )


@tenant_bp.route('/users/<int:user_id>/invite', methods=['POST'])
@jwt_required()
@require_permission('manage_users')
@log_api_call('resend_user_invitation')
def resend_user_invitation(user_id):
    """Resend invitation to user."""
    try:
        current_user = get_current_user()
        if not current_user or not current_user.tenant:
            return not_found_response('tenant')
        
        tenant = current_user.tenant
        
        # Find user in same tenant
        user = User.query.filter_by(id=user_id, tenant_id=tenant.id).first()
        if not user:
            return not_found_response('user')
        
        # Generate new verification token
        user.generate_email_verification_token()
        user.save()
        
        # TODO: Send invitation email
        
        # Log the action
        AuditLog.log_user_action(
            user=current_user,
            action='resend_invitation',
            resource_type='user',
            resource_id=user.id
        )
        
        logger.info("Invitation resent", user_id=user.id, sent_by=current_user.id)
        
        return success_response(
            message=_('Invitation sent successfully')
        )
        
    except Exception as e:
        logger.error("Failed to resend invitation", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to send invitation'),
            status_code=500
        )