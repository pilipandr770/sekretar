#!/usr/bin/env python3
"""
CLI commands for database initialization and management

This module provides command-line interface for database initialization,
health checking, repair, and reset operations using the DatabaseInitializer
and related components.
"""
import click
import sys
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import text

from app.utils.database_initializer import DatabaseInitializer
from app.utils.health_validator import HealthValidator
from app.services.data_seeder import DataSeeder


@click.group()
def database():
    """Database initialization and management commands."""
    pass


@database.command()
@click.option('--force', is_flag=True, help='Force initialization even if database exists')
@click.option('--skip-seeding', is_flag=True, help='Skip data seeding during initialization')
@click.option('--admin-email', default='admin@ai-secretary.com', 
              help='Admin user email address')
@click.option('--admin-password', default='admin123', 
              help='Admin user password')
@with_appcontext
def init(force, skip_seeding, admin_email, admin_password):
    """Initialize database with schema, migrations, and seed data."""
    click.echo("🚀 Starting database initialization...")
    
    try:
        # Import here to avoid circular imports
        from app import db
        
        # Initialize the database initializer
        initializer = DatabaseInitializer(current_app, db)
        
        # Check if database is already initialized
        if not force:
            status = initializer.get_initialization_status()
            if status.get('schema_exists', False):
                click.echo("⚠️ Database appears to be already initialized.")
                click.echo("Use --force flag to reinitialize.")
                return
        
        # Run initialization
        click.echo("📋 Running database initialization...")
        result = initializer.initialize()
        
        if result.success:
            click.echo("✅ Database initialization completed successfully!")
            
            # Show completed steps
            if result.steps_completed:
                click.echo("📊 Steps completed:")
                for step in result.steps_completed:
                    click.echo(f"   • {step}")
            
            # Show warnings if any
            if result.warnings:
                click.echo("⚠️ Warnings:")
                for warning in result.warnings:
                    click.echo(f"   • {warning}")
            
            click.echo(f"⏱️ Duration: {result.duration:.2f}s")
            click.echo(f"🗄️ Database type: {result.database_type}")
            
            # Show login information if seeding was performed
            if not skip_seeding:
                click.echo("\n" + "=" * 60)
                click.echo("🔑 Login Information:")
                click.echo(f"📧 Email: {admin_email}")
                click.echo(f"🔐 Password: {admin_password}")
                click.echo("=" * 60)
            
        else:
            click.echo("❌ Database initialization failed!")
            if result.errors:
                click.echo("Errors:")
                for error in result.errors:
                    click.echo(f"   • {error}")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Initialization failed with exception: {str(e)}")
        sys.exit(1)


