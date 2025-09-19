#!/usr/bin/env python3
"""
Deployment Readiness Check for AI Secretary Project
Implements task 8.2: Тестирование деплоя

This script validates that the project is ready for deployment to Render.
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_render_requirements():
    """Check Render deployment requirements."""
    logger.info("🚀 Checking Render deployment requirements...")
    
    issues = []
    
    # Check for render.yaml
    if not os.path.exists('render.yaml'):
        issues.append("Missing render.yaml file for Render deployment")
    else:
        logger.info("✅ render.yaml exists")
        
        # Validate render.yaml content
        try:
            with open('render.yaml', 'r') as f:
                content = f.read()
                
            if 'services:' not in content:
                issues.append("render.yaml missing services section")
            if 'buildCommand:' not in content:
                issues.append("render.yaml missing buildCommand")
            if 'startCommand:' not in content:
                issues.append("render.yaml missing startCommand")
                
        except Exception as e:
            issues.append(f"Error reading render.yaml: {e}")
    
    # Check for production startup script
    startup_scripts = ['start-prod.py', 'start.py']
    startup_found = False
    
    for script in startup_scripts:
        if os.path.exists(script):
            startup_found = True
            logger.info(f"✅ Startup script found: {script}")
            break
    
    if not startup_found:
        issues.append("No startup script found (start-prod.py or start.py)")
    
    # Check requirements.txt
    if not os.path.exists('requirements.txt'):
        issues.append("Missing requirements.txt")
    else:
        logger.info("✅ requirements.txt exists")
        
        # Check for essential dependencies
        try:
            with open('requirements.txt', 'r') as f:
                requirements = f.read().lower()
                
            essential_deps = ['flask', 'sqlalchemy', 'gunicorn']
            for dep in essential_deps:
                if dep not in requirements:
                    issues.append(f"Missing essential dependency: {dep}")
                    
        except Exception as e:
            issues.append(f"Error reading requirements.txt: {e}")
    
    return len(issues) == 0, issues


def check_environment_variables():
    """Check production environment variables."""
    logger.info("⚙️ Checking environment variables for production...")
    
    issues = []
    warnings = []
    
    # Critical production variables
    critical_vars = [
        'SECRET_KEY',
        'JWT_SECRET_KEY', 
        'DATABASE_URL'
    ]
    
    # Check .env.example for documentation
    if os.path.exists('.env.example'):
        logger.info("✅ .env.example exists")
        
        try:
            with open('.env.example', 'r') as f:
                example_content = f.read()
                
            for var in critical_vars:
                if f"{var}=" not in example_content:
                    issues.append(f"Missing {var} in .env.example")
                    
        except Exception as e:
            issues.append(f"Error reading .env.example: {e}")
    else:
        issues.append("Missing .env.example file")
    
    # Check for placeholder values in .env (if exists)
    if os.path.exists('.env'):
        try:
            with open('.env', 'r') as f:
                env_content = f.read()
                
            placeholder_patterns = ['your-', 'change-me', 'example-', 'dev-secret']
            for pattern in placeholder_patterns:
                if pattern in env_content.lower():
                    warnings.append(f"Found placeholder value pattern '{pattern}' in .env")
                    
        except Exception as e:
            warnings.append(f"Error reading .env: {e}")
    
    # Check for production-specific variables
    prod_vars = [
        'FLASK_ENV=production',
        'FLASK_DEBUG=false',
        'FORCE_HTTPS=true'
    ]
    
    for var in prod_vars:
        warnings.append(f"Ensure {var} is set in production environment")
    
    return len(issues) == 0, issues, warnings


def check_database_readiness():
    """Check database readiness for production."""
    logger.info("🗄️ Checking database readiness...")
    
    issues = []
    warnings = []
    
    # Check migrations directory
    if not os.path.exists('migrations'):
        issues.append("Missing migrations directory")
    else:
        logger.info("✅ migrations directory exists")
        
        # Check for migration files
        versions_dir = Path('migrations/versions')
        if versions_dir.exists():
            migration_files = list(versions_dir.glob('*.py'))
            if len(migration_files) == 0:
                warnings.append("No migration files found - database may not be initialized")
            else:
                logger.info(f"✅ Found {len(migration_files)} migration files")
        else:
            warnings.append("Missing migrations/versions directory")
    
    # Check for database initialization script
    init_scripts = ['init_database.py', 'scripts/init-db.py', 'scripts/init-db.ps1']
    init_found = False
    
    for script in init_scripts:
        if os.path.exists(script):
            init_found = True
            logger.info(f"✅ Database init script found: {script}")
            break
    
    if not init_found:
        warnings.append("No database initialization script found")
    
    return len(issues) == 0, issues, warnings


def check_security_settings():
    """Check security settings for production."""
    logger.info("🔒 Checking security settings...")
    
    issues = []
    warnings = []
    
    # Check .gitignore for sensitive files
    if os.path.exists('.gitignore'):
        try:
            with open('.gitignore', 'r') as f:
                gitignore_content = f.read()
                
            sensitive_patterns = ['.env', '*.db', '*.key', '*.pem', 'instance/']
            for pattern in sensitive_patterns:
                if pattern not in gitignore_content:
                    issues.append(f"Missing {pattern} in .gitignore - security risk")
                    
        except Exception as e:
            issues.append(f"Error reading .gitignore: {e}")
    else:
        issues.append("Missing .gitignore file")
    
    # Check for exposed sensitive files
    sensitive_files = ['.env', '*.key', '*.pem', 'secrets.json']
    for pattern in sensitive_files:
        if '*' in pattern:
            # Use glob for patterns
            from glob import glob
            files = glob(pattern)
            if files:
                for file in files:
                    warnings.append(f"Sensitive file found: {file} - ensure it's in .gitignore")
        else:
            if os.path.exists(pattern):
                warnings.append(f"Sensitive file found: {pattern} - ensure it's in .gitignore")
    
    # Check for debug settings
    if os.path.exists('.env'):
        try:
            with open('.env', 'r') as f:
                env_content = f.read().lower()
                
            if 'flask_debug=true' in env_content or 'debug=true' in env_content:
                issues.append("Debug mode enabled in .env - security risk for production")
                
        except Exception as e:
            warnings.append(f"Error checking .env for debug settings: {e}")
    
    return len(issues) == 0, issues, warnings


def check_performance_readiness():
    """Check performance readiness for production."""
    logger.info("⚡ Checking performance readiness...")
    
    issues = []
    warnings = []
    
    # Check for WSGI server configuration
    wsgi_servers = ['gunicorn', 'uwsgi', 'waitress']
    wsgi_found = False
    
    if os.path.exists('requirements.txt'):
        try:
            with open('requirements.txt', 'r') as f:
                requirements = f.read().lower()
                
            for server in wsgi_servers:
                if server in requirements:
                    wsgi_found = True
                    logger.info(f"✅ WSGI server found: {server}")
                    break
                    
        except Exception as e:
            warnings.append(f"Error checking requirements.txt: {e}")
    
    if not wsgi_found:
        issues.append("No production WSGI server found in requirements.txt")
    
    # Check for caching configuration
    cache_indicators = ['redis', 'memcached', 'flask-caching']
    cache_found = False
    
    if os.path.exists('requirements.txt'):
        try:
            with open('requirements.txt', 'r') as f:
                requirements = f.read().lower()
                
            for cache in cache_indicators:
                if cache in requirements:
                    cache_found = True
                    logger.info(f"✅ Caching solution found: {cache}")
                    break
                    
        except Exception as e:
            pass
    
    if not cache_found:
        warnings.append("No caching solution found - may impact performance")
    
    # Check for static file handling
    static_handlers = ['whitenoise', 'nginx', 'apache']
    static_found = False
    
    if os.path.exists('requirements.txt'):
        try:
            with open('requirements.txt', 'r') as f:
                requirements = f.read().lower()
                
            for handler in static_handlers:
                if handler in requirements:
                    static_found = True
                    logger.info(f"✅ Static file handler found: {handler}")
                    break
                    
        except Exception as e:
            pass
    
    if not static_found:
        warnings.append("No static file handler found - may impact performance")
    
    return len(issues) == 0, issues, warnings


def check_monitoring_readiness():
    """Check monitoring and logging readiness."""
    logger.info("📊 Checking monitoring and logging readiness...")
    
    issues = []
    warnings = []
    
    # Check for logging configuration
    logging_files = ['logging.conf', 'logging.yaml', 'app/utils/logging_config.py']
    logging_found = False
    
    for log_file in logging_files:
        if os.path.exists(log_file):
            logging_found = True
            logger.info(f"✅ Logging configuration found: {log_file}")
            break
    
    if not logging_found:
        warnings.append("No logging configuration found")
    
    # Check for health check endpoints
    health_endpoints = ['health', 'healthz', 'status']
    health_found = False
    
    # Look for health check routes in code
    try:
        result = subprocess.run([
            'grep', '-r', '-i', 'health', 'app/', '--include=*.py'
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            health_found = True
            logger.info("✅ Health check endpoints found")
            
    except Exception:
        # Fallback: check for health files
        health_files = ['app/api/health.py', 'app/health.py', 'health.py']
        for health_file in health_files:
            if os.path.exists(health_file):
                health_found = True
                logger.info(f"✅ Health check file found: {health_file}")
                break
    
    if not health_found:
        warnings.append("No health check endpoints found")
    
    # Check for error handling
    error_handlers = ['app/errors.py', 'app/api/errors.py', 'app/utils/error_handler.py']
    error_found = False
    
    for error_file in error_handlers:
        if os.path.exists(error_file):
            error_found = True
            logger.info(f"✅ Error handler found: {error_file}")
            break
    
    if not error_found:
        warnings.append("No error handlers found")
    
    return len(issues) == 0, issues, warnings


def generate_deployment_report(results):
    """Generate deployment readiness report."""
    logger.info("📋 Generating deployment readiness report...")
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'overall_ready': True,
        'checks': {},
        'summary': {
            'total_checks': len(results),
            'passed_checks': 0,
            'failed_checks': 0,
            'total_issues': 0,
            'total_warnings': 0
        },
        'all_issues': [],
        'all_warnings': [],
        'recommendations': []
    }
    
    # Process results
    for check_name, result in results.items():
        if len(result) == 2:  # (success, issues)
            success, issues = result
            warnings = []
        else:  # (success, issues, warnings)
            success, issues, warnings = result
        
        report['checks'][check_name] = {
            'success': success,
            'issues': issues,
            'warnings': warnings
        }
        
        if success:
            report['summary']['passed_checks'] += 1
        else:
            report['summary']['failed_checks'] += 1
            report['overall_ready'] = False
        
        report['summary']['total_issues'] += len(issues)
        report['summary']['total_warnings'] += len(warnings)
        report['all_issues'].extend(issues)
        report['all_warnings'].extend(warnings)
    
    # Generate recommendations
    if report['all_issues']:
        report['recommendations'].append("Fix all critical issues before deployment")
    
    if report['all_warnings']:
        report['recommendations'].append("Review and address warnings for optimal deployment")
    
    if report['overall_ready']:
        report['recommendations'].append("Project appears ready for deployment to Render")
    else:
        report['recommendations'].append("Project is NOT ready for deployment - fix issues first")
    
    return report


def main():
    """Main deployment readiness check."""
    logger.info("🚀 Starting deployment readiness check...")
    
    results = {}
    
    # Run all checks
    results['render_requirements'] = check_render_requirements()
    results['environment_variables'] = check_environment_variables()
    results['database_readiness'] = check_database_readiness()
    results['security_settings'] = check_security_settings()
    results['performance_readiness'] = check_performance_readiness()
    results['monitoring_readiness'] = check_monitoring_readiness()
    
    # Generate report
    report = generate_deployment_report(results)
    
    # Save report
    report_file = f"deployment_readiness_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Print summary
    logger.info(f"📊 Report saved to: {report_file}")
    logger.info(f"🎯 Overall ready: {report['overall_ready']}")
    logger.info(f"📈 Passed: {report['summary']['passed_checks']}/{report['summary']['total_checks']}")
    logger.info(f"❌ Issues: {report['summary']['total_issues']}")
    logger.info(f"⚠️ Warnings: {report['summary']['total_warnings']}")
    
    if report['all_issues']:
        logger.info("❌ Critical Issues:")
        for issue in report['all_issues']:
            logger.info(f"   - {issue}")
    
    if report['all_warnings']:
        logger.info("⚠️ Warnings:")
        for warning in report['all_warnings'][:5]:  # Show first 5
            logger.info(f"   - {warning}")
        if len(report['all_warnings']) > 5:
            logger.info(f"   ... and {len(report['all_warnings']) - 5} more warnings")
    
    if report['recommendations']:
        logger.info("💡 Recommendations:")
        for rec in report['recommendations']:
            logger.info(f"   - {rec}")
    
    return report['overall_ready']


if __name__ == "__main__":
    ready = main()
    sys.exit(0 if ready else 1)