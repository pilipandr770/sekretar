"""Consent management service for GDPR compliance."""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ConsentService:
    """Service for managing user consent for GDPR compliance."""
    
    def __init__(self, db_session: Session):
        """Initialize with database session."""
        self.db = db_session
    
    def grant_consent(self, tenant_id: int, consent_type: str, purpose: str,
                     user_id: int = None, external_user_id: str = None, 
                     email: str = None, phone: str = None,
                     legal_basis: str = None, expires_at: datetime = None,
                     source: str = None, ip_address: str = None, 
                     user_agent: str = None, evidence: Dict[str, Any] = None) -> 'ConsentRecord':
        """
        Grant consent for a user.
        
        Args:
            tenant_id: Tenant ID
            consent_type: Type of consent (marketing, analytics, etc.)
            purpose: Purpose of data processing
            user_id: Internal user ID (optional)
            external_user_id: External user identifier (optional)
            email: User email (optional)
            phone: User phone (optional)
            legal_basis: Legal basis for processing
            expires_at: When consent expires (optional)
            source: Source of consent (web, telegram, etc.)
            ip_address: IP address when consent was given
            user_agent: User agent when consent was given
            evidence: Additional evidence of consent
            
        Returns:
            Created consent record
        """
        from app.models.gdpr_compliance import ConsentRecord, ConsentType
        
        # Convert string to enum
        try:
            consent_type_enum = ConsentType(consent_type)
        except ValueError:
            raise ValueError(f"Invalid consent type: {consent_type}")
        
        # Check if there's already an active consent record
        existing_consent = self.get_user_consent(
            tenant_id=tenant_id,
            consent_type=consent_type,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email
        )
        
        # If there's an existing valid consent, update it
        if existing_consent and existing_consent.is_valid():
            logger.info(f"Updating existing consent record {existing_consent.id}")
            consent_record = existing_consent
        else:
            # Create new consent record
            consent_record = ConsentRecord.create(
                tenant_id=tenant_id,
                user_id=user_id,
                external_user_id=external_user_id,
                email=email,
                phone=phone,
                consent_type=consent_type_enum,
                purpose=purpose,
                legal_basis=legal_basis,
                expires_at=expires_at
            )
        
        # Grant the consent
        consent_record.grant_consent(
            source=source,
            ip_address=ip_address,
            user_agent=user_agent,
            evidence=evidence
        )
        
        consent_record.save()
        
        logger.info(f"Granted {consent_type} consent for tenant {tenant_id}")
        return consent_record
    
    def withdraw_consent(self, tenant_id: int, consent_type: str,
                        user_id: int = None, external_user_id: str = None,
                        email: str = None, reason: str = None) -> bool:
        """
        Withdraw consent for a user.
        
        Args:
            tenant_id: Tenant ID
            consent_type: Type of consent to withdraw
            user_id: Internal user ID (optional)
            external_user_id: External user identifier (optional)
            email: User email (optional)
            reason: Reason for withdrawal (optional)
            
        Returns:
            True if consent was withdrawn, False if no consent found
        """
        consent_record = self.get_user_consent(
            tenant_id=tenant_id,
            consent_type=consent_type,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email
        )
        
        if not consent_record:
            logger.warning(f"No consent record found for {consent_type} consent")
            return False
        
        consent_record.withdraw_consent(reason=reason)
        consent_record.save()
        
        logger.info(f"Withdrew {consent_type} consent for tenant {tenant_id}")
        return True
    
    def get_user_consent(self, tenant_id: int, consent_type: str = None,
                        user_id: int = None, external_user_id: str = None,
                        email: str = None) -> Optional['ConsentRecord']:
        """
        Get the most recent consent record for a user.
        
        Args:
            tenant_id: Tenant ID
            consent_type: Type of consent (optional)
            user_id: Internal user ID (optional)
            external_user_id: External user identifier (optional)
            email: User email (optional)
            
        Returns:
            Most recent consent record or None
        """
        from app.models.gdpr_compliance import ConsentRecord, ConsentType
        
        consent_type_enum = None
        if consent_type:
            try:
                consent_type_enum = ConsentType(consent_type)
            except ValueError:
                raise ValueError(f"Invalid consent type: {consent_type}")
        
        consents = ConsentRecord.get_user_consent(
            tenant_id=tenant_id,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email,
            consent_type=consent_type_enum
        )
        
        return consents[0] if consents else None
    
    def get_all_user_consents(self, tenant_id: int, user_id: int = None,
                             external_user_id: str = None, email: str = None) -> List['ConsentRecord']:
        """
        Get all consent records for a user.
        
        Args:
            tenant_id: Tenant ID
            user_id: Internal user ID (optional)
            external_user_id: External user identifier (optional)
            email: User email (optional)
            
        Returns:
            List of all consent records for the user
        """
        from app.models.gdpr_compliance import ConsentRecord
        
        return ConsentRecord.get_user_consent(
            tenant_id=tenant_id,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email
        )
    
    def has_valid_consent(self, tenant_id: int, consent_type: str,
                         user_id: int = None, external_user_id: str = None,
                         email: str = None) -> bool:
        """
        Check if user has valid consent for a specific type.
        
        Args:
            tenant_id: Tenant ID
            consent_type: Type of consent to check
            user_id: Internal user ID (optional)
            external_user_id: External user identifier (optional)
            email: User email (optional)
            
        Returns:
            True if user has valid consent, False otherwise
        """
        from app.models.gdpr_compliance import ConsentRecord, ConsentType
        
        try:
            consent_type_enum = ConsentType(consent_type)
        except ValueError:
            return False
        
        return ConsentRecord.has_valid_consent(
            tenant_id=tenant_id,
            consent_type=consent_type_enum,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email
        )
    
    def check_expired_consents(self, tenant_id: int = None) -> Dict[str, Any]:
        """
        Check for expired consents and update their status.
        
        Args:
            tenant_id: Optional tenant ID to check (if None, checks all tenants)
            
        Returns:
            Report of expired consents
        """
        from app.models.gdpr_compliance import ConsentRecord, ConsentStatus
        
        query = ConsentRecord.query.filter(
            ConsentRecord.status == ConsentStatus.GRANTED,
            ConsentRecord.expires_at.isnot(None),
            ConsentRecord.expires_at < datetime.utcnow()
        )
        
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        
        expired_consents = query.all()
        
        report = {
            'check_date': datetime.utcnow().isoformat(),
            'tenant_id': tenant_id,
            'expired_count': len(expired_consents),
            'expired_consents': []
        }
        
        for consent in expired_consents:
            consent.status = ConsentStatus.EXPIRED
            consent.save()
            
            report['expired_consents'].append({
                'id': consent.id,
                'tenant_id': consent.tenant_id,
                'consent_type': consent.consent_type.value,
                'user_id': consent.user_id,
                'external_user_id': consent.external_user_id,
                'email': consent.email,
                'expired_at': consent.expires_at.isoformat(),
                'purpose': consent.purpose
            })
        
        if expired_consents:
            self.db.commit()
            logger.info(f"Marked {len(expired_consents)} consents as expired")
        
        return report
    
    def get_consent_summary(self, tenant_id: int) -> Dict[str, Any]:
        """
        Get consent summary for a tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Consent summary report
        """
        from app.models.gdpr_compliance import ConsentRecord, ConsentType, ConsentStatus
        
        consents = ConsentRecord.query.filter_by(tenant_id=tenant_id).all()
        
        summary = {
            'tenant_id': tenant_id,
            'total_consents': len(consents),
            'by_type': {},
            'by_status': {},
            'recent_activity': []
        }
        
        # Group by type
        for consent_type in ConsentType:
            type_consents = [c for c in consents if c.consent_type == consent_type]
            summary['by_type'][consent_type.value] = {
                'total': len(type_consents),
                'granted': len([c for c in type_consents if c.status == ConsentStatus.GRANTED]),
                'withdrawn': len([c for c in type_consents if c.status == ConsentStatus.WITHDRAWN]),
                'expired': len([c for c in type_consents if c.status == ConsentStatus.EXPIRED])
            }
        
        # Group by status
        for status in ConsentStatus:
            status_consents = [c for c in consents if c.status == status]
            summary['by_status'][status.value] = len(status_consents)
        
        # Recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_consents = [c for c in consents if c.created_at > thirty_days_ago]
        
        summary['recent_activity'] = [
            {
                'id': consent.id,
                'consent_type': consent.consent_type.value,
                'status': consent.status.value,
                'created_at': consent.created_at.isoformat(),
                'granted_at': consent.granted_at.isoformat() if consent.granted_at else None,
                'withdrawn_at': consent.withdrawn_at.isoformat() if consent.withdrawn_at else None
            }
            for consent in sorted(recent_consents, key=lambda x: x.created_at, reverse=True)[:10]
        ]
        
        return summary
    
    def create_consent_preferences(self, tenant_id: int, user_id: int = None,
                                  external_user_id: str = None, email: str = None,
                                  preferences: Dict[str, bool] = None) -> List['ConsentRecord']:
        """
        Create consent preferences for a user.
        
        Args:
            tenant_id: Tenant ID
            user_id: Internal user ID (optional)
            external_user_id: External user identifier (optional)
            email: User email (optional)
            preferences: Dictionary of consent type -> granted status
            
        Returns:
            List of created consent records
        """
        preferences = preferences or {}
        created_consents = []
        
        for consent_type, granted in preferences.items():
            if granted:
                consent_record = self.grant_consent(
                    tenant_id=tenant_id,
                    consent_type=consent_type,
                    purpose=f"User preference for {consent_type}",
                    user_id=user_id,
                    external_user_id=external_user_id,
                    email=email,
                    source='preferences'
                )
                created_consents.append(consent_record)
            else:
                # If preference is False, withdraw any existing consent
                self.withdraw_consent(
                    tenant_id=tenant_id,
                    consent_type=consent_type,
                    user_id=user_id,
                    external_user_id=external_user_id,
                    email=email,
                    reason='User preference'
                )
        
        return created_consents
    
    def export_user_consents(self, tenant_id: int, user_id: int = None,
                            external_user_id: str = None, email: str = None) -> Dict[str, Any]:
        """
        Export all consent data for a user (for GDPR data portability).
        
        Args:
            tenant_id: Tenant ID
            user_id: Internal user ID (optional)
            external_user_id: External user identifier (optional)
            email: User email (optional)
            
        Returns:
            Exported consent data
        """
        consents = self.get_all_user_consents(
            tenant_id=tenant_id,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email
        )
        
        export_data = {
            'export_date': datetime.utcnow().isoformat(),
            'tenant_id': tenant_id,
            'user_identification': {
                'user_id': user_id,
                'external_user_id': external_user_id,
                'email': email
            },
            'consents': []
        }
        
        for consent in consents:
            consent_data = {
                'id': consent.id,
                'consent_type': consent.consent_type.value,
                'status': consent.status.value,
                'purpose': consent.purpose,
                'legal_basis': consent.legal_basis,
                'granted_at': consent.granted_at.isoformat() if consent.granted_at else None,
                'withdrawn_at': consent.withdrawn_at.isoformat() if consent.withdrawn_at else None,
                'expires_at': consent.expires_at.isoformat() if consent.expires_at else None,
                'source': consent.source,
                'ip_address': consent.ip_address,
                'user_agent': consent.user_agent,
                'evidence': consent.evidence,
                'created_at': consent.created_at.isoformat(),
                'updated_at': consent.updated_at.isoformat()
            }
            export_data['consents'].append(consent_data)
        
        return export_data
    
    def delete_user_consents(self, tenant_id: int, user_id: int = None,
                            external_user_id: str = None, email: str = None) -> int:
        """
        Delete all consent records for a user (for GDPR right to be forgotten).
        
        Args:
            tenant_id: Tenant ID
            user_id: Internal user ID (optional)
            external_user_id: External user identifier (optional)
            email: User email (optional)
            
        Returns:
            Number of deleted consent records
        """
        consents = self.get_all_user_consents(
            tenant_id=tenant_id,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email
        )
        
        count = 0
        for consent in consents:
            self.db.delete(consent)
            count += 1
        
        if count > 0:
            self.db.commit()
            logger.info(f"Deleted {count} consent records for user")
        
        return count
    
    def validate_consent_requirements(self, tenant_id: int, operation: str,
                                    user_id: int = None, external_user_id: str = None,
                                    email: str = None) -> Dict[str, Any]:
        """
        Validate that required consents are in place for an operation.
        
        Args:
            tenant_id: Tenant ID
            operation: Operation being performed (e.g., 'send_marketing_email')
            user_id: Internal user ID (optional)
            external_user_id: External user identifier (optional)
            email: User email (optional)
            
        Returns:
            Validation result with required consents and their status
        """
        # Define consent requirements for different operations
        operation_requirements = {
            'send_marketing_email': ['marketing'],
            'track_analytics': ['analytics'],
            'send_communication': ['communication'],
            'process_personal_data': ['data_processing'],
            'share_with_third_party': ['third_party_sharing']
        }
        
        required_consents = operation_requirements.get(operation, [])
        
        validation_result = {
            'operation': operation,
            'tenant_id': tenant_id,
            'user_identification': {
                'user_id': user_id,
                'external_user_id': external_user_id,
                'email': email
            },
            'required_consents': required_consents,
            'consent_status': {},
            'can_proceed': True,
            'missing_consents': []
        }
        
        for consent_type in required_consents:
            has_consent = self.has_valid_consent(
                tenant_id=tenant_id,
                consent_type=consent_type,
                user_id=user_id,
                external_user_id=external_user_id,
                email=email
            )
            
            validation_result['consent_status'][consent_type] = has_consent
            
            if not has_consent:
                validation_result['can_proceed'] = False
                validation_result['missing_consents'].append(consent_type)
        
        return validation_result