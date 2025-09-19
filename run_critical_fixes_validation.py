#!/usr/bin/env python3
"""
Critical Fixes Validation Test Runner
Runs comprehensive tests to validate all critical fixes are working.
"""
import os
import sys
import subprocess
import time
import json
from datetime import datetime


class ValidationTestRunner:
    """Test runner for critical fixes validation"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {},
            'summary': {
                'total_tests': 0,
                'passed': 0,
                'failed': 0,
                'skipped': 0,
                'errors': []
            }
        }
    
    def run_test_suite(self, test_file, description):
        """Run a specific test suite"""
        print(f"\n{'='*60}")
        print(f"Running {description}")
        print(f"{'='*60}")
        
        try:
            # Run pytest with verbose output
            cmd = [
                sys.executable, '-m', 'pytest',
                test_file,
                '-v',
                '--tb=short',
                '--no-header',
                '--json-report',
                '--json-report-file=temp_report.json'
            ]
            
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            duration = time.time() - start_time
            
            # Parse JSON report if available
            test_results = self.parse_json_report()
            
            self.results['tests'][test_file] = {
                'description': description,
                'duration': duration,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'test_results': test_results
            }
            
            # Update summary
            if test_results:
                self.results['summary']['total_tests'] += test_results.get('total', 0)
                self.results['summary']['passed'] += test_results.get('passed', 0)
                self.results['summary']['failed'] += test_results.get('failed', 0)
                self.results['summary']['skipped'] += test_results.get('skipped', 0)
            
            print(f"✅ Completed in {duration:.2f}s")
            if result.returncode != 0:
                print(f"⚠️  Some tests failed (exit code: {result.returncode})")
                self.results['summary']['errors'].append(f"{test_file}: exit code {result.returncode}")
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            print(f"❌ Test suite timed out after 5 minutes")
            self.results['summary']['errors'].append(f"{test_file}: timeout")
            return False
            
        except Exception as e:
            print(f"❌ Error running test suite: {e}")
            self.results['summary']['errors'].append(f"{test_file}: {str(e)}")
            return False
    
    def parse_json_report(self):
        """Parse pytest JSON report"""
        try:
            if os.path.exists('temp_report.json'):
                with open('temp_report.json', 'r') as f:
                    report = json.load(f)
                
                os.remove('temp_report.json')  # Clean up
                
                return {
                    'total': report.get('summary', {}).get('total', 0),
                    'passed': report.get('summary', {}).get('passed', 0),
                    'failed': report.get('summary', {}).get('failed', 0),
                    'skipped': report.get('summary', {}).get('skipped', 0),
                    'duration': report.get('duration', 0)
                }
        except Exception as e:
            print(f"Warning: Could not parse JSON report: {e}")
        
        return None
    
    def run_all_validations(self):
        """Run all validation test suites"""
        print("🚀 Starting Critical Fixes Validation")
        print(f"Timestamp: {self.results['timestamp']}")
        
        # Test suites to run
        test_suites = [
            ('tests/test_critical_fixes_validation.py', 'Critical Fixes Comprehensive Validation'),
            ('tests/test_performance_validation.py', 'Performance Validation Tests'),
            ('tests/test_service_fallback_validation.py', 'Service Fallback Validation Tests')
        ]
        
        all_passed = True
        
        for test_file, description in test_suites:
            if os.path.exists(test_file):
                success = self.run_test_suite(test_file, description)
                if not success:
                    all_passed = False
            else:
                print(f"⚠️  Test file not found: {test_file}")
                self.results['summary']['errors'].append(f"Test file not found: {test_file}")
                all_passed = False
        
        return all_passed
    
    def run_quick_smoke_tests(self):
        """Run quick smoke tests to verify basic functionality"""
        print(f"\n{'='*60}")
        print("Running Quick Smoke Tests")
        print(f"{'='*60}")
        
        smoke_tests = [
            self.test_app_starts,
            self.test_database_connection,
            self.test_basic_endpoints,
            self.test_configuration_validity
        ]
        
        smoke_results = []
        
        for test in smoke_tests:
            try:
                result = test()
                smoke_results.append(result)
                if result['passed']:
                    print(f"✅ {result['name']}")
                else:
                    print(f"❌ {result['name']}: {result['error']}")
            except Exception as e:
                print(f"❌ {test.__name__}: {str(e)}")
                smoke_results.append({
                    'name': test.__name__,
                    'passed': False,
                    'error': str(e)
                })
        
        self.results['smoke_tests'] = smoke_results
        return all(r['passed'] for r in smoke_results)
    
    def test_app_starts(self):
        """Test that the app starts without errors"""
        try:
            from app import create_app
            app = create_app('testing')
            return {'name': 'App Startup', 'passed': True, 'error': None}
        except Exception as e:
            return {'name': 'App Startup', 'passed': False, 'error': str(e)}
    
    def test_database_connection(self):
        """Test database connection"""
        try:
            from app import create_app, db
            app = create_app('testing')
            with app.app_context():
                db.session.execute('SELECT 1')
            return {'name': 'Database Connection', 'passed': True, 'error': None}
        except Exception as e:
            return {'name': 'Database Connection', 'passed': False, 'error': str(e)}
    
    def test_basic_endpoints(self):
        """Test basic endpoints respond"""
        try:
            from app import create_app
            app = create_app('testing')
            client = app.test_client()
            
            # Test basic endpoints
            endpoints = ['/', '/api/v1/health']
            for endpoint in endpoints:
                response = client.get(endpoint)
                if response.status_code >= 500:
                    return {'name': 'Basic Endpoints', 'passed': False, 'error': f'{endpoint} returned {response.status_code}'}
            
            return {'name': 'Basic Endpoints', 'passed': True, 'error': None}
        except Exception as e:
            return {'name': 'Basic Endpoints', 'passed': False, 'error': str(e)}
    
    def test_configuration_validity(self):
        """Test configuration is valid"""
        try:
            from app import create_app
            app = create_app('testing')
            
            # Check critical configuration
            required_configs = ['SECRET_KEY', 'SQLALCHEMY_DATABASE_URI']
            for config in required_configs:
                if not app.config.get(config):
                    return {'name': 'Configuration Validity', 'passed': False, 'error': f'Missing {config}'}
            
            return {'name': 'Configuration Validity', 'passed': True, 'error': None}
        except Exception as e:
            return {'name': 'Configuration Validity', 'passed': False, 'error': str(e)}
    
    def generate_report(self):
        """Generate validation report"""
        print(f"\n{'='*60}")
        print("VALIDATION REPORT")
        print(f"{'='*60}")
        
        # Summary
        summary = self.results['summary']
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Skipped: {summary['skipped']}")
        
        if summary['errors']:
            print(f"\nErrors ({len(summary['errors'])}):")
            for error in summary['errors']:
                print(f"  - {error}")
        
        # Test suite details
        print(f"\nTest Suite Details:")
        for test_file, results in self.results['tests'].items():
            print(f"\n{test_file}:")
            print(f"  Description: {results['description']}")
            print(f"  Duration: {results['duration']:.2f}s")
            print(f"  Exit Code: {results['return_code']}")
            
            if results['test_results']:
                tr = results['test_results']
                print(f"  Tests: {tr['total']} total, {tr['passed']} passed, {tr['failed']} failed, {tr['skipped']} skipped")
        
        # Smoke tests
        if 'smoke_tests' in self.results:
            print(f"\nSmoke Tests:")
            for test in self.results['smoke_tests']:
                status = "✅" if test['passed'] else "❌"
                print(f"  {status} {test['name']}")
                if not test['passed'] and test['error']:
                    print(f"    Error: {test['error']}")
        
        # Overall result
        overall_success = (
            summary['failed'] == 0 and
            len(summary['errors']) == 0 and
            all(r['passed'] for r in self.results.get('smoke_tests', []))
        )
        
        print(f"\n{'='*60}")
        if overall_success:
            print("🎉 ALL VALIDATIONS PASSED!")
        else:
            print("⚠️  SOME VALIDATIONS FAILED")
        print(f"{'='*60}")
        
        return overall_success
    
    def save_report(self, filename='validation_report.json'):
        """Save detailed report to file"""
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"\n📄 Detailed report saved to: {filename}")
        except Exception as e:
            print(f"Warning: Could not save report: {e}")


def main():
    """Main function"""
    print("Critical Fixes Validation Test Runner")
    print("=====================================")
    
    # Check if we're in the right directory
    if not os.path.exists('app'):
        print("❌ Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Install pytest-json-report if not available
    try:
        import pytest_json_report
    except ImportError:
        print("Installing pytest-json-report...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pytest-json-report'], check=True)
    
    runner = ValidationTestRunner()
    
    # Run smoke tests first
    print("Running quick smoke tests...")
    smoke_passed = runner.run_quick_smoke_tests()
    
    if not smoke_passed:
        print("\n⚠️  Smoke tests failed. Continuing with full validation anyway...")
    
    # Run full validation
    validation_passed = runner.run_all_validations()
    
    # Generate and save report
    overall_success = runner.generate_report()
    runner.save_report()
    
    # Exit with appropriate code
    sys.exit(0 if overall_success else 1)


if __name__ == '__main__':
    main()