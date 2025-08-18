"""GDPR compliance models for data retention, consent, and PII management."""
from datetime import datetime, timedelta
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, DateTime, JSON, Enum
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, BaseModel, SoftDeleteMixin, AuditMixin, get_fk_reference
import enum


class ConsentType(enum.Enum):
    """Types of consent."""
    MARKETING = "marketing"
    ANALYTICS = "analytics"
    COMMUNICATION = "communication"
    DATA_PROCESSING = "data_processing"
    THIRD_PARTY_SHARING = "third_party_sharing"


class ConsentStatus(enum.Enum):
    """Consent status."""
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    PENDING = "pending"


class DataRetentionPolicy(TenantAwareModel, AuditMixin):
    """Data retention policies for different data types."""
    
    __tablename__ = 'data_retention_policies'
    
    # Policy identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Data type and scope
    data_type = Column(String(100), nullable=False, index=True)  # messages, contacts, documents, etc.
    table_name = Column(String(100), nullable=False)
    
    # Retention settings
    retention_days = Column(Integer, nullable=False)  # Days to retain data
    auto_delete = Column(Boolean, default=True, nullable=False)
    anonymize_instead = Column(Boolean, default=False, nullable=False)
    
    # Legal basis
    legal_basis = Column(String(100), nullable=True)  # contract, consent, legitimate_interest, etc.
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Configuration
    config = Column(JSON, default=dict, nullable=False)  # Additional configuration
    
    def __repr__(self):
        return f'<DataRetentionPolicy {self.name} - {self.retention_days} days>'
    
    def is_expired(self, created_date):
        """Check if data created on given date should be deleted."""
        if not self.is_active:
            return False
        
        expiry_date = created_date + timedelta(days=self.retention_days)
        return datetime.utcnow() > expiry_date
    
    def get_expiry_date(self, created_date):
        """Get expiry date for data created on given date."""
        return created_date + timedelta(days=self.retention_days)
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        data = super().to_dict(exclude=exclude)
        return data


