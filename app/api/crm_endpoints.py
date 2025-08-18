"""CRM management API endpoints - Task and Note sections."""
from flask import Blueprint, request, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from sqlalchemy import and_, or_, desc
from app.models.task import Task
from app.models.note import Note
from app.models.lead import Lead
from app.models.user import User
from app.utils.decorators import (
    require_json, require_permission, 
    log_api_call, validate_pagination, audit_log
)
from app.utils.response import (
    success_response, error_response, validation_error_response,
    not_found_response, paginated_response
)
from app.utils.rate_limit_decorators import api_rate_limit
import structlog

logger = structlog.get_logger()


# ============================================================================
# TASK ENDPOINTS
# ============================================================================

def register_task_endpoints(crm_bp):
    """Register task-related endpoints."""
    
    @crm_bp.route('/tasks', methods=['GET'])
    @api_rate_limit(category="crm")
    @jwt_required()
    @require_permission('view_crm')
    @validate_pagination()
    @log_api_call('list_tasks')
    def list_tasks():
        """List tasks with filtering and pagination."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            tenant_id = user.tenant_id
            page = g.page
            per_page = g.per_page
            
            # Build query
            query = Task.query.filter_by(tenant_id=tenant_id)
            
            # Apply filters
            if request.args.get('status'):
                query = query.filter_by(status=request.args.get('status'))
            
            if request.args.get('lead_id'):
                query = query.filter_by(lead_id=int(request.args.get('lead_id')))
            
            if request.args.get('assigned_to_id'):
                query = query.filter_by(assigned_to_id=int(request.args.get('assigned_to_id')))
            
            if request.args.get('priority'):
                query = query.filter_by(priority=request.args.get('priority'))
            
            if request.args.get('task_type'):
                query = query.filter_by(task_type=request.args.get('task_type'))
            
            if request.args.get('overdue') == 'true':
                from datetime import datetime
                now = datetime.utcnow().isoformat()
                query = query.filter(
                    Task.status != 'completed',
                    Task.due_date < now
                )
            
            if request.args.get('due_today') == 'true':
                from datetime import datetime, date
                today = date.today()
                start_of_day = datetime.combine(today, datetime.min.time()).isoformat()
                end_of_day = datetime.combine(today, datetime.max.time()).isoformat()
                query = query.filter(
                    Task.status != 'completed',
                    Task.due_date >= start_of_day,
                    Task.due_date <= end_of_day
                )
            
            if request.args.get('search'):
                search_term = f"%{request.args.get('search')}%"
                query = query.filter(
                    or_(
                        Task.title.ilike(search_term),
                        Task.description.ilike(search_term)
                    )
                )
            
            # Order by due date, then priority
            query = query.order_by(Task.due_date.asc(), Task.priority.desc(), Task.created_at.desc())
            
            # Paginate
            pagination = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            tasks = [task.to_dict() for task in pagination.items]
            
            return paginated_response(
                items=tasks,
                page=page,
                per_page=per_page,
                total=pagination.total,
                message=_('Tasks retrieved successfully')
            )
            
        except Exception as e:
            logger.error("Failed to list tasks", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to retrieve tasks'),
                status_code=500
            )

    @crm_bp.route('/tasks', methods=['POST'])
    @jwt_required()
    @require_permission('manage_crm')
    @require_json(['title'])
    @log_api_call('create_task')
    @audit_log('create', 'task')
    def create_task():
        """Create new task."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            tenant_id = user.tenant_id
            data = request.get_json()
            
            title = data['title'].strip()
            if not title:
                return validation_error_response({
                    'title': [_('Task title is required')]
                })
            
            # Validate lead if provided
            lead_id = data.get('lead_id')
            if lead_id:
                lead = Lead.query.filter_by(
                    id=lead_id,
                    tenant_id=tenant_id
                ).first()
                if not lead:
                    return not_found_response('lead')
            
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
            
            # Create task
            task = Task.create(
                tenant_id=tenant_id,
                title=title,
                description=data.get('description', ''),
                lead_id=lead_id,
                assigned_to_id=assigned_to_id,
                priority=data.get('priority', 'medium'),
                task_type=data.get('task_type', 'general'),
                category=data.get('category'),
                due_date=data.get('due_date'),
                extra_data=data.get('extra_data', {}),
                tags=data.get('tags', [])
            )
            
            logger.info("Task created", task_id=task.id, tenant_id=tenant_id, user_id=user.id)
            
            return success_response(
                message=_('Task created successfully'),
                data=task.to_dict(),
                status_code=201
            )
            
        except Exception as e:
            logger.error("Failed to create task", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to create task'),
                status_code=500
            )

    @crm_bp.route('/tasks/<int:task_id>', methods=['GET'])
    @jwt_required()
    @require_permission('view_crm')
    @log_api_call('get_task')
    def get_task(task_id):
        """Get specific task."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            # Find task in same tenant
            task = Task.query.filter_by(
                id=task_id,
                tenant_id=user.tenant_id
            ).first()
            
            if not task:
                return not_found_response('task')
            
            return success_response(
                message=_('Task retrieved successfully'),
                data=task.to_dict()
            )
            
        except Exception as e:
            logger.error("Failed to get task", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to retrieve task'),
                status_code=500
            )

    @crm_bp.route('/tasks/<int:task_id>', methods=['PUT'])
    @jwt_required()
    @require_permission('manage_crm')
    @require_json()
    @log_api_call('update_task')
    @audit_log('update', 'task')
    def update_task(task_id):
        """Update task."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            tenant_id = user.tenant_id
            data = request.get_json()
            
            # Find task in same tenant
            task = Task.query.filter_by(
                id=task_id,
                tenant_id=tenant_id
            ).first()
            
            if not task:
                return not_found_response('task')
            
            # Fields that can be updated
            updatable_fields = [
                'title', 'description', 'priority', 'task_type', 'category',
                'due_date', 'assigned_to_id', 'extra_data', 'tags'
            ]
            
            for field in updatable_fields:
                if field in data:
                    # Validate specific fields
                    if field == 'title' and not data[field].strip():
                        return validation_error_response({
                            'title': [_('Task title is required')]
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
                    
                    setattr(task, field, data[field])
            
            task.save()
            
            logger.info("Task updated", task_id=task.id, user_id=user.id)
            
            return success_response(
                message=_('Task updated successfully'),
                data=task.to_dict()
            )
            
        except Exception as e:
            logger.error("Failed to update task", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to update task'),
                status_code=500
            )

    @crm_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
    @jwt_required()
    @require_permission('manage_crm')
    @log_api_call('delete_task')
    @audit_log('delete', 'task')
    def delete_task(task_id):
        """Delete task."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            # Find task in same tenant
            task = Task.query.filter_by(
                id=task_id,
                tenant_id=user.tenant_id
            ).first()
            
            if not task:
                return not_found_response('task')
            
            # Soft delete
            task.delete()
            
            logger.info("Task deleted", task_id=task.id, user_id=user.id)
            
            return success_response(
                message=_('Task deleted successfully')
            )
            
        except Exception as e:
            logger.error("Failed to delete task", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to delete task'),
                status_code=500
            )

    @crm_bp.route('/tasks/<int:task_id>/status', methods=['PUT'])
    @jwt_required()
    @require_permission('manage_crm')
    @require_json(['status'])
    @log_api_call('update_task_status')
    @audit_log('update_status', 'task')
    def update_task_status(task_id):
        """Update task status."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            data = request.get_json()
            status = data['status']
            
            # Find task in same tenant
            task = Task.query.filter_by(
                id=task_id,
                tenant_id=user.tenant_id
            ).first()
            
            if not task:
                return not_found_response('task')
            
            valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
            if status not in valid_statuses:
                return validation_error_response({
                    'status': [_('Invalid status. Valid values: %(statuses)s', 
                               statuses=', '.join(valid_statuses))]
                })
            
            old_status = task.status
            
            if status == 'completed':
                task.complete()
            elif status == 'in_progress':
                task.start()
            elif status == 'cancelled':
                task.cancel()
            elif status == 'pending':
                task.reopen()
            
            task.save()
            
            logger.info(
                "Task status updated",
                task_id=task.id,
                old_status=old_status,
                new_status=status,
                user_id=user.id
            )
            
            return success_response(
                message=_('Task status updated successfully'),
                data=task.to_dict()
            )
            
        except Exception as e:
            logger.error("Failed to update task status", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to update task status'),
                status_code=500
            )


# ============================================================================
# NOTE ENDPOINTS
# ============================================================================

def register_note_endpoints(crm_bp):
    """Register note-related endpoints."""
    
    @crm_bp.route('/notes', methods=['GET'])
    @jwt_required()
    @require_permission('view_crm')
    @validate_pagination()
    @log_api_call('list_notes')
    def list_notes():
        """List notes with filtering and pagination."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            tenant_id = user.tenant_id
            page = g.page
            per_page = g.per_page
            
            # Build query
            query = Note.query.filter_by(tenant_id=tenant_id)
            
            # Filter private notes (only show user's own private notes)
            query = query.filter(
                or_(
                    Note.is_private == False,
                    Note.user_id == user.id
                )
            )
            
            # Apply filters
            if request.args.get('lead_id'):
                query = query.filter_by(lead_id=int(request.args.get('lead_id')))
            
            if request.args.get('user_id'):
                query = query.filter_by(user_id=int(request.args.get('user_id')))
            
            if request.args.get('note_type'):
                query = query.filter_by(note_type=request.args.get('note_type'))
            
            if request.args.get('is_pinned') == 'true':
                query = query.filter_by(is_pinned=True)
            
            if request.args.get('search'):
                search_term = f"%{request.args.get('search')}%"
                query = query.filter(
                    or_(
                        Note.title.ilike(search_term),
                        Note.content.ilike(search_term)
                    )
                )
            
            # Order by pinned first, then creation date
            query = query.order_by(Note.is_pinned.desc(), Note.created_at.desc())
            
            # Paginate
            pagination = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            notes = [note.to_dict() for note in pagination.items]
            
            return paginated_response(
                items=notes,
                page=page,
                per_page=per_page,
                total=pagination.total,
                message=_('Notes retrieved successfully')
            )
            
        except Exception as e:
            logger.error("Failed to list notes", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to retrieve notes'),
                status_code=500
            )

    @crm_bp.route('/notes', methods=['POST'])
    @jwt_required()
    @require_permission('manage_crm')
    @require_json(['content'])
    @log_api_call('create_note')
    @audit_log('create', 'note')
    def create_note():
        """Create new note."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            tenant_id = user.tenant_id
            data = request.get_json()
            
            content = data['content'].strip()
            if not content:
                return validation_error_response({
                    'content': [_('Note content is required')]
                })
            
            # Validate lead if provided
            lead_id = data.get('lead_id')
            if lead_id:
                lead = Lead.query.filter_by(
                    id=lead_id,
                    tenant_id=tenant_id
                ).first()
                if not lead:
                    return not_found_response('lead')
            
            # Create note
            note = Note.create(
                tenant_id=tenant_id,
                user_id=user.id,
                title=data.get('title'),
                content=content,
                lead_id=lead_id,
                note_type=data.get('note_type', 'general'),
                is_private=data.get('is_private', False),
                is_pinned=data.get('is_pinned', False),
                extra_data=data.get('extra_data', {}),
                tags=data.get('tags', [])
            )
            
            logger.info("Note created", note_id=note.id, tenant_id=tenant_id, user_id=user.id)
            
            return success_response(
                message=_('Note created successfully'),
                data=note.to_dict(),
                status_code=201
            )
            
        except Exception as e:
            logger.error("Failed to create note", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to create note'),
                status_code=500
            )

    @crm_bp.route('/notes/<int:note_id>', methods=['GET'])
    @jwt_required()
    @require_permission('view_crm')
    @log_api_call('get_note')
    def get_note(note_id):
        """Get specific note."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            # Find note in same tenant
            note = Note.query.filter_by(
                id=note_id,
                tenant_id=user.tenant_id
            ).first()
            
            if not note:
                return not_found_response('note')
            
            # Check if user can view this note
            if not note.can_be_viewed_by(user):
                return error_response(
                    error_code='AUTHORIZATION_ERROR',
                    message=_('Access denied to private note'),
                    status_code=403
                )
            
            return success_response(
                message=_('Note retrieved successfully'),
                data=note.to_dict()
            )
            
        except Exception as e:
            logger.error("Failed to get note", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to retrieve note'),
                status_code=500
            )

    @crm_bp.route('/notes/<int:note_id>', methods=['PUT'])
    @jwt_required()
    @require_permission('manage_crm')
    @require_json()
    @log_api_call('update_note')
    @audit_log('update', 'note')
    def update_note(note_id):
        """Update note."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            data = request.get_json()
            
            # Find note in same tenant
            note = Note.query.filter_by(
                id=note_id,
                tenant_id=user.tenant_id
            ).first()
            
            if not note:
                return not_found_response('note')
            
            # Check if user can edit this note
            if not note.can_be_edited_by(user):
                return error_response(
                    error_code='AUTHORIZATION_ERROR',
                    message=_('Access denied to edit this note'),
                    status_code=403
                )
            
            # Fields that can be updated
            updatable_fields = [
                'title', 'content', 'note_type', 'is_private', 'is_pinned',
                'extra_data', 'tags'
            ]
            
            for field in updatable_fields:
                if field in data:
                    # Validate specific fields
                    if field == 'content' and not data[field].strip():
                        return validation_error_response({
                            'content': [_('Note content is required')]
                        })
                    
                    setattr(note, field, data[field])
            
            note.save()
            
            logger.info("Note updated", note_id=note.id, user_id=user.id)
            
            return success_response(
                message=_('Note updated successfully'),
                data=note.to_dict()
            )
            
        except Exception as e:
            logger.error("Failed to update note", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to update note'),
                status_code=500
            )

    @crm_bp.route('/notes/<int:note_id>', methods=['DELETE'])
    @jwt_required()
    @require_permission('manage_crm')
    @log_api_call('delete_note')
    @audit_log('delete', 'note')
    def delete_note(note_id):
        """Delete note."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            # Find note in same tenant
            note = Note.query.filter_by(
                id=note_id,
                tenant_id=user.tenant_id
            ).first()
            
            if not note:
                return not_found_response('note')
            
            # Check if user can edit this note (same permission as delete)
            if not note.can_be_edited_by(user):
                return error_response(
                    error_code='AUTHORIZATION_ERROR',
                    message=_('Access denied to delete this note'),
                    status_code=403
                )
            
            # Soft delete
            note.delete()
            
            logger.info("Note deleted", note_id=note.id, user_id=user.id)
            
            return success_response(
                message=_('Note deleted successfully')
            )
            
        except Exception as e:
            logger.error("Failed to delete note", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to delete note'),
                status_code=500
            )