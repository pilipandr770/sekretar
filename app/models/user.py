"""User model for authentication and authorization."""
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from app.models.base import BaseModel, SoftDeleteMixin, AuditMixin
from app.utils.schema import get_schema_name


class User(BaseModel, SoftDeleteMixin, AuditMixin):
    """User model."""
    
    __tablename__ = 'users'
    
    # Tenant relationship
    tenant_id = Column(Integer, ForeignKey(f'{get_schema_name()}.tenants.id'), nullable=False, index=True)
    tenant = relationship('Tenant', back_populates='users')
    
    # Basic information
    email = Column(String(255), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    
    # Role and permissions
    role = Column(String(50), nullable=False, default='read_only')  # owner, manager, support, accounting, read_only
    is_active = Column(Boolean, default=True, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    
    # Authentication
    last_login_at = Column(DateTime, nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    email_verification_token = Column(String(255), nullable=True)
    
    # Profile
    avatar_url = Column(String(500), nullable=True)
    timezone = Column(String(50), default='UTC', nullable=False)
    language = Column(String(10), default='en', nullable=False)  # en, de, uk
    
    # Settings
    notification_preferences = Column(Text, nullable=True)  # JSON string
    
    # Relationships
    assigned_leads = relationship('Lead', foreign_keys='Lead.assigned_to_id', back_populates='assigned_to')
    assigned_tasks = relationship('Task', foreign_keys='Task.assigned_to_id', back_populates='assigned_to')
    notes = relationship('Note', back_populates='user')
    audit_logs = relationship('AuditLog', back_populates='user')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    @property
    def full_name(self):
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.email.split('@')[0]
    
    @property
    def is_owner(self):
        """Check if user is tenant owner."""
        return self.role == 'owner'
    
    @property
    def is_manager(self):
        """Check if user is manager or higher."""
        return self.role in ['owner', 'manager']
    
    @property
    def can_manage_users(self):
        """Check if user can manage other users."""
        return self.role in ['owner', 'manager']
    
    @property
    def can_access_billing(self):
        """Check if user can access billing features."""
        return self.role in ['owner', 'manager', 'accounting']
    
    @property
    def can_manage_settings(self):
        """Check if user can manage tenant settings."""
        return self.role in ['owner', 'manager']
    
    def set_password(self, password):
        """Set user password."""
        self.password_hash = generate_password_hash(password)
        return self
    
    def check_password(self, password):
        """Check if provided password is correct."""
        return check_password_hash(self.password_hash, password)
    
    def generate_password_reset_token(self):
        """Generate password reset token."""
        import secrets
        token = secrets.token_urlsafe(32)
        self.password_reset_token = token
        self.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        return token
    
    def verify_password_reset_token(self, token):
        """Verify password reset token."""
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        
        if datetime.utcnow() > self.password_reset_expires:
            return False
        
        return self.password_reset_token == token
    
    def clear_password_reset_token(self):
        """Clear password reset token."""
        self.password_reset_token = None
        self.password_reset_expires = None
        return self
    
    def generate_email_verification_token(self):
        """Generate email verification token."""
        import secrets
        token = secrets.token_urlsafe(32)
        self.email_verification_token = token
        return token
    
    def verify_email_token(self, token):
        """Verify email verification token."""
        if self.email_verification_token == token:
            self.is_email_verified = True
            self.email_verification_token = None
            return True
        return False
    
    def update_last_login(self):
        """Update last login timestamp."""
        self.last_login_at = datetime.utcnow()
        return self.save()
    
    def has_permission(self, permission):
        """Check if user has specific permission."""
        role_permissions = {
            'owner': [
                'manage_users', 'manage_settings', 'manage_billing',
                'manage_channels', 'manage_knowledge', 'manage_crm',
                'manage_calendar', 'manage_kyb', 'view_analytics'
            ],
            'manager': [
                'manage_users', 'manage_settings', 'manage_billing',
                'manage_channels', 'manage_knowledge', 'manage_crm',
                'manage_calendar', 'manage_kyb', 'view_analytics'
            ],
            'support': [
                'manage_channels', 'manage_crm', 'manage_calendar',
                'view_knowledge', 'view_kyb'
            ],
            'accounting': [
                'manage_billing', 'view_crm', 'view_analytics'
            ],
            'read_only': [
                'view_crm', 'view_calendar', 'view_knowledge'
            ]
        }
        
        return permission in role_permissions.get(self.role, [])
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        exclude.extend(['password_hash', 'password_reset_token', 'email_verification_token'])
        
        data = super().to_dict(exclude=exclude)
        data['full_name'] = self.full_name
        data['is_owner'] = self.is_owner
        data['is_manager'] = self.is_manager
        
        return data
    
    @classmethod
    def create(cls, email, password, tenant_id, **kwargs):
        """Create new user with password hashing."""
        user = cls(email=email, tenant_id=tenant_id, **kwargs)
        user.set_password(password)
        user.generate_email_verification_token()
        return user.save()
    
    @classmethod
    def authenticate(cls, email, password, tenant_id=None):
        """Authenticate user by email and password."""
        query = cls.query.filter_by(email=email, is_active=True)
        
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        
        user = query.first()
        
        if user and user.check_password(password):
            user.update_last_login()
            return user
        
        return None