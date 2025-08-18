"""CLI commands for data retention and GDPR compliance management."""
import click
import json
from datetime import datetime, timedelta
from flask import current_app
from flask.cli import with_appcontext
from app import db
from app.models.tenant import Tenant
from app.models.gdpr_compliance import DataRetentionPolicy, ConsentRecord
from app.services.data_retention_service import DataRetentionService
from app.services.consent_service import ConsentService
from app.services.pii_service import PIIDetector
from app.workers.data_retention import (
    cleanup_expired_data, check_expired_consents,
    generate_retention_report, cleanup_expired_exports
)


@click.group()
def data_retention():
    """Data retention and GDPR compliance commands."""
    pass


@data_retention.command()
@click.option('--tenant-id', type=int, help='Tenant ID (optional, processes all if not specified)')
@click.option('--dry-run/--no-dry-run', default=True, help='Perform dry run without actual changes')
@click.option('--batch-size', default=100, help='Batch size for processing')
@click.option('--policy-id', type=int, help='Specific policy ID to process')
@with_appcontext
def cleanup(tenant_id, dry_run, batch_size, policy_id):
    """Run data cleanup according to retention policies."""
    click.echo(f"Starting data cleanup - tenant_id={tenant_id}, dry_run={dry_run}, batch_size={batch_size}")
    
    try:
        with db.session.begin():
            retention_service = DataRetentionService(db.session)
            
            if tenant_id:
                # Process specific tenant
                result = retention_service.cleanup_expired_data(
                    tenant_id=tenant_id,
                    policy_id=policy_id,
                    dry_run=dry_run,
                    batch_size=batch_size
                )
                
                click.echo(f"Tenant {tenant_id} cleanup completed:")
                click.echo(f"  - Deleted: {result['total_deleted']} records")
                click.echo(f"  - Anonymized: {result['total_anonymized']} records")
                
                if result['errors']:
                    click.echo("Errors:")
                    for error in result['errors']:
                        click.echo(f"  - {error}")
            else:
                # Process all tenants
                tenants = Tenant.query.filter_by(is_active=True).all()
                total_deleted = 0
                total_anonymized = 0
                
                for tenant in tenants:
                    click.echo(f"Processing tenant {tenant.id} ({tenant.name})...")
                    
                    result = retention_service.cleanup_expired_data(
                        tenant_id=tenant.id,
                        policy_id=policy_id,
                        dry_run=dry_run,
                        batch_size=batch_size
                    )
                    
                    total_deleted += result['total_deleted']
                    total_anonymized += result['total_anonymized']
                    
                    click.echo(f"  - Deleted: {result['total_deleted']} records")
                    click.echo(f"  - Anonymized: {result['total_anonymized']} records")
                
                click.echo(f"\nTotal across all tenants:")
                click.echo(f"  - Deleted: {total_deleted} records")
                click.echo(f"  - Anonymized: {total_anonymized} records")
        
        click.echo("Data cleanup completed successfully!")
        
    except Exception as e:
        click.echo(f"Error during cleanup: {e}", err=True)
        raise click.ClickException(str(e))


@data_retention.command()
@click.option('--tenant-id', type=int, help='Tenant ID (optional, processes all if not specified)')
@with_appcontext
def check_consents(tenant_id):
    """Check for expired consents and update their status."""
    click.echo(f"Checking expired consents - tenant_id={tenant_id}")
    
    try:
        with db.session.begin():
            consent_service = ConsentService(db.session)
            
            if tenant_id:
                # Process specific tenant
                result = consent_service.check_expired_consents(tenant_id)
                click.echo(f"Tenant {tenant_id}: {result['expired_count']} consents expired")
            else:
                # Process all tenants
                tenants = Tenant.query.filter_by(is_active=True).all()
                total_expired = 0
                
                for tenant in tenants:
                    result = consent_service.check_expired_consents(tenant.id)
                    expired_count = result['expired_count']
                    total_expired += expired_count
                    
                    if expired_count > 0:
                        click.echo(f"Tenant {tenant.id} ({tenant.name}): {expired_count} consents expired")
                
                click.echo(f"Total expired consents: {total_expired}")
        
        click.echo("Consent check completed successfully!")
        
    except Exception as e:
        click.echo(f"Error during consent check: {e}", err=True)
        raise click.ClickException(str(e))


