"""
Service dependency checker for AI Secretary application.
Addresses Requirements 5.3 and 4.1 for service dependency checking.
"""

import os
import sys
import time
import socket
import logging
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ServiceChecker:
    """Checks service dependencies and health status."""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.results: Dict[str, Dict[str, Any]] = {}
        
    def check_all_services(self, env_vars: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """Check all service dependencies."""
        logger.info("Starting comprehensive service dependency check")
        
        self.results.clear()
        
        # Core system checks
        self.results['system'] = self._check_system_requirements()
        self.results['python'] = self._check_python_environment()
        self.results['packages'] = self._check_python_packages()
        
        # Database services
        self.results['database'] = self._check_database_service(env_vars)
        
        # Cache services
        self.results['redis'] = self._check_redis_service(env_vars)
        self.results['cache'] = self._check_cache_service(env_vars)
        
        # External services
        self.results['external_apis'] = self._check_external_apis(env_vars)
        
        # Application services
        self.results['flask'] = self._check_flask_application()
        
        return self.results
    
    def _check_system_requirements(self) -> Dict[str, Any]:
        """Check basic system requirements."""
        try:
            import platform
            
            system_info = {
                'platform': platform.system(),
                'platform_version': platform.version(),
                'architecture': platform.architecture()[0],
                'python_version': platform.python_version(),
                'hostname': socket.gethostname()
            }
            
            # Check available disk space
            try:
                import shutil
                total, used, free = shutil.disk_usage('.')
                system_info['disk_space'] = {
                    'total_gb': round(total / (1024**3), 2),
                    'free_gb': round(free / (1024**3), 2),
                    'used_gb': round(used / (1024**3), 2)
                }
                
                if free < 1024**3:  # Less than 1GB free
                    return {
                        'status': 'warning',
                        'info': system_info,
                        'warning': 'Low disk space (less than 1GB free)'
                    }
            except Exception:
                pass
            
            return {
                'status': 'healthy',
                'info': system_info
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': f"System check failed: {e}"
            }
    
    def _check_python_environment(self) -> Dict[str, Any]:
        """Check Python environment and virtual environment."""
        try:
            python_info = {
                'version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                'executable': sys.executable,
                'prefix': sys.prefix,
                'path': sys.path[:3]  # First 3 paths for brevity
            }
            
            # Check if in virtual environment
            in_venv = (
                hasattr(sys, 'real_prefix') or
                (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
            )
            
            python_info['virtual_env'] = in_venv
            
            if not in_venv:
                return {
                    'status': 'warning',
                    'info': python_info,
                    'warning': 'Not running in virtual environment - recommended for development'
                }
            
            # Check Python version
            if sys.version_info < (3, 8):
                return {
                    'status': 'unhealthy',
                    'info': python_info,
                    'error': 'Python 3.8+ required'
                }
            
            return {
                'status': 'healthy',
                'info': python_info
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': f"Python environment check failed: {e}"
            }
    
    def _check_python_packages(self) -> Dict[str, Any]:
        """Check required Python packages and their versions."""
        required_packages = {
            'flask': '2.0.0',
            'sqlalchemy': '1.4.0',
            'flask_sqlalchemy': '2.5.0',
            'flask_migrate': '3.0.0',
            'flask_jwt_extended': '4.0.0',
            'flask_babel': '2.0.0',
            'redis': '4.0.0',
            'celery': '5.0.0',
            'requests': '2.25.0',
            'python-dotenv': '0.19.0'
        }
        
        installed_packages = {}
        missing_packages = []
        outdated_packages = []
        
        for package, min_version in required_packages.items():
            try:
                import importlib.util
                import importlib.metadata
                
                spec = importlib.util.find_spec(package)
                if spec is None:
                    missing_packages.append(package)
                    continue
                
                try:
                    version = importlib.metadata.version(package)
                    installed_packages[package] = version
                    
                    # Simple version comparison (not perfect but good enough)
                    if self._compare_versions(version, min_version) < 0:
                        outdated_packages.append({
                            'package': package,
                            'installed': version,
                            'required': min_version
                        })
                        
                except importlib.metadata.PackageNotFoundError:
                    installed_packages[package] = 'unknown'
                    
            except Exception as e:
                logger.warning(f"Error checking package {package}: {e}")
                missing_packages.append(package)
        
        if missing_packages:
            return {
                'status': 'unhealthy',
                'installed': installed_packages,
                'missing': missing_packages,
                'outdated': outdated_packages,
                'error': f"Missing critical packages: {', '.join(missing_packages)}"
            }
        
        if outdated_packages:
            return {
                'status': 'warning',
                'installed': installed_packages,
                'missing': missing_packages,
                'outdated': outdated_packages,
                'warning': f"Outdated packages detected: {len(outdated_packages)} packages"
            }
        
        return {
            'status': 'healthy',
            'installed': installed_packages,
            'missing': missing_packages,
            'outdated': outdated_packages
        }
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """Simple version comparison. Returns -1, 0, or 1."""
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # Pad shorter version with zeros
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            for v1, v2 in zip(v1_parts, v2_parts):
                if v1 < v2:
                    return -1
                elif v1 > v2:
                    return 1
            
            return 0
        except Exception:
            return 0  # Assume equal if comparison fails
    
    def _check_database_service(self, env_vars: Dict[str, str]) -> Dict[str, Any]:
        """Check database service connectivity and health."""
        database_url = env_vars.get('DATABASE_URL', '').strip()
        
        if not database_url:
            return {
                'status': 'not_configured',
                'error': 'DATABASE_URL not configured'
            }
        
        try:
            parsed = urlparse(database_url)
            
            if parsed.scheme == 'sqlite':
                return self._check_sqlite_database(database_url)
            elif parsed.scheme in ['postgresql', 'postgres']:
                return self._check_postgresql_database(database_url)
            else:
                return {
                    'status': 'unknown',
                    'type': parsed.scheme,
                    'note': 'Database type not specifically supported for health checks'
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': f"Database service check failed: {e}"
            }
    
    def _check_sqlite_database(self, database_url: str) -> Dict[str, Any]:
        """Check SQLite database."""
        try:
            import sqlite3
            
            db_path = database_url.replace('sqlite:///', '')
            
            if db_path == ':memory:':
                return {
                    'status': 'healthy',
                    'type': 'SQLite',
                    'location': 'in-memory',
                    'note': 'In-memory database - data will not persist'
                }
            
            # Check if database file exists and is accessible
            if not os.path.exists(db_path):
                # Try to create the database directory
                db_dir = os.path.dirname(db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                
                return {
                    'status': 'healthy',
                    'type': 'SQLite',
                    'location': db_path,
                    'note': 'Database file will be created on first use'
                }
            
            # Test database connection and get info
            with sqlite3.connect(db_path, timeout=self.timeout) as conn:
                cursor = conn.cursor()
                
                # Test basic query
                cursor.execute('SELECT 1')
                cursor.fetchone()
                
                # Get database info
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                file_size = os.path.getsize(db_path)
                
                return {
                    'status': 'healthy',
                    'type': 'SQLite',
                    'location': db_path,
                    'size_bytes': file_size,
                    'size_mb': round(file_size / (1024 * 1024), 2),
                    'tables_count': len(tables),
                    'tables': tables[:10]  # First 10 tables
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'type': 'SQLite',
                'error': str(e)
            }
    
    def _check_postgresql_database(self, database_url: str) -> Dict[str, Any]:
        """Check PostgreSQL database."""
        try:
            # Try different PostgreSQL drivers
            connection_info = None
            driver_used = None
            
            # Try psycopg2 first
            try:
                import psycopg2
                import psycopg2.extras
                
                conn = psycopg2.connect(database_url, connect_timeout=self.timeout)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # Test connection
                    cur.execute('SELECT version()')
                    version_info = cur.fetchone()
                    
                    # Get database info
                    cur.execute('SELECT current_database(), current_user, inet_server_addr(), inet_server_port()')
                    db_info = cur.fetchone()
                    
                    # Get table count
                    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
                    table_count = cur.fetchone()[0]
                    
                    connection_info = {
                        'version': version_info[0] if version_info else 'unknown',
                        'database': db_info[0] if db_info else 'unknown',
                        'user': db_info[1] if db_info else 'unknown',
                        'host': db_info[2] if db_info else 'unknown',
                        'port': db_info[3] if db_info else 'unknown',
                        'tables_count': table_count
                    }
                    driver_used = 'psycopg2'
                
                conn.close()
                
            except ImportError:
                # Try SQLAlchemy as fallback
                try:
                    from sqlalchemy import create_engine, text
                    
                    engine = create_engine(database_url, connect_args={'connect_timeout': self.timeout})
                    with engine.connect() as conn:
                        # Test connection
                        result = conn.execute(text('SELECT version()'))
                        version_info = result.fetchone()
                        
                        result = conn.execute(text('SELECT current_database(), current_user'))
                        db_info = result.fetchone()
                        
                        connection_info = {
                            'version': version_info[0] if version_info else 'unknown',
                            'database': db_info[0] if db_info else 'unknown',
                            'user': db_info[1] if db_info else 'unknown'
                        }
                        driver_used = 'SQLAlchemy'
                        
                except ImportError:
                    return {
                        'status': 'degraded',
                        'type': 'PostgreSQL',
                        'error': 'No PostgreSQL driver available (psycopg2 or SQLAlchemy)',
                        'note': 'Database connectivity will be tested during application startup'
                    }
            
            if connection_info:
                return {
                    'status': 'healthy',
                    'type': 'PostgreSQL',
                    'driver': driver_used,
                    'connection_info': connection_info
                }
            else:
                return {
                    'status': 'unhealthy',
                    'type': 'PostgreSQL',
                    'error': 'Failed to establish connection'
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'type': 'PostgreSQL',
                'error': str(e)
            }
    
    def _check_redis_service(self, env_vars: Dict[str, str]) -> Dict[str, Any]:
        """Check Redis service connectivity and health."""
        redis_url = env_vars.get('REDIS_URL', '').strip()
        
        if not redis_url:
            return {
                'status': 'not_configured',
                'note': 'Redis not configured - using fallback cache'
            }
        
        try:
            import redis
            
            # Parse Redis URL
            parsed = urlparse(redis_url)
            
            # Create Redis client
            r = redis.from_url(
                redis_url,
                socket_connect_timeout=self.timeout,
                socket_timeout=self.timeout,
                retry_on_timeout=True
            )
            
            # Test connection
            start_time = time.time()
            r.ping()
            ping_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Get Redis info
            info = r.info()
            
            # Test basic operations
            test_key = f"health_check_{int(time.time())}"
            r.set(test_key, "test_value", ex=60)  # Expire in 60 seconds
            test_value = r.get(test_key)
            r.delete(test_key)
            
            if test_value != b"test_value":
                raise Exception("Redis read/write test failed")
            
            return {
                'status': 'healthy',
                'host': parsed.hostname,
                'port': parsed.port,
                'ping_ms': round(ping_time, 2),
                'version': info.get('redis_version', 'unknown'),
                'mode': info.get('redis_mode', 'standalone'),
                'memory_used': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'uptime_seconds': info.get('uptime_in_seconds', 0)
            }
            
        except ImportError:
            return {
                'status': 'degraded',
                'error': 'Redis package not installed',
                'fallback': 'simple cache'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'fallback': 'simple cache'
            }
    
    def _check_cache_service(self, env_vars: Dict[str, str]) -> Dict[str, Any]:
        """Check cache service configuration."""
        cache_type = env_vars.get('CACHE_TYPE', 'simple').lower()
        redis_url = env_vars.get('REDIS_URL', '').strip()
        
        if cache_type == 'redis':
            if not redis_url:
                return {
                    'status': 'misconfigured',
                    'type': 'redis',
                    'error': 'CACHE_TYPE is redis but REDIS_URL not configured',
                    'fallback': 'Will use simple cache'
                }
            
            # Redis status already checked in _check_redis_service
            redis_status = self.results.get('redis', {}).get('status', 'unknown')
            
            if redis_status == 'healthy':
                return {
                    'status': 'healthy',
                    'type': 'redis',
                    'note': 'Using Redis cache'
                }
            else:
                return {
                    'status': 'degraded',
                    'type': 'redis',
                    'error': 'Redis not available',
                    'fallback': 'Will use simple cache'
                }
        
        elif cache_type == 'simple':
            return {
                'status': 'healthy',
                'type': 'simple',
                'note': 'Using simple in-memory cache'
            }
        
        else:
            return {
                'status': 'unknown',
                'type': cache_type,
                'note': f'Unknown cache type: {cache_type}'
            }
    
    def _check_external_apis(self, env_vars: Dict[str, str]) -> Dict[str, Any]:
        """Check external API services."""
        apis = {}
        
        # OpenAI API
        openai_key = env_vars.get('OPENAI_API_KEY', '').strip()
        if openai_key and not openai_key.startswith('your-'):
            apis['openai'] = self._test_openai_api(openai_key)
        else:
            apis['openai'] = {
                'status': 'not_configured',
                'note': 'OpenAI API key not configured'
            }
        
        # Google APIs (OAuth)
        google_client_id = env_vars.get('GOOGLE_CLIENT_ID', '').strip()
        if google_client_id and not google_client_id.startswith('your-'):
            apis['google_oauth'] = {
                'status': 'configured',
                'note': 'Google OAuth configured (cannot test without user interaction)'
            }
        else:
            apis['google_oauth'] = {
                'status': 'not_configured',
                'note': 'Google OAuth not configured'
            }
        
        # Stripe API
        stripe_key = env_vars.get('STRIPE_SECRET_KEY', '').strip()
        if stripe_key and stripe_key.startswith(('sk_test_', 'sk_live_')):
            apis['stripe'] = {
                'status': 'configured',
                'mode': 'test' if stripe_key.startswith('sk_test_') else 'live',
                'note': 'Stripe API configured (not tested to avoid charges)'
            }
        else:
            apis['stripe'] = {
                'status': 'not_configured',
                'note': 'Stripe API not configured'
            }
        
        # Overall status
        configured_count = sum(1 for api in apis.values() if api['status'] in ['healthy', 'configured'])
        total_count = len(apis)
        
        return {
            'status': 'healthy' if configured_count > 0 else 'warning',
            'configured': configured_count,
            'total': total_count,
            'apis': apis
        }
    
    def _test_openai_api(self, api_key: str) -> Dict[str, Any]:
        """Test OpenAI API connectivity."""
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # Test with a simple models list request
            response = requests.get(
                'https://api.openai.com/v1/models',
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                models_data = response.json()
                model_count = len(models_data.get('data', []))
                
                return {
                    'status': 'healthy',
                    'models_available': model_count,
                    'note': 'OpenAI API accessible'
                }
            elif response.status_code == 401:
                return {
                    'status': 'unhealthy',
                    'error': 'Invalid API key'
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': f'API returned status {response.status_code}'
                }
                
        except requests.exceptions.Timeout:
            return {
                'status': 'unhealthy',
                'error': 'API request timeout'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_flask_application(self) -> Dict[str, Any]:
        """Check Flask application readiness."""
        try:
            # Check if Flask is importable
            import flask
            
            # Check if run.py exists
            if not os.path.exists('run.py'):
                return {
                    'status': 'unhealthy',
                    'error': 'run.py not found - Flask application entry point missing'
                }
            
            # Check if app directory exists
            if not os.path.exists('app'):
                return {
                    'status': 'unhealthy',
                    'error': 'app directory not found'
                }
            
            # Check for critical app files
            critical_files = [
                'app/__init__.py',
                'app/models',
                'app/api',
                'config.py'
            ]
            
            missing_files = []
            for file_path in critical_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)
            
            if missing_files:
                return {
                    'status': 'unhealthy',
                    'error': f'Missing critical files: {", ".join(missing_files)}'
                }
            
            return {
                'status': 'healthy',
                'flask_version': flask.__version__,
                'note': 'Flask application structure looks good'
            }
            
        except ImportError:
            return {
                'status': 'unhealthy',
                'error': 'Flask not installed'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def get_overall_health(self) -> Tuple[str, Dict[str, Any]]:
        """Get overall system health status."""
        if not self.results:
            return 'unknown', {'error': 'No health checks performed'}
        
        healthy_count = 0
        warning_count = 0
        unhealthy_count = 0
        total_count = 0
        
        critical_services = ['python', 'packages', 'database', 'flask']
        critical_failures = []
        
        for service_name, service_result in self.results.items():
            total_count += 1
            status = service_result.get('status', 'unknown')
            
            if status == 'healthy':
                healthy_count += 1
            elif status in ['warning', 'degraded', 'misconfigured']:
                warning_count += 1
            elif status in ['unhealthy', 'not_configured']:
                if service_name in critical_services:
                    critical_failures.append(service_name)
                unhealthy_count += 1
        
        health_percentage = (healthy_count / total_count * 100) if total_count > 0 else 0
        
        if critical_failures:
            overall_status = 'critical'
        elif health_percentage >= 80:
            overall_status = 'healthy'
        elif health_percentage >= 60:
            overall_status = 'degraded'
        else:
            overall_status = 'unhealthy'
        
        summary = {
            'overall_status': overall_status,
            'health_percentage': round(health_percentage, 1),
            'services': {
                'total': total_count,
                'healthy': healthy_count,
                'warning': warning_count,
                'unhealthy': unhealthy_count
            },
            'critical_failures': critical_failures,
            'timestamp': datetime.now().isoformat()
        }
        
        return overall_status, summary


def check_service_dependencies(env_vars: Dict[str, str], timeout: int = 10) -> Dict[str, Any]:
    """Convenience function to check all service dependencies."""
    checker = ServiceChecker(timeout)
    results = checker.check_all_services(env_vars)
    overall_status, summary = checker.get_overall_health()
    
    return {
        'summary': summary,
        'services': results
    }


if __name__ == "__main__":
    # CLI usage
    import json
    from app.utils.config_validator import ConfigValidator
    
    # Load environment variables
    config_file = sys.argv[1] if len(sys.argv) > 1 else ".env"
    validator = ConfigValidator(config_file)
    env_vars = validator._load_env_file()
    
    # Check services
    result = check_service_dependencies(env_vars)
    
    print(json.dumps(result, indent=2))
    
    if result['summary']['overall_status'] in ['critical', 'unhealthy']:
        sys.exit(1)