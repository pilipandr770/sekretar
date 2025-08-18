"""Lead model for CRM."""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, JSON, Numeric
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, SoftDeleteMixin, AuditMixin, get_fk_reference


class Lead(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Lead model for CRM."""
    
    __tablename__ = 'leads'
    
    # Contact relationship
    contact_id = Column(Integer, ForeignKey(get_fk_reference('contacts')), nullable=True, index=True)
    contact = relationship('Contact', back_populates='leads')
    
    # Pipeline and stage
    pipeline_id = Column(Integer, ForeignKey(get_fk_reference('pipelines')), nullable=False, index=True)
    pipeline = relationship('Pipeline', back_populates='leads')
    
    stage_id = Column(Integer, ForeignKey(get_fk_reference('stages')), nullable=False, index=True)
    stage = relationship('Stage', back_populates='leads')
    
    # Basic information
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Value and probability
    value = Column(Numeric(15, 2), nullable=True)  # Deal value
    probability = Column(Integer, default=50, nullable=False)  # Win probability (0-100)
    expected_close_date = Column(String(50), nullable=True)  # ISO date string
    
    # Status
    status = Column(String(50), default='open', nullable=False, index=True)  # open, won, lost, cancelled
    priority = Column(String(20), default='medium', nullable=False)  # low, medium, high, urgent
    
    # Assignment
    assigned_to_id = Column(Integer, ForeignKey(get_fk_reference('users')), nullable=True, index=True)
    assigned_to = relationship('User', foreign_keys=[assigned_to_id], back_populates='assigned_leads')
    
    # Source and tracking
    source = Column(String(100), nullable=True)  # website, referral, cold_call, etc.
    campaign = Column(String(100), nullable=True)  # Marketing campaign
    
    # Custom fields and metadata
    custom_fields = Column(JSON, default=dict, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    
    # Relationships
    tasks = relationship('Task', back_populates='lead', cascade='all, delete-orphan')
    notes = relationship('Note', back_populates='lead', cascade='all, delete-orphan')
    threads = relationship('Thread', back_populates='lead')
    
    def __repr__(self):
        return f'<Lead {self.title}>'    

    @property
    def display_name(self):
        """Get display name for the lead."""
        if self.contact:
            return f"{self.title} - {self.contact.display_name}"
        return self.title
    
    @property
    def is_open(self):
        """Check if lead is still open."""
        return self.status == 'open'
    
    @property
    def is_closed(self):
        """Check if lead is closed (won or lost)."""
        return self.status in ['won', 'lost']
    
    @property
    def is_won(self):
        """Check if lead is won."""
        return self.status == 'won'
    
    @property
    def is_lost(self):
        """Check if lead is lost."""
        return self.status == 'lost'
    
    @property
    def weighted_value(self):
        """Get weighted value (value * probability)."""
        if self.value and self.probability:
            return float(self.value) * (self.probability / 100.0)
        return 0.0
    
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
        """Add tag to lead."""
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
        return self
    
    def remove_tag(self, tag):
        """Remove tag from lead."""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
        return self
    
    def has_tag(self, tag):
        """Check if lead has specific tag."""
        return self.tags and tag in self.tags
    
    def move_to_stage(self, stage_id):
        """Move lead to a different stage."""
        old_stage_id = self.stage_id
        self.stage_id = stage_id
        
        # Update probability based on stage
        if self.stage:
            if self.stage.is_won:
                self.probability = 100
                self.status = 'won'
            elif self.stage.is_closed and not self.stage.is_won:
                self.probability = 0
                self.status = 'lost'
        
        return self
    
    def assign_to_user(self, user_id):
        """Assign lead to user."""
        self.assigned_to_id = user_id
        return self
    
    def unassign(self):
        """Unassign lead from user."""
        self.assigned_to_id = None
        return self
    
    def mark_as_won(self):
        """Mark lead as won."""
        self.status = 'won'
        self.probability = 100
        
        # Move to won stage if available
        if self.pipeline:
            won_stage = next((stage for stage in self.pipeline.stages if stage.is_won), None)
            if won_stage:
                self.stage_id = won_stage.id
        
        return self
    
    def mark_as_lost(self, reason=None):
        """Mark lead as lost."""
        self.status = 'lost'
        self.probability = 0
        
        if reason:
            self.set_custom_field('lost_reason', reason)
        
        # Move to lost stage if available
        if self.pipeline:
            lost_stage = next((stage for stage in self.pipeline.stages 
                             if stage.is_closed and not stage.is_won), None)
            if lost_stage:
                self.stage_id = lost_stage.id
        
        return self
    
    def reopen(self):
        """Reopen a closed lead."""
        if self.is_closed:
            self.status = 'open'
            
            # Move to first stage
            if self.pipeline:
                first_stage = self.pipeline.get_first_stage()
                if first_stage:
                    self.stage_id = first_stage.id
                    self.probability = 50  # Reset to default probability
        
        return self
    
    def get_task_count(self):
        """Get number of tasks for this lead."""
        return len(self.tasks) if self.tasks else 0
    
    def get_open_task_count(self):
        """Get number of open tasks for this lead."""
        if not self.tasks:
            return 0
        return len([task for task in self.tasks if task.status != 'completed'])
    
    def get_note_count(self):
        """Get number of notes for this lead."""
        return len(self.notes) if self.notes else 0
    
    def get_thread_count(self):
        """Get number of linked conversation threads."""
        return len(self.threads) if self.threads else 0
    
    def get_active_threads(self):
        """Get active conversation threads linked to this lead."""
        if not self.threads:
            return []
        return [thread for thread in self.threads if thread.status == 'open']
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['display_name'] = self.display_name
        data['is_open'] = self.is_open
        data['is_closed'] = self.is_closed
        data['is_won'] = self.is_won
        data['is_lost'] = self.is_lost
        data['weighted_value'] = self.weighted_value
        data['task_count'] = self.get_task_count()
        data['open_task_count'] = self.get_open_task_count()
        data['note_count'] = self.get_note_count()
        data['thread_count'] = self.get_thread_count()
        data['active_thread_count'] = len(self.get_active_threads())
        
        # Add related object info
        if self.contact:
            data['contact_name'] = self.contact.display_name
            data['contact_email'] = self.contact.email
        
        if self.stage:
            data['stage_name'] = self.stage.name
            data['stage_color'] = self.stage.color
        
        if self.pipeline:
            data['pipeline_name'] = self.pipeline.name
        
        if self.assigned_to:
            data['assigned_to_name'] = self.assigned_to.full_name
            data['assigned_to_email'] = self.assigned_to.email
        
        return data
    
    @classmethod
    def create_from_contact(cls, tenant_id, contact_id, title, pipeline_id=None, **kwargs):
        """Create lead from existing contact."""
        from app.models.pipeline import Pipeline
        
        # Get default pipeline if not specified
        if not pipeline_id:
            default_pipeline = Pipeline.get_default(tenant_id)
            if default_pipeline:
                pipeline_id = default_pipeline.id
            else:
                raise ValueError("No pipeline specified and no default pipeline found")
        
        # Get first stage of pipeline
        pipeline = Pipeline.query.get(pipeline_id)
        if not pipeline:
            raise ValueError("Pipeline not found")
        
        first_stage = pipeline.get_first_stage()
        if not first_stage:
            raise ValueError("Pipeline has no stages")
        
        return cls.create(
            tenant_id=tenant_id,
            contact_id=contact_id,
            title=title,
            pipeline_id=pipeline_id,
            stage_id=first_stage.id,
            **kwargs
        )
    
    @classmethod
    def get_by_status(cls, tenant_id, status):
        """Get leads by status."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            status=status
        ).all()
    
    @classmethod
    def get_by_stage(cls, stage_id):
        """Get leads in a specific stage."""
        return cls.query.filter_by(stage_id=stage_id).all()
    
    @classmethod
    def get_by_assigned_user(cls, tenant_id, user_id):
        """Get leads assigned to a specific user."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            assigned_to_id=user_id,
            status='open'
        ).all()
    
    @classmethod
    def get_unassigned(cls, tenant_id):
        """Get unassigned open leads."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            assigned_to_id=None,
            status='open'
        ).all()
    
    @classmethod
    def get_recent(cls, tenant_id, limit=10):
        """Get recently created leads."""
        return cls.query.filter_by(tenant_id=tenant_id)\
                      .order_by(cls.created_at.desc())\
                      .limit(limit).all()
    
    @classmethod
    def search(cls, tenant_id, query, limit=20):
        """Search leads by title, description, or contact info."""
        search_term = f'%{query.lower()}%'
        
        return cls.query.join(cls.contact, isouter=True)\
                      .filter(
                          cls.tenant_id == tenant_id,
                          (cls.title.ilike(search_term) |
                           cls.description.ilike(search_term))
                      ).limit(limit).all()