@data_retention.command()
@click.option('--tenant-id', type=int, help='Tenant ID (optional, generates report for all if not specified)')
@click.option('--output-file', help='Output file path (optional, prints to console if not specified)')
@with_appcontext
def report(tenant_id, output_file):
    """Generate data retention compliance report."""
    click.echo(f"Generating retention report - tenant_id={tenant_id}")
    
    try:
        with db.session.begin():
            retention_service = DataRetentionService(db.session)
            
            if tenant_id:
                # Generate report for specific tenant
                report_data = retention_service.find_expired_data(tenant_id)
            else:
                # Generate report for all tenants
                tenants = Tenant.query.filter_by(is_active=True).all()
                
                report_data = {
                    'report_date': datetime.utcnow().isoformat(),
                    'tenant_count': len(tenants),
                    'total_expired_records': 0,
                    'tenant_reports': {}
                }
                
                for tenant in tenants:
                    tenant_report = retention_service.find_expired_data(tenant.id)
                    report_data['tenant_reports'][tenant.id] = tenant_report
                    report_data['total_expired_records'] += tenant_report['total_expired_records']
        
        # Output report
        report_json = json.dumps(report_data, indent=2, default=str)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_json)
            click.echo(f"Report saved to {output_file}")
        else:
            click.echo("Data Retention Report:")
            click.echo(report_json)
        
    except Exception as e:
        click.echo(f"Error generating report: {e}", err=True)
        raise click.ClickException(str(e))


@data_retention.command()
@click.argument('tenant_id', type=int)
@with_appcontext
def create_default_policies(tenant_id):
    """Create default retention policies for a tenant."""
    click.echo(f"Creating default retention policies for tenant {tenant_id}")
    
    try:
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            raise click.ClickException(f"Tenant {tenant_id} not found")
        
        with db.session.begin():
            retention_service = DataRetentionService(db.session)
            policies = retention_service.create_default_policies(tenant_id)
            
            click.echo(f"Created {len(policies)} default retention policies:")
            for policy in policies:
                click.echo(f"  - {policy.name}: {policy.retention_days} days ({policy.data_type})")
        
        click.echo("Default policies created successfully!")
        
    except Exception as e:
        click.echo(f"Error creating default policies: {e}", err=True)
        raise click.ClickException(str(e))


@data_retention.command()
@click.argument('tenant_id', type=int)
@click.argument('name')
@click.argument('data_type')
@click.argument('table_name')
@click.argument('retention_days', type=int)
@click.option('--auto-delete/--no-auto-delete', default=True, help='Enable automatic deletion')
@click.option('--anonymize/--no-anonymize', default=False, help='Anonymize instead of delete')
@click.option('--legal-basis', help='Legal basis for retention')
@click.option('--description', help='Policy description')
@with_appcontext
def create_policy(tenant_id, name, data_type, table_name, retention_days, 
                 auto_delete, anonymize, legal_basis, description):
    """Create a new retention policy."""
    click.echo(f"Creating retention policy '{name}' for tenant {tenant_id}")
    
    try:
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            raise click.ClickException(f"Tenant {tenant_id} not found")
        
        with db.session.begin():
            retention_service = DataRetentionService(db.session)
            
            policy = retention_service.create_retention_policy(
                tenant_id=tenant_id,
                name=name,
                data_type=data_type,
                table_name=table_name,
                retention_days=retention_days,
                auto_delete=auto_delete,
                anonymize_instead=anonymize,
                legal_basis=legal_basis,
                description=description
            )
            
            click.echo(f"Policy created successfully:")
            click.echo(f"  - ID: {policy.id}")
            click.echo(f"  - Name: {policy.name}")
            click.echo(f"  - Data Type: {policy.data_type}")
            click.echo(f"  - Retention: {policy.retention_days} days")
            click.echo(f"  - Auto Delete: {policy.auto_delete}")
            click.echo(f"  - Anonymize: {policy.anonymize_instead}")
        
    except Exception as e:
        click.echo(f"Error creating policy: {e}", err=True)
        raise click.ClickException(str(e))


@data_retention.command()
@click.argument('tenant_id', type=int)
@with_appcontext
def list_policies(tenant_id):
    """List retention policies for a tenant."""
    try:
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            raise click.ClickException(f"Tenant {tenant_id} not found")
        
        with db.session.begin():
            retention_service = DataRetentionService(db.session)
            policies = retention_service.get_tenant_policies(tenant_id, active_only=False)
            
            if not policies:
                click.echo(f"No retention policies found for tenant {tenant_id}")
                return
            
            click.echo(f"Retention policies for tenant {tenant_id} ({tenant.name}):")
            click.echo("-" * 80)
            
            for policy in policies:
                status = "Active" if policy.is_active else "Inactive"
                action = "Anonymize" if policy.anonymize_instead else "Delete"
                auto = "Auto" if policy.auto_delete else "Manual"
                
                click.echo(f"ID: {policy.id}")
                click.echo(f"Name: {policy.name}")
                click.echo(f"Data Type: {policy.data_type}")
                click.echo(f"Table: {policy.table_name}")
                click.echo(f"Retention: {policy.retention_days} days")
                click.echo(f"Action: {action} ({auto})")
                click.echo(f"Status: {status}")
                click.echo(f"Legal Basis: {policy.legal_basis or 'Not specified'}")
                if policy.description:
                    click.echo(f"Description: {policy.description}")
                click.echo("-" * 80)
        
    except Exception as e:
        click.echo(f"Error listing policies: {e}", err=True)
        raise click.ClickException(str(e))


