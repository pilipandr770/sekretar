"""
Test Environment Management

Manages isolated test environment with database and Redis instances.
"""
import asyncio
import logging
import os
import tempfile
import shutil
import subprocess
import time
from typing import Dict, Any, Optional
import redis
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sqlite3

from tests.infrastructure.models import TestEnvironmentConfig


class TestEnvironment:
    """
    Manages isolated test environment setup and cleanup.
    
    Provides isolated database and Redis instances for comprehensive testing.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize test environment manager."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Environment state
        self.is_setup = False
        self.temp_dir: Optional[str] = None
        self.test_db_path: Optional[str] = None
        self.redis_process: Optional[subprocess.Popen] = None
        self.postgres_process: Optional[subprocess.Popen] = None
        
        # Connection details
        self.database_url: Optional[str] = None
        self.redis_url: Optional[str] = None
        self.api_base_url: Optional[str] = None
        
        # Test environment configuration
        self.env_config = TestEnvironmentConfig(
            database_url=config.get('database_url', 'sqlite:///test.db'),
            redis_url=config.get('redis_url', 'redis://localhost:6380/0'),
            api_base_url=config.get('api_base_url', 'http://localhost:5001'),
            external_services=config.get('external_services', {}),
            test_data_path=config.get('test_data_path', 'test_data'),
            cleanup_on_exit=config.get('cleanup_on_exit', True),
            parallel_execution=config.get('parallel_execution', False),
            max_workers=config.get('max_workers', 4)
        )
    
    async def setup(self) -> bool:
        """
        Setup isolated test environment.
        
        Returns:
            bool: True if setup successful, False otherwise
        """
        try:
            self.logger.info("Setting up isolated test environment")
            
            # Create temporary directory for test environment
            self.temp_dir = tempfile.mkdtemp(prefix="ai_secretary_test_")
            self.logger.info(f"Created temporary directory: {self.temp_dir}")
            
            # Setup database
            await self._setup_database()
            
            # Setup Redis
            await self._setup_redis()
            
            # Setup test data directory
            await self._setup_test_data_directory()
            
            # Verify environment
            await self._verify_environment()
            
            self.is_setup = True
            self.logger.info("Test environment setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup test environment: {str(e)}")
            await self.cleanup()
            return False
    
    async def _setup_database(self):
        """Setup isolated test database."""
        self.logger.info("Setting up test database")
        
        db_type = self._detect_database_type()
        
        if db_type == 'sqlite':
            await self._setup_sqlite_database()
        elif db_type == 'postgresql':
            await self._setup_postgresql_database()
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def _detect_database_type(self) -> str:
        """Detect database type from configuration."""
        db_url = self.env_config.database_url
        if db_url.startswith('sqlite'):
            return 'sqlite'
        elif db_url.startswith('postgresql'):
            return 'postgresql'
        else:
            return 'sqlite'  # Default to SQLite for testing
    
    async def _setup_sqlite_database(self):
        """Setup SQLite test database."""
        self.test_db_path = os.path.join(self.temp_dir, 'test.db')
        self.database_url = f'sqlite:///{self.test_db_path}'
        
        # Create empty database file
        conn = sqlite3.connect(self.test_db_path)
        conn.close()
        
        self.logger.info(f"SQLite test database created: {self.test_db_path}")
    
    async def _setup_postgresql_database(self):
        """Setup PostgreSQL test database."""
        # For comprehensive testing, we'll use a dedicated test database
        # This assumes PostgreSQL is available on the system
        
        try:
            # Extract connection details from URL
            import urllib.parse as urlparse
            parsed = urlparse.urlparse(self.env_config.database_url)
            
            host = parsed.hostname or 'localhost'
            port = parsed.port or 5432
            username = parsed.username or 'postgres'
            password = parsed.password or ''
            
            # Create test database name
            test_db_name = f"ai_secretary_test_{int(time.time())}"
            
            # Connect to PostgreSQL and create test database
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            cursor = conn.cursor()
            cursor.execute(f'CREATE DATABASE "{test_db_name}"')
            cursor.close()
            conn.close()
            
            # Update database URL
            self.database_url = f'postgresql://{username}:{password}@{host}:{port}/{test_db_name}'
            
            self.logger.info(f"PostgreSQL test database created: {test_db_name}")
            
        except Exception as e:
            self.logger.warning(f"Failed to setup PostgreSQL test database: {str(e)}")
            self.logger.info("Falling back to SQLite for testing")
            await self._setup_sqlite_database()
    
    async def _setup_redis(self):
        """Setup isolated Redis instance for testing."""
        self.logger.info("Setting up test Redis instance")
        
        try:
            # Try to start Redis on a different port for testing
            redis_port = 6380
            redis_dir = os.path.join(self.temp_dir, 'redis')
            os.makedirs(redis_dir, exist_ok=True)
            
            # Create Redis configuration
            redis_conf = os.path.join(redis_dir, 'redis.conf')
            with open(redis_conf, 'w') as f:
                f.write(f"""
