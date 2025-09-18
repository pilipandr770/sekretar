"""
Data Seeding System for Database Initialization

This module provides comprehensive data seeding functionality including:
- Initial data creation logic for essential system data
- Admin user creation with default credentials
- System tenant and role seeding functionality
- Duplicate data detection to skip existing records during seeding
"""

import logging
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from werkzeug.security import generate_password_hash

from app import db
from app.models.user import User
from app.models.tenant import Tenant
from app.models.role import Role
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


@dataclass
class SeedingResult:
    """Result of data seeding operation."""
    success: bool
    records_created: Dict[str, int]
    records_skipped: Dict[str, int]
    errors: List[str]
    warnings: List[str]
    duration: float = 0.0

    def __post_init__(self):
        if self.records_created is None:
            self.records_created = {}
        if self.records_skipped is None:
            self.records_skipped = {}
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


@dataclass
class SeedData:
    """Configuration for seed data."""
    admin_email: str = "admin@ai-secretary.com"
    admin_password: str = "admin123"
    admin_first_name: str = "Admin"
    admin_last_name: str = "User"
    default_tenant_name: str = "Default Tenant"
    default_tenant_domain: str = "localhost"
    default_tenant_slug: str = "default"


class DataSeeder:
    """
    Handles database data seeding operations.
    
    Provides functionality for:
    - Creating essential initial data
    - Admin user creation with secure defaults
    - System tenant and role creation
    - Duplicate detection and skipping
    - Data validation after seeding
    """

    def __init__(self, app: Flask = None, seed_config: SeedData = None):
        """
        Initialize DataSeeder.
        
        Args:
            app: Flask application instance
            seed_config: Configuration for seed data
        """
        self.app = app
        self.seed_config = seed_config or SeedData()
        
    def seed_initial_data(self) -> SeedingResult:
        """
        Seed all initial data required for application functionality.
        
        Returns:
            SeedingResult with operation details
        """
        start_time = datetime.now()
        result = SeedingResult(
            success=False,
            records_created={},
            records_skipped={},
            errors=[],
            warnings=[]
        )
        
        try:
            logger.info("🌱 Starting initial data seeding...")
            
            # Step 1: Create system tenant
            tenant_result = self._create_system_tenant()
            if not tenant_result[0]:
                result.errors.append(f"Failed to create system tenant: {tenant_result[1]}")
                return result
            
            tenant, tenant_created = tenant_result[1], tenant_result[2]
            if tenant_created:
                result.records_created['tenants'] = result.records_created.get('tenants', 0) + 1
                logger.info(f"✅ Created system tenant: {tenant.name}")
            else:
                result.records_skipped['tenants'] = result.records_skipped.get('tenants', 0) + 1
                logger.info(f"⏭️ System tenant already exists: {tenant.name}")
            
            # Step 2: Create system roles for the tenant
            roles_result = self._create_system_roles(tenant.id)
            if not roles_result[0]:
                result.errors.append(f"Failed to create system roles: {roles_result[1]}")
                return result
            
            roles_created, roles_skipped = roles_result[1], roles_result[2]
            result.records_created['roles'] = roles_created
            result.records_skipped['roles'] = roles_skipped
            
            if roles_created > 0:
                logger.info(f"✅ Created {roles_created} system roles")
            if roles_skipped > 0:
                logger.info(f"⏭️ Skipped {roles_skipped} existing roles")
            
            # Step 3: Create admin user
            admin_result = self._create_admin_user(tenant.id)
            if not admin_result[0]:
                result.errors.append(f"Failed to create admin user: {admin_result[1]}")
                return result
            
            admin_user, admin_created = admin_result[1], admin_result[2]
            if admin_created:
                result.records_created['users'] = result.records_created.get('users', 0) + 1
                logger.info(f"✅ Created admin user: {admin_user.email}")
            else:
                result.records_skipped['users'] = result.records_skipped.get('users', 0) + 1
                logger.info(f"⏭️ Admin user already exists: {admin_user.email}")
            
            # Step 4: Assign owner role to admin user
            if admin_created or not admin_user.has_role('Owner'):
                role_assignment_result = self._assign_owner_role(admin_user, tenant.id)
                if not role_assignment_result[0]:
                    result.warnings.append(f"Failed to assign owner role: {role_assignment_result[1]}")
                else:
                    logger.info("✅ Assigned Owner role to admin user")
            
            # Step 5: Validate seeded data
            validation_result = self._validate_seed_data(tenant.id)
            if not validation_result[0]:
                result.warnings.append(f"Data validation issues: {validation_result[1]}")
            else:
                logger.info("✅ Seed data validation passed")
            
            result.success = True
            logger.info("🎉 Initial data seeding completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Data seeding failed: {e}")
            result.errors.append(str(e))
            result.success = False
            
        finally:
            result.duration = (datetime.now() - start_time).total_seconds()
            
        return result

    def create_admin_user(self, tenant_id: int = None) -> bool:
        """
        Create admin user with default credentials.
        
        Args:
            tenant_id: ID of tenant to create admin user for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not tenant_id:
                # Find or create default tenant
                tenant_result = self._create_system_tenant()
                if not tenant_result[0]:
                    logger.error(f"Failed to get/create tenant: {tenant_result[1]}")
                    return False
                tenant_id = tenant_result[1].id
            
            admin_result = self._create_admin_user(tenant_id)
            if admin_result[0]:
                admin_user, created = admin_result[1], admin_result[2]
                if created:
                    logger.info(f"✅ Created admin user: {admin_user.email}")
                else:
                    logger.info(f"⏭️ Admin user already exists: {admin_user.email}")
                return True
            else:
                logger.error(f"Failed to create admin user: {admin_result[1]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to create admin user: {e}")
            return False

    def create_system_tenants(self) -> bool:
        """
        Create system tenants and associated data.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            tenant_result = self._create_system_tenant()
            if tenant_result[0]:
                tenant, created = tenant_result[1], tenant_result[2]
                if created:
                    logger.info(f"✅ Created system tenant: {tenant.name}")
                    
                    # Create roles for the tenant
                    roles_result = self._create_system_roles(tenant.id)
                    if roles_result[0]:
                        roles_created = roles_result[1]
                        logger.info(f"✅ Created {roles_created} system roles")
                    else:
                        logger.warning(f"Failed to create system roles: {roles_result[1]}")
                else:
                    logger.info(f"⏭️ System tenant already exists: {tenant.name}")
                return True
            else:
                logger.error(f"Failed to create system tenant: {tenant_result[1]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to create system tenants: {e}")
            return False

    def validate_seed_data(self, tenant_id: int = None) -> bool:
        """
        Validate that seeded data exists and is correct.
        
        Args:
            tenant_id: ID of tenant to validate (optional)
            
        Returns:
            True if validation passes, False otherwise
        """
        try:
            if tenant_id:
                validation_result = self._validate_seed_data(tenant_id)
                return validation_result[0]
            else:
                # Validate default tenant
                tenant = Tenant.query.filter_by(slug=self.seed_config.default_tenant_slug).first()
                if not tenant:
                    logger.error("Default tenant not found")
                    return False
                
                validation_result = self._validate_seed_data(tenant.id)
                return validation_result[0]
                
        except Exception as e:
            logger.error(f"❌ Failed to validate seed data: {e}")
            return False

    def _create_system_tenant(self) -> Tuple[bool, Any, bool]:
        """
        Create or get system tenant.
        
        Returns:
            Tuple of (success, tenant_or_error_message, created)
        """
        try:
            # Check if tenant already exists
            existing_tenant = Tenant.query.filter_by(
                slug=self.seed_config.default_tenant_slug
            ).first()
            
            if existing_tenant:
                return True, existing_tenant, False
            
            # Create new tenant
            tenant = Tenant(
                name=self.seed_config.default_tenant_name,
                domain=self.seed_config.default_tenant_domain,
                slug=self.seed_config.default_tenant_slug,
                is_active=True,
                subscription_status='active'  # Set as active for system tenant
            )
            
            db.session.add(tenant)
            db.session.commit()
            
            return True, tenant, True
            
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Integrity error creating tenant: {e}")
            return False, f"Tenant with slug '{self.seed_config.default_tenant_slug}' already exists", False
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error creating tenant: {e}")
            return False, str(e), False
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Unexpected error creating tenant: {e}")
            return False, str(e), False

    def _create_system_roles(self, tenant_id: int) -> Tuple[bool, int, int]:
        """
        Create system roles for tenant.
        
        Args:
            tenant_id: ID of tenant to create roles for
            
        Returns:
            Tuple of (success, roles_created_count, roles_skipped_count)
        """
        try:
            # Check existing roles
            existing_roles = Role.query.filter_by(
                tenant_id=tenant_id,
                is_system_role=True
            ).all()
            
            existing_role_names = {role.name for role in existing_roles}
            
            # Define system roles
            system_roles_data = [
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
            
            roles_created = 0
            roles_skipped = 0
            
            for role_data in system_roles_data:
                if role_data['name'] in existing_role_names:
                    roles_skipped += 1
                    continue
                
                role = Role(
                    tenant_id=tenant_id,
                    name=role_data['name'],
                    description=role_data['description'],
                    is_system_role=True,
                    is_active=True
                )
                role.set_permissions(role_data['permissions'])
                
                db.session.add(role)
                roles_created += 1
            
            if roles_created > 0:
                db.session.commit()
            
            return True, roles_created, roles_skipped
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error creating system roles: {e}")
            return False, 0, 0
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Unexpected error creating system roles: {e}")
            return False, 0, 0

    def _create_admin_user(self, tenant_id: int) -> Tuple[bool, Any, bool]:
        """
        Create admin user for tenant.
        
        Args:
            tenant_id: ID of tenant to create admin user for
            
        Returns:
            Tuple of (success, user_or_error_message, created)
        """
        try:
            # Check if admin user already exists
            existing_user = User.query.filter_by(
                email=self.seed_config.admin_email,
                tenant_id=tenant_id
            ).first()
            
            if existing_user:
                return True, existing_user, False
            
            # Create admin user
            admin_user = User(
                tenant_id=tenant_id,
                email=self.seed_config.admin_email,
                password_hash=generate_password_hash(self.seed_config.admin_password),
                first_name=self.seed_config.admin_first_name,
                last_name=self.seed_config.admin_last_name,
                role='owner',  # Legacy role field for backward compatibility
                is_active=True,
                is_email_verified=True,  # Pre-verify admin user
                language='en',
                timezone='UTC'
            )
            
            db.session.add(admin_user)
            db.session.commit()
            
            return True, admin_user, True
            
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Integrity error creating admin user: {e}")
            return False, f"User with email '{self.seed_config.admin_email}' already exists", False
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error creating admin user: {e}")
            return False, str(e), False
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Unexpected error creating admin user: {e}")
            return False, str(e), False

    def _assign_owner_role(self, user: User, tenant_id: int) -> Tuple[bool, str]:
        """
        Assign Owner role to user.
        
        Args:
            user: User to assign role to
            tenant_id: ID of tenant
            
        Returns:
            Tuple of (success, error_message_if_failed)
        """
        try:
            # Find Owner role
            owner_role = Role.query.filter_by(
                name='Owner',
                tenant_id=tenant_id,
                is_system_role=True
            ).first()
            
            if not owner_role:
                return False, "Owner role not found"
            
            # Check if user already has the role
            if user.has_role('Owner'):
                return True, "User already has Owner role"
            
            # Assign role
            user.add_role(owner_role)
            db.session.commit()
            
            return True, ""
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error assigning owner role: {e}")
            return False, str(e)
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Unexpected error assigning owner role: {e}")
            return False, str(e)

    def _validate_seed_data(self, tenant_id: int) -> Tuple[bool, str]:
        """
        Validate that all required seed data exists.
        
        Args:
            tenant_id: ID of tenant to validate
            
        Returns:
            Tuple of (success, error_message_if_failed)
        """
        try:
            issues = []
            
            # Validate tenant exists
            tenant = Tenant.query.get(tenant_id)
            if not tenant:
                issues.append(f"Tenant with ID {tenant_id} not found")
            elif not tenant.is_active:
                issues.append(f"Tenant {tenant.name} is not active")
            
            # Validate system roles exist
            expected_roles = ['Owner', 'Manager', 'Support', 'Accounting', 'Read Only']
            existing_roles = Role.query.filter_by(
                tenant_id=tenant_id,
                is_system_role=True
            ).all()
            
            existing_role_names = {role.name for role in existing_roles}
            missing_roles = set(expected_roles) - existing_role_names
            
            if missing_roles:
                issues.append(f"Missing system roles: {', '.join(missing_roles)}")
            
            # Validate admin user exists
            admin_user = User.query.filter_by(
                email=self.seed_config.admin_email,
                tenant_id=tenant_id
            ).first()
            
            if not admin_user:
                issues.append(f"Admin user {self.seed_config.admin_email} not found")
            else:
                if not admin_user.is_active:
                    issues.append("Admin user is not active")
                if not admin_user.is_email_verified:
                    issues.append("Admin user email is not verified")
                if not admin_user.has_role('Owner'):
                    issues.append("Admin user does not have Owner role")
                
                # Test password
                if not admin_user.check_password(self.seed_config.admin_password):
                    issues.append("Admin user password is incorrect")
            
            if issues:
                return False, "; ".join(issues)
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Error validating seed data: {e}")
            return False, str(e)

    def get_seeding_status(self, tenant_id: int = None) -> Dict[str, Any]:
        """
        Get current seeding status for a tenant.
        
        Args:
            tenant_id: ID of tenant to check (optional)
            
        Returns:
            Dictionary with seeding status information
        """
        status = {
            'tenant_exists': False,
            'tenant_active': False,
            'roles_created': 0,
            'admin_user_exists': False,
            'admin_user_active': False,
            'admin_has_owner_role': False,
            'seeding_complete': False,
            'issues': []
        }
        
        try:
            # If no tenant_id provided, use default
            if not tenant_id:
                tenant = Tenant.query.filter_by(
                    slug=self.seed_config.default_tenant_slug
                ).first()
                if tenant:
                    tenant_id = tenant.id
                else:
                    status['issues'].append("Default tenant not found")
                    return status
            
            # Check tenant
            tenant = Tenant.query.get(tenant_id)
            if tenant:
                status['tenant_exists'] = True
                status['tenant_active'] = tenant.is_active
            else:
                status['issues'].append(f"Tenant with ID {tenant_id} not found")
                return status
            
            # Check roles
            roles = Role.query.filter_by(
                tenant_id=tenant_id,
                is_system_role=True
            ).count()
            status['roles_created'] = roles
            
            # Check admin user
            admin_user = User.query.filter_by(
                email=self.seed_config.admin_email,
                tenant_id=tenant_id
            ).first()
            
            if admin_user:
                status['admin_user_exists'] = True
                status['admin_user_active'] = admin_user.is_active
                status['admin_has_owner_role'] = admin_user.has_role('Owner')
            
            # Determine if seeding is complete
            status['seeding_complete'] = (
                status['tenant_exists'] and
                status['tenant_active'] and
                status['roles_created'] >= 5 and  # Expected number of system roles
                status['admin_user_exists'] and
                status['admin_user_active'] and
                status['admin_has_owner_role']
            )
            
        except Exception as e:
            logger.error(f"Error getting seeding status: {e}")
            status['issues'].append(str(e))
            
        return status

    def reset_seed_data(self, tenant_id: int, confirm: bool = False) -> bool:
        """
        Reset (delete and recreate) seed data for a tenant.
        
        Args:
            tenant_id: ID of tenant to reset
            confirm: Confirmation flag to prevent accidental deletion
            
        Returns:
            True if successful, False otherwise
        """
        if not confirm:
            logger.warning("Reset operation requires confirmation flag")
            return False
        
        try:
            logger.info(f"🔄 Resetting seed data for tenant {tenant_id}...")
            
            # Delete admin user
            admin_user = User.query.filter_by(
                email=self.seed_config.admin_email,
                tenant_id=tenant_id
            ).first()
            
            if admin_user:
                db.session.delete(admin_user)
                logger.info("🗑️ Deleted admin user")
            
            # Delete system roles
            system_roles = Role.query.filter_by(
                tenant_id=tenant_id,
                is_system_role=True
            ).all()
            
            for role in system_roles:
                db.session.delete(role)
            
            if system_roles:
                logger.info(f"🗑️ Deleted {len(system_roles)} system roles")
            
            db.session.commit()
            
            # Recreate seed data
            seeding_result = self.seed_initial_data()
            
            if seeding_result.success:
                logger.info("✅ Seed data reset completed successfully")
                return True
            else:
                logger.error(f"❌ Failed to recreate seed data: {seeding_result.errors}")
                return False
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Failed to reset seed data: {e}")
            return False