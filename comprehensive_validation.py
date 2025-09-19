#!/usr/bin/env python3
"""
Comprehensive Validation Suite for AI Secretary Project
Implements task 8.1: Комплексная валидация проекта

This script runs all created validators and performs comprehensive project validation.
"""

import os
import sys
import json
import time
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


def run_config_validation():
    """Run configuration validation."""
    logger.info("📋 Running configuration validation...")
    
    try:
        # Add app to path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
        from app.utils.config_validator import ConfigValidator
        
        validator = ConfigValidator(".env")
        result = validator.validate_all()
        
        if result.valid:
            logger.info("✅ Configuration validation passed")
            return True, result
        else:
            logger.error("❌ Configuration validation failed")
            logger.error(f"Critical issues: {len(result.critical_issues)}")
            logger.error(f"Errors: {len(result.errors)}")
            return False, result
            
    except Exception as e:
        logger.error(f"❌ Config validation failed: {e}")
        return False, {'error': str(e)}


def run_health_validation():
    """Run health validation."""
    logger.info("🏥 Running health validation...")
    
    try:
        from app import create_app
        from flask_sqlalchemy import SQLAlchemy
        from app.utils.health_validator import HealthValidator
        
        app = create_app()
        with app.app_context():
            db = SQLAlchemy(app)
            validator = HealthValidator(app, db)
            result = validator.generate_health_report()
            
            if result.get('overall_status') == 'healthy':
                logger.info("✅ Health validation passed")
                return True, result
            else:
                logger.warning("⚠️ Health validation found issues")
                return False, result
                
    except Exception as e:
        logger.error(f"❌ Health validation failed: {e}")
        return False, {'error': str(e)}


def run_route_validation():
    """Run route validation."""
    logger.info("🛣️ Running route validation...")
    
    try:
        from app import create_app
        from app.utils.route_validator import RouteValidator
        
        app = create_app()
        with app.app_context():
            validator = RouteValidator(app)
            result = validator.validate_all_routes()
            
            if result.success:
                logger.info("✅ Route validation passed")
                return True, result
            else:
                logger.warning("⚠️ Route validation found issues")
                return False, result
                
    except Exception as e:
        logger.error(f"❌ Route validation failed: {e}")
        return False, {'error': str(e)}


def run_gitignore_validation():
    """Run gitignore validation."""
    logger.info("📁 Running gitignore validation...")
    
    try:
        from gitignore_validator import GitignoreValidator
        
        validator = GitignoreValidator()
        result = validator.validate_gitignore()
        
        if result.get('valid'):
            logger.info("✅ Gitignore validation passed")
            return True, result
        else:
            logger.warning("⚠️ Gitignore validation found issues")
            return False, result
            
    except Exception as e:
        logger.error(f"❌ Gitignore validation failed: {e}")
        return False, {'error': str(e)}


def test_application_startup():
    """Test application startup."""
    logger.info("🔄 Testing application startup...")
    
    try:
        # Try to import and create the app
        from app import create_app
        
        app = create_app()
        
        # Test basic app creation
        if app:
            logger.info("✅ Application startup test passed")
            return True, {'success': True, 'message': 'App created successfully'}
        else:
            logger.error("❌ Application startup failed - app is None")
            return False, {'success': False, 'error': 'App creation returned None'}
            
    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        return False, {'success': False, 'error': str(e)}


def test_api_endpoints():
    """Test basic API endpoints."""
    logger.info("🌐 Testing API endpoints...")
    
    try:
        from app import create_app
        
        app = create_app()
        client = app.test_client()
        
        # Test basic endpoints
        endpoints_to_test = [
            ('/', 'GET'),
            ('/health', 'GET'),
            ('/api/health', 'GET'),
        ]
        
        results = []
        for endpoint, method in endpoints_to_test:
            try:
                if method == 'GET':
                    response = client.get(endpoint)
                else:
                    response = client.post(endpoint)
                
                results.append({
                    'endpoint': endpoint,
                    'method': method,
                    'status_code': response.status_code,
                    'success': response.status_code < 500
                })
                
            except Exception as e:
                results.append({
                    'endpoint': endpoint,
                    'method': method,
                    'error': str(e),
                    'success': False
                })
        
        successful_tests = sum(1 for r in results if r.get('success', False))
        total_tests = len(results)
        
        if successful_tests == total_tests:
            logger.info(f"✅ API endpoints test passed ({successful_tests}/{total_tests})")
            return True, {'results': results, 'success_rate': 1.0}
        else:
            logger.warning(f"⚠️ API endpoints test partial success ({successful_tests}/{total_tests})")
            return False, {'results': results, 'success_rate': successful_tests / total_tests}
            
    except Exception as e:
        logger.error(f"❌ API endpoints test failed: {e}")
        return False, {'error': str(e)}


def generate_validation_report(results):
    """Generate comprehensive validation report."""
    logger.info("📊 Generating validation report...")
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'overall_success': True,
        'validations': {},
        'summary': {
            'total_validations': 0,
            'passed_validations': 0,
            'failed_validations': 0,
            'warnings': 0
        },
        'recommendations': []
    }
    
    # Process results
    for validation_name, (success, data) in results.items():
        report['validations'][validation_name] = {
            'success': success,
            'data': data
        }
        
        report['summary']['total_validations'] += 1
        if success:
            report['summary']['passed_validations'] += 1
        else:
            report['summary']['failed_validations'] += 1
            report['overall_success'] = False
    
    # Generate recommendations
    if not results.get('config_validation', (True, {}))[0]:
        report['recommendations'].append("Fix configuration issues before deployment")
    
    if not results.get('health_validation', (True, {}))[0]:
        report['recommendations'].append("Address health validation issues")
    
    if not results.get('startup_test', (True, {}))[0]:
        report['recommendations'].append("Fix application startup issues")
    
    return report


def main():
    """Main validation function."""
    logger.info("🚀 Starting comprehensive project validation...")
    start_time = time.time()
    
    results = {}
    
    # Run all validations
    results['config_validation'] = run_config_validation()
    results['health_validation'] = run_health_validation()
    results['route_validation'] = run_route_validation()
    results['gitignore_validation'] = run_gitignore_validation()
    results['startup_test'] = test_application_startup()
    
    # Run API tests only if startup succeeded
    if results['startup_test'][0]:
        results['api_endpoints_test'] = test_api_endpoints()
    else:
        logger.warning("⚠️ Skipping API tests due to startup failure")
        results['api_endpoints_test'] = (False, {'skipped': True, 'reason': 'startup_failed'})
    
    # Generate report
    report = generate_validation_report(results)
    
    # Save report
    report_file = f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    duration = time.time() - start_time
    
    # Print summary
    logger.info(f"✅ Validation completed in {duration:.2f}s")
    logger.info(f"📊 Report saved to: {report_file}")
    logger.info(f"🎯 Overall success: {report['overall_success']}")
    logger.info(f"📈 Passed: {report['summary']['passed_validations']}/{report['summary']['total_validations']}")
    
    if report['recommendations']:
        logger.info("💡 Recommendations:")
        for rec in report['recommendations']:
            logger.info(f"   - {rec}")
    
    return report['overall_success']


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)