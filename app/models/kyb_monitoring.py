"""KYB (Know Your Business) monitoring models."""
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime, Boolean, Float, JSON
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, SoftDeleteMixin, get_fk_reference
from app import db


class Counterparty(TenantAwareModel, SoftDeleteMixin):
    """Counterparty/business partner model for KYB monitoring."""
    __tablename__ = 'counterparties'
    
    # Basic information
    name = Column(String(255), nullable=False, index=True)
    vat_number = Column(String(50), index=True)
    lei_code = Column(String(20), index=True)  # Legal Entity Identifier
    registration_number = Column(String(100))
    
    # Address information
    address = Column(Text)
    country_code = Column(String(2), index=True)  # ISO country code
    city = Column(String(100))
    postal_code = Column(String(20))
    
    # Contact information
    email = Column(String(255))
    phone = Column(String(50))
    website = Column(String(255))
    
    # Risk assessment
    risk_score = Column(Float, default=0.0)  # 0-100 risk score
    risk_level = Column(String(20), default='low', index=True)  # low, medium, high, critical
    status = Column(String(50), default='active', index=True)  # active, inactive, blocked, under_review
    
    # Monitoring configuration
    monitoring_enabled = Column(Boolean, default=True)
    monitoring_frequency = Column(String(20), default='daily')  # daily, weekly, monthly
    last_checked = Column(DateTime, index=True)
    next_check = Column(DateTime, index=True)
    
    # Additional metadata
    notes = Column(Text)
    tags = Column(JSON)  # Array of tags for categorization
    custom_fields = Column(JSON)  # Custom fields for tenant-specific data
    
    # Relationships
    snapshots = relationship("CounterpartySnapshot", back_populates="counterparty", cascade="all, delete-orphan")
    diffs = relationship("CounterpartyDiff", back_populates="counterparty", cascade="all, delete-orphan")
    alerts = relationship("KYBAlert", back_populates="counterparty", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Counterparty {self.name}>'
    
    def calculate_risk_score(self):
        """Calculate risk score based on latest findings."""
        # This would be implemented based on business rules
        # For now, return current score
        return self.risk_score
    
    def update_risk_level(self):
        """Update risk level based on risk score."""
        if self.risk_score >= 90:
            self.risk_level = 'critical'
        elif self.risk_score >= 70:
            self.risk_level = 'high'
        elif self.risk_score >= 40:
            self.risk_level = 'medium'
        else:
            self.risk_level = 'low'
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['full_address'] = self.get_full_address()
        data['display_name'] = self.get_display_name()
        
        return data
    
    def get_full_address(self):
        """Get formatted full address."""
        parts = []
        if self.address:
            parts.append(self.address)
        if self.city:
            parts.append(self.city)
        if self.postal_code:
            parts.append(self.postal_code)
        if self.country_code:
            parts.append(self.country_code)
        return ', '.join(parts) if parts else None
    
    def get_display_name(self):
        """Get display name with country code if available."""
        if self.country_code:
            return f"{self.name} ({self.country_code})"
        return self.name


class CounterpartySnapshot(TenantAwareModel):
    """Snapshot of counterparty data from external sources."""
    __tablename__ = 'counterparty_snapshots'
    
    counterparty_id = Column(Integer, ForeignKey(get_fk_reference('counterparties')), nullable=False, index=True)
    
    # Source information
    source = Column(String(100), nullable=False, index=True)  # VIES, GLEIF, OFAC, etc.
    source_url = Column(String(500))
    check_type = Column(String(50), nullable=False, index=True)  # vat, sanctions, lei, insolvency
    
    # Data snapshot
    data_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hash of raw_data
    raw_data = Column(JSON, nullable=False)  # Complete response from source
    processed_data = Column(JSON)  # Normalized/processed data
    
    # Check results
    status = Column(String(50), nullable=False, index=True)  # valid, invalid, not_found, error, timeout
    response_time_ms = Column(Integer)  # API response time
    error_message = Column(Text)  # Error details if status is error
    
    # Evidence and compliance
    evidence_stored = Column(Boolean, default=True)
    evidence_path = Column(String(500))  # Path to stored evidence file
    compliance_notes = Column(Text)
    
    # Relationships
    counterparty = relationship("Counterparty", back_populates="snapshots")
    
    def __repr__(self):
        return f'<CounterpartySnapshot {self.source}:{self.check_type} for {self.counterparty.name}>'
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add counterparty name for easier display
        if self.counterparty:
            data['counterparty_name'] = self.counterparty.name
        
        return data


class CounterpartyDiff(TenantAwareModel):
    """Detected changes between counterparty snapshots."""
    __tablename__ = 'counterparty_diffs'
    
    counterparty_id = Column(Integer, ForeignKey(get_fk_reference('counterparties')), nullable=False, index=True)
    old_snapshot_id = Column(Integer, ForeignKey(get_fk_reference('counterparty_snapshots')), nullable=True)
    new_snapshot_id = Column(Integer, ForeignKey(get_fk_reference('counterparty_snapshots')), nullable=False)
    
    # Change details
    field_path = Column(String(255), nullable=False)  # JSON path to changed field
    old_value = Column(Text)
    new_value = Column(Text)
    change_type = Column(String(50), nullable=False, index=True)  # added, modified, removed
    
    # Risk assessment
    risk_impact = Column(String(20), default='low', index=True)  # low, medium, high, critical
    risk_score_delta = Column(Float, default=0.0)  # Change in risk score
    
    # Processing status
    processed = Column(Boolean, default=False, index=True)
    alert_generated = Column(Boolean, default=False)
    
    # Relationships
    counterparty = relationship("Counterparty", back_populates="diffs")
    old_snapshot = relationship("CounterpartySnapshot", foreign_keys=[old_snapshot_id])
    new_snapshot = relationship("CounterpartySnapshot", foreign_keys=[new_snapshot_id])
    
    def __repr__(self):
        return f'<CounterpartyDiff {self.field_path} for {self.counterparty.name}>'
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add counterparty name for easier display
        if self.counterparty:
            data['counterparty_name'] = self.counterparty.name
        
        return data


class KYBAlert(TenantAwareModel):
    """Alerts generated from KYB monitoring."""
    __tablename__ = 'kyb_alerts'
    
    counterparty_id = Column(Integer, ForeignKey(get_fk_reference('counterparties')), nullable=False, index=True)
    diff_id = Column(Integer, ForeignKey(get_fk_reference('counterparty_diffs')), nullable=True)
    
    # Alert details
    alert_type = Column(String(50), nullable=False, index=True)  # sanctions_match, data_change, validation_failure
    severity = Column(String(20), nullable=False, index=True)  # low, medium, high, critical
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    
    # Alert data
    alert_data = Column(JSON)  # Additional structured data
    source = Column(String(100))  # Which system/check generated the alert
    
    # Status tracking
    status = Column(String(50), default='open', index=True)  # open, acknowledged, resolved, false_positive
    acknowledged_at = Column(DateTime)
    acknowledged_by_id = Column(Integer, ForeignKey(get_fk_reference('users')))
    resolved_at = Column(DateTime)
    resolved_by_id = Column(Integer, ForeignKey(get_fk_reference('users')))
    resolution_notes = Column(Text)
    
    # Notification tracking
    notification_sent = Column(Boolean, default=False)
    notification_sent_at = Column(DateTime)
    notification_channels = Column(JSON)  # Which channels were notified
    
    # Relationships
    counterparty = relationship("Counterparty", back_populates="alerts")
    diff = relationship("CounterpartyDiff")
    acknowledged_by = relationship("User", foreign_keys=[acknowledged_by_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    
    def __repr__(self):
        return f'<KYBAlert {self.alert_type}:{self.severity} for {self.counterparty.name}>'
    
    def acknowledge(self, user_id, notes=None):
        """Acknowledge the alert."""
        self.status = 'acknowledged'
        self.acknowledged_at = datetime.utcnow()
        self.acknowledged_by_id = user_id
        if notes:
            self.resolution_notes = notes
    
    def resolve(self, user_id, notes=None):
        """Resolve the alert."""
        self.status = 'resolved'
        self.resolved_at = datetime.utcnow()
        self.resolved_by_id = user_id
        if notes:
            self.resolution_notes = notes
    
    def mark_false_positive(self, user_id, notes=None):
        """Mark alert as false positive."""
        self.status = 'false_positive'
        self.resolved_at = datetime.utcnow()
        self.resolved_by_id = user_id
        if notes:
            self.resolution_notes = notes
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add counterparty name for easier display
        if self.counterparty:
            data['counterparty_name'] = self.counterparty.name
        
        # Add user names for acknowledgment/resolution
        if self.acknowledged_by:
            data['acknowledged_by_name'] = self.acknowledged_by.full_name
        if self.resolved_by:
            data['resolved_by_name'] = self.resolved_by.full_name
        
        return data


class KYBMonitoringConfig(TenantAwareModel):
    """Configuration for KYB monitoring per tenant."""
    __tablename__ = 'kyb_monitoring_configs'
    
    # Data source configurations
    vies_enabled = Column(Boolean, default=True)
    gleif_enabled = Column(Boolean, default=True)
    sanctions_eu_enabled = Column(Boolean, default=True)
    sanctions_ofac_enabled = Column(Boolean, default=True)
    sanctions_uk_enabled = Column(Boolean, default=True)
    insolvency_de_enabled = Column(Boolean, default=False)
    
    # Monitoring frequencies
    default_check_frequency = Column(String(20), default='daily')
    high_risk_check_frequency = Column(String(20), default='daily')
    low_risk_check_frequency = Column(String(20), default='weekly')
    
    # Alert settings
    alert_on_sanctions_match = Column(Boolean, default=True)
    alert_on_vat_invalid = Column(Boolean, default=True)
    alert_on_lei_invalid = Column(Boolean, default=True)
    alert_on_insolvency = Column(Boolean, default=True)
    alert_on_data_change = Column(Boolean, default=True)
    
    # Notification settings
    email_notifications = Column(Boolean, default=True)
    telegram_notifications = Column(Boolean, default=False)
    webhook_notifications = Column(Boolean, default=False)
    webhook_url = Column(String(500))
    
    # Risk scoring weights
    sanctions_weight = Column(Float, default=100.0)
    insolvency_weight = Column(Float, default=80.0)
    vat_invalid_weight = Column(Float, default=30.0)
    lei_invalid_weight = Column(Float, default=20.0)
    data_change_weight = Column(Float, default=10.0)
    
    # Retention settings
    snapshot_retention_days = Column(Integer, default=365)
    alert_retention_days = Column(Integer, default=1095)  # 3 years
    
    def __repr__(self):
        return f'<KYBMonitoringConfig for tenant {self.tenant_id}>'
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Group related settings for easier frontend handling
        data['data_sources'] = {
            'vies_enabled': self.vies_enabled,
            'gleif_enabled': self.gleif_enabled,
            'sanctions_eu_enabled': self.sanctions_eu_enabled,
            'sanctions_ofac_enabled': self.sanctions_ofac_enabled,
            'sanctions_uk_enabled': self.sanctions_uk_enabled,
            'insolvency_de_enabled': self.insolvency_de_enabled
        }
        
        data['check_frequencies'] = {
            'default': self.default_check_frequency,
            'high_risk': self.high_risk_check_frequency,
            'low_risk': self.low_risk_check_frequency
        }
        
        data['alert_settings'] = {
            'sanctions_match': self.alert_on_sanctions_match,
            'vat_invalid': self.alert_on_vat_invalid,
            'lei_invalid': self.alert_on_lei_invalid,
            'insolvency': self.alert_on_insolvency,
            'data_change': self.alert_on_data_change
        }
        
        data['notifications'] = {
            'email': self.email_notifications,
            'telegram': self.telegram_notifications,
            'webhook': self.webhook_notifications,
            'webhook_url': self.webhook_url
        }
        
        data['risk_weights'] = {
            'sanctions': self.sanctions_weight,
            'insolvency': self.insolvency_weight,
            'vat_invalid': self.vat_invalid_weight,
            'lei_invalid': self.lei_invalid_weight,
            'data_change': self.data_change_weight
        }
        
        data['retention'] = {
            'snapshots_days': self.snapshot_retention_days,
            'alerts_days': self.alert_retention_days
        }
        
        return data