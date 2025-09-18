"""
Tests for MigrationRunner class.

This module tests the migration runner functionality including:
- Migration detection and execution
- Rollback mechanisms
- Migration history tracking
- Error handling and recovery
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.services.migration_runner import MigrationRunner, MigrationResult, MigrationInfo


class TestMigrationRunner:
    """Test cases for MigrationRunner class."""

    def _setup_mock_connection(self, mock_create_engine):
        """Helper method to setup mock database connection."""
        mock_engine = Mock()
        mock_connection = Mock()
        mock_create_engine.return_value = mock_engine
        mock_engine.connect.return_value = mock_connection
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=None)
        return mock_engine, mock_connection

    @pytest.fixture
    def temp_migrations_dir(self):
        """Create temporary migrations directory for testing."""
        temp_dir = tempfile.mkdtemp()
        migrations_dir = Path(temp_dir) / 'migrations'
        migrations_dir.mkdir()
        
        # Create alembic.ini
        alembic_ini = migrations_dir / 'alembic.ini'
        alembic_ini.write_text("""
[alembic]
script_location = migrations
sqlalchemy.url = sqlite:///test.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
        """)
        
        # Create versions directory
        versions_dir = migrations_dir / 'versions'
        versions_dir.mkdir()
        
        yield migrations_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_app(self):
        """Create mock Flask app."""
        app = Mock()
        app.config = {
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db'
        }
        return app

    @pytest.fixture
    def migration_runner(self, mock_app, temp_migrations_dir):
        """Create MigrationRunner instance for testing."""
        with patch('app.services.migration_runner.MigrationRunner._find_migrations_directory') as mock_find:
            mock_find.return_value = temp_migrations_dir
            runner = MigrationRunner(app=mock_app)
            return runner

    def test_initialization_success(self, mock_app, temp_migrations_dir):
        """Test successful MigrationRunner initialization."""
        with patch('app.services.migration_runner.MigrationRunner._find_migrations_directory') as mock_find:
            mock_find.return_value = temp_migrations_dir
            
            runner = MigrationRunner(app=mock_app)
            
            assert runner.app == mock_app
            assert runner.db_url == 'sqlite:///test.db'
            assert runner.alembic_config is not None
            assert runner.script_directory is not None

    def test_initialization_no_migrations_dir(self, mock_app):
        """Test initialization failure when migrations directory not found."""
        with patch('app.services.migration_runner.MigrationRunner._find_migrations_directory') as mock_find:
            mock_find.return_value = None
            
            with pytest.raises(RuntimeError, match="Migrations directory not found"):
                MigrationRunner(app=mock_app)

    def test_initialization_no_alembic_ini(self, mock_app, temp_migrations_dir):
        """Test initialization failure when alembic.ini not found."""
        # Remove alembic.ini
        (temp_migrations_dir / 'alembic.ini').unlink()
        
        with patch('app.services.migration_runner.MigrationRunner._find_migrations_directory') as mock_find:
            mock_find.return_value = temp_migrations_dir
            
            with pytest.raises(RuntimeError, match="alembic.ini not found"):
                MigrationRunner(app=mock_app)

    @patch('app.services.migration_runner.create_engine')
    @patch('app.services.migration_runner.MigrationContext')
    def test_check_pending_migrations_none(self, mock_context_class, mock_create_engine, migration_runner):
        """Test checking pending migrations when none exist."""
        # Mock database connection and context
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        mock_context = Mock()
        
        mock_context_class.configure.return_value = mock_context
        mock_context.get_current_revision.return_value = 'abc123'
        
        # Mock script directory
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.get_heads.return_value = ['abc123']
        migration_runner.script_directory.walk_revisions.return_value = []
        
        result = migration_runner.check_pending_migrations()
        
        assert result == []

    @patch('app.services.migration_runner.create_engine')
    @patch('app.services.migration_runner.MigrationContext')
    def test_check_pending_migrations_found(self, mock_context_class, mock_create_engine, migration_runner):
        """Test checking pending migrations when some exist."""
        # Mock database connection and context
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        mock_context = Mock()
        
        mock_context_class.configure.return_value = mock_context
        mock_context.get_current_revision.return_value = 'abc123'
        
        # Mock script directory with pending migrations
        mock_revision1 = Mock()
        mock_revision1.revision = 'def456'
        mock_revision1.doc = 'Add new table'
        
        mock_revision2 = Mock()
        mock_revision2.revision = 'ghi789'
        mock_revision2.doc = 'Update schema'
        
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.get_heads.return_value = ['ghi789']
        migration_runner.script_directory.walk_revisions.return_value = [mock_revision2, mock_revision1]
        migration_runner.script_directory.get_revision.side_effect = lambda x: {
            'def456': mock_revision1,
            'ghi789': mock_revision2
        }[x]
        
        result = migration_runner.check_pending_migrations()
        
        assert len(result) == 2
        assert 'def456' in result
        assert 'ghi789' in result

    @patch('app.services.migration_runner.command')
    @patch('app.services.migration_runner.create_engine')
    @patch('app.services.migration_runner.MigrationContext')
    def test_run_migrations_success(self, mock_context_class, mock_create_engine, mock_command, migration_runner):
        """Test successful migration execution."""
        # Mock pending migrations check
        migration_runner.check_pending_migrations = Mock(return_value=['abc123', 'def456'])
        
        # Mock database connection and context
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        mock_context = Mock()
        
        mock_context_class.configure.return_value = mock_context
        mock_context.get_current_revision.side_effect = ['old_rev', 'new_rev']
        
        # Mock successful upgrade command
        mock_command.upgrade = Mock()
        
        # Mock script directory to avoid revision lookup errors
        mock_revision1 = Mock()
        mock_revision1.doc = 'First migration'
        mock_revision2 = Mock()
        mock_revision2.doc = 'Second migration'
        
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.get_revision.side_effect = lambda x: {
            'abc123': mock_revision1,
            'def456': mock_revision2
        }[x]
        
        result = migration_runner.run_migrations()
        
        assert result.success is True
        assert result.migrations_applied == ['abc123', 'def456']
        assert result.error_message is None
        assert result.failed_migration is None
        assert result.rollback_performed is False
        assert result.duration >= 0
        
        mock_command.upgrade.assert_called_once_with(migration_runner.alembic_config, 'head')

    @patch('app.services.migration_runner.command')
    def test_run_migrations_no_pending(self, mock_command, migration_runner):
        """Test migration execution when no pending migrations."""
        # Mock no pending migrations
        migration_runner.check_pending_migrations = Mock(return_value=[])
        
        result = migration_runner.run_migrations()
        
        assert result.success is True
        assert result.migrations_applied == []
        assert result.error_message is None
        assert result.duration >= 0  # Duration can be 0 for very fast operations
        
        # Upgrade command should not be called
        mock_command.upgrade.assert_not_called()

    @patch('app.services.migration_runner.command')
    @patch('app.services.migration_runner.create_engine')
    @patch('app.services.migration_runner.MigrationContext')
    def test_run_migrations_failure(self, mock_context_class, mock_create_engine, mock_command, migration_runner):
        """Test migration execution failure."""
        # Mock pending migrations check
        migration_runner.check_pending_migrations = Mock(return_value=['abc123', 'def456'])
        
        # Mock database connection and context
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        mock_context = Mock()
        
        mock_context_class.configure.return_value = mock_context
        mock_context.get_current_revision.return_value = 'old_rev'
        
        # Mock failed upgrade command
        from alembic.util.exc import CommandError
        mock_command.upgrade.side_effect = CommandError("Migration failed")
        
        # Mock rollback configuration
        migration_runner._should_rollback_on_failure = Mock(return_value=False)
        
        result = migration_runner.run_migrations()
        
        assert result.success is False
        assert result.error_message == "Migration failed"
        assert result.failed_migration == 'abc123'  # First migration should be marked as failed
        assert result.rollback_performed is False

    @patch('app.services.migration_runner.command')
    def test_rollback_migration_success(self, mock_command, migration_runner):
        """Test successful migration rollback."""
        # Mock script directory
        mock_migration = Mock()
        mock_migration.revision = 'abc123'
        
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.get_revision.return_value = mock_migration
        
        # Mock successful downgrade command
        mock_command.downgrade = Mock()
        
        result = migration_runner.rollback_migration('abc123')
        
        assert result is True
        mock_command.downgrade.assert_called_once_with(migration_runner.alembic_config, 'abc123')

    @patch('app.services.migration_runner.command')
    def test_rollback_migration_invalid_id(self, mock_command, migration_runner):
        """Test rollback with invalid migration ID."""
        # Mock script directory returning None for invalid migration
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.get_revision.return_value = None
        
        result = migration_runner.rollback_migration('invalid_id')
        
        assert result is False
        mock_command.downgrade.assert_not_called()

    @patch('app.services.migration_runner.command')
    def test_rollback_migration_failure(self, mock_command, migration_runner):
        """Test migration rollback failure."""
        # Mock script directory
        mock_migration = Mock()
        mock_migration.revision = 'abc123'
        
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.get_revision.return_value = mock_migration
        
        # Mock failed downgrade command
        mock_command.downgrade.side_effect = Exception("Rollback failed")
        
        result = migration_runner.rollback_migration('abc123')
        
        assert result is False

    @patch('app.services.migration_runner.create_engine')
    @patch('app.services.migration_runner.MigrationContext')
    def test_get_migration_history(self, mock_context_class, mock_create_engine, migration_runner):
        """Test getting migration history."""
        # Mock database connection and context
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        mock_context = Mock()
        
        mock_context_class.configure.return_value = mock_context
        mock_context.get_current_revision.return_value = 'current_rev'
        
        # Mock script directory with migrations
        mock_revision1 = Mock()
        mock_revision1.revision = 'abc123'
        mock_revision1.doc = 'First migration'
        mock_revision1.branch_labels = None
        mock_revision1.dependencies = None
        
        mock_revision2 = Mock()
        mock_revision2.revision = 'def456'
        mock_revision2.doc = 'Second migration'
        mock_revision2.branch_labels = ['feature']
        mock_revision2.dependencies = ['abc123']
        
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.walk_revisions.return_value = [mock_revision2, mock_revision1]
        migration_runner.script_directory.get_heads.return_value = ['def456']
        
        # Mock helper methods
        migration_runner._is_migration_applied = Mock(side_effect=lambda rev, current: rev == 'abc123')
        migration_runner._get_migration_date = Mock(return_value='2023-01-01')
        
        result = migration_runner.get_migration_history()
        
        assert len(result) == 2
        
        # Check first migration
        migration1 = next(m for m in result if m['revision'] == 'abc123')
        assert migration1['description'] == 'First migration'
        assert migration1['is_applied'] is True
        assert migration1['is_head'] is False
        
        # Check second migration
        migration2 = next(m for m in result if m['revision'] == 'def456')
        assert migration2['description'] == 'Second migration'
        assert migration2['is_applied'] is False
        assert migration2['is_head'] is True
        assert migration2['branch_labels'] == ['feature']
        assert migration2['depends_on'] == ['abc123']

    @patch('app.services.migration_runner.create_engine')
    @patch('app.services.migration_runner.MigrationContext')
    def test_validate_migration_state_valid(self, mock_context_class, mock_create_engine, migration_runner):
        """Test migration state validation when state is valid."""
        # Mock database connection and context
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        mock_context = Mock()
        
        mock_context_class.configure.return_value = mock_context
        mock_context.get_current_revision.return_value = 'current_rev'
        
        # Mock script directory
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.get_heads.return_value = ['head_rev']
        
        # Mock revision walking
        mock_revision = Mock()
        mock_revision.revision = 'current_rev'
        migration_runner.script_directory.walk_revisions.return_value = [mock_revision]
        
        # Mock pending migrations check
        migration_runner.check_pending_migrations = Mock(return_value=[])
        
        result = migration_runner.validate_migration_state()
        
        assert result['valid'] is True
        assert result['current_revision'] == 'current_rev'
        assert result['head_revisions'] == ['head_rev']
        assert result['pending_migrations'] == []
        assert len(result['issues']) == 0

    @patch('app.services.migration_runner.create_engine')
    @patch('app.services.migration_runner.MigrationContext')
    def test_validate_migration_state_multiple_heads(self, mock_context_class, mock_create_engine, migration_runner):
        """Test migration state validation with multiple heads."""
        # Mock database connection and context
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        mock_context = Mock()
        
        mock_context_class.configure.return_value = mock_context
        mock_context.get_current_revision.return_value = 'current_rev'
        
        # Mock script directory with multiple heads
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.get_heads.return_value = ['head1', 'head2']
        
        # Mock revision walking
        mock_revision = Mock()
        mock_revision.revision = 'current_rev'
        migration_runner.script_directory.walk_revisions.return_value = [mock_revision]
        
        # Mock pending migrations check
        migration_runner.check_pending_migrations = Mock(return_value=[])
        
        result = migration_runner.validate_migration_state()
        
        assert result['valid'] is False
        assert len(result['issues']) == 1
        assert 'Multiple migration heads found' in result['issues'][0]

    @patch('app.services.migration_runner.create_engine')
    @patch('app.services.migration_runner.MigrationContext')
    def test_get_current_revision(self, mock_context_class, mock_create_engine, migration_runner):
        """Test getting current database revision."""
        # Mock database connection and context
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        mock_context = Mock()
        
        mock_context_class.configure.return_value = mock_context
        mock_context.get_current_revision.return_value = 'abc123'
        
        result = migration_runner.get_current_revision()
        
        assert result == 'abc123'

    @patch('app.services.migration_runner.command')
    def test_stamp_database_success(self, mock_command, migration_runner):
        """Test successful database stamping."""
        mock_command.stamp = Mock()
        
        result = migration_runner.stamp_database('abc123')
        
        assert result is True
        mock_command.stamp.assert_called_once_with(migration_runner.alembic_config, 'abc123')

    @patch('app.services.migration_runner.command')
    def test_stamp_database_failure(self, mock_command, migration_runner):
        """Test database stamping failure."""
        mock_command.stamp.side_effect = Exception("Stamp failed")
        
        result = migration_runner.stamp_database('abc123')
        
        assert result is False

    @patch('app.services.migration_runner.command')
    def test_create_migration_success(self, mock_command, migration_runner):
        """Test successful migration creation."""
        mock_command.revision = Mock()
        
        # Mock script directory to return new revision
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.get_heads.return_value = ['new_rev_123']
        
        result = migration_runner.create_migration('Test migration', autogenerate=True)
        
        assert result == 'new_rev_123'
        mock_command.revision.assert_called_once_with(
            migration_runner.alembic_config,
            message='Test migration',
            autogenerate=True
        )

    @patch('app.services.migration_runner.command')
    def test_create_migration_failure(self, mock_command, migration_runner):
        """Test migration creation failure."""
        mock_command.revision.side_effect = Exception("Creation failed")
        
        result = migration_runner.create_migration('Test migration')
        
        assert result is None

    def test_get_migration_info_success(self, migration_runner):
        """Test getting migration info successfully."""
        # Mock script directory
        mock_migration = Mock()
        mock_migration.revision = 'abc123'
        mock_migration.doc = 'Test migration'
        mock_migration.branch_labels = ['feature']
        mock_migration.dependencies = ['prev_rev']
        
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.get_revision.return_value = mock_migration
        migration_runner.script_directory.get_heads.return_value = ['abc123']
        
        # Mock helper methods
        migration_runner.get_current_revision = Mock(return_value='abc123')
        migration_runner._is_migration_applied = Mock(return_value=True)
        
        result = migration_runner.get_migration_info('abc123')
        
        assert result is not None
        assert result.revision == 'abc123'
        assert result.description == 'Test migration'
        assert result.is_head is True
        assert result.is_applied is True
        assert result.branch_labels == ['feature']
        assert result.depends_on == ['prev_rev']

    def test_get_migration_info_not_found(self, migration_runner):
        """Test getting migration info for non-existent migration."""
        # Mock script directory returning None
        migration_runner.script_directory = Mock()
        migration_runner.script_directory.get_revision.return_value = None
        
        result = migration_runner.get_migration_info('nonexistent')
        
        assert result is None

    @patch('app.services.migration_runner.create_engine')
    @patch('app.services.migration_runner.text')
    def test_alembic_version_table_exists_true(self, mock_text, mock_create_engine, migration_runner):
        """Test checking alembic_version table existence when it exists."""
        # Mock database connection
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        mock_result = Mock()
        
        mock_connection.execute.return_value = mock_result
        mock_result.fetchone.return_value = ('some_version',)
        
        result = migration_runner._alembic_version_table_exists()
        
        assert result is True

    @patch('app.services.migration_runner.create_engine')
    def test_alembic_version_table_exists_false(self, mock_create_engine, migration_runner):
        """Test checking alembic_version table existence when it doesn't exist."""
        # Mock database connection that raises exception
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        
        mock_connection.execute.side_effect = Exception("Table doesn't exist")
        
        result = migration_runner._alembic_version_table_exists()
        
        assert result is False

    @patch('app.services.migration_runner.create_engine')
    @patch('app.services.migration_runner.text')
    def test_create_alembic_version_table_success(self, mock_text, mock_create_engine, migration_runner):
        """Test successful creation of alembic_version table."""
        # Mock database connection
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        
        result = migration_runner._create_alembic_version_table()
        
        assert result is True
        mock_connection.execute.assert_called()
        mock_connection.commit.assert_called_once()

    @patch('app.services.migration_runner.create_engine')
    def test_create_alembic_version_table_failure(self, mock_create_engine, migration_runner):
        """Test failure in creating alembic_version table."""
        # Mock database connection that raises exception
        mock_engine, mock_connection = self._setup_mock_connection(mock_create_engine)
        
        mock_connection.execute.side_effect = Exception("Creation failed")
        
        result = migration_runner._create_alembic_version_table()
        
        assert result is False

    def test_repair_migration_state_already_valid(self, migration_runner):
        """Test migration state repair when state is already valid."""
        # Mock validation returning valid state
        migration_runner.validate_migration_state = Mock(return_value={
            'valid': True,
            'issues': [],
            'head_revisions': ['abc123']
        })
        
        result = migration_runner.repair_migration_state()
        
        assert result['success'] is True
        assert len(result['repairs_performed']) == 0
        assert len(result['issues_found']) == 0

    def test_repair_migration_state_multiple_heads(self, migration_runner):
        """Test migration state repair with multiple heads."""
        # Mock validation returning invalid state with multiple heads
        migration_runner.validate_migration_state = Mock(return_value={
            'valid': False,
            'issues': ['Multiple heads detected'],
            'head_revisions': ['head1', 'head2']
        })
        
        result = migration_runner.repair_migration_state()
        
        assert result['success'] is False
        assert len(result['issues_found']) == 1
        assert 'Multiple migration heads detected' in result['manual_intervention_required'][0]

    def test_repair_migration_state_missing_table(self, migration_runner):
        """Test migration state repair with missing alembic_version table."""
        # Mock validation returning invalid state
        migration_runner.validate_migration_state = Mock(side_effect=[
            {
                'valid': False,
                'issues': ['Missing alembic_version table'],
                'head_revisions': ['abc123']
            },
            {
                'valid': True,
                'issues': [],
                'head_revisions': ['abc123']
            }
        ])
        
        # Mock table existence check and creation
        migration_runner._alembic_version_table_exists = Mock(return_value=False)
        migration_runner._create_alembic_version_table = Mock(return_value=True)
        
        result = migration_runner.repair_migration_state()
        
        assert result['success'] is True
        assert 'Created alembic_version table' in result['repairs_performed']


