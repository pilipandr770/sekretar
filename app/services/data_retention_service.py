"""Data retention and cleanup service for GDPR compliance."""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import text, and_, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DataRetentionService:
    """Service for managing data retention and automated cleanup."""
    
    def __init__(self, db_session: Session):
        """Initialize with database session."""
        self.db = db_session
    
    def create_retention_policy(self, tenant_id: int, name: str, data_type: str, 
                               table_name: str, retention_days: int, 
                               auto_delete: bool = True, anonymize_instead: bool = False,
                               legal_basis: str = None, description: str = None,
                               config: Dict[str, Any] = None) -> 'DataRetentionPolicy':
        """
        Create a new data retention policy.
        
        Args:
            tenant_id: Tenant ID
            name: Policy name
            data_type: Type of data (messages, contacts, documents, etc.)
            table_name: Database table name
            retention_days: Days to retain data
            auto_delete: Whether to automatically delete expired data
            anonymize_instead: Whether to anonymize instead of delete
            legal_basis: Legal basis for retention
            description: Policy description
            config: Additional configuration
            
        Returns:
            Created retention policy
        """
        from app.models.gdpr_compliance import DataRetentionPolicy
        
        policy = DataRetentionPolicy.create(
            tenant_id=tenant_id,
            name=name,
            description=description,
            data_type=data_type,
            table_name=table_name,
            retention_days=retention_days,
            auto_delete=auto_delete,
            anonymize_instead=anonymize_instead,
            legal_basis=legal_basis,
            config=config or {}
        )
        
        logger.info(f"Created retention policy '{name}' for tenant {tenant_id}")
        return policy
    
    def get_tenant_policies(self, tenant_id: int, active_only: bool = True) -> List['DataRetentionPolicy']:
        """Get all retention policies for a tenant."""
        from app.models.gdpr_compliance import DataRetentionPolicy
        
        query = DataRetentionPolicy.query.filter_by(tenant_id=tenant_id)
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        return query.all()
    
    def find_expired_data(self, tenant_id: int, policy_id: int = None) -> Dict[str, Any]:
        """
        Find data that has expired according to retention policies.
        
        Args:
            tenant_id: Tenant ID
            policy_id: Optional specific policy ID
            
        Returns:
            Report of expired data
        """
        from app.models.gdpr_compliance import DataRetentionPolicy
        
        query = DataRetentionPolicy.query.filter_by(tenant_id=tenant_id, is_active=True)
        
        if policy_id:
            query = query.filter_by(id=policy_id)
        
        policies = query.all()
        
        expired_data_report = {
            'tenant_id': tenant_id,
            'scan_date': datetime.utcnow().isoformat(),
            'policies_scanned': len(policies),
            'expired_data': {},
            'total_expired_records': 0
        }
        
        for policy in policies:
            expired_records = self._find_expired_records_for_policy(policy)
            
            if expired_records:
                expired_data_report['expired_data'][policy.data_type] = {
                    'policy_id': policy.id,
                    'policy_name': policy.name,
                    'table_name': policy.table_name,
                    'retention_days': policy.retention_days,
                    'expired_count': len(expired_records),
                    'auto_delete': policy.auto_delete,
                    'anonymize_instead': policy.anonymize_instead,
                    'sample_records': expired_records[:5]  # Sample for review
                }
                expired_data_report['total_expired_records'] += len(expired_records)
        
        return expired_data_report
    
    def cleanup_expired_data(self, tenant_id: int, policy_id: int = None, 
                           dry_run: bool = True, batch_size: int = 100) -> Dict[str, Any]:
        """
        Clean up expired data according to retention policies.
        
        Args:
            tenant_id: Tenant ID
            policy_id: Optional specific policy ID
            dry_run: If True, simulate cleanup without actual changes
            batch_size: Number of records to process in each batch
            
        Returns:
            Cleanup report
        """
        from app.models.gdpr_compliance import DataRetentionPolicy
        
        query = DataRetentionPolicy.query.filter_by(
            tenant_id=tenant_id, 
            is_active=True,
            auto_delete=True
        )
        
        if policy_id:
            query = query.filter_by(id=policy_id)
        
        policies = query.all()
        
        cleanup_report = {
            'tenant_id': tenant_id,
            'cleanup_date': datetime.utcnow().isoformat(),
            'dry_run': dry_run,
            'batch_size': batch_size,
            'policies_processed': len(policies),
            'results': {},
            'errors': [],
            'total_deleted': 0,
            'total_anonymized': 0
        }
        
        for policy in policies:
            try:
                if policy.anonymize_instead:
                    result = self._anonymize_expired_data(policy, dry_run, batch_size)
                    cleanup_report['total_anonymized'] += result['processed_count']
                else:
                    result = self._delete_expired_data(policy, dry_run, batch_size)
                    cleanup_report['total_deleted'] += result['processed_count']
                
                cleanup_report['results'][policy.data_type] = result
                
            except Exception as e:
                error_msg = f"Error processing policy {policy.name}: {str(e)}"
                cleanup_report['errors'].append(error_msg)
                logger.error(error_msg, exc_info=True)
        
        return cleanup_report
    
    def create_default_policies(self, tenant_id: int) -> List['DataRetentionPolicy']:
        """
        Create default retention policies for a new tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            List of created policies
        """
        default_policies = [
            {
                'name': 'Message Retention',
                'data_type': 'messages',
                'table_name': 'inbox_messages',
                'retention_days': 2555,  # 7 years for business communications
                'legal_basis': 'legitimate_interest',
                'description': 'Retain customer messages for business purposes'
            },
            {
                'name': 'Contact Data Retention',
                'data_type': 'contacts',
                'table_name': 'contacts',
                'retention_days': 1095,  # 3 years
                'legal_basis': 'consent',
                'description': 'Retain contact information with consent'
            },
            {
                'name': 'Lead Data Retention',
                'data_type': 'leads',
                'table_name': 'leads',
                'retention_days': 1825,  # 5 years
                'legal_basis': 'legitimate_interest',
                'description': 'Retain lead information for sales tracking'
            },
            {
                'name': 'Document Retention',
                'data_type': 'documents',
                'table_name': 'documents',
                'retention_days': 2555,  # 7 years
                'legal_basis': 'legitimate_interest',
                'description': 'Retain uploaded documents for knowledge base'
            },
            {
                'name': 'Audit Log Retention',
                'data_type': 'audit_logs',
                'table_name': 'audit_logs',
                'retention_days': 2555,  # 7 years for compliance
                'legal_basis': 'legal_obligation',
                'description': 'Retain audit logs for compliance requirements'
            },
            {
                'name': 'PII Detection Log Retention',
                'data_type': 'pii_logs',
                'table_name': 'pii_detection_logs',
                'retention_days': 1095,  # 3 years
                'legal_basis': 'legal_obligation',
                'description': 'Retain PII detection logs for compliance'
            }
        ]
        
        created_policies = []
        
        for policy_config in default_policies:
            try:
                policy = self.create_retention_policy(
                    tenant_id=tenant_id,
                    **policy_config
                )
                created_policies.append(policy)
            except Exception as e:
                logger.error(f"Failed to create default policy {policy_config['name']}: {e}")
        
        logger.info(f"Created {len(created_policies)} default retention policies for tenant {tenant_id}")
        return created_policies
    
    def _find_expired_records_for_policy(self, policy: 'DataRetentionPolicy') -> List[Dict[str, Any]]:
        """Find expired records for a specific policy."""
        cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)
        
        # Build query based on table name
        table_queries = {
            'inbox_messages': self._find_expired_messages,
            'contacts': self._find_expired_contacts,
            'leads': self._find_expired_leads,
            'documents': self._find_expired_documents,
            'audit_logs': self._find_expired_audit_logs,
            'pii_detection_logs': self._find_expired_pii_logs
        }
        
        finder_func = table_queries.get(policy.table_name)
        if finder_func:
            return finder_func(policy.tenant_id, cutoff_date)
        else:
            logger.warning(f"No finder function for table {policy.table_name}")
            return []
    
    def _find_expired_messages(self, tenant_id: int, cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Find expired inbox messages."""
        from app.models.inbox_message import InboxMessage
        
        expired_messages = InboxMessage.query.filter(
            and_(
                InboxMessage.tenant_id == tenant_id,
                InboxMessage.created_at < cutoff_date,
                InboxMessage.deleted_at.is_(None)  # Not already soft deleted
            )
        ).all()
        
        return [
            {
                'id': msg.id,
                'created_at': msg.created_at.isoformat(),
                'sender_id': msg.sender_id,
                'content_preview': msg.content[:50] + '...' if msg.content and len(msg.content) > 50 else msg.content
            }
            for msg in expired_messages
        ]
    
    def _find_expired_contacts(self, tenant_id: int, cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Find expired contacts."""
        from app.models.contact import Contact
        
        expired_contacts = Contact.query.filter(
            and_(
                Contact.tenant_id == tenant_id,
                Contact.created_at < cutoff_date,
                Contact.deleted_at.is_(None)
            )
        ).all()
        
        return [
            {
                'id': contact.id,
                'created_at': contact.created_at.isoformat(),
                'name': contact.name,
                'email': contact.email
            }
            for contact in expired_contacts
        ]
    
    def _find_expired_leads(self, tenant_id: int, cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Find expired leads."""
        from app.models.lead import Lead
        
        expired_leads = Lead.query.filter(
            and_(
                Lead.tenant_id == tenant_id,
                Lead.created_at < cutoff_date,
                Lead.deleted_at.is_(None)
            )
        ).all()
        
        return [
            {
                'id': lead.id,
                'created_at': lead.created_at.isoformat(),
                'status': lead.status,
                'value': lead.value
            }
            for lead in expired_leads
        ]
    
    def _find_expired_documents(self, tenant_id: int, cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Find expired documents."""
        from app.models.knowledge import Document
        
        expired_docs = Document.query.join(Document.source).filter(
            and_(
                Document.source.has(tenant_id=tenant_id),
                Document.created_at < cutoff_date
            )
        ).all()
        
        return [
            {
                'id': doc.id,
                'created_at': doc.created_at.isoformat(),
                'title': doc.title,
                'source_id': doc.source_id
            }
            for doc in expired_docs
        ]
    
    def _find_expired_audit_logs(self, tenant_id: int, cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Find expired audit logs."""
        from app.models.audit_log import AuditLog
        
        expired_logs = AuditLog.query.filter(
            and_(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at < cutoff_date
            )
        ).all()
        
        return [
            {
                'id': log.id,
                'created_at': log.created_at.isoformat(),
                'action': log.action,
                'resource_type': log.resource_type
            }
            for log in expired_logs
        ]
    
    def _find_expired_pii_logs(self, tenant_id: int, cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Find expired PII detection logs."""
        from app.models.gdpr_compliance import PIIDetectionLog
        
        expired_logs = PIIDetectionLog.query.filter(
            and_(
                PIIDetectionLog.tenant_id == tenant_id,
                PIIDetectionLog.created_at < cutoff_date
            )
        ).all()
        
        return [
            {
                'id': log.id,
                'created_at': log.created_at.isoformat(),
                'pii_type': log.pii_type,
                'source_table': log.source_table
            }
            for log in expired_logs
        ]
    
    def _delete_expired_data(self, policy: 'DataRetentionPolicy', dry_run: bool, batch_size: int) -> Dict[str, Any]:
        """Delete expired data for a policy."""
        cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)
        
        result = {
            'policy_name': policy.name,
            'table_name': policy.table_name,
            'cutoff_date': cutoff_date.isoformat(),
            'processed_count': 0,
            'batch_count': 0,
            'dry_run': dry_run,
            'errors': []
        }
        
        # Get deletion function for table
        deletion_functions = {
            'inbox_messages': self._delete_expired_messages,
            'contacts': self._delete_expired_contacts,
            'leads': self._delete_expired_leads,
            'documents': self._delete_expired_documents,
            'audit_logs': self._delete_expired_audit_logs,
            'pii_detection_logs': self._delete_expired_pii_logs
        }
        
        deletion_func = deletion_functions.get(policy.table_name)
        if not deletion_func:
            result['errors'].append(f"No deletion function for table {policy.table_name}")
            return result
        
        try:
            processed_count = deletion_func(policy.tenant_id, cutoff_date, dry_run, batch_size)
            result['processed_count'] = processed_count
            result['batch_count'] = (processed_count + batch_size - 1) // batch_size
            
        except Exception as e:
            error_msg = f"Error deleting data: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return result
    
    def _anonymize_expired_data(self, policy: 'DataRetentionPolicy', dry_run: bool, batch_size: int) -> Dict[str, Any]:
        """Anonymize expired data for a policy."""
        cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)
        
        result = {
            'policy_name': policy.name,
            'table_name': policy.table_name,
            'cutoff_date': cutoff_date.isoformat(),
            'processed_count': 0,
            'batch_count': 0,
            'dry_run': dry_run,
            'errors': []
        }
        
        # Get anonymization function for table
        anonymization_functions = {
            'inbox_messages': self._anonymize_expired_messages,
            'contacts': self._anonymize_expired_contacts,
            'leads': self._anonymize_expired_leads
        }
        
        anonymization_func = anonymization_functions.get(policy.table_name)
        if not anonymization_func:
            result['errors'].append(f"No anonymization function for table {policy.table_name}")
            return result
        
        try:
            processed_count = anonymization_func(policy.tenant_id, cutoff_date, dry_run, batch_size)
            result['processed_count'] = processed_count
            result['batch_count'] = (processed_count + batch_size - 1) // batch_size
            
        except Exception as e:
            error_msg = f"Error anonymizing data: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return result
    
    def _delete_expired_messages(self, tenant_id: int, cutoff_date: datetime, dry_run: bool, batch_size: int) -> int:
        """Delete expired messages."""
        from app.models.inbox_message import InboxMessage
        
        if dry_run:
            count = InboxMessage.query.filter(
                and_(
                    InboxMessage.tenant_id == tenant_id,
                    InboxMessage.created_at < cutoff_date,
                    InboxMessage.deleted_at.is_(None)
                )
            ).count()
            return count
        
        # Use soft delete for messages
        expired_messages = InboxMessage.query.filter(
            and_(
                InboxMessage.tenant_id == tenant_id,
                InboxMessage.created_at < cutoff_date,
                InboxMessage.deleted_at.is_(None)
            )
        ).limit(batch_size).all()
        
        count = 0
        for message in expired_messages:
            message.soft_delete()
            count += 1
        
        if expired_messages:
            self.db.commit()
        
        return count
    
    def _delete_expired_contacts(self, tenant_id: int, cutoff_date: datetime, dry_run: bool, batch_size: int) -> int:
        """Delete expired contacts."""
        from app.models.contact import Contact
        
        if dry_run:
            count = Contact.query.filter(
                and_(
                    Contact.tenant_id == tenant_id,
                    Contact.created_at < cutoff_date,
                    Contact.deleted_at.is_(None)
                )
            ).count()
            return count
        
        expired_contacts = Contact.query.filter(
            and_(
                Contact.tenant_id == tenant_id,
                Contact.created_at < cutoff_date,
                Contact.deleted_at.is_(None)
            )
        ).limit(batch_size).all()
        
        count = 0
        for contact in expired_contacts:
            contact.soft_delete()
            count += 1
        
        if expired_contacts:
            self.db.commit()
        
        return count
    
    def _delete_expired_leads(self, tenant_id: int, cutoff_date: datetime, dry_run: bool, batch_size: int) -> int:
        """Delete expired leads."""
        from app.models.lead import Lead
        
        if dry_run:
            count = Lead.query.filter(
                and_(
                    Lead.tenant_id == tenant_id,
                    Lead.created_at < cutoff_date,
                    Lead.deleted_at.is_(None)
                )
            ).count()
            return count
        
        expired_leads = Lead.query.filter(
            and_(
                Lead.tenant_id == tenant_id,
                Lead.created_at < cutoff_date,
                Lead.deleted_at.is_(None)
            )
        ).limit(batch_size).all()
        
        count = 0
        for lead in expired_leads:
            lead.soft_delete()
            count += 1
        
        if expired_leads:
            self.db.commit()
        
        return count
    
    def _delete_expired_documents(self, tenant_id: int, cutoff_date: datetime, dry_run: bool, batch_size: int) -> int:
        """Delete expired documents."""
        from app.models.knowledge import Document
        
        if dry_run:
            count = Document.query.join(Document.source).filter(
                and_(
                    Document.source.has(tenant_id=tenant_id),
                    Document.created_at < cutoff_date
                )
            ).count()
            return count
        
        # Hard delete documents as they don't have soft delete
        expired_docs = Document.query.join(Document.source).filter(
            and_(
                Document.source.has(tenant_id=tenant_id),
                Document.created_at < cutoff_date
            )
        ).limit(batch_size).all()
        
        count = 0
        for doc in expired_docs:
            self.db.delete(doc)
            count += 1
        
        if expired_docs:
            self.db.commit()
        
        return count
    
    def _delete_expired_audit_logs(self, tenant_id: int, cutoff_date: datetime, dry_run: bool, batch_size: int) -> int:
        """Delete expired audit logs."""
        from app.models.audit_log import AuditLog
        
        if dry_run:
            count = AuditLog.query.filter(
                and_(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.created_at < cutoff_date
                )
            ).count()
            return count
        
        # Hard delete audit logs
        expired_logs = AuditLog.query.filter(
            and_(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at < cutoff_date
            )
        ).limit(batch_size).all()
        
        count = 0
        for log in expired_logs:
            self.db.delete(log)
            count += 1
        
        if expired_logs:
            self.db.commit()
        
        return count
    
    def _delete_expired_pii_logs(self, tenant_id: int, cutoff_date: datetime, dry_run: bool, batch_size: int) -> int:
        """Delete expired PII detection logs."""
        from app.models.gdpr_compliance import PIIDetectionLog
        
        if dry_run:
            count = PIIDetectionLog.query.filter(
                and_(
                    PIIDetectionLog.tenant_id == tenant_id,
                    PIIDetectionLog.created_at < cutoff_date
                )
            ).count()
            return count
        
        expired_logs = PIIDetectionLog.query.filter(
            and_(
                PIIDetectionLog.tenant_id == tenant_id,
                PIIDetectionLog.created_at < cutoff_date
            )
        ).limit(batch_size).all()
        
        count = 0
        for log in expired_logs:
            self.db.delete(log)
            count += 1
        
        if expired_logs:
            self.db.commit()
        
        return count
    
    def _anonymize_expired_messages(self, tenant_id: int, cutoff_date: datetime, dry_run: bool, batch_size: int) -> int:
        """Anonymize expired messages."""
        from app.models.inbox_message import InboxMessage
        from app.services.pii_service import PIIDetector
        
        if dry_run:
            count = InboxMessage.query.filter(
                and_(
                    InboxMessage.tenant_id == tenant_id,
                    InboxMessage.created_at < cutoff_date,
                    InboxMessage.deleted_at.is_(None)
                )
            ).count()
            return count
        
        pii_detector = PIIDetector()
        expired_messages = InboxMessage.query.filter(
            and_(
                InboxMessage.tenant_id == tenant_id,
                InboxMessage.created_at < cutoff_date,
                InboxMessage.deleted_at.is_(None)
            )
        ).limit(batch_size).all()
        
        count = 0
        for message in expired_messages:
            # Anonymize PII in message content
            if message.content:
                anonymized_content, _ = pii_detector.mask_pii_in_text(message.content)
                message.content = anonymized_content
            
            # Anonymize sender information
            if message.sender_email:
                message.sender_email = f"anonymized_{message.id}@example.com"
            if message.sender_phone:
                message.sender_phone = "***-***-****"
            if message.sender_name:
                message.sender_name = f"Anonymized User {message.id}"
            
            count += 1
        
        if expired_messages:
            self.db.commit()
        
        return count
    
    def _anonymize_expired_contacts(self, tenant_id: int, cutoff_date: datetime, dry_run: bool, batch_size: int) -> int:
        """Anonymize expired contacts."""
        from app.models.contact import Contact
        
        if dry_run:
            count = Contact.query.filter(
                and_(
                    Contact.tenant_id == tenant_id,
                    Contact.created_at < cutoff_date,
                    Contact.deleted_at.is_(None)
                )
            ).count()
            return count
        
        expired_contacts = Contact.query.filter(
            and_(
                Contact.tenant_id == tenant_id,
                Contact.created_at < cutoff_date,
                Contact.deleted_at.is_(None)
            )
        ).limit(batch_size).all()
        
        count = 0
        for contact in expired_contacts:
            # Anonymize contact information
            if contact.email:
                contact.email = f"anonymized_{contact.id}@example.com"
            if contact.phone:
                contact.phone = "***-***-****"
            if contact.name:
                contact.name = f"Anonymized Contact {contact.id}"
            
            count += 1
        
        if expired_contacts:
            self.db.commit()
        
        return count
    
    def _anonymize_expired_leads(self, tenant_id: int, cutoff_date: datetime, dry_run: bool, batch_size: int) -> int:
        """Anonymize expired leads."""
        from app.models.lead import Lead
        
        if dry_run:
            count = Lead.query.filter(
                and_(
                    Lead.tenant_id == tenant_id,
                    Lead.created_at < cutoff_date,
                    Lead.deleted_at.is_(None)
                )
            ).count()
            return count
        
        expired_leads = Lead.query.filter(
            and_(
                Lead.tenant_id == tenant_id,
                Lead.created_at < cutoff_date,
                Lead.deleted_at.is_(None)
            )
        ).limit(batch_size).all()
        
        count = 0
        for lead in expired_leads:
            # Anonymize lead information while preserving business value
            if hasattr(lead, 'contact') and lead.contact:
                if lead.contact.email:
                    lead.contact.email = f"anonymized_{lead.contact.id}@example.com"
                if lead.contact.phone:
                    lead.contact.phone = "***-***-****"
                if lead.contact.name:
                    lead.contact.name = f"Anonymized Lead {lead.id}"
            
            count += 1
        
        if expired_leads:
            self.db.commit()
        
        return count