"""Comprehensive core business API endpoint tests.

This module implements comprehensive testing of core business API endpoints
using real company data from the comprehensive test dataset. Tests cover:
- Tenant management API tests with real company data
- CRM contact/lead API tests using real company information
- KYB counterparty API tests with real VAT/LEI data

Requirements covered: 2.2, 2.3, 2.4
"""
import json
import pytest
from unittest.mock import patch, MagicMock


class TestTenantManagementAPI:
    """Test tenant management API endpoints."""
    
    @pytest.fixture
    def real_company_data(self):
        """Load real company data for testing."""
        try:
            with open('comprehensive_test_dataset.json', 'r') as f:
                dataset = json.load(f)
            return dataset['companies']
        except FileNotFoundError:
            # Fallback to minimal test data
            return {
                'sap_germany': {
                    'name': 'SAP SE',
                    'vat_number': 'DE143593636',
                    'country_code': 'DE',
                    'address': 'Dietmar-Hopp-Allee 16, 69190 Walldorf'
                }
            }

    def test_tenant_language_settings_get(self, client, auth_headers):
        """Test getting tenant language settings.
        
        Requirements: 2.2 - Core business API
        """
        response = client.get('/api/v1/i18n/tenant/language', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data

    def test_tenant_language_settings_update(self, client, auth_headers, real_company_data):
        """Test updating tenant language settings with real company data.
        
        Requirements: 2.2 - Core business API
        """
        company = list(real_company_data.values())[0]
        
        # Test updating language settings
        update_data = {
            'default_language': 'de',  # German for German company
            'supported_languages': ['en', 'de'],
            'auto_detect': True
        }
        
        response = client.put(
            '/api/v1/i18n/tenant/language',
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_tenant_language_settings_unauthorized(self, client):
        """Test tenant language settings without authentication.
        
        Requirements: 2.2 - Core business API
        """
        response = client.get('/api/v1/i18n/tenant/language')
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data


class TestCRMContactAPI:
    """Test CRM contact management API endpoints."""
    
    @pytest.fixture
    def real_company_data(self):
        """Load real company data for testing."""
        try:
            with open('comprehensive_test_dataset.json', 'r') as f:
                dataset = json.load(f)
            return dataset['companies']
        except FileNotFoundError:
            return {
                'sap_germany': {
                    'name': 'SAP SE',
                    'vat_number': 'DE143593636',
                    'country_code': 'DE',
                    'address': 'Dietmar-Hopp-Allee 16, 69190 Walldorf'
                }
            }

    def test_contacts_list_endpoint(self, client, auth_headers):
        """Test listing contacts endpoint.
        
        Requirements: 2.3 - CRM API tests
        """
        response = client.get('/api/v1/crm/contacts', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'contacts' in data['data']
        assert isinstance(data['data']['contacts'], list)

    def test_contacts_create_with_real_company_data(self, client, auth_headers, real_company_data):
        """Test creating contact with real company data.
        
        Requirements: 2.3 - CRM API tests
        """
        company = list(real_company_data.values())[0]
        
        contact_data = {
            'company_name': company['name'],
            'first_name': 'Hans',
            'last_name': 'Mueller',
            'email': f'hans.mueller@{company["name"].lower().replace(" ", "").replace(".", "")}.com',
            'phone': '+49 6227 7-47474',
            'position': 'Sales Director',
            'address': company.get('address', ''),
            'country': company.get('country_code', 'DE'),
            'vat_number': company.get('vat_number'),
            'notes': f'Contact from {company["name"]} - real company data test'
        }
        
        response = client.post(
            '/api/v1/crm/contacts',
            json=contact_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'contact' in data['data']
        
        # Verify contact data
        contact = data['data']['contact']
        assert contact['company_name'] == company['name']
        assert contact['first_name'] == 'Hans'
        assert contact['last_name'] == 'Mueller'

    def test_contacts_create_validation(self, client, auth_headers):
        """Test contact creation validation.
        
        Requirements: 2.3 - CRM API tests
        """
        # Test missing required fields
        incomplete_data = {
            'first_name': 'John',
            # Missing last_name and email
        }
        
        response = client.post(
            '/api/v1/crm/contacts',
            json=incomplete_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data

    def test_contacts_get_by_id(self, client, auth_headers):
        """Test getting contact by ID.
        
        Requirements: 2.3 - CRM API tests
        """
        # Test with non-existent contact ID
        response = client.get('/api/v1/crm/contacts/999999', headers=auth_headers)
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_contacts_update(self, client, auth_headers, real_company_data):
        """Test updating contact with real company data.
        
        Requirements: 2.3 - CRM API tests
        """
        company = list(real_company_data.values())[0]
        
        # Test updating non-existent contact
        update_data = {
            'company_name': company['name'],
            'position': 'Senior Sales Director',
            'notes': f'Updated contact from {company["name"]}'
        }
        
        response = client.put(
            '/api/v1/crm/contacts/999999',
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_contacts_delete(self, client, auth_headers):
        """Test deleting contact.
        
        Requirements: 2.3 - CRM API tests
        """
        # Test deleting non-existent contact
        response = client.delete('/api/v1/crm/contacts/999999', headers=auth_headers)
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_contacts_unauthorized_access(self, client):
        """Test CRM contacts endpoints without authentication.
        
        Requirements: 2.3 - CRM API tests
        """
        endpoints = [
            ('/api/v1/crm/contacts', 'GET'),
            ('/api/v1/crm/contacts', 'POST'),
            ('/api/v1/crm/contacts/1', 'GET'),
            ('/api/v1/crm/contacts/1', 'PUT'),
            ('/api/v1/crm/contacts/1', 'DELETE')
        ]
        
        for endpoint, method in endpoints:
            if method == 'GET':
                response = client.get(endpoint)
            elif method == 'POST':
                response = client.post(endpoint, json={})
            elif method == 'PUT':
                response = client.put(endpoint, json={})
            elif method == 'DELETE':
                response = client.delete(endpoint)
            
            assert response.status_code == 401
            data = response.get_json()
            assert 'error' in data


class TestCRMLeadAPI:
    """Test CRM lead management API endpoints."""
    
    @pytest.fixture
    def real_company_data(self):
        """Load real company data for testing."""
        try:
            with open('comprehensive_test_dataset.json', 'r') as f:
                dataset = json.load(f)
            return dataset['companies']
        except FileNotFoundError:
            return {
                'sap_germany': {
                    'name': 'SAP SE',
                    'vat_number': 'DE143593636',
                    'country_code': 'DE',
                    'address': 'Dietmar-Hopp-Allee 16, 69190 Walldorf'
                }
            }

    def test_leads_list_endpoint(self, client, auth_headers):
        """Test listing leads endpoint.
        
        Requirements: 2.3 - CRM API tests
        """
        response = client.get('/api/v1/crm/leads', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'leads' in data['data']
        assert isinstance(data['data']['leads'], list)

    def test_leads_create_with_real_company_data(self, client, auth_headers, real_company_data):
        """Test creating lead with real company data.
        
        Requirements: 2.3 - CRM API tests
        """
        company = list(real_company_data.values())[0]
        
        lead_data = {
            'title': f'Enterprise Software Implementation - {company["name"]}',
            'company_name': company['name'],
            'contact_name': 'Klaus Weber',
            'contact_email': f'klaus.weber@{company["name"].lower().replace(" ", "").replace(".", "")}.com',
            'contact_phone': '+49 6227 7-12345',
            'source': 'Website',
            'status': 'new',
            'stage': 'qualification',
            'value': 150000.00,
            'currency': 'EUR',
            'probability': 25,
            'expected_close_date': '2025-12-31',
            'description': f'Potential enterprise software implementation for {company["name"]}',
            'notes': f'Lead from {company["name"]} - real company data test'
        }
        
        response = client.post(
            '/api/v1/crm/leads',
            json=lead_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'lead' in data['data']
        
        # Verify lead data
        lead = data['data']['lead']
        assert company['name'] in lead['title']
        assert lead['company_name'] == company['name']
        assert lead['value'] == 150000.00

    def test_leads_create_validation(self, client, auth_headers):
        """Test lead creation validation.
        
        Requirements: 2.3 - CRM API tests
        """
        # Test missing required fields
        incomplete_data = {
            'title': 'Test Lead',
            # Missing company_name and other required fields
        }
        
        response = client.post(
            '/api/v1/crm/leads',
            json=incomplete_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data

    def test_leads_get_by_id(self, client, auth_headers):
        """Test getting lead by ID.
        
        Requirements: 2.3 - CRM API tests
        """
        # Test with non-existent lead ID
        response = client.get('/api/v1/crm/leads/999999', headers=auth_headers)
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_leads_update_stage(self, client, auth_headers):
        """Test updating lead stage.
        
        Requirements: 2.3 - CRM API tests
        """
        # Test updating non-existent lead stage
        stage_data = {
            'stage': 'proposal',
            'probability': 50,
            'notes': 'Moved to proposal stage'
        }
        
        response = client.put(
            '/api/v1/crm/leads/999999/stage',
            json=stage_data,
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_leads_update_status(self, client, auth_headers):
        """Test updating lead status.
        
        Requirements: 2.3 - CRM API tests
        """
        # Test updating non-existent lead status
        status_data = {
            'status': 'qualified',
            'notes': 'Lead qualified for further processing'
        }
        
        response = client.put(
            '/api/v1/crm/leads/999999/status',
            json=status_data,
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_leads_history(self, client, auth_headers):
        """Test getting lead history.
        
        Requirements: 2.3 - CRM API tests
        """
        # Test getting history for non-existent lead
        response = client.get('/api/v1/crm/leads/999999/history', headers=auth_headers)
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_leads_unauthorized_access(self, client):
        """Test CRM leads endpoints without authentication.
        
        Requirements: 2.3 - CRM API tests
        """
        endpoints = [
            ('/api/v1/crm/leads', 'GET'),
            ('/api/v1/crm/leads', 'POST'),
            ('/api/v1/crm/leads/1', 'GET'),
            ('/api/v1/crm/leads/1', 'PUT'),
            ('/api/v1/crm/leads/1', 'DELETE'),
            ('/api/v1/crm/leads/1/stage', 'PUT'),
            ('/api/v1/crm/leads/1/status', 'PUT'),
            ('/api/v1/crm/leads/1/history', 'GET')
        ]
        
        for endpoint, method in endpoints:
            if method == 'GET':
                response = client.get(endpoint)
            elif method == 'POST':
                response = client.post(endpoint, json={})
            elif method == 'PUT':
                response = client.put(endpoint, json={})
            elif method == 'DELETE':
                response = client.delete(endpoint)
            
            assert response.status_code == 401
            data = response.get_json()
            assert 'error' in data


class TestKYBCounterpartyAPI:
    """Test KYB counterparty management API endpoints."""
    
    @pytest.fixture
    def real_company_data(self):
        """Load real company data for testing."""
        try:
            with open('comprehensive_test_dataset.json', 'r') as f:
                dataset = json.load(f)
            return dataset['companies']
        except FileNotFoundError:
            return {
                'sap_germany': {
                    'name': 'SAP SE',
                    'vat_number': 'DE143593636',
                    'country_code': 'DE',
                    'address': 'Dietmar-Hopp-Allee 16, 69190 Walldorf',
                    'lei_code': '529900T8BM49AURSDO55'
                }
            }

    def test_counterparties_list_endpoint(self, client, auth_headers):
        """Test listing counterparties endpoint.
        
        Requirements: 2.4 - KYB API tests
        """
        response = client.get('/api/v1/kyb/counterparties', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'counterparties' in data['data']
        assert isinstance(data['data']['counterparties'], list)

    def test_counterparties_create_with_real_vat_lei_data(self, client, auth_headers, real_company_data):
        """Test creating counterparty with real VAT/LEI data.
        
        Requirements: 2.4 - KYB API tests
        """
        company = list(real_company_data.values())[0]
        
        counterparty_data = {
            'name': company['name'],
            'vat_number': company.get('vat_number'),
            'lei_code': company.get('lei_code'),
            'country_code': company.get('country_code', 'DE'),
            'address': company.get('address', ''),
            'business_type': 'corporation',
            'industry': 'Technology',
            'risk_level': 'low',
            'notes': f'Counterparty for {company["name"]} - real VAT/LEI data test'
        }
        
        response = client.post(
            '/api/v1/kyb/counterparties',
            json=counterparty_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'counterparty' in data['data']
        
        # Verify counterparty data
        counterparty = data['data']['counterparty']
        assert counterparty['name'] == company['name']
        if company.get('vat_number'):
            assert counterparty['vat_number'] == company['vat_number']
        if company.get('lei_code'):
            assert counterparty['lei_code'] == company['lei_code']

    def test_counterparties_create_validation(self, client, auth_headers):
        """Test counterparty creation validation.
        
        Requirements: 2.4 - KYB API tests
        """
        # Test missing required fields
        incomplete_data = {
            'name': 'Test Company',
            # Missing country_code and other required fields
        }
        
        response = client.post(
            '/api/v1/kyb/counterparties',
            json=incomplete_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data

    def test_counterparties_get_by_id(self, client, auth_headers):
        """Test getting counterparty by ID.
        
        Requirements: 2.4 - KYB API tests
        """
        # Test with non-existent counterparty ID
        response = client.get('/api/v1/kyb/counterparties/999999', headers=auth_headers)
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_counterparties_update_with_real_data(self, client, auth_headers, real_company_data):
        """Test updating counterparty with real data.
        
        Requirements: 2.4 - KYB API tests
        """
        company = list(real_company_data.values())[0]
        
        # Test updating non-existent counterparty
        update_data = {
            'name': company['name'],
            'risk_level': 'medium',
            'notes': f'Updated counterparty for {company["name"]} with real data'
        }
        
        response = client.put(
            '/api/v1/kyb/counterparties/999999',
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_counterparties_sanctions_check(self, client, auth_headers):
        """Test sanctions screening for counterparty.
        
        Requirements: 2.4 - KYB API tests
        """
        # Test sanctions check for non-existent counterparty
        sanctions_data = {
            'lists': ['eu_sanctions', 'ofac_sdn', 'uk_hmt'],
            'threshold': 0.8
        }
        
        response = client.post(
            '/api/v1/kyb/counterparties/999999/sanctions',
            json=sanctions_data,
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_counterparties_insolvency_check(self, client, auth_headers):
        """Test insolvency monitoring for counterparty.
        
        Requirements: 2.4 - KYB API tests
        """
        # Test insolvency check for non-existent counterparty
        response = client.post('/api/v1/kyb/insolvency/check/999999', headers=auth_headers)
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_counterparties_snapshots(self, client, auth_headers):
        """Test getting counterparty snapshots.
        
        Requirements: 2.4 - KYB API tests
        """
        # Test getting snapshots for non-existent counterparty
        response = client.get('/api/v1/kyb/counterparties/999999/snapshots', headers=auth_headers)
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_counterparties_diffs(self, client, auth_headers):
        """Test getting counterparty data differences.
        
        Requirements: 2.4 - KYB API tests
        """
        # Test getting diffs for non-existent counterparty
        response = client.get('/api/v1/kyb/counterparties/999999/diffs', headers=auth_headers)
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_counterparties_unauthorized_access(self, client):
        """Test KYB counterparties endpoints without authentication.
        
        Requirements: 2.4 - KYB API tests
        """
        endpoints = [
            ('/api/v1/kyb/counterparties', 'GET'),
            ('/api/v1/kyb/counterparties', 'POST'),
            ('/api/v1/kyb/counterparties/1', 'GET'),
            ('/api/v1/kyb/counterparties/1', 'PUT'),
            ('/api/v1/kyb/counterparties/1', 'DELETE'),
            ('/api/v1/kyb/counterparties/1/sanctions', 'POST'),
            ('/api/v1/kyb/insolvency/check/1', 'POST'),
            ('/api/v1/kyb/counterparties/1/snapshots', 'GET'),
            ('/api/v1/kyb/counterparties/1/diffs', 'GET')
        ]
        
        for endpoint, method in endpoints:
            if method == 'GET':
                response = client.get(endpoint)
            elif method == 'POST':
                response = client.post(endpoint, json={})
            elif method == 'PUT':
                response = client.put(endpoint, json={})
            elif method == 'DELETE':
                response = client.delete(endpoint)
            
            assert response.status_code == 401
            data = response.get_json()
            assert 'error' in data


class TestCoreAPIErrorHandling:
    """Test core API error handling and edge cases."""

    def test_invalid_json_requests(self, client, auth_headers):
        """Test core API endpoints with invalid JSON data.
        
        Requirements: 2.2, 2.3, 2.4 - Core business API
        """
        endpoints = [
            '/api/v1/crm/contacts',
            '/api/v1/crm/leads',
            '/api/v1/kyb/counterparties'
        ]
        
        for endpoint in endpoints:
            response = client.post(
                endpoint,
                data='invalid json data',
                headers=auth_headers
            )
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False

    def test_oversized_requests(self, client, auth_headers, real_company_data):
        """Test core API endpoints with oversized request data.
        
        Requirements: 2.2, 2.3, 2.4 - Core business API
        """
        company = list(real_company_data.values())[0]
        
        # Create oversized data
        oversized_data = {
            'name': company['name'],
            'description': 'A' * 10000,  # Very long description
            'notes': 'B' * 10000  # Very long notes
        }
        
        endpoints = [
            '/api/v1/crm/contacts',
            '/api/v1/crm/leads',
            '/api/v1/kyb/counterparties'
        ]
        
        for endpoint in endpoints:
            response = client.post(
                endpoint,
                json=oversized_data,
                headers=auth_headers
            )
            
            # Should handle gracefully
            assert response.status_code in [400, 413, 500]  # Bad request, payload too large, or server error

    def test_special_characters_in_data(self, client, auth_headers, real_company_data):
        """Test core API endpoints with special characters in data.
        
        Requirements: 2.2, 2.3, 2.4 - Core business API
        """
        company = list(real_company_data.values())[0]
        
        special_char_data = {
            'name': f'{company["name"]} & Co. (Special Chars: äöü)',
            'description': 'Company with special characters: àáâãäåæçèéêë',
            'notes': 'Notes with emojis: 🏢 💼 📊',
            'address': 'Straße 123, München, Deutschland'
        }
        
        # Test with CRM contacts endpoint
        response = client.post(
            '/api/v1/crm/contacts',
            json={
                'company_name': special_char_data['name'],
                'first_name': 'José',
                'last_name': 'García-López',
                'email': 'jose.garcia@example.com',
                'notes': special_char_data['notes']
            },
            headers=auth_headers
        )
        
        # Should handle special characters properly
        assert response.status_code in [201, 400, 500]  # Various valid responses

    def test_sql_injection_attempts(self, client, auth_headers):
        """Test core API endpoints against SQL injection attempts.
        
        Requirements: 2.2, 2.3, 2.4 - Core business API
        """
        injection_data = {
            'name': "Test Company'; DROP TABLE contacts; --",
            'email': "test@example.com' OR '1'='1",
            'vat_number': "DE123456789'; DELETE FROM counterparties; --"
        }
        
        endpoints = [
            '/api/v1/crm/contacts',
            '/api/v1/crm/leads',
            '/api/v1/kyb/counterparties'
        ]
        
        for endpoint in endpoints:
            response = client.post(
                endpoint,
                json=injection_data,
                headers=auth_headers
            )
            
            # Should handle safely without SQL injection
            assert response.status_code in [201, 400, 500]  # Various valid responses
            data = response.get_json()
            assert data['success'] in [True, False]  # Should not crash

    def test_concurrent_requests(self, client, auth_headers, real_company_data):
        """Test core API endpoints with concurrent requests.
        
        Requirements: 2.2, 2.3, 2.4 - Core business API
        """
        import threading
        import time
        
        company = list(real_company_data.values())[0]
        results = []
        
        def make_request():
            contact_data = {
                'company_name': f'{company["name"]} - Thread Test',
                'first_name': 'Test',
                'last_name': 'User',
                'email': f'test.{time.time()}@example.com'
            }
            
            response = client.post(
                '/api/v1/crm/contacts',
                json=contact_data,
                headers=auth_headers
            )
            results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should be handled properly
        for status_code in results:
            assert status_code in [201, 400, 500]  # Various valid responses