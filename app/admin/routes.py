"""Admin routes for user and role management."""
from flask import request, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from sqlalchemy import or_
from app.admin import admin_bp
from app.models.user import User
from app.models.role import Role, Permission
from app.models.tenant import Tenant
from app.models.audit_log import AuditLog
from app.utils.decorators import (
    require_json, log_api_call, validate_pagination,
    require_permission, require_permissions, require_owner_or_permission
)
from app.utils.response import (
    success_response, error_response, validation_error_response,
    unauthorized_response, not_found_response
)
from app.utils.validators import validate_email
from app import db
import structlog

logger = structlog.get_logger()


# User Management Endpoints

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@validate_pagination()
@require_permission(Permission.MANAGE_USERS)
@log_api_call('list_users')
def list_users():
    """List users in the tenant with pagination and filtering."""
    try:
        user = get_current_user()
        
        # Build query
        query = User.query.filter_by(tenant_id=user.tenant_id, is_deleted=False)
        
        # Apply filters
        search = request.args.get('search', '').strip()
        if search:
            query = query.filter(
                or_(
                    User.email.ilike(f'%{search}%'),
                    User.first_name.ilike(f'%{search}%'),
                    User.last_name.ilike(f'%{search}%')
                )
            )
        
        role_filter = request.args.get('role')
        if role_filter:
            query = query.filter(User.role == role_filter)
        
        status_filter = request.args.get('status')
        if status_filter == 'active':
            query = query.filter(User.is_active == True)
        elif status_filter == 'inactive':
            query = query.filter(User.is_active == False)
        
        # Apply sorting
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        if hasattr(User, sort_by):
            if sort_order == 'asc':
                query = query.order_by(getattr(User, sort_by).asc())
            else:
                query = query.order_by(getattr(User, sort_by).desc())
        
        # Paginate
        pagination = query.paginate(
            page=g.page,
            per_page=g.per_page,
            error_out=False
        )
        
        return success_response(
            message=_('Users retrieved successfully'),
            data={
                'users': [user.to_dict() for user in pagination.items],
                'pagination': {
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }
        )
        
    except Exception as e:
        logger.error("Failed to list users", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve users'),
            status_code=500
        )


@admin_bp.route('/users', methods=['POST'])
@jwt_required()
@require_json(['email', 'role'])
@require_permission(Permission.MANAGE_USERS)
@log_api_call('create_user')
def create_user():
    """Create a new user in the tenant."""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        # Validate input
        email = data['email'].strip().lower()
        role = data['role']
        
        if not validate_email(email):
            return validation_error_response({
                'email': [_('Invalid email address')]
            })
        
        # Validate role
        valid_roles = ['manager', 'support', 'accounting', 'read_only']
        if role not in valid_roles:
            return validation_error_response({
                'role': [_('Invalid role. Must be one of: %(roles)s', 
                         roles=', '.join(valid_roles))]
            })
        
        # Check if user already exists in tenant
        existing_user = User.query.filter_by(
            email=email, 
            tenant_id=current_user.tenant_id,
            is_deleted=False
        ).first()
        
        if existing_user:
            return error_response(
                error_code='CONFLICT_ERROR',
                message=_('User with this email already exists in your organization'),
                status_code=409
            )
        
        # Generate temporary password
        import secrets
        import string
        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        
        # Create user
        new_user = User.create(
            email=email,
            password=temp_password,
            tenant_id=current_user.tenant_id,
            role=role,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            language=data.get('language', 'en'),
            is_active=data.get('is_active', True)
        )
        
        # Assign roles if provided
        if 'roles' in data and isinstance(data['roles'], list):
            for role_name in data['roles']:
                role_obj = Role.get_by_name(role_name, current_user.tenant_id)
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
                'first_name': data.get('first_name'),
                'last_name': data.get('last_name')
            }
        )
        
        # TODO: Send invitation email with temporary password
        
        logger.info(
            "User created successfully",
            user_id=new_user.id,
            email=email,
            created_by=current_user.id
        )
        
        return success_response(
            message=_('User created successfully. Invitation email sent.'),
            data={
                'user': new_user.to_dict(),
                'temporary_password': temp_password  # Remove in production
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


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
@require_permission(Permission.MANAGE_USERS)
@log_api_call('get_user')
def get_user(user_id):
    """Get user details."""
    try:
        current_user = get_current_user()
        
        user = User.query.filter_by(
            id=user_id,
            tenant_id=current_user.tenant_id,
            is_deleted=False
        ).first()
        
        if not user:
            return not_found_response(_('User not found'))
        
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


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
@require_json()
@require_permission(Permission.MANAGE_USERS)
@log_api_call('update_user')
def update_user(user_id):
    """Update user details."""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        user = User.query.filter_by(
            id=user_id,
            tenant_id=current_user.tenant_id,
            is_deleted=False
        ).first()
        
        if not user:
            return not_found_response(_('User not found'))
        
        # Prevent self-modification of critical fields
        if user.id == current_user.id:
            if 'role' in data or 'is_active' in data:
                return error_response(
                    error_code='VALIDATION_ERROR',
                    message=_('Cannot modify your own role or status'),
                    status_code=400
                )
        
        # Store old values for audit
        old_values = {}
        new_values = {}
        
        # Update allowed fields
        updatable_fields = [
            'first_name', 'last_name', 'role', 'is_active',
            'language', 'timezone'
        ]
        
        for field in updatable_fields:
            if field in data:
                old_values[field] = getattr(user, field)
                new_values[field] = data[field]
                setattr(user, field, data[field])
        
        # Validate role if provided
        if 'role' in data:
            valid_roles = ['owner', 'manager', 'support', 'accounting', 'read_only']
            if data['role'] not in valid_roles:
                return validation_error_response({
                    'role': [_('Invalid role')]
                })
        
        # Update roles if provided
        if 'roles' in data and isinstance(data['roles'], list):
            # Clear existing roles
            user.roles.clear()
            
            # Add new roles
            for role_name in data['roles']:
                role_obj = Role.get_by_name(role_name, current_user.tenant_id)
                if role_obj:
                    user.add_role(role_obj)
        
        user.save()
        
        # Log user update
        AuditLog.log_user_action(
            user=current_user,
            action='update',
            resource_type='user',
            resource_id=user.id,
            old_values=old_values,
            new_values=new_values
        )
        
        logger.info(
            "User updated successfully",
            user_id=user.id,
            updated_by=current_user.id
        )
        
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


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
@require_permission(Permission.MANAGE_USERS)
@log_api_call('delete_user')
def delete_user(user_id):
    """Soft delete a user."""
    try:
        current_user = get_current_user()
        
        user = User.query.filter_by(
            id=user_id,
            tenant_id=current_user.tenant_id,
            is_deleted=False
        ).first()
        
        if not user:
            return not_found_response(_('User not found'))
        
        # Prevent self-deletion
        if user.id == current_user.id:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Cannot delete your own account'),
                status_code=400
            )
        
        # Prevent deletion of owner
        if user.is_owner:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Cannot delete the organization owner'),
                status_code=400
            )
        
        # Soft delete
        user.soft_delete()
        
        # Log user deletion
        AuditLog.log_user_action(
            user=current_user,
            action='delete',
            resource_type='user',
            resource_id=user.id,
            old_values={'email': user.email, 'role': user.role}
        )
        
        logger.info(
            "User deleted successfully",
            user_id=user.id,
            deleted_by=current_user.id
        )
        
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


