#!/usr/bin/env python3
"""Test KYB system functionality."""

import requests
import json
import time

def test_vat_check():
    """Test VAT number checking."""
    print("🔍 Testing VAT number checking...")
    
    # Test German VAT number
    test_cases = [
        {"vat_number": "DE123456789", "country_code": "DE", "expected": "invalid"},
        {"vat_number": "DE811569869", "country_code": "DE", "expected": "valid"},  # Real German VAT
        {"vat_number": "FR12345678901", "country_code": "FR", "expected": "invalid"},
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {test_case['vat_number']} ({test_case['country_code']})")
        
        try:
            response = requests.post('http://localhost:5000/api/v1/secretary/vat-check', 
                json={
                    'vat_number': test_case['vat_number'],
                    'country_code': test_case['country_code']
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    result = data['data']
                    status = result.get('status', 'unknown')
                    print(f"   ✅ Status: {status}")
                    print(f"   ⏱️  Response time: {result.get('response_time_ms', 0)}ms")
                    
                    if status == 'valid':
                        print(f"   🏢 Company: {result.get('name', 'N/A')}")
                        print(f"   📍 Address: {result.get('address', 'N/A')}")
                else:
                    print(f"   ❌ API Error: {data.get('error', {}).get('message', 'Unknown')}")
            else:
                print(f"   ❌ HTTP Error: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("   ⏰ Timeout - VIES API is slow")
        except requests.exceptions.ConnectionError:
            print("   🔌 Connection Error - Server not running?")
        except Exception as e:
            print(f"   💥 Error: {str(e)}")
        
        # Small delay between requests
        time.sleep(1)

def test_api_endpoints():
    """Test API endpoints availability."""
    print("\n🌐 Testing API endpoints...")
    
    endpoints = [
        {"url": "http://localhost:5000/", "name": "Welcome"},
        {"url": "http://localhost:5000/api/v1/health", "name": "Health"},
        {"url": "http://localhost:5000/api/v1/version", "name": "Version"},
        {"url": "http://localhost:5000/api/v1/docs", "name": "Documentation"},
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint['url'], timeout=5)
            if response.status_code == 200:
                print(f"   ✅ {endpoint['name']}: OK")
            else:
                print(f"   ⚠️  {endpoint['name']}: {response.status_code}")
        except Exception as e:
            print(f"   ❌ {endpoint['name']}: {str(e)}")

def test_web_interface():
    """Test web interface pages."""
    print("\n🖥️  Testing web interface...")
    
    pages = [
        {"url": "http://localhost:5000/web", "name": "Main Page"},
        {"url": "http://localhost:5000/web/dashboard", "name": "Dashboard"},
        {"url": "http://localhost:5000/web/secretary-setup", "name": "Secretary Setup"},
        {"url": "http://localhost:5000/web/kyb-dashboard", "name": "KYB Dashboard"},
        {"url": "http://localhost:5000/web/api-tester", "name": "API Tester"},
        {"url": "http://localhost:5000/web/docs", "name": "Documentation"},
    ]
    
    for page in pages:
        try:
            response = requests.get(page['url'], timeout=5)
            if response.status_code == 200:
                print(f"   ✅ {page['name']}: OK")
            else:
                print(f"   ⚠️  {page['name']}: {response.status_code}")
        except Exception as e:
            print(f"   ❌ {page['name']}: {str(e)}")

def main():
    """Run all tests."""
    print("🚀 AI Secretary KYB System Test")
    print("=" * 50)
    
    # Test API endpoints first
    test_api_endpoints()
    
    # Test web interface
    test_web_interface()
    
    # Test KYB functionality
    test_vat_check()
    
    print("\n" + "=" * 50)
    print("✅ Testing completed!")
    print("\n💡 Next steps:")
    print("   1. Check server logs for any errors")
    print("   2. Open http://localhost:5000/web/secretary-setup in browser")
    print("   3. Try the KYB Dashboard at http://localhost:5000/web/kyb-dashboard")

if __name__ == '__main__':
    main()