"""
Environment Checker for AI Secretary application.
Validates system requirements, port availability, file permissions, Python versions, and dependencies.
Addresses Requirements 6.2 and 6.5 for comprehensive environment validation.
"""

import os
import sys
import socket
import subprocess
import platform
import importlib.util
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .config_validator import ValidationSeverity, ServiceStatus, ValidationIssue, ServiceHealth

logger = logging.getLogger(__name__)


class SystemRequirement(Enum):
    """System requirement types."""
    PYTHON_VERSION = "python_version"
    DISK_SPACE = "disk_space"
    MEMORY = "memory"
    NETWORK = "network"
    PERMISSIONS = "permissions"
    DEPENDENCIES = "dependencies"


@dataclass
class EnvironmentReport:
    """Environment validation report."""
    valid: bool = True
    system_info: Dict[str, Any] = field(default_factory=dict)
    requirements_met: List[str] = field(default_factory=list)
    requirements_failed: List[str] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    errors: List[ValidationIssue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_issue(self, message: str, severity: ValidationSeverity, category: str, 
                  suggestion: Optional[str] = None):
        """Add an environment issue."""
        issue = ValidationIssue(
            message=message,
            severity=severity,
            category=category,
            suggestion=suggestion
        )
        
        if severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
            self.errors.append(issue)
            self.valid = False
        else:
            self.warnings.append(issue)
        
        if suggestion:
            self.recommendations.append(suggestion)
    
    def add_requirement_result(self, requirement: str, passed: bool):
        """Add requirement validation result."""
        if passed:
            self.requirements_met.append(requirement)
        else:
            self.requirements_failed.append(requirement)
            self.valid = False


class EnvironmentChecker:
    """
    Environment validation system for system requirements, ports, permissions, and dependencies.
    """
    
    def __init__(self):
        self.report = EnvironmentReport()
        
        # Minimum system requirements
        self.min_python_version = (3, 8, 0)
        self.min_disk_space_mb = 500  # 500 MB
        self.min_memory_mb = 512  # 512 MB
        
        # Required Python packages
        self.required_packages = {
            'flask': 'Web framework',
            'sqlalchemy': 'Database ORM',
            'flask_sqlalchemy': 'Flask SQLAlchemy integration',
            'flask_migrate': 'Database migrations',
            'flask_jwt_extended': 'JWT authentication',
            'flask_babel': 'Internationalization',
            'redis': 'Redis client (optional)',
            'celery': 'Task queue (optional)',
            'psycopg2': 'PostgreSQL driver (optional)',
            'requests': 'HTTP client',
            'python-dotenv': 'Environment variables'
        }
        
        # Optional packages with fallbacks
        self.optional_packages = {
            'redis': 'Simple cache fallback available',
            'celery': 'Background tasks will be disabled',
            'psycopg2': 'SQLite fallback available',
            'openai': 'AI features will be disabled'
        }
    
    def validate_environment(self) -> EnvironmentReport:
        """
        Run comprehensive environment validation.
        
        Returns:
            EnvironmentReport with complete environment assessment
        """
        logger.info("Starting comprehensive environment validation")
        
        # Reset report
        self.report = EnvironmentReport()
        
        try:
            # Collect system information
            self._collect_system_info()
            
            # Validate system requirements
            self._validate_python_version()
            self._validate_system_resources()
            self._validate_network_capabilities()
            self._validate_file_permissions()
            self._validate_python_dependencies()
            
            # Generate recommendations
            self._generate_recommendations()
            
            logger.info(f"Environment validation completed: {len(self.report.requirements_met)} requirements met, "
                       f"{len(self.report.requirements_failed)} failed")
            
        except Exception as e:
            self.report.add_issue(
                f"Environment validation failed with exception: {str(e)}",
                ValidationSeverity.CRITICAL,
                "system",
                "Check system accessibility and permissions"
            )
            logger.error(f"Environment validation failed: {e}", exc_info=True)
        
        return self.report
    
    def _collect_system_info(self) -> None:
        """Collect basic system information."""
        try:
            self.report.system_info.update({
                'platform': platform.platform(),
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'python_version': platform.python_version(),
                'python_executable': sys.executable,
                'working_directory': os.getcwd(),
                'user': os.getenv('USER', os.getenv('USERNAME', 'unknown')),
                'home_directory': os.path.expanduser('~')
            })
            
            # Get additional system info if available
            try:
                import psutil
                self.report.system_info.update({
                    'cpu_count': psutil.cpu_count(),
                    'memory_total': psutil.virtual_memory().total,
                    'memory_available': psutil.virtual_memory().available,
                    'disk_usage': psutil.disk_usage('.').free
                })
            except ImportError:
                # psutil not available, use basic methods
                pass
                
        except Exception as e:
            self.report.add_issue(
                f"Failed to collect system information: {e}",
                ValidationSeverity.WARNING,
                "system",
                "System information collection failed but not critical"
            )
    
    def _validate_python_version(self) -> None:
        """Validate Python version meets minimum requirements."""
        current_version = sys.version_info[:3]
        
        if current_version >= self.min_python_version:
            self.report.add_requirement_result("Python version", True)
            self.report.add_issue(
                f"Python version {'.'.join(map(str, current_version))} meets requirements",
                ValidationSeverity.INFO,
                "python"
            )
        else:
            self.report.add_requirement_result("Python version", False)
            self.report.add_issue(
                f"Python version {'.'.join(map(str, current_version))} is below minimum "
                f"{'.'.join(map(str, self.min_python_version))}",
                ValidationSeverity.CRITICAL,
                "python",
                f"Upgrade Python to version {'.'.join(map(str, self.min_python_version))} or higher"
            )
    
    def _validate_system_resources(self) -> None:
        """Validate system resources (disk space, memory)."""
        # Check disk space
        try:
            disk_usage = self._get_disk_usage()
            if disk_usage['free_mb'] >= self.min_disk_space_mb:
                self.report.add_requirement_result("Disk space", True)
                self.report.add_issue(
                    f"Sufficient disk space: {disk_usage['free_mb']:.0f} MB available",
                    ValidationSeverity.INFO,
                    "resources"
                )
            else:
                self.report.add_requirement_result("Disk space", False)
                self.report.add_issue(
                    f"Insufficient disk space: {disk_usage['free_mb']:.0f} MB available, "
                    f"{self.min_disk_space_mb} MB required",
                    ValidationSeverity.ERROR,
                    "resources",
                    f"Free up at least {self.min_disk_space_mb - disk_usage['free_mb']:.0f} MB disk space"
                )
        except Exception as e:
            self.report.add_issue(
                f"Failed to check disk space: {e}",
                ValidationSeverity.WARNING,
                "resources",
                "Manual disk space verification recommended"
            )
        
        # Check memory
        try:
            memory_info = self._get_memory_info()
            if memory_info['available_mb'] >= self.min_memory_mb:
                self.report.add_requirement_result("Memory", True)
                self.report.add_issue(
                    f"Sufficient memory: {memory_info['available_mb']:.0f} MB available",
                    ValidationSeverity.INFO,
                    "resources"
                )
            else:
                self.report.add_requirement_result("Memory", False)
                self.report.add_issue(
                    f"Low memory: {memory_info['available_mb']:.0f} MB available, "
                    f"{self.min_memory_mb} MB recommended",
                    ValidationSeverity.WARNING,
                    "resources",
                    "Close other applications or add more RAM"
                )
        except Exception as e:
            self.report.add_issue(
                f"Failed to check memory: {e}",
                ValidationSeverity.WARNING,
                "resources",
                "Manual memory verification recommended"
            )
    
    def _validate_network_capabilities(self) -> None:
        """Validate network connectivity and port availability."""
        # Test basic network connectivity
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            self.report.add_requirement_result("Network connectivity", True)
            self.report.add_issue(
                "Network connectivity available",
                ValidationSeverity.INFO,
                "network"
            )
        except Exception:
            self.report.add_requirement_result("Network connectivity", False)
            self.report.add_issue(
                "Network connectivity test failed",
                ValidationSeverity.WARNING,
                "network",
                "Check internet connection for external service access"
            )
        
        # Check common port availability
        common_ports = [5000, 8000, 3000, 5432, 6379]  # Flask, Redis, PostgreSQL
        available_ports = []
        
        for port in common_ports:
            if self._is_port_available(port):
                available_ports.append(port)
        
        if available_ports:
            self.report.add_issue(
                f"Available ports: {', '.join(map(str, available_ports))}",
                ValidationSeverity.INFO,
                "network"
            )
        else:
            self.report.add_issue(
                "No common development ports available",
                ValidationSeverity.WARNING,
                "network",
                "Check for port conflicts with other applications"
            )
    
    def _validate_file_permissions(self) -> None:
        """Validate file system permissions."""
        # Check write permissions in current directory
        try:
            test_file = Path('.') / '.env_test_write'
            test_file.write_text('test')
            test_file.unlink()
            
            self.report.add_requirement_result("Write permissions", True)
            self.report.add_issue(
                "Write permissions available in current directory",
                ValidationSeverity.INFO,
                "permissions"
            )
        except Exception as e:
            self.report.add_requirement_result("Write permissions", False)
            self.report.add_issue(
                f"No write permissions in current directory: {e}",
                ValidationSeverity.ERROR,
                "permissions",
                "Ensure write permissions for application directory"
            )
        
        # Check critical directories
        critical_dirs = ['logs', 'uploads', 'instance']
        for dir_name in critical_dirs:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                try:
                    dir_path.mkdir(exist_ok=True)
                    self.report.add_issue(
                        f"Created directory: {dir_name}",
                        ValidationSeverity.INFO,
                        "permissions"
                    )
                except Exception as e:
                    self.report.add_issue(
                        f"Cannot create directory '{dir_name}': {e}",
                        ValidationSeverity.WARNING,
                        "permissions",
                        f"Manually create {dir_name} directory with write permissions"
                    )
    
    def _validate_python_dependencies(self) -> None:
        """Validate Python package dependencies."""
        missing_required = []
        missing_optional = []
        installed_packages = {}
        
        # Check required packages
        for package, description in self.required_packages.items():
            try:
                spec = importlib.util.find_spec(package)
                if spec is None:
                    if package in self.optional_packages:
                        missing_optional.append(package)
                    else:
                        missing_required.append(package)
                else:
                    # Try to get version
                    try:
                        module = importlib.import_module(package)
                        version = getattr(module, '__version__', 'unknown')
                        installed_packages[package] = version
                    except Exception:
                        installed_packages[package] = 'installed'
            except Exception:
                if package in self.optional_packages:
                    missing_optional.append(package)
                else:
                    missing_required.append(package)
        
        # Report results
        if missing_required:
            self.report.add_requirement_result("Required packages", False)
            self.report.add_issue(
                f"Missing required packages: {', '.join(missing_required)}",
                ValidationSeverity.CRITICAL,
                "dependencies",
                f"Install missing packages: pip install {' '.join(missing_required)}"
            )
        else:
            self.report.add_requirement_result("Required packages", True)
            self.report.add_issue(
                f"All required packages installed: {len(installed_packages)} packages",
                ValidationSeverity.INFO,
                "dependencies"
            )
        
        if missing_optional:
            self.report.add_issue(
                f"Missing optional packages: {', '.join(missing_optional)}",
                ValidationSeverity.INFO,
                "dependencies",
                f"Optional packages provide additional features: pip install {' '.join(missing_optional)}"
            )
        
        # Store package information
        self.report.system_info['installed_packages'] = installed_packages
        self.report.system_info['missing_required'] = missing_required
        self.report.system_info['missing_optional'] = missing_optional
    
    def _generate_recommendations(self) -> None:
        """Generate environment-specific recommendations."""
        # Python version recommendations
        if sys.version_info < (3, 9):
            self.report.recommendations.append(
                "Consider upgrading to Python 3.9+ for better performance and features"
            )
        
        # System-specific recommendations
        system = platform.system().lower()
        if system == 'windows':
            self.report.recommendations.append(
                "On Windows, consider using Windows Subsystem for Linux (WSL) for better compatibility"
            )
        elif system == 'darwin':  # macOS
            self.report.recommendations.append(
                "On macOS, ensure Xcode Command Line Tools are installed for package compilation"
            )
        
        # Resource recommendations
        try:
            memory_info = self._get_memory_info()
            if memory_info['available_mb'] < 1024:  # Less than 1GB
                self.report.recommendations.append(
                    "Consider increasing available memory for better performance"
                )
        except Exception:
            pass
    
    def _get_disk_usage(self) -> Dict[str, float]:
        """Get disk usage information."""
        try:
            import psutil
            usage = psutil.disk_usage('.')
            return {
                'total_mb': usage.total / (1024 * 1024),
                'used_mb': usage.used / (1024 * 1024),
                'free_mb': usage.free / (1024 * 1024)
            }
        except ImportError:
            # Fallback method
            import shutil
            total, used, free = shutil.disk_usage('.')
            return {
                'total_mb': total / (1024 * 1024),
                'used_mb': used / (1024 * 1024),
                'free_mb': free / (1024 * 1024)
            }
    
    def _get_memory_info(self) -> Dict[str, float]:
        """Get memory information."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return {
                'total_mb': memory.total / (1024 * 1024),
                'available_mb': memory.available / (1024 * 1024),
                'used_mb': memory.used / (1024 * 1024),
                'percent': memory.percent
            }
        except ImportError:
            # Basic fallback - not very accurate
            return {
                'total_mb': 1024,  # Assume 1GB minimum
                'available_mb': 512,  # Assume 512MB available
                'used_mb': 512,
                'percent': 50.0
            }
    
    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                return result != 0  # Port is available if connection fails
        except Exception:
            return False
    
    def check_port_availability(self, ports: List[int]) -> Dict[int, bool]:
        """
        Check availability of specific ports.
        
        Args:
            ports: List of ports to check
            
        Returns:
            Dictionary mapping port numbers to availability status
        """
        return {port: self._is_port_available(port) for port in ports}
    
    def validate_file_permissions(self, paths: List[str]) -> Dict[str, Dict[str, bool]]:
        """
        Validate file permissions for specific paths.
        
        Args:
            paths: List of file/directory paths to check
            
        Returns:
            Dictionary with permission status for each path
        """
        results = {}
        
        for path_str in paths:
            path = Path(path_str)
            results[path_str] = {
                'exists': path.exists(),
                'readable': False,
                'writable': False,
                'executable': False
            }
            
            if path.exists():
                try:
                    results[path_str]['readable'] = os.access(path, os.R_OK)
                    results[path_str]['writable'] = os.access(path, os.W_OK)
                    results[path_str]['executable'] = os.access(path, os.X_OK)
                except Exception:
                    pass
        
        return results
    
    def get_system_summary(self) -> Dict[str, Any]:
        """
        Get a summary of system information.
        
        Returns:
            Dictionary with system summary
        """
        return {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'working_directory': os.getcwd(),
            'environment_valid': self.report.valid,
            'requirements_met': len(self.report.requirements_met),
            'requirements_failed': len(self.report.requirements_failed),
            'last_check': datetime.now().isoformat()
        }


def validate_environment() -> EnvironmentReport:
    """Convenience function to validate environment."""
    checker = EnvironmentChecker()
    return checker.validate_environment()


if __name__ == "__main__":
    # CLI usage
    import json
    
    result = validate_environment()
    
    print(json.dumps({
        'valid': result.valid,
        'system_info': result.system_info,
        'requirements_met': result.requirements_met,
        'requirements_failed': result.requirements_failed,
        'warnings': len(result.warnings),
        'errors': len(result.errors),
        'recommendations': result.recommendations
    }, indent=2))
    
    if not result.valid:
        sys.exit(1)