@database.command()
@click.option('--detailed', is_flag=True, help='Show detailed health information')
@click.option('--performance', is_flag=True, help='Include performance metrics')
@with_appcontext
def health(detailed, performance):
    """Check database health and connectivity."""
    click.echo("🏥 Checking database health...")
    
    try:
        # Import here to avoid circular imports
        from app import db
        
        # Initialize health validator
        validator = HealthValidator(current_app, db)
        
        # Run comprehensive health check
        result = validator.run_comprehensive_health_check()
        
        # Show basic health status
        status_icon = "✅" if result.status.name == "HEALTHY" else "⚠️" if result.status.name == "WARNING" else "❌"
        click.echo(f"Overall Status: {status_icon} {result.status.name}")
        total_checks = result.checks_passed + result.checks_failed
        click.echo(f"Checks Passed: {result.checks_passed}/{total_checks}")
        
        # Show connectivity status
        connectivity_ok = validator.validate_connectivity()
        conn_icon = "✅" if connectivity_ok else "❌"
        click.echo(f"Database Connectivity: {conn_icon}")
        
        # Show detailed information if requested
        if detailed:
            click.echo("\n📋 Detailed Health Report:")
            
            # Schema integrity
            schema_result = validator.validate_schema_integrity()
            schema_icon = "✅" if schema_result.valid else "❌"
            click.echo(f"Schema Integrity: {schema_icon}")
            
            if not schema_result.valid and schema_result.issues:
                click.echo("   Issues:")
                for issue in schema_result.issues:
                    click.echo(f"     • {issue}")
            
            # Data integrity
            data_result = validator.validate_data_integrity()
            data_icon = "✅" if data_result.valid else "❌"
            click.echo(f"Data Integrity: {data_icon}")
            
            if not data_result.valid and data_result.issues:
                click.echo("   Issues:")
                for issue in data_result.issues:
                    click.echo(f"     • {issue}")
        
        # Show performance metrics if requested
        if performance:
            health_report = validator.generate_health_report()
            perf_metrics = health_report.get('performance_metrics', {})
            
            if perf_metrics:
                click.echo("\n📊 Performance Metrics:")
                click.echo(f"   • Connection Pool Size: {perf_metrics.get('connection_pool_size', 'N/A')}")
                click.echo(f"   • Active Connections: {perf_metrics.get('active_connections', 'N/A')}")
                click.echo(f"   • Query Response Time: {perf_metrics.get('query_response_time', 'N/A')}ms")
        
        # Show suggestions if any issues found
        if result.status.name != "HEALTHY":
            click.echo("\n💡 Suggestions:")
            if hasattr(result, 'suggestions') and result.suggestions:
                for suggestion in result.suggestions:
                    click.echo(f"   • {suggestion}")
            else:
                click.echo("   • Run 'flask database repair' to attempt automatic fixes")
                click.echo("   • Check database logs for more details")
        
    except Exception as e:
        click.echo(f"❌ Health check failed: {str(e)}")
        sys.exit(1)


@database.command()
@click.option('--auto-fix', is_flag=True, help='Automatically attempt to fix issues')
@click.option('--dry-run', is_flag=True, help='Show what would be repaired without making changes')
@with_appcontext
def repair(auto_fix, dry_run):
    """Repair common database issues."""
    click.echo("🔧 Checking for database issues to repair...")
    
    try:
        # Import here to avoid circular imports
        from app import db
        
        # Initialize components
        initializer = DatabaseInitializer(current_app, db)
        validator = HealthValidator(current_app, db)
        
        # First, run health check to identify issues
        health_result = validator.run_comprehensive_health_check()
        
        if health_result.status.name == "HEALTHY":
            click.echo("✅ Database is healthy - no repairs needed!")
            return
        
        click.echo(f"Found issues with status: {health_result.status.name}")
        
        # Get detailed validation results
        schema_result = validator.validate_schema_integrity()
        data_result = validator.validate_data_integrity()
        
        issues_found = []
        
        # Collect schema issues
        if not schema_result.valid:
            issues_found.extend(schema_result.issues)
        
        # Collect data issues
        if not data_result.valid:
            issues_found.extend(data_result.issues)
        
        if not issues_found:
            click.echo("✅ No specific issues identified for repair.")
            return
        
        click.echo(f"📋 Found {len(issues_found)} issues:")
        for i, issue in enumerate(issues_found, 1):
            click.echo(f"   {i}. {issue}")
        
        if dry_run:
            click.echo("\n🔍 Dry run mode - showing potential repairs:")
            click.echo("   • Would attempt to recreate missing tables")
            click.echo("   • Would reseed missing system data")
            click.echo("   • Would repair orphaned records")
            click.echo("Use --auto-fix to perform actual repairs.")
            return
        
        if not auto_fix:
            click.echo("\n⚠️ Use --auto-fix flag to attempt automatic repairs.")
            click.echo("Or use --dry-run to see what would be repaired.")
            return
        
        # Attempt repairs
        click.echo("\n🔧 Attempting automatic repairs...")
        
        repair_result = initializer.repair_if_needed()
        
        if repair_result.success:
            click.echo("✅ Database repair completed successfully!")
            if repair_result.repairs_performed:
                click.echo("🔧 Repairs performed:")
                for repair in repair_result.repairs_performed:
                    click.echo(f"   • {repair}")
        else:
            click.echo("❌ Database repair failed!")
            if repair_result.errors:
                click.echo("Errors:")
                for error in repair_result.errors:
                    click.echo(f"   • {error}")
            
            # Show manual repair suggestions
            if repair_result.manual_steps:
                click.echo("\n📝 Manual repair steps required:")
                for step in repair_result.manual_steps:
                    click.echo(f"   • {step}")
        
    except Exception as e:
        click.echo(f"❌ Repair operation failed: {str(e)}")
        sys.exit(1)


