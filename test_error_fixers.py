#!/usr/bin/env python3
"""Test script for error fixers without full app import."""
import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_database_fixer():
    """Test database fixer."""
    print("🔧 Testing DatabaseFixer...")
    
    try:
        # Import and test database fixer
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
        from app.utils.database_fixer import DatabaseFixer
        
        # Create fixer without app (will use current_app when needed)
        fixer = DatabaseFixer()
        
        # Test table existence check
        print("   Testing table existence check...")
        exists = fixer.check_table_exists('users')
        print(f"   Users table exists: {exists}")
        
        print("✅ DatabaseFixer test completed")
        return True
        
    except Exception as e:
        print(f"❌ DatabaseFixer test failed: {e}")
        return False


def test_context_fixer():
    """Test context fixer."""
    print("🔄 Testing ContextFixer...")
    
    try:
        from app.utils.context_fixer import ContextFixer, with_app_context, safe_app_context_operation
        
        # Create fixer
        fixer = ContextFixer()
        
        # Test decorators
        @safe_app_context_operation
        def test_function():
            return "test"
        
        result = test_function()
        print(f"   Test function result: {result}")
        
        print("✅ ContextFixer test completed")
        return True
        
    except Exception as e:
        print(f"❌ ContextFixer test failed: {e}")
        return False


def test_route_validator():
    """Test route validator."""
    print("🛣️  Testing RouteValidator...")
    
    try:
        from app.utils.route_validator import RouteValidator
        
        # Create validator without app (will use current_app when needed)
        validator = RouteValidator()
        
        print("✅ RouteValidator test completed")
        return True
        
    except Exception as e:
        print(f"❌ RouteValidator test failed: {e}")
        return False


def test_error_fixer():
    """Test main error fixer."""
    print("🚀 Testing ErrorFixer...")
    
    try:
        from app.utils.error_fixer import ErrorFixer
        
        # Create error fixer
        fixer = ErrorFixer()
        
        # Test health check
        print("   Testing quick health check...")
        health = fixer.quick_health_check()
        print(f"   Health status: {health}")
        
        print("✅ ErrorFixer test completed")
        return True
        
    except Exception as e:
        print(f"❌ ErrorFixer test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 Testing error fixing utilities...")
    
    tests = [
        test_database_fixer,
        test_context_fixer,
        test_route_validator,
        test_error_fixer
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print(f"\n📊 Test Results:")
    print(f"   Passed: {passed}")
    print(f"   Failed: {failed}")
    print(f"   Total: {passed + failed}")
    
    if failed == 0:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())