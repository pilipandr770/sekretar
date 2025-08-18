"""PII detection and data minimization service."""
import re
import hashlib
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class PIIDetector:
    """Service for detecting and handling PII in text and data."""
    
    # PII patterns with confidence levels
    PII_PATTERNS = {
        'email': {
            'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'confidence': 'high',
            'description': 'Email address'
        },
        'phone': {
            'pattern': r'(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',
            'confidence': 'medium',
            'description': 'Phone number'
        },
        'ssn': {
            'pattern': r'\b\d{3}-?\d{2}-?\d{4}\b',
            'confidence': 'high',
            'description': 'Social Security Number'
        },
        'credit_card': {
            'pattern': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            'confidence': 'medium',
            'description': 'Credit card number'
        },
        'iban': {
            'pattern': r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b',
            'confidence': 'high',
            'description': 'IBAN number'
        },
        'ip_address': {
            'pattern': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
            'confidence': 'medium',
            'description': 'IP address'
        },
        'passport': {
            'pattern': r'\b[A-Z]{1,2}\d{6,9}\b',
            'confidence': 'medium',
            'description': 'Passport number'
        },
        'vat_number': {
            'pattern': r'\b[A-Z]{2}\d{8,12}\b',
            'confidence': 'medium',
            'description': 'VAT number'
        }
    }
    
    def __init__(self):
        """Initialize PII detector."""
        self.compiled_patterns = {}
        for pii_type, config in self.PII_PATTERNS.items():
            self.compiled_patterns[pii_type] = {
                'regex': re.compile(config['pattern'], re.IGNORECASE),
                'confidence': config['confidence'],
                'description': config['description']
            }
    
    def detect_pii_in_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect PII in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of detected PII items with type, value, confidence, and position
        """
        if not text:
            return []
        
        detected_pii = []
        
        for pii_type, config in self.compiled_patterns.items():
            matches = config['regex'].finditer(text)
            
            for match in matches:
                detected_pii.append({
                    'type': pii_type,
                    'value': match.group(),
                    'confidence': config['confidence'],
                    'description': config['description'],
                    'start': match.start(),
                    'end': match.end(),
                    'context': self._get_context(text, match.start(), match.end())
                })
        
        return detected_pii
    
    def detect_pii_in_data(self, data: Dict[str, Any], field_mapping: Optional[Dict[str, str]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect PII in structured data.
        
        Args:
            data: Dictionary of field names and values
            field_mapping: Optional mapping of field names to PII types
            
        Returns:
            Dictionary mapping field names to detected PII
        """
        field_mapping = field_mapping or {}
        detected_pii = {}
        
        for field_name, value in data.items():
            if value is None:
                continue
            
            field_pii = []
            
            # Check if field is explicitly mapped to a PII type
            if field_name in field_mapping:
                pii_type = field_mapping[field_name]
                if pii_type in self.compiled_patterns:
                    field_pii.append({
                        'type': pii_type,
                        'value': str(value),
                        'confidence': 'high',  # High confidence for explicitly mapped fields
                        'description': self.compiled_patterns[pii_type]['description'],
                        'source': 'field_mapping'
                    })
            
            # Also check content with pattern matching
            if isinstance(value, str):
                text_pii = self.detect_pii_in_text(value)
                for pii_item in text_pii:
                    pii_item['source'] = 'pattern_matching'
                    field_pii.append(pii_item)
            
            if field_pii:
                detected_pii[field_name] = field_pii
        
        return detected_pii
    
    def mask_pii_in_text(self, text: str, mask_char: str = '*', preserve_chars: int = 2) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Mask PII in text.
        
        Args:
            text: Text to mask
            mask_char: Character to use for masking
            preserve_chars: Number of characters to preserve at start/end
            
        Returns:
            Tuple of (masked_text, list_of_masked_pii)
        """
        if not text:
            return text, []
        
        detected_pii = self.detect_pii_in_text(text)
        masked_text = text
        masked_items = []
        
        # Sort by position in reverse order to avoid index shifting
        detected_pii.sort(key=lambda x: x['start'], reverse=True)
        
        for pii_item in detected_pii:
            original_value = pii_item['value']
            masked_value = self._mask_value(original_value, mask_char, preserve_chars)
            
            # Replace in text
            masked_text = (masked_text[:pii_item['start']] + 
                          masked_value + 
                          masked_text[pii_item['end']:])
            
            masked_items.append({
                'type': pii_item['type'],
                'original_value': original_value,
                'masked_value': masked_value,
                'confidence': pii_item['confidence'],
                'position': (pii_item['start'], pii_item['end'])
            })
        
        return masked_text, masked_items
    
    def anonymize_data(self, data: Dict[str, Any], field_mapping: Optional[Dict[str, str]] = None) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
        """
        Anonymize PII in structured data.
        
        Args:
            data: Data to anonymize
            field_mapping: Optional field to PII type mapping
            
        Returns:
            Tuple of (anonymized_data, anonymization_log)
        """
        anonymized_data = data.copy()
        anonymization_log = {}
        
        detected_pii = self.detect_pii_in_data(data, field_mapping)
        
        for field_name, pii_items in detected_pii.items():
            field_log = []
            
            if isinstance(data[field_name], str):
                # For string fields, mask the content
                masked_text, masked_items = self.mask_pii_in_text(data[field_name])
                anonymized_data[field_name] = masked_text
                field_log.extend(masked_items)
            else:
                # For non-string fields with detected PII, hash the value
                original_value = str(data[field_name])
                hashed_value = self._hash_value(original_value)
                anonymized_data[field_name] = f"HASHED_{hashed_value[:8]}"
                
                field_log.append({
                    'type': pii_items[0]['type'] if pii_items else 'unknown',
                    'original_value': original_value,
                    'anonymized_value': anonymized_data[field_name],
                    'method': 'hashing'
                })
            
            if field_log:
                anonymization_log[field_name] = field_log
        
        return anonymized_data, anonymization_log
    
    def _get_context(self, text: str, start: int, end: int, context_chars: int = 20) -> str:
        """Get context around detected PII."""
        context_start = max(0, start - context_chars)
        context_end = min(len(text), end + context_chars)
        
        context = text[context_start:context_end]
        
        # Mark the PII location
        pii_start = start - context_start
        pii_end = end - context_start
        
        return (context[:pii_start] + 
                '[PII]' + 
                context[pii_start:pii_end] + 
                '[/PII]' + 
                context[pii_end:])
    
    def _mask_value(self, value: str, mask_char: str = '*', preserve_chars: int = 2) -> str:
        """Mask a value while preserving some characters."""
        if len(value) <= preserve_chars * 2:
            return mask_char * len(value)
        
        preserved_start = value[:preserve_chars]
        preserved_end = value[-preserve_chars:] if preserve_chars > 0 else ''
        masked_middle = mask_char * (len(value) - preserve_chars * 2)
        
        return preserved_start + masked_middle + preserved_end
    
    def _hash_value(self, value: str) -> str:
        """Hash a value for anonymization."""
        return hashlib.sha256(value.encode()).hexdigest()
    
    def validate_pii_detection(self, text: str, expected_pii: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate PII detection accuracy (for testing).
        
        Args:
            text: Text to analyze
            expected_pii: List of expected PII items
            
        Returns:
            Validation results with precision, recall, and F1 score
        """
        detected_pii = self.detect_pii_in_text(text)
        
        # Convert to sets for comparison
        detected_set = set((item['type'], item['value']) for item in detected_pii)
        expected_set = set((item['type'], item['value']) for item in expected_pii)
        
        true_positives = len(detected_set & expected_set)
        false_positives = len(detected_set - expected_set)
        false_negatives = len(expected_set - detected_set)
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'detected_pii': detected_pii,
            'missed_pii': list(expected_set - detected_set),
            'false_detections': list(detected_set - expected_set)
        }


