"""Data retention and cleanup worker for GDPR compliance."""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from celery import current_task
from app import db
from app.workers.base import MonitoredWorker, create_task_decorator

logger = logging.getLogger(__name__)


@create_task_decorator(queue='data_retention', max_retries=2)
def cleanup_expired_data(self, tenant_id: int = None, policy_id: int = None, 
                        dry_run: bool = False, batch_size: int = 100):
    """
    Clean up expired data according to retention policies.
    
    Args:
        tenant_id: Optional tenant ID to process (if None, processes all tenants)
        policy_id: Optional specific policy ID to process
        dry_run: If True, simulate cleanup without actual changes
        batch_size: Number of records to process in each batch
    """
    from app.services.data_retention_service import DataRetentionService
    
    logger.info(f"Starting data cleanup task - tenant_id={tenant_id}, policy_id={policy_id}, dry_run={dry_run}")
    
    cleanup_report = {
        'task_id': current_task.request.id,
        'start_time': datetime.utcnow().isoformat(),
        'tenant_id': tenant_id,
        'policy_id': policy_id,
        'dry_run': dry_run,
        'batch_size': batch_size,
        'tenants_processed': 0,
        'total_deleted': 0,
        'total_anonymized': 0,
        'errors': [],
        'tenant_results': {}
    }
    
    try:
        with db.session.begin():
            retention_service = DataRetentionService(db.session)
            
            if tenant_id:
                # Process specific tenant
                tenant_result = retention_service.cleanup_expired_data(
                    tenant_id=tenant_id,
                    policy_id=policy_id,
                    dry_run=dry_run,
                    batch_size=batch_size
                )
                cleanup_report['tenant_results'][tenant_id] = tenant_result
                cleanup_report['total_deleted'] += tenant_result['total_deleted']
                cleanup_report['total_anonymized'] += tenant_result['total_anonymized']
                cleanup_report['tenants_processed'] = 1
                
            else:
                # Process all tenants
                from app.models.tenant import Tenant
                tenants = Tenant.query.filter_by(is_active=True).all()
                
                for tenant in tenants:
                    try:
                        tenant_result = retention_service.cleanup_expired_data(
                            tenant_id=tenant.id,
                            policy_id=policy_id,
                            dry_run=dry_run,
                            batch_size=batch_size
                        )
                        cleanup_report['tenant_results'][tenant.id] = tenant_result
                        cleanup_report['total_deleted'] += tenant_result['total_deleted']
                        cleanup_report['total_anonymized'] += tenant_result['total_anonymized']
                        cleanup_report['tenants_processed'] += 1
                        
                    except Exception as e:
                        error_msg = f"Error processing tenant {tenant.id}: {str(e)}"
                        cleanup_report['errors'].append(error_msg)
                        logger.error(error_msg, exc_info=True)
        
        cleanup_report['end_time'] = datetime.utcnow().isoformat()
        cleanup_report['status'] = 'completed'
        
        logger.info(f"Data cleanup completed - deleted: {cleanup_report['total_deleted']}, "
                   f"anonymized: {cleanup_report['total_anonymized']}")
        
        return cleanup_report
        
    except Exception as e:
        cleanup_report['end_time'] = datetime.utcnow().isoformat()
        cleanup_report['status'] = 'failed'
        cleanup_report['error'] = str(e)
        logger.error(f"Data cleanup task failed: {e}", exc_info=True)
        raise


