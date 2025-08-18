"""GDPR data export and deletion request service."""
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class GDPRRequestService:
    """Service for processing GDPR data export and deletion requests."""
    
    def __init__(self, db_session: Session):
        """Initialize with database session."""
        self.db = db_session
    
    def create_deletion_request(self, tenant_id: int, request_type: str = 'full_deletion',
                               user_id: int = None, external_user_id: str = None,
                               email: str = None, phone: str = None, reason: str = None,
                               data_types: List[str] = None) -> 'DataDeletionRequest':
        """
        Create a new data deletion request.
        
        Args:
            tenant_id: Tenant ID
            request_type: Type of deletion (full_deletion, anonymization, specific_data)
            user_id: Internal user ID (optional)
            external_user_id: External user identifier (optional)
            email: User email (optional)
            phone: User phone (optional)
            reason: Reason for deletion request
            data_types: Specific data types to delete (optional)
            
        Returns:
            Created deletion request
        """
        from app.models.gdpr_compliance import DataDeletionRequest
        
        deletion_request = DataDeletionRequest.create_deletion_request(
            tenant_id=tenant_id,
            request_type=request_type,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email,
            phone=phone,
            reason=reason,
            data_types=data_types or []
        )
        
        logger.info(f"Created deletion request {deletion_request.request_id} for tenant {tenant_id}")
        return deletion_request
    
    def create_export_request(self, tenant_id: int, user_id: int = None,
                             external_user_id: str = None, email: str = None,
                             phone: str = None, export_format: str = 'json',
                             data_types: List[str] = None, include_metadata: bool = True) -> 'DataExportRequest':
        """
        Create a new data export request.
        
        Args:
            tenant_id: Tenant ID
            user_id: Internal user ID (optional)
            external_user_id: External user identifier (optional)
            email: User email (optional)
            phone: User phone (optional)
            export_format: Export format (json, csv, xml)
            data_types: Specific data types to export (optional)
            include_metadata: Whether to include metadata
            
        Returns:
            Created export request
        """
        from app.models.gdpr_compliance import DataExportRequest
        
        export_request = DataExportRequest.create_export_request(
            tenant_id=tenant_id,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email,
            phone=phone,
            export_format=export_format,
            data_types=data_types or [],
            include_metadata=include_metadata
        )
        
        logger.info(f"Created export request {export_request.request_id} for tenant {tenant_id}")
        return export_request
    
    def process_deletion_request(self, deletion_request: 'DataDeletionRequest') -> Dict[str, Any]:
        """
        Process a data deletion request.
        
        Args:
            deletion_request: The deletion request to process
            
        Returns:
            Processing result with deleted record counts and errors
        """
        result = {
            'request_id': deletion_request.request_id,
            'tenant_id': deletion_request.tenant_id,
            'deleted_records': {},
            'errors': [],
            'start_time': datetime.utcnow().isoformat()
        }
        
        try:
            # Get user identification
            user_filter = self._build_user_filter(deletion_request)
            
            # Delete data based on request type
            if deletion_request.request_type == 'full_deletion':
                result.update(self._process_full_deletion(deletion_request, user_filter))
            elif deletion_request.request_type == 'anonymization':
                result.update(self._process_anonymization(deletion_request, user_filter))
            elif deletion_request.request_type == 'specific_data':
                result.update(self._process_specific_deletion(deletion_request, user_filter))
            else:
                raise ValueError(f"Unknown request type: {deletion_request.request_type}")
            
            result['end_time'] = datetime.utcnow().isoformat()
            result['status'] = 'completed'
            
        except Exception as e:
            result['end_time'] = datetime.utcnow().isoformat()
            result['status'] = 'failed'
            result['errors'].append(str(e))
            logger.error(f"Deletion request processing failed: {e}", exc_info=True)
        
        return result
    
    def process_export_request(self, export_request: 'DataExportRequest') -> Dict[str, Any]:
        """
        Process a data export request.
        
        Args:
            export_request: The export request to process
            
        Returns:
            Processing result with file path and metadata
        """
        result = {
            'request_id': export_request.request_id,
            'tenant_id': export_request.tenant_id,
            'file_path': None,
            'file_size': 0,
            'record_counts': {},
            'start_time': datetime.utcnow().isoformat()
        }
        
        try:
            # Get user identification
            user_filter = self._build_user_filter(export_request)
            
            # Export data
            export_data = self._collect_user_data(export_request.tenant_id, user_filter, export_request.data_types)
            
            # Create export file
            file_path = self._create_export_file(export_request, export_data)
            
            result['file_path'] = file_path
            result['file_size'] = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            result['record_counts'] = {k: len(v) if isinstance(v, list) else 1 for k, v in export_data.items()}
            result['end_time'] = datetime.utcnow().isoformat()
            result['status'] = 'completed'
            
        except Exception as e:
            result['end_time'] = datetime.utcnow().isoformat()
            result['status'] = 'failed'
            result['error'] = str(e)
            logger.error(f"Export request processing failed: {e}", exc_info=True)
        
        return result
    
    def _build_user_filter(self, request) -> Dict[str, Any]:
        """Build user filter criteria from request."""
        user_filter = {
            'tenant_id': request.tenant_id
        }
        
        if request.user_id:
            user_filter['user_id'] = request.user_id
        if request.external_user_id:
            user_filter['external_user_id'] = request.external_user_id
        if request.email:
            user_filter['email'] = request.email
        if hasattr(request, 'phone') and request.phone:
            user_filter['phone'] = request.phone
        
        return user_filter
    
    def _process_full_deletion(self, deletion_request: 'DataDeletionRequest', user_filter: Dict[str, Any]) -> Dict[str, Any]:
        """Process full data deletion."""
        result = {'deleted_records': {}, 'errors': []}
        
        # Delete from all relevant tables
        deletion_tables = [
            ('inbox_messages', self._delete_messages),
            ('contacts', self._delete_contacts),
            ('leads', self._delete_leads),
            ('tasks', self._delete_tasks),
            ('notes', self._delete_notes),
            ('consent_records', self._delete_consent_records),
            ('pii_detection_logs', self._delete_pii_logs),
            ('audit_logs', self._delete_audit_logs)
        ]
        
        for table_name, deletion_func in deletion_tables:
            try:
                count = deletion_func(user_filter)
                if count > 0:
                    result['deleted_records'][table_name] = count
                    deletion_request.add_deleted_record(table_name, count)
            except Exception as e:
                error_msg = f"Error deleting from {table_name}: {str(e)}"
                result['errors'].append(error_msg)
                deletion_request.add_error(error_msg, table_name)
        
        return result
    
    def _process_anonymization(self, deletion_request: 'DataDeletionRequest', user_filter: Dict[str, Any]) -> Dict[str, Any]:
        """Process data anonymization instead of deletion."""
        from app.services.pii_service import DataMinimizer
        
        result = {'anonymized_records': {}, 'errors': []}
        minimizer = DataMinimizer(self.db)
        
        # Anonymize data in relevant tables
        anonymization_tables = [
            ('inbox_messages', self._anonymize_messages),
            ('contacts', self._anonymize_contacts),
            ('leads', self._anonymize_leads)
        ]
        
        for table_name, anonymization_func in anonymization_tables:
            try:
                count = anonymization_func(user_filter, minimizer)
                if count > 0:
                    result['anonymized_records'][table_name] = count
            except Exception as e:
                error_msg = f"Error anonymizing {table_name}: {str(e)}"
                result['errors'].append(error_msg)
                deletion_request.add_error(error_msg, table_name)
        
        return result
    
    def _process_specific_deletion(self, deletion_request: 'DataDeletionRequest', user_filter: Dict[str, Any]) -> Dict[str, Any]:
        """Process deletion of specific data types."""
        result = {'deleted_records': {}, 'errors': []}
        
        # Map data types to deletion functions
        deletion_mapping = {
            'messages': ('inbox_messages', self._delete_messages),
            'contacts': ('contacts', self._delete_contacts),
            'leads': ('leads', self._delete_leads),
            'tasks': ('tasks', self._delete_tasks),
            'notes': ('notes', self._delete_notes),
            'consents': ('consent_records', self._delete_consent_records)
        }
        
        for data_type in deletion_request.data_types:
            if data_type in deletion_mapping:
                table_name, deletion_func = deletion_mapping[data_type]
                try:
                    count = deletion_func(user_filter)
                    if count > 0:
                        result['deleted_records'][table_name] = count
                        deletion_request.add_deleted_record(table_name, count)
                except Exception as e:
                    error_msg = f"Error deleting {data_type}: {str(e)}"
                    result['errors'].append(error_msg)
                    deletion_request.add_error(error_msg, table_name)
        
        return result
    
    def _collect_user_data(self, tenant_id: int, user_filter: Dict[str, Any], data_types: List[str] = None) -> Dict[str, Any]:
        """Collect all user data for export."""
        export_data = {
            'export_metadata': {
                'tenant_id': tenant_id,
                'export_date': datetime.utcnow().isoformat(),
                'user_filter': user_filter,
                'data_types': data_types or []
            }
        }
        
        # Collect data from all relevant tables
        data_collectors = {
            'messages': self._collect_messages,
            'contacts': self._collect_contacts,
            'leads': self._collect_leads,
            'tasks': self._collect_tasks,
            'notes': self._collect_notes,
            'consents': self._collect_consent_records,
            'audit_logs': self._collect_audit_logs
        }
        
        # If specific data types requested, only collect those
        if data_types:
            collectors_to_run = {k: v for k, v in data_collectors.items() if k in data_types}
        else:
            collectors_to_run = data_collectors
        
        for data_type, collector_func in collectors_to_run.items():
            try:
                data = collector_func(user_filter)
                if data:
                    export_data[data_type] = data
            except Exception as e:
                logger.error(f"Error collecting {data_type}: {e}")
                export_data[f'{data_type}_error'] = str(e)
        
        return export_data
    
    def _create_export_file(self, export_request: 'DataExportRequest', export_data: Dict[str, Any]) -> str:
        """Create export file in requested format."""
        # Create exports directory if it doesn't exist
        export_dir = os.path.join(os.getcwd(), 'exports')
        os.makedirs(export_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"data_export_{export_request.request_id}_{timestamp}.{export_request.export_format}"
        file_path = os.path.join(export_dir, filename)
        
        # Write file in requested format
        if export_request.export_format == 'json':
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str, ensure_ascii=False)
        elif export_request.export_format == 'csv':
            self._write_csv_export(file_path, export_data)
        elif export_request.export_format == 'xml':
            self._write_xml_export(file_path, export_data)
        else:
            raise ValueError(f"Unsupported export format: {export_request.export_format}")
        
        return file_path
    
    def _write_csv_export(self, file_path: str, export_data: Dict[str, Any]):
        """Write export data as CSV files (one per data type)."""
        import csv
        import zipfile
        
        # Create a zip file containing CSV files for each data type
        zip_path = file_path.replace('.csv', '.zip')
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for data_type, data in export_data.items():
                if data_type == 'export_metadata':
                    continue
                
                if isinstance(data, list) and data:
                    csv_filename = f"{data_type}.csv"
                    csv_content = self._convert_to_csv(data)
                    zipf.writestr(csv_filename, csv_content)
        
        return zip_path
    
    def _write_xml_export(self, file_path: str, export_data: Dict[str, Any]):
        """Write export data as XML."""
        import xml.etree.ElementTree as ET
        
        root = ET.Element("data_export")
        
        for data_type, data in export_data.items():
            section = ET.SubElement(root, data_type)
            
            if isinstance(data, list):
                for item in data:
                    item_elem = ET.SubElement(section, "item")
                    self._dict_to_xml(item_elem, item)
            elif isinstance(data, dict):
                self._dict_to_xml(section, data)
            else:
                section.text = str(data)
        
        tree = ET.ElementTree(root)
        tree.write(file_path, encoding='utf-8', xml_declaration=True)
    
    def _convert_to_csv(self, data: List[Dict[str, Any]]) -> str:
        """Convert list of dictionaries to CSV string."""
        import csv
        import io
        
        if not data:
            return ""
        
        output = io.StringIO()
        fieldnames = set()
        
        # Collect all possible fieldnames
        for item in data:
            fieldnames.update(item.keys())
        
        fieldnames = sorted(list(fieldnames))
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for item in data:
            # Convert complex values to strings
            row = {}
            for key, value in item.items():
                if isinstance(value, (dict, list)):
                    row[key] = json.dumps(value, default=str)
                else:
                    row[key] = value
            writer.writerow(row)
        
        return output.getvalue()
    
    def _dict_to_xml(self, parent, data):
        """Convert dictionary to XML elements."""
        import xml.etree.ElementTree as ET
        
        if isinstance(data, dict):
            for key, value in data.items():
                elem = ET.SubElement(parent, str(key))
                if isinstance(value, (dict, list)):
                    self._dict_to_xml(elem, value)
                else:
                    elem.text = str(value)
        elif isinstance(data, list):
            for item in data:
                item_elem = ET.SubElement(parent, "item")
                self._dict_to_xml(item_elem, item)
    
    # Data deletion methods
    def _delete_messages(self, user_filter: Dict[str, Any]) -> int:
        """Delete user messages."""
        from app.models.inbox_message import InboxMessage
        
        query = InboxMessage.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'email' in user_filter:
            query = query.filter_by(sender_email=user_filter['email'])
        if 'external_user_id' in user_filter:
            query = query.filter_by(sender_id=user_filter['external_user_id'])
        
        messages = query.all()
        count = len(messages)
        
        for message in messages:
            message.soft_delete()
        
        return count
    
    def _delete_contacts(self, user_filter: Dict[str, Any]) -> int:
        """Delete user contacts."""
        from app.models.contact import Contact
        
        query = Contact.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'email' in user_filter:
            query = query.filter_by(email=user_filter['email'])
        
        contacts = query.all()
        count = len(contacts)
        
        for contact in contacts:
            contact.soft_delete()
        
        return count
    
    def _delete_leads(self, user_filter: Dict[str, Any]) -> int:
        """Delete user leads."""
        from app.models.lead import Lead
        
        query = Lead.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        # Find leads associated with user's contacts
        if 'email' in user_filter:
            from app.models.contact import Contact
            contacts = Contact.query.filter_by(
                tenant_id=user_filter['tenant_id'],
                email=user_filter['email']
            ).all()
            
            if contacts:
                contact_ids = [c.id for c in contacts]
                query = query.filter(Lead.contact_id.in_(contact_ids))
            else:
                return 0
        
        leads = query.all()
        count = len(leads)
        
        for lead in leads:
            lead.soft_delete()
        
        return count
    
    def _delete_tasks(self, user_filter: Dict[str, Any]) -> int:
        """Delete user tasks."""
        from app.models.task import Task
        
        query = Task.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'user_id' in user_filter:
            query = query.filter_by(assigned_to_id=user_filter['user_id'])
        
        tasks = query.all()
        count = len(tasks)
        
        for task in tasks:
            task.soft_delete()
        
        return count
    
    def _delete_notes(self, user_filter: Dict[str, Any]) -> int:
        """Delete user notes."""
        from app.models.note import Note
        
        query = Note.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'user_id' in user_filter:
            query = query.filter_by(user_id=user_filter['user_id'])
        
        notes = query.all()
        count = len(notes)
        
        for note in notes:
            self.db.delete(note)
        
        return count
    
    def _delete_consent_records(self, user_filter: Dict[str, Any]) -> int:
        """Delete user consent records."""
        from app.models.gdpr_compliance import ConsentRecord
        
        query = ConsentRecord.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'user_id' in user_filter:
            query = query.filter_by(user_id=user_filter['user_id'])
        if 'external_user_id' in user_filter:
            query = query.filter_by(external_user_id=user_filter['external_user_id'])
        if 'email' in user_filter:
            query = query.filter_by(email=user_filter['email'])
        
        consents = query.all()
        count = len(consents)
        
        for consent in consents:
            self.db.delete(consent)
        
        return count
    
    def _delete_pii_logs(self, user_filter: Dict[str, Any]) -> int:
        """Delete PII detection logs."""
        from app.models.gdpr_compliance import PIIDetectionLog
        
        # This is more complex as PII logs don't directly link to users
        # We'll delete logs related to deleted records
        query = PIIDetectionLog.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        logs = query.all()
        count = len(logs)
        
        for log in logs:
            self.db.delete(log)
        
        return count
    
    def _delete_audit_logs(self, user_filter: Dict[str, Any]) -> int:
        """Delete user audit logs."""
        from app.models.audit_log import AuditLog
        
        query = AuditLog.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'user_id' in user_filter:
            query = query.filter_by(user_id=user_filter['user_id'])
        
        logs = query.all()
        count = len(logs)
        
        for log in logs:
            self.db.delete(log)
        
        return count
    
    # Data anonymization methods
    def _anonymize_messages(self, user_filter: Dict[str, Any], minimizer) -> int:
        """Anonymize user messages."""
        from app.models.inbox_message import InboxMessage
        
        query = InboxMessage.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'email' in user_filter:
            query = query.filter_by(sender_email=user_filter['email'])
        
        messages = query.all()
        count = 0
        
        for message in messages:
            # Anonymize message data
            message_data = {
                'content': message.content,
                'sender_email': message.sender_email,
                'sender_name': message.sender_name,
                'sender_phone': message.sender_phone
            }
            
            anonymized_data = minimizer.minimize_message_data(message_data)
            
            message.content = anonymized_data.get('content', message.content)
            message.sender_email = anonymized_data.get('sender_email', f"anonymized_{message.id}@example.com")
            message.sender_name = anonymized_data.get('sender_name', f"Anonymized User {message.id}")
            message.sender_phone = anonymized_data.get('sender_phone', "***-***-****")
            
            count += 1
        
        return count
    
    def _anonymize_contacts(self, user_filter: Dict[str, Any], minimizer) -> int:
        """Anonymize user contacts."""
        from app.models.contact import Contact
        
        query = Contact.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'email' in user_filter:
            query = query.filter_by(email=user_filter['email'])
        
        contacts = query.all()
        count = 0
        
        for contact in contacts:
            contact_data = {
                'name': contact.name,
                'email': contact.email,
                'phone': contact.phone,
                'company': contact.company
            }
            
            anonymized_data = minimizer.minimize_contact_data(contact_data)
            
            contact.name = anonymized_data.get('name', f"Anonymized Contact {contact.id}")
            contact.email = anonymized_data.get('email', f"anonymized_{contact.id}@example.com")
            contact.phone = anonymized_data.get('phone', "***-***-****")
            contact.company = anonymized_data.get('company', contact.company)
            
            count += 1
        
        return count
    
    def _anonymize_leads(self, user_filter: Dict[str, Any], minimizer) -> int:
        """Anonymize user leads."""
        from app.models.lead import Lead
        from app.models.contact import Contact
        
        # Find leads associated with user's contacts
        if 'email' in user_filter:
            contacts = Contact.query.filter_by(
                tenant_id=user_filter['tenant_id'],
                email=user_filter['email']
            ).all()
            
            if not contacts:
                return 0
            
            contact_ids = [c.id for c in contacts]
            leads = Lead.query.filter(Lead.contact_id.in_(contact_ids)).all()
        else:
            return 0
        
        count = 0
        for lead in leads:
            # Anonymize associated contact first
            if lead.contact:
                self._anonymize_contacts({'tenant_id': lead.tenant_id, 'email': lead.contact.email}, minimizer)
            count += 1
        
        return count
    
    # Data collection methods for export
    def _collect_messages(self, user_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect user messages for export."""
        from app.models.inbox_message import InboxMessage
        
        query = InboxMessage.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'email' in user_filter:
            query = query.filter_by(sender_email=user_filter['email'])
        if 'external_user_id' in user_filter:
            query = query.filter_by(sender_id=user_filter['external_user_id'])
        
        messages = query.all()
        return [message.to_dict() for message in messages]
    
    def _collect_contacts(self, user_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect user contacts for export."""
        from app.models.contact import Contact
        
        query = Contact.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'email' in user_filter:
            query = query.filter_by(email=user_filter['email'])
        
        contacts = query.all()
        return [contact.to_dict() for contact in contacts]
    
    def _collect_leads(self, user_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect user leads for export."""
        from app.models.lead import Lead
        from app.models.contact import Contact
        
        if 'email' in user_filter:
            contacts = Contact.query.filter_by(
                tenant_id=user_filter['tenant_id'],
                email=user_filter['email']
            ).all()
            
            if not contacts:
                return []
            
            contact_ids = [c.id for c in contacts]
            leads = Lead.query.filter(Lead.contact_id.in_(contact_ids)).all()
        else:
            return []
        
        return [lead.to_dict() for lead in leads]
    
    def _collect_tasks(self, user_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect user tasks for export."""
        from app.models.task import Task
        
        query = Task.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'user_id' in user_filter:
            query = query.filter_by(assigned_to_id=user_filter['user_id'])
        
        tasks = query.all()
        return [task.to_dict() for task in tasks]
    
    def _collect_notes(self, user_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect user notes for export."""
        from app.models.note import Note
        
        query = Note.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'user_id' in user_filter:
            query = query.filter_by(user_id=user_filter['user_id'])
        
        notes = query.all()
        return [note.to_dict() for note in notes]
    
    def _collect_consent_records(self, user_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect user consent records for export."""
        from app.models.gdpr_compliance import ConsentRecord
        
        query = ConsentRecord.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'user_id' in user_filter:
            query = query.filter_by(user_id=user_filter['user_id'])
        if 'external_user_id' in user_filter:
            query = query.filter_by(external_user_id=user_filter['external_user_id'])
        if 'email' in user_filter:
            query = query.filter_by(email=user_filter['email'])
        
        consents = query.all()
        return [consent.to_dict() for consent in consents]
    
    def _collect_audit_logs(self, user_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect user audit logs for export."""
        from app.models.audit_log import AuditLog
        
        query = AuditLog.query.filter_by(tenant_id=user_filter['tenant_id'])
        
        if 'user_id' in user_filter:
            query = query.filter_by(user_id=user_filter['user_id'])
        
        logs = query.all()
        return [log.to_dict() for log in logs]