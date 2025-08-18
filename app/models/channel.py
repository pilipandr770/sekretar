"""Channel model for omnichannel communication."""
from sqlalchemy import Column, String, Boolean, JSON, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, SoftDeleteMixin, AuditMixin


class Channel(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Communication channel model."""
    
    __tablename__ = 'channels'
    
    # Channel information
    name = Column(String(100), nullable=False)  # Human-readable name
    type = Column(String(50), nullable=False, index=True)  # telegram, signal, widget, email
    
    # Configuration (JSON field for channel-specific settings)
    config = Column(JSON, default=dict, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_connected = Column(Boolean, default=False, nullable=False)
    
    # Connection details
    connection_status = Column(String(50), default='disconnected', nullable=False)  # connected, disconnected, error, pending
    last_connected_at = Column(String(50), nullable=True)  # ISO datetime string
    last_error = Column(Text, nullable=True)
    
    # Statistics
    messages_received = Column(Integer, default=0, nullable=False)
    messages_sent = Column(Integer, default=0, nullable=False)
    
    # Relationships
    inbox_messages = relationship('InboxMessage', back_populates='channel', cascade='all, delete-orphan')
    threads = relationship('Thread', back_populates='channel', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Channel {self.name} ({self.type})>'
    
    def get_config(self, key, default=None):
        """Get configuration value."""
        return self.config.get(key, default) if self.config else default
    
    def set_config(self, key, value):
        """Set configuration value."""
        if self.config is None:
            self.config = {}
        self.config[key] = value
        return self
    
    def update_config(self, updates):
        """Update multiple configuration values."""
        if self.config is None:
            self.config = {}
        self.config.update(updates)
        return self
    
    def mark_connected(self):
        """Mark channel as connected."""
        from datetime import datetime
        self.is_connected = True
        self.connection_status = 'connected'
        self.last_connected_at = datetime.utcnow().isoformat()
        self.last_error = None
        return self
    
    def mark_disconnected(self, error=None):
        """Mark channel as disconnected."""
        self.is_connected = False
        self.connection_status = 'error' if error else 'disconnected'
        if error:
            self.last_error = str(error)
        return self
    
    def increment_received(self):
        """Increment received messages counter."""
        self.messages_received += 1
        return self
    
    def increment_sent(self):
        """Increment sent messages counter."""
        self.messages_sent += 1
        return self
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['total_messages'] = self.messages_received + self.messages_sent
        data['is_healthy'] = self.is_connected and self.connection_status == 'connected'
        
        return data
    
    @classmethod
    def create_telegram_channel(cls, tenant_id, name, bot_token, **kwargs):
        """Create Telegram channel."""
        config = {
            'bot_token': bot_token,
            'webhook_url': kwargs.get('webhook_url'),
            'allowed_users': kwargs.get('allowed_users', [])
        }
        
        return cls.create(
            tenant_id=tenant_id,
            name=name,
            type='telegram',
            config=config,
            **kwargs
        )
    
    @classmethod
    def create_signal_channel(cls, tenant_id, name, phone_number, **kwargs):
        """Create Signal channel."""
        config = {
            'phone_number': phone_number,
            'signal_cli_path': kwargs.get('signal_cli_path'),
            'allowed_numbers': kwargs.get('allowed_numbers', [])
        }
        
        return cls.create(
            tenant_id=tenant_id,
            name=name,
            type='signal',
            config=config,
            **kwargs
        )
    
    @classmethod
    def create_widget_channel(cls, tenant_id, name, **kwargs):
        """Create Web Widget channel."""
        config = {
            'widget_id': kwargs.get('widget_id'),
            'allowed_domains': kwargs.get('allowed_domains', []),
            'theme': kwargs.get('theme', 'default'),
            'position': kwargs.get('position', 'bottom-right'),
            'greeting_message': kwargs.get('greeting_message', 'Hello! How can I help you?')
        }
        
        return cls.create(
            tenant_id=tenant_id,
            name=name,
            type='widget',
            config=config,
            **kwargs
        )
    
    @classmethod
    def get_active_channels(cls, tenant_id, channel_type=None):
        """Get active channels for tenant."""
        query = cls.query.filter_by(tenant_id=tenant_id, is_active=True)
        
        if channel_type:
            query = query.filter_by(type=channel_type)
        
        return query.all()
    
    def test_connection(self):
        """Test channel connection (to be implemented by channel handlers)."""
        # This method should be overridden by specific channel implementations
        return True, "Connection test not implemented for this channel type"