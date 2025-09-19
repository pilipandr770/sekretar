#!/usr/bin/env python3
"""
Test WebSocket connection to identify 400 errors.
"""
import requests
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_socketio_endpoint():
    """Test if the Socket.IO endpoint is accessible."""
    base_url = "http://localhost:5000"
    
    # Test Socket.IO polling endpoint
    socketio_url = f"{base_url}/socket.io/"
    
    print("🔍 Testing Socket.IO endpoint accessibility...")
    print(f"Testing URL: {socketio_url}")
    
    try:
        # Test basic Socket.IO endpoint
        params = {
            'EIO': '4',  # Engine.IO version 4
            'transport': 'polling',
            't': 'test'
        }
        
        response = requests.get(socketio_url, params=params, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("✅ Socket.IO endpoint is accessible")
            return True
        elif response.status_code == 400:
            print("❌ Socket.IO endpoint returns 400 Bad Request")
            print("This indicates a configuration issue with the WebSocket server")
            return False
        elif response.status_code == 404:
            print("❌ Socket.IO endpoint not found (404)")
            print("WebSocket server may not be properly initialized")
            return False
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server - is the application running?")
        return False
    except requests.exceptions.Timeout:
        print("❌ Connection timeout")
        return False
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        return False

def test_app_health():
    """Test if the main application is running."""
    base_url = "http://localhost:5000"
    
    print("🔍 Testing main application health...")
    
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        
        if response.status_code == 200:
            print("✅ Main application is healthy")
            return True
        else:
            print(f"⚠️  Health check returned: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to main application")
        return False
    except Exception as e:
        print(f"❌ Error testing health: {e}")
        return False

def main():
    """Run WebSocket connection tests."""
    print("🧪 WebSocket Connection Test")
    print("=" * 40)
    
    # Test main app first
    app_healthy = test_app_health()
    print()
    
    # Test Socket.IO endpoint
    socketio_working = test_socketio_endpoint()
    print()
    
    # Summary
    print("📊 Test Summary:")
    print(f"   Main App: {'✅ Healthy' if app_healthy else '❌ Not responding'}")
    print(f"   Socket.IO: {'✅ Working' if socketio_working else '❌ Not working'}")
    
    if not app_healthy:
        print("\n💡 Recommendations:")
        print("   1. Start the application with: python run.py")
        print("   2. Check if port 5000 is available")
        
    elif not socketio_working:
        print("\n💡 Recommendations:")
        print("   1. Check WebSocket manager initialization in logs")
        print("   2. Verify Flask-SocketIO is properly installed")
        print("   3. Check CORS configuration for WebSocket")
        print("   4. Review server startup logs for WebSocket errors")
    
    return socketio_working

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)