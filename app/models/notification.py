"""Notification models for managing notification preferences and delivery tracking."""
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, TenantAwareModel, TimestampMixin, get_fk_reference


class NotificationType(Enum):
    """Types of notifications."""
    EMAIL = "email"
    TELEGRAM = "telegram"
    SIGNAL = "signal"
    SMS = "sms"
    WEBHOOK = "webhook"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationStatus(Enum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class NotificationTemplate(TenantAwareModel, TimestampMixin):
    """Template for notifications."""
    __tablename__ = 'notification_templates'
    
    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # NotificationType
    subject_template = Column(String(255))
    body_template = Column(Text, nullable=False)
    html_template = Column(Text)
    variables = Column(JSON)  # Expected template variables
    is_active = Column(Boolean, default=True)
    
    # Relationships
    notifications = relationship("Notification", back_populates="template")
    
    def __repr__(self):
        return f'<NotificationTemplate {self.name}>'


class NotificationPreference(TenantAwareModel, TimestampMixin):
    """User notification preferences."""
    __tablename__ = 'notification_preferences'
    
    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    user_id = Column(Integer, ForeignKey(get_fk_reference('users')), nullable=False)
    notification_type = Column(String(20), nullable=False)  # NotificationType
    event_type = Column(String(50), nullable=False)  # e.g., 'kyb_alert', 'invoice_paid'
    is_enabled = Column(Boolean, default=True)
    delivery_address = Column(String(255))  # email, phone, telegram_chat_id
    settings = Column(JSON)  # Additional settings like frequency, quiet hours
    
    # Relationships
    user = relationship("User", back_populates="notification_preferences")
    
    def __repr__(self):
        return f'<NotificationPreference {self.user_id}:{self.event_type}>'


class Notification(TenantAwareModel, TimestampMixin):
    """Individual notification record."""
    __tablename__ = 'notifications'
    
    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    template_id = Column(String(36), ForeignKey(get_fk_reference('notification_templates')))
    user_id = Column(Integer, ForeignKey(get_fk_reference('users')))
    recipient = Column(String(255), nullable=False)  # email, phone, chat_id
    type = Column(String(20), nullable=False)  # NotificationType
    priority = Column(String(10), default=NotificationPriority.NORMAL.value)
    status = Column(String(20), default=NotificationStatus.PENDING.value)
    
    # Content
    subject = Column(String(255))
    body = Column(Text, nullable=False)
    html_body = Column(Text)
    variables = Column(JSON)  # Template variables used
    
    # Delivery tracking
    scheduled_at = Column(DateTime)
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    failed_at = Column(DateTime)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text)
    
    # External references
    external_id = Column(String(255))  # Provider-specific ID
    extra_data = Column(JSON)  # Additional provider-specific data
    
    # Relationships
    template = relationship("NotificationTemplate", back_populates="notifications")
    user = relationship("User", back_populates="notifications")
    
    def __repr__(self):
        return f'<Notification {self.id}:{self.type}:{self.status}>'
    
    def is_retryable(self) -> bool:
        """Check if notification can be retried."""
        return (
            self.status == NotificationStatus.FAILED.value and
            self.retry_count < self.max_retries
        )
    
    def mark_sent(self, external_id: Optional[str] = None, metadata: Optional[Dict] = None):
        """Mark notification as sent."""
        self.status = NotificationStatus.SENT.value
        self.sent_at = datetime.utcnow()
        if external_id:
            self.external_id = external_id
        if metadata:
            self.metadata = metadata
    
    def mark_delivered(self, metadata: Optional[Dict] = None):
        """Mark notification as delivered."""
        self.status = NotificationStatus.DELIVERED.value
        self.delivered_at = datetime.utcnow()
        if metadata:
            self.metadata = {**(self.metadata or {}), **metadata}
    
    def mark_failed(self, error_message: str, metadata: Optional[Dict] = None):
        """Mark notification as failed."""
        self.status = NotificationStatus.FAILED.value
        self.failed_at = datetime.utcnow()
        self.error_message = error_message
        self.retry_count += 1
        if metadata:
            self.metadata = {**(self.metadata or {}), **metadata}


class NotificationEvent(TenantAwareModel, TimestampMixin):
    """Notification event log for tracking delivery status changes."""
    __tablename__ = 'notification_events'
    
    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    notification_id = Column(String(36), ForeignKey(get_fk_reference('notifications')), nullable=False)
    event_type = Column(String(50), nullable=False)  # sent, delivered, failed, opened, clicked
    timestamp = Column(DateTime, default=datetime.utcnow)
    data = Column(JSON)  # Event-specific data
    
    # Relationships
    notification = relationship("Notification")
    
    def __repr__(self):
        return f'<NotificationEvent {self.notification_id}:{self.event_type}>'