class DataMinimizer:
    """Service for data minimization and retention management."""
    
    def __init__(self, db_session):
        """Initialize data minimizer with database session."""
        self.db = db_session
        self.pii_detector = PIIDetector()
    
    def minimize_message_data(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Minimize PII in message data.
        
        Args:
            message_data: Message data to minimize
            
        Returns:
            Minimized message data
        """
        # Field mapping for message data
        field_mapping = {
            'sender_email': 'email',
            'sender_phone': 'phone',
            'content': None  # Will be pattern-matched
        }
        
        minimized_data, anonymization_log = self.pii_detector.anonymize_data(
            message_data, field_mapping
        )
        
        # Log PII detection if any found
        if anonymization_log:
            self._log_pii_detection(
                'inbox_messages',
                message_data.get('id'),
                anonymization_log
            )
        
        return minimized_data
    
    def minimize_contact_data(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Minimize PII in contact data.
        
        Args:
            contact_data: Contact data to minimize
            
        Returns:
            Minimized contact data
        """
        # Field mapping for contact data
        field_mapping = {
            'email': 'email',
            'phone': 'phone',
            'name': None,  # Names might contain PII patterns
            'company': None
        }
        
        minimized_data, anonymization_log = self.pii_detector.anonymize_data(
            contact_data, field_mapping
        )
        
        # Log PII detection if any found
        if anonymization_log:
            self._log_pii_detection(
                'contacts',
                contact_data.get('id'),
                anonymization_log
            )
        
        return minimized_data
    
    def check_retention_compliance(self, tenant_id: int) -> Dict[str, Any]:
        """
        Check retention compliance for a tenant.
        
        Args:
            tenant_id: Tenant ID to check
            
        Returns:
            Compliance report
        """
        from app.models.gdpr_compliance import DataRetentionPolicy
        
        policies = DataRetentionPolicy.query.filter_by(
            tenant_id=tenant_id,
            is_active=True
        ).all()
        
        compliance_report = {
            'tenant_id': tenant_id,
            'check_date': datetime.utcnow().isoformat(),
            'policies_checked': len(policies),
            'expired_data': {},
            'total_expired_records': 0
        }
        
        for policy in policies:
            expired_records = self._find_expired_records(policy)
            if expired_records:
                compliance_report['expired_data'][policy.data_type] = {
                    'policy_name': policy.name,
                    'retention_days': policy.retention_days,
                    'expired_count': len(expired_records),
                    'auto_delete': policy.auto_delete,
                    'anonymize_instead': policy.anonymize_instead,
                    'records': expired_records[:10]  # Sample of expired records
                }
                compliance_report['total_expired_records'] += len(expired_records)
        
        return compliance_report
    
    def cleanup_expired_data(self, tenant_id: int, dry_run: bool = True) -> Dict[str, Any]:
        """
        Clean up expired data according to retention policies.
        
        Args:
            tenant_id: Tenant ID
            dry_run: If True, only simulate cleanup without actual deletion
            
        Returns:
            Cleanup report
        """
        from app.models.gdpr_compliance import DataRetentionPolicy
        
        policies = DataRetentionPolicy.query.filter_by(
            tenant_id=tenant_id,
            is_active=True,
            auto_delete=True
        ).all()
        
        cleanup_report = {
            'tenant_id': tenant_id,
            'cleanup_date': datetime.utcnow().isoformat(),
            'dry_run': dry_run,
            'policies_processed': len(policies),
            'deleted_records': {},
            'anonymized_records': {},
            'errors': [],
            'total_deleted': 0,
            'total_anonymized': 0
        }
        
        for policy in policies:
            try:
                if policy.anonymize_instead:
                    result = self._anonymize_expired_records(policy, dry_run)
                    cleanup_report['anonymized_records'][policy.data_type] = result
                    cleanup_report['total_anonymized'] += result['count']
                else:
                    result = self._delete_expired_records(policy, dry_run)
                    cleanup_report['deleted_records'][policy.data_type] = result
                    cleanup_report['total_deleted'] += result['count']
            
            except Exception as e:
                error_msg = f"Error processing policy {policy.name}: {str(e)}"
                cleanup_report['errors'].append(error_msg)
                logger.error(error_msg, exc_info=True)
        
        return cleanup_report
    
    def _log_pii_detection(self, source_table: str, source_id: int, anonymization_log: Dict[str, List[Dict[str, Any]]]):
        """Log PII detection for audit purposes."""
        from app.models.gdpr_compliance import PIIDetectionLog
        
        for field_name, pii_items in anonymization_log.items():
            for pii_item in pii_items:
                try:
                    PIIDetectionLog.log_detection(
                        tenant_id=1,  # This should be passed from context
                        source_table=source_table,
                        source_id=source_id,
                        field_name=field_name,
                        pii_type=pii_item['type'],
                        confidence=pii_item.get('confidence', 'medium'),
                        action_taken='masked',
                        original_value=pii_item.get('original_value'),
                        detection_method='pattern_matching'
                    )
                except Exception as e:
                    logger.error(f"Failed to log PII detection: {e}")
    
    def _find_expired_records(self, policy) -> List[Dict[str, Any]]:
        """Find records that have expired according to policy."""
        # This would need to be implemented based on the specific table structure
        # For now, return empty list as placeholder
        return []
    
    def _delete_expired_records(self, policy, dry_run: bool) -> Dict[str, Any]:
        """Delete expired records according to policy."""
        # Placeholder implementation
        return {
            'policy_name': policy.name,
            'count': 0,
            'dry_run': dry_run
        }
    
    def _anonymize_expired_records(self, policy, dry_run: bool) -> Dict[str, Any]:
        """Anonymize expired records according to policy."""
        # Placeholder implementation
        return {
            'policy_name': policy.name,
            'count': 0,
            'dry_run': dry_run
        }