"""Role model for role-based access control."""
from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, TenantAwareModel, get_fk_reference
from app.models.associations import user_roles
from app import db


class Role(TenantAwareModel):
    """Role model for role-based access control."""
    
    __tablename__ = 'roles'
    
    # Basic information
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # System role flag (cannot be deleted/modified)
    is_system_role = Column(Boolean, default=False, nullable=False)
    
    # Permissions (JSON array of permission strings)
    permissions = Column(Text, nullable=False, default='[]')  # JSON string
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    users = relationship('User', secondary=user_roles, back_populates='roles')
    
    def __repr__(self):
        return f'<Role {self.name}>'
    
    def get_permissions(self):
        """Get permissions as a list."""
        import json
        try:
            return json.loads(self.permissions) if self.permissions else []
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_permissions(self, permissions_list):
        """Set permissions from a list."""
        import json
        self.permissions = json.dumps(permissions_list)
        return self
    
    def has_permission(self, permission):
        """Check if role has specific permission."""
        return permission in self.get_permissions()
    
    def add_permission(self, permission):
        """Add a permission to the role."""
        permissions = self.get_permissions()
        if permission not in permissions:
            permissions.append(permission)
            self.set_permissions(permissions)
        return self
    
    def remove_permission(self, permission):
        """Remove a permission from the role."""
        permissions = self.get_permissions()
        if permission in permissions:
            permissions.remove(permission)
            self.set_permissions(permissions)
        return self
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        data['permissions'] = self.get_permissions()
        return data
    
    @classmethod
    def create_system_roles(cls, tenant_id):
        """Create default system roles for a tenant."""
        system_roles = [
            {
                'name': 'Owner',
                'description': 'Full access to all features and settings',
                'permissions': [
                    'manage_users', 'manage_settings', 'manage_billing',
                    'manage_channels', 'manage_knowledge', 'manage_crm',
                    'manage_calendar', 'manage_kyb', 'view_analytics',
                    'manage_roles', 'view_audit_logs'
                ]
            },
            {
                'name': 'Manager',
                'description': 'Management access to most features',
                'permissions': [
                    'manage_users', 'manage_settings', 'manage_billing',
                    'manage_channels', 'manage_knowledge', 'manage_crm',
                    'manage_calendar', 'manage_kyb', 'view_analytics'
                ]
            },
            {
                'name': 'Support',
                'description': 'Support agent access to customer-facing features',
                'permissions': [
                    'manage_channels', 'manage_crm', 'manage_calendar',
                    'view_knowledge', 'view_kyb'
                ]
            },
            {
                'name': 'Accounting',
                'description': 'Access to billing and financial features',
                'permissions': [
                    'manage_billing', 'view_crm', 'view_analytics'
                ]
            },
            {
                'name': 'Read Only',
                'description': 'Read-only access to basic features',
                'permissions': [
                    'view_crm', 'view_calendar', 'view_knowledge'
                ]
            }
        ]
        
        created_roles = []
        for role_data in system_roles:
            role = cls(
                tenant_id=tenant_id,
                name=role_data['name'],
                description=role_data['description'],
                is_system_role=True
            )
            role.set_permissions(role_data['permissions'])
            role.save()
            created_roles.append(role)
        
        return created_roles
    
    @classmethod
    def get_by_name(cls, name, tenant_id):
        """Get role by name within tenant."""
        return cls.query.filter_by(name=name, tenant_id=tenant_id).first()


class Permission:
    """Permission constants and utilities."""
    
    # User management
    MANAGE_USERS = 'manage_users'
    MANAGE_ROLES = 'manage_roles'
    
    # Settings
    MANAGE_SETTINGS = 'manage_settings'
    
    # Billing
    MANAGE_BILLING = 'manage_billing'
    
    # Channels
    MANAGE_CHANNELS = 'manage_channels'
    
    # Knowledge
    MANAGE_KNOWLEDGE = 'manage_knowledge'
    VIEW_KNOWLEDGE = 'view_knowledge'
    
    # CRM
    MANAGE_CRM = 'manage_crm'
    VIEW_CRM = 'view_crm'
    
    # Calendar
    MANAGE_CALENDAR = 'manage_calendar'
    VIEW_CALENDAR = 'view_calendar'
    
    # KYB
    MANAGE_KYB = 'manage_kyb'
    VIEW_KYB = 'view_kyb'
    
    # Analytics
    VIEW_ANALYTICS = 'view_analytics'
    
    # Audit
    VIEW_AUDIT_LOGS = 'view_audit_logs'
    
    @classmethod
    def get_all_permissions(cls):
        """Get all available permissions."""
        return [
            cls.MANAGE_USERS,
            cls.MANAGE_ROLES,
            cls.MANAGE_SETTINGS,
            cls.MANAGE_BILLING,
            cls.MANAGE_CHANNELS,
            cls.MANAGE_KNOWLEDGE,
            cls.VIEW_KNOWLEDGE,
            cls.MANAGE_CRM,
            cls.VIEW_CRM,
            cls.MANAGE_CALENDAR,
            cls.VIEW_CALENDAR,
            cls.MANAGE_KYB,
            cls.VIEW_KYB,
            cls.VIEW_ANALYTICS,
            cls.VIEW_AUDIT_LOGS
        ]
    
    @classmethod
    def get_permission_groups(cls):
        """Get permissions grouped by category."""
        return {
            'User Management': [cls.MANAGE_USERS, cls.MANAGE_ROLES],
            'Settings': [cls.MANAGE_SETTINGS],
            'Billing': [cls.MANAGE_BILLING],
            'Channels': [cls.MANAGE_CHANNELS],
            'Knowledge': [cls.MANAGE_KNOWLEDGE, cls.VIEW_KNOWLEDGE],
            'CRM': [cls.MANAGE_CRM, cls.VIEW_CRM],
            'Calendar': [cls.MANAGE_CALENDAR, cls.VIEW_CALENDAR],
            'KYB': [cls.MANAGE_KYB, cls.VIEW_KYB],
            'Analytics': [cls.VIEW_ANALYTICS],
            'Audit': [cls.VIEW_AUDIT_LOGS]
        }