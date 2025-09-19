#!/usr/bin/env python3
"""
Example usage of the validation system.
Demonstrates how to use ConfigValidator, EnvironmentChecker, and ValidationSystem.
"""

import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def example_config_validation():
    """Example of using ConfigValidator."""
    print("🔧 Configuration Validation Example")
    print("-" * 40)
    
    from utils.config_validator import ConfigValidator
    
    # Create validator
    validator = ConfigValidator('.env')
    
    # Run validation
    report = validator.validate_all()
    
    # Display results
    print(f"Configuration valid: {report.valid}")
    print(f"Critical issues: {len(report.critical_issues)}")
    print(f"Errors: {len(report.errors)}")
    print(f"Warnings: {len(report.warnings)}")
    print(f"Services configured: {len(report.services)}")
    
    # Show first few issues
    if report.critical_issues:
        print("\nCritical Issues:")
        for issue in report.critical_issues[:3]:
            print(f"  ❌ {issue.message}")
            if issue.suggestion:
                print(f"     💡 {issue.suggestion}")
    
    if report.warnings:
        print("\nWarnings:")
        for issue in report.warnings[:3]:
            print(f"  ⚠️ {issue.message}")
    
    print()

def example_environment_validation():
    """Example of using EnvironmentChecker."""
    print("🌍 Environment Validation Example")
    print("-" * 40)
    
    from utils.environment_checker import EnvironmentChecker
    
    # Create checker
    checker = EnvironmentChecker()
    
    # Run validation
    report = checker.validate_environment()
    
    # Display results
    print(f"Environment valid: {report.valid}")
    print(f"Requirements met: {len(report.requirements_met)}")
    print(f"Requirements failed: {len(report.requirements_failed)}")
    print(f"System info collected: {len(report.system_info)} items")
    
    # Show system info
    if report.system_info:
        print("\nSystem Information:")
        for key, value in list(report.system_info.items())[:5]:
            print(f"  📊 {key}: {value}")
    
    # Show failed requirements
    if report.requirements_failed:
        print("\nFailed Requirements:")
        for req in report.requirements_failed:
            print(f"  ❌ {req}")
    
    print()

def example_comprehensive_validation():
    """Example of using ValidationSystem."""
    print("🔍 Comprehensive Validation Example")
    print("-" * 40)
    
    from utils.validation_system import ValidationSystem, ValidationLevel
    
    # Create validation system
    validator = ValidationSystem()
    
    # Get quick status
    status = validator.get_quick_status()
    
    print("Quick Status:")
    print(f"  📁 Config file exists: {status['config_file_exists']}")
    print(f"  🗄️ Database configured: {status['database_configured']}")
    print(f"  🐍 Python version: {status['python_version']}")
    print(f"  🌍 Flask environment: {status['flask_env']}")
    print(f"  🔧 Debug mode: {status['debug_mode']}")
    print(f"  🔌 Services configured: {status['services_count']}")
    
    if status['configured_services']:
        print(f"  📋 Services: {', '.join(status['configured_services'])}")
    
    print()

def example_with_flask_app():
    """Example with Flask app integration."""
    print("🌐 Flask App Integration Example")
    print("-" * 40)
    
    try:
        import flask
        from utils.validation_system import ValidationSystem, ValidationLevel
        
        # Create Flask app
        app = flask.Flask(__name__)
        
        # Load environment variables
        app.config.update({
            'SECRET_KEY': os.getenv('SECRET_KEY', 'dev-key'),
            'DATABASE_URL': os.getenv('DATABASE_URL', 'sqlite:///test.db'),
            'FLASK_ENV': os.getenv('FLASK_ENV', 'development')
        })
        
        # Create validation system
        validator = ValidationSystem(app)
        
        # Run basic validation
        report = validator.validate_system(level=ValidationLevel.BASIC)
        
        print(f"System valid: {report.valid}")
        print(f"Total checks: {report.total_checks}")
        print(f"Passed checks: {report.passed_checks}")
        print(f"Failed checks: {report.failed_checks}")
        print(f"Warnings: {report.warnings}")
        
        # Show summary
        summary = report.get_summary()
        print(f"\nSummary: {summary}")
        
    except ImportError:
        print("Flask not available - skipping Flask integration example")
    
    print()

def main():
    """Run all examples."""
    print("🧪 Validation System Usage Examples")
    print("=" * 50)
    
    # Run examples
    example_config_validation()
    example_environment_validation()
    example_comprehensive_validation()
    example_with_flask_app()
    
    print("=" * 50)
    print("✅ All examples completed!")
    print("\nTo use in your application:")
    print("1. Import the validators you need")
    print("2. Create instances with appropriate parameters")
    print("3. Call validation methods")
    print("4. Process the reports and take action")

if __name__ == "__main__":
    main()