@database.command()
@click.option('--confirm', is_flag=True, help='Confirm the reset operation')
@click.option('--keep-data', is_flag=True, help='Keep user data, only reset schema')
@with_appcontext
def reset(confirm, keep_data):
    """Reset database for development environments."""
    # Safety check - only allow in development
    if current_app.config.get('ENV') == 'production':
        click.echo("❌ Database reset is not allowed in production environment!")
        sys.exit(1)
    
    if not confirm:
        click.echo("⚠️ This will completely reset the database!")
        click.echo("All data will be lost unless --keep-data is specified.")
        click.echo("Use --confirm flag to proceed.")
        return
    
    click.echo("🔄 Resetting database...")
    
    try:
        # Import here to avoid circular imports
        from app import db
        
        if keep_data:
            click.echo("📊 Keeping user data, resetting schema only...")
            # TODO: Implement selective reset that preserves user data
            click.echo("⚠️ Selective reset not yet implemented. Use full reset.")
            return
        
        # Drop all tables
        click.echo("🗑️ Dropping all tables...")
        db.drop_all()
        
        # Recreate schema
        click.echo("🏗️ Recreating schema...")
        db.create_all()
        
        # Initialize with seed data
        click.echo("🌱 Seeding initial data...")
        initializer = DatabaseInitializer(current_app, db)
        result = initializer.initialize()
        
        if result.success:
            click.echo("✅ Database reset completed successfully!")
            click.echo("\n" + "=" * 60)
            click.echo("🔑 Login Information:")
            click.echo("📧 Email: admin@ai-secretary.com")
            click.echo("🔐 Password: admin123")
            click.echo("=" * 60)
        else:
            click.echo("❌ Database reset failed during initialization!")
            if result.errors:
                for error in result.errors:
                    click.echo(f"   • {error}")
        
    except Exception as e:
        click.echo(f"❌ Database reset failed: {str(e)}")
        sys.exit(1)


