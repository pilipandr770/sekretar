"""CRM Stage management API endpoints."""
from flask import request, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from sqlalchemy import and_, or_, desc
from app.models.pipeline import Pipeline, Stage
from app.utils.decorators import (
    require_json, require_permission, 
    log_api_call, audit_log
)
from app.utils.response import (
    success_response, error_response, validation_error_response,
    not_found_response, conflict_response
)
import structlog

logger = structlog.get_logger()


def register_stage_endpoints(crm_bp):
    """Register stage-related endpoints."""
    
    @crm_bp.route('/pipelines/<int:pipeline_id>/stages', methods=['GET'])
    @jwt_required()
    @require_permission('view_crm')
    @log_api_call('list_pipeline_stages')
    def list_pipeline_stages(pipeline_id):
        """List stages for a specific pipeline."""
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
            
            # Get ordered stages
            stages = pipeline.get_ordered_stages()
            
            return success_response(
                message=_('Pipeline stages retrieved successfully'),
                data=[stage.to_dict() for stage in stages]
            )
            
        except Exception as e:
            logger.error("Failed to list pipeline stages", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to retrieve pipeline stages'),
                status_code=500
            )

    @crm_bp.route('/pipelines/<int:pipeline_id>/stages', methods=['POST'])
    @jwt_required()
    @require_permission('manage_crm')
    @require_json(['name'])
    @log_api_call('create_pipeline_stage')
    @audit_log('create', 'stage')
    def create_pipeline_stage(pipeline_id):
        """Create new stage in pipeline."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            tenant_id = user.tenant_id
            data = request.get_json()
            
            # Find pipeline in same tenant
            pipeline = Pipeline.query.filter_by(
                id=pipeline_id,
                tenant_id=tenant_id
            ).first()
            
            if not pipeline:
                return not_found_response('pipeline')
            
            name = data['name'].strip()
            if not name:
                return validation_error_response({
                    'name': [_('Stage name is required')]
                })
            
            # Check for duplicate stage name in pipeline
            existing_stage = pipeline.get_stage_by_name(name)
            if existing_stage:
                return conflict_response(_('Stage with this name already exists in pipeline'))
            
            # Create stage
            stage = Stage.create(
                tenant_id=tenant_id,
                pipeline_id=pipeline_id,
                name=name,
                description=data.get('description', ''),
                color=data.get('color', '#3498db'),
                position=len(pipeline.stages),
                is_closed=data.get('is_closed', False),
                is_won=data.get('is_won', False),
                auto_actions=data.get('auto_actions', {})
            )
            
            # Update pipeline stages order
            if pipeline.stages_order is None:
                pipeline.stages_order = []
            pipeline.stages_order.append(stage.id)
            pipeline.save()
            
            logger.info("Stage created", stage_id=stage.id, pipeline_id=pipeline_id, user_id=user.id)
            
            return success_response(
                message=_('Stage created successfully'),
                data=stage.to_dict(),
                status_code=201
            )
            
        except Exception as e:
            logger.error("Failed to create stage", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to create stage'),
                status_code=500
            )

    @crm_bp.route('/stages/<int:stage_id>', methods=['GET'])
    @jwt_required()
    @require_permission('view_crm')
    @log_api_call('get_stage')
    def get_stage(stage_id):
        """Get specific stage."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            # Find stage in same tenant
            stage = Stage.query.filter_by(
                id=stage_id,
                tenant_id=user.tenant_id
            ).first()
            
            if not stage:
                return not_found_response('stage')
            
            return success_response(
                message=_('Stage retrieved successfully'),
                data=stage.to_dict()
            )
            
        except Exception as e:
            logger.error("Failed to get stage", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to retrieve stage'),
                status_code=500
            )

    @crm_bp.route('/stages/<int:stage_id>', methods=['PUT'])
    @jwt_required()
    @require_permission('manage_crm')
    @require_json()
    @log_api_call('update_stage')
    @audit_log('update', 'stage')
    def update_stage(stage_id):
        """Update stage."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            tenant_id = user.tenant_id
            data = request.get_json()
            
            # Find stage in same tenant
            stage = Stage.query.filter_by(
                id=stage_id,
                tenant_id=tenant_id
            ).first()
            
            if not stage:
                return not_found_response('stage')
            
            # Check for duplicate stage name if name is being changed
            if data.get('name') and data['name'] != stage.name:
                existing_stage = stage.pipeline.get_stage_by_name(data['name'])
                if existing_stage:
                    return conflict_response(_('Stage with this name already exists in pipeline'))
            
            # Fields that can be updated
            updatable_fields = [
                'name', 'description', 'color', 'is_closed', 'is_won', 'auto_actions'
            ]
            
            for field in updatable_fields:
                if field in data:
                    if field == 'name' and not data[field].strip():
                        return validation_error_response({
                            'name': [_('Stage name is required')]
                        })
                    
                    setattr(stage, field, data[field])
            
            stage.save()
            
            logger.info("Stage updated", stage_id=stage.id, user_id=user.id)
            
            return success_response(
                message=_('Stage updated successfully'),
                data=stage.to_dict()
            )
            
        except Exception as e:
            logger.error("Failed to update stage", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to update stage'),
                status_code=500
            )

    @crm_bp.route('/stages/<int:stage_id>', methods=['DELETE'])
    @jwt_required()
    @require_permission('manage_crm')
    @log_api_call('delete_stage')
    @audit_log('delete', 'stage')
    def delete_stage(stage_id):
        """Delete stage."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return not_found_response('tenant')
            
            # Find stage in same tenant
            stage = Stage.query.filter_by(
                id=stage_id,
                tenant_id=user.tenant_id
            ).first()
            
            if not stage:
                return not_found_response('stage')
            
            # Check if stage has leads
            if stage.leads:
                return error_response(
                    error_code='VALIDATION_ERROR',
                    message=_('Cannot delete stage with associated leads'),
                    status_code=400
                )
            
            # Remove from pipeline stages order
            pipeline = stage.pipeline
            if pipeline.stages_order and stage.id in pipeline.stages_order:
                pipeline.stages_order.remove(stage.id)
                pipeline.save()
            
            # Soft delete
            stage.delete()
            
            logger.info("Stage deleted", stage_id=stage.id, user_id=user.id)
            
            return success_response(
                message=_('Stage deleted successfully')
            )
            
        except Exception as e:
            logger.error("Failed to delete stage", error=str(e), exc_info=True)
            return error_response(
                error_code='INTERNAL_ERROR',
                message=_('Failed to delete stage'),
                status_code=500
            )