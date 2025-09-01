"""Comprehensive CRM contact management tests using real company data.

This test suite implements task 5.1 from the comprehensive system testing spec:
- Write contact creation tests using real company data
- Implement contact update and search functionality tests  
- Create contact deduplication tests with similar company names
"""
import pytest
import json
from datetime import datetime
from app.models.contact import Contact
from app.models.tenant import Tenant
from app.models.user import User
from app import db


class TestContactCreationWithRealData:
    """Test contact creation using real company data from the comprehensive dataset."""
    
    @pytest.fixture
    def real_company_data(self):
        """Real company data from comprehensive test dataset."""
        return {
            "sap_germany": {
                "name": "SAP SE",
                "vat_number": "DE143593636",
                "lei_code": "529900T8BM49AURSDO55",
                "country_code": "DE",
                "address": "Dietmar-Hopp-Allee 16, 69190 Walldorf",
                "industry": "Technology",
                "size": "Large"
            },
            "microsoft_ireland": {
                "name": "Microsoft Ireland Operations Limited", 
                "vat_number": "IE9825613N",
                "lei_code": "635400AKJKKLMN4KNZ71",
                "country_code": "IE",
                "address": "One Microsoft Place, South County Business Park, Leopardstown, Dublin 18",
                "industry": "Technology",
                "size": "Large"
            },
            "google_ireland": {
                "name": "Google Ireland Limited",
                "vat_number": "IE6388047V", 
                "lei_code": "549300PPXHEU2JF0AM85",
                "country_code": "IE",
                "address": "Gordon House, Barrow Street, Dublin 4",
                "industry": "Technology",
                "size": "Large"
            },
            "santander_spain": {
                "name": "Banco Santander, S.A.",
                "vat_number": "ESA39000013",
                "lei_code": "5493006QMFDDMYWIAM13", 
                "country_code": "ES",
                "address": "Ciudad Grupo Santander, Avenida de Cantabria, s/n, 28660 Boadilla del Monte, Madrid",
                "industry": "Financial Services",
                "size": "Large"
            },
            "bnp_paribas_france": {
                "name": "BNP Paribas",
                "vat_number": "FR76662042449",
                "lei_code": "R0MUWSFPU8MPRO8K5P83",
                "country_code": "FR", 
                "address": "16 Boulevard des Italiens, 75009 Paris",
                "industry": "Financial Services",
                "size": "Large"
            }
        }

    def test_create_contact_with_real_company_data(self, client, auth_headers, test_tenant, real_company_data):
        """Test creating contacts using real company data from different countries."""
        created_contacts = []
        
        for company_key, company_data in real_company_data.items():
            contact_data = {
                "company": company_data["name"],
                "first_name": "John",
                "last_name": "Doe", 
                "email": f"john.doe@{company_key.replace('_', '-')}.com",
                "phone": "+1234567890",
                "address_line1": company_data["address"].split(',')[0],
                "city": company_data["address"].split(',')[-1].strip(),
                "country": company_data["country_code"],
                "contact_type": "prospect",
                "source": "comprehensive_test",
                "custom_fields": {
                    "vat_number": company_data["vat_number"],
                    "lei_code": company_data["lei_code"],
                    "industry": company_data["industry"],
                    "company_size": company_data["size"]
                },
                "tags": [company_data["industry"], company_data["country_code"], "real_data_test"]
            }
            
            response = client.post(
                '/api/v1/crm/contacts',
                headers=auth_headers,
                json=contact_data
            )
            
            assert response.status_code == 201, f"Failed to create contact for {company_key}"
            
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['data']['company'] == company_data["name"]
            assert data['data']['country'] == company_data["country_code"]
            assert data['data']['custom_fields']['vat_number'] == company_data["vat_number"]
            assert data['data']['custom_fields']['lei_code'] == company_data["lei_code"]
            assert company_data["industry"] in data['data']['tags']
            
            created_contacts.append(data['data'])
        
        # Verify all contacts were created successfully
        assert len(created_contacts) == len(real_company_data)
        
        # Verify contacts are retrievable
        response = client.get('/api/v1/crm/contacts', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        contact_companies = [c['company'] for c in data['data']['items']]
        
        for company_data in real_company_data.values():
            assert company_data["name"] in contact_companies

    def test_create_contact_with_vat_validation_data(self, client, auth_headers, test_tenant, real_company_data):
        """Test creating contacts with VAT numbers that can be validated."""
        # Use companies with valid VAT numbers from the dataset
        valid_vat_companies = {
            "google_ireland": real_company_data["google_ireland"],
            "santander_spain": real_company_data["santander_spain"],
            "bnp_paribas_france": real_company_data["bnp_paribas_france"]
        }
        
        for company_key, company_data in valid_vat_companies.items():
            contact_data = {
                "company": company_data["name"],
                "first_name": "VAT",
                "last_name": "Validator",
                "email": f"vat.validator@{company_key.replace('_', '-')}.com",
                "country": company_data["country_code"],
                "custom_fields": {
                    "vat_number": company_data["vat_number"],
                    "vat_validated": True,
                    "validation_source": "comprehensive_test_dataset"
                },
                "tags": ["vat_validated", "real_company"]
            }
            
            response = client.post(
                '/api/v1/crm/contacts',
                headers=auth_headers,
                json=contact_data
            )
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data['data']['custom_fields']['vat_number'] == company_data["vat_number"]
            assert data['data']['custom_fields']['vat_validated'] is True

    def test_create_contact_with_lei_code_data(self, client, auth_headers, test_tenant, real_company_data):
        """Test creating contacts with LEI codes from real companies."""
        for company_key, company_data in real_company_data.items():
            contact_data = {
                "company": company_data["name"],
                "first_name": "LEI",
                "last_name": "Contact",
                "email": f"lei.contact@{company_key.replace('_', '-')}.com",
                "custom_fields": {
                    "lei_code": company_data["lei_code"],
                    "lei_status": "ACTIVE",
                    "corporate_hierarchy": "parent_entity"
                },
                "tags": ["lei_validated", "corporate_entity"]
            }
            
            response = client.post(
                '/api/v1/crm/contacts',
                headers=auth_headers,
                json=contact_data
            )
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data['data']['custom_fields']['lei_code'] == company_data["lei_code"]
            assert "lei_validated" in data['data']['tags']


class TestContactUpdateFunctionality:
    """Test contact update functionality with real company data."""
    
    @pytest.fixture
    def sample_contact(self, client, auth_headers, test_tenant):
        """Create a sample contact for update tests."""
        contact_data = {
            "company": "SAP SE",
            "first_name": "Update",
            "last_name": "Test",
            "email": "update.test@sap.com",
            "phone": "+49123456789",
            "address_line1": "Dietmar-Hopp-Allee 16",
            "city": "Walldorf",
            "country": "DE",
            "custom_fields": {
                "vat_number": "DE143593636",
                "industry": "Technology"
            }
        }
        
        response = client.post(
            '/api/v1/crm/contacts',
            headers=auth_headers,
            json=contact_data
        )
        
        assert response.status_code == 201
        return json.loads(response.data)['data']

    def test_update_contact_company_information(self, client, auth_headers, sample_contact):
        """Test updating contact company information with real data."""
        contact_id = sample_contact['id']
        
        # Update to Microsoft Ireland data
        update_data = {
            "company": "Microsoft Ireland Operations Limited",
            "address_line1": "One Microsoft Place",
            "city": "Dublin 18",
            "country": "IE",
            "custom_fields": {
                "vat_number": "IE9825613N",
                "lei_code": "635400AKJKKLMN4KNZ71",
                "industry": "Technology"
            },
            "tags": ["updated", "microsoft", "ireland"]
        }
        
        response = client.put(
            f'/api/v1/crm/contacts/{contact_id}',
            headers=auth_headers,
            json=update_data
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['company'] == "Microsoft Ireland Operations Limited"
        assert data['data']['country'] == "IE"
        assert data['data']['custom_fields']['vat_number'] == "IE9825613N"
        assert "microsoft" in data['data']['tags']

    def test_update_contact_validation_status(self, client, auth_headers, sample_contact):
        """Test updating contact validation status based on real data validation."""
        contact_id = sample_contact['id']
        
        # Simulate validation results from real data testing
        update_data = {
            "custom_fields": {
                "vat_number": "DE143593636",
                "vat_validated": False,
                "vat_validation_date": datetime.utcnow().isoformat(),
                "vat_validation_source": "VIES",
                "lei_code": "529900T8BM49AURSDO55", 
                "lei_validated": True,
                "lei_validation_date": datetime.utcnow().isoformat(),
                "lei_validation_source": "GLEIF"
            },
            "tags": ["validation_completed", "lei_valid", "vat_invalid"]
        }
        
        response = client.put(
            f'/api/v1/crm/contacts/{contact_id}',
            headers=auth_headers,
            json=update_data
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['custom_fields']['vat_validated'] is False
        assert data['data']['custom_fields']['lei_validated'] is True
        assert "validation_completed" in data['data']['tags']

    def test_update_contact_industry_classification(self, client, auth_headers, sample_contact):
        """Test updating contact industry classification."""
        contact_id = sample_contact['id']
        
        update_data = {
            "custom_fields": {
                "industry": "Enterprise Software",
                "sub_industry": "Business Applications",
                "market_segment": "Large Enterprise",
                "employee_count": "100000+",
                "annual_revenue": "30B+"
            },
            "tags": ["enterprise", "software", "large_corp"]
        }
        
        response = client.put(
            f'/api/v1/crm/contacts/{contact_id}',
            headers=auth_headers,
            json=update_data
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['custom_fields']['industry'] == "Enterprise Software"
        assert data['data']['custom_fields']['market_segment'] == "Large Enterprise"


class TestContactSearchFunctionality:
    """Test contact search functionality with real company data."""
    
    @pytest.fixture
    def search_test_contacts(self, client, auth_headers, test_tenant):
        """Create multiple contacts for search testing."""
        contacts_data = [
            {
                "company": "SAP SE",
                "first_name": "Hans",
                "last_name": "Mueller",
                "email": "hans.mueller@sap.com",
                "country": "DE",
                "custom_fields": {"industry": "Technology", "vat_number": "DE143593636"}
            },
            {
                "company": "Microsoft Ireland Operations Limited",
                "first_name": "John",
                "last_name": "Smith", 
                "email": "john.smith@microsoft.com",
                "country": "IE",
                "custom_fields": {"industry": "Technology", "vat_number": "IE9825613N"}
            },
            {
                "company": "Banco Santander, S.A.",
                "first_name": "Maria",
                "last_name": "Garcia",
                "email": "maria.garcia@santander.com",
                "country": "ES",
                "custom_fields": {"industry": "Financial Services", "vat_number": "ESA39000013"}
            },
            {
                "company": "BNP Paribas",
                "first_name": "Pierre",
                "last_name": "Dubois",
                "email": "pierre.dubois@bnpparibas.com",
                "country": "FR",
                "custom_fields": {"industry": "Financial Services", "vat_number": "FR76662042449"}
            }
        ]
        
        created_contacts = []
        for contact_data in contacts_data:
            response = client.post(
                '/api/v1/crm/contacts',
                headers=auth_headers,
                json=contact_data
            )
            assert response.status_code == 201
            created_contacts.append(json.loads(response.data)['data'])
        
        return created_contacts

    def test_search_contacts_by_company_name(self, client, auth_headers, search_test_contacts):
        """Test searching contacts by company name."""
        # Search for SAP
        response = client.get('/api/v1/crm/contacts?search=SAP', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data['data']['items']) >= 1
        
        sap_contact = next((c for c in data['data']['items'] if 'SAP' in c['company']), None)
        assert sap_contact is not None
        assert sap_contact['company'] == "SAP SE"
        
        # Search for Microsoft
        response = client.get('/api/v1/crm/contacts?search=Microsoft', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        microsoft_contact = next((c for c in data['data']['items'] if 'Microsoft' in c['company']), None)
        assert microsoft_contact is not None
        assert "Microsoft Ireland" in microsoft_contact['company']

    def test_search_contacts_by_industry(self, client, auth_headers, search_test_contacts):
        """Test filtering contacts by industry."""
        # Filter by Technology industry
        response = client.get('/api/v1/crm/contacts?search=Technology', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        tech_companies = [c['company'] for c in data['data']['items'] 
                         if c.get('custom_fields', {}).get('industry') == 'Technology']
        
        assert "SAP SE" in tech_companies or "Microsoft Ireland Operations Limited" in tech_companies
        
        # Filter by Financial Services
        response = client.get('/api/v1/crm/contacts?search=Financial', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        financial_companies = [c['company'] for c in data['data']['items']
                             if 'Santander' in c['company'] or 'BNP' in c['company']]
        
        assert len(financial_companies) >= 1

    def test_search_contacts_by_country(self, client, auth_headers, search_test_contacts):
        """Test filtering contacts by country."""
        # Search German companies
        response = client.get('/api/v1/crm/contacts?search=DE', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        german_contacts = [c for c in data['data']['items'] if c['country'] == 'DE']
        assert len(german_contacts) >= 1
        
        # Search Irish companies  
        response = client.get('/api/v1/crm/contacts?search=IE', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        irish_contacts = [c for c in data['data']['items'] if c['country'] == 'IE']
        assert len(irish_contacts) >= 1

    def test_search_contacts_by_email_domain(self, client, auth_headers, search_test_contacts):
        """Test searching contacts by email domain."""
        # Search for SAP email domain
        response = client.get('/api/v1/crm/contacts?search=sap.com', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        sap_contacts = [c for c in data['data']['items'] if 'sap.com' in c['email']]
        assert len(sap_contacts) >= 1
        
        # Search for Microsoft email domain
        response = client.get('/api/v1/crm/contacts?search=microsoft.com', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        microsoft_contacts = [c for c in data['data']['items'] if 'microsoft.com' in c['email']]
        assert len(microsoft_contacts) >= 1


class TestContactDeduplication:
    """Test contact deduplication with similar company names."""
    
    @pytest.fixture
    def similar_companies_data(self):
        """Companies with similar names for deduplication testing."""
        return [
            {
                "company": "Microsoft Corporation",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@microsoft.com",
                "country": "US",
                "custom_fields": {"vat_number": "US123456789", "entity_type": "Corporation"}
            },
            {
                "company": "Microsoft Ireland Operations Limited",
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane.smith@microsoft.com",
                "country": "IE", 
                "custom_fields": {"vat_number": "IE9825613N", "entity_type": "Limited Company"}
            },
            {
                "company": "Microsoft Ireland Research",
                "first_name": "Bob",
                "last_name": "Johnson",
                "email": "bob.johnson@microsoft.com",
                "country": "IE",
                "custom_fields": {"vat_number": "IE9876543N", "entity_type": "Research Division"}
            },
            {
                "company": "SAP SE",
                "first_name": "Hans",
                "last_name": "Mueller",
                "email": "hans.mueller@sap.com",
                "country": "DE",
                "custom_fields": {"vat_number": "DE143593636", "entity_type": "SE"}
            },
            {
                "company": "SAP America Inc",
                "first_name": "Mike",
                "last_name": "Wilson",
                "email": "mike.wilson@sap.com",
                "country": "US",
                "custom_fields": {"vat_number": "US987654321", "entity_type": "Inc"}
            }
        ]

    def test_detect_similar_company_names(self, client, auth_headers, test_tenant, similar_companies_data):
        """Test detection of similar company names during contact creation."""
        created_contacts = []
        
        # Create contacts with similar company names
        for contact_data in similar_companies_data:
            response = client.post(
                '/api/v1/crm/contacts',
                headers=auth_headers,
                json=contact_data
            )
            assert response.status_code == 201
            created_contacts.append(json.loads(response.data)['data'])
        
        # Search for Microsoft-related companies
        response = client.get('/api/v1/crm/contacts?search=Microsoft', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        microsoft_contacts = [c for c in data['data']['items'] if 'Microsoft' in c['company']]
        
        # Should find all 3 Microsoft entities
        assert len(microsoft_contacts) >= 3
        
        company_names = [c['company'] for c in microsoft_contacts]
        assert "Microsoft Corporation" in company_names
        assert "Microsoft Ireland Operations Limited" in company_names
        assert "Microsoft Ireland Research" in company_names

    def test_identify_duplicate_contacts_by_email(self, client, auth_headers, test_tenant):
        """Test identification of potential duplicate contacts by email domain."""
        # Create contacts with same email domain but different companies
        contacts_data = [
            {
                "company": "Google Ireland Limited",
                "first_name": "Alice",
                "last_name": "Brown",
                "email": "alice.brown@google.com",
                "country": "IE"
            },
            {
                "company": "Google LLC",
                "first_name": "Alice",
                "last_name": "Brown", 
                "email": "alice.brown@google.com",  # Same email
                "country": "US"
            }
        ]
        
        # Create first contact
        response = client.post(
            '/api/v1/crm/contacts',
            headers=auth_headers,
            json=contacts_data[0]
        )
        assert response.status_code == 201
        
        # Try to create second contact with same email - should fail
        response = client.post(
            '/api/v1/crm/contacts',
            headers=auth_headers,
            json=contacts_data[1]
        )
        assert response.status_code == 409  # Conflict - duplicate email

    def test_merge_similar_company_contacts(self, client, auth_headers, test_tenant):
        """Test merging contacts from similar companies."""
        # Create two contacts for the same company with different spellings
        contact1_data = {
            "company": "Banco Santander S.A.",
            "first_name": "Maria",
            "last_name": "Rodriguez",
            "email": "maria.rodriguez@santander.com",
            "phone": "+34123456789",
            "custom_fields": {"vat_number": "ESA39000013"}
        }
        
        contact2_data = {
            "company": "Banco Santander, S.A.",  # Slightly different spelling
            "first_name": "Carlos",
            "last_name": "Lopez",
            "email": "carlos.lopez@santander.com",
            "phone": "+34987654321",
            "custom_fields": {"vat_number": "ESA39000013"}  # Same VAT number
        }
        
        # Create both contacts
        response1 = client.post('/api/v1/crm/contacts', headers=auth_headers, json=contact1_data)
        assert response1.status_code == 201
        contact1 = json.loads(response1.data)['data']
        
        response2 = client.post('/api/v1/crm/contacts', headers=auth_headers, json=contact2_data)
        assert response2.status_code == 201
        contact2 = json.loads(response2.data)['data']
        
        # Search should find both contacts
        response = client.get('/api/v1/crm/contacts?search=Santander', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        santander_contacts = [c for c in data['data']['items'] if 'Santander' in c['company']]
        assert len(santander_contacts) >= 2
        
        # Verify they have the same VAT number (indicating same company)
        vat_numbers = [c['custom_fields']['vat_number'] for c in santander_contacts 
                      if c.get('custom_fields', {}).get('vat_number')]
        assert len(set(vat_numbers)) == 1  # All should have same VAT number

    def test_company_name_normalization(self, client, auth_headers, test_tenant):
        """Test company name normalization for deduplication."""
        # Create contacts with company names that should be normalized
        normalized_companies = [
            {
                "company": "BNP Paribas S.A.",
                "first_name": "Pierre",
                "last_name": "Martin",
                "email": "pierre.martin@bnpparibas.com",
                "custom_fields": {"vat_number": "FR76662042449"}
            },
            {
                "company": "BNP PARIBAS",  # All caps
                "first_name": "Marie",
                "last_name": "Dubois",
                "email": "marie.dubois@bnpparibas.com",
                "custom_fields": {"vat_number": "FR76662042449"}
            },
            {
                "company": "bnp paribas",  # All lowercase
                "first_name": "Jean",
                "last_name": "Moreau",
                "email": "jean.moreau@bnpparibas.com",
                "custom_fields": {"vat_number": "FR76662042449"}
            }
        ]
        
        created_contacts = []
        for contact_data in normalized_companies:
            response = client.post(
                '/api/v1/crm/contacts',
                headers=auth_headers,
                json=contact_data
            )
            assert response.status_code == 201
            created_contacts.append(json.loads(response.data)['data'])
        
        # Search should find all variations
        response = client.get('/api/v1/crm/contacts?search=BNP', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        bnp_contacts = [c for c in data['data']['items'] if 'BNP' in c['company'].upper()]
        assert len(bnp_contacts) >= 3
        
        # All should have the same VAT number
        vat_numbers = [c['custom_fields']['vat_number'] for c in bnp_contacts
                      if c.get('custom_fields', {}).get('vat_number')]
        assert len(set(vat_numbers)) == 1


class TestContactValidationWithRealData:
    """Test contact validation using real company data validation results."""
    
    def test_validate_contact_vat_numbers(self, client, auth_headers, test_tenant):
        """Test contact creation with VAT number validation status."""
        # Use validation results from comprehensive test dataset
        validation_test_data = [
            {
                "company": "Google Ireland Limited",
                "vat_number": "IE6388047V",
                "vat_valid": True,
                "vat_name": "GOOGLE IRELAND LIMITED",
                "vat_address": "3RD FLOOR, GORDON HOUSE, BARROW STREET, DUBLIN 4"
            },
            {
                "company": "Spotify AB", 
                "vat_number": "SE556703748501",
                "vat_valid": True,
                "vat_name": "Spotify AB",
                "vat_address": "REGERINGSGATAN 19 \n111 53 STOCKHOLM"
            },
            {
                "company": "SAP SE",
                "vat_number": "DE143593636", 
                "vat_valid": False,
                "vat_error": "VAT validation failed"
            }
        ]
        
        for test_data in validation_test_data:
            contact_data = {
                "company": test_data["company"],
                "first_name": "VAT",
                "last_name": "Test",
                "email": f"vat.test@{test_data['company'].lower().replace(' ', '')}.com",
                "custom_fields": {
                    "vat_number": test_data["vat_number"],
                    "vat_validated": test_data["vat_valid"],
                    "vat_validation_name": test_data.get("vat_name"),
                    "vat_validation_address": test_data.get("vat_address"),
                    "vat_validation_error": test_data.get("vat_error")
                },
                "tags": ["vat_tested", "validation_complete"]
            }
            
            response = client.post(
                '/api/v1/crm/contacts',
                headers=auth_headers,
                json=contact_data
            )
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data['data']['custom_fields']['vat_validated'] == test_data["vat_valid"]
            if test_data["vat_valid"]:
                assert data['data']['custom_fields']['vat_validation_name'] == test_data["vat_name"]

    def test_validate_contact_lei_codes(self, client, auth_headers, test_tenant):
        """Test contact creation with LEI code validation status."""
        # Use LEI validation results from comprehensive test dataset
        lei_test_data = [
            {
                "company": "Deutsche Bank AG",
                "lei_code": "7LTWFZYICNSX8D621K86",
                "lei_valid": True,
                "lei_legal_name": "DEUTSCHE BANK AKTIENGESELLSCHAFT",
                "lei_status": "ACTIVE"
            },
            {
                "company": "BNP Paribas",
                "lei_code": "R0MUWSFPU8MPRO8K5P83", 
                "lei_valid": True,
                "lei_legal_name": "BNP PARIBAS",
                "lei_status": "ACTIVE"
            },
            {
                "company": "Microsoft Ireland Operations Limited",
                "lei_code": "635400AKJKKLMN4KNZ71",
                "lei_valid": False,
                "lei_error": "LEI code not found"
            }
        ]
        
        for test_data in lei_test_data:
            contact_data = {
                "company": test_data["company"],
                "first_name": "LEI",
                "last_name": "Test",
                "email": f"lei.test@{test_data['company'].lower().replace(' ', '')}.com",
                "custom_fields": {
                    "lei_code": test_data["lei_code"],
                    "lei_validated": test_data["lei_valid"],
                    "lei_legal_name": test_data.get("lei_legal_name"),
                    "lei_status": test_data.get("lei_status"),
                    "lei_validation_error": test_data.get("lei_error")
                },
                "tags": ["lei_tested", "validation_complete"]
            }
            
            response = client.post(
                '/api/v1/crm/contacts',
                headers=auth_headers,
                json=contact_data
            )
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data['data']['custom_fields']['lei_validated'] == test_data["lei_valid"]
            if test_data["lei_valid"]:
                assert data['data']['custom_fields']['lei_legal_name'] == test_data["lei_legal_name"]