@data_retention.command()
@click.argument('text')
@with_appcontext
def detect_pii(text):
    """Detect PII in provided text."""
    click.echo("Detecting PII in provided text...")
    
    try:
        pii_detector = PIIDetector()
        detected_pii = pii_detector.detect_pii_in_text(text)
        
        if not detected_pii:
            click.echo("No PII detected in the text.")
            return
        
        click.echo(f"Found {len(detected_pii)} PII items:")
        click.echo("-" * 50)
        
        for i, pii_item in enumerate(detected_pii, 1):
            click.echo(f"{i}. Type: {pii_item['type']}")
            click.echo(f"   Value: {pii_item['value']}")
            click.echo(f"   Confidence: {pii_item['confidence']}")
            click.echo(f"   Position: {pii_item['start']}-{pii_item['end']}")
            click.echo(f"   Context: {pii_item['context']}")
            click.echo("-" * 50)
        
    except Exception as e:
        click.echo(f"Error detecting PII: {e}", err=True)
        raise click.ClickException(str(e))


@data_retention.command()
@click.argument('text')
@click.option('--mask-char', default='*', help='Character to use for masking')
@click.option('--preserve-chars', default=2, type=int, help='Number of characters to preserve at start/end')
@with_appcontext
def mask_pii(text, mask_char, preserve_chars):
    """Mask PII in provided text."""
    click.echo("Masking PII in provided text...")
    
    try:
        pii_detector = PIIDetector()
        masked_text, masked_items = pii_detector.mask_pii_in_text(text, mask_char, preserve_chars)
        
        click.echo(f"Original text: {text}")
        click.echo(f"Masked text: {masked_text}")
        
        if masked_items:
            click.echo(f"\nMasked {len(masked_items)} PII items:")
            for i, item in enumerate(masked_items, 1):
                click.echo(f"{i}. {item['type']}: {item['original_value']} -> {item['masked_value']}")
        else:
            click.echo("\nNo PII found to mask.")
        
    except Exception as e:
        click.echo(f"Error masking PII: {e}", err=True)
        raise click.ClickException(str(e))


@data_retention.command()
@click.option('--tenant-id', type=int, help='Tenant ID (optional, processes all if not specified)')
@with_appcontext
def cleanup_exports():
    """Clean up expired data export files."""
    click.echo("Cleaning up expired data export files...")
    
    try:
        from app.models.gdpr_compliance import DataExportRequest
        import os
        
        with db.session.begin():
            # Find expired exports
            expired_exports = DataExportRequest.query.filter(
                DataExportRequest.status == 'completed',
                DataExportRequest.expires_at < datetime.utcnow()
            )
            
            if tenant_id:
                expired_exports = expired_exports.filter_by(tenant_id=tenant_id)
            
            expired_exports = expired_exports.all()
            
            files_deleted = 0
            exports_updated = 0
            
            for export_request in expired_exports:
                try:
                    # Delete the file if it exists
                    if export_request.file_path and os.path.exists(export_request.file_path):
                        os.remove(export_request.file_path)
                        files_deleted += 1
                    
                    # Update status
                    export_request.status = 'expired'
                    export_request.file_path = None
                    export_request.download_token = None
                    exports_updated += 1
                    
                except Exception as e:
                    click.echo(f"Error cleaning up export {export_request.request_id}: {e}")
            
            click.echo(f"Cleanup completed:")
            click.echo(f"  - Files deleted: {files_deleted}")
            click.echo(f"  - Export records updated: {exports_updated}")
        
    except Exception as e:
        click.echo(f"Error during export cleanup: {e}", err=True)
        raise click.ClickException(str(e))


@data_retention.command()
@click.option('--tenant-id', type=int, help='Tenant ID (optional, schedules for all if not specified)')
@click.option('--async/--sync', default=True, help='Run as background task or synchronously')
@with_appcontext
def schedule_cleanup(tenant_id, async_task):
    """Schedule data cleanup as a background task."""
    click.echo(f"Scheduling data cleanup task - tenant_id={tenant_id}, async={async_task}")
    
    try:
        if async_task:
            # Schedule as Celery task
            task = cleanup_expired_data.apply_async(
                kwargs={
                    'tenant_id': tenant_id,
                    'dry_run': False,
                    'batch_size': 500
                }
            )
            
            click.echo(f"Background cleanup task scheduled with ID: {task.id}")
            click.echo("Use 'celery -A celery_app.celery flower' to monitor task progress")
        else:
            # Run synchronously
            click.echo("Running cleanup synchronously...")
            # This would call the actual function without Celery
            click.echo("Synchronous execution not implemented in CLI - use 'cleanup' command instead")
        
    except Exception as e:
        click.echo(f"Error scheduling cleanup: {e}", err=True)
        raise click.ClickException(str(e))


def init_app(app):
    """Initialize CLI commands with Flask app."""
    app.cli.add_command(data_retention)