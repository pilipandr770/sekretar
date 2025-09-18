#!/usr/bin/env python3
"""
CLI command for data seeding operations

This module provides command-line interface for database data seeding
operations using the DataSeeder class.
"""
import click
from flask import current_app
from flask.cli import with_appcontext

from app.services.data_seeder import DataSeeder, SeedData
from app.models.tenant import Tenant


@click.group()
def seed():
    """Database seeding commands."""
    pass


@seed.command()
@click.option('--admin-email', default='admin@ai-secretary.com', 
              help='Admin user email address')
@click.option('--admin-password', default='admin123', 
              help='Admin user password')
@click.option('--tenant-name', default='Default Tenant', 
              help='Default tenant name')
@click.option('--tenant-slug', default='default', 
              help='Default tenant slug')
@click.option('--tenant-domain', default='localhost', 
              help='Default tenant domain')
@with_appcontext
def init(admin_email, admin_password, tenant_name, tenant_slug, tenant_domain):
    """Initialize database with seed data."""
    click.echo("🌱 Initializing database with seed data...")
    
    # Create seed configuration
    seed_config = SeedData(
        admin_email=admin_email,
        admin_password=admin_password,
        admin_first_name="Admin",
        admin_last_name="User",
        default_tenant_name=tenant_name,
        default_tenant_domain=tenant_domain,
        default_tenant_slug=tenant_slug
    )
    
    # Initialize seeder
    seeder = DataSeeder(app=current_app, seed_config=seed_config)
    
    # Run seeding
    result = seeder.seed_initial_data()
    
    if result.success:
        click.echo("✅ Database seeding completed successfully!")
        
        if result.records_created:
            click.echo("📊 Records created:")
            for record_type, count in result.records_created.items():
                click.echo(f"   • {record_type}: {count}")
        
        if result.records_skipped:
            click.echo("⏭️ Records skipped (already exist):")
            for record_type, count in result.records_skipped.items():
                click.echo(f"   • {record_type}: {count}")
        
        if result.warnings:
            click.echo("⚠️ Warnings:")
            for warning in result.warnings:
                click.echo(f"   • {warning}")
        
        click.echo(f"⏱️ Duration: {result.duration:.2f}s")
        
        # Show login information
        click.echo("\n" + "=" * 60)
        click.echo("🔑 Login Information:")
        click.echo(f"📧 Email: {admin_email}")
        click.echo(f"🔐 Password: {admin_password}")
        click.echo(f"🏢 Tenant: {tenant_name}")
        click.echo("=" * 60)
        
    else:
        click.echo("❌ Database seeding failed!")
        if result.errors:
            click.echo("Errors:")
            for error in result.errors:
                click.echo(f"   • {error}")


@seed.command()
@click.option('--tenant-id', type=int, help='Tenant ID to check status for')
@with_appcontext
def status(tenant_id):
    """Check seeding status."""
    click.echo("📊 Checking seeding status...")
    
    seeder = DataSeeder(app=current_app)
    status_info = seeder.get_seeding_status(tenant_id)
    
    click.echo(f"Seeding complete: {'✅' if status_info['seeding_complete'] else '❌'}")
    click.echo(f"Tenant exists: {'✅' if status_info['tenant_exists'] else '❌'}")
    click.echo(f"Tenant active: {'✅' if status_info['tenant_active'] else '❌'}")
    click.echo(f"Admin user exists: {'✅' if status_info['admin_user_exists'] else '❌'}")
    click.echo(f"Admin user active: {'✅' if status_info['admin_user_active'] else '❌'}")
    click.echo(f"Admin has owner role: {'✅' if status_info['admin_has_owner_role'] else '❌'}")
    click.echo(f"System roles created: {status_info['roles_created']}")
    
    if status_info['issues']:
        click.echo("\n❌ Issues found:")
        for issue in status_info['issues']:
            click.echo(f"   • {issue}")


@seed.command()
@click.option('--tenant-id', type=int, help='Tenant ID to validate')
@with_appcontext
def validate(tenant_id):
    """Validate seed data integrity."""
    click.echo("🔍 Validating seed data...")
    
    seeder = DataSeeder(app=current_app)
    is_valid = seeder.validate_seed_data(tenant_id)
    
    if is_valid:
        click.echo("✅ Seed data validation passed!")
    else:
        click.echo("❌ Seed data validation failed!")


@seed.command()
@click.option('--tenant-id', type=int, required=True, help='Tenant ID to reset')
@click.option('--confirm', is_flag=True, help='Confirm the reset operation')
@with_appcontext
def reset(tenant_id, confirm):
    """Reset seed data for a tenant."""
    if not confirm:
        click.echo("⚠️ This will delete and recreate all seed data for the tenant!")
        click.echo("Use --confirm flag to proceed.")
        return
    
    click.echo(f"🔄 Resetting seed data for tenant {tenant_id}...")
    
    seeder = DataSeeder(app=current_app)
    success = seeder.reset_seed_data(tenant_id, confirm=True)
    
    if success:
        click.echo("✅ Seed data reset completed successfully!")
    else:
        click.echo("❌ Seed data reset failed!")


@seed.command()
@with_appcontext
def list_tenants():
    """List all tenants."""
    click.echo("🏢 Available tenants:")
    
    tenants = Tenant.query.all()
    
    if not tenants:
        click.echo("   No tenants found.")
        return
    
    for tenant in tenants:
        status = "✅ Active" if tenant.is_active else "❌ Inactive"
        click.echo(f"   • ID: {tenant.id}, Name: {tenant.name}, Slug: {tenant.slug} ({status})")


@seed.command()
@click.option('--admin-email', default='admin@ai-secretary.com', 
              help='Admin user email address')
@click.option('--admin-password', default='admin123', 
              help='Admin user password')
@click.option('--tenant-id', type=int, help='Tenant ID to create admin for')
@with_appcontext
def create_admin(admin_email, admin_password, tenant_id):
    """Create admin user only."""
    click.echo("👤 Creating admin user...")
    
    # Create seed configuration
    seed_config = SeedData(
        admin_email=admin_email,
        admin_password=admin_password,
        admin_first_name="Admin",
        admin_last_name="User"
    )
    
    seeder = DataSeeder(app=current_app, seed_config=seed_config)
    success = seeder.create_admin_user(tenant_id)
    
    if success:
        click.echo("✅ Admin user created successfully!")
        click.echo(f"📧 Email: {admin_email}")
        click.echo(f"🔐 Password: {admin_password}")
    else:
        click.echo("❌ Failed to create admin user!")


@seed.command()
@with_appcontext
def create_tenants():
    """Create system tenants only."""
    click.echo("🏢 Creating system tenants...")
    
    seeder = DataSeeder(app=current_app)
    success = seeder.create_system_tenants()
    
    if success:
        click.echo("✅ System tenants created successfully!")
    else:
        click.echo("❌ Failed to create system tenants!")


# Register commands with Flask CLI
def init_app(app):
    """Initialize CLI commands with Flask app."""
    app.cli.add_command(seed)