port {redis_port}
dir {redis_dir}
save ""
appendonly no
protected-mode no
bind 127.0.0.1
""")
            
            # Start Redis server
            self.redis_process = subprocess.Popen([
                'redis-server', redis_conf
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for Redis to start
            await asyncio.sleep(2)
            
            # Test connection
            redis_client = redis.Redis(host='localhost', port=redis_port, db=0)
            redis_client.ping()
            redis_client.close()
            
            self.redis_url = f'redis://localhost:{redis_port}/0'
            self.logger.info(f"Redis test instance started on port {redis_port}")
            
        except Exception as e:
            self.logger.warning(f"Failed to start dedicated Redis instance: {str(e)}")
            self.logger.info("Using default Redis configuration")
            self.redis_url = 'redis://localhost:6379/15'  # Use high DB number for testing
    
    async def _setup_test_data_directory(self):
        """Setup test data directory."""
        test_data_dir = os.path.join(self.temp_dir, 'test_data')
        os.makedirs(test_data_dir, exist_ok=True)
        
        # Update configuration
        self.env_config.test_data_path = test_data_dir
        
        self.logger.info(f"Test data directory created: {test_data_dir}")
    
    async def _verify_environment(self):
        """Verify test environment is working correctly."""
        self.logger.info("Verifying test environment")
        
        # Test database connection
        await self._verify_database_connection()
        
        # Test Redis connection
        await self._verify_redis_connection()
        
        self.logger.info("Test environment verification completed")
    
    async def _verify_database_connection(self):
        """Verify database connection."""
        try:
            if self.database_url.startswith('sqlite'):
                conn = sqlite3.connect(self.test_db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                cursor.close()
                conn.close()
            else:
                # PostgreSQL verification
                import urllib.parse as urlparse
                parsed = urlparse.urlparse(self.database_url)
                conn = psycopg2.connect(
                    host=parsed.hostname,
                    port=parsed.port,
                    user=parsed.username,
                    password=parsed.password,
                    database=parsed.path[1:]  # Remove leading slash
                )
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                cursor.close()
                conn.close()
            
            self.logger.info("Database connection verified")
            
        except Exception as e:
            raise RuntimeError(f"Database connection verification failed: {str(e)}")
    
    async def _verify_redis_connection(self):
        """Verify Redis connection."""
        try:
            import urllib.parse as urlparse
            parsed = urlparse.urlparse(self.redis_url)
            
            redis_client = redis.Redis(
                host=parsed.hostname or 'localhost',
                port=parsed.port or 6379,
                db=int(parsed.path[1:]) if parsed.path and len(parsed.path) > 1 else 0
            )
            redis_client.ping()
            redis_client.close()
            
            self.logger.info("Redis connection verified")
            
        except Exception as e:
            raise RuntimeError(f"Redis connection verification failed: {str(e)}")
    
    async def cleanup(self):
        """Cleanup test environment."""
        if not self.env_config.cleanup_on_exit:
            self.logger.info("Cleanup disabled, skipping environment cleanup")
            return
        
        self.logger.info("Cleaning up test environment")
        
        try:
            # Stop Redis process
            if self.redis_process:
                self.redis_process.terminate()
                try:
                    self.redis_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.redis_process.kill()
                self.redis_process = None
                self.logger.info("Redis process stopped")
            
            # Cleanup PostgreSQL test database
            if self.database_url and self.database_url.startswith('postgresql'):
                await self._cleanup_postgresql_database()
            
            # Remove temporary directory
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                self.logger.info(f"Removed temporary directory: {self.temp_dir}")
            
            self.is_setup = False
            self.logger.info("Test environment cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during test environment cleanup: {str(e)}")
    
    async def _cleanup_postgresql_database(self):
        """Cleanup PostgreSQL test database."""
        try:
            import urllib.parse as urlparse
            parsed = urlparse.urlparse(self.database_url)
            
            host = parsed.hostname or 'localhost'
            port = parsed.port or 5432
            username = parsed.username or 'postgres'
            password = parsed.password or ''
            test_db_name = parsed.path[1:]  # Remove leading slash
            
            # Connect to PostgreSQL and drop test database
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            cursor = conn.cursor()
            cursor.execute(f'DROP DATABASE IF EXISTS "{test_db_name}"')
            cursor.close()
            conn.close()
            
            self.logger.info(f"PostgreSQL test database dropped: {test_db_name}")
            
        except Exception as e:
            self.logger.warning(f"Failed to cleanup PostgreSQL test database: {str(e)}")
    
    def get_environment_config(self) -> TestEnvironmentConfig:
        """Get current environment configuration."""
        # Update URLs with actual values
        self.env_config.database_url = self.database_url or self.env_config.database_url
        self.env_config.redis_url = self.redis_url or self.env_config.redis_url
        
        return self.env_config
    
    def get_environment_variables(self) -> Dict[str, str]:
        """Get environment variables for test execution."""
        return {
            'TESTING': 'True',
            'DATABASE_URL': self.database_url or self.env_config.database_url,
            'REDIS_URL': self.redis_url or self.env_config.redis_url,
            'TEST_DATABASE_URL': self.database_url or self.env_config.database_url,
            'CELERY_BROKER_URL': self.redis_url or self.env_config.redis_url,
            'CELERY_RESULT_BACKEND': self.redis_url or self.env_config.redis_url,
            'FLASK_ENV': 'testing',
            'DB_SCHEMA': '',  # Disable schema for testing
            'HEALTH_CHECK_DATABASE_ENABLED': 'false',
            'HEALTH_CHECK_REDIS_ENABLED': 'false',
            'TENANT_MIDDLEWARE_ENABLED': 'false'
        }
    
    async def reset_environment(self):
        """Reset environment to clean state."""
        self.logger.info("Resetting test environment")
        
        try:
            # Clear Redis
            if self.redis_url:
                import urllib.parse as urlparse
                parsed = urlparse.urlparse(self.redis_url)
                redis_client = redis.Redis(
                    host=parsed.hostname or 'localhost',
                    port=parsed.port or 6379,
                    db=int(parsed.path[1:]) if parsed.path and len(parsed.path) > 1 else 0
                )
                redis_client.flushdb()
                redis_client.close()
                self.logger.info("Redis database cleared")
            
            # Clear database tables (if needed)
            # This would be implemented based on the specific database schema
            
            self.logger.info("Test environment reset completed")
            
        except Exception as e:
            self.logger.error(f"Failed to reset test environment: {str(e)}")
            raise