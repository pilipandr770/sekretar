"""Tenant model for multi-tenant architecture."""
from sqlalchemy import Column, String, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, SoftDeleteMixin


class Tenant(BaseModel, SoftDeleteMixin):
    """Tenant (Organization) model."""
    
    __tablename__ = 'tenants'
    
    # Basic information
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True, nullable=True, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    
    # Contact information
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Settings (JSON field for flexible configuration)
    settings = Column(JSON, default=dict, nullable=False)
    
    # Subscription information
    subscription_status = Column(String(50), default='trial', nullable=False)  # trial, active, suspended, cancelled
    trial_ends_at = Column(String(50), nullable=True)  # ISO datetime string
    
    # Relationships
    users = relationship('User', back_populates='tenant', cascade='all, delete-orphan')
    channels = relationship('Channel', back_populates='tenant', cascade='all, delete-orphan')
    inbox_messages = relationship('InboxMessage', back_populates='tenant', cascade='all, delete-orphan')
    leads = relationship('Lead', back_populates='tenant', cascade='all, delete-orphan')
    tasks = relationship('Task', back_populates='tenant', cascade='all, delete-orphan')
    knowledge_sources = relationship('KnowledgeSource', back_populates='tenant', cascade='all, delete-orphan')
    invoices = relationship('Invoice', back_populates='tenant', cascade='all, delete-orphan')
    counterparties = relationship('Counterparty', back_populates='tenant', cascade='all, delete-orphan')
    subscriptions = relationship('Subscription', back_populates='tenant', cascade='all, delete-orphan')
    usage_events = relationship('UsageEvent', back_populates='tenant', cascade='all, delete-orphan')
    audit_logs = relationship('AuditLog', back_populates='tenant', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Tenant {self.name}>'
    
    def to_dict(self, exclude=None):
        """Convert to dictionary with additional fields."""
        exclude = exclude or []
        exclude.extend(['settings'])  # Exclude sensitive settings by default
        
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['user_count'] = len(self.users) if self.users else 0
        data['is_trial'] = self.subscription_status == 'trial'
        
        return data
    
    def get_setting(self, key, default=None):
        """Get a setting value."""
        return self.settings.get(key, default)
    
    def set_setting(self, key, value):
        """Set a setting value."""
        if self.settings is None:
            self.settings = {}
        self.settings[key] = value
        return self
    
    def is_trial_expired(self):
        """Check if trial period has expired."""
        if self.subscription_status != 'trial' or not self.trial_ends_at:
            return False
        
        from datetime import datetime
        try:
            trial_end = datetime.fromisoformat(self.trial_ends_at.replace('Z', '+00:00'))
            return datetime.utcnow() > trial_end
        except (ValueError, AttributeError):
            return True  # If we can't parse the date, consider it expired
    
    def can_access_feature(self, feature_name):
        """Check if tenant can access a specific feature."""
        if self.subscription_status == 'suspended' or self.subscription_status == 'cancelled':
            return False
        
        if self.subscription_status == 'trial' and self.is_trial_expired():
            # During expired trial, only allow basic features
            basic_features = ['inbox_read', 'crm_read', 'calendar_read']
            return feature_name in basic_features
        
        return True
    
    @classmethod
    def create_with_owner(cls, name, owner_email, owner_password, **kwargs):
        """Create tenant with owner user."""
        from app.models.user import User
        import secrets
        import string
        
        # Generate unique slug
        slug = kwargs.get('slug')
        if not slug:
            slug = name.lower().replace(' ', '-').replace('_', '-')
            # Ensure uniqueness
            counter = 1
            original_slug = slug
            while cls.query.filter_by(slug=slug).first():
                slug = f"{original_slug}-{counter}"
                counter += 1
        
        # Create tenant
        tenant = cls(name=name, slug=slug, **kwargs)
        tenant.save()
        
        # Create owner user
        owner = User.create(
            tenant_id=tenant.id,
            email=owner_email,
            password=owner_password,
            role='owner',
            is_active=True
        )
        
        return tenant, owner