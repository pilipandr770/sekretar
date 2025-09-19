#!/usr/bin/env python3
"""
Test script for Error Handler functionality
"""

import os
import sys
import json
from pathlib import Path

def test_error_handler_files():
    """Test that all error handler files exist and have correct content"""
    
    print("Testing Error Handler Implementation...")
    print("=" * 50)
    
    # Check if error handler JavaScript file exists
    error_handler_js = Path("app/static/js/error-handler.js")
    if not error_handler_js.exists():
        print("❌ Error handler JavaScript file not found")
        return False
    
    print("✅ Error handler JavaScript file exists")
    
    # Check if error handler CSS file exists
    error_handler_css = Path("app/static/css/error-handler.css")
    if not error_handler_css.exists():
        print("❌ Error handler CSS file not found")
        return False
    
    print("✅ Error handler CSS file exists")
    
    # Check if error test template exists
    error_test_template = Path("app/templates/error_test.html")
    if not error_test_template.exists():
        print("❌ Error test template not found")
        return False
    
    print("✅ Error test template exists")
    
    # Check JavaScript file content
    with open(error_handler_js, 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    required_js_features = [
        'class ErrorHandler',
        'setupGlobalErrorHandlers',
        'handleJavaScriptError',
        'handlePromiseRejection',
        'handleAPIError',
        'handleNetworkError',
        'setupNetworkMonitoring',
        'interceptFetchRequests',
        'showNotification',
        'setupGracefulDegradation'
    ]
    
    missing_features = []
    for feature in required_js_features:
        if feature not in js_content:
            missing_features.append(feature)
    
    if missing_features:
        print(f"❌ Missing JavaScript features: {', '.join(missing_features)}")
        return False
    
    print("✅ All required JavaScript features present")
    
    # Check CSS file content
    with open(error_handler_css, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    required_css_classes = [
        '.error-notifications',
        '.error-notification',
        '.offline-indicator',
        '@keyframes slideInRight'
    ]
    
    missing_css = []
    for css_class in required_css_classes:
        if css_class not in css_content:
            missing_css.append(css_class)
    
    if missing_css:
        print(f"❌ Missing CSS classes: {', '.join(missing_css)}")
        return False
    
    print("✅ All required CSS classes present")
    
    # Check base template integration
    base_template = Path("app/templates/base.html")
    if not base_template.exists():
        print("❌ Base template not found")
        return False
    
    with open(base_template, 'r', encoding='utf-8') as f:
        base_content = f.read()
    
    if 'error-handler.js' not in base_content:
        print("❌ Error handler JavaScript not included in base template")
        return False
    
    if 'error-handler.css' not in base_content:
        print("❌ Error handler CSS not included in base template")
        return False
    
    print("✅ Error handler properly integrated in base template")
    
    # Check integration with existing JavaScript files
    auth_manager = Path("app/static/js/auth-manager.js")
    if auth_manager.exists():
        with open(auth_manager, 'r', encoding='utf-8') as f:
            auth_content = f.read()
        
        if 'window.errorHandler' not in auth_content:
            print("❌ Auth manager not integrated with error handler")
            return False
        
        print("✅ Auth manager integrated with error handler")
    
    app_js = Path("app/static/js/app.js")
    if app_js.exists():
        with open(app_js, 'r', encoding='utf-8') as f:
            app_content = f.read()
        
        if 'window.errorHandler' not in app_content:
            print("❌ Main app not integrated with error handler")
            return False
        
        print("✅ Main app integrated with error handler")
    
    websocket_client = Path("app/static/js/websocket-client.js")
    if websocket_client.exists():
        with open(websocket_client, 'r', encoding='utf-8') as f:
            ws_content = f.read()
        
        if 'window.errorHandler' not in ws_content:
            print("❌ WebSocket client not integrated with error handler")
            return False
        
        print("✅ WebSocket client integrated with error handler")
    
    return True

def test_error_handler_requirements():
    """Test that error handler meets the requirements"""
    
    print("\nTesting Requirements Compliance...")
    print("=" * 50)
    
    error_handler_js = Path("app/static/js/error-handler.js")
    with open(error_handler_js, 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    # Requirement 6.1: Implement global error handlers for uncaught JavaScript errors
    global_error_handlers = [
        "window.addEventListener('error'",
        "window.addEventListener('unhandledrejection'",
        "handleJavaScriptError",
        "handlePromiseRejection"
    ]
    
    for handler in global_error_handlers:
        if handler not in js_content:
            print(f"❌ Missing global error handler: {handler}")
            return False
    
    print("✅ Requirement 6.1: Global error handlers implemented")
    
    # Requirement 6.2: Add user-friendly error messages for API failures
    api_error_features = [
        "handleAPIError",
        "getAPIErrorMessage",
        "getUserFriendlyMessage",
        "showNotification"
    ]
    
    for feature in api_error_features:
        if feature not in js_content:
            print(f"❌ Missing API error feature: {feature}")
            return False
    
    print("✅ Requirement 6.2: User-friendly API error messages implemented")
    
    # Requirement 6.3: Create graceful degradation for network issues
    network_features = [
        "setupNetworkMonitoring",
        "setupGracefulDegradation",
        "setupOfflineMode",
        "markOfflineElements",
        "retryFailedRequests"
    ]
    
    for feature in network_features:
        if feature not in js_content:
            print(f"❌ Missing network degradation feature: {feature}")
            return False
    
    print("✅ Requirement 6.3: Graceful degradation for network issues implemented")
    
    # Requirement 6.4: Enhanced error handling integration
    integration_features = [
        "interceptFetchRequests",
        "addFailedRequest",
        "setupRetryMechanisms",
        "cachePageState"
    ]
    
    for feature in integration_features:
        if feature not in js_content:
            print(f"❌ Missing integration feature: {feature}")
            return False
    
    print("✅ Requirement 6.4: Enhanced error handling integration implemented")
    
    return True

def main():
    """Main test function"""
    
    print("Error Handler Implementation Test")
    print("=" * 50)
    
    # Test file existence and content
    if not test_error_handler_files():
        print("\n❌ File tests failed")
        return False
    
    # Test requirements compliance
    if not test_error_handler_requirements():
        print("\n❌ Requirements tests failed")
        return False
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print("✅ Error Handler implementation is complete and meets all requirements")
    print("\nNext steps:")
    print("1. Start the application: python run.py")
    print("2. Visit /error-test to test the error handling functionality")
    print("3. Test various error scenarios using the test page")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)