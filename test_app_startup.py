#!/usr/bin/env python3
"""
Test application startup without circular imports
"""

import os
import sys
import subprocess
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_app_import():
    """Test if we can import the app without errors."""
    logger.info("🔄 Testing app import...")
    
    try:
        # Use subprocess to avoid circular import issues
        result = subprocess.run([
            sys.executable, '-c', 
            'from app import create_app; app = create_app(); print("SUCCESS: App created")'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and "SUCCESS" in result.stdout:
            logger.info("✅ App import and creation successful")
            return True, result.stdout.strip()
        else:
            logger.error("❌ App import failed")
            logger.error(f"stdout: {result.stdout}")
            logger.error(f"stderr: {result.stderr}")
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        logger.error("❌ App import timed out")
        return False, "Import timed out after 30 seconds"
    except Exception as e:
        logger.error(f"❌ App import failed: {e}")
        return False, str(e)


def test_flask_run():
    """Test if flask run command works."""
    logger.info("🌐 Testing flask run command...")
    
    try:
        # Set environment variables
        env = os.environ.copy()
        env['FLASK_APP'] = 'run.py'
        env['FLASK_ENV'] = 'development'
        
        # Try to start flask with --help to test if it works
        result = subprocess.run([
            sys.executable, '-m', 'flask', '--help'
        ], capture_output=True, text=True, timeout=10, env=env)
        
        if result.returncode == 0:
            logger.info("✅ Flask command available")
            return True, "Flask command works"
        else:
            logger.error("❌ Flask command failed")
            return False, result.stderr
            
    except Exception as e:
        logger.error(f"❌ Flask command test failed: {e}")
        return False, str(e)


def test_database_connection():
    """Test database connection."""
    logger.info("🗄️ Testing database connection...")
    
    try:
        result = subprocess.run([
            sys.executable, '-c', '''
import os
import sqlite3
from pathlib import Path

# Try to connect to database
db_files = ["ai_secretary.db", "instance/ai_secretary.db", "dev.db"]
for db_file in db_files:
    if os.path.exists(db_file):
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            print(f"SUCCESS: Connected to {db_file}, found {len(tables)} tables")
            break
        except Exception as e:
            print(f"ERROR: Failed to connect to {db_file}: {e}")
else:
    print("ERROR: No database file found")
'''
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "SUCCESS" in result.stdout:
            logger.info("✅ Database connection successful")
            return True, result.stdout.strip()
        else:
            logger.warning("⚠️ Database connection issues")
            return False, result.stdout + result.stderr
            
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False, str(e)


def test_config_loading():
    """Test configuration loading."""
    logger.info("⚙️ Testing configuration loading...")
    
    try:
        result = subprocess.run([
            sys.executable, '-c', '''
import os
import sys
sys.path.insert(0, ".")

try:
    from config import Config
    config = Config()
    print(f"SUCCESS: Config loaded, SECRET_KEY length: {len(getattr(config, 'SECRET_KEY', ''))}")
except Exception as e:
    print(f"ERROR: Config loading failed: {e}")
'''
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "SUCCESS" in result.stdout:
            logger.info("✅ Configuration loading successful")
            return True, result.stdout.strip()
        else:
            logger.error("❌ Configuration loading failed")
            return False, result.stdout + result.stderr
            
    except Exception as e:
        logger.error(f"❌ Config test failed: {e}")
        return False, str(e)


def main():
    """Main test function."""
    logger.info("🚀 Starting application startup tests...")
    
    results = {}
    
    # Run tests
    results['app_import'] = test_app_import()
    results['flask_command'] = test_flask_run()
    results['database_connection'] = test_database_connection()
    results['config_loading'] = test_config_loading()
    
    # Summary
    passed = sum(1 for success, _ in results.values() if success)
    total = len(results)
    
    logger.info(f"📊 Test Results: {passed}/{total} passed")
    
    for test_name, (success, message) in results.items():
        status = "✅" if success else "❌"
        logger.info(f"{status} {test_name}: {message}")
    
    overall_success = passed == total
    logger.info(f"🎯 Overall success: {overall_success}")
    
    return overall_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)