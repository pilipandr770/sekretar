"""Pipeline and Stage models for CRM."""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, SoftDeleteMixin, AuditMixin
from app.utils.schema import get_schema_name


class Pipeline(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Sales pipeline model."""
    
    __tablename__ = 'pipelines'
    
    # Basic information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Configuration
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Stage ordering (JSON array of stage IDs)
    stages_order = Column(JSON, default=list, nullable=False)
    
    # Settings
    settings = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    stages = relationship('Stage', back_populates='pipeline', cascade='all, delete-orphan')
    leads = relationship('Lead', back_populates='pipeline')
    
    def __repr__(self):
        return f'<Pipeline {self.name}>'
    
    def get_setting(self, key, default=None):
        """Get pipeline setting."""
        return self.settings.get(key, default) if self.settings else default
    
    def set_setting(self, key, value):
        """Set pipeline setting."""
        if self.settings is None:
            self.settings = {}
        self.settings[key] = value
        return self
    
    def get_ordered_stages(self):
        """Get stages in the correct order."""
        if not self.stages_order:
            return sorted(self.stages, key=lambda s: s.position)
        
        # Create a mapping of stage ID to stage object
        stage_map = {stage.id: stage for stage in self.stages}
        
        # Return stages in the specified order
        ordered_stages = []
        for stage_id in self.stages_order:
            if stage_id in stage_map:
                ordered_stages.append(stage_map[stage_id])
        
        # Add any stages not in the order list
        ordered_ids = set(self.stages_order)
        for stage in self.stages:
            if stage.id not in ordered_ids:
                ordered_stages.append(stage)
        
        return ordered_stages
    
    def update_stages_order(self, stage_ids):
        """Update the order of stages."""
        self.stages_order = stage_ids
        
        # Update position field for consistency
        for i, stage_id in enumerate(stage_ids):
            stage = next((s for s in self.stages if s.id == stage_id), None)
            if stage:
                stage.position = i
        
        return self
    
    def add_stage(self, name, **kwargs):
        """Add a new stage to the pipeline."""
        position = len(self.stages)
        
        stage = Stage.create(
            tenant_id=self.tenant_id,
            pipeline_id=self.id,
            name=name,
            position=position,
            **kwargs
        )
        
        # Update stages order
        if self.stages_order is None:
            self.stages_order = []
        self.stages_order.append(stage.id)
        self.save()
        
        return stage
    
    def get_stage_by_name(self, name):
        """Get stage by name."""
        return next((stage for stage in self.stages if stage.name == name), None)
    
    def get_first_stage(self):
        """Get the first stage in the pipeline."""
        ordered_stages = self.get_ordered_stages()
        return ordered_stages[0] if ordered_stages else None
    
    def get_last_stage(self):
        """Get the last stage in the pipeline."""
        ordered_stages = self.get_ordered_stages()
        return ordered_stages[-1] if ordered_stages else None
    
    def get_lead_count(self):
        """Get total number of leads in this pipeline."""
        return len(self.leads) if self.leads else 0
    
    def get_stage_stats(self):
        """Get statistics for each stage."""
        stats = {}
        
        for stage in self.stages:
            lead_count = len([lead for lead in self.leads if lead.stage_id == stage.id])
            total_value = sum(lead.value or 0 for lead in self.leads if lead.stage_id == stage.id)
            
            stats[stage.id] = {
                'name': stage.name,
                'lead_count': lead_count,
                'total_value': total_value,
                'position': stage.position
            }
        
        return stats
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['lead_count'] = self.get_lead_count()
        data['stage_count'] = len(self.stages) if self.stages else 0
        
        # Add stages
        data['stages'] = [stage.to_dict() for stage in self.get_ordered_stages()]
        
        return data
    
    @classmethod
    def get_default(cls, tenant_id):
        """Get default pipeline for tenant."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            is_default=True,
            is_active=True
        ).first()
    
    @classmethod
    def create_default(cls, tenant_id, **kwargs):
        """Create default pipeline with standard stages."""
        pipeline = cls.create(
            tenant_id=tenant_id,
            name="Sales Pipeline",
            description="Default sales pipeline",
            is_default=True,
            **kwargs
        )
        
        # Create default stages
        stages = [
            {"name": "Lead", "color": "#3498db", "description": "New leads"},
            {"name": "Qualified", "color": "#f39c12", "description": "Qualified prospects"},
            {"name": "Proposal", "color": "#e74c3c", "description": "Proposal sent"},
            {"name": "Negotiation", "color": "#9b59b6", "description": "In negotiation"},
            {"name": "Closed Won", "color": "#27ae60", "description": "Successfully closed"},
            {"name": "Closed Lost", "color": "#95a5a6", "description": "Lost opportunity"}
        ]
        
        stage_ids = []
        for i, stage_data in enumerate(stages):
            stage = Stage.create(
                tenant_id=tenant_id,
                pipeline_id=pipeline.id,
                position=i,
                **stage_data
            )
            stage_ids.append(stage.id)
        
        pipeline.stages_order = stage_ids
        pipeline.save()
        
        return pipeline


