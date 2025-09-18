"""
Migration Runner System for Database Initialization

This module provides comprehensive migration management functionality including:
- Automatic migration detection and execution
- Migration rollback mechanisms for failed migrations
- Migration history tracking and validation
- Integration with Alembic migration system
"""

import logging
import os
import sys
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from flask import Flask
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.utils.logging_config import get_logger


logger = get_logger(__name__)


@dataclass
class MigrationResult:
    """Result of migration operation."""
    success: bool
    migrations_applied: List[str]
    failed_migration: Optional[str] = None
    error_message: Optional[str] = None
    rollback_performed: bool = False
    duration: float = 0.0
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class MigrationInfo:
    """Information about a migration."""
    revision: str
    description: str
    is_head: bool
    is_applied: bool
    branch_labels: Optional[List[str]] = None
    depends_on: Optional[List[str]] = None


class MigrationRunner:
    """
    Handles database migration operations with Alembic integration.
    
    Provides functionality for:
    - Detecting pending migrations
    - Executing migrations safely
    - Rolling back failed migrations
    - Tracking migration history
    - Validating migration state
    """

    def __init__(self, app: Flask = None, db_url: str = None):
        """
        Initialize MigrationRunner.
        
        Args:
            app: Flask application instance
            db_url: Database URL (if not using Flask app)
        """
        self.app = app
        self.db_url = db_url or (app.config['SQLALCHEMY_DATABASE_URI'] if app else None)
        self.alembic_config = None
        self.script_directory = None
        self._initialize_alembic()

    def _initialize_alembic(self) -> None:
        """Initialize Alembic configuration."""
        try:
            # Find migrations directory
            migrations_dir = self._find_migrations_directory()
            if not migrations_dir:
                raise RuntimeError("Migrations directory not found")

            # Create Alembic configuration
            alembic_ini_path = migrations_dir / 'alembic.ini'
            if not alembic_ini_path.exists():
                raise RuntimeError(f"alembic.ini not found at {alembic_ini_path}")

            self.alembic_config = AlembicConfig(str(alembic_ini_path))
            
            # Set database URL
            if self.db_url:
                self.alembic_config.set_main_option('sqlalchemy.url', self.db_url)
            
            # Set script location
            self.alembic_config.set_main_option('script_location', str(migrations_dir))
            
            # Initialize script directory
            self.script_directory = ScriptDirectory.from_config(self.alembic_config)
            
            logger.info(f"✅ Alembic configuration initialized with migrations at {migrations_dir}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Alembic configuration: {e}")
            raise

    def _find_migrations_directory(self) -> Optional[Path]:
        """Find the migrations directory."""
        # Try common locations
        possible_paths = [
            Path('migrations'),
            Path('app/migrations'),
            Path('../migrations'),
            Path('./migrations')
        ]
        
        for path in possible_paths:
            if path.exists() and (path / 'alembic.ini').exists():
                return path.resolve()
        
        return None

    def check_pending_migrations(self) -> List[str]:
        """
        Check for pending migrations.
        
        Returns:
            List of pending migration revision IDs
        """
        try:
            engine = create_engine(self.db_url)
            
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_rev = context.get_current_revision()
                
                # Get all revisions from head to current
                heads = self.script_directory.get_heads()
                pending_revisions = []
                
                for head in heads:
                    revisions = list(self.script_directory.walk_revisions(head, current_rev))
                    # Remove the current revision if it exists
                    if revisions and revisions[-1].revision == current_rev:
                        revisions = revisions[:-1]
                    
                    pending_revisions.extend([rev.revision for rev in revisions])
                
                # Remove duplicates and sort
                pending_revisions = list(set(pending_revisions))
                
                logger.info(f"📋 Found {len(pending_revisions)} pending migrations")
                for rev in pending_revisions:
                    migration = self.script_directory.get_revision(rev)
                    logger.info(f"  • {rev}: {migration.doc}")
                
                return pending_revisions
                
        except Exception as e:
            logger.error(f"❌ Failed to check pending migrations: {e}")
            return []

    def run_migrations(self) -> MigrationResult:
        """
        Run all pending migrations.
        
        Returns:
            MigrationResult with operation details
        """
        start_time = datetime.now()
        result = MigrationResult(
            success=False,
            migrations_applied=[],
            warnings=[]
        )
        
        try:
            # Check for pending migrations first
            pending_migrations = self.check_pending_migrations()
            
            if not pending_migrations:
                logger.info("✅ No pending migrations found")
                result.success = True
                result.duration = (datetime.now() - start_time).total_seconds()
                return result
            
            logger.info(f"🔄 Running {len(pending_migrations)} pending migrations...")
            
            # Create engine for migration
            engine = create_engine(self.db_url)
            
            # Run migrations using Alembic
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_rev_before = context.get_current_revision()
                
                try:
                    # Execute upgrade command
                    command.upgrade(self.alembic_config, 'head')
                    
                    # Check what was applied
                    context = MigrationContext.configure(connection)
                    current_rev_after = context.get_current_revision()
                    
                    if current_rev_after != current_rev_before:
                        result.migrations_applied = pending_migrations
                        result.success = True
                        logger.info(f"✅ Successfully applied {len(pending_migrations)} migrations")
                        
                        for migration_id in pending_migrations:
                            migration = self.script_directory.get_revision(migration_id)
                            logger.info(f"  ✓ {migration_id}: {migration.doc}")
                    else:
                        result.warnings.append("No migrations were actually applied despite pending migrations")
                        result.success = True
                        
                except CommandError as e:
                    logger.error(f"❌ Migration command failed: {e}")
                    result.error_message = str(e)
                    
                    # Try to determine which migration failed
                    context = MigrationContext.configure(connection)
                    current_rev_after = context.get_current_revision()
                    
                    if current_rev_after != current_rev_before:
                        # Some migrations were applied before failure
                        applied_migrations = self._get_applied_migrations_since(
                            current_rev_before, current_rev_after
                        )
                        result.migrations_applied = applied_migrations
                        
                        # Find the failed migration
                        remaining = [m for m in pending_migrations if m not in applied_migrations]
                        if remaining:
                            result.failed_migration = remaining[0]
                    else:
                        # First migration failed
                        result.failed_migration = pending_migrations[0] if pending_migrations else None
                    
                    # Attempt rollback if configured
                    if self._should_rollback_on_failure():
                        rollback_success = self._rollback_failed_migration(result.failed_migration)
                        result.rollback_performed = rollback_success
                        if rollback_success:
                            logger.info("✅ Successfully rolled back failed migration")
                        else:
                            logger.error("❌ Failed to rollback migration")
                            result.warnings.append("Rollback failed - manual intervention required")
                    
                    raise
                    
        except Exception as e:
            logger.error(f"❌ Migration execution failed: {e}")
            result.error_message = str(e)
            result.success = False
            
        finally:
            result.duration = (datetime.now() - start_time).total_seconds()
            
        return result

    def rollback_migration(self, migration_id: str) -> bool:
        """
        Rollback a specific migration.
        
        Args:
            migration_id: Migration revision ID to rollback to
            
        Returns:
            True if rollback successful, False otherwise
        """
        try:
            logger.info(f"🔄 Rolling back to migration {migration_id}...")
            
            # Validate migration exists
            try:
                migration = self.script_directory.get_revision(migration_id)
                if not migration:
                    logger.error(f"❌ Migration {migration_id} not found")
                    return False
            except Exception as e:
                logger.error(f"❌ Invalid migration ID {migration_id}: {e}")
                return False
            
            # Execute downgrade command
            command.downgrade(self.alembic_config, migration_id)
            
            logger.info(f"✅ Successfully rolled back to migration {migration_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to rollback migration {migration_id}: {e}")
            return False

    def get_migration_history(self) -> List[Dict[str, Any]]:
        """
        Get migration history with detailed information.
        
        Returns:
            List of migration history entries
        """
        try:
            engine = create_engine(self.db_url)
            history = []
            
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_rev = context.get_current_revision()
                
                # Get all revisions
                for revision in self.script_directory.walk_revisions():
                    migration_info = {
                        'revision': revision.revision,
                        'description': revision.doc or 'No description',
                        'branch_labels': revision.branch_labels,
                        'depends_on': revision.dependencies,
                        'is_head': revision.revision in self.script_directory.get_heads(),
                        'is_applied': self._is_migration_applied(revision.revision, current_rev),
                        'created_date': self._get_migration_date(revision.revision)
                    }
                    history.append(migration_info)
                
                # Sort by creation date (newest first)
                history.sort(key=lambda x: x.get('created_date', ''), reverse=True)
                
            logger.info(f"📋 Retrieved migration history: {len(history)} migrations")
            return history
            
        except Exception as e:
            logger.error(f"❌ Failed to get migration history: {e}")
            return []

    def validate_migration_state(self) -> Dict[str, Any]:
        """
        Validate the current migration state.
        
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'valid': True,
            'issues': [],
            'warnings': [],
            'current_revision': None,
            'head_revisions': [],
            'pending_migrations': [],
            'orphaned_migrations': []
        }
        
        try:
            engine = create_engine(self.db_url)
            
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_rev = context.get_current_revision()
                heads = self.script_directory.get_heads()
                
                validation_result['current_revision'] = current_rev
                validation_result['head_revisions'] = heads
                
                # Check for pending migrations
                pending = self.check_pending_migrations()
                validation_result['pending_migrations'] = pending
                
                if pending:
                    validation_result['warnings'].append(
                        f"{len(pending)} pending migrations found"
                    )
                
                # Check for multiple heads (branching)
                if len(heads) > 1:
                    validation_result['issues'].append(
                        f"Multiple migration heads found: {heads}"
                    )
                    validation_result['valid'] = False
                
                # Check if current revision is valid
                if current_rev and current_rev not in [rev.revision for rev in self.script_directory.walk_revisions()]:
                    validation_result['issues'].append(
                        f"Current revision {current_rev} not found in migration scripts"
                    )
                    validation_result['valid'] = False
                
                # Check for orphaned migrations (migrations that can't be reached from heads)
                all_revisions = set(rev.revision for rev in self.script_directory.walk_revisions())
                reachable_revisions = set()
                
                for head in heads:
                    for rev in self.script_directory.walk_revisions(head):
                        reachable_revisions.add(rev.revision)
                
                orphaned = all_revisions - reachable_revisions
                if orphaned:
                    validation_result['orphaned_migrations'] = list(orphaned)
                    validation_result['warnings'].append(
                        f"Found {len(orphaned)} orphaned migrations"
                    )
                
            logger.info(f"🔍 Migration state validation: {'✅ Valid' if validation_result['valid'] else '❌ Invalid'}")
            
            if validation_result['issues']:
                for issue in validation_result['issues']:
                    logger.error(f"  ❌ {issue}")
            
            if validation_result['warnings']:
                for warning in validation_result['warnings']:
                    logger.warning(f"  ⚠️ {warning}")
                    
        except Exception as e:
            logger.error(f"❌ Failed to validate migration state: {e}")
            validation_result['valid'] = False
            validation_result['issues'].append(f"Validation failed: {str(e)}")
            
        return validation_result

    def get_current_revision(self) -> Optional[str]:
        """
        Get the current database revision.
        
        Returns:
            Current revision ID or None if not found
        """
        try:
            engine = create_engine(self.db_url)
            
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return context.get_current_revision()
                
        except Exception as e:
            logger.error(f"❌ Failed to get current revision: {e}")
            return None

    def stamp_database(self, revision: str = 'head') -> bool:
        """
        Stamp the database with a specific revision without running migrations.
        
        Args:
            revision: Revision to stamp (default: 'head')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"🏷️ Stamping database with revision {revision}...")
            
            command.stamp(self.alembic_config, revision)
            
            logger.info(f"✅ Successfully stamped database with revision {revision}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to stamp database: {e}")
            return False

    def create_migration(self, message: str, autogenerate: bool = True) -> Optional[str]:
        """
        Create a new migration.
        
        Args:
            message: Migration message/description
            autogenerate: Whether to auto-generate migration content
            
        Returns:
            New migration revision ID or None if failed
        """
        try:
            logger.info(f"📝 Creating new migration: {message}")
            
            # Create the migration
            if autogenerate:
                command.revision(
                    self.alembic_config,
                    message=message,
                    autogenerate=True
                )
            else:
                command.revision(
                    self.alembic_config,
                    message=message
                )
            
            # Get the newly created revision
            heads = self.script_directory.get_heads()
            if heads:
                new_revision = heads[0]  # Assuming single head
                logger.info(f"✅ Created migration {new_revision}: {message}")
                return new_revision
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to create migration: {e}")
            return None

    def _get_applied_migrations_since(self, from_rev: str, to_rev: str) -> List[str]:
        """Get list of migrations applied between two revisions."""
        try:
            applied = []
            
            if not from_rev:
                # Get all migrations up to to_rev
                for rev in self.script_directory.walk_revisions(to_rev):
                    applied.append(rev.revision)
                    if rev.revision == to_rev:
                        break
            else:
                # Get migrations between from_rev and to_rev
                for rev in self.script_directory.walk_revisions(to_rev, from_rev):
                    if rev.revision != from_rev:  # Exclude the starting revision
                        applied.append(rev.revision)
            
            return applied
            
        except Exception as e:
            logger.error(f"❌ Failed to get applied migrations: {e}")
            return []

    def _is_migration_applied(self, revision: str, current_rev: str) -> bool:
        """Check if a migration is applied."""
        if not current_rev:
            return False
            
        try:
            # Walk from current revision backwards to see if we find the target revision
            for rev in self.script_directory.walk_revisions(current_rev):
                if rev.revision == revision:
                    return True
            return False
            
        except Exception:
            return False

    def _get_migration_date(self, revision: str) -> str:
        """Extract creation date from migration revision."""
        try:
            # Alembic revision IDs often contain timestamps
            # This is a simple heuristic - could be improved
            migration = self.script_directory.get_revision(revision)
            if hasattr(migration, 'create_date'):
                return str(migration.create_date)
            
            # Try to extract from revision ID if it contains timestamp
            if len(revision) >= 12 and revision[:12].isdigit():
                return revision[:12]
                
            return ''
            
        except Exception:
            return ''

    def _should_rollback_on_failure(self) -> bool:
        """Check if rollback should be performed on migration failure."""
        # This could be configurable via environment variable or app config
        return os.environ.get('MIGRATION_ROLLBACK_ON_FAILURE', 'false').lower() == 'true'

    def _rollback_failed_migration(self, failed_migration: str) -> bool:
        """Rollback a failed migration."""
        if not failed_migration:
            return False
            
        try:
            # Get the previous revision
            migration = self.script_directory.get_revision(failed_migration)
            if migration.down_revision:
                return self.rollback_migration(migration.down_revision)
            else:
                # This is the first migration, rollback to base
                return self.rollback_migration('base')
                
        except Exception as e:
            logger.error(f"❌ Failed to rollback failed migration {failed_migration}: {e}")
            return False

    def get_migration_info(self, revision: str) -> Optional[MigrationInfo]:
        """
        Get detailed information about a specific migration.
        
        Args:
            revision: Migration revision ID
            
        Returns:
            MigrationInfo object or None if not found
        """
        try:
            migration = self.script_directory.get_revision(revision)
            if not migration:
                return None
            
            # Check if migration is applied
            current_rev = self.get_current_revision()
            is_applied = self._is_migration_applied(revision, current_rev)
            
            # Check if this is a head revision
            heads = self.script_directory.get_heads()
            is_head = revision in heads
            
            return MigrationInfo(
                revision=revision,
                description=migration.doc or 'No description',
                is_head=is_head,
                is_applied=is_applied,
                branch_labels=migration.branch_labels,
                depends_on=migration.dependencies
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to get migration info for {revision}: {e}")
            return None

    def repair_migration_state(self) -> Dict[str, Any]:
        """
        Attempt to repair common migration state issues.
        
        Returns:
            Dictionary with repair results
        """
        repair_result = {
            'success': False,
            'repairs_performed': [],
            'issues_found': [],
            'manual_intervention_required': []
        }
        
        try:
            logger.info("🔧 Attempting to repair migration state...")
            
            # Validate current state
            validation = self.validate_migration_state()
            
            if validation['valid']:
                logger.info("✅ Migration state is already valid")
                repair_result['success'] = True
                return repair_result
            
            repair_result['issues_found'] = validation['issues']
            
            # Attempt to resolve multiple heads
            if len(validation['head_revisions']) > 1:
                logger.info("🔧 Attempting to resolve multiple heads...")
                # This is complex and usually requires manual intervention
                repair_result['manual_intervention_required'].append(
                    "Multiple migration heads detected - manual merge required"
                )
            
            # Check for missing alembic_version table
            if not self._alembic_version_table_exists():
                logger.info("🔧 Creating missing alembic_version table...")
                if self._create_alembic_version_table():
                    repair_result['repairs_performed'].append("Created alembic_version table")
                else:
                    repair_result['manual_intervention_required'].append(
                        "Failed to create alembic_version table"
                    )
            
            # Re-validate after repairs
            validation_after = self.validate_migration_state()
            repair_result['success'] = validation_after['valid']
            
            if repair_result['success']:
                logger.info("✅ Migration state successfully repaired")
            else:
                logger.warning("⚠️ Some issues remain after repair attempt")
                
        except Exception as e:
            logger.error(f"❌ Failed to repair migration state: {e}")
            repair_result['manual_intervention_required'].append(f"Repair failed: {str(e)}")
            
        return repair_result

    def _alembic_version_table_exists(self) -> bool:
        """Check if alembic_version table exists."""
        try:
            engine = create_engine(self.db_url)
            
            with engine.connect() as connection:
                # Try to query the alembic_version table
                result = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                result.fetchone()
                return True
                
        except Exception:
            return False

    def _create_alembic_version_table(self) -> bool:
        """Create the alembic_version table."""
        try:
            engine = create_engine(self.db_url)
            
            with engine.connect() as connection:
                # Create the table
                connection.execute(text("""
                    CREATE TABLE alembic_version (
                        version_num VARCHAR(32) NOT NULL,
                        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                    )
                """))
                connection.commit()
                
            logger.info("✅ Created alembic_version table")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create alembic_version table: {e}")
            return False