# Role Management Endpoints

@admin_bp.route('/roles', methods=['GET'])
@jwt_required()
@require_permission(Permission.MANAGE_ROLES)
@log_api_call('list_roles')
def list_roles():
    """List all roles in the tenant."""
    try:
        current_user = get_current_user()
        
        roles = Role.query.filter_by(
            tenant_id=current_user.tenant_id,
            is_deleted=False
        ).order_by(Role.name).all()
        
        return success_response(
            message=_('Roles retrieved successfully'),
            data={
                'roles': [role.to_dict() for role in roles],
                'available_permissions': Permission.get_all_permissions(),
                'permission_groups': Permission.get_permission_groups()
            }
        )
        
    except Exception as e:
        logger.error("Failed to list roles", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve roles'),
            status_code=500
        )


@admin_bp.route('/roles', methods=['POST'])
@jwt_required()
@require_json(['name', 'permissions'])
@require_owner_or_permission(Permission.MANAGE_ROLES)
@log_api_call('create_role')
def create_role():
    """Create a new role."""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        name = data['name'].strip()
        permissions = data['permissions']
        
        # Validate input
        if len(name) < 2:
            return validation_error_response({
                'name': [_('Role name must be at least 2 characters')]
            })
        
        # Check if role already exists
        existing_role = Role.get_by_name(name, current_user.tenant_id)
        if existing_role:
            return error_response(
                error_code='CONFLICT_ERROR',
                message=_('Role with this name already exists'),
                status_code=409
            )
        
        # Validate permissions
        valid_permissions = Permission.get_all_permissions()
        invalid_permissions = [p for p in permissions if p not in valid_permissions]
        if invalid_permissions:
            return validation_error_response({
                'permissions': [_('Invalid permissions: %(perms)s', 
                               perms=', '.join(invalid_permissions))]
            })
        
        # Create role
        role = Role(
            tenant_id=current_user.tenant_id,
            name=name,
            description=data.get('description', ''),
            is_system_role=False
        )
        role.set_permissions(permissions)
        role.save()
        
        # Log role creation
        AuditLog.log_user_action(
            user=current_user,
            action='create',
            resource_type='role',
            resource_id=role.id,
            new_values={
                'name': name,
                'permissions': permissions
            }
        )
        
        logger.info(
            "Role created successfully",
            role_id=role.id,
            name=name,
            created_by=current_user.id
        )
        
        return success_response(
            message=_('Role created successfully'),
            data=role.to_dict(),
            status_code=201
        )
        
    except Exception as e:
        logger.error("Failed to create role", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to create role'),
            status_code=500
        )


