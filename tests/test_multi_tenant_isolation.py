"""Comprehensive multi-tenant isolation testing suite with real company data."""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from flask_jwt_extended import create_access_token

from app.models.user import User
from app.models.tenant import Tenant
from app.models.role import Role
from app.models.crm.contact import Contact
from app.models.crm.lead import Lead
from app.models.kyb.counterparty import Counterparty
from app.models.knowledge.document import Document
from app.models.audit_log import AuditLog
from app import db


class TestMultiTenantIsolation:
    """Test multi-tenant data isolation with real company data."""
    
    @pytest.fixture
    def real_company_data(self):
        """Load real company data for multi-tenant testing."""
        try:
            with open('comprehensive_test_dataset.json', 'r', encoding='utf-8') as f:
                dataset = json.load(f)
            return dataset['companies']
        except FileNotFoundError:
            # Fallback to predefined data if file not found
            return {
                "tenant_a_company": {
                    "name": "SAP SE",
                    "vat_number": "DE143593636",
                    "lei_code": "529900T8BM49AURSDO55",
                    "country_code": "DE",
                    "address": "Dietmar-Hopp-Allee 16, 69190 Walldorf",
                    "industry": "Technology",
                    "size": "Large"
                },
                "tenant_b_company": {
                    "name": "Microsoft Ireland Operations Limited",
                    "vat_number": "IE9825613N",
                    "lei_code": "635400AKJKKLMN4KNZ71",
                    "country_code": "IE",
                    "address": "One Microsoft Place, South County Business Park, Leopardstown, Dublin 18",
                    "industry": "Technology",
                    "size": "Large"
                },
                "tenant_c_company": {
                    "name": "Unilever PLC",
                    "vat_number": "GB440861235",
                    "lei_code": "549300BFXFJ6KBNTKY86",
                    "country_code": "GB",
                    "address": "100 Victoria Embankment, London EC4Y 0DY",
                    "industry": "Consumer Goods",
                    "size": "Large"
                }
            }
    
    @pytest.fixture
    def multi_tenant_setup(self, app, real_company_data):
        """Create multiple tenants with real company data for isolation testing."""
        with app.app_context():
            tenants_data = {}
            
            # Create Tenant A (SAP)
            company_a = real_company_data['tenant_a_company']
            tenant_a, owner_a = Tenant.create_with_owner(
                name=company_a['name'],
                owner_email='owner@sap.com',
                owner_password='SecurePassword123!',
                owner_first_name='SAP',
                owner_last_name='Owner'
            )
            tenant_a.vat_number = company_a['vat_number']
            tenant_a.lei_code = company_a['lei_code']
            tenant_a.address = company_a['address']
            tenant_a.country_code = company_a['country_code']
            tenant_a.save()
            
            # Create additional user for Tenant A
            user_a = User.create(
                email='user@sap.com',
                password='SecurePassword123!',
                tenant_id=tenant_a.id,
                first_name='SAP',
                last_name='User',
                role='manager'
            )
            
            # Create Tenant B (Microsoft)
            company_b = real_company_data['tenant_b_company']
            tenant_b, owner_b = Tenant.create_with_owner(
                name=company_b['name'],
                owner_email='owner@microsoft.com',
                owner_password='SecurePassword123!',
                owner_first_name='Microsoft',
                owner_last_name='Owner'
            )
            tenant_b.vat_number = company_b['vat_number']
            tenant_b.lei_code = company_b['lei_code']
            tenant_b.address = company_b['address']
            tenant_b.country_code = company_b['country_code']
            tenant_b.save()
            
            # Create additional user for Tenant B
            user_b = User.create(
                email='user@microsoft.com',
                password='SecurePassword123!',
                tenant_id=tenant_b.id,
                first_name='Microsoft',
                last_name='User',
                role='manager'
            )
            
            # Create Tenant C (Unilever)
            company_c = real_company_data['tenant_c_company']
            tenant_c, owner_c = Tenant.create_with_owner(
                name=company_c['name'],
                owner_email='owner@unilever.com',
                owner_password='SecurePassword123!',
                owner_first_name='Unilever',
                owner_last_name='Owner'
            )
            tenant_c.vat_number = company_c['vat_number']
            tenant_c.lei_code = company_c['lei_code']
            tenant_c.address = company_c['address']
            tenant_c.country_code = company_c['country_code']
            tenant_c.save()
            
            # Create additional user for Tenant C
            user_c = User.create(
                email='user@unilever.com',
                password='SecurePassword123!',
                tenant_id=tenant_c.id,
                first_name='Unilever',
                last_name='User',
                role='manager'
            )
            
            tenants_data = {
                'tenant_a': {
                    'tenant': tenant_a,
                    'owner': owner_a,
                    'user': user_a,
                    'company': company_a
                },
                'tenant_b': {
                    'tenant': tenant_b,
                    'owner': owner_b,
                    'user': user_b,
                    'company': company_b
                },
                'tenant_c': {
                    'tenant': tenant_c,
                    'owner': owner_c,
                    'user': user_c,
                    'company': company_c
                }
            }
            
            return tenants_data
    
    def test_tenant_creation_with_real_company_data(self, app, multi_tenant_setup):
        """Test that tenants are created correctly with real company data."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Verify Tenant A (SAP)
            tenant_a = tenants_data['tenant_a']['tenant']
            assert tenant_a.name == "SAP SE"
            assert tenant_a.vat_number == "DE143593636"
            assert tenant_a.lei_code == "529900T8BM49AURSDO55"
            assert tenant_a.country_code == "DE"
            assert tenant_a.is_active is True
            assert tenant_a.subscription_status == "trial"
            
            # Verify Tenant B (Microsoft)
            tenant_b = tenants_data['tenant_b']['tenant']
            assert tenant_b.name == "Microsoft Ireland Operations Limited"
            assert tenant_b.vat_number == "IE9825613N"
            assert tenant_b.lei_code == "635400AKJKKLMN4KNZ71"
            assert tenant_b.country_code == "IE"
            assert tenant_b.is_active is True
            assert tenant_b.subscription_status == "trial"
            
            # Verify Tenant C (Unilever)
            tenant_c = tenants_data['tenant_c']['tenant']
            assert tenant_c.name == "Unilever PLC"
            assert tenant_c.vat_number == "GB440861235"
            assert tenant_c.lei_code == "549300BFXFJ6KBNTKY86"
            assert tenant_c.country_code == "GB"
            assert tenant_c.is_active is True
            assert tenant_c.subscription_status == "trial"
            
            # Verify all tenants have unique IDs
            tenant_ids = [tenant_a.id, tenant_b.id, tenant_c.id]
            assert len(set(tenant_ids)) == 3  # All unique
    
    def test_user_tenant_isolation(self, app, multi_tenant_setup):
        """Test that users are properly isolated by tenant."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Get users from different tenants
            owner_a = tenants_data['tenant_a']['owner']
            user_a = tenants_data['tenant_a']['user']
            owner_b = tenants_data['tenant_b']['owner']
            user_b = tenants_data['tenant_b']['user']
            
            # Verify users belong to correct tenants
            assert owner_a.tenant_id == tenants_data['tenant_a']['tenant'].id
            assert user_a.tenant_id == tenants_data['tenant_a']['tenant'].id
            assert owner_b.tenant_id == tenants_data['tenant_b']['tenant'].id
            assert user_b.tenant_id == tenants_data['tenant_b']['tenant'].id
            
            # Verify users cannot access other tenants' data
            assert owner_a.tenant_id != owner_b.tenant_id
            assert user_a.tenant_id != user_b.tenant_id
            
            # Test user queries are tenant-scoped
            tenant_a_users = User.query.filter_by(tenant_id=tenants_data['tenant_a']['tenant'].id).all()
            tenant_b_users = User.query.filter_by(tenant_id=tenants_data['tenant_b']['tenant'].id).all()
            
            assert len(tenant_a_users) == 2  # owner + user
            assert len(tenant_b_users) == 2  # owner + user
            
            # Verify no cross-tenant user access
            tenant_a_user_ids = [u.id for u in tenant_a_users]
            tenant_b_user_ids = [u.id for u in tenant_b_users]
            
            assert not set(tenant_a_user_ids).intersection(set(tenant_b_user_ids))
    
    def test_crm_data_isolation(self, app, multi_tenant_setup):
        """Test CRM data isolation between tenants."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Create contacts for each tenant using real company data
            # Tenant A (SAP) creates contact for a German company
            contact_a = Contact(
                tenant_id=tenants_data['tenant_a']['tenant'].id,
                name="BASF SE",
                email="contact@basf.com",
                company="BASF SE",
                vat_number="DE812001441",
                country="DE",
                created_by_id=tenants_data['tenant_a']['owner'].id
            )
            contact_a.save()
            
            # Tenant B (Microsoft) creates contact for an Irish company
            contact_b = Contact(
                tenant_id=tenants_data['tenant_b']['tenant'].id,
                name="Accenture Ireland",
                email="contact@accenture.ie",
                company="Accenture Ireland",
                vat_number="IE6336345J",
                country="IE",
                created_by_id=tenants_data['tenant_b']['owner'].id
            )
            contact_b.save()
            
            # Tenant C (Unilever) creates contact for a UK company
            contact_c = Contact(
                tenant_id=tenants_data['tenant_c']['tenant'].id,
                name="Tesco PLC",
                email="contact@tesco.com",
                company="Tesco PLC",
                vat_number="GB220014259",
                country="GB",
                created_by_id=tenants_data['tenant_c']['owner'].id
            )
            contact_c.save()
            
            # Test tenant isolation - each tenant should only see their own contacts
            tenant_a_contacts = Contact.query.filter_by(tenant_id=tenants_data['tenant_a']['tenant'].id).all()
            tenant_b_contacts = Contact.query.filter_by(tenant_id=tenants_data['tenant_b']['tenant'].id).all()
            tenant_c_contacts = Contact.query.filter_by(tenant_id=tenants_data['tenant_c']['tenant'].id).all()
            
            assert len(tenant_a_contacts) == 1
            assert len(tenant_b_contacts) == 1
            assert len(tenant_c_contacts) == 1
            
            assert tenant_a_contacts[0].company == "BASF SE"
            assert tenant_b_contacts[0].company == "Accenture Ireland"
            assert tenant_c_contacts[0].company == "Tesco PLC"
            
            # Verify no cross-tenant contact access
            all_contact_ids = [contact_a.id, contact_b.id, contact_c.id]
            assert len(set(all_contact_ids)) == 3  # All unique
            
            # Test that tenant A cannot access tenant B's contacts
            cross_tenant_query = Contact.query.filter_by(
                tenant_id=tenants_data['tenant_b']['tenant'].id
            ).filter_by(
                created_by_id=tenants_data['tenant_a']['owner'].id
            ).all()
            assert len(cross_tenant_query) == 0
    
    def test_kyb_counterparty_isolation(self, app, multi_tenant_setup):
        """Test KYB counterparty data isolation between tenants."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Create counterparties for each tenant using real company data
            # Tenant A (SAP) monitors German companies
            counterparty_a = Counterparty(
                tenant_id=tenants_data['tenant_a']['tenant'].id,
                name="Siemens AG",
                vat_number="DE129273398",
                lei_code="7LTWFZYICNSX8D621K86",
                country_code="DE",
                status="active",
                created_by_id=tenants_data['tenant_a']['owner'].id
            )
            counterparty_a.save()
            
            # Tenant B (Microsoft) monitors Irish companies
            counterparty_b = Counterparty(
                tenant_id=tenants_data['tenant_b']['tenant'].id,
                name="Google Ireland Limited",
                vat_number="IE6388047V",
                lei_code="549300PPXHEU2JF0AM85",
                country_code="IE",
                status="active",
                created_by_id=tenants_data['tenant_b']['owner'].id
            )
            counterparty_b.save()
            
            # Tenant C (Unilever) monitors UK companies
            counterparty_c = Counterparty(
                tenant_id=tenants_data['tenant_c']['tenant'].id,
                name="BP p.l.c.",
                vat_number="GB974507946",
                lei_code="213800BP4LPRQS1GNC15",
                country_code="GB",
                status="active",
                created_by_id=tenants_data['tenant_c']['owner'].id
            )
            counterparty_c.save()
            
            # Test tenant isolation for counterparties
            tenant_a_counterparties = Counterparty.query.filter_by(
                tenant_id=tenants_data['tenant_a']['tenant'].id
            ).all()
            tenant_b_counterparties = Counterparty.query.filter_by(
                tenant_id=tenants_data['tenant_b']['tenant'].id
            ).all()
            tenant_c_counterparties = Counterparty.query.filter_by(
                tenant_id=tenants_data['tenant_c']['tenant'].id
            ).all()
            
            assert len(tenant_a_counterparties) == 1
            assert len(tenant_b_counterparties) == 1
            assert len(tenant_c_counterparties) == 1
            
            assert tenant_a_counterparties[0].name == "Siemens AG"
            assert tenant_b_counterparties[0].name == "Google Ireland Limited"
            assert tenant_c_counterparties[0].name == "BP p.l.c."
            
            # Verify VAT numbers are correctly isolated
            assert tenant_a_counterparties[0].vat_number == "DE129273398"
            assert tenant_b_counterparties[0].vat_number == "IE6388047V"
            assert tenant_c_counterparties[0].vat_number == "GB974507946"
            
            # Test cross-tenant isolation
            cross_tenant_search = Counterparty.query.filter_by(
                name="Siemens AG"
            ).filter_by(
                tenant_id=tenants_data['tenant_b']['tenant'].id
            ).all()
            assert len(cross_tenant_search) == 0
    
    def test_knowledge_document_isolation(self, app, multi_tenant_setup):
        """Test knowledge base document isolation between tenants."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Create documents for each tenant
            doc_a = Document(
                tenant_id=tenants_data['tenant_a']['tenant'].id,
                title="SAP Implementation Guide",
                content="Internal SAP implementation procedures...",
                document_type="guide",
                created_by_id=tenants_data['tenant_a']['owner'].id
            )
            doc_a.save()
            
            doc_b = Document(
                tenant_id=tenants_data['tenant_b']['tenant'].id,
                title="Microsoft Azure Best Practices",
                content="Azure cloud deployment guidelines...",
                document_type="guide",
                created_by_id=tenants_data['tenant_b']['owner'].id
            )
            doc_b.save()
            
            doc_c = Document(
                tenant_id=tenants_data['tenant_c']['tenant'].id,
                title="Unilever Brand Guidelines",
                content="Brand identity and marketing guidelines...",
                document_type="policy",
                created_by_id=tenants_data['tenant_c']['owner'].id
            )
            doc_c.save()
            
            # Test document isolation
            tenant_a_docs = Document.query.filter_by(
                tenant_id=tenants_data['tenant_a']['tenant'].id
            ).all()
            tenant_b_docs = Document.query.filter_by(
                tenant_id=tenants_data['tenant_b']['tenant'].id
            ).all()
            tenant_c_docs = Document.query.filter_by(
                tenant_id=tenants_data['tenant_c']['tenant'].id
            ).all()
            
            assert len(tenant_a_docs) == 1
            assert len(tenant_b_docs) == 1
            assert len(tenant_c_docs) == 1
            
            assert tenant_a_docs[0].title == "SAP Implementation Guide"
            assert tenant_b_docs[0].title == "Microsoft Azure Best Practices"
            assert tenant_c_docs[0].title == "Unilever Brand Guidelines"
            
            # Verify content isolation
            assert "SAP implementation" in tenant_a_docs[0].content
            assert "Azure cloud" in tenant_b_docs[0].content
            assert "Brand identity" in tenant_c_docs[0].content
            
            # Test search isolation - tenant A shouldn't find tenant B's documents
            cross_tenant_search = Document.query.filter(
                Document.title.contains("Azure")
            ).filter_by(
                tenant_id=tenants_data['tenant_a']['tenant'].id
            ).all()
            assert len(cross_tenant_search) == 0
    
    def test_audit_log_isolation(self, app, multi_tenant_setup):
        """Test audit log isolation between tenants."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Create audit logs for different tenants
            audit_a = AuditLog.log_action(
                action='create',
                resource_type='contact',
                resource_id=1,
                user_id=tenants_data['tenant_a']['owner'].id,
                tenant_id=tenants_data['tenant_a']['tenant'].id,
                details={'name': 'SAP Contact Created'}
            )
            
            audit_b = AuditLog.log_action(
                action='update',
                resource_type='lead',
                resource_id=2,
                user_id=tenants_data['tenant_b']['owner'].id,
                tenant_id=tenants_data['tenant_b']['tenant'].id,
                details={'name': 'Microsoft Lead Updated'}
            )
            
            audit_c = AuditLog.log_action(
                action='delete',
                resource_type='document',
                resource_id=3,
                user_id=tenants_data['tenant_c']['owner'].id,
                tenant_id=tenants_data['tenant_c']['tenant'].id,
                details={'name': 'Unilever Document Deleted'}
            )
            
            # Test audit log isolation
            tenant_a_logs = AuditLog.query.filter_by(
                tenant_id=tenants_data['tenant_a']['tenant'].id
            ).all()
            tenant_b_logs = AuditLog.query.filter_by(
                tenant_id=tenants_data['tenant_b']['tenant'].id
            ).all()
            tenant_c_logs = AuditLog.query.filter_by(
                tenant_id=tenants_data['tenant_c']['tenant'].id
            ).all()
            
            assert len(tenant_a_logs) >= 1  # At least the one we created
            assert len(tenant_b_logs) >= 1
            assert len(tenant_c_logs) >= 1
            
            # Find our specific audit logs
            sap_log = next((log for log in tenant_a_logs if log.details and 'SAP Contact' in str(log.details)), None)
            microsoft_log = next((log for log in tenant_b_logs if log.details and 'Microsoft Lead' in str(log.details)), None)
            unilever_log = next((log for log in tenant_c_logs if log.details and 'Unilever Document' in str(log.details)), None)
            
            assert sap_log is not None
            assert microsoft_log is not None
            assert unilever_log is not None
            
            assert sap_log.action == 'create'
            assert microsoft_log.action == 'update'
            assert unilever_log.action == 'delete'
            
            # Verify cross-tenant isolation
            cross_tenant_logs = AuditLog.query.filter_by(
                tenant_id=tenants_data['tenant_a']['tenant'].id
            ).filter(
                AuditLog.details.contains('Microsoft')
            ).all()
            assert len(cross_tenant_logs) == 0
    
    def test_role_isolation_between_tenants(self, app, multi_tenant_setup):
        """Test that roles are isolated between tenants."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Get roles for each tenant
            tenant_a_roles = Role.query.filter_by(
                tenant_id=tenants_data['tenant_a']['tenant'].id
            ).all()
            tenant_b_roles = Role.query.filter_by(
                tenant_id=tenants_data['tenant_b']['tenant'].id
            ).all()
            tenant_c_roles = Role.query.filter_by(
                tenant_id=tenants_data['tenant_c']['tenant'].id
            ).all()
            
            # Each tenant should have default system roles
            assert len(tenant_a_roles) == 5  # Owner, Manager, Support, Accounting, Read Only
            assert len(tenant_b_roles) == 5
            assert len(tenant_c_roles) == 5
            
            # Verify role names are consistent across tenants
            role_names_a = [role.name for role in tenant_a_roles]
            role_names_b = [role.name for role in tenant_b_roles]
            role_names_c = [role.name for role in tenant_c_roles]
            
            expected_roles = ["Owner", "Manager", "Support", "Accounting", "Read Only"]
            assert set(role_names_a) == set(expected_roles)
            assert set(role_names_b) == set(expected_roles)
            assert set(role_names_c) == set(expected_roles)
            
            # Verify role IDs are different (no sharing between tenants)
            all_role_ids = []
            for roles in [tenant_a_roles, tenant_b_roles, tenant_c_roles]:
                all_role_ids.extend([role.id for role in roles])
            
            assert len(set(all_role_ids)) == len(all_role_ids)  # All unique
            
            # Create custom role for tenant A
            custom_role_a = Role(
                tenant_id=tenants_data['tenant_a']['tenant'].id,
                name="SAP Administrator",
                description="Custom role for SAP administration"
            )
            custom_role_a.set_permissions(['manage_crm', 'manage_kyb'])
            custom_role_a.save()
            
            # Verify custom role is only visible to tenant A
            tenant_a_custom_roles = Role.query.filter_by(
                tenant_id=tenants_data['tenant_a']['tenant'].id,
                name="SAP Administrator"
            ).all()
            tenant_b_custom_roles = Role.query.filter_by(
                tenant_id=tenants_data['tenant_b']['tenant'].id,
                name="SAP Administrator"
            ).all()
            
            assert len(tenant_a_custom_roles) == 1
            assert len(tenant_b_custom_roles) == 0
    
    def test_api_endpoint_tenant_isolation(self, client, multi_tenant_setup):
        """Test API endpoints properly isolate tenant data."""
        tenants_data = multi_tenant_setup
        
        # Create access tokens for different tenants
        token_a = create_access_token(identity=tenants_data['tenant_a']['owner'])
        token_b = create_access_token(identity=tenants_data['tenant_b']['owner'])
        
        headers_a = {'Authorization': f'Bearer {token_a}'}
        headers_b = {'Authorization': f'Bearer {token_b}'}
        
        # Create contact for tenant A
        contact_data_a = {
            'name': 'BMW Group',
            'email': 'contact@bmw.com',
            'company': 'BMW Group',
            'vat_number': 'DE129273398',
            'country': 'DE'
        }
        
        response_a = client.post('/api/v1/crm/contacts',
                               json=contact_data_a,
                               headers=headers_a)
        assert response_a.status_code == 201
        contact_a_data = response_a.get_json()
        contact_a_id = contact_a_data['data']['id']
        
        # Create contact for tenant B
        contact_data_b = {
            'name': 'Facebook Ireland',
            'email': 'contact@facebook.ie',
            'company': 'Facebook Ireland',
            'vat_number': 'IE6388047V',
            'country': 'IE'
        }
        
        response_b = client.post('/api/v1/crm/contacts',
                               json=contact_data_b,
                               headers=headers_b)
        assert response_b.status_code == 201
        contact_b_data = response_b.get_json()
        contact_b_id = contact_b_data['data']['id']
        
        # Test that tenant A can only see their own contacts
        response_a_list = client.get('/api/v1/crm/contacts', headers=headers_a)
        assert response_a_list.status_code == 200
        contacts_a = response_a_list.get_json()['data']['items']
        
        contact_names_a = [contact['name'] for contact in contacts_a]
        assert 'BMW Group' in contact_names_a
        assert 'Facebook Ireland' not in contact_names_a
        
        # Test that tenant B can only see their own contacts
        response_b_list = client.get('/api/v1/crm/contacts', headers=headers_b)
        assert response_b_list.status_code == 200
        contacts_b = response_b_list.get_json()['data']['items']
        
        contact_names_b = [contact['name'] for contact in contacts_b]
        assert 'Facebook Ireland' in contact_names_b
        assert 'BMW Group' not in contact_names_b
        
        # Test that tenant A cannot access tenant B's contact by ID
        response_cross_access = client.get(f'/api/v1/crm/contacts/{contact_b_id}',
                                         headers=headers_a)
        assert response_cross_access.status_code == 404
        
        # Test that tenant B cannot access tenant A's contact by ID
        response_cross_access_b = client.get(f'/api/v1/crm/contacts/{contact_a_id}',
                                           headers=headers_b)
        assert response_cross_access_b.status_code == 404
    
    def test_database_constraint_tenant_isolation(self, app, multi_tenant_setup):
        """Test database-level constraints enforce tenant isolation."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Test that we cannot create a user with wrong tenant_id
            with pytest.raises(Exception):  # Should raise integrity error
                wrong_user = User(
                    email='wrong@test.com',
                    password_hash='hashed_password',
                    tenant_id=99999,  # Non-existent tenant
                    first_name='Wrong',
                    last_name='User'
                )
                db.session.add(wrong_user)
                db.session.commit()
            
            db.session.rollback()
            
            # Test that we cannot create contact with wrong tenant_id
            with pytest.raises(Exception):  # Should raise integrity error
                wrong_contact = Contact(
                    tenant_id=99999,  # Non-existent tenant
                    name='Wrong Contact',
                    email='wrong@contact.com'
                )
                db.session.add(wrong_contact)
                db.session.commit()
            
            db.session.rollback()
    
    def test_tenant_settings_isolation(self, app, multi_tenant_setup):
        """Test tenant settings are properly isolated."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Set different settings for each tenant
            tenant_a = tenants_data['tenant_a']['tenant']
            tenant_b = tenants_data['tenant_b']['tenant']
            tenant_c = tenants_data['tenant_c']['tenant']
            
            # Tenant A settings (SAP-specific)
            tenant_a.set_setting('sap_integration', True)
            tenant_a.set_setting('german_compliance', True)
            tenant_a.set_setting('max_users', 100)
            tenant_a.save()
            
            # Tenant B settings (Microsoft-specific)
            tenant_b.set_setting('azure_integration', True)
            tenant_b.set_setting('office365_sync', True)
            tenant_b.set_setting('max_users', 50)
            tenant_b.save()
            
            # Tenant C settings (Unilever-specific)
            tenant_c.set_setting('brand_guidelines', True)
            tenant_c.set_setting('uk_compliance', True)
            tenant_c.set_setting('max_users', 200)
            tenant_c.save()
            
            # Verify settings isolation
            assert tenant_a.get_setting('sap_integration') is True
            assert tenant_a.get_setting('azure_integration') is None
            assert tenant_a.get_setting('max_users') == 100
            
            assert tenant_b.get_setting('azure_integration') is True
            assert tenant_b.get_setting('sap_integration') is None
            assert tenant_b.get_setting('max_users') == 50
            
            assert tenant_c.get_setting('brand_guidelines') is True
            assert tenant_c.get_setting('sap_integration') is None
            assert tenant_c.get_setting('max_users') == 200
            
            # Test default values work correctly
            assert tenant_a.get_setting('nonexistent', 'default') == 'default'
            assert tenant_b.get_setting('nonexistent', 'default') == 'default'
            assert tenant_c.get_setting('nonexistent', 'default') == 'default'


class TestUserRoleAssignmentIsolation:
    """Test user role assignment isolation between tenants."""
    
    def test_user_role_assignment_within_tenant(self, app, multi_tenant_setup):
        """Test user role assignment works correctly within tenant boundaries."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Get tenant A data
            tenant_a = tenants_data['tenant_a']['tenant']
            user_a = tenants_data['tenant_a']['user']
            
            # Get tenant A roles
            manager_role_a = Role.query.filter_by(
                tenant_id=tenant_a.id,
                name='Manager'
            ).first()
            support_role_a = Role.query.filter_by(
                tenant_id=tenant_a.id,
                name='Support'
            ).first()
            
            assert manager_role_a is not None
            assert support_role_a is not None
            
            # Assign roles to user A
            user_a.add_role(manager_role_a)
            user_a.add_role(support_role_a)
            user_a.save()
            
            # Verify role assignment
            assert user_a.has_role('Manager')
            assert user_a.has_role('Support')
            
            # Verify permissions from roles
            assert user_a.has_permission('manage_crm')
            assert user_a.has_permission('view_crm')
            
            # Get tenant B data
            tenant_b = tenants_data['tenant_b']['tenant']
            user_b = tenants_data['tenant_b']['user']
            
            # Verify user B doesn't have tenant A's roles
            assert not user_b.has_role('Manager')  # Different tenant's Manager role
            assert not user_b.has_role('Support')  # Different tenant's Support role
    
    def test_cross_tenant_role_assignment_prevention(self, app, multi_tenant_setup):
        """Test that users cannot be assigned roles from other tenants."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Get user from tenant A and role from tenant B
            user_a = tenants_data['tenant_a']['user']
            tenant_b = tenants_data['tenant_b']['tenant']
            
            manager_role_b = Role.query.filter_by(
                tenant_id=tenant_b.id,
                name='Manager'
            ).first()
            
            # Attempt to assign tenant B's role to tenant A's user
            # This should be prevented by application logic
            with pytest.raises(ValueError, match="Role belongs to different tenant"):
                user_a.add_role(manager_role_b)
    
    def test_permission_inheritance_isolation(self, app, multi_tenant_setup):
        """Test that permission inheritance is isolated between tenants."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Create custom roles with different permissions for each tenant
            tenant_a = tenants_data['tenant_a']['tenant']
            tenant_b = tenants_data['tenant_b']['tenant']
            
            # Custom role for tenant A with specific permissions
            custom_role_a = Role(
                tenant_id=tenant_a.id,
                name='SAP Specialist',
                description='SAP-specific role'
            )
            custom_role_a.set_permissions(['manage_crm', 'view_analytics', 'manage_kyb'])
            custom_role_a.save()
            
            # Custom role for tenant B with different permissions
            custom_role_b = Role(
                tenant_id=tenant_b.id,
                name='Azure Specialist',
                description='Azure-specific role'
            )
            custom_role_b.set_permissions(['view_crm', 'manage_calendar', 'view_knowledge'])
            custom_role_b.save()
            
            # Assign roles to users
            user_a = tenants_data['tenant_a']['user']
            user_b = tenants_data['tenant_b']['user']
            
            user_a.add_role(custom_role_a)
            user_b.add_role(custom_role_b)
            
            user_a.save()
            user_b.save()
            
            # Verify permission isolation
            assert user_a.has_permission('manage_crm')
            assert user_a.has_permission('view_analytics')
            assert user_a.has_permission('manage_kyb')
            assert not user_a.has_permission('manage_calendar')  # Not in their role
            
            assert user_b.has_permission('view_crm')
            assert user_b.has_permission('manage_calendar')
            assert user_b.has_permission('view_knowledge')
            assert not user_b.has_permission('manage_kyb')  # Not in their role
            
            # Verify users don't inherit permissions from other tenants
            assert not user_a.has_permission('azure_specific_permission')
            assert not user_b.has_permission('sap_specific_permission')