class TestMigrationResult:
    """Test cases for MigrationResult dataclass."""

    def test_migration_result_initialization(self):
        """Test MigrationResult initialization."""
        result = MigrationResult(
            success=True,
            migrations_applied=['abc123', 'def456']
        )
        
        assert result.success is True
        assert result.migrations_applied == ['abc123', 'def456']
        assert result.failed_migration is None
        assert result.error_message is None
        assert result.rollback_performed is False
        assert result.duration == 0.0
        assert result.warnings == []

    def test_migration_result_with_failure(self):
        """Test MigrationResult with failure information."""
        result = MigrationResult(
            success=False,
            migrations_applied=['abc123'],
            failed_migration='def456',
            error_message='Migration failed',
            rollback_performed=True,
            duration=5.5,
            warnings=['Warning message']
        )
        
        assert result.success is False
        assert result.migrations_applied == ['abc123']
        assert result.failed_migration == 'def456'
        assert result.error_message == 'Migration failed'
        assert result.rollback_performed is True
        assert result.duration == 5.5
        assert result.warnings == ['Warning message']


class TestMigrationInfo:
    """Test cases for MigrationInfo dataclass."""

    def test_migration_info_initialization(self):
        """Test MigrationInfo initialization."""
        info = MigrationInfo(
            revision='abc123',
            description='Test migration',
            is_head=True,
            is_applied=False,
            branch_labels=['feature'],
            depends_on=['prev_rev']
        )
        
        assert info.revision == 'abc123'
        assert info.description == 'Test migration'
        assert info.is_head is True
        assert info.is_applied is False
        assert info.branch_labels == ['feature']
        assert info.depends_on == ['prev_rev']

    def test_migration_info_minimal(self):
        """Test MigrationInfo with minimal information."""
        info = MigrationInfo(
            revision='abc123',
            description='Test migration',
            is_head=False,
            is_applied=True
        )
        
        assert info.revision == 'abc123'
        assert info.description == 'Test migration'
        assert info.is_head is False
        assert info.is_applied is True
        assert info.branch_labels is None
        assert info.depends_on is None