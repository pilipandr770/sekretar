"""Audit log model for GDPR compliance and security."""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, get_fk_reference


class AuditLog(BaseModel):
    """Audit log for tracking user actions and data changes."""
    
    __tablename__ = 'audit_logs'
    
    # Tenant relationship
    tenant_id = Column(Integer, ForeignKey(get_fk_reference('tenants')), nullable=False, index=True)
    tenant = relationship('Tenant', back_populates='audit_logs')
    
    # User who performed the action
    user_id = Column(Integer, ForeignKey(get_fk_reference('users')), nullable=True, index=True)
    user = relationship('User', back_populates='audit_logs')
    
    # Action details
    action = Column(String(100), nullable=False, index=True)  # create, update, delete, login, logout, etc.
    resource_type = Column(String(100), nullable=False, index=True)  # user, lead, message, etc.
    resource_id = Column(String(100), nullable=True, index=True)  # ID of the affected resource
    
    # Request context
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=True, index=True)
    
    # Change details
    old_values = Column(JSON, nullable=True)  # Previous values (for updates)
    new_values = Column(JSON, nullable=True)  # New values (for creates/updates)
    
    # Additional metadata
    extra_data = Column(JSON, nullable=True)  # Additional context data
    
    # Status
    status = Column(String(20), default='success', nullable=False)  # success, failed, error
    error_message = Column(Text, nullable=True)
    
    def __repr__(self):
        return f'<AuditLog {self.action} on {self.resource_type}>'
    
    @classmethod
    def log_action(cls, action, resource_type, tenant_id, user_id=None, resource_id=None,
                   old_values=None, new_values=None, extra_data=None, ip_address=None,
                   user_agent=None, request_id=None, status='success', error_message=None):
        """Create audit log entry."""
        log_entry = cls(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            old_values=old_values,
            new_values=new_values,
            extra_data=extra_data,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            status=status,
            error_message=error_message
        )
        
        return log_entry.save()
    
    @classmethod
    def log_user_action(cls, user, action, resource_type, resource_id=None,
                       old_values=None, new_values=None, extra_data=None,
                       request_context=None):
        """Log user action with context."""
        ip_address = None
        user_agent = None
        request_id = None
        
        if request_context:
            ip_address = request_context.get('ip_address')
            user_agent = request_context.get('user_agent')
            request_id = request_context.get('request_id')
        
        return cls.log_action(
            action=action,
            resource_type=resource_type,
            tenant_id=user.tenant_id,
            user_id=user.id,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            extra_data=extra_data,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )
    
    @classmethod
    def log_login(cls, user, ip_address=None, user_agent=None, success=True):
        """Log user login attempt."""
        return cls.log_action(
            action='login',
            resource_type='user',
            tenant_id=user.tenant_id,
            user_id=user.id,
            resource_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            status='success' if success else 'failed'
        )
    
    @classmethod
    def log_logout(cls, user, ip_address=None, user_agent=None):
        """Log user logout."""
        return cls.log_action(
            action='logout',
            resource_type='user',
            tenant_id=user.tenant_id,
            user_id=user.id,
            resource_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @classmethod
    def log_data_export(cls, user, resource_type, extra_data=None):
        """Log data export for GDPR compliance."""
        return cls.log_user_action(
            user=user,
            action='export',
            resource_type=resource_type,
            extra_data=extra_data or {}
        )
    
    @classmethod
    def log_data_deletion(cls, user, resource_type, resource_id, extra_data=None):
        """Log data deletion for GDPR compliance."""
        return cls.log_user_action(
            user=user,
            action='delete',
            resource_type=resource_type,
            resource_id=resource_id,
            extra_data=extra_data or {}
        )
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add user information if available
        if self.user:
            data['user_email'] = self.user.email
            data['user_name'] = self.user.full_name
        
        return data