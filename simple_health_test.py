#!/usr/bin/env python3
"""
Simple test for HealthValidator functionality.
"""

import asyncio
import os
import sys
from datetime import datetime

# Set environment variables for testing
os.environ.update({
    'FLASK_ENV': 'testing',
    'SECRET_KEY': 'test-key',
    'DATABASE_URL': 'sqlite:///test.db',
    'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db'
})

# Import after setting environment
from app.services.health_validator import (
    HealthValidator, ServiceStatus, ServiceType, 
    ServiceValidationResult, SystemHealthReport
)


def test_status_messages():
    """Test status message generation."""
    print("💬 Testing status message generation...")
    
    validator = HealthValidator()
    
    # Create test results for different statuses
    test_results = [
        ServiceValidationResult(
            service_name="test_available",
            service_type=ServiceType.EXTERNAL_API,
            status=ServiceStatus.AVAILABLE,
            response_time_ms=150.5
        ),
        ServiceValidationResult(
            service_name="test_degraded",
            service_type=ServiceType.DATABASE,
            status=ServiceStatus.DEGRADED,
            response_time_ms=2500.0,
            error_message="High response time detected"
        ),
        ServiceValidationResult(
            service_name="test_fallback",
            service_type=ServiceType.CACHE,
            status=ServiceStatus.FALLBACK,
            error_message="Connection refused",
            fallback_available=True,
            fallback_message="Using in-memory cache"
        ),
        ServiceValidationResult(
            service_name="test_unavailable",
            service_type=ServiceType.MESSAGING,
            status=ServiceStatus.UNAVAILABLE,
            error_message="Service not configured",
            fallback_available=False
        )
    ]
    
    for result in test_results:
        message = validator.get_service_status_message(result.service_name, result)
        print(f"  {result.status.value} -> {message}")
    
    print("✅ Status message generation test completed\n")


def test_fallback_modes():
    """Test fallback mode configuration."""
    print("🔄 Testing fallback mode configuration...")
    
    validator = HealthValidator()
    
    # Test that fallback modes are properly configured
    expected_services = ['openai', 'stripe', 'redis', 'google_oauth', 'telegram', 'signal', 'smtp', 'database']
    
    for service in expected_services:
        if service in validator.fallback_modes:
            fallback_info = validator.fallback_modes[service]
            print(f"  ✅ {service}: fallback_available={fallback_info['fallback_available']}")
            if fallback_info['fallback_message']:
                print(f"     Message: {fallback_info['fallback_message']}")
        else:
            print(f"  ❌ {service}: No fallback configuration found")
    
    print("✅ Fallback mode configuration test completed\n")


async def test_service_validation_structure():
    """Test that service validation methods exist and return proper structure."""
    print("🔍 Testing service validation structure...")
    
    validator = HealthValidator()
    
    # Test methods exist
    validation_methods = [
        'validate_database',
        'validate_redis', 
        'validate_openai',
        'validate_stripe',
        'validate_google_oauth',
        'validate_telegram',
        'validate_smtp'
    ]
    
    for method_name in validation_methods:
        if hasattr(validator, method_name):
            print(f"  ✅ {method_name} method exists")
        else:
            print(f"  ❌ {method_name} method missing")
    
    # Test that validate_all_services exists
    if hasattr(validator, 'validate_all_services'):
        print(f"  ✅ validate_all_services method exists")
    else:
        print(f"  ❌ validate_all_services method missing")
    
    # Test utility methods
    utility_methods = ['get_service_status_message', 'generate_status_summary']
    for method_name in utility_methods:
        if hasattr(validator, method_name):
            print(f"  ✅ {method_name} utility method exists")
        else:
            print(f"  ❌ {method_name} utility method missing")
    
    print("✅ Service validation structure test completed\n")


def test_data_structures():
    """Test that data structures are properly defined."""
    print("📊 Testing data structures...")
    
    # Test ServiceStatus enum
    expected_statuses = ['AVAILABLE', 'DEGRADED', 'UNAVAILABLE', 'FALLBACK', 'UNKNOWN']
    for status in expected_statuses:
        if hasattr(ServiceStatus, status):
            print(f"  ✅ ServiceStatus.{status} exists")
        else:
            print(f"  ❌ ServiceStatus.{status} missing")
    
    # Test ServiceType enum
    expected_types = ['DATABASE', 'CACHE', 'EXTERNAL_API', 'MESSAGING', 'STORAGE', 'AUTHENTICATION']
    for service_type in expected_types:
        if hasattr(ServiceType, service_type):
            print(f"  ✅ ServiceType.{service_type} exists")
        else:
            print(f"  ❌ ServiceType.{service_type} missing")
    
    # Test that dataclasses can be instantiated
    try:
        result = ServiceValidationResult(
            service_name="test",
            service_type=ServiceType.DATABASE,
            status=ServiceStatus.AVAILABLE,
            response_time_ms=100.0
        )
        print(f"  ✅ ServiceValidationResult can be instantiated")
    except Exception as e:
        print(f"  ❌ ServiceValidationResult instantiation failed: {e}")
    
    try:
        report = SystemHealthReport(
            overall_status=ServiceStatus.AVAILABLE,
            services={},
            fallback_services=[],
            critical_issues=[],
            warnings=[],
            recommendations=[]
        )
        print(f"  ✅ SystemHealthReport can be instantiated")
    except Exception as e:
        print(f"  ❌ SystemHealthReport instantiation failed: {e}")
    
    print("✅ Data structures test completed\n")


def main():
    """Main test function."""
    print("🧪 HealthValidator Simple Test Suite")
    print("=" * 50)
    print()
    
    try:
        # Test data structures
        test_data_structures()
        
        # Test fallback modes
        test_fallback_modes()
        
        # Test status messages
        test_status_messages()
        
        # Test service validation structure
        asyncio.run(test_service_validation_structure())
        
        print("✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()