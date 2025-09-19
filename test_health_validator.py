#!/usr/bin/env python3
"""
Test script for the HealthValidator service.

This script tests the comprehensive health validation system with fallback modes
and informative status messages.
"""

import asyncio
import sys
import os
from datetime import datetime

# Set up the environment
os.environ.setdefault('FLASK_ENV', 'testing')

from flask import Flask


def create_test_app():
    """Create a minimal Flask app for testing."""
    app = Flask(__name__)
    
    # Set test configuration
    app.config.update({
        'SECRET_KEY': 'test-secret-key',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'TESTING': True,
        
        # External service configurations (some intentionally missing for testing)
        'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
        'STRIPE_SECRET_KEY': os.environ.get('STRIPE_SECRET_KEY'),
        'REDIS_URL': os.environ.get('REDIS_URL'),
        'GOOGLE_CLIENT_ID': os.environ.get('GOOGLE_CLIENT_ID'),
        'GOOGLE_CLIENT_SECRET': os.environ.get('GOOGLE_CLIENT_SECRET'),
        'TELEGRAM_BOT_TOKEN': os.environ.get('TELEGRAM_BOT_TOKEN'),
        'SMTP_SERVER': os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
        'SMTP_USERNAME': os.environ.get('SMTP_USERNAME'),
        'SMTP_PASSWORD': os.environ.get('SMTP_PASSWORD'),
        'SMTP_PORT': int(os.environ.get('SMTP_PORT', 587)),
    })
    
    # Initialize database
    from app import db
    db.init_app(app)
    
    return app


async def test_individual_services():
    """Test individual service validations."""
    print("🔍 Testing individual service validations...\n")
    
    from app.services.health_validator import health_validator, ServiceStatus
    
    services = [
        ('Database', health_validator.validate_database),
        ('Redis', health_validator.validate_redis),
        ('OpenAI', health_validator.validate_openai),
        ('Stripe', health_validator.validate_stripe),
        ('Google OAuth', health_validator.validate_google_oauth),
        ('Telegram', health_validator.validate_telegram),
        ('SMTP', health_validator.validate_smtp),
    ]
    
    for service_name, validation_method in services:
        try:
            print(f"Testing {service_name}...")
            result = await validation_method()
            
            status_icon = {
                ServiceStatus.AVAILABLE: "✅",
                ServiceStatus.DEGRADED: "⚠️",
                ServiceStatus.FALLBACK: "🔄",
                ServiceStatus.UNAVAILABLE: "❌",
                ServiceStatus.UNKNOWN: "❓"
            }.get(result.status, "❓")
            
            print(f"  {status_icon} Status: {result.status.value}")
            if result.response_time_ms:
                print(f"  ⏱️  Response Time: {result.response_time_ms:.2f}ms")
            if result.error_message:
                print(f"  ❗ Error: {result.error_message}")
            if result.fallback_available:
                print(f"  🔄 Fallback: {result.fallback_message}")
            if result.recommendations:
                print(f"  💡 Recommendations:")
                for rec in result.recommendations:
                    print(f"     • {rec}")
            print()
            
        except Exception as e:
            print(f"  ❌ Failed to test {service_name}: {e}\n")


async def test_comprehensive_validation():
    """Test comprehensive system validation."""
    print("🏥 Running comprehensive system health validation...\n")
    
    from app.services.health_validator import health_validator
    
    try:
        report = await health_validator.validate_all_services()
        summary = health_validator.generate_status_summary(report)
        
        # Print overall status
        status_icon = {
            'available': "🟢",
            'degraded': "🟡",
            'fallback': "🟠",
            'unavailable': "🔴",
            'unknown': "⚪"
        }.get(report.overall_status.value, "⚪")
        
        print(f"{status_icon} Overall System Status: {report.overall_status.value.upper()}")
        print(f"📊 {summary['status_message']}")
        print()
        
        # Print service summary
        services_summary = summary['services_summary']
        print("📋 Services Summary:")
        print(f"  • Total Services: {services_summary['total']}")
        print(f"  • Available: {services_summary['available']}")
        print(f"  • Degraded: {services_summary['degraded']}")
        print(f"  • Fallback Mode: {services_summary['fallback']}")
        print(f"  • Unavailable: {services_summary['unavailable']}")
        print()
        
        # Print service messages
        print("📝 Service Status Messages:")
        for service, message in summary['service_messages'].items():
            print(f"  {message}")
        print()
        
        # Print critical issues
        if report.critical_issues:
            print("🚨 Critical Issues:")
            for issue in report.critical_issues:
                print(f"  • {issue}")
            print()
        
        # Print warnings
        if report.warnings:
            print("⚠️  Warnings:")
            for warning in report.warnings:
                print(f"  • {warning}")
            print()
        
        # Print recommendations
        if report.recommendations:
            print("💡 Recommendations:")
            for rec in report.recommendations:
                print(f"  • {rec}")
            print()
        
        # Print fallback services
        if report.fallback_services:
            print("🔄 Services in Fallback Mode:")
            for service in report.fallback_services:
                print(f"  • {service}")
            print()
        
        print(f"🕐 Report generated at: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
    except Exception as e:
        print(f"❌ Comprehensive validation failed: {e}")


def test_status_messages():
    """Test status message generation."""
    print("💬 Testing status message generation...\n")
    
    from app.services.health_validator import ServiceValidationResult, ServiceType
    
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
        message = health_validator.get_service_status_message(result.service_name, result)
        print(f"Status: {result.status.value} -> {message}")
    
    print()


async def main():
    """Main test function."""
    print("🧪 HealthValidator Test Suite")
    print("=" * 50)
    print()
    
    # Create test Flask app context
    app = create_test_app()
    
    with app.app_context():
        # Test status message generation
        test_status_messages()
        
        # Test individual services
        await test_individual_services()
        
        # Test comprehensive validation
        await test_comprehensive_validation()
    
    print("✅ Test suite completed!")


if __name__ == '__main__':
    # Run the async test suite
    asyncio.run(main())