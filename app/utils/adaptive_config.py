"""
Adaptive Configuration Manager

This module provides adaptive configuration management that automatically
detects available services and configures the application accordingly.
"""
import os
import logging
import socket
import time
from typing import Dict, Optional, Type, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import psycopg2
import sqlite3
import redis
from config import Config, DevelopmentConfig, TestingConfig, ProductionConfig


logger = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    """Service availability status."""
    name: str
    available: bool
    last_check: datetime
    error_message: Optional[str] = None
    connection_string: Optional[str] = None


@dataclass
class DatabaseConfig:
    """Database configuration."""
    type: str  # 'postgresql' or 'sqlite'
    connection_string: str
    schema: Optional[str] = None
    engine_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdaptiveApplicationConfig:
    """Adaptive application configuration."""
    database: DatabaseConfig
    services: Dict[str, ServiceStatus]
    features: Dict[str, bool]
    environment: str
    base_config_class: Type[Config]


class AdaptiveConfigManager:
    """
    Manages adaptive configuration based on available services.
    
    This class detects available database systems, cache backends, and other
    services, then creates appropriate configuration objects.
    """
    
    def __init__(self, environment: Optional[str] = None):
        """Initialize the adaptive config manager."""
        self.environment = environment or self._detect_environment()
        self.services: Dict[str, ServiceStatus] = {}
        self._connection_timeout = 5  # seconds
        
    def _detect_environment(self) -> str:
        """Detect the current environment."""
        flask_env = os.environ.get('FLASK_ENV', '').lower()
        if flask_env in ['production', 'prod']:
            return 'production'
        elif flask_env in ['testing', 'test']:
            return 'testing'
        else:
            return 'development'
    
    def detect_database(self) -> Tuple[str, str]:
        """
        Detect available database system.
        
        Returns:
            Tuple of (database_type, connection_string)
        """
        logger.info("Detecting available database systems...")
        
        # Check for explicit SQLite mode
        force_sqlite = os.environ.get('FORCE_SQLITE', '').lower() in ['true', '1', 'yes']
        prefer_sqlite = os.environ.get('PREFER_SQLITE', '').lower() in ['true', '1', 'yes']
        
        if force_sqlite:
            logger.info("🔒 FORCE_SQLITE enabled - using SQLite exclusively")
            db_type = 'sqlite'
            connection_string = self._get_sqlite_connection_string()
            logger.info(f"✅ SQLite forced: {connection_string}")
            return db_type, connection_string
        
        if prefer_sqlite:
            logger.info("⚡ PREFER_SQLITE enabled - trying SQLite first")
            # Try SQLite first when preferred
            if self._test_sqlite_connection():
                db_type = 'sqlite'
                connection_string = self._get_sqlite_connection_string()
                logger.info(f"✅ SQLite preferred: {connection_string}")
                return db_type, connection_string
            
            # Fallback to PostgreSQL if SQLite fails
            if self._test_postgresql_connection():
                db_type = 'postgresql'
                connection_string = self._get_postgresql_connection_string()
                logger.info(f"✅ PostgreSQL fallback: {connection_string}")
                return db_type, connection_string
        else:
            # Default behavior: try PostgreSQL first
            if self._test_postgresql_connection():
                db_type = 'postgresql'
                connection_string = self._get_postgresql_connection_string()
                logger.info(f"✅ PostgreSQL detected: {connection_string}")
                return db_type, connection_string
        
        # Final fallback to SQLite
        db_type = 'sqlite'
        connection_string = self._get_sqlite_connection_string()
        logger.info(f"✅ SQLite fallback: {connection_string}")
        return db_type, connection_string
    
    def _test_postgresql_connection(self) -> bool:
        """Test PostgreSQL connection availability."""
        try:
            connection_string = self._get_postgresql_connection_string()
            
            # Parse connection string to get host and port
            if connection_string.startswith('postgresql://'):
                # Extract host and port from connection string
                import urllib.parse
                parsed = urllib.parse.urlparse(connection_string)
                host = parsed.hostname or 'localhost'
                port = parsed.port or 5432
                
                # Test socket connection first (faster than database connection)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self._connection_timeout)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result != 0:
                    self.services['postgresql'] = ServiceStatus(
                        name='postgresql',
                        available=False,
                        last_check=datetime.now(),
                        error_message=f"Cannot connect to PostgreSQL at {host}:{port}",
                        connection_string=connection_string
                    )
                    return False
                
                # Test actual database connection
                conn = psycopg2.connect(connection_string, connect_timeout=self._connection_timeout)
                conn.close()
                
                self.services['postgresql'] = ServiceStatus(
                    name='postgresql',
                    available=True,
                    last_check=datetime.now(),
                    connection_string=connection_string
                )
                return True
                
        except Exception as e:
            self.services['postgresql'] = ServiceStatus(
                name='postgresql',
                available=False,
                last_check=datetime.now(),
                error_message=str(e)
            )
            logger.debug(f"PostgreSQL connection failed: {e}")
            return False
    
    def _test_sqlite_connection(self) -> bool:
        """Test SQLite connection availability."""
        try:
            connection_string = self._get_sqlite_connection_string()
            
            # Extract file path from connection string
            if connection_string.startswith('sqlite:///'):
                db_path = connection_string[10:]  # Remove 'sqlite:///'
                
                # For in-memory database, always return True
                if db_path == ':memory:':
                    self.services['sqlite'] = ServiceStatus(
                        name='sqlite',
                        available=True,
                        last_check=datetime.now(),
                        connection_string=connection_string
                    )
                    return True
                
                # For file database, check if we can create/access it
                try:
                    conn = sqlite3.connect(db_path, timeout=self._connection_timeout)
                    conn.close()
                    
                    self.services['sqlite'] = ServiceStatus(
                        name='sqlite',
                        available=True,
                        last_check=datetime.now(),
                        connection_string=connection_string
                    )
                    return True
                    
                except Exception as e:
                    self.services['sqlite'] = ServiceStatus(
                        name='sqlite',
                        available=False,
                        last_check=datetime.now(),
                        error_message=str(e),
                        connection_string=connection_string
                    )
                    return False
            
        except Exception as e:
            self.services['sqlite'] = ServiceStatus(
                name='sqlite',
                available=False,
                last_check=datetime.now(),
                error_message=str(e)
            )
            logger.debug(f"SQLite connection failed: {e}")
            return False
    
    def _get_postgresql_connection_string(self) -> str:
        """Get PostgreSQL connection string from environment."""
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Handle Render.com format
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            return database_url
        
        # Build from individual components
        host = os.environ.get('DB_HOST', 'localhost')
        port = os.environ.get('DB_PORT', '5432')
        database = os.environ.get('DB_NAME', 'ai_secretary')
        username = os.environ.get('DB_USER', 'postgres')
        password = os.environ.get('DB_PASSWORD', '')
        
        if password:
            return f'postgresql://{username}:{password}@{host}:{port}/{database}'
        else:
            return f'postgresql://{username}@{host}:{port}/{database}'
    
    def _get_sqlite_connection_string(self) -> str:
        """Get SQLite connection string."""
        # Check for explicit SQLite URL
        sqlite_url = os.environ.get('SQLITE_DATABASE_URL')
        if sqlite_url:
            return sqlite_url
        
        # Use default SQLite database
        if self.environment == 'testing':
            return 'sqlite:///:memory:'
        else:
            return 'sqlite:///ai_secretary.db'
    
    def detect_cache_backend(self) -> str:
        """
        Detect available cache backend.
        
        Returns:
            Cache backend type ('redis' or 'simple')
        """
        logger.info("Detecting available cache backend...")
        
        # Try Redis first
        if self._test_redis_connection():
            logger.info("✅ Redis cache backend detected")
            return 'redis'
        
        # Fallback to simple cache
        logger.info("✅ Simple cache backend (fallback)")
        return 'simple'
    
    def _test_redis_connection(self) -> bool:
        """Test Redis connection availability."""
        try:
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
            
            # Parse Redis URL to get host and port
            import urllib.parse
            parsed = urllib.parse.urlparse(redis_url)
            host = parsed.hostname or 'localhost'
            port = parsed.port or 6379
            
            # Test socket connection first
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._connection_timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result != 0:
                self.services['redis'] = ServiceStatus(
                    name='redis',
                    available=False,
                    last_check=datetime.now(),
                    error_message=f"Cannot connect to Redis at {host}:{port}"
                )
                return False
            
            # Test actual Redis connection
            r = redis.from_url(redis_url, socket_connect_timeout=self._connection_timeout)
            r.ping()
            
            self.services['redis'] = ServiceStatus(
                name='redis',
                available=True,
                last_check=datetime.now(),
                connection_string=redis_url
            )
            return True
            
        except Exception as e:
            self.services['redis'] = ServiceStatus(
                name='redis',
                available=False,
                last_check=datetime.now(),
                error_message=str(e)
            )
            logger.debug(f"Redis connection failed: {e}")
            return False
    
    def get_config_class(self) -> Type[Config]:
        """
        Get appropriate configuration class based on detected services.
        
        Returns:
            Configuration class adapted for available services
        """
        # Get base configuration class
        base_configs = {
            'development': DevelopmentConfig,
            'testing': TestingConfig,
            'production': ProductionConfig
        }
        
        base_config = base_configs.get(self.environment, DevelopmentConfig)
        
        # Create adaptive configuration class
        class AdaptiveConfig(base_config):
            """Dynamically created configuration class based on available services."""
            pass
        
        # Detect and configure database
        db_type, db_connection_string = self.detect_database()
        
        if db_type == 'sqlite':
            # SQLite-specific configuration
            AdaptiveConfig.SQLALCHEMY_DATABASE_URI = db_connection_string
            AdaptiveConfig.SQLALCHEMY_ENGINE_OPTIONS = {
                'pool_pre_ping': True,
                'pool_recycle': 300,
                # SQLite doesn't support pool_timeout and max_overflow
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': 20
                }
            }
            # Remove PostgreSQL-specific schema configuration
            AdaptiveConfig.DB_SCHEMA = None
        else:
            # PostgreSQL configuration (use base config)
            AdaptiveConfig.SQLALCHEMY_DATABASE_URI = db_connection_string
        
        # Detect and configure cache backend
        cache_backend = self.detect_cache_backend()
        
        if cache_backend == 'simple':
            AdaptiveConfig.CACHE_TYPE = 'simple'
            # Remove Redis-specific cache configuration
            AdaptiveConfig.CACHE_REDIS_URL = None
        
        # Add service status information
        AdaptiveConfig.DETECTED_DATABASE_TYPE = db_type
        AdaptiveConfig.DETECTED_CACHE_BACKEND = cache_backend
        AdaptiveConfig.SERVICE_STATUS = self.services.copy()
        
        # Add feature flags based on service availability
        AdaptiveConfig.FEATURES = self._get_feature_flags()
        
        return AdaptiveConfig
    
    def _get_feature_flags(self) -> Dict[str, bool]:
        """Get feature flags based on service availability."""
        features = {
            'database_postgresql': self.services.get('postgresql', ServiceStatus('postgresql', False, datetime.now())).available,
            'database_sqlite': self.services.get('sqlite', ServiceStatus('sqlite', True, datetime.now())).available,
            'cache_redis': self.services.get('redis', ServiceStatus('redis', False, datetime.now())).available,
            'cache_simple': True,  # Always available
        }
        
        # Add external service features
        features.update({
            'celery': features['cache_redis'],  # Celery requires Redis
            'rate_limiting': features['cache_redis'],  # Rate limiting requires Redis
            'websockets': True,  # SocketIO can work without Redis
        })
        
        return features
    
    def validate_services(self) -> Dict[str, bool]:
        """
        Validate all configured services.
        
        Returns:
            Dictionary of service names and their availability status
        """
        logger.info("Validating all services...")
        
        # Re-test all services
        postgresql_available = self._test_postgresql_connection()
        sqlite_available = self._test_sqlite_connection()
        redis_available = self._test_redis_connection()
        
        # Return availability status
        return {
            'postgresql': postgresql_available,
            'sqlite': sqlite_available,
            'redis': redis_available
        }
    
    def get_service_status(self) -> Dict[str, ServiceStatus]:
        """Get current service status."""
        return self.services.copy()
    
    def create_adaptive_config(self) -> AdaptiveApplicationConfig:
        """
        Create complete adaptive configuration.
        
        Returns:
            AdaptiveApplicationConfig with all detected services and features
        """
        # Detect database
        db_type, db_connection_string = self.detect_database()
        
        # Create database config
        database_config = DatabaseConfig(
            type=db_type,
            connection_string=db_connection_string,
            schema=os.environ.get('DB_SCHEMA') if db_type == 'postgresql' else None,
            engine_options=self._get_database_engine_options(db_type)
        )
        
        # Get configuration class
        config_class = self.get_config_class()
        
        # Create adaptive config
        adaptive_config = AdaptiveApplicationConfig(
            database=database_config,
            services=self.get_service_status(),
            features=self._get_feature_flags(),
            environment=self.environment,
            base_config_class=config_class
        )
        
        return adaptive_config
    
    def _get_database_engine_options(self, db_type: str) -> Dict[str, Any]:
        """Get database engine options based on database type."""
        if db_type == 'postgresql':
            schema = os.environ.get('DB_SCHEMA', 'ai_secretary')
            return {
                'pool_pre_ping': True,
                'pool_recycle': 300,
                'pool_timeout': 20,
                'max_overflow': 0,
                'connect_args': {
                    'options': f'-csearch_path={schema},public'
                }
            }
        else:  # sqlite
            return {
                'pool_pre_ping': True,
                'pool_recycle': 300,
                # SQLite doesn't support pool_timeout and max_overflow
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': 20
                }
            }


def get_adaptive_config(environment: Optional[str] = None) -> Type[Config]:
    """
    Get adaptive configuration class for the current environment.
    
    This is the main entry point for getting configuration that adapts
    to available services.
    
    Args:
        environment: Optional environment name
        
    Returns:
        Configuration class adapted for available services
    """
    manager = AdaptiveConfigManager(environment)
    return manager.get_config_class()


def validate_current_services() -> Dict[str, bool]:
    """
    Validate all services in the current environment.
    
    Returns:
        Dictionary of service availability status
    """
    manager = AdaptiveConfigManager()
    return manager.validate_services()