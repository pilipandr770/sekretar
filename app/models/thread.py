"""Thread model for conversation management."""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, SoftDeleteMixin, AuditMixin
from app.utils.schema import get_schema_name


class Thread(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Conversation thread model."""
    
    __tablename__ = 'threads'
    
    # Channel relationship
    channel_id = Column(Integer, ForeignKey(f'{get_schema_name()}.channels.id'), nullable=False, index=True)
    channel = relationship('Channel', back_populates='threads')
    
    # Customer information
    customer_id = Column(String(255), nullable=False, index=True)  # External customer ID (phone, telegram_id, etc.)
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    
    # Thread information
    subject = Column(String(500), nullable=True)
    status = Column(String(50), default='open', nullable=False, index=True)  # open, closed, archived, spam
    priority = Column(String(20), default='normal', nullable=False)  # low, normal, high, urgent
    
    # Assignment
    assigned_to_id = Column(Integer, ForeignKey(f'{get_schema_name()}.users.id'), nullable=True, index=True)
    assigned_to = relationship('User', foreign_keys=[assigned_to_id])
    
    # AI handling
    ai_enabled = Column(Boolean, default=True, nullable=False)
    ai_context = Column(JSON, default=dict, nullable=False)  # AI conversation context
    
    # Statistics
    message_count = Column(Integer, default=0, nullable=False)
    last_message_at = Column(String(50), nullable=True)  # ISO datetime string
    last_customer_message_at = Column(String(50), nullable=True)
    last_agent_message_at = Column(String(50), nullable=True)
    
    # Metadata
    metadata = Column(JSON, default=dict, nullable=False)  # Additional thread data
    tags = Column(JSON, default=list, nullable=False)  # Thread tags
    
    # Relationships
    messages = relationship('InboxMessage', back_populates='thread', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Thread {self.customer_id} on {self.channel.name if self.channel else "Unknown"}>'
    
    def get_metadata(self, key, default=None):
        """Get metadata value."""
        return self.metadata.get(key, default) if self.metadata else default
    
    def set_metadata(self, key, value):
        """Set metadata value."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value
        return self
    
    def add_tag(self, tag):
        """Add tag to thread."""
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
        return self
    
    def remove_tag(self, tag):
        """Remove tag from thread."""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
        return self
    
    def has_tag(self, tag):
        """Check if thread has specific tag."""
        return self.tags and tag in self.tags
    
    def assign_to_user(self, user_id):
        """Assign thread to user."""
        self.assigned_to_id = user_id
        self.ai_enabled = False  # Disable AI when assigned to human
        return self
    
    def unassign(self):
        """Unassign thread from user."""
        self.assigned_to_id = None
        self.ai_enabled = True  # Re-enable AI when unassigned
        return self
    
    def close(self):
        """Close thread."""
        self.status = 'closed'
        return self
    
    def reopen(self):
        """Reopen thread."""
        self.status = 'open'
        return self
    
    def archive(self):
        """Archive thread."""
        self.status = 'archived'
        return self
    
    def mark_as_spam(self):
        """Mark thread as spam."""
        self.status = 'spam'
        self.ai_enabled = False
        return self
    
    def update_last_message(self, message_timestamp, is_from_customer=True):
        """Update last message timestamp."""
        self.last_message_at = message_timestamp
        
        if is_from_customer:
            self.last_customer_message_at = message_timestamp
        else:
            self.last_agent_message_at = message_timestamp
        
        return self
    
    def increment_message_count(self):
        """Increment message count."""
        self.message_count += 1
        return self
    
    def get_ai_context(self, key, default=None):
        """Get AI context value."""
        return self.ai_context.get(key, default) if self.ai_context else default
    
    def set_ai_context(self, key, value):
        """Set AI context value."""
        if self.ai_context is None:
            self.ai_context = {}
        self.ai_context[key] = value
        return self
    
    def clear_ai_context(self):
        """Clear AI context."""
        self.ai_context = {}
        return self
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['is_active'] = self.status in ['open']
        data['needs_attention'] = (
            self.status == 'open' and 
            self.assigned_to_id is None and 
            not self.ai_enabled
        )
        
        # Add channel info
        if self.channel:
            data['channel_name'] = self.channel.name
            data['channel_type'] = self.channel.type
        
        # Add assigned user info
        if self.assigned_to:
            data['assigned_to_name'] = self.assigned_to.full_name
            data['assigned_to_email'] = self.assigned_to.email
        
        return data
    
    @classmethod
    def find_or_create(cls, tenant_id, channel_id, customer_id, **kwargs):
        """Find existing thread or create new one."""
        # Look for existing open thread
        existing = cls.query.filter_by(
            tenant_id=tenant_id,
            channel_id=channel_id,
            customer_id=customer_id,
            status='open'
        ).first()
        
        if existing:
            return existing, False
        
        # Create new thread
        thread = cls.create(
            tenant_id=tenant_id,
            channel_id=channel_id,
            customer_id=customer_id,
            **kwargs
        )
        
        return thread, True
    
    @classmethod
    def get_active_threads(cls, tenant_id, assigned_to_id=None, channel_id=None):
        """Get active threads for tenant."""
        query = cls.query.filter_by(tenant_id=tenant_id, status='open')
        
        if assigned_to_id:
            query = query.filter_by(assigned_to_id=assigned_to_id)
        
        if channel_id:
            query = query.filter_by(channel_id=channel_id)
        
        return query.order_by(cls.last_message_at.desc()).all()
    
    @classmethod
    def get_unassigned_threads(cls, tenant_id):
        """Get unassigned threads that need attention."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            status='open',
            assigned_to_id=None
        ).filter(
            cls.ai_enabled == False
        ).order_by(cls.last_message_at.desc()).all()