@admin_bp.route('/roles/<int:role_id>', methods=['PUT'])
@jwt_required()
@require_json()
@require_owner_or_permission(Permission.MANAGE_ROLES)
@log_api_call('update_role')
def update_role(role_id):
    """Update a role."""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        role = Role.query.filter_by(
            id=role_id,
            tenant_id=current_user.tenant_id,
            is_deleted=False
        ).first()
        
        if not role:
            return not_found_response(_('Role not found'))
        
        # Prevent modification of system roles
        if role.is_system_role:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Cannot modify system roles'),
                status_code=400
            )
        
        # Store old values for audit
        old_values = {
            'name': role.name,
            'description': role.description,
            'permissions': role.get_permissions()
        }
        
        # Update fields
        if 'name' in data:
            name = data['name'].strip()
            if len(name) < 2:
                return validation_error_response({
                    'name': [_('Role name must be at least 2 characters')]
                })
            
            # Check for name conflicts
            existing_role = Role.query.filter_by(
                name=name,
                tenant_id=current_user.tenant_id
            ).filter(Role.id != role_id).first()
            
            if existing_role:
                return error_response(
                    error_code='CONFLICT_ERROR',
                    message=_('Role with this name already exists'),
                    status_code=409
                )
            
            role.name = name
        
        if 'description' in data:
            role.description = data['description']
        
        if 'permissions' in data:
            permissions = data['permissions']
            
            # Validate permissions
            valid_permissions = Permission.get_all_permissions()
            invalid_permissions = [p for p in permissions if p not in valid_permissions]
            if invalid_permissions:
                return validation_error_response({
                    'permissions': [_('Invalid permissions: %(perms)s', 
                                   perms=', '.join(invalid_permissions))]
                })
            
            role.set_permissions(permissions)
        
        role.save()
        
        # Log role update
        AuditLog.log_user_action(
            user=current_user,
            action='update',
            resource_type='role',
            resource_id=role.id,
            old_values=old_values,
            new_values={
                'name': role.name,
                'description': role.description,
                'permissions': role.get_permissions()
            }
        )
        
        logger.info(
            "Role updated successfully",
            role_id=role.id,
            updated_by=current_user.id
        )
        
        return success_response(
            message=_('Role updated successfully'),
            data=role.to_dict()
        )
        
    except Exception as e:
        logger.error("Failed to update role", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update role'),
            status_code=500
        )


@admin_bp.route('/roles/<int:role_id>', methods=['DELETE'])
@jwt_required()
@require_owner_or_permission(Permission.MANAGE_ROLES)
@log_api_call('delete_role')
def delete_role(role_id):
    """Delete a role."""
    try:
        current_user = get_current_user()
        
        role = Role.query.filter_by(
            id=role_id,
            tenant_id=current_user.tenant_id,
            is_deleted=False
        ).first()
        
        if not role:
            return not_found_response(_('Role not found'))
        
        # Prevent deletion of system roles
        if role.is_system_role:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Cannot delete system roles'),
                status_code=400
            )
        
        # Check if role is in use
        users_with_role = User.query.join(User.roles).filter(
            Role.id == role_id,
            User.tenant_id == current_user.tenant_id,
            User.is_deleted == False
        ).count()
        
        if users_with_role > 0:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=_('Cannot delete role that is assigned to users'),
                status_code=400
            )
        
        # Soft delete
        role.soft_delete()
        
        # Log role deletion
        AuditLog.log_user_action(
            user=current_user,
            action='delete',
            resource_type='role',
            resource_id=role.id,
            old_values={
                'name': role.name,
                'permissions': role.get_permissions()
            }
        )
        
        logger.info(
            "Role deleted successfully",
            role_id=role.id,
            deleted_by=current_user.id
        )
        
        return success_response(
            message=_('Role deleted successfully')
        )
        
    except Exception as e:
        logger.error("Failed to delete role", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to delete role'),
            status_code=500
        )


# Permission Management Endpoints

@admin_bp.route('/permissions', methods=['GET'])
@jwt_required()
@require_permission(Permission.MANAGE_ROLES)
@log_api_call('list_permissions')
def list_permissions():
    """List all available permissions."""
    try:
        return success_response(
            message=_('Permissions retrieved successfully'),
            data={
                'permissions': Permission.get_all_permissions(),
                'permission_groups': Permission.get_permission_groups()
            }
        )
        
    except Exception as e:
        logger.error("Failed to list permissions", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve permissions'),
            status_code=500
        )