@create_task_decorator(queue='data_retention', max_retries=1)
def check_expired_consents(self, tenant_id: int = None):
    """
    Check for expired consents and update their status.
    
    Args:
        tenant_id: Optional tenant ID to check (if None, checks all tenants)
    """
    from app.services.consent_service import ConsentService
    
    logger.info(f"Starting expired consent check - tenant_id={tenant_id}")
    
    check_report = {
        'task_id': current_task.request.id,
        'start_time': datetime.utcnow().isoformat(),
        'tenant_id': tenant_id,
        'tenants_processed': 0,
        'total_expired': 0,
        'errors': [],
        'tenant_results': {}
    }
    
    try:
        with db.session.begin():
            consent_service = ConsentService(db.session)
            
            if tenant_id:
                # Process specific tenant
                tenant_result = consent_service.check_expired_consents(tenant_id)
                check_report['tenant_results'][tenant_id] = tenant_result
                check_report['total_expired'] += tenant_result['expired_count']
                check_report['tenants_processed'] = 1
                
            else:
                # Process all tenants
                from app.models.tenant import Tenant
                tenants = Tenant.query.filter_by(is_active=True).all()
                
                for tenant in tenants:
                    try:
                        tenant_result = consent_service.check_expired_consents(tenant.id)
                        check_report['tenant_results'][tenant.id] = tenant_result
                        check_report['total_expired'] += tenant_result['expired_count']
                        check_report['tenants_processed'] += 1
                        
                    except Exception as e:
                        error_msg = f"Error processing tenant {tenant.id}: {str(e)}"
                        check_report['errors'].append(error_msg)
                        logger.error(error_msg, exc_info=True)
        
        check_report['end_time'] = datetime.utcnow().isoformat()
        check_report['status'] = 'completed'
        
        logger.info(f"Expired consent check completed - expired: {check_report['total_expired']}")
        
        return check_report
        
    except Exception as e:
        check_report['end_time'] = datetime.utcnow().isoformat()
        check_report['status'] = 'failed'
        check_report['error'] = str(e)
        logger.error(f"Expired consent check failed: {e}", exc_info=True)
        raise


@create_task_decorator(queue='data_retention', max_retries=2)
def process_data_deletion_request(self, request_id: str):
    """
    Process a data deletion request.
    
    Args:
        request_id: ID of the deletion request to process
    """
    from app.models.gdpr_compliance import DataDeletionRequest
    from app.services.gdpr_request_service import GDPRRequestService
    
    logger.info(f"Processing data deletion request: {request_id}")
    
    try:
        with db.session.begin():
            # Get the deletion request
            deletion_request = DataDeletionRequest.query.filter_by(
                request_id=request_id
            ).first()
            
            if not deletion_request:
                raise ValueError(f"Deletion request {request_id} not found")
            
            if deletion_request.status != 'verified':
                raise ValueError(f"Deletion request {request_id} is not verified")
            
            # Start processing
            deletion_request.start_processing()
            db.session.commit()
            
            # Process the deletion
            gdpr_service = GDPRRequestService(db.session)
            result = gdpr_service.process_deletion_request(deletion_request)
            
            # Update request with results
            deletion_request.complete_processing(
                deleted_records=result.get('deleted_records', {}),
                errors=result.get('errors', [])
            )
            
            logger.info(f"Data deletion request {request_id} completed successfully")
            return result
            
    except Exception as e:
        # Mark request as failed
        try:
            with db.session.begin():
                deletion_request = DataDeletionRequest.query.filter_by(
                    request_id=request_id
                ).first()
                if deletion_request:
                    deletion_request.add_error(f"Processing failed: {str(e)}")
                    deletion_request.status = 'failed'
                    db.session.commit()
        except Exception as update_error:
            logger.error(f"Failed to update deletion request status: {update_error}")
        
        logger.error(f"Data deletion request {request_id} failed: {e}", exc_info=True)
        raise


@create_task_decorator(queue='data_retention', max_retries=2)
def process_data_export_request(self, request_id: str):
    """
    Process a data export request.
    
    Args:
        request_id: ID of the export request to process
    """
    from app.models.gdpr_compliance import DataExportRequest
    from app.services.gdpr_request_service import GDPRRequestService
    
    logger.info(f"Processing data export request: {request_id}")
    
    try:
        with db.session.begin():
            # Get the export request
            export_request = DataExportRequest.query.filter_by(
                request_id=request_id
            ).first()
            
            if not export_request:
                raise ValueError(f"Export request {request_id} not found")
            
            if export_request.status != 'pending':
                raise ValueError(f"Export request {request_id} is not pending")
            
            # Start processing
            export_request.start_processing()
            db.session.commit()
            
            # Process the export
            gdpr_service = GDPRRequestService(db.session)
            result = gdpr_service.process_export_request(export_request)
            
            # Update request with results
            export_request.complete_processing(
                file_path=result['file_path'],
                file_size=result['file_size'],
                record_counts=result.get('record_counts', {})
            )
            
            logger.info(f"Data export request {request_id} completed successfully")
            return result
            
    except Exception as e:
        # Mark request as failed
        try:
            with db.session.begin():
                export_request = DataExportRequest.query.filter_by(
                    request_id=request_id
                ).first()
                if export_request:
                    export_request.status = 'failed'
                    db.session.commit()
        except Exception as update_error:
            logger.error(f"Failed to update export request status: {update_error}")
        
        logger.error(f"Data export request {request_id} failed: {e}", exc_info=True)
        raise


