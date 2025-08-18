#!/usr/bin/env python3
"""
Test JWT token format and validation.
"""

import requests
import json

def test_jwt_format():
    """Test JWT token creation and validation."""
    base_url = "http://localhost:5000"
    
    print("🔐 Testing JWT token format...")
    
    # Test data for registration
    test_user = {
        "email": "test@example.com",
        "password": "testpassword123",
        "organization_name": "Test Organization",
        "first_name": "Test",
        "last_name": "User"
    }
    
    try:
        # Try to register a test user
        print("📝 Attempting user registration...")
        response = requests.post(
            f"{base_url}/api/v1/auth/register",
            json=test_user,
            timeout=10
        )
        
        if response.status_code == 201:
            data = response.json()
            print("✅ Registration successful")
            
            # Check token format
            if 'data' in data and 'access_token' in data['data']:
                token = data['data']['access_token']
                print(f"✅ Access token received: {token[:50]}...")
                
                # Test the token with /me endpoint
                headers = {'Authorization': f'Bearer {token}'}
                me_response = requests.get(
                    f"{base_url}/api/v1/auth/me",
                    headers=headers,
                    timeout=5
                )
                
                if me_response.status_code == 200:
                    print("✅ Token validation successful")
                    user_data = me_response.json()
                    print(f"   User ID: {user_data['data']['user']['id']}")
                    print(f"   Tenant ID: {user_data['data']['tenant']['id']}")
                else:
                    print(f"❌ Token validation failed: {me_response.status_code}")
                    print(f"   Response: {me_response.text}")
            else:
                print("❌ No access token in response")
                
        elif response.status_code == 409:
            print("ℹ️  User already exists, trying login instead...")
            
            # Try login
            login_data = {
                "email": test_user["email"],
                "password": test_user["password"]
            }
            
            login_response = requests.post(
                f"{base_url}/api/v1/auth/login",
                json=login_data,
                timeout=10
            )
            
            if login_response.status_code == 200:
                data = login_response.json()
                print("✅ Login successful")
                
                if 'data' in data and 'access_token' in data['data']:
                    token = data['data']['access_token']
                    print(f"✅ Access token received: {token[:50]}...")
                    
                    # Test the token
                    headers = {'Authorization': f'Bearer {token}'}
                    me_response = requests.get(
                        f"{base_url}/api/v1/auth/me",
                        headers=headers,
                        timeout=5
                    )
                    
                    if me_response.status_code == 200:
                        print("✅ Token validation successful")
                        user_data = me_response.json()
                        print(f"   User ID: {user_data['data']['user']['id']}")
                        print(f"   Tenant ID: {user_data['data']['tenant']['id']}")
                    else:
                        print(f"❌ Token validation failed: {me_response.status_code}")
                        print(f"   Response: {me_response.text}")
            else:
                print(f"❌ Login failed: {login_response.status_code}")
                print(f"   Response: {login_response.text}")
        else:
            print(f"❌ Registration failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
    
    print("\n📋 JWT Format Test Complete")

if __name__ == "__main__":
    test_jwt_format()