class Stage(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Pipeline stage model."""
    
    __tablename__ = 'stages'
    
    # Pipeline relationship
    pipeline_id = Column(Integer, ForeignKey(f'{get_schema_name()}.pipelines.id'), nullable=False, index=True)
    pipeline = relationship('Pipeline', back_populates='stages')
    
    # Basic information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Visual
    color = Column(String(7), default='#3498db', nullable=False)  # Hex color code
    
    # Position and behavior
    position = Column(Integer, nullable=False, default=0)
    is_closed = Column(Boolean, default=False, nullable=False)  # Is this a closing stage?
    is_won = Column(Boolean, default=False, nullable=False)  # Is this a winning stage?
    
    # Automation settings
    auto_actions = Column(JSON, default=dict, nullable=False)  # Automated actions when lead enters stage
    
    # Relationships
    leads = relationship('Lead', back_populates='stage')
    
    def __repr__(self):
        return f'<Stage {self.name}>'
    
    def get_auto_action(self, action_type, default=None):
        """Get auto action configuration."""
        return self.auto_actions.get(action_type, default) if self.auto_actions else default
    
    def set_auto_action(self, action_type, config):
        """Set auto action configuration."""
        if self.auto_actions is None:
            self.auto_actions = {}
        self.auto_actions[action_type] = config
        return self
    
    def get_lead_count(self):
        """Get number of leads in this stage."""
        return len(self.leads) if self.leads else 0
    
    def get_total_value(self):
        """Get total value of leads in this stage."""
        return sum(lead.value or 0 for lead in self.leads if self.leads)
    
    def get_next_stage(self):
        """Get the next stage in the pipeline."""
        ordered_stages = self.pipeline.get_ordered_stages()
        
        try:
            current_index = ordered_stages.index(self)
            if current_index < len(ordered_stages) - 1:
                return ordered_stages[current_index + 1]
        except ValueError:
            pass
        
        return None
    
    def get_previous_stage(self):
        """Get the previous stage in the pipeline."""
        ordered_stages = self.pipeline.get_ordered_stages()
        
        try:
            current_index = ordered_stages.index(self)
            if current_index > 0:
                return ordered_stages[current_index - 1]
        except ValueError:
            pass
        
        return None
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['lead_count'] = self.get_lead_count()
        data['total_value'] = self.get_total_value()
        
        # Add pipeline info
        if self.pipeline:
            data['pipeline_name'] = self.pipeline.name
        
        return data
    
    @classmethod
    def get_by_pipeline(cls, pipeline_id):
        """Get all stages for a pipeline, ordered by position."""
        return cls.query.filter_by(pipeline_id=pipeline_id)\
                      .order_by(cls.position)\
                      .all()