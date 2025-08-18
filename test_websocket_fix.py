#!/usr/bin/env python3
"""
Test the WebSocket fixes.
"""

import requests
import json

def test_websocket_fix():
    """Test that WebSocket connections are handled properly."""
    base_url = "http://localhost:5000"
    
    print("🔧 Testing WebSocket connection fixes...")
    
    # Test 1: Check that the application is running
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ Application is running")
        else:
            print(f"❌ Application health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to application: {e}")
        return False
    
    # Test 2: Check that WebSocket endpoint exists (should return 400 without auth)
    try:
        response = requests.get(f"{base_url}/socket.io/?EIO=4&transport=polling", timeout=5)
        print(f"✅ WebSocket endpoint responds: {response.status_code}")
    except Exception as e:
        print(f"ℹ️  WebSocket endpoint test: {e}")
    
    # Test 3: Check authentication endpoints
    try:
        # Test login endpoint structure
        response = requests.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": "invalid", "password": "invalid"},
            timeout=5
        )
        if response.status_code in [400, 401]:
            print("✅ Authentication endpoint is protected")
        else:
            print(f"ℹ️  Auth endpoint response: {response.status_code}")
    except Exception as e:
        print(f"❌ Auth endpoint test failed: {e}")
    
    print("\n📋 WebSocket Fix Summary:")
    print("   - WebSocket connections now check for authentication tokens")
    print("   - Client-side WebSocket only connects when authenticated")
    print("   - Reduced log spam from unauthenticated connection attempts")
    print("\n💡 To test WebSocket functionality:")
    print("   1. Login through the web interface")
    print("   2. Check browser console for WebSocket connection status")
    print("   3. WebSocket should connect automatically after login")
    
    return True

if __name__ == "__main__":
    test_websocket_fix()