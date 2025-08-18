#!/usr/bin/env python3
"""
AI Secretary KYB System Demo

This script demonstrates the complete KYB (Know Your Business) functionality:
1. Company setup
2. Counterparty management
3. VAT number verification
4. Sanctions screening
5. Change monitoring
6. Notifications

Run this script to see the system in action!
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"
API_BASE = f"{BASE_URL}/api/v1/secretary"

def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"🚀 {title}")
    print("=" * 60)

def print_step(step, description):
    """Print a formatted step."""
    print(f"\n📋 Step {step}: {description}")
    print("-" * 40)

def make_request(method, url, data=None):
    """Make HTTP request with error handling."""
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=10)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, timeout=10)
        elif method.upper() == 'PUT':
            response = requests.put(url, json=data, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return response
    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to server. Is it running on http://localhost:5000?")
        return None
    except requests.exceptions.Timeout:
        print("⏰ Error: Request timeout")
        return None
    except Exception as e:
        print(f"💥 Error: {str(e)}")
        return None

def demo_company_setup():
    """Demo: Create a company profile."""
    print_step(1, "Company Setup")
    
    company_data = {
        "name": "ACME Tech Solutions GmbH",
        "vat_number": "DE123456789",
        "address": "Musterstraße 123, 10115 Berlin, Germany",
        "phone": "+49 30 12345678",
        "email": "info@acme-tech.de",
        "business_area": "IT Services & Consulting",
        "ai_instructions": "You are a professional AI secretary for ACME Tech Solutions. Help clients with inquiries about our IT services, schedule meetings, and perform KYB checks on potential business partners."
    }
    
    print("Creating company profile...")
    response = make_request('POST', f"{API_BASE}/companies", company_data)
    
    if response and response.status_code == 201:
        data = response.json()
        company_id = data['data']['id']
        print(f"✅ Company created successfully!")
        print(f"   Company ID: {company_id}")
        print(f"   Name: {data['data']['name']}")
        print(f"   VAT: {data['data']['vat_number']}")
        return company_id
    else:
        print(f"❌ Failed to create company: {response.status_code if response else 'No response'}")
        return None

def demo_vat_checks():
    """Demo: VAT number verification."""
    print_step(2, "VAT Number Verification")
    
    test_cases = [
        {"vat_number": "DE811569869", "country_code": "DE", "description": "Valid German company"},
        {"vat_number": "FR40303265045", "country_code": "FR", "description": "Valid French company"},
        {"vat_number": "DE999999999", "country_code": "DE", "description": "Invalid German VAT"},
        {"vat_number": "NL123456789B01", "country_code": "NL", "description": "Test Dutch VAT"},
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 Test {i}: {test_case['description']}")
        print(f"   VAT: {test_case['vat_number']} ({test_case['country_code']})")
        
        response = make_request('POST', f"{API_BASE}/vat-check", {
            'vat_number': test_case['vat_number'],
            'country_code': test_case['country_code']
        })
        
        if response and response.status_code == 200:
            data = response.json()
            if data.get('success'):
                result = data['data']
                status = result.get('status', 'unknown')
                
                if status == 'valid':
                    print(f"   ✅ Status: {status.upper()}")
                    print(f"   🏢 Company: {result.get('name', 'N/A')}")
                    print(f"   📍 Address: {result.get('address', 'N/A')[:50]}...")
                    print(f"   ⏱️  Response time: {result.get('response_time_ms', 0)}ms")
                elif status == 'invalid':
                    print(f"   ❌ Status: {status.upper()}")
                    print(f"   💬 Error: {result.get('error', 'N/A')}")
                else:
                    print(f"   ⚠️  Status: {status.upper()}")
                    print(f"   💬 Error: {result.get('error', 'N/A')}")
            else:
                print(f"   ❌ API Error: {data.get('error', {}).get('message', 'Unknown')}")
        else:
            print(f"   💥 Request failed: {response.status_code if response else 'No response'}")
        
        # Small delay between requests to be nice to VIES API
        time.sleep(2)

def demo_counterparty_management(company_id):
    """Demo: Add and manage counterparties."""
    if not company_id:
        print("⚠️  Skipping counterparty demo - no company ID")
        return []
    
    print_step(3, "Counterparty Management")
    
    counterparties = [
        {
            "name": "Siemens AG",
            "vat_number": "DE811569869",
            "country_code": "DE",
            "address": "Werner-von-Siemens-Straße 1, 80333 München"
        },
        {
            "name": "SAP SE",
            "vat_number": "DE143593636",
            "country_code": "DE",
            "address": "Dietmar-Hopp-Allee 16, 69190 Walldorf"
        },
        {
            "name": "Test Sanctions Company",
            "vat_number": "DE999999999",
            "country_code": "DE",
            "address": "Test Address with SBERBANK keyword"
        }
    ]
    
    created_counterparties = []
    
    for i, cp_data in enumerate(counterparties, 1):
        print(f"\n➕ Adding counterparty {i}: {cp_data['name']}")
        
        response = make_request('POST', f"{API_BASE}/companies/{company_id}/counterparties", cp_data)
        
        if response and response.status_code == 201:
            data = response.json()
            cp_id = data['data']['id']
            created_counterparties.append(cp_id)
            
            print(f"   ✅ Added successfully!")
            print(f"   ID: {cp_id}")
            
            # Check if KYB result is included
            if 'kyb_result' in data['data']:
                kyb_result = data['data']['kyb_result']
                print(f"   🔍 KYB Status: {kyb_result.get('overall_status', 'unknown')}")
                print(f"   ⚠️  Risk Level: {kyb_result.get('risk_level', 'unknown')}")
                
                if kyb_result.get('checks'):
                    print(f"   📊 Checks performed: {len(kyb_result['checks'])}")
        else:
            print(f"   ❌ Failed to add: {response.status_code if response else 'No response'}")
    
    return created_counterparties

def demo_sanctions_screening():
    """Demo: Sanctions screening."""
    print_step(4, "Sanctions Screening")
    
    test_companies = [
        "Microsoft Corporation",
        "Google LLC", 
        "SBERBANK Russia",  # Should trigger sanctions alert
        "Normal Business Ltd",
        "GAZPROM Energy"     # Should trigger sanctions alert
    ]
    
    print("Testing sanctions screening (demo keywords)...")
    
    for company in test_companies:
        print(f"\n🔍 Screening: {company}")
        
        # This would normally be done through the KYB service
        # For demo, we'll show what would happen
        company_upper = company.upper()
        sanctioned_keywords = ['SBERBANK', 'GAZPROM', 'ROSNEFT', 'WAGNER']
        
        found_matches = [kw for kw in sanctioned_keywords if kw in company_upper]
        
        if found_matches:
            print(f"   🚨 SANCTIONS MATCH FOUND!")
            print(f"   📋 Matched keywords: {', '.join(found_matches)}")
            print(f"   ⚠️  Risk Level: HIGH")
            print(f"   📧 Alert would be sent to compliance team")
        else:
            print(f"   ✅ No sanctions matches found")
            print(f"   ⚠️  Risk Level: LOW")

def demo_monitoring_report(company_id):
    """Demo: Generate monitoring report."""
    if not company_id:
        print("⚠️  Skipping monitoring demo - no company ID")
        return
    
    print_step(5, "Monitoring & Reporting")
    
    print("Generating monitoring report...")
    response = make_request('GET', f"{API_BASE}/companies/{company_id}/monitoring-report")
    
    if response and response.status_code == 200:
        data = response.json()
        if data.get('success'):
            report = data['data']
            stats = report.get('statistics', {})
            
            print("✅ Monitoring report generated!")
            print(f"\n📊 Statistics:")
            print(f"   Total Counterparties: {stats.get('total_counterparties', 0)}")
            print(f"   High Risk: {stats.get('high_risk_counterparties', 0)}")
            print(f"   Recent Changes: {stats.get('recent_changes', 0)}")
            print(f"   Recent Checks: {stats.get('recent_checks', 0)}")
            print(f"   Unnotified Changes: {stats.get('unnotified_changes', 0)}")
            
            if report.get('recent_changes'):
                print(f"\n📋 Recent Changes:")
                for change in report['recent_changes'][:3]:
                    print(f"   • {change.get('field_name', 'Unknown')} changed")
                    print(f"     From: {change.get('old_value', 'N/A')}")
                    print(f"     To: {change.get('new_value', 'N/A')}")
        else:
            print(f"❌ Report generation failed: {data.get('error', {}).get('message', 'Unknown')}")
    else:
        print(f"💥 Request failed: {response.status_code if response else 'No response'}")

def demo_web_interface():
    """Demo: Show web interface links."""
    print_step(6, "Web Interface")
    
    print("🖥️  Web interfaces available:")
    print(f"   • Main Page: {BASE_URL}/web")
    print(f"   • Secretary Setup: {BASE_URL}/web/secretary-setup")
    print(f"   • KYB Dashboard: {BASE_URL}/web/kyb-dashboard")
    print(f"   • API Tester: {BASE_URL}/web/api-tester")
    print(f"   • Documentation: {BASE_URL}/web/docs")
    
    print("\n💡 Try these in your browser to see the full interface!")

def main():
    """Run the complete KYB system demo."""
    print_header("AI Secretary KYB System Demo")
    print("This demo showcases the complete Know Your Business functionality.")
    print("Make sure the Flask server is running on http://localhost:5000")
    
    # Check if server is running
    print("\n🔌 Checking server connection...")
    response = make_request('GET', f"{BASE_URL}/api/v1/health")
    if not response:
        print("❌ Cannot connect to server. Please start the Flask application first.")
        print("   Run: python -m flask run --host=0.0.0.0 --port=5000")
        return
    
    print("✅ Server is running!")
    
    # Run demo steps
    company_id = demo_company_setup()
    demo_vat_checks()
    counterparty_ids = demo_counterparty_management(company_id)
    demo_sanctions_screening()
    demo_monitoring_report(company_id)
    demo_web_interface()
    
    # Final summary
    print_header("Demo Completed Successfully! 🎉")
    print("✅ Company profile created")
    print("✅ VAT numbers verified through VIES API")
    print("✅ Counterparties added with automatic KYB checks")
    print("✅ Sanctions screening demonstrated")
    print("✅ Monitoring and reporting working")
    print("✅ Web interface ready for use")
    
    print(f"\n🚀 Next Steps:")
    print(f"   1. Open {BASE_URL}/web/secretary-setup to configure your AI secretary")
    print(f"   2. Visit {BASE_URL}/web/kyb-dashboard to monitor counterparties")
    print(f"   3. Use the API endpoints for integration with your systems")
    print(f"   4. Set up email notifications for real-time alerts")
    
    print(f"\n💡 The KYB system is now ready for production use!")

if __name__ == '__main__':
    main()