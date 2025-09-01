"""
Configuration for comprehensive testing infrastructure.
"""
import os
from typing import Dict, Any


class ComprehensiveTestConfig:
    """Configuration for comprehensive testing."""
    
    # Test Environment Configuration
    TEST_ENVIRONMENT = {
        'database_url': os.environ.get('TEST_DATABASE_URL', 'sqlite:///test_comprehensive.db'),
        'redis_url': os.environ.get('TEST_REDIS_URL', 'redis://localhost:6380/0'),
        'api_base_url': os.environ.get('TEST_API_BASE_URL', 'http://localhost:5001'),
        'cleanup_on_exit': os.environ.get('TEST_CLEANUP_ON_EXIT', 'true').lower() == 'true',
        'parallel_execution': os.environ.get('TEST_PARALLEL_EXECUTION', 'false').lower() == 'true',
        'max_workers': int(os.environ.get('TEST_MAX_WORKERS', '4')),
        'external_services': {
            'vies': os.environ.get('VIES_API_URL', 'https://ec.europa.eu/taxation_customs/vies/services/checkVatService'),
            'gleif': os.environ.get('GLEIF_API_URL', 'https://api.gleif.org/api/v1'),
            'stripe': os.environ.get('STRIPE_API_URL', 'https://api.stripe.com/v1'),
            'google_calendar': os.environ.get('GOOGLE_CALENDAR_API_URL', 'https://www.googleapis.com/calendar/v3')
        }
    }
    
    # Test Data Manager Configuration
    TEST_DATA_MANAGER = {
        'vies_api_url': os.environ.get('VIES_API_URL', 'https://ec.europa.eu/taxation_customs/vies/services/checkVatService'),
        'gleif_api_url': os.environ.get('GLEIF_API_URL', 'https://api.gleif.org/api/v1'),
        'companies_house_api_key': os.environ.get('COMPANIES_HOUSE_API_KEY'),
        'opencorporates_api_key': os.environ.get('OPENCORPORATES_API_KEY'),
        'rate_limits': {
            'vies': int(os.environ.get('VIES_RATE_LIMIT', '10')),  # requests per minute
            'gleif': int(os.environ.get('GLEIF_RATE_LIMIT', '60')),
            'companies_house': int(os.environ.get('COMPANIES_HOUSE_RATE_LIMIT', '600')),
            'opencorporates': int(os.environ.get('OPENCORPORATES_RATE_LIMIT', '500'))
        },
        'timeout_seconds': int(os.environ.get('API_TIMEOUT_SECONDS', '30')),
        'retry_attempts': int(os.environ.get('API_RETRY_ATTEMPTS', '3')),
        'cache_duration_hours': int(os.environ.get('DATA_CACHE_DURATION_HOURS', '24'))
    }
    
    # Test Execution Configuration
    TEST_EXECUTION = {
        'max_execution_time_minutes': int(os.environ.get('MAX_EXECUTION_TIME_MINUTES', '120')),
        'test_timeout_seconds': int(os.environ.get('TEST_TIMEOUT_SECONDS', '300')),
        'retry_failed_tests': os.environ.get('RETRY_FAILED_TESTS', 'true').lower() == 'true',
        'max_retries': int(os.environ.get('MAX_TEST_RETRIES', '2')),
        'continue_on_failure': os.environ.get('CONTINUE_ON_FAILURE', 'true').lower() == 'true',
        'detailed_logging': os.environ.get('DETAILED_LOGGING', 'true').lower() == 'true',
        'save_test_artifacts': os.environ.get('SAVE_TEST_ARTIFACTS', 'true').lower() == 'true'
    }
    
    # Reporting Configuration
    REPORTING = {
        'output_directory': os.environ.get('TEST_REPORT_OUTPUT_DIR', 'test_reports'),
        'generate_html_report': os.environ.get('GENERATE_HTML_REPORT', 'true').lower() == 'true',
        'generate_json_report': os.environ.get('GENERATE_JSON_REPORT', 'true').lower() == 'true',
        'generate_csv_report': os.environ.get('GENERATE_CSV_REPORT', 'false').lower() == 'true',
        'include_performance_metrics': os.environ.get('INCLUDE_PERFORMANCE_METRICS', 'true').lower() == 'true',
        'include_detailed_logs': os.environ.get('INCLUDE_DETAILED_LOGS', 'false').lower() == 'true'
    }
    
    # Performance Testing Configuration
    PERFORMANCE = {
        'load_test_enabled': os.environ.get('LOAD_TEST_ENABLED', 'true').lower() == 'true',
        'concurrent_users': int(os.environ.get('CONCURRENT_USERS', '10')),
        'test_duration_seconds': int(os.environ.get('LOAD_TEST_DURATION_SECONDS', '300')),
        'ramp_up_seconds': int(os.environ.get('RAMP_UP_SECONDS', '60')),
        'response_time_threshold_ms': int(os.environ.get('RESPONSE_TIME_THRESHOLD_MS', '2000')),
        'error_rate_threshold': float(os.environ.get('ERROR_RATE_THRESHOLD', '0.05')),
        'throughput_threshold_rps': float(os.environ.get('THROUGHPUT_THRESHOLD_RPS', '10.0'))
    }
    
    # Security Testing Configuration
    SECURITY = {
        'security_tests_enabled': os.environ.get('SECURITY_TESTS_ENABLED', 'true').lower() == 'true',
        'authentication_tests': os.environ.get('AUTHENTICATION_TESTS', 'true').lower() == 'true',
        'authorization_tests': os.environ.get('AUTHORIZATION_TESTS', 'true').lower() == 'true',
        'input_validation_tests': os.environ.get('INPUT_VALIDATION_TESTS', 'true').lower() == 'true',
        'sql_injection_tests': os.environ.get('SQL_INJECTION_TESTS', 'true').lower() == 'true',
        'xss_tests': os.environ.get('XSS_TESTS', 'true').lower() == 'true',
        'csrf_tests': os.environ.get('CSRF_TESTS', 'true').lower() == 'true'
    }
    
    # Integration Testing Configuration
    INTEGRATION = {
        'external_api_tests': os.environ.get('EXTERNAL_API_TESTS', 'true').lower() == 'true',
        'webhook_tests': os.environ.get('WEBHOOK_TESTS', 'true').lower() == 'true',
        'oauth_tests': os.environ.get('OAUTH_TESTS', 'true').lower() == 'true',
        'payment_tests': os.environ.get('PAYMENT_TESTS', 'false').lower() == 'true',  # Disabled by default
        'email_tests': os.environ.get('EMAIL_TESTS', 'false').lower() == 'true',  # Disabled by default
        'sms_tests': os.environ.get('SMS_TESTS', 'false').lower() == 'true'  # Disabled by default
    }
    
    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Get complete configuration dictionary."""
        return {
            'environment': cls.TEST_ENVIRONMENT,
            'data_manager': cls.TEST_DATA_MANAGER,
            'execution': cls.TEST_EXECUTION,
            'reporting': cls.REPORTING,
            'performance': cls.PERFORMANCE,
            'security': cls.SECURITY,
            'integration': cls.INTEGRATION
        }
    
    @classmethod
    def get_environment_variables(cls) -> Dict[str, str]:
        """Get environment variables for test execution."""
        return {
            # Flask/Application settings
            'FLASK_ENV': 'testing',
            'TESTING': 'True',
            'WTF_CSRF_ENABLED': 'False',
            'DB_SCHEMA': '',
            
            # Database settings
            'DATABASE_URL': cls.TEST_ENVIRONMENT['database_url'],
            'TEST_DATABASE_URL': cls.TEST_ENVIRONMENT['database_url'],
            
            # Redis settings
            'REDIS_URL': cls.TEST_ENVIRONMENT['redis_url'],
            'CELERY_BROKER_URL': cls.TEST_ENVIRONMENT['redis_url'],
            'CELERY_RESULT_BACKEND': cls.TEST_ENVIRONMENT['redis_url'],
            'RATE_LIMIT_STORAGE_URL': cls.TEST_ENVIRONMENT['redis_url'],
            
            # Disable health checks for testing
            'HEALTH_CHECK_DATABASE_ENABLED': 'false',
            'HEALTH_CHECK_REDIS_ENABLED': 'false',
            
            # Disable middleware that might interfere with testing
            'TENANT_MIDDLEWARE_ENABLED': 'false',
            
            # API URLs
            'VIES_API_URL': cls.TEST_DATA_MANAGER['vies_api_url'],
            'GLEIF_API_URL': cls.TEST_DATA_MANAGER['gleif_api_url'],
            
            # Logging
            'LOG_LEVEL': 'DEBUG' if cls.TEST_EXECUTION['detailed_logging'] else 'INFO',
            'LOG_FORMAT': 'text',
            
            # Security settings for testing
            'JWT_ACCESS_TOKEN_EXPIRES': 'False',  # Disable token expiration for tests
            'SECRET_KEY': 'test-secret-key-not-for-production',
            'JWT_SECRET_KEY': 'test-jwt-secret-key-not-for-production'
        }
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate configuration and check for required settings."""
        required_settings = []
        missing_settings = []
        
        # Check for required external API keys if integration tests are enabled
        if cls.INTEGRATION['external_api_tests']:
            if cls.INTEGRATION['payment_tests'] and not os.environ.get('STRIPE_SECRET_KEY'):
                missing_settings.append('STRIPE_SECRET_KEY (required for payment tests)')
            
            if cls.INTEGRATION['oauth_tests'] and not os.environ.get('GOOGLE_CLIENT_ID'):
                missing_settings.append('GOOGLE_CLIENT_ID (required for OAuth tests)')
        
        if missing_settings:
            print("Warning: Missing configuration for some tests:")
            for setting in missing_settings:
                print(f"  - {setting}")
            print("These tests will be skipped.")
        
        return True  # Always return True, just warn about missing optional settings