class ConsentRecord(TenantAwareModel, AuditMixin):
    """User consent records for GDPR compliance."""
    
    __tablename__ = 'consent_records'
    
    # User identification (can be external user, not just system users)
    user_id = Column(Integer, ForeignKey(get_fk_reference('users')), nullable=True, index=True)
    user = relationship('User', foreign_keys=[user_id])
    
    # External user identification (for non-registered users)
    external_user_id = Column(String(255), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    
    # Consent details
    consent_type = Column(Enum(ConsentType), nullable=False, index=True)
    status = Column(Enum(ConsentStatus), nullable=False, index=True)
    
    # Consent metadata
    purpose = Column(Text, nullable=False)  # Purpose of data processing
    legal_basis = Column(String(100), nullable=True)
    
    # Timestamps
    granted_at = Column(DateTime, nullable=True)
    withdrawn_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Source and context
    source = Column(String(100), nullable=True)  # web, telegram, signal, api
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Evidence
    evidence = Column(JSON, default=dict, nullable=False)  # Proof of consent
    
    def __repr__(self):
        return f'<ConsentRecord {self.consent_type.value} - {self.status.value}>'
    
    def grant_consent(self, source=None, ip_address=None, user_agent=None, evidence=None):
        """Grant consent."""
        self.status = ConsentStatus.GRANTED
        self.granted_at = datetime.utcnow()
        self.withdrawn_at = None
        
        if source:
            self.source = source
        if ip_address:
            self.ip_address = ip_address
        if user_agent:
            self.user_agent = user_agent
        if evidence:
            self.evidence = evidence or {}
        
        return self
    
    def withdraw_consent(self, reason=None):
        """Withdraw consent."""
        self.status = ConsentStatus.WITHDRAWN
        self.withdrawn_at = datetime.utcnow()
        
        if reason:
            if not self.evidence:
                self.evidence = {}
            self.evidence['withdrawal_reason'] = reason
        
        return self
    
    def is_valid(self):
        """Check if consent is currently valid."""
        if self.status != ConsentStatus.GRANTED:
            return False
        
        if self.expires_at and datetime.utcnow() > self.expires_at:
            self.status = ConsentStatus.EXPIRED
            self.save()
            return False
        
        return True
    
    def is_expired(self):
        """Check if consent is expired."""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        return False
    
    @classmethod
    def get_user_consent(cls, tenant_id, user_id=None, external_user_id=None, email=None, consent_type=None):
        """Get user consent records."""
        query = cls.query.filter_by(tenant_id=tenant_id)
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        elif external_user_id:
            query = query.filter_by(external_user_id=external_user_id)
        elif email:
            query = query.filter_by(email=email)
        else:
            return []
        
        if consent_type:
            query = query.filter_by(consent_type=consent_type)
        
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def has_valid_consent(cls, tenant_id, consent_type, user_id=None, external_user_id=None, email=None):
        """Check if user has valid consent for specific type."""
        consents = cls.get_user_consent(
            tenant_id=tenant_id,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email,
            consent_type=consent_type
        )
        
        for consent in consents:
            if consent.is_valid():
                return True
        
        return False


class PIIDetectionLog(TenantAwareModel):
    """Log of PII detection and processing."""
    
    __tablename__ = 'pii_detection_logs'
    
    # Source information
    source_table = Column(String(100), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    
    # PII details
    pii_type = Column(String(50), nullable=False, index=True)  # email, phone, ssn, credit_card, etc.
    confidence = Column(String(20), nullable=False)  # high, medium, low
    
    # Processing action
    action_taken = Column(String(50), nullable=False)  # masked, encrypted, flagged, removed
    original_value_hash = Column(String(255), nullable=True)  # Hash of original value for verification
    
    # Detection metadata
    detection_method = Column(String(100), nullable=True)  # regex, ml_model, manual
    detection_config = Column(JSON, default=dict, nullable=False)
    
    def __repr__(self):
        return f'<PIIDetectionLog {self.pii_type} in {self.source_table}.{self.field_name}>'
    
    @classmethod
    def log_detection(cls, tenant_id, source_table, source_id, field_name, pii_type, 
                     confidence, action_taken, original_value=None, detection_method=None, 
                     detection_config=None):
        """Log PII detection."""
        import hashlib
        
        original_value_hash = None
        if original_value:
            original_value_hash = hashlib.sha256(str(original_value).encode()).hexdigest()
        
        return cls.create(
            tenant_id=tenant_id,
            source_table=source_table,
            source_id=source_id,
            field_name=field_name,
            pii_type=pii_type,
            confidence=confidence,
            action_taken=action_taken,
            original_value_hash=original_value_hash,
            detection_method=detection_method,
            detection_config=detection_config or {}
        )


class DataDeletionRequest(TenantAwareModel, AuditMixin):
    """Data deletion requests for GDPR compliance."""
    
    __tablename__ = 'data_deletion_requests'
    
    # Request identification
    request_id = Column(String(100), nullable=False, unique=True, index=True)
    
    # User identification
    user_id = Column(Integer, ForeignKey(get_fk_reference('users')), nullable=True, index=True)
    user = relationship('User', foreign_keys=[user_id])
    
    external_user_id = Column(String(255), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    
    # Request details
    request_type = Column(String(50), nullable=False)  # full_deletion, anonymization, specific_data
    reason = Column(Text, nullable=True)
    
    # Scope
    data_types = Column(JSON, default=list, nullable=False)  # List of data types to delete
    date_range_start = Column(DateTime, nullable=True)
    date_range_end = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(50), default='pending', nullable=False, index=True)  # pending, processing, completed, failed
    
    # Processing
    processed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Results
    deleted_records = Column(JSON, default=dict, nullable=False)  # Count of deleted records by table
    errors = Column(JSON, default=list, nullable=False)  # Any errors during processing
    
    # Verification
    verification_token = Column(String(255), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f'<DataDeletionRequest {self.request_id} - {self.status}>'
    
    def generate_request_id(self):
        """Generate unique request ID."""
        import uuid
        self.request_id = f"DEL_{uuid.uuid4().hex[:12].upper()}"
        return self.request_id
    
    def generate_verification_token(self):
        """Generate verification token."""
        import secrets
        self.verification_token = secrets.token_urlsafe(32)
        return self.verification_token
    
    def verify_request(self, token):
        """Verify deletion request with token."""
        if self.verification_token == token:
            self.verified_at = datetime.utcnow()
            self.status = 'verified'
            return True
        return False
    
    def start_processing(self):
        """Mark request as processing."""
        self.status = 'processing'
        self.processed_at = datetime.utcnow()
        return self
    
    def complete_processing(self, deleted_records=None, errors=None):
        """Mark request as completed."""
        self.status = 'completed' if not errors else 'failed'
        self.completed_at = datetime.utcnow()
        
        if deleted_records:
            self.deleted_records = deleted_records
        if errors:
            self.errors = errors
        
        return self
    
    def add_deleted_record(self, table_name, count=1):
        """Add deleted record count."""
        if not self.deleted_records:
            self.deleted_records = {}
        
        if table_name in self.deleted_records:
            self.deleted_records[table_name] += count
        else:
            self.deleted_records[table_name] = count
        
        return self
    
    def add_error(self, error_message, table_name=None):
        """Add error to request."""
        if not self.errors:
            self.errors = []
        
        error_entry = {
            'message': error_message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if table_name:
            error_entry['table'] = table_name
        
        self.errors.append(error_entry)
        return self
    
    @classmethod
    def create_deletion_request(cls, tenant_id, request_type, user_id=None, external_user_id=None, 
                               email=None, phone=None, reason=None, data_types=None):
        """Create new deletion request."""
        request = cls.create(
            tenant_id=tenant_id,
            request_type=request_type,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email,
            phone=phone,
            reason=reason,
            data_types=data_types or []
        )
        
        request.generate_request_id()
        request.generate_verification_token()
        request.save()
        
        return request


class DataExportRequest(TenantAwareModel, AuditMixin):
    """Data export requests for GDPR compliance."""
    
    __tablename__ = 'data_export_requests'
    
    # Request identification
    request_id = Column(String(100), nullable=False, unique=True, index=True)
    
    # User identification
    user_id = Column(Integer, ForeignKey(get_fk_reference('users')), nullable=True, index=True)
    user = relationship('User', foreign_keys=[user_id])
    
    external_user_id = Column(String(255), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    
    # Request details
    export_format = Column(String(20), default='json', nullable=False)  # json, csv, xml
    include_metadata = Column(Boolean, default=True, nullable=False)
    
    # Scope
    data_types = Column(JSON, default=list, nullable=False)  # List of data types to export
    date_range_start = Column(DateTime, nullable=True)
    date_range_end = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(50), default='pending', nullable=False, index=True)  # pending, processing, completed, failed, expired
    
    # Processing
    processed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # When export file expires
    
    # Results
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    record_counts = Column(JSON, default=dict, nullable=False)  # Count of exported records by table
    
    # Security
    download_token = Column(String(255), nullable=True)
    download_count = Column(Integer, default=0, nullable=False)
    max_downloads = Column(Integer, default=3, nullable=False)
    
    def __repr__(self):
        return f'<DataExportRequest {self.request_id} - {self.status}>'
    
    def generate_request_id(self):
        """Generate unique request ID."""
        import uuid
        self.request_id = f"EXP_{uuid.uuid4().hex[:12].upper()}"
        return self.request_id
    
    def generate_download_token(self):
        """Generate download token."""
        import secrets
        self.download_token = secrets.token_urlsafe(32)
        return self.download_token
    
    def set_expiry(self, days=7):
        """Set export expiry date."""
        self.expires_at = datetime.utcnow() + timedelta(days=days)
        return self
    
    def is_expired(self):
        """Check if export is expired."""
        return self.expires_at and datetime.utcnow() > self.expires_at
    
    def can_download(self):
        """Check if export can be downloaded."""
        return (self.status == 'completed' and 
                not self.is_expired() and 
                self.download_count < self.max_downloads)
    
    def record_download(self):
        """Record a download attempt."""
        self.download_count += 1
        return self
    
    def start_processing(self):
        """Mark request as processing."""
        self.status = 'processing'
        self.processed_at = datetime.utcnow()
        return self
    
    def complete_processing(self, file_path, file_size, record_counts=None):
        """Mark request as completed."""
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        self.file_path = file_path
        self.file_size = file_size
        
        if record_counts:
            self.record_counts = record_counts
        
        # Set expiry and generate download token
        self.set_expiry()
        self.generate_download_token()
        
        return self
    
    @classmethod
    def create_export_request(cls, tenant_id, user_id=None, external_user_id=None, 
                             email=None, phone=None, export_format='json', 
                             data_types=None, include_metadata=True):
        """Create new export request."""
        request = cls.create(
            tenant_id=tenant_id,
            user_id=user_id,
            external_user_id=external_user_id,
            email=email,
            phone=phone,
            export_format=export_format,
            include_metadata=include_metadata,
            data_types=data_types or []
        )
        
        request.generate_request_id()
        request.save()
        
        return request