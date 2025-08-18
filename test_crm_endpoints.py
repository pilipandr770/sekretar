#!/usr/bin/env python3
"""Test script to verify CRM endpoints are working."""

import os
import sys
import tempfile
from flask_jwt_extended import create_access_token

# Set environment variables before importing
os.environ['TESTING'] = 'True'
os.environ['DB_SCHEMA'] = ''

from app import create_app
from app import db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.contact import Contact
from app.models.pipeline import Pipeline


def test_crm_endpoints():
    """Test CRM endpoints functionality."""
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp()
    
    flask_app = create_app('testing')
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    flask_app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
    flask_app.config['DB_SCHEMA'] = None
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['HEALTH_CHECK_DATABASE_ENABLED'] = False
    flask_app.config['HEALTH_CHECK_REDIS_ENABLED'] = False
    flask_app.config['TENANT_MIDDLEWARE_ENABLED'] = False
    
    with flask_app.app_context():
        try:
            # Create all tables
            import app.models
            db.create_all()
            
            # Create test tenant
            tenant = Tenant(
                name="Test Tenant",
                domain="test.example.com",
                slug="test-tenant",
                settings={"test": True}
            )
            db.session.add(tenant)
            db.session.commit()
            
            # Create test user
            user = User(
                tenant_id=tenant.id,
                email="test@example.com",
                password_hash="hashed_password",
                first_name="Test",
                last_name="User",
                role="manager",
                is_active=True
            )
            db.session.add(user)
            db.session.commit()
            
            # Refresh user object to ensure it has all attributes
            db.session.refresh(user)
            
            # Create access token manually with user ID
            access_token = create_access_token(
                identity=user.id,
                additional_claims={
                    'tenant_id': user.tenant_id,
                    'role': user.role,
                    'is_active': user.is_active
                }
            )
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Test client
            client = flask_app.test_client()
            
            print("Testing CRM endpoints...")
            
            # Test 1: List contacts (should be empty initially)
            print("1. Testing GET /api/v1/crm/contacts")
            response = client.get('/api/v1/crm/contacts', headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✓ Contacts endpoint working")
            else:
                print(f"   ✗ Contacts endpoint failed: {response.data}")
            
            # Test 2: Create contact
            print("2. Testing POST /api/v1/crm/contacts")
            contact_data = {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "company": "Test Company"
            }
            response = client.post('/api/v1/crm/contacts', headers=headers, json=contact_data)
            print(f"   Status: {response.status_code}")
            if response.status_code == 201:
                print("   ✓ Contact creation working")
                contact_id = response.get_json()['data']['id']
            else:
                print(f"   ✗ Contact creation failed: {response.data}")
                contact_id = None
            
            # Test 3: List pipelines
            print("3. Testing GET /api/v1/crm/pipelines")
            response = client.get('/api/v1/crm/pipelines', headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✓ Pipelines endpoint working")
            else:
                print(f"   ✗ Pipelines endpoint failed: {response.data}")
            
            # Test 4: Create pipeline
            print("4. Testing POST /api/v1/crm/pipelines")
            pipeline_data = {
                "name": "Test Pipeline",
                "description": "A test pipeline"
            }
            response = client.post('/api/v1/crm/pipelines', headers=headers, json=pipeline_data)
            print(f"   Status: {response.status_code}")
            if response.status_code == 201:
                print("   ✓ Pipeline creation working")
                pipeline_id = response.get_json()['data']['id']
            else:
                print(f"   ✗ Pipeline creation failed: {response.data}")
                pipeline_id = None
            
            # Test 5: List leads
            print("5. Testing GET /api/v1/crm/leads")
            response = client.get('/api/v1/crm/leads', headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✓ Leads endpoint working")
            else:
                print(f"   ✗ Leads endpoint failed: {response.data}")
            
            # Test 6: Create lead (if we have contact and pipeline)
            if contact_id and pipeline_id:
                print("6. Testing POST /api/v1/crm/leads")
                lead_data = {
                    "title": "Test Lead",
                    "contact_id": contact_id,
                    "pipeline_id": pipeline_id,
                    "value": 1000.00
                }
                response = client.post('/api/v1/crm/leads', headers=headers, json=lead_data)
                print(f"   Status: {response.status_code}")
                if response.status_code == 201:
                    print("   ✓ Lead creation working")
                    lead_id = response.get_json()['data']['id']
                else:
                    print(f"   ✗ Lead creation failed: {response.data}")
                    lead_id = None
            else:
                print("6. Skipping lead creation (missing contact or pipeline)")
                lead_id = None
            
            # Test 7: List tasks
            print("7. Testing GET /api/v1/crm/tasks")
            response = client.get('/api/v1/crm/tasks', headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✓ Tasks endpoint working")
            else:
                print(f"   ✗ Tasks endpoint failed: {response.data}")
            
            # Test 8: Create task
            print("8. Testing POST /api/v1/crm/tasks")
            task_data = {
                "title": "Test Task",
                "description": "A test task",
                "assigned_to_id": user.id
            }
            if lead_id:
                task_data["lead_id"] = lead_id
            
            response = client.post('/api/v1/crm/tasks', headers=headers, json=task_data)
            print(f"   Status: {response.status_code}")
            if response.status_code == 201:
                print("   ✓ Task creation working")
            else:
                print(f"   ✗ Task creation failed: {response.data}")
            
            # Test 9: List notes
            print("9. Testing GET /api/v1/crm/notes")
            response = client.get('/api/v1/crm/notes', headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✓ Notes endpoint working")
            else:
                print(f"   ✗ Notes endpoint failed: {response.data}")
            
            # Test 10: Create note
            print("10. Testing POST /api/v1/crm/notes")
            note_data = {
                "content": "This is a test note",
                "title": "Test Note"
            }
            if lead_id:
                note_data["lead_id"] = lead_id
            
            response = client.post('/api/v1/crm/notes', headers=headers, json=note_data)
            print(f"   Status: {response.status_code}")
            if response.status_code == 201:
                print("   ✓ Note creation working")
            else:
                print(f"   ✗ Note creation failed: {response.data}")
            
            print("\nCRM endpoints test completed!")
            
        except Exception as e:
            print(f"Error during testing: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            os.close(db_fd)
            os.unlink(db_path)


if __name__ == "__main__":
    test_crm_endpoints()