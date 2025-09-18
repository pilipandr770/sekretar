"""
Environment-Specific Database Initialization Configuration

This module provides environment-specific configuration and initialization
handling for different deployment environments (development, testing, production).
"""
import os
import sys
import time
import tempfile
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Supported environments."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class DatabaseType(Enum):
    """Supported database types."""
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    MYSQL = "mysql"


@dataclass
class EnvironmentConfig:
    """Environment-specific configuration."""
    environment: Environment
    database_type: DatabaseType
    database_url: str
    auto_create_database: bool = False
    auto_run_migrations: bool = True
    auto_seed_data: bool = True
    isolated_database: bool = False
    database_file_path: Optional[str] = None
    connection_timeout: int = 30
    pool_size: int = 5
    max_overflow: int = 10
    engine_options: Dict[str, Any] = field(default_factory=dict)
    initialization_options: Dict[str, Any] = field(default_factory=dict)


class EnvironmentDetector:
    """Detect and configure environment-specific settings."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def detect_environment(self) -> Environment:
        """
        Detect the current environment with enhanced detection logic.
        
        Returns:
            Environment enum value
        """
        # Check FLASK_ENV first (highest priority)
        flask_env = os.environ.get('FLASK_ENV', '').lower()
        if flask_env in ['production', 'prod']:
            self.logger.info("🚀 Environment detected: PRODUCTION (from FLASK_ENV)")
            return Environment.PRODUCTION
        elif flask_env in ['testing', 'test']:
            self.logger.info("🧪 Environment detected: TESTING (from FLASK_ENV)")
            return Environment.TESTING
        elif flask_env in ['development', 'dev']:
            self.logger.info("🔧 Environment detected: DEVELOPMENT (from FLASK_ENV)")
            return Environment.DEVELOPMENT
        
        # Check explicit testing indicators
        if os.environ.get('TESTING', '').lower() == 'true':
            self.logger.info("🧪 Environment detected: TESTING (from TESTING flag)")
            return Environment.TESTING
        
        # Check for pytest execution (only if no explicit FLASK_ENV is set and no production indicators)
        # Also check that we're not in a test that explicitly clears environment
        if (not flask_env and 
            not any(os.environ.get(var) for var in ['RENDER', 'HEROKU', 'AWS_LAMBDA_FUNCTION_NAME']) and
            os.environ.get('TESTING') != 'false' and  # Allow tests to disable this detection
            ('pytest' in os.environ.get('_', '') or any('pytest' in arg for arg in sys.argv))):
            self.logger.info("🧪 Environment detected: TESTING (pytest execution)")
            return Environment.TESTING
        
        # Check for production deployment platforms
        production_indicators = ['RENDER', 'HEROKU', 'AWS_LAMBDA_FUNCTION_NAME', 'VERCEL', 'NETLIFY']
        for indicator in production_indicators:
            if os.environ.get(indicator):
                self.logger.info(f"🚀 Environment detected: PRODUCTION (from {indicator})")
                return Environment.PRODUCTION
        
        # Check database URL patterns for environment hints
        database_url = self._get_database_url()
        if database_url:
            if 'test' in database_url.lower() or ':memory:' in database_url:
                self.logger.info("🧪 Environment detected: TESTING (from database URL)")
                return Environment.TESTING
            elif any(prod_db in database_url.lower() for prod_db in ['prod', 'production']):
                self.logger.info("🚀 Environment detected: PRODUCTION (from database URL)")
                return Environment.PRODUCTION
        
        # Check for development indicators
        if os.environ.get('DEBUG', '').lower() == 'true':
            self.logger.info("🔧 Environment detected: DEVELOPMENT (from DEBUG flag)")
            return Environment.DEVELOPMENT
        
        # Default to development with logging
        self.logger.info("🔧 Environment detected: DEVELOPMENT (default)")
        return Environment.DEVELOPMENT
    
    def detect_database_type(self, database_url: Optional[str] = None) -> DatabaseType:
        """
        Detect database type from URL or environment.
        
        Args:
            database_url: Database URL to analyze
            
        Returns:
            DatabaseType enum value
        """
        if not database_url:
            database_url = self._get_database_url()
        
        if not database_url:
            # Default to SQLite for development/testing
            return DatabaseType.SQLITE
        
        if database_url.startswith(('postgresql://', 'postgres://')):
            return DatabaseType.POSTGRESQL
        elif database_url.startswith('sqlite://'):
            return DatabaseType.SQLITE
        elif database_url.startswith('mysql://'):
            return DatabaseType.MYSQL
        else:
            self.logger.warning(f"Unknown database type in URL: {database_url}")
            return DatabaseType.SQLITE
    
    def get_environment_config(self, environment: Optional[Environment] = None) -> EnvironmentConfig:
        """
        Get environment-specific configuration.
        
        Args:
            environment: Environment to configure (auto-detect if None)
            
        Returns:
            EnvironmentConfig for the specified environment
        """
        if environment is None:
            environment = self.detect_environment()
        
        database_url = self._get_database_url()
        database_type = self.detect_database_type(database_url)
        
        if environment == Environment.DEVELOPMENT:
            return self._get_development_config(database_type, database_url)
        elif environment == Environment.TESTING:
            return self._get_testing_config(database_type, database_url)
        elif environment == Environment.PRODUCTION:
            return self._get_production_config(database_type, database_url)
        else:
            raise ValueError(f"Unsupported environment: {environment}")
    
    def _get_development_config(self, database_type: DatabaseType, database_url: str) -> EnvironmentConfig:
        """Get development environment configuration."""
        config = EnvironmentConfig(
            environment=Environment.DEVELOPMENT,
            database_type=database_type,
            database_url=database_url or self._get_default_sqlite_url(),
            auto_create_database=True,
            auto_run_migrations=True,
            auto_seed_data=True,
            isolated_database=False,
            connection_timeout=30,
            pool_size=5,
            max_overflow=10
        )
        
        if database_type == DatabaseType.SQLITE:
            config.database_file_path = self._extract_sqlite_path(config.database_url)
            config.engine_options = {
                'pool_pre_ping': True,
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': int(os.environ.get('SQLITE_TIMEOUT', '20'))
                }
            }
            config.initialization_options = {
                'create_directories': True,
                'backup_existing': False,
                'validate_permissions': True
            }
        elif database_type == DatabaseType.POSTGRESQL:
            config.engine_options = {
                'pool_pre_ping': True,
                'pool_recycle': 300,
                'pool_timeout': 20,
                'connect_args': {
                    'connect_timeout': 10,
                    'options': f'-csearch_path={os.environ.get("DB_SCHEMA", "public")},public'
                }
            }
            config.initialization_options = {
                'create_schema': True,
                'validate_connection': True,
                'retry_attempts': 3
            }
        
        return config
    
    def _get_testing_config(self, database_type: DatabaseType, database_url: str) -> EnvironmentConfig:
        """Get testing environment configuration."""
        # For testing, prefer isolated databases
        if database_type == DatabaseType.SQLITE or not database_url:
            # Use in-memory or temporary file database for testing
            test_db_url = os.environ.get('TEST_DATABASE_URL', 'sqlite:///:memory:')
            database_type = DatabaseType.SQLITE
        else:
            # Use separate test database for PostgreSQL
            test_db_url = self._get_test_database_url(database_url)
        
        config = EnvironmentConfig(
            environment=Environment.TESTING,
            database_type=database_type,
            database_url=test_db_url,
            auto_create_database=True,
            auto_run_migrations=True,
            auto_seed_data=True,
            isolated_database=True,
            connection_timeout=10,
            pool_size=1,
            max_overflow=0
        )
        
        if database_type == DatabaseType.SQLITE:
            if test_db_url == 'sqlite:///:memory:':
                config.database_file_path = ':memory:'
            else:
                config.database_file_path = self._extract_sqlite_path(test_db_url)
            
            config.engine_options = {
                'pool_pre_ping': True,
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': 5
                }
            }
            config.initialization_options = {
                'create_directories': True,
                'cleanup_on_exit': True,
                'fast_initialization': True
            }
        elif database_type == DatabaseType.POSTGRESQL:
            config.engine_options = {
                'pool_pre_ping': True,
                'pool_timeout': 10,
                'connect_args': {
                    'connect_timeout': 5
                }
            }
            config.initialization_options = {
                'create_test_schema': True,
                'cleanup_on_exit': True,
                'fast_initialization': True
            }
        
        return config
    
    def _get_production_config(self, database_type: DatabaseType, database_url: str) -> EnvironmentConfig:
        """Get production environment configuration."""
        if not database_url:
            raise ValueError("DATABASE_URL is required for production environment")
        
        config = EnvironmentConfig(
            environment=Environment.PRODUCTION,
            database_type=database_type,
            database_url=database_url,
            auto_create_database=False,  # Don't auto-create in production
            auto_run_migrations=True,
            auto_seed_data=False,  # Don't auto-seed in production
            isolated_database=False,
            connection_timeout=60,
            pool_size=10,
            max_overflow=20
        )
        
        if database_type == DatabaseType.SQLITE:
            config.database_file_path = self._extract_sqlite_path(database_url)
            config.engine_options = {
                'pool_pre_ping': True,
                'pool_recycle': 3600,
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': int(os.environ.get('SQLITE_TIMEOUT', '30'))
                }
            }
            config.initialization_options = {
                'validate_permissions': True,
                'backup_before_migration': True,
                'strict_validation': True
            }
        elif database_type == DatabaseType.POSTGRESQL:
            config.engine_options = {
                'pool_pre_ping': True,
                'pool_recycle': 3600,
                'pool_timeout': 30,
                'connect_args': {
                    'connect_timeout': 30,
                    'options': f'-csearch_path={os.environ.get("DB_SCHEMA", "public")},public'
                }
            }
            config.initialization_options = {
                'validate_connection': True,
                'backup_before_migration': True,
                'strict_validation': True,
                'retry_attempts': 5
            }
        
        return config
    
    def _get_database_url(self) -> Optional[str]:
        """Get database URL from environment variables."""
        # Try various environment variable names
        for var_name in ['DATABASE_URL', 'SQLALCHEMY_DATABASE_URI', 'DB_URL']:
            url = os.environ.get(var_name)
            if url:
                # Handle Render.com postgres:// format
                if url.startswith('postgres://'):
                    url = url.replace('postgres://', 'postgresql://', 1)
                return url
        
        # Try SQLite-specific URL
        sqlite_url = os.environ.get('SQLITE_DATABASE_URL')
        if sqlite_url:
            return sqlite_url
        
        return None
    
    def _get_default_sqlite_url(self) -> str:
        """Get default SQLite database URL for development."""
        return os.environ.get('SQLITE_DATABASE_URL', 'sqlite:///ai_secretary.db')
    
    def _extract_sqlite_path(self, sqlite_url: str) -> str:
        """Extract file path from SQLite URL."""
        if sqlite_url == 'sqlite:///:memory:':
            return ':memory:'
        elif sqlite_url.startswith('sqlite:///'):
            return sqlite_url[10:]  # Remove 'sqlite:///'
        elif sqlite_url.startswith('sqlite://'):
            return sqlite_url[9:]   # Remove 'sqlite://'
        else:
            return sqlite_url
    
    def _get_test_database_url(self, base_url: str) -> str:
        """Generate test database URL from base URL."""
        if base_url.startswith('postgresql://') or base_url.startswith('postgres://'):
            # Replace database name with test version
            parts = base_url.split('/')
            if len(parts) > 3:
                db_name = parts[-1]
                test_db_name = f"{db_name}_test"
                parts[-1] = test_db_name
                return '/'.join(parts)
        elif base_url.startswith('sqlite://'):
            # Use separate test file
            if base_url == 'sqlite:///:memory:':
                return base_url
            else:
                path = self._extract_sqlite_path(base_url)
                if path != ':memory:':
                    test_path = f"test_{path}"
                    return f"sqlite:///{test_path}"
        
        return base_url


class EnvironmentInitializer:
    """Environment-specific database initialization logic."""
    
    def __init__(self, config: EnvironmentConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._initialization_state = {}
    
    def prepare_environment(self) -> bool:
        """
        Prepare the environment for database initialization.
        
        Returns:
            True if preparation successful, False otherwise
        """
        try:
            self.logger.info(f"🌍 Preparing {self.config.environment.value} environment for database initialization")
            
            # Store initialization start time
            self._initialization_state['start_time'] = time.time()
            self._initialization_state['environment'] = self.config.environment.value
            self._initialization_state['database_type'] = self.config.database_type.value
            
            if self.config.environment == Environment.DEVELOPMENT:
                return self._prepare_development_environment()
            elif self.config.environment == Environment.TESTING:
                return self._prepare_testing_environment()
            elif self.config.environment == Environment.PRODUCTION:
                return self._prepare_production_environment()
            else:
                self.logger.error(f"Unsupported environment: {self.config.environment}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to prepare environment: {str(e)}")
            self._initialization_state['error'] = str(e)
            return False
        finally:
            # Store preparation duration
            if 'start_time' in self._initialization_state:
                self._initialization_state['preparation_duration'] = time.time() - self._initialization_state['start_time']
    
    def _prepare_development_environment(self) -> bool:
        """Prepare development environment with SQLite auto-creation."""
        self.logger.info("🔧 Preparing development environment...")
        
        # Development environment should prioritize ease of setup
        if self.config.database_type == DatabaseType.SQLITE:
            success = self._prepare_sqlite_development()
            if success:
                self.logger.info("✅ Development SQLite environment prepared successfully")
                self._initialization_state['sqlite_auto_created'] = True
            return success
        elif self.config.database_type == DatabaseType.POSTGRESQL:
            success = self._prepare_postgresql_development()
            if success:
                self.logger.info("✅ Development PostgreSQL environment prepared successfully")
                self._initialization_state['postgresql_configured'] = True
            return success
        else:
            self.logger.warning(f"Unsupported database type for development: {self.config.database_type}")
            # In development, we can fallback to SQLite
            self.logger.info("🔄 Falling back to SQLite for development environment")
            self.config.database_type = DatabaseType.SQLITE
            self.config.database_url = self._get_default_sqlite_url()
            self.config.database_file_path = self._extract_sqlite_path(self.config.database_url)
            return self._prepare_sqlite_development()
    
    def _prepare_testing_environment(self) -> bool:
        """Prepare testing environment with isolated test databases."""
        self.logger.info("🧪 Preparing testing environment with isolated databases...")
        
        # Testing environment should use isolated databases
        if self.config.database_type == DatabaseType.SQLITE:
            success = self._prepare_sqlite_testing()
            if success:
                self.logger.info("✅ Testing SQLite environment prepared with isolation")
                self._initialization_state['isolated_database'] = True
                self._initialization_state['test_database_path'] = self.config.database_file_path
            return success
        elif self.config.database_type == DatabaseType.POSTGRESQL:
            success = self._prepare_postgresql_testing()
            if success:
                self.logger.info("✅ Testing PostgreSQL environment prepared with isolation")
                self._initialization_state['isolated_database'] = True
                self._initialization_state['test_database_url'] = self.config.database_url
            return success
        else:
            # For testing, always fallback to in-memory SQLite for maximum isolation
            self.logger.info("🔄 Falling back to in-memory SQLite for testing environment")
            self.config.database_type = DatabaseType.SQLITE
            self.config.database_url = 'sqlite:///:memory:'
            self.config.database_file_path = ':memory:'
            self.config.isolated_database = True
            self._initialization_state['fallback_to_memory'] = True
            return self._prepare_sqlite_testing()
    
    def _prepare_production_environment(self) -> bool:
        """Prepare production environment with PostgreSQL/SQLite support."""
        self.logger.info("🚀 Preparing production environment...")
        
        # Production environment requires strict validation
        if self.config.database_type == DatabaseType.POSTGRESQL:
            success = self._prepare_postgresql_production()
            if success:
                self.logger.info("✅ Production PostgreSQL environment prepared successfully")
                self._initialization_state['production_database'] = 'postgresql'
                self._initialization_state['strict_validation'] = True
            return success
        elif self.config.database_type == DatabaseType.SQLITE:
            success = self._prepare_sqlite_production()
            if success:
                self.logger.info("✅ Production SQLite environment prepared successfully")
                self._initialization_state['production_database'] = 'sqlite'
                self._initialization_state['strict_validation'] = True
            return success
        else:
            self.logger.error(f"Unsupported database type for production: {self.config.database_type}")
            self.logger.error("Production environment requires PostgreSQL or SQLite")
            self._initialization_state['error'] = f"Unsupported database type: {self.config.database_type}"
            return False
    
    def _prepare_sqlite_development(self) -> bool:
        """Prepare SQLite for development environment with auto-creation."""
        if self.config.database_file_path == ':memory:':
            self.logger.info("📝 Using in-memory SQLite database for development")
            return True
        
        db_path = Path(self.config.database_file_path)
        
        # Auto-create directory structure for development
        if self.config.initialization_options.get('create_directories', True):
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"📁 Auto-created database directory: {db_path.parent}")
                self._initialization_state['directory_created'] = str(db_path.parent)
            except Exception as e:
                self.logger.error(f"❌ Failed to create database directory: {e}")
                return False
        
        # Validate permissions for development
        if self.config.initialization_options.get('validate_permissions', True):
            if not os.access(db_path.parent, os.W_OK):
                self.logger.error(f"❌ No write permission for database directory: {db_path.parent}")
                self.logger.info("💡 Try running: chmod 755 {db_path.parent}")
                return False
        
        # For development, remove existing database if it exists and is corrupted
        if db_path.exists() and self.config.initialization_options.get('reset_on_corruption', True):
            try:
                # Quick corruption check
                import sqlite3
                conn = sqlite3.connect(str(db_path))
                conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
                conn.close()
                self.logger.info(f"📝 Existing SQLite database validated: {db_path}")
            except Exception as e:
                self.logger.warning(f"⚠️ Existing database appears corrupted, removing: {e}")
                try:
                    conn.close()
                except:
                    pass
                try:
                    db_path.unlink()
                    self._initialization_state['corrupted_db_removed'] = True
                except Exception as unlink_error:
                    self.logger.warning(f"⚠️ Could not remove corrupted database: {unlink_error}")
                    self._initialization_state['corrupted_db_removal_failed'] = True
        
        self.logger.info(f"📝 SQLite database will be auto-created at: {db_path}")
        self._initialization_state['database_path'] = str(db_path)
        return True
    
    def _prepare_postgresql_development(self) -> bool:
        """Prepare PostgreSQL for development environment."""
        self.logger.info("🐘 Preparing PostgreSQL for development")
        
        # For development, we assume PostgreSQL is already running
        # We'll validate connection during initialization
        return True
    
    def _prepare_sqlite_testing(self) -> bool:
        """Prepare SQLite for testing environment with complete isolation."""
        if self.config.database_file_path == ':memory:':
            self.logger.info("🧪 Using in-memory SQLite database for complete test isolation")
            self._initialization_state['memory_database'] = True
            return True
        
        db_path = Path(self.config.database_file_path)
        
        # Ensure test database is in a test-specific directory
        if not str(db_path).startswith(('test_', '/tmp/', tempfile.gettempdir())):
            # Create isolated test database path
            test_dir = Path(tempfile.gettempdir()) / 'ai_secretary_tests'
            test_dir.mkdir(exist_ok=True)
            db_path = test_dir / f"test_{int(time.time())}_{os.getpid()}.db"
            self.config.database_file_path = str(db_path)
            self.config.database_url = f"sqlite:///{db_path}"
            self.logger.info(f"🔒 Created isolated test database path: {db_path}")
            self._initialization_state['isolated_path_created'] = str(db_path)
        
        # Create directory if needed
        if self.config.initialization_options.get('create_directories', True):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Always clean up existing test database for complete isolation
        if db_path.exists():
            db_path.unlink()
            self.logger.info(f"🧹 Cleaned up existing test database for isolation: {db_path}")
            self._initialization_state['cleaned_existing'] = True
        
        # Set fast initialization options for testing
        self.config.engine_options.update({
            'pool_pre_ping': False,  # Skip for speed in tests
            'connect_args': {
                'check_same_thread': False,
                'timeout': 5,  # Short timeout for tests
                'isolation_level': None  # Autocommit mode for tests
            }
        })
        
        self.logger.info(f"🧪 Isolated test SQLite database will be created at: {db_path}")
        self._initialization_state['test_database_path'] = str(db_path)
        return True
    
    def _prepare_postgresql_testing(self) -> bool:
        """Prepare PostgreSQL for testing environment with isolation."""
        self.logger.info("🧪 Preparing PostgreSQL for testing with database isolation")
        
        # Ensure we're using a test database
        if not ('_test' in self.config.database_url or 'test_' in self.config.database_url):
            # Create isolated test database URL
            base_url = self.config.database_url
            if base_url.count('/') >= 3:
                parts = base_url.split('/')
                db_name = parts[-1]
                test_db_name = f"test_{db_name}_{int(time.time())}_{os.getpid()}"
                parts[-1] = test_db_name
                self.config.database_url = '/'.join(parts)
                self.logger.info(f"🔒 Created isolated test database URL with name: {test_db_name}")
                self._initialization_state['isolated_test_db'] = test_db_name
        
        # Set fast connection options for testing
        self.config.engine_options.update({
            'pool_pre_ping': False,  # Skip for speed in tests
            'pool_size': 1,  # Minimal pool for tests
            'max_overflow': 0,  # No overflow for tests
            'pool_timeout': 5,  # Short timeout for tests
            'connect_args': {
                'connect_timeout': 5,
                'application_name': 'ai_secretary_test'
            }
        })
        
        # Enable fast initialization for testing
        self.config.initialization_options.update({
            'fast_initialization': True,
            'skip_validation': True,  # Skip some validations for speed
            'cleanup_on_exit': True
        })
        
        self.logger.info("✅ PostgreSQL testing environment configured with isolation")
        return True
    
    def _prepare_sqlite_production(self) -> bool:
        """Prepare SQLite for production environment."""
        if self.config.database_file_path == ':memory:':
            self.logger.error("❌ In-memory database not allowed in production")
            return False
        
        db_path = Path(self.config.database_file_path)
        
        # Validate directory exists and is writable
        if not db_path.parent.exists():
            self.logger.error(f"❌ Database directory does not exist: {db_path.parent}")
            return False
        
        if not os.access(db_path.parent, os.W_OK):
            self.logger.error(f"❌ No write permission for database directory: {db_path.parent}")
            return False
        
        # Backup existing database if requested
        if self.config.initialization_options.get('backup_before_migration', True) and db_path.exists():
            backup_path = db_path.with_suffix(f'.backup.{int(time.time())}.db')
            import shutil
            shutil.copy2(db_path, backup_path)
            self.logger.info(f"💾 Created database backup: {backup_path}")
        
        self.logger.info(f"🚀 Production SQLite database at: {db_path}")
        self._initialization_state['production_database'] = 'sqlite'
        self._initialization_state['strict_validation'] = True
        return True
    
    def _prepare_postgresql_production(self) -> bool:
        """Prepare PostgreSQL for production environment."""
        self.logger.info("🚀 Preparing PostgreSQL for production")
        
        # For production, we assume the database server is properly configured
        # We'll validate connection and permissions during initialization
        self._initialization_state['production_database'] = 'postgresql'
        self._initialization_state['strict_validation'] = True
        return True
    
    def cleanup_environment(self) -> bool:
        """
        Clean up environment after initialization (mainly for testing).
        
        Returns:
            True if cleanup successful, False otherwise
        """
        if not self.config.initialization_options.get('cleanup_on_exit', False):
            return True
        
        try:
            if self.config.database_type == DatabaseType.SQLITE:
                return self._cleanup_sqlite()
            elif self.config.database_type == DatabaseType.POSTGRESQL:
                return self._cleanup_postgresql()
            else:
                return True
        except Exception as e:
            self.logger.error(f"Failed to cleanup environment: {str(e)}")
            return False
    
    def _cleanup_sqlite(self) -> bool:
        """Clean up SQLite database files."""
        if self.config.database_file_path == ':memory:':
            return True  # Nothing to clean up for in-memory database
        
        db_path = Path(self.config.database_file_path)
        if db_path.exists():
            db_path.unlink()
            self.logger.info(f"🧹 Cleaned up test database: {db_path}")
        
        return True
    
    def _cleanup_postgresql(self) -> bool:
        """Clean up PostgreSQL test database."""
        # For PostgreSQL, we might want to drop test tables or schema
        # This would be implemented based on specific requirements
        self.logger.info("🧹 PostgreSQL cleanup completed")
        return True
    
    def _get_default_sqlite_url(self) -> str:
        """Get default SQLite database URL for the current environment."""
        if self.config.environment == Environment.TESTING:
            return 'sqlite:///:memory:'
        elif self.config.environment == Environment.DEVELOPMENT:
            return os.environ.get('SQLITE_DATABASE_URL', 'sqlite:///ai_secretary_dev.db')
        else:  # Production
            return os.environ.get('SQLITE_DATABASE_URL', 'sqlite:///ai_secretary.db')
    
    def _extract_sqlite_path(self, sqlite_url: str) -> str:
        """Extract file path from SQLite URL."""
        if sqlite_url == 'sqlite:///:memory:':
            return ':memory:'
        elif sqlite_url.startswith('sqlite:///'):
            return sqlite_url[10:]  # Remove 'sqlite:///'
        elif sqlite_url.startswith('sqlite://'):
            return sqlite_url[9:]   # Remove 'sqlite://'
        else:
            return sqlite_url
    
    def get_initialization_state(self) -> Dict[str, Any]:
        """
        Get the current initialization state.
        
        Returns:
            Dictionary with initialization state information
        """
        return self._initialization_state.copy()


def get_environment_config(environment: Optional[Environment] = None) -> EnvironmentConfig:
    """
    Get environment-specific configuration.
    
    Args:
        environment: Environment to configure (auto-detect if None)
        
    Returns:
        EnvironmentConfig for the specified environment
    """
    detector = EnvironmentDetector()
    return detector.get_environment_config(environment)


def create_environment_initializer(config: Optional[EnvironmentConfig] = None) -> EnvironmentInitializer:
    """
    Create environment initializer with configuration.
    
    Args:
        config: Environment configuration (auto-detect if None)
        
    Returns:
        EnvironmentInitializer instance
    """
    if config is None:
        config = get_environment_config()
    
    return EnvironmentInitializer(config)