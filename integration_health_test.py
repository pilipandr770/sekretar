#!/usr/bin/env python3
"""
Integration test for HealthValidator with Flask app context.
"""

import asyncio
import os
import sys

# Set environment for testing
os.environ.update({
    'FLASK_ENV': 'testing',
    'SECRET_KEY': 'test-key',
    'DATABASE_URL': 'sqlite:///test.db',
    'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db',
    'SQLALCHEMY_TRACK_MODIFICATIONS': 'False'
})

from flask import Flask
from app import create_app
from app.services.health_validator import health_validator


async def test_with_app_context():
    """Test HealthValidator with Flask app context."""
    print("🧪 Testing HealthValidator with Flask app context...")
    
    # Create app
    app = create_app('testing')
    
    with app.app_context():
        try:
            # Test individual service validation
            print("  Testing database validation...")
            db_result = await health_validator.validate_database()
            print(f"    Database status: {db_result.status.value}")
            
            print("  Testing Redis validation...")
            redis_result = await health_validator.validate_redis()
            print(f"    Redis status: {redis_result.status.value}")
            
            print("  Testing OpenAI validation...")
            openai_result = await health_validator.validate_openai()
            print(f"    OpenAI status: {openai_result.status.value}")
            
            # Test comprehensive validation
            print("  Running comprehensive validation...")
            report = await health_validator.validate_all_services()
            print(f"    Overall status: {report.overall_status.value}")
            print(f"    Services checked: {len(report.services)}")
            print(f"    Fallback services: {len(report.fallback_services)}")
            
            # Test status summary generation
            print("  Generating status summary...")
            summary = health_validator.generate_status_summary(report)
            print(f"    Summary generated: {summary['overall_status']}")
            
            print("✅ Integration test completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Integration test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main test function."""
    print("🔗 HealthValidator Integration Test")
    print("=" * 40)
    print()
    
    success = asyncio.run(test_with_app_context())
    
    if success:
        print("\n✅ All integration tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Integration tests failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()