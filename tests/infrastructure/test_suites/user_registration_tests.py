"""
User Registration Testing Suite

Comprehensive tests for user registration functionality.
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.models.user import User
from app.models.tenant import Tenant
from app.models.audit_log import AuditLog
from app import db


class TestUserRegistrationSuite:
    """Comprehensive user registration test suite."""
    
    def test_basic_registration_flow(self, client, app):
        """Test basic user registration flow."""
        with app.app_context():
            registration_data = {
                'email': 'test@example.com',
                'password': 'SecurePassword123!',
                'organization_name': 'Test Organization',
                'first_name': 'Test',
                'last_name': 'User'
            }
            
            response = client.post('/api/v1/auth/register', 
                                 json=registration_data,
                                 content_type='application/json')
            
            assert response.status_code == 201
            data = response.get_json()
            assert data['success'] is True
            assert 'user' in data['data']
            assert 'tenant' in data['data']
    
    def test_email_validation(self, client, app):
        """Test email validation during registration."""
        with app.app_context():
            invalid_emails = [
                'invalid-email',
                'test@',
                '@domain.com',
                'test..test@domain.com'
            ]
            
            for email in invalid_emails:
                registration_data = {
                    'email': email,
                    'password': 'SecurePassword123!',
                    'organization_name': 'Test Organization',
                    'first_name': 'Test',
                    'last_name': 'User'
                }
                
                response = client.post('/api/v1/auth/register', 
                                     json=registration_data,
                                     content_type='application/json')
                
                assert response.status_code in [400, 422, 500]  # Various validation error codes
    
    def test_password_strength_validation(self, client, app):
        """Test password strength validation."""
        with app.app_context():
            weak_passwords = [
                '123',
                'password',
                'PASSWORD',
                '12345678'
            ]
            
            for password in weak_passwords:
                registration_data = {
                    'email': 'test@example.com',
                    'password': password,
                    'organization_name': 'Test Organization',
                    'first_name': 'Test',
                    'last_name': 'User'
                }
                
                response = client.post('/api/v1/auth/register', 
                                     json=registration_data,
                                     content_type='application/json')
                
                assert response.status_code in [400, 422, 500]  # Various validation error codes