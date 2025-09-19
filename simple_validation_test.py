#!/usr/bin/env python3
"""
Simple validation test for AI Secretary Project
Tests basic functionality without complex imports
"""

import os
import sys
import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_environment_setup():
    """Test basic environment setup."""
    logger.info("🔧 Testing environment setup...")
    
    issues = []
    
    # Check .env file exists
    if not os.path.exists('.env'):
        issues.append("Missing .env file")
    else:
        logger.info("✅ .env file exists")
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        issues.append(f"Python version {python_version.major}.{python_version.minor} is too old (need 3.8+)")
    else:
        logger.info(f"✅ Python version {python_version.major}.{python_version.minor} is compatible")
    
    # Check requirements.txt
    if not os.path.exists('requirements.txt'):
        issues.append("Missing requirements.txt file")
    else:
        logger.info("✅ requirements.txt exists")
    
    # Check app directory
    if not os.path.exists('app'):
        issues.append("Missing app directory")
    else:
        logger.info("✅ app directory exists")
    
    # Check main app file
    if not os.path.exists('app/fast_app.py'):
        issues.append("Missing app/fast_app.py")
    else:
        logger.info("✅ app/fast_app.py exists")
    
    return len(issues) == 0, issues


def test_config_file():
    """Test configuration file."""
    logger.info("📋 Testing configuration file...")
    
    if not os.path.exists('.env'):
        return False, ["Missing .env file"]
    
    issues = []
    critical_vars = ['SECRET_KEY', 'JWT_SECRET_KEY', 'DATABASE_URL', 'FLASK_APP']
    
    try:
        with open('.env', 'r') as f:
            content = f.read()
            
        for var in critical_vars:
            if f"{var}=" not in content:
                issues.append(f"Missing {var} in .env")
            elif f"{var}=your-" in content or f"{var}=change-me" in content:
                issues.append(f"{var} has placeholder value")
        
        if len(issues) == 0:
            logger.info("✅ Configuration file looks good")
        else:
            logger.warning(f"⚠️ Configuration issues found: {len(issues)}")
            
    except Exception as e:
        issues.append(f"Error reading .env: {e}")
    
    return len(issues) == 0, issues


def test_database_file():
    """Test database setup."""
    logger.info("🗄️ Testing database setup...")
    
    issues = []
    
    # Check if SQLite database exists (for development)
    db_files = ['ai_secretary.db', 'instance/ai_secretary.db', 'dev.db']
    db_found = False
    
    for db_file in db_files:
        if os.path.exists(db_file):
            db_found = True
            logger.info(f"✅ Database file found: {db_file}")
            break
    
    if not db_found:
        issues.append("No database file found - may need initialization")
    
    # Check migrations directory
    if not os.path.exists('migrations'):
        issues.append("Missing migrations directory")
    else:
        logger.info("✅ migrations directory exists")
    
    return len(issues) == 0, issues


def test_import_basic():
    """Test basic imports without circular dependencies."""
    logger.info("📦 Testing basic imports...")
    
    issues = []
    
    try:
        # Test basic Flask import
        import flask
        logger.info("✅ Flask import successful")
    except Exception as e:
        issues.append(f"Flask import failed: {e}")
    
    try:
        # Test SQLAlchemy import
        import sqlalchemy
        logger.info("✅ SQLAlchemy import successful")
    except Exception as e:
        issues.append(f"SQLAlchemy import failed: {e}")
    
    try:
        # Test other critical imports
        import requests
        import jwt
        import werkzeug
        logger.info("✅ Critical dependencies import successful")
    except Exception as e:
        issues.append(f"Critical dependency import failed: {e}")
    
    return len(issues) == 0, issues


def test_file_structure():
    """Test project file structure."""
    logger.info("📁 Testing file structure...")
    
    issues = []
    required_files = [
        'run.py',
        'config.py',
        'requirements.txt',
        'app/__init__.py',
        'app/fast_app.py',
        'app/models',
        'app/api',
        'app/utils'
    ]
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            issues.append(f"Missing required file/directory: {file_path}")
        else:
            logger.info(f"✅ {file_path} exists")
    
    return len(issues) == 0, issues


def test_gitignore():
    """Test .gitignore file."""
    logger.info("📝 Testing .gitignore...")
    
    if not os.path.exists('.gitignore'):
        return False, ["Missing .gitignore file"]
    
    issues = []
    required_patterns = [
        '.env',
        '*.db',
        '__pycache__',
        '.pytest_cache',
        'instance/',
        'logs/'
    ]
    
    try:
        with open('.gitignore', 'r') as f:
            content = f.read()
        
        for pattern in required_patterns:
            if pattern not in content:
                issues.append(f"Missing pattern in .gitignore: {pattern}")
        
        if len(issues) == 0:
            logger.info("✅ .gitignore looks good")
        else:
            logger.warning(f"⚠️ .gitignore issues: {len(issues)}")
            
    except Exception as e:
        issues.append(f"Error reading .gitignore: {e}")
    
    return len(issues) == 0, issues


def run_syntax_check():
    """Run Python syntax check on main files."""
    logger.info("🔍 Running syntax check...")
    
    issues = []
    files_to_check = [
        'run.py',
        'config.py',
        'app/fast_app.py'
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            try:
                result = subprocess.run([
                    sys.executable, '-m', 'py_compile', file_path
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"✅ {file_path} syntax OK")
                else:
                    issues.append(f"Syntax error in {file_path}: {result.stderr}")
                    
            except Exception as e:
                issues.append(f"Error checking {file_path}: {e}")
    
    return len(issues) == 0, issues


def generate_simple_report(results):
    """Generate simple validation report."""
    logger.info("📊 Generating validation report...")
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'overall_success': True,
        'tests': {},
        'summary': {
            'total_tests': len(results),
            'passed_tests': 0,
            'failed_tests': 0
        },
        'all_issues': []
    }
    
    for test_name, (success, issues) in results.items():
        report['tests'][test_name] = {
            'success': success,
            'issues': issues
        }
        
        if success:
            report['summary']['passed_tests'] += 1
        else:
            report['summary']['failed_tests'] += 1
            report['overall_success'] = False
            report['all_issues'].extend(issues)
    
    return report


def main():
    """Main validation function."""
    logger.info("🚀 Starting simple project validation...")
    
    results = {}
    
    # Run all tests
    results['environment_setup'] = test_environment_setup()
    results['config_file'] = test_config_file()
    results['database_setup'] = test_database_file()
    results['basic_imports'] = test_import_basic()
    results['file_structure'] = test_file_structure()
    results['gitignore'] = test_gitignore()
    results['syntax_check'] = run_syntax_check()
    
    # Generate report
    report = generate_simple_report(results)
    
    # Save report
    report_file = f"simple_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Print summary
    logger.info(f"📊 Report saved to: {report_file}")
    logger.info(f"🎯 Overall success: {report['overall_success']}")
    logger.info(f"📈 Passed: {report['summary']['passed_tests']}/{report['summary']['total_tests']}")
    
    if report['all_issues']:
        logger.info("❌ Issues found:")
        for issue in report['all_issues']:
            logger.info(f"   - {issue}")
    
    return report['overall_success']


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)