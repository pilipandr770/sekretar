"""
Data Seeding System

This module provides comprehensive data seeding functionality for initial
system data creation, including admin users, system tenants, and roles.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.models import User, Tenant, Role
from .database_init_logger import get_database_init_logger, LogLevel, LogCategory

logger = logging.getLogger(__name__)


@dataclass
class SeedingResult:
    """Result of data seeding process."""
    success: bool
    records_created: Dict[str, int] = field(default_factory=dict)
    records_skipped: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_created(self, record_type: str, count: int = 1):
        """Add created record count."""
        self.records_created[record_type] = self.records_created.get(record_type, 0) + count
        logger.info(f"✅ Created {count} {record_type} record(s)")
    
    def add_skipped(self, record_type: str, count: int = 1):
        """Add skipped record count."""
        self.records_skipped[record_type] = self.records_skipped.get(record_type, 0) + count
        logger.info(f"⏭️ Skipped {count} existing {record_type} record(s)")
    
    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
        logger.error(f"❌ Seeding error: {error}")
    
    def add_warning(self, warning: str):
        """Add a warning message."""
        self.warnings.append(warning)
        logger.warning(f"⚠️ Seeding warning: {warning}")


class DataSeeder:
    """
    Data seeding system for creating initial system data.
    
    Handles creation of admin users, system tenants, roles, and other
    essential data required for application functionality.
    """
    
    def __init__(self, app: Flask, db: SQLAlchemy):
        self.app = app
        self.db = db
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize logging system
        log_level = LogLevel.DEBUG if app.debug else LogLevel.INFO
        self.init_logger = get_database_init_logger("data_seeder", log_level)
        
        # Default admin credentials
        self.default_admin_email = "admin@ai-secretary.com"
        self.default_admin_password = "admin123"
        self.default_tenant_name = "AI Secretary System"
        self.default_tenant_slug = "ai-secretary-system"
    
    def seed_initial_data(self) -> SeedingResult:
        """
        Seed all initial data required for application functionality.
        
        Returns:
            SeedingResult with seeding details
        """
        start_time = time.time()
        result = SeedingResult(success=True)
        
        self.init_logger.start_initialization(total_steps=3)
        
        try:
            # Step 1: Create system tenant
            with self.init_logger.step("Create System Tenant", LogCategory.SEEDING):
                tenant_result = self._create_system_tenant()
                if tenant_result['success']:
                    if tenant_result['created']:
                        result.add_created('tenant')
                        self.init_logger.info(LogCategory.SEEDING, f"Created system tenant: {tenant_result['tenant'].name}")
                    else:
                        result.add_skipped('tenant')
                        self.init_logger.info(LogCategory.SEEDING, f"System tenant already exists: {tenant_result['tenant'].name}")
                    
                    system_tenant = tenant_result['tenant']
                else:
                    result.success = False
                    result.add_error(f"Failed to create system tenant: {tenant_result['error']}")
                    self.init_logger.error(LogCategory.SEEDING, f"Failed to create system tenant: {tenant_result['error']}")
                    return result
            
            # Step 2: Create system roles
            with self.init_logger.step("Create System Roles", LogCategory.SEEDING):
                roles_result = self._create_system_roles(system_tenant.id)
                if roles_result['success']:
                    result.add_created('roles', roles_result['created_count'])
                    result.add_skipped('roles', roles_result['skipped_count'])
                    self.init_logger.info(
                        LogCategory.SEEDING, 
                        f"Created {roles_result['created_count']} roles, skipped {roles_result['skipped_count']} existing roles"
                    )
                else:
                    result.success = False
                    result.add_error(f"Failed to create system roles: {roles_result['error']}")
                    self.init_logger.error(LogCategory.SEEDING, f"Failed to create system roles: {roles_result['error']}")
                    return result
            
            # Step 3: Create admin user
            with self.init_logger.step("Create Admin User", LogCategory.SEEDING):
                admin_result = self._create_admin_user(system_tenant.id)
                if admin_result['success']:
                    if admin_result['created']:
                        result.add_created('admin_user')
                        self.init_logger.info(
                            LogCategory.SEEDING, 
                            f"Created admin user: {admin_result['user'].email}"
                        )
                    else:
                        result.add_skipped('admin_user')
                        self.init_logger.info(
                            LogCategory.SEEDING, 
                            f"Admin user already exists: {admin_result['user'].email}"
                        )
                else:
                    result.success = False
                    result.add_error(f"Failed to create admin user: {admin_result['error']}")
                    self.init_logger.error(LogCategory.SEEDING, f"Failed to create admin user: {admin_result['error']}")
                    return result
        
        except Exception as e:
            result.success = False
            result.add_error(f"Data seeding failed with exception: {str(e)}")
            self.init_logger.critical(
                LogCategory.SEEDING, 
                f"Data seeding failed with exception: {str(e)}", 
                error=e
            )
        
        finally:
            result.duration = time.time() - start_time
            
            # Log performance metrics
            self.init_logger.log_performance_metric("total_seeding_time", result.duration * 1000, "ms")
            
            # Finish logging
            self.init_logger.finish_initialization(result.success)
        
        return result
    
    def create_admin_user(self, tenant_id: Optional[int] = None) -> bool:
        """
        Create default admin user.
        
        Args:
            tenant_id: Tenant ID for the admin user. If None, uses system tenant.
            
        Returns:
            True if admin user was created or already exists, False on error
        """
        try:
            # Get or create system tenant if no tenant_id provided
            if tenant_id is None:
                tenant_result = self._create_system_tenant()
                if not tenant_result['success']:
                    self.logger.error(f"Failed to get system tenant: {tenant_result['error']}")
                    return False
                tenant_id = tenant_result['tenant'].id
            
            # Create admin user
            admin_result = self._create_admin_user(tenant_id)
            return admin_result['success']
            
        except Exception as e:
            self.logger.error(f"Failed to create admin user: {str(e)}", exc_info=True)
            return False
    
    def create_system_tenants(self) -> bool:
        """
        Create system tenants and roles.
        
        Returns:
            True if system tenants were created or already exist, False on error
        """
        try:
            # Create system tenant
            tenant_result = self._create_system_tenant()
            if not tenant_result['success']:
                self.logger.error(f"Failed to create system tenant: {tenant_result['error']}")
                return False
            
            # Create system roles
            roles_result = self._create_system_roles(tenant_result['tenant'].id)
            if not roles_result['success']:
                self.logger.error(f"Failed to create system roles: {roles_result['error']}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create system tenants: {str(e)}", exc_info=True)
            return False
    
    def validate_seed_data(self) -> bool:
        """
        Validate that seeded data exists and is correct.
        
        Returns:
            True if all seeded data is valid, False otherwise
        """
        try:
            # Check system tenant exists
            system_tenant = Tenant.query.filter_by(slug=self.default_tenant_slug).first()
            if not system_tenant:
                self.logger.error("System tenant not found")
                return False
            
            # Check admin user exists
            admin_user = User.query.filter_by(
                email=self.default_admin_email,
                tenant_id=system_tenant.id
            ).first()
            if not admin_user:
                self.logger.error("Admin user not found")
                return False
            
            # Check admin user can authenticate
            if not admin_user.check_password(self.default_admin_password):
                self.logger.error("Admin user password validation failed")
                return False
            
            # Check system roles exist
            required_roles = ['Owner', 'Manager', 'Support', 'Accounting', 'Read Only']
            for role_name in required_roles:
                role = Role.query.filter_by(name=role_name, tenant_id=system_tenant.id).first()
                if not role:
                    self.logger.error(f"System role '{role_name}' not found")
                    return False
            
            # Check admin user has owner role
            owner_role = Role.query.filter_by(name='Owner', tenant_id=system_tenant.id).first()
            if owner_role and not admin_user.has_role('Owner'):
                self.logger.error("Admin user does not have Owner role")
                return False
            
            self.logger.info("✅ All seeded data validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Seed data validation failed: {str(e)}", exc_info=True)
            return False
    
    def _create_system_tenant(self) -> Dict[str, Any]:
        """
        Create or get system tenant.
        
        Returns:
            Dictionary with success status, tenant object, and creation flag
        """
        try:
            # Check if system tenant already exists
            existing_tenant = Tenant.query.filter_by(slug=self.default_tenant_slug).first()
            if existing_tenant:
                return {
                    'success': True,
                    'tenant': existing_tenant,
                    'created': False
                }
            
            # Create new system tenant
            tenant = Tenant(
                name=self.default_tenant_name,
                slug=self.default_tenant_slug,
                email=self.default_admin_email,
                is_active=True,
                subscription_status='active',
                settings={
                    'system_tenant': True,
                    'created_by_seeder': True,
                    'created_at': datetime.now().isoformat()
                }
            )
            
            self.db.session.add(tenant)
            self.db.session.commit()
            
            return {
                'success': True,
                'tenant': tenant,
                'created': True
            }
            
        except IntegrityError as e:
            self.db.session.rollback()
            # Handle race condition - another process might have created the tenant
            existing_tenant = Tenant.query.filter_by(slug=self.default_tenant_slug).first()
            if existing_tenant:
                return {
                    'success': True,
                    'tenant': existing_tenant,
                    'created': False
                }
            else:
                return {
                    'success': False,
                    'error': f"Integrity error creating system tenant: {str(e)}"
                }
        except Exception as e:
            self.db.session.rollback()
            return {
                'success': False,
                'error': f"Failed to create system tenant: {str(e)}"
            }
    
    def _create_system_roles(self, tenant_id: int) -> Dict[str, Any]:
        """
        Create system roles for a tenant.
        
        Args:
            tenant_id: Tenant ID to create roles for
            
        Returns:
            Dictionary with success status and creation counts
        """
        try:
            created_count = 0
            skipped_count = 0
            
            # Check if roles already exist
            existing_roles = Role.query.filter_by(tenant_id=tenant_id, is_system_role=True).all()
            existing_role_names = {role.name for role in existing_roles}
            
            # Define system roles
            system_roles = [
                {
                    'name': 'Owner',
                    'description': 'Full access to all features and settings',
                    'permissions': [
                        'manage_users', 'manage_settings', 'manage_billing',
                        'manage_channels', 'manage_knowledge', 'manage_crm',
                        'manage_calendar', 'manage_kyb', 'view_analytics',
                        'manage_roles', 'view_audit_logs', 'manage_translations'
                    ]
                },
                {
                    'name': 'Manager',
                    'description': 'Management access to most features',
                    'permissions': [
                        'manage_users', 'manage_settings', 'manage_billing',
                        'manage_channels', 'manage_knowledge', 'manage_crm',
                        'manage_calendar', 'manage_kyb', 'view_analytics',
                        'manage_translations'
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
            
            # Create roles that don't exist
            for role_data in system_roles:
                if role_data['name'] in existing_role_names:
                    skipped_count += 1
                    continue
                
                role = Role(
                    tenant_id=tenant_id,
                    name=role_data['name'],
                    description=role_data['description'],
                    is_system_role=True,
                    is_active=True
                )
                role.set_permissions(role_data['permissions'])
                
                self.db.session.add(role)
                created_count += 1
            
            if created_count > 0:
                self.db.session.commit()
            
            return {
                'success': True,
                'created_count': created_count,
                'skipped_count': skipped_count
            }
            
        except Exception as e:
            self.db.session.rollback()
            return {
                'success': False,
                'error': f"Failed to create system roles: {str(e)}",
                'created_count': 0,
                'skipped_count': 0
            }
    
    def _create_admin_user(self, tenant_id: int) -> Dict[str, Any]:
        """
        Create admin user for a tenant.
        
        Args:
            tenant_id: Tenant ID to create admin user for
            
        Returns:
            Dictionary with success status, user object, and creation flag
        """
        try:
            # Check if admin user already exists
            existing_user = User.query.filter_by(
                email=self.default_admin_email,
                tenant_id=tenant_id
            ).first()
            
            if existing_user:
                # Ensure existing user has correct role
                owner_role = Role.query.filter_by(name='Owner', tenant_id=tenant_id).first()
                if owner_role and not existing_user.has_role('Owner'):
                    existing_user.add_role(owner_role)
                    existing_user.save()
                
                return {
                    'success': True,
                    'user': existing_user,
                    'created': False
                }
            
            # Create new admin user
            admin_user = User(
                tenant_id=tenant_id,
                email=self.default_admin_email,
                first_name="System",
                last_name="Administrator",
                role='owner',  # Keep for backward compatibility
                is_active=True,
                is_email_verified=True,
                language='en',
                timezone='UTC'
            )
            admin_user.set_password(self.default_admin_password)
            
            self.db.session.add(admin_user)
            self.db.session.flush()  # Get the user ID
            
            # Assign Owner role
            owner_role = Role.query.filter_by(name='Owner', tenant_id=tenant_id).first()
            if owner_role:
                admin_user.add_role(owner_role)
            
            self.db.session.commit()
            
            return {
                'success': True,
                'user': admin_user,
                'created': True
            }
            
        except IntegrityError as e:
            self.db.session.rollback()
            # Handle race condition - another process might have created the user
            existing_user = User.query.filter_by(
                email=self.default_admin_email,
                tenant_id=tenant_id
            ).first()
            if existing_user:
                return {
                    'success': True,
                    'user': existing_user,
                    'created': False
                }
            else:
                return {
                    'success': False,
                    'error': f"Integrity error creating admin user: {str(e)}"
                }
        except Exception as e:
            self.db.session.rollback()
            return {
                'success': False,
                'error': f"Failed to create admin user: {str(e)}"
            }
    
    def get_seeding_status(self) -> Dict[str, Any]:
        """
        Get current data seeding status.
        
        Returns:
            Dictionary with seeding status details
        """
        status = {
            'system_tenant_exists': False,
            'admin_user_exists': False,
            'system_roles_exist': False,
            'seeding_complete': False,
            'validation_passed': False
        }
        
        try:
            # Check system tenant
            system_tenant = Tenant.query.filter_by(slug=self.default_tenant_slug).first()
            status['system_tenant_exists'] = system_tenant is not None
            
            if system_tenant:
                # Check admin user
                admin_user = User.query.filter_by(
                    email=self.default_admin_email,
                    tenant_id=system_tenant.id
                ).first()
                status['admin_user_exists'] = admin_user is not None
                
                # Check system roles
                system_roles = Role.query.filter_by(
                    tenant_id=system_tenant.id,
                    is_system_role=True
                ).count()
                status['system_roles_exist'] = system_roles >= 5  # At least 5 system roles
                
                # Overall seeding status
                status['seeding_complete'] = (
                    status['system_tenant_exists'] and
                    status['admin_user_exists'] and
                    status['system_roles_exist']
                )
                
                # Validation status
                if status['seeding_complete']:
                    status['validation_passed'] = self.validate_seed_data()
        
        except Exception as e:
            self.logger.error(f"Failed to get seeding status: {str(e)}", exc_info=True)
        
        return status
    
    def reset_seed_data(self) -> bool:
        """
        Reset all seeded data (for development/testing only).
        
        Returns:
            True if reset successful, False otherwise
        """
        if not self.app.debug and not self.app.testing:
            self.logger.error("Reset seed data is only allowed in debug or testing mode")
            return False
        
        try:
            # Find system tenant
            system_tenant = Tenant.query.filter_by(slug=self.default_tenant_slug).first()
            if not system_tenant:
                self.logger.info("No system tenant found to reset")
                return True
            
            # Delete admin user
            admin_user = User.query.filter_by(
                email=self.default_admin_email,
                tenant_id=system_tenant.id
            ).first()
            if admin_user:
                self.db.session.delete(admin_user)
            
            # Delete system roles
            system_roles = Role.query.filter_by(
                tenant_id=system_tenant.id,
                is_system_role=True
            ).all()
            for role in system_roles:
                self.db.session.delete(role)
            
            # Delete system tenant
            self.db.session.delete(system_tenant)
            
            self.db.session.commit()
            
            self.logger.info("✅ Seed data reset completed")
            return True
            
        except Exception as e:
            self.db.session.rollback()
            self.logger.error(f"Failed to reset seed data: {str(e)}", exc_info=True)
            return False