class TestTenantDataCleanup:
    """Test tenant data cleanup and deletion scenarios."""
    
    def test_tenant_deactivation_isolation(self, app, multi_tenant_setup):
        """Test that tenant deactivation doesn't affect other tenants."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Deactivate tenant A
            tenant_a = tenants_data['tenant_a']['tenant']
            tenant_a.is_active = False
            tenant_a.save()
            
            # Verify tenant A is deactivated
            assert not tenant_a.is_active
            
            # Verify other tenants are still active
            tenant_b = tenants_data['tenant_b']['tenant']
            tenant_c = tenants_data['tenant_c']['tenant']
            
            assert tenant_b.is_active
            assert tenant_c.is_active
            
            # Verify tenant A users are affected
            user_a = tenants_data['tenant_a']['user']
            owner_a = tenants_data['tenant_a']['owner']
            
            # Users should still exist but tenant is inactive
            assert user_a.tenant.is_active is False
            assert owner_a.tenant.is_active is False
            
            # Verify other tenant users are unaffected
            user_b = tenants_data['tenant_b']['user']
            user_c = tenants_data['tenant_c']['user']
            
            assert user_b.tenant.is_active is True
            assert user_c.tenant.is_active is True
    
    def test_tenant_data_soft_deletion(self, app, multi_tenant_setup):
        """Test soft deletion of tenant data maintains isolation."""
        with app.app_context():
            tenants_data = multi_tenant_setup
            
            # Create some data for tenant A
            tenant_a = tenants_data['tenant_a']['tenant']
            contact_a = Contact(
                tenant_id=tenant_a.id,
                name="Test Contact A",
                email="test@a.com",
                created_by_id=tenants_data['tenant_a']['owner'].id
            )
            contact_a.save()
            
            # Create some data for tenant B
            tenant_b = tenants_data['tenant_b']['tenant']
            contact_b = Contact(
                tenant_id=tenant_b.id,
                name="Test Contact B",
                email="test@b.com",
                created_by_id=tenants_data['tenant_b']['owner'].id
            )
            contact_b.save()
            
            # Soft delete tenant A's contact
            contact_a.is_deleted = True
            contact_a.deleted_at = datetime.utcnow()
            contact_a.save()
            
            # Verify tenant A's contact is soft deleted
            active_contacts_a = Contact.query.filter_by(
                tenant_id=tenant_a.id,
                is_deleted=False
            ).all()
            assert len(active_contacts_a) == 0
            
            # Verify tenant B's contact is unaffected
            active_contacts_b = Contact.query.filter_by(
                tenant_id=tenant_b.id,
                is_deleted=False
            ).all()
            assert len(active_contacts_b) == 1
            assert active_contacts_b[0].name == "Test Contact B"
            
            # Verify soft deleted data is still isolated
            deleted_contacts_a = Contact.query.filter_by(
                tenant_id=tenant_a.id,
                is_deleted=True
            ).all()
            assert len(deleted_contacts_a) == 1
            assert deleted_contacts_a[0].name == "Test Contact A"
            
            # Verify tenant B cannot see tenant A's deleted data
            all_contacts_b = Contact.query.filter_by(
                tenant_id=tenant_b.id
            ).all()
            contact_names_b = [c.name for c in all_contacts_b]
            assert "Test Contact A" not in contact_names_b