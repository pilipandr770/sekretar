"""Note model for CRM."""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, SoftDeleteMixin, AuditMixin
from app.utils.schema import get_schema_name


class Note(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Note model for CRM."""
    
    __tablename__ = 'notes'
    
    # Lead relationship (optional - notes can exist without leads)
    lead_id = Column(Integer, ForeignKey(f'{get_schema_name()}.leads.id'), nullable=True, index=True)
    lead = relationship('Lead', back_populates='notes')
    
    # User who created the note
    user_id = Column(Integer, ForeignKey(f'{get_schema_name()}.users.id'), nullable=False, index=True)
    user = relationship('User', back_populates='notes')
    
    # Note content
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    
    # Note type and visibility
    note_type = Column(String(50), default='general', nullable=False)  # general, call, meeting, email, etc.
    is_private = Column(Boolean, default=False, nullable=False)  # Private to the user who created it
    is_pinned = Column(Boolean, default=False, nullable=False)  # Pinned to top
    
    # Metadata
    metadata = Column(JSON, default=dict, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    
    def __repr__(self):
        return f'<Note {self.title or "Untitled"}>'
    
    @property
    def display_title(self):
        """Get display title for the note."""
        if self.title:
            return self.title
        
        # Generate title from content (first 50 characters)
        if self.content:
            content_preview = self.content.strip()[:50]
            if len(self.content) > 50:
                content_preview += "..."
            return content_preview
        
        return "Untitled Note"
    
    @property
    def content_preview(self):
        """Get content preview (first 200 characters)."""
        if not self.content:
            return ""
        
        preview = self.content.strip()[:200]
        if len(self.content) > 200:
            preview += "..."
        
        return preview
    
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
        """Add tag to note."""
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
        return self
    
    def remove_tag(self, tag):
        """Remove tag from note."""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
        return self
    
    def has_tag(self, tag):
        """Check if note has specific tag."""
        return self.tags and tag in self.tags
    
    def pin(self):
        """Pin note to top."""
        self.is_pinned = True
        return self
    
    def unpin(self):
        """Unpin note."""
        self.is_pinned = False
        return self
    
    def make_private(self):
        """Make note private."""
        self.is_private = True
        return self
    
    def make_public(self):
        """Make note public."""
        self.is_private = False
        return self
    
    def can_be_viewed_by(self, user):
        """Check if note can be viewed by user."""
        # Owner can always view
        if self.user_id == user.id:
            return True
        
        # Private notes can only be viewed by owner
        if self.is_private:
            return False
        
        # Public notes can be viewed by anyone in the same tenant
        return self.tenant_id == user.tenant_id
    
    def can_be_edited_by(self, user):
        """Check if note can be edited by user."""
        # Only owner can edit
        if self.user_id == user.id:
            return True
        
        # Managers can edit public notes
        if not self.is_private and user.is_manager:
            return True
        
        return False
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['display_title'] = self.display_title
        data['content_preview'] = self.content_preview
        
        # Add related object info
        if self.lead:
            data['lead_title'] = self.lead.title
            data['lead_id'] = self.lead.id
        
        if self.user:
            data['user_name'] = self.user.full_name
            data['user_email'] = self.user.email
        
        return data
    
    @classmethod
    def get_by_lead(cls, lead_id, user=None):
        """Get notes for a specific lead."""
        query = cls.query.filter_by(lead_id=lead_id)
        
        # Filter private notes if user is specified
        if user:
            query = query.filter(
                (cls.is_private == False) | (cls.user_id == user.id)
            )
        
        return query.order_by(cls.is_pinned.desc(), cls.created_at.desc()).all()
    
    @classmethod
    def get_by_user(cls, tenant_id, user_id, include_private=True):
        """Get notes created by a specific user."""
        query = cls.query.filter_by(
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        if not include_private:
            query = query.filter_by(is_private=False)
        
        return query.order_by(cls.is_pinned.desc(), cls.created_at.desc()).all()
    
    @classmethod
    def get_recent(cls, tenant_id, user=None, limit=10):
        """Get recent notes."""
        query = cls.query.filter_by(tenant_id=tenant_id)
        
        # Filter private notes if user is specified
        if user:
            query = query.filter(
                (cls.is_private == False) | (cls.user_id == user.id)
            )
        
        return query.order_by(cls.created_at.desc()).limit(limit).all()
    
    @classmethod
    def search(cls, tenant_id, query_text, user=None, limit=20):
        """Search notes by title and content."""
        search_term = f'%{query_text.lower()}%'
        
        query = cls.query.filter(
            cls.tenant_id == tenant_id,
            (cls.title.ilike(search_term) | cls.content.ilike(search_term))
        )
        
        # Filter private notes if user is specified
        if user:
            query = query.filter(
                (cls.is_private == False) | (cls.user_id == user.id)
            )
        
        return query.order_by(cls.created_at.desc()).limit(limit).all()