@create_task_decorator(queue='data_retention', max_retries=1)
def cleanup_expired_exports(self):
    """Clean up expired data export files."""
    from app.models.gdpr_compliance import DataExportRequest
    import os
    
    logger.info("Starting cleanup of expired data exports")
    
    cleanup_report = {
        'task_id': current_task.request.id,
        'start_time': datetime.utcnow().isoformat(),
        'expired_exports': 0,
        'files_deleted': 0,
        'errors': []
    }
    
    try:
        with db.session.begin():
            # Find expired exports
            expired_exports = DataExportRequest.query.filter(
                DataExportRequest.status == 'completed',
                DataExportRequest.expires_at < datetime.utcnow()
            ).all()
            
            for export_request in expired_exports:
                try:
                    # Delete the file if it exists
                    if export_request.file_path and os.path.exists(export_request.file_path):
                        os.remove(export_request.file_path)
                        cleanup_report['files_deleted'] += 1
                    
                    # Update status
                    export_request.status = 'expired'
                    export_request.file_path = None
                    export_request.download_token = None
                    
                    cleanup_report['expired_exports'] += 1
                    
                except Exception as e:
                    error_msg = f"Error cleaning up export {export_request.request_id}: {str(e)}"
                    cleanup_report['errors'].append(error_msg)
                    logger.error(error_msg)
        
        cleanup_report['end_time'] = datetime.utcnow().isoformat()
        cleanup_report['status'] = 'completed'
        
        logger.info(f"Export cleanup completed - expired: {cleanup_report['expired_exports']}, "
                   f"files deleted: {cleanup_report['files_deleted']}")
        
        return cleanup_report
        
    except Exception as e:
        cleanup_report['end_time'] = datetime.utcnow().isoformat()
        cleanup_report['status'] = 'failed'
        cleanup_report['error'] = str(e)
        logger.error(f"Export cleanup failed: {e}", exc_info=True)
        raise


@create_task_decorator(queue='data_retention', max_retries=1)
def generate_retention_report(self, tenant_id: int = None):
    """
    Generate data retention compliance report.
    
    Args:
        tenant_id: Optional tenant ID (if None, generates report for all tenants)
    """
    from app.services.data_retention_service import DataRetentionService
    
    logger.info(f"Generating retention report - tenant_id={tenant_id}")
    
    try:
        with db.session.begin():
            retention_service = DataRetentionService(db.session)
            
            if tenant_id:
                # Generate report for specific tenant
                report = retention_service.find_expired_data(tenant_id)
            else:
                # Generate report for all tenants
                from app.models.tenant import Tenant
                tenants = Tenant.query.filter_by(is_active=True).all()
                
                report = {
                    'report_date': datetime.utcnow().isoformat(),
                    'tenant_count': len(tenants),
                    'total_expired_records': 0,
                    'tenant_reports': {}
                }
                
                for tenant in tenants:
                    tenant_report = retention_service.find_expired_data(tenant.id)
                    report['tenant_reports'][tenant.id] = tenant_report
                    report['total_expired_records'] += tenant_report['total_expired_records']
        
        logger.info(f"Retention report generated - total expired records: {report.get('total_expired_records', 0)}")
        return report
        
    except Exception as e:
        logger.error(f"Retention report generation failed: {e}", exc_info=True)
        raise


# Periodic task scheduling (to be configured in celery beat)
def schedule_periodic_tasks():
    """Schedule periodic data retention tasks."""
    from celery_app import celery
    
    # Daily cleanup of expired data
    celery.conf.beat_schedule.update({
        'daily-data-cleanup': {
            'task': 'app.workers.data_retention.cleanup_expired_data',
            'schedule': 86400.0,  # 24 hours
            'kwargs': {'dry_run': False, 'batch_size': 500}
        },
        'daily-consent-check': {
            'task': 'app.workers.data_retention.check_expired_consents',
            'schedule': 86400.0,  # 24 hours
        },
        'weekly-export-cleanup': {
            'task': 'app.workers.data_retention.cleanup_expired_exports',
            'schedule': 604800.0,  # 7 days
        },
        'weekly-retention-report': {
            'task': 'app.workers.data_retention.generate_retention_report',
            'schedule': 604800.0,  # 7 days
        }
    })