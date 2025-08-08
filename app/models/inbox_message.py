"""Inbox message model for unified messaging."""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, JSON, LargeBinary
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, SoftDeleteMixin, AuditMixin
from app.utils.schema import get_schema_name


class InboxMessage(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Unified inbox message model."""
    
    __tablename__ = 'inbox_messages'
    
    # Channel and thread relationships
    channel_id = Column(Integer, ForeignKey(f'{get_schema_name()}.channels.id'), nullable=False, index=True)
    channel = relationship('Channel', back_populates='inbox_messages')
    
    thread_id = Column(Integer, ForeignKey(f'{get_schema_name()}.threads.id'), nullable=False, index=True)
    thread = relationship('Thread', back_populates='messages')
    
    # Message identification
    external_id = Column(String(255), nullable=True, index=True)  # External message ID from channel
    message_id = Column(String(255), nullable=True, index=True)  # Our internal message ID
    
    # Sender information
    sender_id = Column(String(255), nullable=False, index=True)  # External sender ID
    sender_name = Column(String(255), nullable=True)
    sender_email = Column(String(255), nullable=True)
    sender_phone = Column(String(50), nullable=True)
    
    # Message content
    content = Column(Text, nullable=True)
    content_type = Column(String(50), default='text', nullable=False)  # text, image, file, audio, video
    
    # Message direction and type
    direction = Column(String(20), nullable=False, index=True)  # inbound, outbound
    message_type = Column(String(50), default='message', nullable=False)  # message, system, notification
    
    # AI processing
    ai_processed = Column(Boolean, default=False, nullable=False)
    ai_response = Column(Text, nullable=True)
    ai_confidence = Column(String(20), nullable=True)  # high, medium, low
    ai_intent = Column(String(100), nullable=True)
    ai_sentiment = Column(String(20), nullable=True)  # positive, neutral, negative
    
    # Status
    status = Column(String(50), default='received', nullable=False, index=True)  # received, processing, sent, failed, read
    is_read = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    sent_at = Column(String(50), nullable=True)  # ISO datetime string
    delivered_at = Column(String(50), nullable=True)
    read_at = Column(String(50), nullable=True)
    
    # Metadata
    metadata = Column(JSON, default=dict, nullable=False)  # Channel-specific metadata
    
    # Relationships
    attachments = relationship('Attachment', back_populates='message', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<InboxMessage {self.direction} from {self.sender_id}>'
    
    def get_metadata(self, key, default=None):
        """Get metadata value."""
        return self.metadata.get(key, default) if self.metadata else default
    
    def set_metadata(self, key, value):
        """Set metadata value."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value
        return self
    
    def mark_as_read(self):
        """Mark message as read."""
        from datetime import datetime
        self.is_read = True
        self.read_at = datetime.utcnow().isoformat()
        return self
    
    def mark_as_sent(self):
        """Mark message as sent."""
        from datetime import datetime
        self.status = 'sent'
        self.delivered_at = datetime.utcnow().isoformat()
        return self
    
    def mark_as_failed(self, error=None):
        """Mark message as failed."""
        self.status = 'failed'
        if error:
            self.set_metadata('error', str(error))
        return self
    
    def set_ai_response(self, response, confidence=None, intent=None, sentiment=None):
        """Set AI response and processing results."""
        self.ai_response = response
        self.ai_processed = True
        self.ai_confidence = confidence
        self.ai_intent = intent
        self.ai_sentiment = sentiment
        return self
    
    def has_attachments(self):
        """Check if message has attachments."""
        return len(self.attachments) > 0
    
    def get_attachment_count(self):
        """Get number of attachments."""
        return len(self.attachments)
    
    def is_from_customer(self):
        """Check if message is from customer."""
        return self.direction == 'inbound'
    
    def is_from_agent(self):
        """Check if message is from agent."""
        return self.direction == 'outbound'
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['has_attachments'] = self.has_attachments()
        data['attachment_count'] = self.get_attachment_count()
        data['is_from_customer'] = self.is_from_customer()
        data['is_from_agent'] = self.is_from_agent()
        
        # Add channel info
        if self.channel:
            data['channel_name'] = self.channel.name
            data['channel_type'] = self.channel.type
        
        # Add thread info
        if self.thread:
            data['thread_status'] = self.thread.status
            data['thread_subject'] = self.thread.subject
        
        return data
    
    @classmethod
    def create_inbound(cls, tenant_id, channel_id, thread_id, sender_id, content, **kwargs):
        """Create inbound message from customer."""
        from datetime import datetime
        
        message = cls.create(
            tenant_id=tenant_id,
            channel_id=channel_id,
            thread_id=thread_id,
            sender_id=sender_id,
            content=content,
            direction='inbound',
            sent_at=datetime.utcnow().isoformat(),
            **kwargs
        )
        
        # Update thread statistics
        if message.thread:
            message.thread.increment_message_count()
            message.thread.update_last_message(message.sent_at, is_from_customer=True)
            message.thread.save()
        
        # Update channel statistics
        if message.channel:
            message.channel.increment_received()
            message.channel.save()
        
        return message
    
    @classmethod
    def create_outbound(cls, tenant_id, channel_id, thread_id, content, sender_id=None, **kwargs):
        """Create outbound message to customer."""
        from datetime import datetime
        
        message = cls.create(
            tenant_id=tenant_id,
            channel_id=channel_id,
            thread_id=thread_id,
            sender_id=sender_id or 'system',
            content=content,
            direction='outbound',
            sent_at=datetime.utcnow().isoformat(),
            status='processing',
            **kwargs
        )
        
        # Update thread statistics
        if message.thread:
            message.thread.increment_message_count()
            message.thread.update_last_message(message.sent_at, is_from_customer=False)
            message.thread.save()
        
        return message
    
    @classmethod
    def get_thread_messages(cls, thread_id, limit=50, offset=0):
        """Get messages for a thread."""
        return cls.query.filter_by(thread_id=thread_id)\
                      .order_by(cls.created_at.desc())\
                      .limit(limit)\
                      .offset(offset)\
                      .all()
    
    @classmethod
    def get_unread_messages(cls, tenant_id, channel_id=None):
        """Get unread messages for tenant."""
        query = cls.query.filter_by(
            tenant_id=tenant_id,
            is_read=False,
            direction='inbound'
        )
        
        if channel_id:
            query = query.filter_by(channel_id=channel_id)
        
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_messages_needing_ai_processing(cls, tenant_id, limit=10):
        """Get messages that need AI processing."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            direction='inbound',
            ai_processed=False
        ).order_by(cls.created_at.asc()).limit(limit).all()


class Attachment(TenantAwareModel, SoftDeleteMixin):
    """Message attachment model."""
    
    __tablename__ = 'attachments'
    
    # Message relationship
    message_id = Column(Integer, ForeignKey(f'{get_schema_name()}.inbox_messages.id'), nullable=False, index=True)
    message = relationship('InboxMessage', back_populates='attachments')
    
    # File information
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=True)  # Local file path or URL
    file_size = Column(Integer, nullable=True)  # Size in bytes
    mime_type = Column(String(100), nullable=True)
    
    # File content (for small files or temporary storage)
    file_data = Column(LargeBinary, nullable=True)
    
    # Status
    status = Column(String(50), default='uploaded', nullable=False)  # uploaded, processing, ready, failed
    
    # Metadata
    metadata = Column(JSON, default=dict, nullable=False)
    
    def __repr__(self):
        return f'<Attachment {self.filename}>'
    
    def get_file_extension(self):
        """Get file extension."""
        if self.filename and '.' in self.filename:
            return self.filename.rsplit('.', 1)[1].lower()
        return None
    
    def is_image(self):
        """Check if attachment is an image."""
        if self.mime_type:
            return self.mime_type.startswith('image/')
        
        ext = self.get_file_extension()
        return ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
    
    def is_document(self):
        """Check if attachment is a document."""
        if self.mime_type:
            return self.mime_type in [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain'
            ]
        
        ext = self.get_file_extension()
        return ext in ['pdf', 'doc', 'docx', 'txt', 'md']
    
    def is_audio(self):
        """Check if attachment is audio."""
        if self.mime_type:
            return self.mime_type.startswith('audio/')
        
        ext = self.get_file_extension()
        return ext in ['mp3', 'wav', 'ogg', 'm4a', 'aac']
    
    def is_video(self):
        """Check if attachment is video."""
        if self.mime_type:
            return self.mime_type.startswith('video/')
        
        ext = self.get_file_extension()
        return ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm']
    
    def get_human_readable_size(self):
        """Get human readable file size."""
        if not self.file_size:
            return "Unknown size"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        exclude.append('file_data')  # Don't include binary data in dict
        
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['file_extension'] = self.get_file_extension()
        data['is_image'] = self.is_image()
        data['is_document'] = self.is_document()
        data['is_audio'] = self.is_audio()
        data['is_video'] = self.is_video()
        data['human_readable_size'] = self.get_human_readable_size()
        
        return data