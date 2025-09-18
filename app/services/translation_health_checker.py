#!/usr/bin/env python3
"""
Translation system health checker service.
Runs as a separate service to continuously monitor translation system health.
"""

import os
import sys
import time
import logging
import signal
from datetime import datetime
from typing import Dict, Any

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from app import create_app
from app.services.translation_monitoring_service import get_translation_monitoring_service

class TranslationHealthChecker:
    """Standalone translation health checker service."""
    
    def __init__(self):
        self.app = None
        self.monitoring_service = None
        self.running = True
        self.check_interval = int(os.environ.get('HEALTH_CHECK_INTERVAL', 300))  # 5 minutes
        self.timeout = int(os.environ.get('HEALTH_CHECK_TIMEOUT', 30))  # 30 seconds
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('/app/logs/translation-health.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def initialize(self):
        """Initialize the Flask app and monitoring service."""
        try:
            self.logger.info("Initializing translation health checker...")
            
            # Create Flask app
            self.app = create_app('production')
            
            with self.app.app_context():
                # Initialize monitoring service
                self.monitoring_service = get_translation_monitoring_service()
                
                self.logger.info("Translation health checker initialized successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to initialize health checker: {e}")
            return False
    
    def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        try:
            with self.app.app_context():
                health_result = self.monitoring_service.perform_health_check()
                
                # Log health status
                status = health_result.get('overall_status', 'unknown')
                self.logger.info(f"Health check completed: {status}")
                
                # Log any critical alerts
                alerts = self.monitoring_service.get_alerts_by_severity('critical')
                if alerts:
                    self.logger.warning(f"Critical alerts active: {len(alerts)}")
                    for alert in alerts[:5]:  # Log first 5 alerts
                        self.logger.warning(f"  - {alert.title}: {alert.message}")
                
                return health_result
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                'overall_status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def check_translation_files(self) -> Dict[str, Any]:
        """Check translation file integrity."""
        languages = ['en', 'de', 'uk']
        file_status = {'status': 'healthy', 'issues': []}
        
        for language in languages:
            po_path = f'/app/app/translations/{language}/LC_MESSAGES/messages.po'
            mo_path = f'/app/app/translations/{language}/LC_MESSAGES/messages.mo'
            
            if not os.path.exists(po_path):
                file_status['status'] = 'unhealthy'
                file_status['issues'].append(f'Missing .po file for {language}')
            
            if not os.path.exists(mo_path):
                file_status['status'] = 'unhealthy'
                file_status['issues'].append(f'Missing .mo file for {language}')
            
            # Check file sizes
            if os.path.exists(po_path) and os.path.getsize(po_path) == 0:
                file_status['status'] = 'unhealthy'
                file_status['issues'].append(f'Empty .po file for {language}')
            
            if os.path.exists(mo_path) and os.path.getsize(mo_path) == 0:
                file_status['status'] = 'unhealthy'
                file_status['issues'].append(f'Empty .mo file for {language}')
        
        return file_status
    
    def test_translation_endpoints(self) -> Dict[str, Any]:
        """Test translation API endpoints."""
        import requests
        
        base_url = os.environ.get('APP_BASE_URL', 'http://app:5000')
        test_results = {'status': 'healthy', 'tests': []}
        
        # Test health endpoint
        try:
            response = requests.get(f'{base_url}/api/v1/health', timeout=self.timeout)
            if response.status_code == 200:
                test_results['tests'].append({'endpoint': 'health', 'status': 'pass'})
            else:
                test_results['status'] = 'unhealthy'
                test_results['tests'].append({
                    'endpoint': 'health', 
                    'status': 'fail', 
                    'error': f'HTTP {response.status_code}'
                })
        except Exception as e:
            test_results['status'] = 'unhealthy'
            test_results['tests'].append({
                'endpoint': 'health', 
                'status': 'fail', 
                'error': str(e)
            })
        
        # Test languages endpoint
        try:
            response = requests.get(f'{base_url}/api/v1/languages', timeout=self.timeout)
            if response.status_code == 200:
                test_results['tests'].append({'endpoint': 'languages', 'status': 'pass'})
            else:
                test_results['status'] = 'unhealthy'
                test_results['tests'].append({
                    'endpoint': 'languages', 
                    'status': 'fail', 
                    'error': f'HTTP {response.status_code}'
                })
        except Exception as e:
            test_results['status'] = 'unhealthy'
            test_results['tests'].append({
                'endpoint': 'languages', 
                'status': 'fail', 
                'error': str(e)
            })
        
        # Test translation endpoints for each language
        languages = ['en', 'de', 'uk']
        test_key = 'Welcome'
        
        for language in languages:
            try:
                response = requests.get(
                    f'{base_url}/api/v1/translate',
                    params={'key': test_key, 'lang': language},
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    test_results['tests'].append({
                        'endpoint': f'translate_{language}', 
                        'status': 'pass'
                    })
                else:
                    test_results['status'] = 'unhealthy'
                    test_results['tests'].append({
                        'endpoint': f'translate_{language}', 
                        'status': 'fail', 
                        'error': f'HTTP {response.status_code}'
                    })
            except Exception as e:
                test_results['status'] = 'unhealthy'
                test_results['tests'].append({
                    'endpoint': f'translate_{language}', 
                    'status': 'fail', 
                    'error': str(e)
                })
        
        return test_results
    
    def run_health_checks(self):
        """Run all health checks and log results."""
        self.logger.info("Running comprehensive health checks...")
        
        # Perform main health check
        health_result = self.perform_health_check()
        
        # Check translation files
        file_status = self.check_translation_files()
        
        # Test translation endpoints
        endpoint_tests = self.test_translation_endpoints()
        
        # Combine results
        overall_status = 'healthy'
        if (health_result.get('overall_status') != 'healthy' or 
            file_status.get('status') != 'healthy' or 
            endpoint_tests.get('status') != 'healthy'):
            overall_status = 'unhealthy'
        
        # Log comprehensive results
        self.logger.info(f"Health check summary: {overall_status}")
        self.logger.info(f"  Main health check: {health_result.get('overall_status', 'unknown')}")
        self.logger.info(f"  File integrity: {file_status.get('status', 'unknown')}")
        self.logger.info(f"  Endpoint tests: {endpoint_tests.get('status', 'unknown')}")
        
        # Log issues
        if file_status.get('issues'):
            for issue in file_status['issues']:
                self.logger.warning(f"  File issue: {issue}")
        
        failed_tests = [t for t in endpoint_tests.get('tests', []) if t.get('status') == 'fail']
        if failed_tests:
            for test in failed_tests:
                self.logger.warning(f"  Endpoint test failed: {test['endpoint']} - {test.get('error', 'unknown error')}")
        
        return overall_status
    
    def run(self):
        """Main service loop."""
        if not self.initialize():
            self.logger.error("Failed to initialize, exiting...")
            sys.exit(1)
        
        self.logger.info(f"Translation health checker started (check interval: {self.check_interval}s)")
        
        while self.running:
            try:
                start_time = time.time()
                
                # Run health checks
                status = self.run_health_checks()
                
                # Calculate check duration
                duration = time.time() - start_time
                self.logger.info(f"Health check completed in {duration:.2f}s")
                
                # Sleep until next check
                if self.running:
                    time.sleep(self.check_interval)
                    
            except KeyboardInterrupt:
                self.logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                if self.running:
                    time.sleep(60)  # Wait 1 minute before retrying
        
        self.logger.info("Translation health checker stopped")

def main():
    """Main entry point."""
    checker = TranslationHealthChecker()
    checker.run()

if __name__ == '__main__':
    main()