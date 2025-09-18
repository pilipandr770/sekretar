"""User model for authentication and authorization."""
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from app.models.base import BaseModel, SoftDeleteMixin, AuditMixin, get_fk_reference
from app.models.associations import user_roles


class User(BaseModel, SoftDeleteMixin, AuditMixin):
    """User model."""
    
    __tablename__ = 'users'
    
    # Tenant relationship
    tenant_id = Column(Integer, ForeignKey(get_fk_reference('tenants')), nullable=False, index=True)
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
    
    # Google OAuth
    google_oauth_token = Column(Text, nullable=True)  # JSON string for OAuth tokens
    google_oauth_refresh_token = Column(String(255), nullable=True)
    google_oauth_expires_at = Column(DateTime, nullable=True)
    google_calendar_connected = Column(Boolean, default=False, nullable=False)
    
    # Profile
    avatar_url = Column(String(500), nullable=True)
    timezone = Column(String(50), default='UTC', nullable=False)
    language = Column(String(10), default='en', nullable=False)  # en, de, uk
    
    # Settings
    notification_preferences_json = Column(Text, nullable=True)  # JSON string for legacy support
    
    # Relationships
    assigned_leads = relationship('Lead', foreign_keys='Lead.assigned_to_id', back_populates='assigned_to')
    assigned_tasks = relationship('Task', foreign_keys='Task.assigned_to_id', back_populates='assigned_to')
    notes = relationship('Note', foreign_keys='Note.user_id', back_populates='user')
    audit_logs = relationship('AuditLog', foreign_keys='AuditLog.user_id', back_populates='user')
    
    # Role-based access control
    roles = relationship('Role', secondary=user_roles, back_populates='users')
    
    # Notifications
    notification_preferences = relationship('NotificationPreference', back_populates='user')
    notifications = relationship('Notification', back_populates='user')
    
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
        if password is None:
            return False
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
    
    def set_google_oauth_tokens(self, token_data):
        """Store Google OAuth tokens."""
        import json
        
        self.google_oauth_token = json.dumps(token_data)
        self.google_oauth_refresh_token = token_data.get('refresh_token')
        
        # Calculate expiry time
        if 'expires_in' in token_data:
            expires_in = int(token_data['expires_in'])
            self.google_oauth_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        self.google_calendar_connected = True
        return self.save()
    
    def get_google_oauth_tokens(self):
        """Get Google OAuth tokens as dictionary."""
        if not self.google_oauth_token:
            return None
        
        import json
        try:
            return json.loads(self.google_oauth_token)
        except (json.JSONDecodeError, TypeError):
            return None
    
    def is_google_oauth_expired(self):
        """Check if Google OAuth token is expired."""
        if not self.google_oauth_expires_at:
            return True
        
        return datetime.utcnow() >= self.google_oauth_expires_at
    
    def clear_google_oauth_tokens(self):
        """Clear Google OAuth tokens."""
        self.google_oauth_token = None
        self.google_oauth_refresh_token = None
        self.google_oauth_expires_at = None
        self.google_calendar_connected = False
        return self.save()
    
    def has_permission(self, permission):
        """Check if user has specific permission."""
        # Check role-based permissions first (new system)
        if self.roles:
            for role in self.roles:
                if role.has_permission(permission):
                    return True
        
        # Fallback to legacy role-based permissions for backward compatibility
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
    
    def add_role(self, role):
        """Add a role to the user."""
        if role not in self.roles:
            self.roles.append(role)
        return self
    
    def remove_role(self, role):
        """Remove a role from the user."""
        if role in self.roles:
            self.roles.remove(role)
        return self
    
    def has_role(self, role_name):
        """Check if user has a specific role."""
        return any(role.name == role_name for role in self.roles)
    
    def get_all_permissions(self):
        """Get all permissions from all roles."""
        permissions = set()
        for role in self.roles:
            permissions.update(role.get_permissions())
        return list(permissions)
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        exclude.extend(['password_hash', 'password_reset_token', 'email_verification_token'])
        
        data = super().to_dict(exclude=exclude)
        data['full_name'] = self.full_name
        data['is_owner'] = self.is_owner
        data['is_manager'] = self.is_manager
        data['roles'] = [role.to_dict() for role in self.roles] if self.roles else []
        data['permissions'] = self.get_all_permissions()
        
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
        """Authenticate user by email and password (database-agnostic)."""
        try:
            # Normalize email for consistent lookup
            email = email.strip().lower()
            
            # Build query with database-agnostic filters
            query = cls.query.filter(
                cls.email == email,
                cls.is_active == True,
                cls.deleted_at.is_(None)  # Ensure soft-deleted users are excluded
            )
            
            if tenant_id:
                query = query.filter(cls.tenant_id == tenant_id)
            
            user = query.first()
            
            if user and user.check_password(password):
                # Update last login timestamp
                user.update_last_login()
                return user
            
            return None
            
        except Exception as e:
            # Log error but don't expose details
            import structlog
            logger = structlog.get_logger()
            logger.error(
                "User authentication query failed",
                email=email,
                tenant_id=tenant_id,
                error=str(e),
                exc_info=True
            )
            return None
    
    @classmethod
    def find_by_email(cls, email, tenant_id=None):
        """Find user by email (database-agnostic)."""
        try:
            # Normalize email for consistent lookup
            email = email.strip().lower()
            
            # Build query with database-agnostic filters
            query = cls.query.filter(
                cls.email == email,
                cls.deleted_at.is_(None)  # Ensure soft-deleted users are excluded
            )
            
            if tenant_id:
                query = query.filter(cls.tenant_id == tenant_id)
            
            return query.first()
            
        except Exception as e:
            # Log error but don't expose details
            import structlog
            logger = structlog.get_logger()
            logger.error(
                "User lookup query failed",
                email=email,
                tenant_id=tenant_id,
                error=str(e),
                exc_info=True
            )
            return None
    
    @classmethod
    def find_by_id(cls, user_id):
        """Find user by ID (database-agnostic)."""
        try:
            return cls.query.filter(
                cls.id == user_id,
                cls.is_active == True,
                cls.deleted_at.is_(None)
            ).first()
            
        except Exception as e:
            # Log error but don't expose details
            import structlog
            logger = structlog.get_logger()
            logger.error(
                "User ID lookup query failed",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            return None