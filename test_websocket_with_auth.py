#!/usr/bin/env python3
"""
Test WebSocket connection with proper authentication.
"""

import requests
import json
import socketio
import time

def test_websocket_with_auth():
    """Test WebSocket connection with valid JWT token."""
    base_url = "http://localhost:5000"
    
    print("🔌 Testing WebSocket with authentication...")
    
    # First, get a valid token
    login_data = {
        "email": "test@example.com",
        "password": "testpassword123"
    }
    
    try:
        # Login to get token
        response = requests.post(
            f"{base_url}/api/v1/auth/login",
            json=login_data,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Login failed: {response.status_code}")
            return False
        
        data = response.json()
        token = data['data']['access_token']
        print(f"✅ Got authentication token: {token[:30]}...")
        
        # Test WebSocket connection with token
        sio = socketio.Client()
        connected = False
        connection_error = None
        
        @sio.event
        def connect():
            nonlocal connected
            connected = True
            print("✅ WebSocket connected successfully!")
        
        @sio.event
        def connect_error(data):
            nonlocal connection_error
            connection_error = data
            print(f"❌ WebSocket connection error: {data}")
        
        @sio.event
        def disconnect():
            print("🔌 WebSocket disconnected")
        
        @sio.event
        def connected(data):
            print(f"✅ WebSocket authentication successful: {data}")
        
        # Connect with authentication
        try:
            sio.connect(base_url, auth={'token': token}, wait_timeout=10)
            time.sleep(2)  # Wait for connection to establish
            
            if connected:
                print("✅ WebSocket connection test passed!")
                
                # Test a simple emit
                sio.emit('ping')
                time.sleep(1)
                
            sio.disconnect()
            
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
            return False
        
        return connected
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_websocket_with_auth()
    if success:
        print("\n🎉 All tests passed! WebSocket authentication is working.")
    else:
        print("\n⚠️  WebSocket authentication needs attention.")