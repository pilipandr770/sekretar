"""Contact model for CRM."""
from sqlalchemy import Column, String, Text, Boolean, JSON, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, SoftDeleteMixin, AuditMixin


class Contact(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Contact model for CRM."""
    
    __tablename__ = 'contacts'
    
    # Basic information
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    company = Column(String(255), nullable=True)
    title = Column(String(100), nullable=True)  # Job title
    
    # Contact information
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    mobile = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    
    # Address
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    
    # Social media
    linkedin_url = Column(String(255), nullable=True)
    twitter_handle = Column(String(100), nullable=True)
    
    # Status and classification
    status = Column(String(50), default='active', nullable=False)  # active, inactive, blocked
    contact_type = Column(String(50), default='prospect', nullable=False)  # prospect, customer, partner, vendor
    source = Column(String(100), nullable=True)  # website, referral, cold_call, etc.
    
    # Preferences
    preferred_contact_method = Column(String(50), default='email', nullable=False)  # email, phone, sms
    timezone = Column(String(50), nullable=True)
    language = Column(String(10), default='en', nullable=False)
    
    # Marketing
    email_opt_in = Column(Boolean, default=True, nullable=False)
    sms_opt_in = Column(Boolean, default=False, nullable=False)
    
    # Custom fields and metadata
    custom_fields = Column(JSON, default=dict, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    notes = Column(Text, nullable=True)
    
    # Relationships
    leads = relationship('Lead', back_populates='contact', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Contact {self.full_name}>'
    
    @property
    def full_name(self):
        """Get contact's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        elif self.company:
            return self.company
        elif self.email:
            return self.email.split('@')[0]
        else:
            return f"Contact #{self.id}"
    
    @property
    def display_name(self):
        """Get display name with company if available."""
        name = self.full_name
        if self.company and name != self.company:
            return f"{name} ({self.company})"
        return name
    
    @property
    def full_address(self):
        """Get formatted full address."""
        parts = []
        
        if self.address_line1:
            parts.append(self.address_line1)
        if self.address_line2:
            parts.append(self.address_line2)
        
        city_state_zip = []
        if self.city:
            city_state_zip.append(self.city)
        if self.state:
            city_state_zip.append(self.state)
        if self.postal_code:
            city_state_zip.append(self.postal_code)
        
        if city_state_zip:
            parts.append(' '.join(city_state_zip))
        
        if self.country:
            parts.append(self.country)
        
        return '\n'.join(parts) if parts else None
    
    def get_custom_field(self, key, default=None):
        """Get custom field value."""
        return self.custom_fields.get(key, default) if self.custom_fields else default
    
    def set_custom_field(self, key, value):
        """Set custom field value."""
        if self.custom_fields is None:
            self.custom_fields = {}
        self.custom_fields[key] = value
        return self
    
    def add_tag(self, tag):
        """Add tag to contact."""
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
        return self
    
    def remove_tag(self, tag):
        """Remove tag from contact."""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
        return self
    
    def has_tag(self, tag):
        """Check if contact has specific tag."""
        return self.tags and tag in self.tags
    
    def get_primary_email(self):
        """Get primary email address."""
        return self.email
    
    def get_primary_phone(self):
        """Get primary phone number."""
        return self.mobile or self.phone
    
    def can_contact_via_email(self):
        """Check if contact can be reached via email."""
        return self.email and self.email_opt_in and self.status == 'active'
    
    def can_contact_via_sms(self):
        """Check if contact can be reached via SMS."""
        return self.get_primary_phone() and self.sms_opt_in and self.status == 'active'
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['full_name'] = self.full_name
        data['display_name'] = self.display_name
        data['full_address'] = self.full_address
        data['primary_email'] = self.get_primary_email()
        data['primary_phone'] = self.get_primary_phone()
        data['can_email'] = self.can_contact_via_email()
        data['can_sms'] = self.can_contact_via_sms()
        
        # Add lead count
        data['lead_count'] = len(self.leads) if self.leads else 0
        
        return data
    
    @classmethod
    def find_by_email(cls, tenant_id, email):
        """Find contact by email."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            email=email.lower().strip()
        ).first()
    
    @classmethod
    def find_by_phone(cls, tenant_id, phone):
        """Find contact by phone number."""
        # Normalize phone number (remove spaces, dashes, etc.)
        normalized_phone = ''.join(filter(str.isdigit, phone))
        
        return cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.phone.like(f'%{normalized_phone}%') | 
            cls.mobile.like(f'%{normalized_phone}%')
        ).first()
    
    @classmethod
    def find_or_create_by_email(cls, tenant_id, email, **kwargs):
        """Find existing contact by email or create new one."""
        email = email.lower().strip()
        contact = cls.find_by_email(tenant_id, email)
        
        if contact:
            return contact, False
        
        # Create new contact
        contact = cls.create(
            tenant_id=tenant_id,
            email=email,
            **kwargs
        )
        
        return contact, True
    
    @classmethod
    def search(cls, tenant_id, query, limit=20):
        """Search contacts by name, email, company, or phone."""
        search_term = f'%{query.lower()}%'
        
        return cls.query.filter(
            cls.tenant_id == tenant_id,
            (cls.first_name.ilike(search_term) |
             cls.last_name.ilike(search_term) |
             cls.company.ilike(search_term) |
             cls.email.ilike(search_term) |
             cls.phone.like(search_term) |
             cls.mobile.like(search_term))
        ).limit(limit).all()
    
    @classmethod
    def get_by_type(cls, tenant_id, contact_type):
        """Get contacts by type."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            contact_type=contact_type,
            status='active'
        ).all()
    
    @classmethod
    def get_recent(cls, tenant_id, limit=10):
        """Get recently created contacts."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            status='active'
        ).order_by(cls.created_at.desc()).limit(limit).all()