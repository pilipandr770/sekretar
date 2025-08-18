"""Task model for CRM."""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, SoftDeleteMixin, AuditMixin, get_fk_reference


class Task(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Task model for CRM."""
    
    __tablename__ = 'tasks'
    
    # Lead relationship (optional - tasks can exist without leads)
    lead_id = Column(Integer, ForeignKey(get_fk_reference('leads')), nullable=True, index=True)
    lead = relationship('Lead', back_populates='tasks')
    
    # Basic information
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Assignment
    assigned_to_id = Column(Integer, ForeignKey(get_fk_reference('users')), nullable=True, index=True)
    assigned_to = relationship('User', foreign_keys=[assigned_to_id], back_populates='assigned_tasks')
    
    # Status and priority
    status = Column(String(50), default='pending', nullable=False, index=True)  # pending, in_progress, completed, cancelled
    priority = Column(String(20), default='medium', nullable=False)  # low, medium, high, urgent
    
    # Dates
    due_date = Column(String(50), nullable=True)  # ISO datetime string
    completed_at = Column(String(50), nullable=True)  # ISO datetime string
    
    # Task type and category
    task_type = Column(String(50), default='general', nullable=False)  # call, email, meeting, follow_up, etc.
    category = Column(String(100), nullable=True)
    
    # Metadata
    extra_data = Column(JSON, default=dict, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    
    def __repr__(self):
        return f'<Task {self.title}>'
    
    @property
    def is_completed(self):
        """Check if task is completed."""
        return self.status == 'completed'
    
    @property
    def is_overdue(self):
        """Check if task is overdue."""
        if not self.due_date or self.is_completed:
            return False
        
        from datetime import datetime
        try:
            due = datetime.fromisoformat(self.due_date.replace('Z', '+00:00'))
            return datetime.utcnow() > due
        except (ValueError, AttributeError):
            return False
    
    @property
    def is_due_today(self):
        """Check if task is due today."""
        if not self.due_date or self.is_completed:
            return False
        
        from datetime import datetime, date
        try:
            due = datetime.fromisoformat(self.due_date.replace('Z', '+00:00'))
            return due.date() == date.today()
        except (ValueError, AttributeError):
            return False
    
    def get_metadata(self, key, default=None):
        """Get metadata value."""
        return self.extra_data.get(key, default) if self.extra_data else default
    
    def set_metadata(self, key, value):
        """Set metadata value."""
        if self.extra_data is None:
            self.extra_data = {}
        self.extra_data[key] = value
        return self
    
    def add_tag(self, tag):
        """Add tag to task."""
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
        return self
    
    def remove_tag(self, tag):
        """Remove tag from task."""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
        return self
    
    def has_tag(self, tag):
        """Check if task has specific tag."""
        return self.tags and tag in self.tags
    
    def complete(self):
        """Mark task as completed."""
        from datetime import datetime
        self.status = 'completed'
        self.completed_at = datetime.utcnow().isoformat()
        return self
    
    def reopen(self):
        """Reopen completed task."""
        self.status = 'pending'
        self.completed_at = None
        return self
    
    def start(self):
        """Mark task as in progress."""
        self.status = 'in_progress'
        return self
    
    def cancel(self):
        """Cancel task."""
        self.status = 'cancelled'
        return self
    
    def assign_to_user(self, user_id):
        """Assign task to user."""
        self.assigned_to_id = user_id
        return self
    
    def unassign(self):
        """Unassign task from user."""
        self.assigned_to_id = None
        return self
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['is_completed'] = self.is_completed
        data['is_overdue'] = self.is_overdue
        data['is_due_today'] = self.is_due_today
        
        # Add related object info
        if self.lead:
            data['lead_title'] = self.lead.title
            data['lead_id'] = self.lead.id
        
        if self.assigned_to:
            data['assigned_to_name'] = self.assigned_to.full_name
            data['assigned_to_email'] = self.assigned_to.email
        
        return data
    
    @classmethod
    def get_by_status(cls, tenant_id, status):
        """Get tasks by status."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            status=status
        ).all()
    
    @classmethod
    def get_by_assigned_user(cls, tenant_id, user_id, status=None):
        """Get tasks assigned to a specific user."""
        query = cls.query.filter_by(
            tenant_id=tenant_id,
            assigned_to_id=user_id
        )
        
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(cls.due_date.asc()).all()
    
    @classmethod
    def get_overdue(cls, tenant_id, user_id=None):
        """Get overdue tasks."""
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        
        query = cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.status != 'completed',
            cls.due_date < now
        )
        
        if user_id:
            query = query.filter_by(assigned_to_id=user_id)
        
        return query.order_by(cls.due_date.asc()).all()
    
    @classmethod
    def get_due_today(cls, tenant_id, user_id=None):
        """Get tasks due today."""
        from datetime import datetime, date
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time()).isoformat()
        end_of_day = datetime.combine(today, datetime.max.time()).isoformat()
        
        query = cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.status != 'completed',
            cls.due_date >= start_of_day,
            cls.due_date <= end_of_day
        )
        
        if user_id:
            query = query.filter_by(assigned_to_id=user_id)
        
        return query.order_by(cls.due_date.asc()).all()
    
    @classmethod
    def get_by_lead(cls, lead_id):
        """Get tasks for a specific lead."""
        return cls.query.filter_by(lead_id=lead_id)\
                      .order_by(cls.due_date.asc()).all()
    
    @classmethod
    def get_recent(cls, tenant_id, limit=10):
        """Get recently created tasks."""
        return cls.query.filter_by(tenant_id=tenant_id)\
                      .order_by(cls.created_at.desc())\
                      .limit(limit).all()