@database.command()
@with_appcontext
def status():
    """Show current database initialization status."""
    click.echo("📊 Database Status Report")
    click.echo("=" * 50)
    
    try:
        # Import here to avoid circular imports
        from app import db
        
        # Initialize components
        initializer = DatabaseInitializer(current_app, db)
        validator = HealthValidator(current_app, db)
        
        # Get initialization status
        status = initializer.get_initialization_status()
        
        # Database connection
        connectivity = validator.validate_connectivity()
        conn_icon = "✅" if connectivity else "❌"
        click.echo(f"Database Connection: {conn_icon}")
        
        # Schema status
        schema_icon = "✅" if status.get('schema_exists', False) else "❌"
        click.echo(f"Schema Exists: {schema_icon}")
        
        # Migration status
        migration_icon = "✅" if status.get('migrations_current', False) else "❌"
        click.echo(f"Migrations Current: {migration_icon}")
        
        # Seed data status
        seeding_icon = "✅" if status.get('seeding_complete', False) else "❌"
        click.echo(f"Seeding Complete: {seeding_icon}")
        
        # Last initialization
        if status.get('last_initialization'):
            click.echo(f"Last Initialization: {status['last_initialization']}")
        
        # Database type and URL
        click.echo(f"Database Type: {status.get('database_type', 'Unknown')}")
        
        # Show table count if schema exists
        if status.get('schema_exists', False):
            try:
                # Try PostgreSQL first
                with db.engine.connect() as conn:
                    result = conn.execute(text("SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema = 'public'"))
                    row = result.fetchone()
                    table_count = row[0] if row else 0
                    click.echo(f"Table Count: {table_count}")
            except:
                # Fallback for SQLite
                try:
                    with db.engine.connect() as conn:
                        result = conn.execute(text("SELECT COUNT(*) as count FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
                        row = result.fetchone()
                        table_count = row[0] if row else 0
                        click.echo(f"Table Count: {table_count}")
                except:
                    click.echo("Table Count: Unable to determine")
        
        # Show overall status
        overall_healthy = all([
            connectivity,
            status.get('schema_exists', False),
            status.get('migrations_current', False),
            status.get('seeding_complete', False)
        ])
        
        overall_icon = "✅" if overall_healthy else "❌"
        overall_status = "READY" if overall_healthy else "NEEDS ATTENTION"
        click.echo(f"\nOverall Status: {overall_icon} {overall_status}")
        
        if not overall_healthy:
            click.echo("\n💡 Suggestions:")
            if not connectivity:
                click.echo("   • Check database connection configuration")
            if not status.get('schema_exists', False):
                click.echo("   • Run 'flask database init' to initialize schema")
            if not status.get('migrations_current', False):
                click.echo("   • Run database migrations")
            if not status.get('seeding_complete', False):
                click.echo("   • Run data seeding")
        
    except Exception as e:
        click.echo(f"❌ Status check failed: {str(e)}")
        sys.exit(1)


@database.command()
@click.option('--format', type=click.Choice(['json', 'text']), default='text',
              help='Output format for the report')
@click.option('--output', type=click.Path(), help='Output file path')
@with_appcontext
def troubleshoot(format, output):
    """Generate comprehensive troubleshooting report."""
    click.echo("🔍 Generating troubleshooting report...")
    
    try:
        # Import here to avoid circular imports
        from app import db
        
        # Initialize components
        initializer = DatabaseInitializer(current_app, db)
        
        # Generate troubleshooting report
        report = initializer.generate_troubleshooting_report()
        
        if format == 'json':
            import json
            report_content = json.dumps(report, indent=2, default=str)
        else:
            # Format as text
            report_content = _format_troubleshooting_report(report)
        
        if output:
            # Write to file
            with open(output, 'w') as f:
                f.write(report_content)
            click.echo(f"✅ Troubleshooting report saved to: {output}")
        else:
            # Print to console
            click.echo("\n" + "=" * 60)
            click.echo("🔍 TROUBLESHOOTING REPORT")
            click.echo("=" * 60)
            click.echo(report_content)
        
    except Exception as e:
        click.echo(f"❌ Failed to generate troubleshooting report: {str(e)}")
        sys.exit(1)


def _format_troubleshooting_report(report: dict) -> str:
    """Format troubleshooting report as readable text."""
    lines = []
    
    # System information
    if 'system_info' in report:
        lines.append("📋 System Information:")
        for key, value in report['system_info'].items():
            lines.append(f"   • {key}: {value}")
        lines.append("")
    
    # Database status
    if 'database_status' in report:
        lines.append("🗄️ Database Status:")
        for key, value in report['database_status'].items():
            icon = "✅" if value else "❌"
            lines.append(f"   • {key}: {icon}")
        lines.append("")
    
    # Error history
    if 'error_history' in report and report['error_history']:
        lines.append("❌ Recent Errors:")
        for error in report['error_history'][-5:]:  # Show last 5 errors
            lines.append(f"   • {error.get('timestamp', 'Unknown')}: {error.get('message', 'No message')}")
        lines.append("")
    
    # Recovery suggestions
    if 'recovery_suggestions' in report and report['recovery_suggestions']:
        lines.append("💡 Recovery Suggestions:")
        for suggestion in report['recovery_suggestions']:
            lines.append(f"   • {suggestion.get('description', 'No description')}")
        lines.append("")
    
    # Configuration
    if 'configuration' in report:
        lines.append("⚙️ Configuration:")
        for key, value in report['configuration'].items():
            # Mask sensitive values
            if 'password' in key.lower() or 'secret' in key.lower():
                value = "***masked***"
            lines.append(f"   • {key}: {value}")
    
    return "\n".join(lines)


# Register commands with Flask CLI
def init_app(app):
    """Initialize CLI commands with Flask app."""
    app.cli.add_command(database)